"""Privacy-preserving AI request telemetry.

Stores only operational metadata: provider/model, position in the chain, token counts when a provider returns them, latency,
outcome and an error CATEGORY. Prompt/response text, error messages and API keys are never retained: an error's text is read
here only to sort it into a fixed category and is then dropped. Every attempt also goes to ops_telemetry (admin portal).
"""
from __future__ import annotations

import re
from collections import Counter, deque
from threading import Lock
from typing import Any

import ops_telemetry

_MAX_RECENT = 200
_lock = Lock()
_recent: deque[dict[str, Any]] = deque(maxlen=_MAX_RECENT)
_counts = Counter()

ERROR_CATEGORIES = ("timeout", "budget_spent", "rate_limited", "auth", "provider_error", "invalid_json", "not_configured", "network", "other")
_HTTP = re.compile(r"\bHTTP (\d{3})\b")


def classify_error(error: BaseException) -> str:
    """A fixed category for a provider failure (the text itself is never stored)."""
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:   # look through "no response received" to the timeout behind it
        seen.add(id(current))
        name, text = type(current).__name__.lower(), str(current).lower()
        if "budget is spent" in text:
            return "budget_spent"
        if "timeout" in name or "timed out" in text or "timeout" in text:
            return "timeout"
        if "not configured" in text or "not installed" in text or "no model configured" in text:
            return "not_configured"
        if "json" in text and ("invalid" in text or "decode" in text):
            return "invalid_json"
        status = _HTTP.search(str(current))
        if status:
            code = int(status.group(1))
            if code == 429:
                return "rate_limited"
            if code in (401, 403):
                return "auth"
            if code >= 500:
                return "provider_error"
        if "connection" in name or "connection" in text:
            return "network"
        current = current.__cause__ or current.__context__
    return "other"


def outcome_for(category: str) -> str:
    return category if category in {"timeout", "budget_spent", "invalid_json"} else "error"


def record(*, provider: str, model: str, latency_ms: float, outcome: str,
           usage: dict[str, int] | None = None, error_class: str | None = None,
           position: int | None = None, error_category: str | None = None) -> None:
    usage = usage or {}
    item = {
        "provider": provider,
        "model": model,
        "latency_ms": round(max(0.0, latency_ms), 1),
        "outcome": outcome,
        "input_tokens": int(usage.get("input_tokens", 0) or 0),
        "output_tokens": int(usage.get("output_tokens", 0) or 0),
        "total_tokens": int(usage.get("total_tokens", 0) or 0),
        "cached_tokens": int(usage.get("cached_tokens", 0) or 0),
    }
    if error_class:
        item["error_class"] = error_class
    with _lock:
        _recent.append(item)
        _counts[(provider, outcome)] += 1
    ops_telemetry.record("ai_attempt", provider=provider, model=model, position=position, outcome=outcome,
                         error_category=error_category, latency_ms=item["latency_ms"],
                         input_tokens=item["input_tokens"], output_tokens=item["output_tokens"],
                         total_tokens=item["total_tokens"], cached_tokens=item["cached_tokens"])


def snapshot() -> dict[str, Any]:
    with _lock:
        rows = list(_recent)
        counts = {f"{provider}:{outcome}": count for (provider, outcome), count in _counts.items()}
    total_tokens = sum(row["total_tokens"] for row in rows)
    input_tokens = sum(row["input_tokens"] for row in rows)
    output_tokens = sum(row["output_tokens"] for row in rows)
    return {
        "retained_recent_requests": len(rows),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "counts": counts,
        "recent": rows[-50:],
        "persistence": "process_memory_only",
    }
