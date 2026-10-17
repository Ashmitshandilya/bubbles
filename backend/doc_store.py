"""Owner-scoped JSON documents for the Whole-Health OS features, with no schema change.

Profiles, plans, food logs, cycle days, schedules and notifications are stored as rows of the existing
``health_events`` ledger: ``event_type = "bubbles_doc"``, ``title = "<kind>:<key>"`` and
``data = {"kind", "key", "payload", "version"}``. They are invisible to the analytics readers (those read
``extracted_health_events``), so large per-day logs can never crowd out a user's real health events.
``docs/proposals/whole-health-os-schema.sql`` describes proper tables; moving to them later only changes this file.

Every function takes the Supabase-like ``db`` and the authenticated ``uid`` and never reads another user's rows.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

TABLE = "health_events"
EVENT_TYPE = "bubbles_doc"
SOURCE = "bubbles_feature"
MAX_PAYLOAD_BYTES = 200_000
MAX_KEY = 120
LIST_LIMIT = 500


def _signing_key() -> bytes:
    """Server-only secret used to sign documents. Rows a browser could have written through the database API are never trusted."""
    key = os.environ.get("BUBBLES_DOC_SIGNING_KEY") or os.environ.get("SUPABASE_SECRET_KEY")
    if not key:
        if os.environ.get("RENDER"):
            raise RuntimeError("No signing key is configured for signed documents")  # never fall back to a published value on the live server
        key = "bubbles-dev-only-signing-key"  # local development and tests only
    return key.encode("utf-8")


def _sig(uid: str, kind: str, key: str, version: int, payload: Any) -> str:
    body = json.dumps([str(uid), kind, str(key), int(version), payload], sort_keys=True, default=str, separators=(",", ":"))
    return hmac.new(_signing_key(), body.encode("utf-8"), hashlib.sha256).hexdigest()


def _scrub(value: Any, depth: int = 0) -> Any:
    """Remove NUL and lone surrogates (valid JSON, rejected by Postgres) from every string, recursively."""
    if depth > 30:
        raise HTTPException(status_code=422, detail="document is nested too deeply")
    if isinstance(value, str):
        return value.replace(chr(0), "").encode("utf-8", "ignore").decode("utf-8")
    if isinstance(value, dict):
        return {_scrub(str(k), depth + 1): _scrub(v, depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_scrub(v, depth + 1) for v in value]
    return value


def row_is_valid(row: dict) -> bool:
    """True only for a document this server signed for this row's owner (blocks forged or foreign rows)."""
    data = row.get("data") if isinstance(row.get("data"), dict) else {}
    sig = data.get("sig")
    if row.get("event_type") != EVENT_TYPE or not isinstance(sig, str) or not row.get("user_id"):
        return False
    try:
        expected = _sig(str(row["user_id"]), str(data.get("kind")), str(data.get("key")), int(data.get("version", 1)), data.get("payload"))
    except (TypeError, ValueError):
        return False
    return hmac.compare_digest(sig, expected)


def _check(kind: str, key: str, payload: Any = None) -> str:
    if not kind or not kind.replace("_", "").isalnum() or len(kind) > 40:
        raise ValueError("bad document kind")
    key = str(key)
    if not key or len(key) > MAX_KEY or ":" in kind:
        raise HTTPException(status_code=422, detail="document key is invalid")
    if payload is not None:
        try:
            size = len(json.dumps(payload, default=str))
        except (TypeError, ValueError, RecursionError):
            raise HTTPException(status_code=422, detail="document is not valid JSON")
        if size > MAX_PAYLOAD_BYTES:
            raise HTTPException(status_code=413, detail="document is too large")
    return f"{kind}:{key}"


def _unpack(row: dict) -> dict:
    data = row.get("data") if isinstance(row.get("data"), dict) else {}
    return {"id": row.get("id"), "kind": data.get("kind"), "key": data.get("key"), "payload": data.get("payload") or {},
            "version": data.get("version", 1), "created_at": row.get("created_at"), "updated_at": row.get("updated_at") or row.get("created_at"),
            "valid": row_is_valid(row)}


def _find(db: Any, uid: str, title: str) -> dict | None:
    rows = (db.table(TABLE).select("*").eq("user_id", uid).eq("event_type", EVENT_TYPE).eq("title", title)
            .order("created_at", desc=True).limit(1).execute().data or [])
    return rows[0] if rows else None


def get(db: Any, uid: str, kind: str, key: str) -> dict | None:
    """The document's payload (a dict) or None."""
    found = _find(db, uid, _check(kind, key))
    return _unpack(found)["payload"] if found and row_is_valid(found) else None


def get_doc(db: Any, uid: str, kind: str, key: str) -> dict | None:
    found = _find(db, uid, _check(kind, key))
    return _unpack(found) if found and row_is_valid(found) else None


def put(db: Any, uid: str, kind: str, key: str, payload: dict, *, when: str | None = None) -> dict:
    """Create or replace one document (history is not kept; plans keep their own version lists). Returns the stored doc."""
    payload = _scrub(payload)
    title = _check(kind, key, payload)
    existing = _find(db, uid, title)
    now = datetime.now(timezone.utc).isoformat()
    if existing:
        version = int((existing.get("data") or {}).get("version", 1)) + 1
        data = {"kind": kind, "key": str(key), "payload": payload, "version": version, "sig": _sig(uid, kind, str(key), version, payload)}
        db.table(TABLE).update({"data": data, "updated_at": now}).eq("id", existing["id"]).eq("user_id", uid).execute()
        return {**_unpack({**existing, "data": data}), "updated_at": now}
    data = {"kind": kind, "key": str(key), "payload": payload, "version": 1, "sig": _sig(uid, kind, str(key), 1, payload)}
    row = {"user_id": uid, "event_type": EVENT_TYPE, "event_date": when or now, "title": title, "source": SOURCE, "user_confirmed": True, "data": data}
    saved = db.table(TABLE).insert(row).select("*").execute()
    if not saved.data:
        raise HTTPException(status_code=500, detail="Unable to save")
    return _unpack(saved.data[0])


def list_docs(db: Any, uid: str, kind: str, limit: int = 200, newest_first: bool = True) -> list[dict]:
    _check(kind, "x")
    rows = (db.table(TABLE).select("*").eq("user_id", uid).eq("event_type", EVENT_TYPE).eq("data->>kind", kind)
            .order("event_date", desc=newest_first).limit(max(1, min(limit, LIST_LIMIT))).execute().data or [])
    return [d for d in (_unpack(r) for r in rows if isinstance(r, dict)) if d["valid"]]


def delete(db: Any, uid: str, kind: str, key: str) -> bool:
    """Remove every row stored for this document (duplicates from concurrent writes included)."""
    title = _check(kind, key)
    found = _find(db, uid, title)
    if not found:
        return False
    db.table(TABLE).delete().eq("user_id", uid).eq("event_type", EVENT_TYPE).eq("title", title).execute()
    return True


SAFETY_HOLD_KINDS = ("safety_pause", "eating_screen")   # kept by "delete all": they only ever make Bubbles MORE careful
TRAIL_KINDS = ("consent_event",)                         # always kept: the minimised record of what a person agreed to (consent.py)
DELETE_CHUNK = 100


def get_many(db: Any, uid: str, kind: str, keys: list[str]) -> dict[str, dict]:
    """Several documents of one kind in ONE read: {key: payload}. Missing, unsigned and foreign rows are left out."""
    wanted = {str(k): _check(kind, k) for k in dict.fromkeys(keys)}
    if not wanted:
        return {}
    rows = (db.table(TABLE).select("*").eq("user_id", uid).eq("event_type", EVENT_TYPE).in_("title", list(wanted.values()))
            .order("created_at", desc=True).limit(len(wanted) * 3).execute().data or [])
    by_title: dict[str, dict] = {}
    for row in rows:
        if row.get("title") not in by_title and row_is_valid(row):   # newest valid row wins, like get()
            by_title[row["title"]] = _unpack(row)["payload"]
    return {key: by_title[title] for key, title in wanted.items() if title in by_title}


def delete_everything(db: Any, uid: str, keep: tuple[str, ...] = SAFETY_HOLD_KINDS) -> int:
    """Remove every Whole-Health OS document for the user except the safety holds in ``keep`` and the consent trail. Returns how many
    were removed. Rows go in chunked deletes (one request per DELETE_CHUNK rows, not one per row)."""
    import consent   # the remembered answer must not outlive the deleted document, even if a delete fails
    keep = tuple(keep) + TRAIL_KINDS
    try:
        try:
            import community_api
            community_api.forget(db, uid)   # posts, comments, reactions, reports and blocks go too
        except Exception:  # noqa: BLE001
            pass
        consent.on_data_deleted(db, uid)   # withdraws what was granted and unlinks the ledger rows from the person
        rows = (db.table(TABLE).select("id,title").eq("user_id", uid).eq("event_type", EVENT_TYPE).limit(20000).execute().data or [])
        ids = [r["id"] for r in rows if str(r.get("title") or "").split(":", 1)[0] not in keep]
        for i in range(0, len(ids), DELETE_CHUNK):
            db.table(TABLE).delete().eq("user_id", uid).eq("event_type", EVENT_TYPE).in_("id", ids[i:i + DELETE_CHUNK]).execute()
        return len(ids)
    finally:
        consent.forget(uid)
