"""Operational telemetry for the admin portal: what happened technically, never what a person told Bubbles.

Events are small dicts ``{seq, at, kind, request_id, data}``. ``data`` holds only whitelisted technical fields (route template,
status, latency, provider, model, outcome, error category, counts). There is no user id, message, prompt, reply, query text,
token, key or address anywhere in an event, and ``record`` drops any field that is not on the list for its kind.

Path: ``record`` appends to an in-memory ring (feeds the live view) and to a bounded queue that a daemon thread writes to
``bubbles_ops_events`` in one batch every few seconds. Every failure is swallowed and counted: a request never waits for
telemetry and never fails because of it. Without the table (migration not applied yet) the module stays in memory-only mode.
"""
from __future__ import annotations

import os
import threading
import time
from collections import deque
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

TABLE = "bubbles_ops_events"
RING_SIZE = 5000
QUEUE_LIMIT = 2000
FLUSH_EVERY_S = 10.0
PRUNE_EVERY_S = 3600.0
AUDIT_RETENTION_DAYS = 365
READ_CAP = 20_000          # ponytail: aggregation reads at most this many rows per range; an SQL summary function is the upgrade path
PAGE = 1000                # PostgREST returns at most 1,000 rows per request by default
MAX_TEXT = 120             # any string in an event is cut to this: a row always fits the table's 4 KB check

# Every field an event of each kind may carry. Anything else passed to record() is dropped.
FIELDS: dict[str, frozenset[str]] = {
    "api": frozenset({"method", "route", "status", "latency_ms", "route_kind", "safety_level", "ai_called"}),
    "ai_attempt": frozenset({"provider", "model", "position", "outcome", "error_category", "latency_ms",
                             "input_tokens", "output_tokens", "total_tokens", "cached_tokens"}),
    "ai_reply": frozenset({"provider", "model", "outcome", "attempts", "fallback_used", "total_ms"}),
    "error": frozenset({"category", "component", "route", "error_class", "severity"}),
    "audit": frozenset({"action", "target", "old", "new", "outcome", "actor"}),   # actor: the administrator, never a user
}

_request_id: ContextVar[str | None] = ContextVar("bubbles_request_id", default=None)
_request_note: ContextVar[dict | None] = ContextVar("bubbles_request_note", default=None)

_lock = threading.Lock()
_ring: deque[dict[str, Any]] = deque(maxlen=RING_SIZE)
_queue: deque[dict[str, Any]] = deque(maxlen=QUEUE_LIMIT)
_seq = 0
_flusher: threading.Thread | None = None
STARTED_AT = datetime.now(timezone.utc)

status: dict[str, Any] = {
    "mode": "memory_only",          # memory_only | stored | not_set_up | write_failing
    "written": 0, "dropped": 0, "write_errors": 0, "last_write_at": None, "last_error_class": None, "last_prune_at": None,
}
retention_days = int(os.getenv("BUBBLES_TELEMETRY_RETENTION_DAYS", "14"))


def _persist_enabled() -> bool:
    return os.getenv("BUBBLES_OPS_PERSIST", "1") != "0"


# ---------------------------------------------------------------- request context

def begin_request() -> tuple[str, Any, Any]:
    """Called by the HTTP middleware: a fresh request id and an empty note for this request."""
    rid = uuid4().hex[:8]   # same 8-character id the 500 answer has always shown
    return rid, _request_id.set(rid), _request_note.set({})


def end_request(tokens: tuple[Any, Any]) -> dict:
    note = _request_note.get() or {}
    _request_id.reset(tokens[0])
    _request_note.reset(tokens[1])
    return note


def current_request_id() -> str | None:
    return _request_id.get()


def current_note() -> dict:
    return dict(_request_note.get() or {})


# The only values a chat note may carry. Anything else is dropped: no free text can ever reach an event this way.
NOTE_VALUES: dict[str, frozenset] = {
    "route_kind": frozenset({"ai", "emergency", "correction", "clarification", "daily_log", "fitness_support", "fitness_answer",
                             "small_talk", "safety_followup", "consent_needed", "empty"}),
    "safety_level": frozenset({"GREEN", "AMBER", "RED"}),
    "ai_called": frozenset({True, False}),
}


def note(**fields: Any) -> None:
    """Adds technical facts about the current request (chat: route_kind, safety_level, ai_called) to its api event."""
    current = _request_note.get()
    if current is not None:
        current.update({k: v for k, v in fields.items() if k in NOTE_VALUES and isinstance(v, (str, bool)) and v in NOTE_VALUES[k]})


# ---------------------------------------------------------------- recording

def record(kind: str, **data: Any) -> None:
    """Never raises."""
    global _seq
    try:
        allowed = FIELDS.get(kind)
        if allowed is None:
            return
        clean = {k: (v[:MAX_TEXT] if isinstance(v, str) else v) for k, v in data.items() if k in allowed and v is not None}
        with _lock:
            _seq += 1
            event = {"seq": _seq, "at": datetime.now(timezone.utc).isoformat(), "kind": kind,
                     "request_id": _request_id.get(), "data": clean}
            _ring.append(event)
            if _persist_enabled():
                if len(_queue) == QUEUE_LIMIT:
                    status["dropped"] += 1
                _queue.append(event)
        if _persist_enabled():
            _ensure_flusher()
    except Exception:  # noqa: BLE001 - telemetry must never break a request
        pass


def recent(after: int = 0, limit: int = 100) -> list[dict[str, Any]]:
    """Events newer than ``after`` (a seq) from memory, oldest first, at most ``limit``."""
    with _lock:
        rows = [e for e in _ring if e["seq"] > after]
    return rows[-limit:]


def memory_events(since: datetime) -> list[dict[str, Any]]:
    cutoff = since.isoformat()
    with _lock:
        return [e for e in _ring if e["at"] >= cutoff]


# ---------------------------------------------------------------- persistence

def _db():
    from supabase_client import supabase
    return supabase


def _ensure_flusher() -> None:
    global _flusher
    if _flusher is not None and _flusher.is_alive():
        return
    with _lock:
        if _flusher is not None and _flusher.is_alive():
            return
        _flusher = threading.Thread(target=_flush_loop, name="bubbles-ops-flush", daemon=True)
        _flusher.start()


def _missing_table(error: Exception) -> bool:
    text = str(error)
    return "PGRST205" in text or "42P01" in text or "does not exist" in text or "Could not find the table" in text


def flush_once() -> int:
    """Writes queued events in one insert. Returns how many were written. Never raises."""
    with _lock:
        batch = [_queue.popleft() for _ in range(min(len(_queue), 500))]
    if not batch:
        return 0
    rows = [{"at": e["at"], "kind": e["kind"], "request_id": e["request_id"], "data": e["data"]} for e in batch]
    try:
        _db().table(TABLE).insert(rows).execute()
    except Exception as error:  # noqa: BLE001
        status["write_errors"] += 1
        status["dropped"] += len(rows)
        status["last_error_class"] = type(error).__name__
        status["mode"] = "not_set_up" if _missing_table(error) else "write_failing"
        return 0
    status["written"] += len(rows)
    status["last_write_at"] = datetime.now(timezone.utc).isoformat()
    status["mode"] = "stored"
    return len(rows)


def prune_once(now: datetime | None = None) -> None:
    """Deletes technical events older than the retention and audit events older than a year. Never raises."""
    now = now or datetime.now(timezone.utc)
    try:
        table = _db().table(TABLE)
        table.delete().neq("kind", "audit").lt("at", (now - timedelta(days=retention_days)).isoformat()).execute()
        _db().table(TABLE).delete().eq("kind", "audit").lt("at", (now - timedelta(days=AUDIT_RETENTION_DAYS)).isoformat()).execute()
        status["last_prune_at"] = now.isoformat()
    except Exception as error:  # noqa: BLE001
        status["last_error_class"] = type(error).__name__


def _flush_loop() -> None:
    last_prune = 0.0
    while True:
        time.sleep(FLUSH_EVERY_S)
        while flush_once() == 500:
            pass
        if status["mode"] == "stored" and time.monotonic() - last_prune > PRUNE_EVERY_S:
            prune_once()
            last_prune = time.monotonic()
        if status["mode"] == "not_set_up":
            time.sleep(300)  # the table is missing: check again in five minutes instead of every few seconds


def stored_events(since: datetime, kinds: list[str] | None = None, *, request_id: str | None = None,
                  before: str | None = None, cap: int = READ_CAP) -> tuple[list[dict[str, Any]], bool, str]:
    """Events since ``since`` (newest first). Returns (events, capped, source). Falls back to memory when nothing is stored."""
    if _persist_enabled() and status["mode"] != "not_set_up":
        try:
            rows: list[dict[str, Any]] = []
            while len(rows) < cap:
                q = _db().table(TABLE).select("id,at,kind,request_id,data").gte("at", since.isoformat())
                if kinds:
                    q = q.in_("kind", kinds)
                if request_id:
                    q = q.eq("request_id", request_id)
                if before:
                    q = q.lt("at", before)
                page = q.order("at", desc=True).range(len(rows), len(rows) + PAGE - 1).execute().data or []
                rows.extend(page)
                if len(page) < PAGE:
                    break
            return rows[:cap], len(rows) >= cap, "stored"
        except Exception as error:  # noqa: BLE001 - the portal falls back to memory, the app is untouched
            status["last_error_class"] = type(error).__name__
            if _missing_table(error):
                status["mode"] = "not_set_up"
    rows = [e for e in memory_events(since) if (not kinds or e["kind"] in kinds) and (not request_id or e["request_id"] == request_id)
            and (not before or e["at"] < before)]
    rows.reverse()
    return rows[:cap], len(rows) > cap, "memory"


def reset_for_tests() -> None:
    global _seq
    with _lock:
        _ring.clear()
        _queue.clear()
        _seq = 0
    status.update({"mode": "memory_only", "written": 0, "dropped": 0, "write_errors": 0, "last_write_at": None,
                   "last_error_class": None, "last_prune_at": None})
