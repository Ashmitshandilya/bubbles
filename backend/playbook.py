"""The Playbook (renovation plan 9.2): learning which reply shapes help people, from de-identified examples that people agreed to share.

What this module does, and the limits it keeps:
  * Capture needs the person's own yes (consent purpose ``improve_bubbles``). It stores only a de-identified REPLY, an intent, a language
    mix, a rating and an outcome. Never the person's message and never a user id; ``cohort_hash`` is an HMAC that only lets us count
    distinct people.
  * Capture is limited to the intents in ``INTENTS``; those are the ones an approved entry may later be used for. Health, safety,
    Safe Harbor and relationship replies are never captured (``blocked_route``).
  * A cluster becomes a DRAFT only when ``MIN_PEOPLE`` distinct people produced helpful replies for the same intent and language.
    Nothing reaches a user until the owner approves it in the admin console.
  * Every function returns quietly when the tables have not been created yet (the migration is applied by the owner).
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import consent
from ttl_cache import TTLCache

PURPOSE = "improve_bubbles"
CANDIDATES, ENTRIES = "bubbles_playbook_candidates", "bubbles_playbook"
MIN_PEOPLE = 20
KEEP_DAYS = 90
MAX_REPLY_CHARS = 700
STATUSES = ("draft", "approved", "retired")
OUTCOMES = ("helpful", "unhelpful", "unknown")

# intent -> words in the person's message that mark it. Only app-help intents: never health, safety, Safe Harbor or relationship advice.
INTENTS: dict[str, tuple[str, ...]] = {
    "app.greeting": ("hi", "hello", "hey", "good morning", "good evening", "namaste"),
    "app.what_can_you_do": ("what can you do", "what do you do", "how can you help", "kya kar sakte", "kya kar sakti"),
    "app.how_to_log": ("how do i log", "how to log", "how do i add", "kaise log", "where do i log"),
    "app.how_it_works": ("how does bubbles work", "how do you work", "how does this work", "kaise kaam"),
}
BLOCKED_ROUTES = frozenset({"emergency", "safe_harbor", "safety_followup", "orbit", "orbit_redirect", "correction", "clarification"})
_ALLOWED_CAPS = frozenset({"I", "I'm", "I'll", "I've", "I'd", "Bubbles", "Today", "Talk", "Patterns", "Track", "Mind", "Community", "Cycle", "Fitness",
                           "Care", "Orbit", "Me", "Settings", "English", "Hinglish", "Hindi"})   # the app's own words, never a person's

_cache = TTLCache("playbook", ttl_s=300, max_entries=200)   # approved guidance text only: no user data, so one cache for everyone


def intent_of(message: str) -> str | None:
    """The app-help intent a message asks for, or None. Whole-phrase matches only, so 'hi' never matches inside another word."""
    text = " " + re.sub(r"[^a-z0-9' ]+", " ", (message or "").lower()).strip() + " "
    words = len(text.split())
    if words > 8:
        return None
    for intent, phrases in INTENTS.items():
        if any(f" {p} " in text for p in phrases):
            # a greeting must be nearly the whole message, so "hi, my chest hurts" is never treated as small talk
            if intent == "app.greeting" and words > 3:
                continue
            return intent
    return None


def blocked_route(route: str | None) -> bool:
    return (route or "") in BLOCKED_ROUTES


# ---- de-identification ---------------------------------------------------------------------------------------------------------

_PATTERNS = [
    (re.compile(r"https?://\S+|www\.\S+", re.I), " "),
    (re.compile(r"\b[\w.+-]+@[\w-]+(\.[\w-]+)+\b"), " "),
    (re.compile(r"(?<!\w)\+?\d[\d\s().-]{6,}\d"), " "),                                   # phone numbers
    (re.compile(r"\b\d{1,2}[/-]\d{1,2}([/-]\d{2,4})?\b|\b\d{4}-\d{2}-\d{2}\b"), " "),      # dates
    (re.compile(r"\b\d+(\.\d+)?\s?(h|hr|hrs|hours?|mins?|minutes?|kg|lbs?|cm|ft|ml|l|kcal|bpm|mg|g|%)\b", re.I), " "),
]


def deidentify(text: str, names: list[str] | tuple[str, ...] = (), places: list[str] | tuple[str, ...] = ()) -> str | None:
    """The reply with names, places, numbers with units, dates, emails, phones and URLs removed, or None when anything that still looks
    personal remains (a capitalised word that is not the start of a sentence, a digit, an @). None means: do not store it."""
    out = str(text or "").strip()
    for name in sorted({n.strip() for n in [*names, *places] if n and len(n.strip()) >= 2}, key=len, reverse=True):
        out = re.sub(rf"(?<!\w){re.escape(name)}(?!\w)", "[someone]", out, flags=re.I)
    for pattern, repl in _PATTERNS:
        out = pattern.sub(repl, out)
    out = re.sub(r"\s+", " ", out).strip()
    if not out or len(out) > MAX_REPLY_CHARS or re.search(r"\d|@", out):
        return None
    # lower the first letter of each sentence, then no capitalised word may remain outside the allow-list
    probe = re.sub(r"(^|[.!?]\s+)([A-Z])", lambda m: m.group(1) + m.group(2).lower(), out)
    for word in re.findall(r"\b[A-Z][\w']*", probe):
        if word not in _ALLOWED_CAPS:
            return None
    return out


def cohort_hash(uid: str, now: datetime | None = None) -> str:
    """HMAC of the user id with a server secret and the month, so distinct people can be counted but not named, and the link rotates monthly."""
    secret = (os.getenv("BUBBLES_PLAYBOOK_SECRET") or os.getenv("BUBBLES_DOC_SIGNING_KEY") or "").encode()
    month = (now or datetime.now(timezone.utc)).strftime("%Y-%m")
    return hmac.new(secret, f"{uid}|{month}".encode(), hashlib.sha256).hexdigest()[:32]


# ---- capture ------------------------------------------------------------------------------------------------------------------

def capture(db: Any, uid: str, *, intent: str | None, language: str, route: str, reply: str, rating: str, outcome: str,
            names: list[str] | tuple[str, ...] = (), places: list[str] | tuple[str, ...] = ()) -> bool:
    """Store one de-identified candidate. False (and nothing stored) without a yes, for a blocked route, an unknown intent, a reply that
    cannot be fully de-identified, or when the table does not exist yet."""
    if intent not in INTENTS or blocked_route(route) or outcome not in OUTCOMES or rating not in ("up", "down", "none"):
        return False
    try:
        if not consent.is_granted(db, uid, PURPOSE):
            return False
        clean = deidentify(reply, names, places)
        if clean is None:
            return False
        db.table(CANDIDATES).insert({"intent": intent, "language": language if language in ("english", "hinglish", "hindi") else "english",
                                     "route": route, "reply_text": clean, "rating": rating, "outcome": outcome, "cohort_hash": cohort_hash(uid)}).execute()
        return True
    except Exception:  # noqa: BLE001 - learning must never get in the way of a reply, and a missing table is just "not set up yet"
        return False


# ---- promotion, purge, use ----------------------------------------------------------------------------------------------------

def _rows(db: Any, table: str, **eq: Any) -> list[dict]:
    query = db.table(table).select("*")
    for key, value in eq.items():
        query = query.eq(key, value)
    return query.limit(5000).execute().data or []


def promote(db: Any) -> int:
    """New drafts from clusters of helpful candidates backed by at least MIN_PEOPLE distinct people. Returns how many drafts were made."""
    made = 0
    try:
        helpful = [r for r in _rows(db, CANDIDATES) if r.get("outcome") == "helpful" or r.get("rating") == "up"]
        existing = {(e.get("intent"), e.get("language")) for e in _rows(db, ENTRIES) if e.get("status") in ("draft", "approved")}
        clusters: dict[tuple[str, str], list[dict]] = {}
        for r in helpful:
            clusters.setdefault((r["intent"], r["language"]), []).append(r)
        for (intent, language), rows in clusters.items():
            if (intent, language) in existing or len({r["cohort_hash"] for r in rows}) < MIN_PEOPLE:
                continue
            counts: dict[str, int] = {}
            for r in rows:
                counts[r["reply_text"]] = counts.get(r["reply_text"], 0) + 1
            example = max(counts, key=lambda t: (counts[t], -len(t)))
            db.table(ENTRIES).insert({"intent": intent, "language": language, "guidance_text": "", "example_text": example, "status": "draft",
                                      "uses": 0, "helpful": 0}).execute()
            made += 1
    except Exception:  # noqa: BLE001
        return made
    return made


def purge(db: Any, now: datetime | None = None) -> None:
    """Candidates older than KEEP_DAYS go."""
    cutoff = ((now or datetime.now(timezone.utc)) - timedelta(days=KEEP_DAYS)).isoformat()
    try:
        db.table(CANDIDATES).delete().lt("created_at", cutoff).execute()
    except Exception:  # noqa: BLE001
        pass


def maintain(db: Any) -> dict[str, int]:
    """Called by the scheduler: purge old candidates, then promote clusters. Counts only."""
    purge(db)
    return {"drafts_made": promote(db)}


def approved_for(db: Any, intent: str | None, language: str) -> dict | None:
    """The one approved entry for this intent and language, or None. Only app-help intents ever have one used."""
    if intent not in INTENTS:
        return None
    def load() -> dict | None:
        try:
            rows = [e for e in _rows(db, ENTRIES, intent=intent, status="approved") if e.get("language") == language]
        except Exception:  # noqa: BLE001
            return None
        return rows[0] if rows else None
    return _cache.get_or_compute((intent, language), load)


def note_use(db: Any, entry: dict, helpful: bool | None = None) -> None:
    """Count one use (and a later thumbs) on an approved entry. Never raises."""
    try:
        patch = {"uses": int(entry.get("uses") or 0) + 1}
        if helpful:
            patch["helpful"] = int(entry.get("helpful") or 0) + 1
        db.table(ENTRIES).update(patch).eq("id", entry["id"]).execute()
        _cache.clear()
    except Exception:  # noqa: BLE001
        pass


def block_for_prompt(entry: dict | None) -> str:
    """The text added to the model prompt for an approved entry, or ''. Adapt, never copy, never a fact about the person."""
    text = str((entry or {}).get("guidance_text") or (entry or {}).get("example_text") or "").strip()
    if not text:
        return ""
    return ("\n\nPLAYBOOK (a reply shape that has helped people with this; adapt, never copy, never treat as a fact about this person):\n- " + text)


# ---- owner review (admin console) ---------------------------------------------------------------------------------------------

def admin_list(db: Any) -> dict[str, Any]:
    """Entries by status, plus how many distinct people stand behind each intent and language (a count, never an id)."""
    try:
        entries = _rows(db, ENTRIES)
        people: dict[tuple[str, str], set[str]] = {}
        for r in _rows(db, CANDIDATES):
            if r.get("outcome") == "helpful" or r.get("rating") == "up":
                people.setdefault((r["intent"], r["language"]), set()).add(r["cohort_hash"])
    except Exception:  # noqa: BLE001 - tables not created yet
        return {"ready": False, "entries": [], "message": "The Playbook tables are not set up yet. Apply 20261101_bubbles_playbook.sql in Supabase."}
    out = []
    for e in sorted(entries, key=lambda x: (STATUSES.index(x.get("status", "draft")) if x.get("status") in STATUSES else 9, str(x.get("intent")))):
        uses, helpful = int(e.get("uses") or 0), int(e.get("helpful") or 0)
        out.append({"id": e["id"], "intent": e["intent"], "language": e["language"], "status": e.get("status"), "guidance_text": e.get("guidance_text") or "",
                    "example_text": e.get("example_text") or "", "uses": uses, "helpful": helpful, "approved_at": e.get("approved_at"),
                    "people": len(people.get((e["intent"], e["language"]), ())),
                    "flagged": e.get("status") == "approved" and uses >= 20 and helpful / uses < 0.3})   # stopped helping: look again
    return {"ready": True, "entries": out, "min_people": MIN_PEOPLE}


def admin_apply(db: Any, entry_id: str, action: str, guidance_text: str | None = None) -> dict[str, Any]:
    """approve, retire or edit one entry. Raises ValueError with a plain code for anything not allowed."""
    if action not in ("approve", "retire", "edit"):
        raise ValueError("unknown_action")
    rows = [r for r in _rows(db, ENTRIES, id=entry_id)]
    if not rows:
        raise ValueError("not_found")
    patch: dict[str, Any] = {}
    if guidance_text is not None:
        text = re.sub(r"\s+", " ", guidance_text).strip()
        if len(text) > MAX_REPLY_CHARS or re.search(r"@|https?://", text):
            raise ValueError("bad_text")
        patch["guidance_text"] = text
    if action == "approve":
        if not (patch.get("guidance_text") or rows[0].get("guidance_text") or rows[0].get("example_text")):
            raise ValueError("empty_entry")
        patch.update(status="approved", approved_at=datetime.now(timezone.utc).isoformat())
    elif action == "retire":
        patch["status"] = "retired"
    db.table(ENTRIES).update(patch).eq("id", entry_id).execute()
    _cache.clear()
    return {"id": entry_id, "action": action, "status": patch.get("status", rows[0].get("status"))}


def capture_from_feedback(db: Any, uid: str, message_id: str, rating: str) -> bool:
    """After a thumbs on a Bubbles reply: when the message before it was a plain app question, the person has said yes, and the reply can be
    fully de-identified, keep it as a candidate. Never raises and never changes the rating."""
    try:
        if rating not in ("up", "down") or not consent.is_granted(db, uid, PURPOSE):
            return False
        reply = (db.table("chat_messages").select("id,content,conversation_id,created_at").eq("id", message_id).eq("user_id", uid).limit(1).execute().data or [None])[0]
        if not reply:
            return False
        before = (db.table("chat_messages").select("content,role,created_at").eq("conversation_id", reply["conversation_id"]).eq("user_id", uid)
                  .lt("created_at", reply["created_at"]).order("created_at", desc=True).limit(3).execute().data or [])
        asked = next((m for m in before if str(m.get("role", "")).lower() == "user"), None)
        intent = intent_of(str((asked or {}).get("content") or ""))
        if not intent:
            return False
        language = "hinglish" if re.search(r"\b(kya|kaise|hai|mujhe|karo|aap)\b", str(asked.get("content")), re.I) else "english"
        return capture(db, uid, intent=intent, language=language, route="rated_reply", reply=str(reply.get("content") or ""),
                       rating=rating, outcome="helpful" if rating == "up" else "unhelpful")
    except Exception:  # noqa: BLE001
        return False
