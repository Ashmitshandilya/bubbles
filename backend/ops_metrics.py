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
    }


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


# ---------------------------------------------------------------- Overall page (counters from ops_rollups.count_events)

# Cost is computed here, at read time, never stored. Every provider in the chat chain is on a free tier ($0 AI policy), so the
# honest figure is zero; a provider not listed here is "unknown" instead of a made-up number.
FREE_TIER = frozenset({"Gemini", "Groq", "NVIDIA", "Mistral"})
FEATURES: tuple[tuple[str, str], ...] = (
    ("/chat", "Chat"), ("/onboarding", "Onboarding"), ("/experience", "Onboarding"), ("/wellness/mind", "Mind"), ("/mind", "Mind"),
    ("/health", "Trackers"), ("/wellness", "Wellness"), ("/cycle", "Cycle"), ("/fitness", "Fitness"), ("/organs", "Body map"),
    ("/body", "Body map"), ("/insights", "Insights"), ("/patterns", "Insights"), ("/notifications", "Notifications"),
    ("/me/consent", "Privacy"), ("/consents", "Privacy"), ("/privacy", "Privacy"), ("/community", "Community"),
    ("/partner", "Sharing"), ("/sharing", "Sharing"), ("/companion", "Today"), ("/profile", "Profile"), ("/memory", "Memory"),
)


def feature_of(route: str | None) -> str:
    route = route or ""
    return next((label for prefix, label in FEATURES if route == prefix or route.startswith(prefix + "/")), "Other")


def cost(provider: str, tokens_in: int, tokens_out: int) -> dict[str, Any]:
    """{'usd': 0.0, 'basis': 'free tier'} for the free providers, {'usd': None, 'basis': 'unknown'} for anything else."""
    return {"usd": 0.0, "basis": "free tier"} if provider in FREE_TIER else {"usd": None, "basis": "unknown"}


def _hist(counters: dict[str, Counter], dim: str, prefix: str = "") -> dict[str, int]:
    return {k[len(prefix):]: n for k, n in counters.get(dim, {}).items() if k.startswith(prefix)}


def overall_view(counters: Any, stage_names: Iterable[str], funnel_steps: Iterable[str]) -> dict[str, Any]:
    """Everything the Overall page shows that comes from event counters. Pure. ``counters`` is Counter[(day, dim, key)]."""
    import ops_rollups as r
    t = r.totals(counters)
    pair = lambda p: (r.percentile(p, 50), r.percentile(p, 95))  # noqa: E731
    requests, chats = t["req"]["total"], t["chat"]["total"]
    kinds = t["route_kind"]
    kinds_known = sum(kinds.values())
    mix = [{"route_kind": k, "count": n, "share": _rate(n, kinds_known)} for k, n in kinds.most_common()]
    ai_n = kinds.get("ai", 0)
    consent_n = kinds.get("consent_needed", 0)

    providers: dict[tuple[str, str], dict[str, Any]] = {}
    for key, n in t["attempt"].items():
        provider, model, outcome = key.split("|")
        row = providers.setdefault((provider, model), {"provider": provider, "model": model, "attempts": 0, "success": 0, "timeouts": 0,
                                                       "answered_replies": 0, "tokens_in": 0, "tokens_out": 0})
        row["attempts"] += n
        row["success"] += n if outcome == "success" else 0
        row["timeouts"] += n if outcome in {"timeout", "budget_spent"} else 0
    for key, n in t["reply"].items():
        provider, model, outcome = key.split("|")
        if outcome == "answered":
            providers.setdefault((provider, model), {"provider": provider, "model": model, "attempts": 0, "success": 0, "timeouts": 0,
                                                     "answered_replies": 0, "tokens_in": 0, "tokens_out": 0})["answered_replies"] += n
    for dim, field in (("tokens_in", "tokens_in"), ("tokens_out", "tokens_out")):
        for key, n in t[dim].items():
            provider, model = key.split("|")
            if (provider, model) in providers:
                providers[(provider, model)][field] += n
    rows = []
    for (provider, model), row in providers.items():
        p50, p95 = pair(_hist(t, "hist.attempt", f"{provider}|{model}|"))
        rows.append({**row, "failed": row["attempts"] - row["success"], "success_rate": _rate(row["success"], row["attempts"]),
                     "timeout_rate": _rate(row["timeouts"], row["attempts"]), "p50_ms": p50, "p95_ms": p95,
                     "cost": cost(provider, row["tokens_in"], row["tokens_out"])})
    rows.sort(key=lambda x: (-x["answered_replies"], -x["attempts"]))

    answered = sum(n for k, n in t["reply"].items() if k.endswith("|answered"))
    degraded = sum(n for k, n in t["reply"].items() if k.endswith("|degraded"))
    used = t["fallback"].get("used", 0)
    attempts = sum(row["attempts"] for row in rows)
    reply50, reply95 = pair(t.get("hist.reply", {}))
    api50, api95 = pair(t.get("hist.api", {}))
    chat50, chat95 = pair(t.get("hist.chat", {}))
    stages = []
    for name in stage_names:
        p50, p95 = pair(t.get(f"hist.stage.{name}", {}))
        stages.append({"stage": name, "n": sum(t.get(f"hist.stage.{name}", {}).values()), "p50_ms": p50, "p95_ms": p95})

    by_route = [{"route": k, "requests": n, "errors_5xx": t["route5xx"].get(k, 0), "feature": feature_of(k.split(" ", 1)[-1])}
                for k, n in t["route"].most_common()]
    features: Counter = Counter()
    for row in by_route:
        features[row["feature"]] += row["requests"]
    steps = list(funnel_steps)
    first = max((t["funnel"].get(s, 0) for s in steps[:1]), default=0)
    funnel = [{"step": s, "count": t["funnel"].get(s, 0), "of_first": _rate(t["funnel"].get(s, 0), first)} for s in steps]
    crashes = Counter()
    for key, n in t["client"].items():
        crashes[key.split("|")[0]] += n

    safety_days = r.per_day(counters, "safety")
    return {
        "totals": {"requests": requests, "chats": chats, "server_errors": sum(n for k, n in t["status"].items() if k == "5xx"),
                   "onboarding_completed": t["funnel"].get("onboarding_completed", 0)},
        "latency": {"api": {"p50_ms": api50, "p95_ms": api95}, "chat": {"p50_ms": chat50, "p95_ms": chat95},
                    "reply": {"p50_ms": reply50, "p95_ms": reply95}},
        "ai": {"replies": answered + degraded, "answered": answered, "degraded": degraded,
               "degraded_rate": _rate(degraded, answered + degraded), "fallback_used": used, "fallback_rate": _rate(used, answered),
               "attempts": attempts, "timeouts": sum(row["timeouts"] for row in rows),
               "timeout_rate": _rate(sum(row["timeouts"] for row in rows), attempts),
               "ai_share": _rate(ai_n, kinds_known), "deterministic_share": _rate(kinds_known - ai_n - consent_n, kinds_known),
               "consent_needed": consent_n, "consent_needed_rate": _rate(consent_n, kinds_known)},
        "providers": rows,
        "stages": stages,
        "route_mix": mix,
        "safety": {"totals": dict(t["safety"]), "per_day": [{"day": d, **{k: v.get(k, 0) for k in ("GREEN", "AMBER", "RED")}} for d, v in safety_days.items()]},
        "features": [{"feature": f, "requests": n} for f, n in features.most_common()],
        "routes": by_route[:60],
        "funnel": funnel,
        "errors": dict(t["error"]),
        "status_classes": dict(t["status"]),
        "client_crashes": dict(crashes),
    }
