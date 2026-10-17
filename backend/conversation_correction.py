"""Conversational corrections and contradiction handling.

Two different things happen when a user pushes back or changes their story:

* **Correction** - Bubbles misread them ("I said no chest pain?"). The earlier user
  message is re-read with the semantics engine; if it really contained the
  denial, the wrong warning is retracted (message metadata + any pending events
  derived from it) and Bubbles acknowledges the mistake without repeating it.
* **Contradiction** - the user's own statements disagree ("my period ended
  yesterday" / "I'm still bleeding"). Either the newer statement simply
  supersedes the older one, or the conflict is surfaced as a question rather than
  silently storing two inconsistent truths.

Everything here is deterministic and generic: it works on concept ids, never on
a particular symptom.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from health_semantics import Fact, analyze, concept_for_text, display_name

_NEGATION_WORD = re.compile(r"\b(?:no|not|none|never|don't|do not|didn't|did not|haven't|isn't|am not|'m not|denied|deny|without)\b", re.I)

# Strong cues complain about Bubbles; weak cues ("I said ...") only count together with a negation or a concept.
_STRONG_CUE = re.compile(
    r"\bthat'?s (?:wrong|not (?:right|true|correct|what i said)|incorrect)\b|\bnot what i said\b|"
    r"\byou (?:misunderstood|misread|got (?:it|that) wrong|are wrong|'re wrong|mixed up|made a mistake)\b|"
    r"\bwhy (?:are|did) you (?:saying|say)\b|\bwhere did you (?:get|see)\b|\b(?:read|look at) (?:it|that|what i (?:wrote|said)) again\b|"
    r"\b(?:stop|quit) saying\b|"
    r"\bi never (?:said|mentioned|told)\b|\bi (?:did ?n[o']t|didn't|did not) (?:say|mention|tell)\b|\bi (?:was )?(?:just )?denied\b", re.I)
_WEAK_CUE = re.compile(r"\bi (?:just |already |clearly |literally )?(?:said|told you|mentioned|wrote|stated|typed)\b", re.I)
_OPEN_NO = re.compile(r"^\W*(?:no|nope|nah)[,!.\s]+(?:i\b|there\b|that)", re.I)
# With no symptom named, only a complaint about what BUBBLES said counts ("that's wrong", "I never said that").
# "I never said I'd stop exercising" talks about something else entirely.
_GENERIC_COMPLAINT = re.compile(
    r"\bi (?:never|didn't|did not|haven't|have not) (?:said|say|mention(?:ed)?|tell|told|claim(?:ed)?|write|wrote)\s+(?:that|it|this|so)\b|"
    r"\bwrong\b|\bmisunderstood\b|\bmisread\b|\bmistake\b|\bnot what i said\b|\b(?:read|look at) (?:it|that|what i (?:wrote|said)) again\b|"
    r"\bwhy (?:are|did) you (?:saying|say)\s+(?:that|it|this)\b|\bwhere did you (?:get|see)\s+(?:that|it|this)\b|"
    r"\b(?:that'?s|that is|it'?s|it is) (?:not true|not right|not correct|incorrect|false)\b|\b(?:stop|quit) saying\s+(?:that|it|this)\b", re.I)


@dataclass(frozen=True)
class Correction:
    is_correction: bool
    kind: str = "none"                       # misread | unfounded | update | none
    concepts: tuple[str, ...] = ()
    retract_message_id: str | None = None    # Bubbles message to mark as retracted
    reject_user_message_id: str | None = None  # user message whose derived events must be rejected
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"is_correction": self.is_correction, "kind": self.kind, "concepts": list(self.concepts),
                "retracted_message_id": self.retract_message_id}


NOT_A_CORRECTION = Correction(False)


def _meta(row: dict[str, Any]) -> dict[str, Any]:
    m = row.get("metadata")
    return m if isinstance(m, dict) else {}


def _claimed_concepts(bubbles_row: dict[str, Any]) -> set[str]:
    """Concepts Bubbles asserted about the user in a message (safety drivers, else present facts in its text)."""
    safety = _meta(bubbles_row).get("safety") or {}
    claimed = set(safety.get("concepts") or [])
    if not claimed:
        facts = analyze(bubbles_row.get("content") or "")
        claimed = {f.concept for f in facts if f.assertion in {"present", "possible"} and f.experiencer == "self"}
        if not claimed:
            # "I'm concerned about your thoughts of self-harm": Bubbles raised it as a worry, which is still raising it
            claimed = {f.concept for f in facts if f.assertion in {"hypothetical", "quoted"} and f.experiencer == "self"}
    return claimed


def detect_correction(text: str, facts_now: Iterable[Fact], history: list[dict[str, Any]]) -> Correction:
    """Is `text` the user correcting something Bubbles said/did? `history` is oldest-first rows with id/role/content/metadata."""
    facts_now = list(facts_now)
    strong = _STRONG_CUE.search(text)
    weak = _WEAK_CUE.search(text)
    opens_no = _OPEN_NO.search(text)
    if not (strong or weak or opens_no):
        return NOT_A_CORRECTION
    if weak and not strong and not opens_no and not (_NEGATION_WORD.search(text) or facts_now):
        return NOT_A_CORRECTION  # "I said hello"
    bubbles_idx = next((i for i in range(len(history) - 1, -1, -1) if history[i].get("role") == "bubbles"), None)
    if bubbles_idx is None:
        return NOT_A_CORRECTION
    bubbles_row = history[bubbles_idx]
    claimed = _claimed_concepts(bubbles_row)
    if not claimed or _meta(bubbles_row).get("safety", {}).get("retracted"):
        return NOT_A_CORRECTION

    self_now = [f for f in facts_now if f.experiencer == "self"]
    if any(f.assertion in {"present", "possible"} and f.temporal in {"current", "recent", "recurring", "unknown"} for f in self_now):
        # "I said I have chest pain" repeats a symptom; it is not a retraction of a false alarm
        return NOT_A_CORRECTION
    denied_now = {f.concept for f in self_now if f.assertion == "negated"}
    mentioned_now = {f.concept for f in self_now}
    if not mentioned_now and not _GENERIC_COMPLAINT.search(text):
        return NOT_A_CORRECTION  # a cue word, but no symptom and no complaint about Bubbles: "I never said I'd stop exercising"

    # what the user actually said earlier (before Bubbles' message)
    earlier_user = [r for r in history[:bubbles_idx] if r.get("role") == "user"]
    denied_earlier: dict[str, str] = {}
    denied_last: set[str] = set()          # denied in the message Bubbles was answering
    affirmed_earlier: set[str] = set()
    for n, row in enumerate(earlier_user):
        for f in analyze(row.get("content") or ""):
            if f.experiencer != "self":
                continue
            if f.assertion == "negated":
                denied_earlier[f.concept] = str(row.get("id"))
                if n == len(earlier_user) - 1:
                    denied_last.add(f.concept)
            elif f.assertion in {"present", "possible"} and f.temporal in {"current", "recent", "recurring", "unknown"}:
                affirmed_earlier.add(f.concept)

    if mentioned_now:
        target = (mentioned_now & claimed)
    else:
        target = claimed  # "that's wrong, I never said that"
    if not target:
        return NOT_A_CORRECTION
    # The warning was triggered by the whole denial ("no chest pain, no shortness of breath..."): when the user re-states
    # more of that denial, those concepts belong to the same misreading even if Bubbles' text named only one of them.
    siblings = (denied_now & denied_last) - target - affirmed_earlier if mentioned_now else set()

    misread = tuple(sorted(c for c in target if c in denied_earlier and c not in affirmed_earlier))
    if misread:
        misread = tuple(sorted(set(misread) | siblings))
    unfounded = tuple(sorted(c for c in target if c not in denied_earlier and c not in affirmed_earlier and (c in denied_now or not mentioned_now)))
    updated = tuple(sorted(c for c in target if c in affirmed_earlier and c in denied_now))

    reject_id = None
    if misread:
        reject_id = denied_earlier[misread[0]]
    elif earlier_user:
        reject_id = str(earlier_user[-1].get("id"))
    retract_id = str(bubbles_row.get("id")) if bubbles_row.get("id") else None

    if misread:
        return Correction(True, "misread", misread, retract_id, reject_id, "denial_found_in_earlier_message")
    if unfounded:
        return Correction(True, "unfounded", unfounded, retract_id, reject_id, "claim_not_found_in_user_messages")
    if updated:
        return Correction(True, "update", updated, None, None, "user_retracts_earlier_statement")
    return NOT_A_CORRECTION


def correction_response(c: Correction) -> str:
    names = _join([display_name(x) for x in c.concepts])
    if c.kind == "misread":
        return (
            f"You're right, thank you for pointing that out. You said you did not have {names}, and I misread that as if you did. "
            "That warning should not have appeared, so I've withdrawn it and discarded anything I'd noted from that misreading. "
            "Nothing you told me suggested an emergency.\n\n"
            "If anything does change, tell me and I'll take it seriously. Otherwise, let's carry on: how are you feeling today?"
        )
    if c.kind == "unfounded":
        return (
            f"You're right. You didn't tell me anything about {names}, and I shouldn't have suggested it. "
            "I've withdrawn that and discarded anything I'd noted from it.\n\nWhat would you like to talk about?"
        )
    return (
        f"Thanks for clarifying. I've updated my notes so you're no longer reporting {names} right now. "
        "If it comes back or changes, just tell me."
    )


def _join(items: list[str]) -> str:
    items = list(dict.fromkeys(items))
    if not items:
        return "that"
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " or " + items[-1]


# --------------------------------------------------------------------------
# Applying a correction (owner-scoped writes; the caller already authenticated the user)
# --------------------------------------------------------------------------

def apply_correction(db: Any, *, user_id: str, conversation_id: str, correction: Correction,
                     correction_message_id: str | None, history: list[dict[str, Any]]) -> dict[str, Any]:
    """Retract the wrong warning and reject the pending events it produced. Never raises."""
    now = datetime.now(timezone.utc).isoformat()
    out = {"retracted_message": False, "rejected_events": 0}
    if correction.retract_message_id:
        try:
            row = next((r for r in history if str(r.get("id")) == correction.retract_message_id), {})
            meta = dict(_meta(row))
            safety = dict(meta.get("safety") or {})
            safety.update({"retracted": True, "retracted_at": now, "retracted_by": correction_message_id,
                           "corrected_concepts": list(correction.concepts)})
            meta["safety"] = safety
            (db.table("chat_messages").update({"metadata": meta})
               .eq("id", correction.retract_message_id).eq("user_id", user_id).eq("conversation_id", conversation_id)
               .execute())
            out["retracted_message"] = True
        except Exception as error:  # noqa: BLE001 - a failed retraction must not break the reply
            _log_failure("retract_message", error, user_id)
    if correction.reject_user_message_id:
        try:
            rows = (db.table("extracted_health_events").select("id,event_type,extracted_data")
                    .eq("user_id", user_id).eq("message_id", correction.reject_user_message_id)
                    .eq("extraction_status", "pending").execute().data or [])
            ids = [r["id"] for r in rows if _event_concept(r) in set(correction.concepts)]
            if ids:
                (db.table("extracted_health_events")
                   .update({"extraction_status": "rejected"})
                   .in_("id", ids).eq("user_id", user_id).eq("extraction_status", "pending").execute())
            out["rejected_events"] = len(ids)
        except Exception as error:  # noqa: BLE001
            _log_failure("reject_events", error, user_id)
    return out


def _event_concept(row: dict[str, Any]) -> str | None:
    data = row.get("extracted_data") or {}
    for key in ("concept", "symptom", "name", "category"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            concept = concept_for_text(value)
            if concept:
                return concept
    return None


def _log_failure(operation: str, error: Exception, user_id: str) -> None:
    try:
        from logging_util import logger
        logger.error(component="CORRECTION", operation=operation, error=error, user_id=user_id,
                     fallback_action="continuing_without_retraction")
    except Exception:  # noqa: BLE001
        pass


# --------------------------------------------------------------------------
# Contradictions
# --------------------------------------------------------------------------

def _is_report(f: Fact) -> bool:
    return f.experiencer == "self" and f.assertion in {"present", "negated", "possible"}


_MOMENT_NOW = re.compile(r"\b(?:right now|at the moment|currently|at present|presently)\b", re.I)
# words that say "this is a CHANGE since before" (a pure update), as opposed to a second statement about the same moment
_UPDATE_WORDS = re.compile(
    r"\b(?:actually|just|suddenly|now|then|again|got|gotten|getting|became|become|since|later|after|but|however|worse|worsen\w*|never mind|oh|update\w*|"
    r"chang\w+|turned|gone|better|passed|stopped|improved|cleared|resolved|anymore|any more)\b", re.I)
_SLEEP_HOURS = re.compile(r"(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|h)\b", re.I)


def _moment(f: Fact) -> str | None:
    """Which moment a statement is about: 'now' ("right now"), 'day' ("today"/"this morning"), or unspecified."""
    if _MOMENT_NOW.search(f.source_text):
        return "now"
    return "day" if f.same_day else None


def _is_update(f: Fact) -> bool:
    return bool(_UPDATE_WORDS.search(_MOMENT_NOW.sub("", f.source_text)))


def _slept_hours(text: str) -> float | None:
    """Hours of sleep stated for a night in `text` ("I slept ... last night, a full 8 hours"); None when not stated."""
    for part in re.split(r"[.!?\n]+", text or ""):
        if re.search(r"\b(?:slept|sleep|asleep)\b", part, re.I) and re.search(r"\b(?:last night|night|this morning|today)\b", part, re.I):
            m = _SLEEP_HOURS.search(part)
            if m:
                return float(m.group(1))
    return None


def detect_contradictions(facts_now: Iterable[Fact], history_facts: Iterable[Fact] = (),
                          history_texts: Iterable[str] = (), text_now: str = "") -> list[dict[str, Any]]:
    """Conflicts inside this message and against earlier statements in the same conversation.

    `history_texts` (earlier user messages, oldest first) and `text_now` are optional; they let the check compare
    quantities that have no symptom concept (hours slept).
    """
    facts_now = list(facts_now)
    now = [f for f in facts_now if _is_report(f)]
    prior = [f for f in history_facts if _is_report(f)]
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    def add(concept: str, kind: str, earlier: Fact, later: Fact, question: str | None) -> None:
        key = (concept, kind)
        if key in seen:
            return
        seen.add(key)
        out.append({
            "concept": concept, "kind": kind,
            "earlier": {"assertion": earlier.assertion, "temporal": earlier.temporal},
            "later": {"assertion": later.assertion, "temporal": later.temporal},
            "question": question,
        })

    def live(f: Fact) -> bool:
        return f.assertion == "present" and f.temporal in {"current", "recent", "recurring", "unknown"}

    # same message: denied and affirmed in one breath
    by_concept: dict[str, list[Fact]] = {}
    for f in now:
        by_concept.setdefault(f.concept, []).append(f)
    for concept, group in by_concept.items():
        neg = next((f for f in group if f.assertion == "negated"), None)
        pos = next((f for f in group if live(f)), None)
        if neg and pos:
            add(concept, "needs_clarification", neg, pos, f"You mentioned both having and not having {display_name(concept)}. Which is right for today?")
        ended = next((f for f in group if f.concept == "period" and f.assertion == "present" and f.temporal == "resolved"), None)
        active = next((f for f in group if f.concept == "period" and live(f)), None)
        if ended and active:
            add("period", "needs_clarification", ended, active, "You said your period ended but also that you're still bleeding. Which is closer to what's happening today?")

    # against earlier turns
    latest_prior: dict[str, Fact] = {}
    for f in prior:
        latest_prior[f.concept] = f
    for concept, group in by_concept.items():
        earlier = latest_prior.get(concept)
        if earlier is None:
            continue
        later = group[-1]
        if concept == "period":
            if earlier.temporal == "resolved" and live(later):
                add("period", "needs_clarification", earlier, later,
                    "Earlier you said your period had ended, but now you're describing bleeding. Is this a new period, or is the earlier one continuing?")
            elif live(earlier) and later.assertion == "negated":
                add("period", "needs_clarification", earlier, later,
                    "Earlier you said you were on your period, but now you're saying it hasn't started. Which is closer to what's happening?")
            elif earlier.assertion == "negated" and live(later):
                add("period", "superseded", earlier, later, None)
            continue
        name = display_name(concept)
        same_moment = _moment(earlier) is not None and _moment(earlier) == _moment(later) and not _is_update(later)
        if earlier.assertion == "negated" and live(later):
            # "no vomiting today" + "I vomited three times today" cannot both describe the same day; "actually I feel nauseous now" is an update
            add(concept, "needs_clarification" if same_moment else "superseded", earlier, later,
                f"You said you had no {name}, and now you're describing {name} for the same time. Which is closer to what happened?" if same_moment else None)
        elif live(earlier) and later.assertion == "negated":
            add(concept, "needs_clarification" if same_moment else "superseded", earlier, later,
                f"You mentioned {name} earlier, but now you're saying you haven't had any for that time. Which is closer to what happened?" if same_moment else None)

    # quantities with no symptom concept: hours slept last night
    texts = list(history_texts)
    if texts:
        later_text = text_now or " ".join(f.source_text for f in now if f.concept == "insomnia" and f.assertion == "present")
        new_h = _slept_hours(later_text)
        old_h = next((h for h in (_slept_hours(t) for t in reversed(texts)) if h is not None), None)
        if new_h is not None and old_h is not None and abs(new_h - old_h) >= 2:
            concept = "insomnia" if any(f.concept == "insomnia" and f.assertion == "present" for f in now) else "sleep"
            if (concept, "needs_clarification") not in seen:
                seen.add((concept, "needs_clarification"))
                out.append({
                    "concept": concept, "kind": "needs_clarification",
                    "earlier": {"assertion": "present", "temporal": "recent"}, "later": {"assertion": "present", "temporal": "recent"},
                    "question": f"You mentioned sleeping about {old_h:g} hours, and now about {new_h:g}. Which is closer to how long you slept?",
                })
    return out


def contradiction_note(conflicts: list[dict[str, Any]]) -> str:
    """One calm sentence per conflict worth surfacing to the user (superseded updates are noted, not questioned)."""
    notes = []
    for c in conflicts:
        if c["kind"] == "needs_clarification" and c.get("question"):
            notes.append(c["question"])
        elif c["kind"] == "superseded":
            name = display_name(c["concept"])
            if c["later"]["assertion"] == "negated":
                notes.append(f"I've updated that you no longer have {name}.")
            else:
                notes.append(f"I've updated my notes: earlier you said no {name}, and now you're reporting it.")
    return " ".join(dict.fromkeys(notes))
