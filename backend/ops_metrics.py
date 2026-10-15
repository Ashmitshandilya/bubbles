"""Pure aggregation of telemetry events (ops_telemetry) into what the admin portal shows. No I/O, so every number is testable.

Every figure comes from recorded events; nothing is estimated. A comparison ("slowest", "most reliable") needs at least
MIN_SAMPLE attempts, otherwise it says there is not enough data yet.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Iterable

MIN_SAMPLE = 10


def percentile(values: list[float], p: float) -> float | None:
    """Nearest-rank percentile (p in 0..100); None for no values."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, -(-len(ordered) * p // 100))  # ceil
    return round(ordered[int(rank) - 1], 1)


def _lat(values: list[float]) -> dict[str, float | None]:
    return {"avg": round(sum(values) / len(values), 1) if values else None,
            "p50": percentile(values, 50), "p95": percentile(values, 95), "p99": percentile(values, 99)}


def _rate(part: int, whole: int) -> float | None:
    return round(part / whole, 3) if whole else None


def _of(events: Iterable[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    return [e for e in events if e.get("kind") == kind]


def ai_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    replies = _of(events, "ai_reply")
    attempts = _of(events, "ai_attempt")
    chats = [e["data"] for e in _of(events, "api") if e["data"].get("route") == "/chat"]
    answered = [r for r in replies if r["data"].get("outcome") == "answered"]
    totals = [r["data"].get("total_ms") for r in replies if r["data"].get("total_ms") is not None]
    return {
        "chat_turns": len(chats),
        "ai_called": sum(1 for c in chats if c.get("ai_called")),
        "answered_without_ai": sum(1 for c in chats if c.get("ai_called") is False),
        "safety_gated": sum(1 for c in chats if c.get("safety_level") == "RED"),
        "replies": len(replies),
        "answered": len(answered),
        "degraded": sum(1 for r in replies if r["data"].get("outcome") == "degraded"),
        "fallback_used": sum(1 for r in answered if r["data"].get("fallback_used")),
        "attempts": len(attempts),
        "failed_attempts": sum(1 for a in attempts if a["data"].get("outcome") != "success"),
        "timeouts": sum(1 for a in attempts if a["data"].get("outcome") in {"timeout", "budget_spent"}),
        "success_rate": _rate(len(answered), len(replies)),
        "reply_ms": _lat(totals),
        "stage_ms": stage_latency(chats),
    }


def stage_latency(api_events: list[dict[str, Any]]) -> dict[str, dict[str, float | None]]:
    """p50 / p95 per chat stage (pre, ctx, rag, ai, post) from the numbers chat turns recorded. A stage nobody timed has no numbers."""
    out: dict[str, dict[str, float | None]] = {}
    for stage in ("pre", "ctx", "rag", "ai", "post"):
        values = [float(d[f"stage_{stage}_ms"]) for d in api_events if isinstance(d.get(f"stage_{stage}_ms"), (int, float))]
        out[stage] = {"n": len(values), **{k: v for k, v in _lat(values).items() if k in ("p50", "p95")}}
    return out


def provider_table(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    attempts = _of(events, "ai_attempt")
    replies = [r for r in _of(events, "ai_reply") if r["data"].get("outcome") == "answered"]
    finals = Counter((r["data"].get("provider"), r["data"].get("model")) for r in replies)
    groups: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
    for a in attempts:
        groups[(a["data"].get("provider"), a["data"].get("model"))].append(a)
    rows = []
    for (provider, model), items in groups.items():
        data = [i["data"] for i in items]
        ok = [i for i in items if i["data"].get("outcome") == "success"]
        bad = [i for i in items if i["data"].get("outcome") != "success"]
        lat = [d["latency_ms"] for d in data if d.get("latency_ms") is not None]
        positions = [d.get("position") or 1 for d in data]
        rows.append({
            "provider": provider, "model": model, "requests": len(items), "successful": len(ok), "failed": len(bad),
            "success_rate": _rate(len(ok), len(items)),
            "timeout_rate": _rate(sum(1 for d in data if d.get("outcome") in {"timeout", "budget_spent"}), len(items)),
            "first_choice_rate": _rate(sum(1 for p in positions if p == 1), len(items)),
            "avg_position": round(sum(positions) / len(positions), 2),
            "final_answers": finals.get((provider, model), 0),
            "final_share": _rate(finals.get((provider, model), 0), len(replies)),
            "latency_ms": _lat(lat),
            "error_categories": dict(Counter(d.get("error_category") or "unknown" for d in (i["data"] for i in bad))),
            "last_success_at": max((i["at"] for i in ok), default=None),
            "last_failure_at": max((i["at"] for i in bad), default=None),
        })
    return sorted(rows, key=lambda r: (-r["final_answers"], -r["requests"]))


def highlights(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Who answers most, who fails most, who is slowest, who is most reliable. None = not enough data yet."""
    sampled = [r for r in rows if r["requests"] >= MIN_SAMPLE]
    pick = lambda r: {"provider": r["provider"], "model": r["model"]}  # noqa: E731
    most = max(rows, key=lambda r: r["final_answers"], default=None)
    return {
        "most_answers": {**pick(most), "final_answers": most["final_answers"], "final_share": most["final_share"]}
        if most and most["final_answers"] else None,
        "most_failing": (lambda r: {**pick(r), "failure_rate": round(1 - r["success_rate"], 3)})(
            max(sampled, key=lambda r: 1 - r["success_rate"])) if sampled else None,
        "slowest": (lambda r: {**pick(r), "p95_ms": r["latency_ms"]["p95"]})(
            max(sampled, key=lambda r: r["latency_ms"]["p95"] or 0)) if sampled else None,
        "most_reliable": (lambda r: {**pick(r), "success_rate": r["success_rate"], "p50_ms": r["latency_ms"]["p50"]})(
            max(sampled, key=lambda r: (r["success_rate"], -(r["latency_ms"]["p50"] or 0)))) if sampled else None,
        "min_sample": MIN_SAMPLE,
    }


def fallback_chain(events: list[dict[str, Any]], chain: list[str]) -> dict[str, Any]:
    """For the configured order: how many replies reached each step, were answered there, or moved on; and how many ran out."""
    by_request: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for a in _of(events, "ai_attempt"):
        if a.get("request_id"):
            by_request[a["request_id"]].append(a["data"])
    steps = {name: {"provider": name, "reached": 0, "answered": 0, "moved_on": 0} for name in chain}
    ran_out = 0
    transitions: Counter = Counter()
    for attempts in by_request.values():
        ordered = sorted(attempts, key=lambda d: d.get("position") or 0)
        for i, d in enumerate(ordered):
            step = steps.setdefault(d.get("provider"), {"provider": d.get("provider"), "reached": 0, "answered": 0, "moved_on": 0})
            step["reached"] += 1
            if d.get("outcome") == "success":
                step["answered"] += 1
                break
            step["moved_on"] += 1
            nxt = ordered[i + 1]["provider"] if i + 1 < len(ordered) else "degraded reply"
            transitions[(d.get("provider"), nxt)] += 1
        else:
            if ordered:
                ran_out += 1
    return {
        "steps": [steps[name] for name in chain] + [s for name, s in steps.items() if name not in chain],
        "transitions": [{"from": a, "to": b, "count": c} for (a, b), c in transitions.most_common()],
        "ran_out": ran_out,
        "requests": len(by_request),
    }


def api_table(events: list[dict[str, Any]], since: datetime, until: datetime, buckets: int = 12) -> list[dict[str, Any]]:
    groups: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
    for e in _of(events, "api"):
        groups[(e["data"].get("method"), e["data"].get("route"))].append(e)
    span = max((until - since).total_seconds(), 1.0)
    rows = []
    for (method, route), items in groups.items():
        data = [i["data"] for i in items]
        lat = [d["latency_ms"] for d in data if d.get("latency_ms") is not None]
        status = [int(d.get("status") or 0) for d in data]
        trend = [0] * buckets
        for i in items:
            at = datetime.fromisoformat(i["at"])
            trend[min(buckets - 1, max(0, int((at - since).total_seconds() / span * buckets)))] += 1
        errors = [i for i in items if int(i["data"].get("status") or 0) >= 500]
        rows.append({
            "method": method, "route": route, "requests": len(items),
            "success_rate": _rate(sum(1 for s in status if s < 400), len(items)),
            "client_errors": sum(1 for s in status if 400 <= s < 500),
            "server_errors": sum(1 for s in status if s >= 500),
            "latency_ms": _lat(lat), "slowest_ms": max(lat, default=None),
            "last_server_error_at": max((i["at"] for i in errors), default=None), "trend": trend,
        })
    return sorted(rows, key=lambda r: -r["requests"])


def api_summary(events: list[dict[str, Any]], since: datetime, until: datetime) -> dict[str, Any]:
    api = [e["data"] for e in _of(events, "api")]
    status = [int(d.get("status") or 0) for d in api]
    minutes = max((until - since).total_seconds() / 60, 1 / 60)
    return {
        "requests": len(api), "per_minute": round(len(api) / minutes, 2),
        "client_errors": sum(1 for s in status if 400 <= s < 500), "server_errors": sum(1 for s in status if s >= 500),
        "error_rate": _rate(sum(1 for s in status if s >= 500), len(api)),
        "latency_ms": _lat([d["latency_ms"] for d in api if d.get("latency_ms") is not None]),
    }


def error_summary(events: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(e["data"].get("category") or "internal" for e in _of(events, "error")))


def answering(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Who gave the answered replies in these events: the top provider/model, its share, and when the last reply was."""
    replies = [r for r in _of(events, "ai_reply") if r["data"].get("outcome") == "answered"]
    if not replies:
        return None
    counts = Counter((r["data"].get("provider"), r["data"].get("model")) for r in replies)
    (provider, model), n = counts.most_common(1)[0]
    return {"provider": provider, "model": model, "share": _rate(n, len(replies)), "n": len(replies),
            "last_reply_at": max(r["at"] for r in replies)}


def headline(*, database: str, persistence_mode: str, all_paused: bool, ai_now: dict[str, Any], api_now: dict[str, Any]) -> dict[str, Any]:
    """ok | warn | fail with the reasons in plain words. Thresholds live here and are tested."""
    fail, warn = [], []
    if database not in {"ok", "unknown"}:
        (warn if database == "permission_denied" else fail).append(f"Database check says {database.replace('_', ' ')}.")
    if all_paused:
        fail.append("Every AI provider is paused, so everyone gets the calm message.")
    replies = ai_now.get("replies") or 0
    if replies >= MIN_SAMPLE and (ai_now.get("success_rate") or 0) < 0.5:
        fail.append("Most AI replies in the last 5 minutes could not be answered.")
    elif ai_now.get("degraded"):
        warn.append(f"{ai_now['degraded']} AI repl{'y' if ai_now['degraded'] == 1 else 'ies'} in the last 5 minutes got the calm message.")
    if (api_now.get("requests") or 0) >= MIN_SAMPLE and (api_now.get("error_rate") or 0) > 0.05:
        warn.append("More than 5% of requests in the last 5 minutes ended in a server error.")
    if persistence_mode != "stored":
        warn.append("Logs are kept in memory only." if persistence_mode in {"memory_only", "not_set_up"} else "Saving logs is failing.")
    return {"status": "fail" if fail else "warn" if warn else "ok", "reasons": fail + warn}
