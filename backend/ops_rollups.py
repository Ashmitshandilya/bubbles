"""Durable counters for the admin Overall page: what happened since the beginning, not only since the last restart.

Raw events (``bubbles_ops_events``) are kept for days and live in memory only until the owner applies the ops migration. This
module turns completed hours of raw events into additive counters per day (``ops_rollups_daily``), so "7 days, 30 days, all
time" survive restarts and pruning. Counters hold metadata only: route templates, fixed lists, provider and model names,
latency buckets. No user id, no text.

How it stays correct: one run reads each completed hour once, adds its counters to the day rows and moves the watermark
(``_state / events_through``, epoch seconds of the hour boundary) in ONE upsert statement, so a crash can neither lose nor
double count an hour. Runs are triggered lazily when the Overall page is read and by the cron endpoint via ``run_rollups(db)``.
"""
from __future__ import annotations

import math
import threading
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

import ops_telemetry
from ops_metrics import CHAT_ROUTES

TABLE = "ops_rollups_daily"
STATE_DAY, STATE_DIM, STATE_KEY = "1970-01-01", "_state", "events_through"
KINDS = ["api", "ai_attempt", "ai_reply", "error", "funnel", "client"]
EDGES = (25, 50, 75, 100, 150, 200, 300, 400, 600, 800, 1200, 1600, 2400, 3200, 4800, 6400, 9600, 12800, 19200, 25600, 38400, 51200)
MIN_GAP_S = 600.0        # the lazy trigger asks the table at most this often per process
PAGE = 1000
RANGE_DAYS = {"7d": 7, "30d": 30}

_lock = threading.Lock()
_last = {"at": 0.0, "result": None}
_missing_until = 0.0


# ---------------------------------------------------------------- counting (pure)

def bucket(ms: float) -> str:
    return next((str(e) for e in EDGES if ms <= e), "inf")


def _num(v: Any) -> bool:
    """A real, finite, non-negative number (not a bool, NaN or infinity): the only thing a latency or token field may hold."""
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v >= 0


def _s(value: Any) -> str:
    return str(value if value not in (None, "") else "unknown").replace("|", "/")[:60]


def count_events(events: Iterable[dict[str, Any]]) -> Counter:
    """Counters keyed ``(day, dimension, key)`` for a batch of events. Pure; the same function feeds raw ranges and rollups."""
    c: Counter = Counter()
    for e in events:
        if not isinstance(e, dict):
            continue
        day, d, kind = str(e.get("at", ""))[:10], e.get("data"), e.get("kind")
        if len(day) != 10 or not isinstance(d, dict):
            continue   # a malformed row is skipped, never counted and never fatal
        if kind == "api":
            route = f"{_s(d.get('method'))} {_s(d.get('route'))}"
            status = d.get("status")
            status = status if isinstance(status, int) and not isinstance(status, bool) and 100 <= status <= 599 else 0
            c[day, "req", "total"] += 1
            c[day, "route", route] += 1
            c[day, "status", f"{status // 100}xx"] += 1
            if status >= 500:
                c[day, "route5xx", route] += 1
            if _num(d.get("latency_ms")):
                c[day, "hist.api", bucket(d["latency_ms"])] += 1
            if d.get("route") in CHAT_ROUTES and d.get("method") == "POST":   # streamed chats count like plain ones
                c[day, "chat", "total"] += 1
                if _num(d.get("latency_ms")):
                    c[day, "hist.chat", bucket(d["latency_ms"])] += 1
                for field in ("route_kind", "safety_level"):
                    if d.get(field):
                        c[day, "route_kind" if field == "route_kind" else "safety", _s(d[field])] += 1
                if d.get("ai_called") is not None:
                    c[day, "ai_called", "true" if d["ai_called"] else "false"] += 1
                for stage in ops_telemetry.STAGE_FIELDS:
                    if _num(d.get(stage)):
                        c[day, f"hist.stage.{stage[6:-3]}", bucket(d[stage])] += 1
        elif kind == "ai_attempt":
            who = f"{_s(d.get('provider'))}|{_s(d.get('model'))}"
            c[day, "attempt", f"{who}|{_s(d.get('outcome'))}"] += 1
            if _num(d.get("latency_ms")):
                c[day, "hist.attempt", f"{who}|{bucket(d['latency_ms'])}"] += 1
            for src, dim in (("input_tokens", "tokens_in"), ("output_tokens", "tokens_out")):
                if _num(d.get(src)) and d[src] > 0:
                    c[day, dim, who] += int(d[src])
        elif kind == "ai_reply":
            c[day, "reply", f"{_s(d.get('provider'))}|{_s(d.get('model'))}|{_s(d.get('outcome'))}"] += 1
            if d.get("outcome") == "answered":
                c[day, "fallback", "used" if d.get("fallback_used") else "not_used"] += 1
            if _num(d.get("total_ms")):
                c[day, "hist.reply", bucket(d["total_ms"])] += 1
        elif kind == "error":
            c[day, "error", _s(d.get("category"))] += 1
        elif kind == "funnel":
            c[day, "funnel", _s(d.get("step"))] += 1
        elif kind == "client":
            c[day, "client", _s(d.get('code'))] += 1
    return c


def totals(counters: Counter) -> dict[str, Counter]:
    """dimension -> key -> count, summed over days."""
    out: dict[str, Counter] = defaultdict(Counter)
    for (_day, dim, key), n in counters.items():
        out[dim][key] += n
    return out


def per_day(counters: Counter, dim: str) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = defaultdict(dict)
    for (day, d, key), n in counters.items():
        if d == dim:
            out[day][key] = out[day].get(key, 0) + n
    return dict(sorted(out.items()))


def percentile(hist: dict[str, int], p: float) -> float | None:
    """Percentile from latency buckets: the upper edge of the bucket holding it (so it is an 'at most', within about a quarter)."""
    n = sum(hist.values())
    if not n:
        return None
    need, seen = max(1, -(-n * p // 100)), 0
    for edge in [*(str(e) for e in EDGES), "inf"]:
        seen += hist.get(edge, 0)
        if seen >= need:
            return float(EDGES[-1] if edge == "inf" else edge)
    return float(EDGES[-1])


# ---------------------------------------------------------------- storage

def _missing(error: Exception) -> bool:
    return ops_telemetry._missing_table(error)


def _pages(make_query) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    while True:
        page = make_query().range(len(rows), len(rows) + PAGE - 1).execute().data or []
        rows.extend(page)
        if len(page) < PAGE:
            return rows


def read_state(db: Any) -> int | None:
    """Epoch seconds of the hour boundary the rollups are complete through; None when never run. Raises if the table is missing."""
    rows = db.table(TABLE).select("count").eq("day", STATE_DAY).eq("dimension", STATE_DIM).eq("key", STATE_KEY).limit(1).execute().data or []
    return int(rows[0]["count"]) if rows else None


def read_counters(db: Any, since_day: str) -> Counter:
    rows = _pages(lambda: db.table(TABLE).select("day,dimension,key,count").gte("day", since_day).neq("dimension", STATE_DIM).order("day"))
    return Counter({(r["day"], r["dimension"], r["key"]): int(r["count"]) for r in rows})


def _hour(t: datetime) -> datetime:
    return t.replace(minute=0, second=0, microsecond=0)


def run_rollups(db: Any = None, *, now: datetime | None = None, max_hours: int = 72) -> dict[str, Any]:
    """Rolls up every completed hour not yet counted (at most ``max_hours`` per call; the next call continues). Idempotent and
    safe to call from the cron endpoint. Never raises. Returns ``{"status": ok|idle|skipped|not_set_up|error, ...}``."""
    global _missing_until
    now = now or datetime.now(timezone.utc)
    try:
        db = db if db is not None else ops_telemetry._db()
        with _lock:
            try:
                state = read_state(db)
            except Exception as error:  # noqa: BLE001
                if _missing(error):
                    _missing_until = time.monotonic() + 300
                    return {"status": "not_set_up"}
                raise
            end = _hour(now)
            if state is None:
                first = db.table(ops_telemetry.TABLE).select("at").order("at").limit(1).execute().data or []
                if not first:
                    return {"status": "idle", "through": None}
                start = _hour(datetime.fromisoformat(str(first[0]["at"]).replace("Z", "+00:00")))
            else:
                start = datetime.fromtimestamp(state, tz=timezone.utc)
            delta: Counter = Counter()
            cursor, hours, capped = start, 0, False
            while cursor < end and hours < max_hours:
                events, was_capped, source = ops_telemetry.stored_events(cursor, KINDS, until=cursor + timedelta(hours=1))
                if source != "stored":
                    return {"status": "skipped", "reason": "events_not_stored"}
                capped = capped or was_capped
                delta.update(count_events(events))
                cursor += timedelta(hours=1)
                hours += 1
            if hours == 0:
                return {"status": "idle", "through": start.isoformat()}
            days = sorted({k[0] for k in delta})
            existing: dict[tuple, int] = {}
            if days:
                for r in _pages(lambda: db.table(TABLE).select("day,dimension,key,count").in_("day", days)):
                    existing[(r["day"], r["dimension"], r["key"])] = int(r["count"])
            rows = [{"day": day, "dimension": dim, "key": key, "count": existing.get((day, dim, key), 0) + n}
                    for (day, dim, key), n in delta.items()]
            rows.append({"day": STATE_DAY, "dimension": STATE_DIM, "key": STATE_KEY, "count": int(cursor.timestamp())})
            db.table(TABLE).upsert(rows, on_conflict="day,dimension,key").execute()   # one statement: counters and watermark together
            return {"status": "ok", "hours": hours, "rows": len(rows) - 1, "through": cursor.isoformat(), "capped": capped}
    except Exception as error:  # noqa: BLE001 - a rollup never breaks the portal or the cron endpoint
        return {"status": "error", "error_class": type(error).__name__}


def ensure_fresh(db: Any, now: datetime | None = None) -> dict[str, Any] | None:
    """The lazy trigger: runs the rollup when it has not been asked for MIN_GAP_S, without blocking a second caller."""
    t = time.monotonic()
    if t < _missing_until or t - _last["at"] < MIN_GAP_S and _last["result"] is not None:
        return _last["result"]
    if not _lock.acquire(blocking=False):
        return _last["result"]
    _lock.release()   # run_rollups takes the lock itself; this was only the "is someone running" probe
    _last["at"] = t
    _last["result"] = run_rollups(db, now=now)
    return _last["result"]


def reset_for_tests() -> None:
    global _missing_until
    _missing_until = 0.0
    _last.update({"at": 0.0, "result": None})


# ---------------------------------------------------------------- reading a range for the Overall page

def collect(db: Any, range_id: str, now: datetime | None = None) -> dict[str, Any]:
    """Counters for ``1h | 24h | 7d | 30d | all`` plus where they came from.

    Short ranges are counted from raw events. Longer ones are the day rows up to the watermark plus the raw events after it, so
    the numbers include the last minutes and still survive a restart. Without the rollup table they fall back to raw events."""
    now = now or datetime.now(timezone.utc)
    short = {"1h": timedelta(hours=1), "24h": timedelta(hours=24)}
    rollup = {"mode": "not_used", "through": None}
    if range_id not in short:
        run = ensure_fresh(db, now)
        try:
            state = read_state(db)
        except Exception as error:  # noqa: BLE001
            state = None
            rollup = {"mode": "not_set_up" if _missing(error) else "unavailable", "through": None}
        if state is not None:
            through = datetime.fromtimestamp(state, tz=timezone.utc)
            since_day = "1970-01-02" if range_id == "all" else (now - timedelta(days=RANGE_DAYS[range_id])).date().isoformat()
            counters = read_counters(db, since_day)
            tail, capped, source = ops_telemetry.stored_events(through, KINDS)
            counters.update(count_events(tail))
            return {"counters": counters, "source": "rollups" if source == "stored" else "rollups+memory", "capped": capped,
                    "rollups": {"mode": "ok", "through": through.isoformat(), "last_run": (run or {}).get("status")}}
        if rollup["mode"] == "not_used":
            rollup = {"mode": "empty", "through": None}
    span = short.get(range_id) or (timedelta(days=RANGE_DAYS[range_id]) if range_id in RANGE_DAYS else timedelta(days=ops_telemetry.retention_days))
    events, capped, source = ops_telemetry.stored_events(now - span, KINDS)
    return {"counters": count_events(events), "source": source, "capped": capped, "rollups": rollup}
