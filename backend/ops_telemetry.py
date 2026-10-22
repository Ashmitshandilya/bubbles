"""Operational telemetry for the admin portal: what happened technically, never what a person told Bubbles.

Events are small dicts ``{seq, at, kind, request_id, data}``. ``data`` holds only whitelisted technical fields (route template,
status, latency, provider, model, outcome, error category, counts). There is no user id, message, prompt, reply, query text,
token, key or address in ``data``, and ``record`` drops any field that is not on the list for its kind.

One named exception (owner decision, docs/admin/README.md): api and ai_attempt events kept in the in-memory ring carry a
top-level ``uid`` for the live admin view. It is never in ``data``, never queued, never written to the database, never logged,
and only ``recent(..., with_uid=True)`` (the admin-gated live endpoint) returns it.

Path: ``record`` appends to an in-memory ring (feeds the live view) and to a bounded queue that a daemon thread writes to
``bubbles_ops_events`` in one batch every few seconds. Every failure is swallowed and counted: a request never waits for
telemetry and never fails because of it. Without the table (migration not applied yet) the module stays in memory-only mode.
"""
from __future__ import annotations

import os
import re
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
FUNNEL_RETENTION_DAYS = 90   # step counts are slow-moving: kept longer than the technical events
READ_CAP = 20_000          # ponytail: aggregation reads at most this many rows per range; an SQL summary function is the upgrade path
PAGE = 1000                # PostgREST returns at most 1,000 rows per request by default
MAX_TEXT = 120             # any string in an event is cut to this: a row always fits the table's 4 KB check

# Every field an event of each kind may carry. Anything else passed to record() is dropped.
FIELDS: dict[str, frozenset[str]] = {
    "api": frozenset({"method", "route", "status", "latency_ms", "route_kind", "safety_level", "ai_called",
                      # chat only: where the time went, in milliseconds (numbers only; see STAGES)
                      "stage_pre_ms", "stage_ctx_ms", "stage_rag_ms", "stage_ai_ms", "stage_post_ms"}),
    "ai_attempt": frozenset({"provider", "model", "position", "outcome", "error_category", "latency_ms",
                             "input_tokens", "output_tokens", "total_tokens", "cached_tokens"}),
    "ai_reply": frozenset({"provider", "model", "outcome", "attempts", "fallback_used", "total_ms"}),
    "error": frozenset({"category", "component", "route", "error_class", "severity"}),
    "audit": frozenset({"action", "target", "old", "new", "outcome", "actor"}),   # actor: the administrator, never a user
    "funnel": frozenset({"step"}),   # first-run setup: which step a person reached (a fixed name, never an answer)
    "client": frozenset({"code"}),   # the website or app reporting that something broke (a fixed code, never a message)
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
    "new_kinds": "unknown", "written": 0, "dropped": 0, "write_errors": 0, "last_write_at": None, "last_error_class": None, "last_prune_at": None,
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


_UID = re.compile(r"^[0-9a-fA-F-]{8,64}$")


def bind_user(uid: Any) -> None:
    """The signed-in person of this request, for the live admin view only (see the module note). Never raises."""
    try:
        current = _request_note.get()
        if current is not None and isinstance(uid, str) and _UID.match(uid):
            current["_uid"] = uid
    except Exception:  # noqa: BLE001
        pass


def current_note() -> dict:
    """The facts noted for this request. Keys starting with an underscore (the live-view user id) are never returned."""
    return {k: v for k, v in (_request_note.get() or {}).items() if not k.startswith("_")}


# The only values a chat note may carry. Anything else is dropped: no free text can ever reach an event this way.
NOTE_VALUES: dict[str, frozenset] = {
    "route_kind": frozenset({"ai", "emergency", "correction", "clarification", "daily_log", "fitness_support", "fitness_answer",
                             "small_talk", "safety_followup", "recall", "remembered", "consent_needed", "empty"}),
    "safety_level": frozenset({"GREEN", "AMBER", "RED"}),
    "ai_called": frozenset({True, False}),
}


# Events whose one field may only be one of these fixed names; anything else drops the whole event (no free text can arrive this way).
FUNNEL_STEPS = ("core", "extras", "later", "completed", "under_18")
CLIENT_CODES = ("render_error", "unhandled_rejection", "chunk_load_failed", "api_unreachable", "sign_in_refresh_failed", "stream_fallback")
FIELD_ENUMS: dict[str, dict[str, frozenset]] = {"funnel": {"step": frozenset(FUNNEL_STEPS)}, "client": {"code": frozenset(CLIENT_CODES)}}
# Kinds added after the first migration: stored only if the database accepts them (supabase/migrations/20261016_bubbles_ops_funnel.sql).
NEW_KINDS = frozenset({"funnel", "client"})


# Where a chat turn spends its time, in order: pre (sign-in to understood), ctx (own data), rag (evidence lookup), ai (the model), post
# (saving). ctx and rag run side by side, so their sum can exceed the request's own time. Numbers only, a fixed set of names.
STAGES = ("pre", "ctx", "rag", "ai", "post")
STAGE_FIELDS = tuple(f"stage_{name}_ms" for name in STAGES)
NOTE_NUMBERS = frozenset(STAGE_FIELDS)
_MAX_STAGE_MS = 600_000.0


def note(**fields: Any) -> None:
    """Adds technical facts about the current request (chat: route_kind, safety_level, ai_called, stage_*_ms) to its api event."""
    current = _request_note.get()
    if current is None:
        return
    for key, value in fields.items():
        if key in NOTE_VALUES and isinstance(value, (str, bool)) and value in NOTE_VALUES[key]:
            current[key] = value
        elif key in NOTE_NUMBERS and isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= _MAX_STAGE_MS:
            current[key] = round(float(value), 1)


# ---------------------------------------------------------------- recording

def funnel(step: str) -> None:
    """One person reached a first-run setup step. Only the fixed names in FUNNEL_STEPS are accepted."""
    record("funnel", step=step)


def client(code: str) -> None:
    """The website or app reported a problem. Only the fixed names in CLIENT_CODES are accepted."""
    record("client", code=code)


def record(kind: str, **data: Any) -> None:
    """Never raises."""
    global _seq
    try:
        allowed = FIELDS.get(kind)
        if allowed is None:
            return
        clean = {k: (v[:MAX_TEXT] if isinstance(v, str) else v) for k, v in data.items() if k in allowed and v is not None}
        for k in [k for k in clean if k in NOTE_NUMBERS]:   # stage timings are numbers in milliseconds, nothing else
            v = clean[k]
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= _MAX_STAGE_MS:
                del clean[k]
        for field, values in FIELD_ENUMS.get(kind, {}).items():
            if clean.get(field) not in values:
                return
        with _lock:
            _seq += 1
            event = {"seq": _seq, "at": datetime.now(timezone.utc).isoformat(), "kind": kind,
                     "request_id": _request_id.get(), "data": clean}
            note_ = _request_note.get()
            uid = note_.get("_uid") if note_ and kind in ("api", "ai_attempt") else None
            _ring.append({**event, "uid": uid} if uid else event)   # the uid lives in the ring only, never in the queue
            if _persist_enabled() and not (kind in NEW_KINDS and status["new_kinds"] == "not_allowed"):
                if len(_queue) == QUEUE_LIMIT:
                    status["dropped"] += 1
                _queue.append(event)
        if _persist_enabled():
            _ensure_flusher()
    except Exception:  # noqa: BLE001 - telemetry must never break a request
        pass


def _strip(e: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in e.items() if k != "uid"}


def recent(after: int = 0, limit: int = 100, *, with_uid: bool = False) -> list[dict[str, Any]]:
    """Events newer than ``after`` (a seq) from memory, oldest first, at most ``limit``. ``uid`` only with ``with_uid``
    (the admin-gated live endpoint); every other reader gets events without it."""
    with _lock:
        rows = [e for e in _ring if e["seq"] > after]
    rows = rows[-limit:]
    return rows if with_uid else [_strip(e) for e in rows]


def memory_events(since: datetime) -> list[dict[str, Any]]:
    cutoff = since.isoformat()
    with _lock:
        return [_strip(e) for e in _ring if e["at"] >= cutoff]


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
    # The newer kinds go in their own insert: if the database does not accept them yet, the technical events still get through.
    newer = [r for r in rows if r["kind"] in NEW_KINDS]
    rows = [r for r in rows if r["kind"] not in NEW_KINDS]
    written = 0
    if newer:
        try:
            _db().table(TABLE).insert(newer).execute()
            status["new_kinds"] = "ok"
            written += len(newer)
        except Exception as error:  # noqa: BLE001
            status["dropped"] += len(newer)
            if "23514" in str(error) or "check constraint" in str(error).lower():
                status["new_kinds"] = "not_allowed"   # the migration is not applied: keep these in memory only
            else:
                status["write_errors"] += 1
                status["last_error_class"] = type(error).__name__
    if not rows:
        if written:
            status["written"] += written
        return written
    try:
        _db().table(TABLE).insert(rows).execute()
    except Exception as error:  # noqa: BLE001
        status["write_errors"] += 1
        status["dropped"] += len(rows)
        status["last_error_class"] = type(error).__name__
        status["mode"] = "not_set_up" if _missing_table(error) else "write_failing"
        return written
    written += len(rows)
    status["written"] += written
    status["last_write_at"] = datetime.now(timezone.utc).isoformat()
    status["mode"] = "stored"
    return written


def prune_once(now: datetime | None = None) -> None:
    """Deletes technical events older than the retention and audit events older than a year. Never raises."""
    now = now or datetime.now(timezone.utc)
    try:
        table = _db().table(TABLE)
        table.delete().in_("kind", ["api", "ai_attempt", "ai_reply", "error", "client"]).lt("at", (now - timedelta(days=retention_days)).isoformat()).execute()
        _db().table(TABLE).delete().eq("kind", "funnel").lt("at", (now - timedelta(days=FUNNEL_RETENTION_DAYS)).isoformat()).execute()
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
                  before: str | None = None, cap: int = READ_CAP, until: datetime | None = None) -> tuple[list[dict[str, Any]], bool, str]:
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
                if until:
                    q = q.lt("at", until.isoformat())
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
            and (not before or e["at"] < before) and (not until or e["at"] < until.isoformat())]
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
