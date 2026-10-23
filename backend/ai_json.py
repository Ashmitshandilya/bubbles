"""One structured answer from the language model, for features that are not the chat (Orbit's reply helper and repair draft).

Gemini first, then the keyed fallback pool, exactly as the chat does, under one reply deadline. The caller gives a ``validate`` function that turns the
parsed JSON into the value it wants (or raises); anything that fails to parse or validate counts as no answer, and the caller uses its own fixed text.
Nothing here decides who may call it: the caller checks the person's yes to outside-AI processing first and sends no name, no safety content.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any, Callable, TypeVar

import admin_settings
from ai_provider import MAX_OUTPUT_TOKENS, ProviderError, call_fallback, call_timeout, reply_budget

T = TypeVar("T")


def _log(operation: str, error: Exception) -> None:
    try:
        from logging_util import logger
        logger.warning(component="AI_JSON", operation=operation, error=error, fallback_action="next_provider")
    except Exception:  # noqa: BLE001
        pass


def _gemini_text(system_instruction: str, message: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ProviderError("GEMINI_API_KEY is not configured.")
    from google import genai
    from google.genai import types
    from bubbles_ai import _gemini_client, _thinking_config
    timeout = call_timeout(float(os.getenv("GEMINI_TIMEOUT_S", "9")))
    client = _gemini_client(api_key, genai, types)
    settings = dict(system_instruction=system_instruction, temperature=0.4, response_mime_type="application/json", max_output_tokens=MAX_OUTPUT_TOKENS,
                    http_options=types.HttpOptions(timeout=int(timeout * 1000)))
    thinking = _thinking_config(types)
    model = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
    started = time.perf_counter()
    try:
        response = client.models.generate_content(model=model, contents=message,
                                                  config=types.GenerateContentConfig(**settings, **({"thinking_config": thinking} if thinking is not None else {})))
    except Exception as error:  # noqa: BLE001
        if thinking is None or "thinking" not in str(error).lower():
            raise
        response = client.models.generate_content(model=model, contents=message, config=types.GenerateContentConfig(**settings))
    if not response.text:
        raise ProviderError("Gemini returned an empty response.")
    try:
        from ai_telemetry import record
        record(provider="Gemini", model=model, latency_ms=(time.perf_counter() - started) * 1000, outcome="success", usage={}, position=1)
    except Exception:  # noqa: BLE001
        pass
    return response.text


def ask_json(system_instruction: str, message: str, validate: Callable[[Any], T]) -> T | None:
    """The validated answer, or None when no provider gave a usable one."""
    with reply_budget():
        if not admin_settings.is_paused("Gemini"):
            try:
                return validate(json.loads(_gemini_text(system_instruction, message)))
            except Exception as error:  # noqa: BLE001
                _log("gemini", error)
        try:
            result = call_fallback(system_instruction=system_instruction, user_message=message, health_data=True, first_position=2)
            return validate(json.loads(result.content))
        except Exception as error:  # noqa: BLE001
            _log("fallback", error)
    return None
