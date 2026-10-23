"""Open threads: a concern the person raised that has not been closed, so Bubbles can ask about it once, warmly, next time.

Plan 6.4. A thread is a signed ``open_thread`` document (one per concern, key = the concept), written after a reply from facts the person
reported about themselves: a symptom of severity 4 or more, or one that keeps coming back. It holds the concept and when, never the message.
It closes when the person says it is gone or better, or after 7 days.

At most three threads reach the model, only when a new conversation starts, and a thread that was asked about is not asked again for 24 hours.
Never for safety topics (those have their own follow-up rules) and never for Safe Harbor content: a fact with a safety tier, a crisis concept,
or any turn whose safety state is not plain is ignored here.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import doc_store
from health_semantics import CRISIS, display_name

KIND = "open_thread"
MIN_SEVERITY = 4
MAX_AGE_DAYS = 7
REASK_HOURS = 24
MAX_IN_PROMPT = 3
ACTIVE = {"current", "recent", "recurring", "unknown"}
MAX_THREADS = 30


def _parse(at: Any) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(at).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def worth_opening(fact: Any) -> bool:
    """A self-reported, active, non-safety symptom that is strong or keeps coming back."""
    if fact.experiencer != "self" or fact.assertion != "present" or fact.temporal not in ACTIVE:
        return False
    if fact.tier or fact.concept in CRISIS:
        return False
    return (fact.severity or 0) >= MIN_SEVERITY or fact.temporal == "recurring"


def closes(fact: Any) -> bool:
    """The person says it is gone or better: denied, or resolved."""
    return fact.experiencer == "self" and (fact.assertion == "negated" or fact.temporal == "resolved")


def is_open(doc: dict[str, Any], now: datetime) -> bool:
    opened = _parse(doc.get("opened_at"))
    return bool(doc.get("concept")) and not doc.get("closed_at") and opened is not None and now - opened <= timedelta(days=MAX_AGE_DAYS)


def due(doc: dict[str, Any], now: datetime) -> bool:
    """Open, and not asked about in the last 24 hours."""
    asked = _parse(doc.get("asked_at"))
    return is_open(doc, now) and (asked is None or now - asked >= timedelta(hours=REASK_HOURS))


def block(docs: list[dict[str, Any]], now: datetime) -> str:
    """The OPEN THREADS lines for the prompt (newest first, at most three), or "". Wording says how long ago, never what they wrote."""
    rows = sorted((d for d in docs if due(d, now)), key=lambda d: str(d.get("opened_at")), reverse=True)[:MAX_IN_PROMPT]
    if not rows:
        return ""
    lines = []
    for d in rows:
        days = max(0, (now - _parse(d["opened_at"])).days)  # type: ignore[operator]
        when = "today" if days == 0 else "yesterday" if days == 1 else f"{days} days ago"
        lines.append(f"- {display_name(d['concept'])} (they mentioned it {when})")
    return ("OPEN THREADS (things they raised that are not settled; if it fits, ask about ONE of them, once, in a few warm words, and let it go if they do):\n"
            + "\n".join(lines))


def _key(concept: str) -> str:
    return str(concept)[:60]


def load_due(db: Any, uid: str, now: datetime | None = None) -> list[dict[str, Any]]:
    """The person's due open threads, newest first. Never raises."""
    now = now or datetime.now(timezone.utc)
    try:
        docs = [d["payload"] for d in doc_store.list_docs(db, uid, KIND, limit=MAX_THREADS)]
        return [d for d in docs if due(d, now)]
    except Exception:  # noqa: BLE001
        return []


def prompt_block(db: Any, uid: str, now: datetime | None = None) -> str:
    return block(load_due(db, uid, now), now or datetime.now(timezone.utc))


def mark_asked(db: Any, uid: str, concepts: list[str], now: datetime | None = None) -> None:
    now = now or datetime.now(timezone.utc)
    for concept in concepts:
        try:
            doc = doc_store.get(db, uid, KIND, _key(concept))
            if doc:
                doc_store.put(db, uid, KIND, _key(concept), {**doc, "asked_at": now.isoformat()})
        except Exception:  # noqa: BLE001
            pass


def _may_open(db: Any, uid: str) -> bool:
    """A thread keeps a symptom the person mentioned, so it needs the same yes as the other details noticed in chat. Closing one never does."""
    try:
        from consent import is_granted
        return bool(is_granted(db, uid, "health_memory_from_chat"))
    except Exception:  # noqa: BLE001
        return False


def mark_shown(db: Any, uid: str, now: datetime | None = None) -> None:
    """The newest due threads (the ones ``prompt_block`` just offered) count as asked. Never raises."""
    now = now or datetime.now(timezone.utc)
    rows = sorted(load_due(db, uid, now), key=lambda d: str(d.get("opened_at")), reverse=True)[:MAX_IN_PROMPT]
    mark_asked(db, uid, [d["concept"] for d in rows], now)


def observe(db: Any, uid: str, facts: list[Any], safety_state: str, now: datetime | None = None) -> list[str]:
    """After a reply: open threads for what is worth following up, close the ones the person says are better. Returns the concepts touched.
    Does nothing when the turn was about a safety concern. Never raises."""
    now = now or datetime.now(timezone.utc)
    touched: list[str] = []
    if safety_state not in ("NO_REDFLAG", "GREEN"):
        # a concern that turned urgent has its own follow-up rules: close any casual thread about it so it is never asked about lightly
        try:
            for fact in facts:
                doc = doc_store.get(db, uid, KIND, _key(fact.concept))
                if doc and not doc.get("closed_at"):
                    doc_store.put(db, uid, KIND, _key(fact.concept), {**doc, "closed_at": now.isoformat(), "closed_because": "safety"})
                    touched.append(fact.concept)
        except Exception:  # noqa: BLE001
            pass
        return touched
    try:
        may_open = _may_open(db, uid)
        for fact in facts:
            key = _key(fact.concept)
            if closes(fact):
                doc = doc_store.get(db, uid, KIND, key)
                if doc and not doc.get("closed_at"):
                    doc_store.put(db, uid, KIND, key, {**doc, "closed_at": now.isoformat()})
                    touched.append(fact.concept)
            elif may_open and worth_opening(fact):
                doc = doc_store.get(db, uid, KIND, key)
                if doc and is_open(doc, now):
                    continue                       # already open: keep the original date so it still ages out
                doc_store.put(db, uid, KIND, key, {"concept": fact.concept, "opened_at": now.isoformat(), "severity": fact.severity})
                touched.append(fact.concept)
    except Exception:  # noqa: BLE001
        return touched
    return touched
