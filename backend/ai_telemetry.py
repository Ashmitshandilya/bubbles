"""Privacy-preserving in-process AI request telemetry.

Stores only operational metadata: provider/model, token counts when a provider
returns them, latency, outcome and error class. Prompt/response text and API
keys are never retained.
"""
from __future__ import annotations

from collections import Counter, deque
from threading import Lock
from typing import Any

_MAX_RECENT = 200
_lock = Lock()
_recent: deque[dict[str, Any]] = deque(maxlen=_MAX_RECENT)
_counts = Counter()


def record(*, provider: str, model: str, latency_ms: float, outcome: str,
           usage: dict[str, int] | None = None, error_class: str | None = None) -> None:
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
