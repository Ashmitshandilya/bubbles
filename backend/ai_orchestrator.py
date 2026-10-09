"""Policy-driven routing, budget estimation and model-cost governance."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Route:
    provider: str
    tier: str
    reason: str


@dataclass(frozen=True)
class Price:
    provider: str
    model: str
    input_per_million: float | None
    output_per_million: float | None
    cached_input_per_million: float | None = None
    effective_date: str = "2026-09-19"
    source: str = "provider pricing documentation"


# Versioned, model-specific prices where the provider publishes a current rate.
# Unknown prices stay None instead of pretending an API is free.
PRICES = {
    ("groq", "openai/gpt-oss-20b"): Price("Groq", "openai/gpt-oss-20b", 0.075, 0.30, 0.0375, source="Groq model pricing"),
    ("groq", "openai/gpt-oss-120b"): Price("Groq", "openai/gpt-oss-120b", 0.15, 0.60, 0.075, source="Groq model pricing"),
    ("mistral", "ministral-3b-latest"): Price("Mistral", "ministral-3b-latest", 0.10, 0.10, 0.01, source="Mistral API pricing"),
    ("mistral", "ministral-8b-latest"): Price("Mistral", "ministral-8b-latest", 0.15, 0.15, 0.015, source="Mistral API pricing"),
    ("mistral", "ministral-14b-latest"): Price("Mistral", "ministral-14b-latest", 0.20, 0.20, 0.02, source="Mistral API pricing"),
    ("mistral", "mistral-small-latest"): Price("Mistral", "mistral-small-latest", 0.15, 0.60, 0.015, source="Mistral API pricing"),
}

# Optional deployment-specific overrides. Set both input/output to a numeric
# value to replace the published baseline for that provider/model.
def _env_price(provider: str, model: str) -> Price | None:
    key = f"BUBBLES_PRICE_{provider}_{model}".upper().replace("/", "_").replace("-", "_").replace(".", "_")
    raw = os.getenv(key)
    if not raw:
        return None
    try:
        input_rate, output_rate = [float(x.strip()) for x in raw.split(",", 1)]
    except (ValueError, TypeError):
        return None
    return Price(provider, model, input_rate, output_rate, effective_date="deployment-override", source="BUBBLES pricing override")


def price_for(provider: str, model: str) -> Price | None:
    return _env_price(provider, model) or PRICES.get((provider.lower(), model))


def estimate_cost(provider: str, model: str, input_tokens: int, output_tokens: int, cached_tokens: int = 0) -> float | None:
    price = price_for(provider, model)
    if not price or price.input_per_million is None or price.output_per_million is None:
        return None
    input_tokens = max(0, int(input_tokens))
    output_tokens = max(0, int(output_tokens))
    cached_tokens = max(0, min(input_tokens, int(cached_tokens)))
    uncached_input = input_tokens - cached_tokens
    input_cost = uncached_input / 1_000_000 * price.input_per_million
    cached_cost = cached_tokens / 1_000_000 * (price.cached_input_per_million if price.cached_input_per_million is not None else price.input_per_million)
    return round(input_cost + cached_cost + output_tokens / 1_000_000 * price.output_per_million, 8)


def route(safety_level: str = "GREEN", sensitivity: str = "health", task: str = "chat", budget_remaining: float | None = None) -> Route:
    if safety_level.upper() == "RED":
        return Route("deterministic", "safety", "urgent safety routing must not depend on model choice")
    if sensitivity == "health":
        return Route("configured_secure_provider", "health", "use configured provider policy; do not send sensitive data to public keyless endpoints")
    if task in {"classification", "extraction"}:
        return Route("configured_fast_provider", "fast", "bounded structured task")
    return Route("configured_quality_provider", "quality", "general reasoning task")


def build_budget(input_tokens: int, output_tokens: int, provider: str = "configured", model: str = "configured", cached_tokens: int = 0) -> dict:
    return {
        "estimated_input_tokens": max(0, input_tokens),
        "estimated_output_tokens": max(0, output_tokens),
        "estimated_cached_tokens": max(0, cached_tokens),
        "estimated_cost_usd": estimate_cost(provider, model, input_tokens, output_tokens, cached_tokens),
        "provider": provider,
        "model": model,
        "pricing_status": "known" if price_for(provider, model) else "unknown",
    }


def sanitize_for_model(text: str, max_chars: int = 12000) -> str:
    return str(text or "")[:max_chars]
