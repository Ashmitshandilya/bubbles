"""Consent: separate purposes, each off until the person says yes, each change written to an append-only ledger.

Bubbles understands emergencies, corrections, daily logs and fitness questions on its own servers. Anything that goes beyond that is a
named purpose (PURPOSES): sending a message to an outside AI model, saving details noticed in chat, sharing with a partner, reminders
by push or email, posting in the community. Each has its own plain-language text, a stable id and a text version.

Storage
  * ``consent_events`` (supabase/migrations/20261016_bubbles_consent_events.sql): one row per decision, append only. The current state of
    a purpose is its newest row, and it counts only while the text version it was given for is still the current one.
  * Until that migration is applied the same events are written as signed documents of kind ``consent_event`` (doc_store), which
    ``doc_store.delete_everything`` always keeps. The trail is never lost and the app works either way.
  * The older single yes (document ``consent`` / ``ai_chat``) still counts for ``ai_chat_processing`` while it is unchanged.

"Delete my data" keeps a minimised trail (purpose, decision, timestamps, a one-way hash of the person): see ``on_data_deleted``.
Read errors are fail-closed. The answer is remembered per person for 5 minutes and forgotten at once on every write.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

import doc_store
from ttl_cache import TTLCache

KIND = "consent"            # the older single yes: document kind / key
KEY = "ai_chat"
VERSION = "2026-10b"        # text version of ai_chat_processing (kept so an old yes keeps its meaning). Bump when what is sent changes.
POLICY_VERSION = "2026-10-23c"
"""Version of the privacy notice (frontend/app/lib/privacy-notice-version.ts must match; a test pins it)."""

TABLE = "consent_events"
EVENT_KIND = "consent_event"
SOURCES = ("settings", "chat_card", "onboarding", "system", "signup")
ACK_PURPOSE = "ack_terms_privacy"
REASK_AFTER_DAYS = 14
MAX_HISTORY = 500
LEDGER_FIELDS = ("id", "purpose", "granted", "policy_version", "text_version", "text_hash", "source", "created_at")

URGENT_LINE = "If something feels urgent, call your local emergency number."

PURPOSES: dict[str, dict[str, Any]] = {
    "ai_chat_processing": {
        "title": "Answer open questions with an outside AI",
        "description": "Your message, your recent messages in the chat and a short summary of your profile and notes (such as your date of birth, "
                       "gender and recent entries) go to an outside AI model so Bubbles can write an answer.",
        "text_version": VERSION, "available": True,
    },
    "health_memory_from_chat": {
        "title": "Save details Bubbles notices in chat",
        "description": "When you mention something about your health in chat, Bubbles suggests saving it so you can confirm or dismiss it. "
                       "When this is off, chat still works and anything you log yourself is still saved.",
        "text_version": "2026-10a", "available": True,
    },
    "partner_sharing": {
        "title": "Share summaries with one person",
        "description": "Lets you choose a few summaries (not your chats or logs) for one person you trust to see. Nothing is shared until you pick what and who.",
        "text_version": "2026-10a", "available": True,
    },
    "orbit_partner_signals": {
        "title": "Let Orbit share gentle signals with my partner",
        "description": "Lets you switch on two things for the person you are connected with: your answers to shared questions and check-ins (shown only when you have both answered), "
                       "and gentle general nudges that never say what you logged. You choose each one, and you can stop at any time.",
        "text_version": "2026-10a", "available": True,
    },
    "push_notifications": {
        "title": "Reminders on your phone",
        "description": "Bubbles sends gentle reminders to this phone. They never contain health details.",
        "text_version": "2026-10a", "available": True,
    },
    "email_reminders": {
        "title": "Reminders by email",
        "description": "Bubbles sends gentle reminders to the email address you signed in with. They never contain health details.",
        "text_version": "2026-10a", "available": True,
    },
    "community_visibility": {
        "title": "Show my posts in the community",
        "description": "Lets your posts and comments appear to other people in the community, under the name or alias you choose.",
        "text_version": "2026-10a", "available": True,
    },
    "product_usage_metrics": {
        "title": "Anonymous usage counts",
        "description": "Share counts of which screens are used, with no messages or health details, to help improve Bubbles. Not available yet.",
        "text_version": "2026-10a", "available": False,
    },
}
ALIASES = {"ai_chat": "ai_chat_processing"}

DISCLOSURES = [{
    "id": "service_storage",
    "title": "Keeping your own logs and chat",
    "text": "Bubbles has to store what you log and what you say in chat so it can remember for you. Only you can see it, and you can delete it in Settings.",
}]

_cache = TTLCache("consent", ttl_s=300, max_entries=5000)
_table_state = TTLCache("consent_table", ttl_s=60, max_entries=4)   # "is the ledger table usable": re-checked every minute


class ConsentError(Exception):
    """A request the person (or app) got wrong. ``status`` is the HTTP status to answer with."""

    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status, self.detail = status, detail


# ---- wording and hashes ----------------------------------------------------------------------------------------------------

def canonical(purpose: str) -> str:
    return ALIASES.get(str(purpose), str(purpose))


def text_hash(purpose: str) -> str:
    """Short fingerprint of the wording a person is shown. A grant must quote it, so a stale screen cannot grant new wording."""
    p = PURPOSES[canonical(purpose)]
    return hashlib.sha256(f"{canonical(purpose)}|{p['text_version']}|{p['description']}".encode("utf-8")).hexdigest()[:16]


def _uid_hash(uid: str) -> str:
    return hmac.new(doc_store._signing_key(), f"consent-trail:{uid}".encode("utf-8"), hashlib.sha256).hexdigest()[:32]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ts(raw: Any) -> datetime:
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).astimezone(timezone.utc)
    except (TypeError, ValueError):
        return datetime(1970, 1, 1, tzinfo=timezone.utc)


# ---- ledger storage (table first, signed documents until the migration is applied) ----------------------------------------

def _is_missing(exc: Exception) -> bool:
    """True when the ledger table cannot be used yet: not created (42P01 / PGRST205) or not granted to the backend (42501)."""
    from db_access import is_permission_denied
    if is_permission_denied(exc):
        return True
    text = f"{getattr(exc, 'code', '')} {exc!r} {exc}".lower()
    return any(s in text for s in ("42p01", "pgrst205", "does not exist", "could not find the table", "schema cache"))


def _table_usable() -> bool:
    return _table_state.peek("usable") is not False


def _mark_table(usable: bool) -> None:
    _table_state.put("usable", usable)


def _table_events(db: Any, uid: str) -> list[dict] | None:
    if not _table_usable():
        return None
    try:
        rows = (db.table(TABLE).select(",".join(LEDGER_FIELDS))
                .eq("user_id", uid).order("created_at", desc=True).limit(MAX_HISTORY).execute().data or [])
    except Exception as exc:  # noqa: BLE001
        if not _is_missing(exc):
            raise
        _mark_table(False)
        return None
    return [{k: r.get(k) for k in LEDGER_FIELDS} for r in rows if isinstance(r, dict)]


def _doc_events(db: Any, uid: str) -> list[dict]:
    out = []
    for d in doc_store.list_docs(db, uid, EVENT_KIND, limit=MAX_HISTORY):
        p = d.get("payload") or {}
        if p.get("purpose"):
            out.append({"id": d.get("key"), **{k: p.get(k) for k in ("purpose", "granted", "policy_version", "text_version", "text_hash", "source", "created_at")}})
    return out


def events(db: Any, uid: str) -> list[dict]:
    """Every recorded decision of this person, newest first (ledger table and fallback documents merged)."""
    merged = (_table_events(db, uid) or []) + _doc_events(db, uid)
    seen, out = set(), []
    for e in sorted(merged, key=lambda e: _ts(e.get("created_at")), reverse=True):
        sig = (e.get("purpose"), e.get("created_at"), e.get("granted"))
        if sig not in seen:
            seen.add(sig)
            out.append(e)
    return out


def _append(db: Any, uid: str, event: dict) -> None:
    if _table_usable():
        try:
            db.table(TABLE).insert({"user_id": uid, "user_hash": _uid_hash(uid), **event}).execute()
            return
        except Exception as exc:  # noqa: BLE001
            if not _is_missing(exc):
                raise
            _mark_table(False)
    doc_store.put(db, uid, EVENT_KIND, f"{int(datetime.now(timezone.utc).timestamp() * 1000)}-{event['purpose']}-{secrets.token_hex(2)}", event)


# ---- current state ---------------------------------------------------------------------------------------------------------

def _compute(db: Any, uid: str) -> dict[str, dict]:
    ledger = events(db, uid)
    out: dict[str, dict] = {}
    for pid, spec in PURPOSES.items():
        mine = [e for e in ledger if e.get("purpose") == pid]
        latest = mine[0] if mine else None
        if latest is None and pid == "ai_chat_processing":   # the older single yes, while its wording is unchanged
            doc = doc_store.get(db, uid, KIND, KEY) or {}
            if doc.get("accepted") is True and doc.get("version") == VERSION:
                latest = {"granted": True, "text_version": VERSION, "created_at": doc.get("at"), "source": "settings"}
        current = bool(latest) and latest.get("text_version") == spec["text_version"]
        granted = bool(latest and latest.get("granted") is True and current and spec["available"])
        declined = next((e for e in mine if e.get("granted") is False), None)
        out[pid] = {
            "granted": granted,
            "decision": "granted" if granted else ("declined" if latest and latest.get("granted") is False and current else "none"),
            "decided_at": latest.get("created_at") if latest else None,
            "declined_at": declined.get("created_at") if declined and declined.get("text_version") == spec["text_version"] else None,
        }
    return out


def _states(db: Any, uid: str) -> dict[str, dict]:
    return _cache.get_or_compute((uid, "all"), lambda: _compute(db, uid))


def forget(uid: str) -> None:
    _cache.invalidate((uid, "all"))


def is_granted(db: Any, uid: str, purpose: str) -> bool:
    """True only when this person has said yes to this purpose, for the wording currently shown. Missing, unknown, unavailable or
    unreadable all mean False, so nothing happens without a clear yes."""
    pid = canonical(purpose)
    if pid not in PURPOSES or not PURPOSES[pid]["available"] or not uid:
        return False
    try:
        return bool(_states(db, uid).get(pid, {}).get("granted"))
    except Exception:  # noqa: BLE001 - if consent cannot be read, nothing is done
        return False


def has_ai_consent(db: Any, uid: str) -> bool:
    return is_granted(db, uid, "ai_chat_processing")


def purpose_state(db: Any, uid: str, purpose: str, states: dict[str, dict] | None = None) -> dict:
    pid = canonical(purpose)
    spec = PURPOSES[pid]
    s = (states if states is not None else _states(db, uid))[pid]
    return {"id": pid, "title": spec["title"], "description": spec["description"], "text_version": spec["text_version"],
            "text_hash": text_hash(pid), "available": spec["available"], "granted": s["granted"], "decision": s["decision"],
            "decided_at": s["decided_at"]}


def overview(db: Any, uid: str) -> dict:
    return {"policy_version": POLICY_VERSION, "purposes": [purpose_state(db, uid, p) for p in PURPOSES], "disclosures": DISCLOSURES}


def history(db: Any, uid: str, limit: int = 100) -> list[dict]:
    out = []
    for e in events(db, uid)[: max(1, min(limit, MAX_HISTORY))]:
        pid = e.get("purpose")
        spec = PURPOSES.get(pid)
        if spec is None and pid != ACK_PURPOSE:
            continue
        out.append({"purpose": pid, "title": spec["title"] if spec else "Terms and Privacy notice", "granted": e.get("granted") is True,
                    "source": e.get("source"), "text_version": e.get("text_version"), "created_at": e.get("created_at"),
                    "kind": "consent" if spec else "acknowledgement"})
    return out


def state(db: Any, uid: str) -> dict:
    """The shape of GET /me/consent (kept for the Settings row and older app builds)."""
    s = _states(db, uid)["ai_chat_processing"]
    return {"ai_chat": s["granted"], "version": VERSION, "decided_at": s["decided_at"]}


# ---- changes ---------------------------------------------------------------------------------------------------------------

def _mirror_channel(db: Any, uid: str, channel: str, on: bool) -> None:
    """Keep the notification settings' channel switch equal to the consent (the reminder code reads the switch)."""
    import notifications
    current = notifications.load_settings(db, uid)
    if current["channels"].get(channel) is not on:
        notifications.save_settings(db, uid, notifications.normalize_settings({"channels": {channel: on}}, current))


def _after_change(db: Any, uid: str, purpose: str, granted: bool) -> None:
    """Withdrawal has its natural stop: partner sharing ends, the reminder channel goes off."""
    try:
        if purpose == "partner_sharing" and not granted:
            import partner_sharing
            partner_sharing.stop_all(db, uid)
        elif purpose == "community_visibility" and not granted:
            import community_api
            community_api.hold_all(db, uid)   # what they wrote stops showing to others; re-granting does not bring it back on its own
        elif purpose == "email_reminders":
            _mirror_channel(db, uid, "email", granted)
        elif purpose == "push_notifications":
            _mirror_channel(db, uid, "push", granted)
    except Exception:  # noqa: BLE001 - the decision itself is already recorded; every later use re-checks it
        pass


def set_purpose(db: Any, uid: str, purpose: str, granted: bool, *, source: str = "settings", hash_seen: str | None = None) -> dict:
    """Record one decision (appends a ledger row) and return the purpose's new state. A grant must quote the current text hash."""
    pid = canonical(purpose)
    if pid not in PURPOSES:
        raise ConsentError(404, "Unknown choice")
    if not isinstance(granted, bool):
        raise ConsentError(422, "granted must be true or false")
    if source not in SOURCES:
        raise ConsentError(422, "source is not valid")
    spec = PURPOSES[pid]
    if granted:
        if not spec["available"]:
            raise ConsentError(409, "This choice is not available yet")
        if not hash_seen:
            raise ConsentError(422, "text_hash is required to say yes")
        if not hmac.compare_digest(str(hash_seen), text_hash(pid)):
            raise ConsentError(409, "The wording changed. Please read it again")
    forget(uid)
    try:
        before = _compute(db, uid)[pid]
        if source != "settings" or before["granted"] is not granted or before["decision"] == "none":
            _append(db, uid, {"purpose": pid, "granted": granted, "policy_version": POLICY_VERSION, "text_version": spec["text_version"],
                              "text_hash": text_hash(pid), "source": source, "created_at": _now()})
    finally:
        forget(uid)
    _after_change(db, uid, pid, granted)
    return purpose_state(db, uid, pid, _compute(db, uid))   # read fresh and not remembered: the next question reads it itself


def set_ai_chat(db: Any, uid: str, accepted: bool, source: str = "settings") -> dict:
    """The older single switch: a decision on ai_chat_processing (``source`` says which screen it came from)."""
    now = set_purpose(db, uid, "ai_chat_processing", bool(accepted), source=source, hash_seen=text_hash("ai_chat_processing"))
    return {"ai_chat": now["granted"], "version": VERSION, "decided_at": now["decided_at"]}


def acknowledge(db: Any, uid: str, version: str, *, source: str = "signup") -> dict:
    """Record that the person was shown the Terms and the Privacy notice (an acknowledgement, not a consent to anything)."""
    version = str(version or "")[:24]
    if not version or source not in SOURCES:
        raise ConsentError(422, "version is required")
    _append(db, uid, {"purpose": ACK_PURPOSE, "granted": True, "policy_version": version, "text_version": version, "text_hash": None,
                      "source": source, "created_at": _now()})
    return {"acknowledged": True, "version": version}


def on_data_deleted(db: Any, uid: str) -> None:
    """Called by "delete my data" before the documents go: withdraw what is granted, then drop the link between the ledger and the
    person (user_id becomes null; purpose, decision, timestamps, versions and the one-way hash stay). Never blocks the deletion."""
    try:
        for pid, s in _compute(db, uid).items():
            if s["granted"]:
                _append(db, uid, {"purpose": pid, "granted": False, "policy_version": POLICY_VERSION, "text_version": PURPOSES[pid]["text_version"],
                                  "text_hash": text_hash(pid), "source": "system", "created_at": _now()})
        if _table_usable():
            try:
                db.table(TABLE).update({"user_id": None}).eq("user_id", uid).execute()
            except Exception as exc:  # noqa: BLE001
                if not _is_missing(exc):
                    raise
    except Exception:  # noqa: BLE001
        pass
    finally:
        forget(uid)


# ---- enforcement helpers ---------------------------------------------------------------------------------------------------

def persist_chat_events(db: Any, uid: str, message_id: str | None, events_: list[dict], persist: Callable[..., list[dict]] | None = None, **kw: Any) -> list[dict]:
    """Save details noticed in chat as suggestions, only when the person agreed (health_memory_from_chat). Otherwise nothing is
    extracted or stored from the chat. ``persist`` defaults to chat_pipeline.persist_events."""
    if not events_ or not is_granted(db, uid, "health_memory_from_chat"):
        return []
    if persist is None:
        from chat_pipeline import persist_events as persist   # noqa: PLW0127 - imported late: chat_pipeline imports this module's callers
    return persist(db, uid, message_id, events_, **kw)


def reask_due(db: Any, uid: str, now: datetime | None = None) -> bool:
    """False while a decline of the AI question is recent (14 days) for the current wording: the chat then shows a small line instead."""
    try:
        s = _states(db, uid)["ai_chat_processing"]
    except Exception:  # noqa: BLE001
        return True
    if s["granted"] or not s["declined_at"]:
        return True
    return (now or datetime.now(timezone.utc)) - _ts(s["declined_at"]) >= timedelta(days=REASK_AFTER_DAYS)


def consent_needed_reply(name: str | None = None) -> str:
    who = f"{name}, to" if name else "To"
    return (
        f"{who} answer this I'd use an outside AI model. It would get your message, your recent messages here and a short summary "
        "of your profile and notes (such as your date of birth, gender and recent entries). Nothing is sent unless you say yes, "
        "and you can change it any time in Settings.\n\n"
        f"Without it I can still log things and answer questions about your cycle, sleep and fitness. {URGENT_LINE}"
    )


def declined_reply(name: str | None = None) -> str:
    who = f"No problem, {name}." if name else "No problem."
    return (
        f"{who} Nothing is sent to an outside AI. I can still log things, show your patterns and answer questions about your cycle, sleep and fitness. "
        f"If you change your mind, it is one switch in Privacy choices.\n\n{URGENT_LINE}"
    )


def chat_prompt(db: Any, uid: str, name: str | None = None) -> dict:
    """What the chat shows when it needs the AI answer and there is no yes: ``ask`` (show the Yes / No card) and the ``reply`` text."""
    ask = reask_due(db, uid)
    return {"ask": ask, "reply": consent_needed_reply(name) if ask else declined_reply(name)}


# ---- admin: counts only ----------------------------------------------------------------------------------------------------

def consent_rates(db: Any, limit: int = 50000) -> dict:
    """Per purpose: how many people's newest decision is yes / no. Counts only, from the ledger table (nothing cross-person is
    readable from the fallback documents, so then ``available`` is false)."""
    try:
        rows = (db.table(TABLE).select("user_hash,purpose,granted,text_version,created_at").order("created_at", desc=True).limit(limit).execute().data or [])
    except Exception:  # noqa: BLE001
        return {"available": False, "purposes": {}, "people_decided": 0}
    latest: dict[tuple[str, str], dict] = {}
    for r in rows:
        if isinstance(r, dict) and r.get("purpose") in PURPOSES:
            latest.setdefault((str(r.get("user_hash")), r["purpose"]), r)
    purposes: dict[str, dict] = {}
    for pid, spec in PURPOSES.items():
        mine = [r for (u, p), r in latest.items() if p == pid and r.get("text_version") == spec["text_version"]]
        yes = sum(1 for r in mine if r.get("granted") is True)
        purposes[pid] = {"granted": yes, "declined": len(mine) - yes, "decided": len(mine), "rate": round(yes / len(mine), 3) if mine else None}
    return {"available": True, "purposes": purposes, "people_decided": len({u for (u, _p) in latest}), "truncated": len(rows) >= limit}
