import json
import os
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

import requests

import admin_settings


# ============================================================
# BUBBLES AI PROVIDER ROUTER
# ============================================================

# IMPORTANT:
# Bubbles never intentionally selects paid models.
# Set ALLOW_PAID_AI=true only if you explicitly want paid models.
ALLOW_PAID_AI = os.getenv("ALLOW_PAID_AI", "false").lower() == "true"
ALLOW_KEYLESS_AI = os.getenv("ALLOW_KEYLESS_AI", "false").lower() == "true"
ALLOW_KEYLESS_HEALTH_DATA = os.getenv("ALLOW_KEYLESS_HEALTH_DATA", "false").lower() == "true"

FREE_MODEL_ALLOWLIST = {
    "Groq": {"openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b", "qwen/qwen3.6-27b"},
    "NVIDIA": {"deepseek-ai/deepseek-v4-flash-0731", "nvidia/nemotron-3-super-120b-a12b", "nvidia/nemotron-3.5-lightning-30b-a3b", "openai/gpt-oss-20b"},
    "Mistral": {"ministral-14b-latest", "ministral-8b-latest", "ministral-3b-latest"},
    "KeylessAI": {"openai-fast"},
    "Kilo": {"kilo-auto/free"},
    "Murakumo": {"murakumo-main"},
    "BlockRun": {"nvidia/nemotron-3.5-lightning"},
    "Animica": {"kimi-k3"},
}

REQUEST_TIMEOUT = int(os.getenv("AI_REQUEST_TIMEOUT", "20"))
AI_MAX_RETRIES = max(0, min(int(os.getenv("AI_MAX_RETRIES", "1")), 2))
AI_RETRY_BACKOFF_MS = max(0, min(int(os.getenv("AI_RETRY_BACKOFF_MS", "250")), 2000))
# One chat reply waits at most this long for AI models in total (Gemini, then every fallback and retry). Without it a slow
# provider chain could take minutes, long after the person's browser and the website's proxy gave up on the request.
AI_REPLY_BUDGET = max(5.0, min(float(os.getenv("AI_REPLY_BUDGET_S", "50")), 90.0))
_MIN_CALL_SECONDS = 3.0
_deadline: ContextVar[float | None] = ContextVar("bubbles_ai_deadline", default=None)


@dataclass
class ProviderResult:
    provider: str
    model: str
    content: str
    usage: dict[str, int] | None = None
    latency_ms: float | None = None
    position: int | None = None


class ProviderError(Exception):
    pass


@contextmanager
def reply_budget(seconds: float | None = None):
    """Every provider call inside this block shares one deadline (an outer budget is kept, never extended)."""
    deadline = time.monotonic() + (AI_REPLY_BUDGET if seconds is None else seconds)
    outer = _deadline.get()
    token = _deadline.set(deadline if outer is None else min(outer, deadline))
    try:
        yield
    finally:
        _deadline.reset(token)


def call_timeout(cap: float = REQUEST_TIMEOUT) -> float:
    """Seconds the next provider call may take: its own cap, cut to what is left of the reply budget.
    Raises ProviderError when too little is left to be worth starting a call."""
    deadline = _deadline.get()
    if deadline is None:
        return cap
    remaining = deadline - time.monotonic()
    if remaining < _MIN_CALL_SECONDS:
        raise ProviderError("the reply time budget is spent")
    return min(cap, remaining)


# ============================================================
# HELPERS
# ============================================================

def _extract_json(text: str) -> dict[str, Any]:
    """
    Extract JSON even if a provider wraps it in markdown.
    """

    text = text.strip()

    if text.startswith("```"):
        lines = text.splitlines()

        if lines and lines[0].startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        text = "\n".join(lines).strip()

        if text.lower().startswith("json"):
            text = text[4:].strip()

    try:
        value = json.loads(text)

        if not isinstance(value, dict):
            raise ProviderError("Provider returned JSON but not an object.")

        return value

    except json.JSONDecodeError:

        start = text.find("{")
        end = text.rfind("}")

        if start != -1 and end != -1 and end > start:
            try:
                value = json.loads(text[start:end + 1])

                if isinstance(value, dict):
                    return value

            except json.JSONDecodeError:
                pass

        raise ProviderError(
            f"Provider returned invalid JSON: {text[:500]}"
        )


def _require_key(env_name: str) -> str:
    value = os.getenv(env_name)

    if not value:
        raise ProviderError(f"{env_name} is not configured.")

    return value


def _post_openai_compatible(
    provider: str,
    url: str,
    api_key: str,
    model: str,
    system_instruction: str,
    user_message: str,
) -> ProviderResult:

    if not model:
        raise ProviderError(f"{provider}: no model configured.")

    if not ALLOW_PAID_AI:
        allowed = FREE_MODEL_ALLOWLIST.get(provider)
        # Fail closed: a provider with no explicit free-model policy must not
        # become an accidental paid-model route when paid AI is disabled.
        if not allowed or model not in allowed:
            raise ProviderError(
                f"{provider}: model {model!r} is not on BUBBLES' explicit free-model allowlist."
            )

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": system_instruction,
            },
            {
                "role": "user",
                "content": user_message,
            },
        ],
        "temperature": 0.2,
    }

    last_error: Exception | None = None
    response = None
    for attempt in range(AI_MAX_RETRIES + 1):
        timeout = call_timeout()  # outside the try: a spent budget ends the retries instead of being swallowed
        try:
            response = requests.post(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=timeout,
            )
            if response.status_code == 429 or response.status_code >= 500:
                raise ProviderError(f"HTTP {response.status_code}")
            break
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as error:
            last_error = error
        except ProviderError as error:
            last_error = error
            if not (response is not None and (response.status_code == 429 or response.status_code >= 500)):
                raise
        except Exception as error:
            last_error = error
        if attempt < AI_MAX_RETRIES:
            time.sleep((AI_RETRY_BACKOFF_MS / 1000.0) * (2 ** attempt))


    if response is None:
        raise ProviderError(f"{provider}: no response received") from last_error

    if response.status_code >= 400:
        body = response.text[:1000]
        raise ProviderError(f"{provider}: HTTP {response.status_code}: {body}")

    try:
        data = response.json()

    except ValueError as error:
        raise ProviderError(
            f"{provider}: response was not JSON."
        ) from error

    try:
        content = data["choices"][0]["message"]["content"]

    except (KeyError, IndexError, TypeError) as error:
        raise ProviderError(
            f"{provider}: unexpected response format: "
            f"{json.dumps(data)[:1000]}"
        ) from error

    if isinstance(content, list):
        parts = []

        for item in content:
            if isinstance(item, dict) and item.get("text"):
                parts.append(str(item["text"]))

        content = "".join(parts)

    if not isinstance(content, str) or not content.strip():
        raise ProviderError(
            f"{provider}: empty model response."
        )

    usage = data.get("usage") if isinstance(data, dict) else None
    normalized_usage: dict[str, int] = {}
    if isinstance(usage, dict):
        normalized_usage = {
            "input_tokens": int(usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0),
            "output_tokens": int(usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0),
            "total_tokens": int(usage.get("total_tokens", 0) or 0),
            "cached_tokens": int((usage.get("prompt_tokens_details") or {}).get("cached_tokens", usage.get("cached_tokens", 0)) or 0) if isinstance(usage.get("prompt_tokens_details", {}), dict) else int(usage.get("cached_tokens", 0) or 0),
        }
        if not normalized_usage["total_tokens"]:
            normalized_usage["total_tokens"] = normalized_usage["input_tokens"] + normalized_usage["output_tokens"]

    return ProviderResult(
        provider=provider,
        model=model,
        content=content.strip(),
        usage=normalized_usage,
    )


# ============================================================
# OPENAI-COMPATIBLE PROVIDERS
# ============================================================

def call_groq(system_instruction: str, user_message: str) -> ProviderResult:
    return _post_openai_compatible(
        provider="Groq",
        url=os.getenv(
            "GROQ_BASE_URL",
            "https://api.groq.com/openai/v1/chat/completions",
        ),
        api_key=_require_key("GROQ_API_KEY"),
        model=os.getenv(
            "GROQ_MODEL",
            "openai/gpt-oss-20b",
        ),
        system_instruction=system_instruction,
        user_message=user_message,
    )


def call_nvidia(system_instruction: str, user_message: str) -> ProviderResult:
    return _post_openai_compatible(
        provider="NVIDIA",
        url=os.getenv(
            "NVIDIA_BASE_URL",
            "https://integrate.api.nvidia.com/v1/chat/completions",
        ),
        api_key=_require_key("NVIDIA_API_KEY"),
        model=os.getenv(
            "NVIDIA_MODEL",
            "nvidia/nemotron-3.5-lightning-30b-a3b",
        ),
        system_instruction=system_instruction,
        user_message=user_message,
    )


def call_zai(system_instruction: str, user_message: str) -> ProviderResult:
    return _post_openai_compatible(
        provider="Z.AI",
        url=os.getenv(
            "ZAI_BASE_URL",
            "https://api.z.ai/api/paas/v4/chat/completions",
        ),
        api_key=_require_key("ZAI_API_KEY"),
        model=os.getenv(
            "ZAI_MODEL",
            "glm-4.7-flash",
        ),
        system_instruction=system_instruction,
        user_message=user_message,
    )


def call_aiml(system_instruction: str, user_message: str) -> ProviderResult:
    return _post_openai_compatible(
        provider="AIML API",
        url=os.getenv(
            "AIML_BASE_URL",
            "https://api.aimlapi.com/v1/chat/completions",
        ),
        api_key=_require_key("AIML_API_KEY"),
        model=os.getenv(
            "AIML_MODEL",
            "openai/gpt-oss-20b",
        ),
        system_instruction=system_instruction,
        user_message=user_message,
    )


def call_sambanova(
    system_instruction: str,
    user_message: str,
) -> ProviderResult:

    return _post_openai_compatible(
        provider="SambaNova",
        url=os.getenv(
            "SAMBANOVA_BASE_URL",
            "https://api.sambanova.ai/v1/chat/completions",
        ),
        api_key=_require_key("SAMBANOVA_API_KEY"),
        model=os.getenv(
            "SAMBANOVA_MODEL",
            "Meta-Llama-3.3-70B-Instruct",
        ),
        system_instruction=system_instruction,
        user_message=user_message,
    )


def call_hyperbolic(
    system_instruction: str,
    user_message: str,
) -> ProviderResult:

    return _post_openai_compatible(
        provider="Hyperbolic",
        url=os.getenv(
            "HYPERBOLIC_BASE_URL",
            "https://api.hyperbolic.xyz/v1/chat/completions",
        ),
        api_key=_require_key("HYPERBOLIC_API_KEY"),
        model=os.getenv(
            "HYPERBOLIC_MODEL",
            "openai/gpt-oss-120b",
        ),
        system_instruction=system_instruction,
        user_message=user_message,
    )


def call_mistral(
    system_instruction: str,
    user_message: str,
) -> ProviderResult:

    return _post_openai_compatible(
        provider="Mistral",
        url=os.getenv(
            "MISTRAL_BASE_URL",
            "https://api.mistral.ai/v1/chat/completions",
        ),
        api_key=_require_key("MISTRAL_API_KEY"),
        model=os.getenv(
            "MISTRAL_MODEL",
            "ministral-14b-latest",
        ),
        system_instruction=system_instruction,
        user_message=user_message,
    )


def call_cerebras(
    system_instruction: str,
    user_message: str,
) -> ProviderResult:

    return _post_openai_compatible(
        provider="Cerebras",
        url=os.getenv(
            "CEREBRAS_BASE_URL",
            "https://api.cerebras.ai/v1/chat/completions",
        ),
        api_key=_require_key("CEREBRAS_API_KEY"),
        model=os.getenv(
            "CEREBRAS_MODEL",
            "gpt-oss-120b",
        ),
        system_instruction=system_instruction,
        user_message=user_message,
    )


# ============================================================
# CLOUDFLARE WORKERS AI
# ============================================================

def call_cloudflare(
    system_instruction: str,
    user_message: str,
) -> ProviderResult:

    account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID")
    api_token = os.getenv("CLOUDFLARE_API_TOKEN")

    if not account_id:
        raise ProviderError(
            "Cloudflare: CLOUDFLARE_ACCOUNT_ID is not configured."
        )

    if not api_token:
        raise ProviderError(
            "Cloudflare: CLOUDFLARE_API_TOKEN is not configured."
        )

    model = os.getenv(
        "CLOUDFLARE_MODEL",
        "@cf/meta/llama-3.1-8b-instruct",
    )

    url = (
        f"https://api.cloudflare.com/client/v4/"
        f"accounts/{account_id}/ai/run/{model}"
    )

    payload = {
        "messages": [
            {
                "role": "system",
                "content": system_instruction,
            },
            {
                "role": "user",
                "content": user_message,
            },
        ]
    }

    try:
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=call_timeout(),
        )

    except requests.RequestException as error:
        raise ProviderError(
            f"Cloudflare: network error: {error}"
        ) from error

    if response.status_code >= 400:
        raise ProviderError(
            f"Cloudflare: HTTP {response.status_code}: "
            f"{response.text[:1000]}"
        )

    try:
        data = response.json()

    except ValueError as error:
        raise ProviderError(
            "Cloudflare: response was not JSON."
        ) from error

    if not data.get("success", False):
        raise ProviderError(
            f"Cloudflare returned failure: {json.dumps(data)[:1000]}"
        )

    result = data.get("result")

    if isinstance(result, dict):
        content = (
            result.get("response")
            or result.get("text")
            or result.get("output")
        )

    else:
        content = result

    if not isinstance(content, str) or not content.strip():
        raise ProviderError(
            f"Cloudflare: unexpected response: "
            f"{json.dumps(data)[:1000]}"
        )

    return ProviderResult(
        provider="Cloudflare",
        model=model,
        content=content.strip(),
    )



# ============================================================
# KEYLESS AI
# ============================================================

def call_keyless(
    system_instruction: str,
    user_message: str,
) -> ProviderResult:

    base_url = os.getenv(
        "KEYLESS_AI_BASE_URL",
        "https://keylessai.thryx.workers.dev/v1",
    )

    model = os.getenv(
        "KEYLESS_AI_MODEL",
        "openai-fast",
    )

    url = f"{base_url.rstrip('/')}/chat/completions"

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": system_instruction,
            },
            {
                "role": "user",
                "content": user_message,
            },
        ],
        "temperature": 0.2,
    }

    try:
        response = requests.post(
            url,
            headers={
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=call_timeout(),
        )

    except requests.RequestException as error:
        raise ProviderError(
            f"KeylessAI: network error: {error}"
        ) from error

    if response.status_code >= 400:
        raise ProviderError(
            f"KeylessAI: HTTP {response.status_code}: "
            f"{response.text[:1000]}"
        )

    try:
        data = response.json()

    except ValueError as error:
        raise ProviderError(
            "KeylessAI: response was not JSON."
        ) from error

    try:
        content = data["choices"][0]["message"]["content"]

    except (KeyError, IndexError, TypeError) as error:
        raise ProviderError(
            f"KeylessAI: unexpected response format: "
            f"{json.dumps(data)[:1000]}"
        ) from error

    if isinstance(content, list):
        parts = []

        for item in content:
            if isinstance(item, dict) and item.get("text"):
                parts.append(str(item["text"]))

        content = "".join(parts)

    if not isinstance(content, str) or not content.strip():
        raise ProviderError(
            "KeylessAI: empty model response."
        )

    return ProviderResult(
        provider="KeylessAI",
        model=model,
        content=content.strip(),
    )

def _call_keyless_compatible(
    provider: str,
    base_url: str,
    model: str,
    system_instruction: str,
    user_message: str,
) -> ProviderResult:
    if not ALLOW_KEYLESS_AI:
        raise ProviderError(f"{provider}: keyless providers are disabled.")
    # Public keyless endpoints are not approved for real health data by default.
    if not ALLOW_KEYLESS_HEALTH_DATA:
        raise ProviderError(
            f"{provider}: disabled for health data; use only synthetic/test prompts."
        )
    return _post_openai_compatible(
        provider=provider,
        url=f"{base_url.rstrip('/')}/chat/completions",
        api_key="not-needed",
        model=model,
        system_instruction=system_instruction,
        user_message=user_message,
    )


def call_kilo(system_instruction: str, user_message: str) -> ProviderResult:
    return _call_keyless_compatible(
        "Kilo",
        os.getenv("KILO_BASE_URL", "https://api.kilo.ai/api/openrouter"),
        os.getenv("KILO_MODEL", "kilo-auto/free"),
        system_instruction, user_message,
    )


def call_murakumo(system_instruction: str, user_message: str) -> ProviderResult:
    return _call_keyless_compatible(
        "Murakumo",
        os.getenv("MURAKUMO_BASE_URL", "https://api.murakumo.cloud/v1"),
        os.getenv("MURAKUMO_MODEL", "murakumo-main"),
        system_instruction, user_message,
    )


def call_blockrun(system_instruction: str, user_message: str) -> ProviderResult:
    return _call_keyless_compatible(
        "BlockRun",
        os.getenv("BLOCKRUN_BASE_URL", "https://blockrun.ai/api/v1"),
        os.getenv("BLOCKRUN_MODEL", "nvidia/nemotron-3.5-lightning"),
        system_instruction, user_message,
    )


def call_animica(system_instruction: str, user_message: str) -> ProviderResult:
    return _call_keyless_compatible(
        "Animica",
        os.getenv("ANIMICA_BASE_URL", "https://animica.dev/v1"),
        os.getenv("ANIMICA_MODEL", "kimi-k3"),
        system_instruction, user_message,
    )


# ============================================================
# PROVIDER ORDER
# ============================================================

# Keyless providers are deliberately NOT part of the default pool. A health
# request must never fall through to an unauthenticated public endpoint just
# because keyed providers are temporarily unavailable.
AUTHENTICATED_PROVIDERS = [
    ("Groq", call_groq),
    ("NVIDIA", call_nvidia),
    ("Mistral", call_mistral),
]

KEYLESS_PROVIDERS = [
    ("KeylessAI", call_keyless),
    ("Kilo", call_kilo),
    ("Murakumo", call_murakumo),
    ("BlockRun", call_blockrun),
    ("Animica", call_animica),
]


def provider_pool(*, health_data: bool) -> list[tuple[str, Any]]:
    providers = list(AUTHENTICATED_PROVIDERS)
    if ALLOW_KEYLESS_AI and (not health_data or ALLOW_KEYLESS_HEALTH_DATA):
        providers.extend(KEYLESS_PROVIDERS)
    # After the policy gate: an administrator's pause can only remove a provider, never add or reorder one (admin_settings).
    return [(name, fn) for name, fn in providers if not admin_settings.is_paused(name)]


# ============================================================
# FALLBACK ROUTER
# ============================================================

def call_fallback(
    system_instruction: str,
    user_message: str,
    *,
    health_data: bool = False,
    first_position: int = 1,
    defer_success: bool = False,
) -> ProviderResult:
    """Tries the pool in order. ``first_position`` numbers the attempts after earlier ones (Gemini). With ``defer_success`` the
    caller records the successful attempt itself, after checking the answer is usable (so telemetry never counts a reply that
    was thrown away as an answer)."""

    errors = []

    for position, (provider_name, provider_function) in enumerate(provider_pool(health_data=health_data), start=first_position):

        started = time.perf_counter()

        try:
            result = provider_function(
                system_instruction=system_instruction,
                user_message=user_message,
            )

            elapsed = time.perf_counter() - started
            result.latency_ms = elapsed * 1000
            result.position = position

            from logging_util import logger
            logger.info(
                component="AI_PROVIDER",
                message=f"provider_call succeeded: {provider_name} model={result.model} elapsed={round(elapsed, 2)}s",
                context={"provider": provider_name, "model": result.model, "elapsed_seconds": round(elapsed, 2)},
            )
            if not defer_success:
                try:
                    from ai_telemetry import record
                    record(provider=provider_name, model=result.model, latency_ms=elapsed * 1000, outcome="success", usage=result.usage,
                           position=position)
                except Exception:
                    pass
            return result

        except Exception as error:

            elapsed = time.perf_counter() - started

            message = str(error)

            errors.append(
                f"{provider_name}: {message}"
            )

            from logging_util import logger
            logger.error(
                component="AI_PROVIDER",
                operation="provider_call",
                error=error,
                context={"provider": provider_name, "elapsed_seconds": round(elapsed, 2)},
            )
            try:
                from ai_telemetry import classify_error, outcome_for, record
                category = classify_error(error)
                record(provider=provider_name, model=os.getenv(f"{provider_name.upper()}_MODEL", "unknown"), latency_ms=elapsed * 1000,
                       outcome=outcome_for(category), error_class=type(error).__name__, position=position, error_category=category)
            except Exception:
                pass
            continue

    raise ProviderError(
        "All fallback AI providers failed:\n"
        + "\n".join(errors)
    )



