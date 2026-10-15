"""Loads the user's logs as daily series for association_insights.analyze(), with a short in-process cache.

Every input is optional: a domain that fails to load or has nothing is just an empty series (missing is never zero).
chat_block() never blocks a chat reply: it returns the cached result, or starts one background computation and returns "".
"""
from __future__ import annotations

import threading
import time
from datetime import date, datetime, timezone
from typing import Any

import association_insights as ai
import mind_checkins as Mind
import pattern_notices
import rag_links
import sleep_engine as S
import wellness_common as W
from health_logs import DOMAINS, list_domain

TTL_SECONDS = 1800
_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_running: set[str] = set()
_lock = threading.Lock()


def _num(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f and abs(f) != float("inf") else None


def _daily(db: Any, uid: str, slug: str, days: int, off: int, field: str, how: str) -> dict[date, float | None]:
    """Per local day: sum, max or mean of a numeric field over the entries that have it."""
    per: dict[date, list[float]] = {}
    try:
        entries = list_domain(db, slug, DOMAINS[slug], uid, days)["entries"]
    except Exception:  # noqa: BLE001 - an unreadable domain is an empty series, never an error for the others
        return {}
    for e in entries:
        v, d = _num(e.get(field)), W.local_date_of(e.get("date"), off)
        if v is None or not d:
            continue
        try:
            per.setdefault(date.fromisoformat(d[:10]), []).append(v)
        except ValueError:
            continue
    agg = {"sum": sum, "max": max, "mean": lambda xs: sum(xs) / len(xs)}[how]
    return {d: round(agg(xs), 2) for d, xs in per.items()}


def load_series(db: Any, uid: str, days: int = 90, tz_offset_minutes: int | None = None) -> dict[str, dict[date, float | None]]:
    off = W.tz_offset(tz_offset_minutes) if tz_offset_minutes is not None else (W.request_tz() or 0)
    today = W.local_now(datetime.now(timezone.utc), off).date()
    out: dict[str, dict[date, float | None]] = {}
    try:
        nights = S.nightly(S.load_entries(db, uid, days + 2), {}, today)
        out["sleep_hours"] = {date.fromisoformat(n["date"]): n["hours"] for n in nights}
        out["sleep_quality"] = {date.fromisoformat(n["date"]): n["quality"] for n in nights if n.get("quality") is not None}
    except Exception:  # noqa: BLE001
        pass
    try:
        out["mood"] = ai._mood(Mind.per_day_moods(Mind.load_mood_entries(db, uid, days), off))
    except Exception:  # noqa: BLE001
        pass
    out["activity_minutes"] = _daily(db, uid, "activity", days, off, "duration", "sum")
    out["hydration_ml"] = _daily(db, uid, "hydration", days, off, "volume", "sum")
    out["calories"] = _daily(db, uid, "nutrition", days, off, "calories", "sum")
    out["symptom_severity"] = _daily(db, uid, "symptoms", days, off, "severity", "max")
    out["resting_hr"] = _daily(db, uid, "vitals", days, off, "heart_rate", "mean")
    out["screen_hours"] = _daily(db, uid, "eyes", days, off, "screen_hours", "max")   # the longest the person logged that day
    out["eye_comfort"] = _daily(db, uid, "eyes", days, off, "comfort", "mean")           # 1 (very uncomfortable) to 5 (very comfortable)
    try:   # estimated phase per day (cycle logs + sleep-day details): 1 for luteal, 0 for any other known phase
        phases = {d: p["cycle_phase"] for d, p in S.load_details(db, uid).items() if p.get("cycle_phase")}
        out["luteal"] = {date.fromisoformat(d[:10]): 1.0 if str(p).lower() == "luteal" else 0.0 for d, p in phases.items()}
    except Exception:  # noqa: BLE001
        pass
    return {k: v for k, v in out.items() if v}


def compute(db: Any, uid: str, days: int = 90, tz_offset_minutes: int | None = None, with_sources: bool = False) -> dict[str, Any]:
    result = ai.analyze(load_series(db, uid, days, tz_offset_minutes))
    result["window_days"] = days
    # remember what was found (new / stronger / reversed / faded); never raises, writes only when a pattern changes
    result["notices"] = pattern_notices.save(db, uid, result)
    if with_sources:   # what the stored, verified health sources say about each link (best effort; may be empty)
        for item in result["insights"]:
            pid = rag_links.pair_id(*item["domains"])
            item["sources"] = rag_links.evidence_for_pair(pid) if pid else []
        result["with_sources"] = True
    with _lock:
        _cache[uid] = (time.monotonic(), result)
        if len(_cache) > 2000:   # bounded: drop the oldest quarter
            for k, _v in sorted(_cache.items(), key=lambda kv: kv[1][0])[:500]:
                _cache.pop(k, None)
    return result


def cached(uid: str) -> dict[str, Any] | None:
    with _lock:
        hit = _cache.get(uid)
    return hit[1] if hit and time.monotonic() - hit[0] < TTL_SECONDS else None


def get(db: Any, uid: str, days: int = 90, tz_offset_minutes: int | None = None, refresh: bool = False) -> dict[str, Any]:
    """For the API: the cached full result when fresh, otherwise compute it (with sources) now."""
    hit = cached(uid)
    if hit and not refresh and hit.get("with_sources") and hit.get("window_days") == days:
        return hit
    return compute(db, uid, days, tz_offset_minutes, with_sources=True)


def _bg(db: Any, uid: str, tz: int | None) -> None:
    try:
        compute(db, uid, 90, tz)
    except Exception:  # noqa: BLE001 - background warm-up only
        pass
    finally:
        with _lock:
            _running.discard(uid)


def chat_block(db: Any, uid: str, tz_offset_minutes: int | None = None) -> str:
    """Context text for the assistant. Cached result now; otherwise warm the cache in the background for the next message."""
    result = cached(uid)
    if result is None:
        with _lock:
            start = uid not in _running
            _running.add(uid)
        if start:
            threading.Thread(target=_bg, args=(db, uid, tz_offset_minutes), daemon=True).start()
        return ""
    lines = ai.chat_lines(result)
    if not lines:
        return ""
    return ("\n\nPATTERNS IN THEIR OWN LOGS (statistical associations, not causes; mention at most one and only if relevant, "
            "say 'in your logs', never imply a diagnosis):\n" + "\n".join("- " + ln for ln in lines))
