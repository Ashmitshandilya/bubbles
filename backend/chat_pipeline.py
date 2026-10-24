"""Chat turn orchestration: understand -> decide -> respond -> save.

``main.chat`` stays a thin HTTP wrapper around this module. Everything here is plain
Python over an injected ``db`` handle so it is unit-testable without FastAPI.

Flow for one user message:

1. ``analyze_turn``   - semantic facts, safety state, Safe Harbor (partner or family violence), correction?, contradictions, daily-log metrics
2. ``route_turn``     - emergency | safe_harbor | correction | clarification | daily_log | ai
3. build the reply    - deterministic copy for all but the last (no model call, no health data
                        leaves the server); the model only handles the "ai" route, with a
                        controlled context (recent turns + explicit user state + labelled evidence)
4. save               - rule-built events (explicit values only) and AI-proposed events after
                        reconciliation against what the user actually said; denials are stored
                        once as a symptom screen, never as symptoms.
"""
from __future__ import annotations

import hashlib
import re
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

from conversation_correction import (
    Correction, NOT_A_CORRECTION, contradiction_note, correction_response, detect_contradictions, detect_correction,
)
from event_dates import find_dates, stated_date, user_today
from daily_log_parser import DailyLog, _estimate_nutrition, parse_daily_log, summarize_log
from event_filters import clean_data
from health_event_pipeline import prepare_db_row
from memory_manager import extract_explicit_personal_facts
from people_memory import recall_target, remembered_reply
import brain
import locale_support
import orbit_knowledge
import paragraph_extras
import response_quality
import topic_tags
import safe_harbor
from safe_harbor import Harbor, HarborContext
from health_semantics import CRISIS, Fact, analyze, concept_for_text, display_name, net_state, split_sentences
from safety_engine import (
    POTENTIAL, SafetyAssessment, assess_safety, clarification_response, emergency_response, urgent_fallback_response,
)

HISTORY_TURNS = 10
HISTORY_FACT_MESSAGES = 6
# A resumed chat can be days old. What the person said more than this many hours ago is history, not how they are now: it is shown to
# the model as "earlier", past symptoms are never listed as current, and an old "no X" is no longer a standing denial.
HISTORY_NOW_HOURS = 48
ACTIVE_TEMPORALS = {"current", "recent", "recurring", "unknown"}
SYMPTOMISH_TYPES = {"symptom", "menstrual_symptom", "medical_condition", "allergy", "medication", "supplement", "family_medical_history"}
MENSTRUAL_CONCEPTS = {"cramps", "spotting"}
NON_SYMPTOM_CONCEPTS = {"period", "medication_use"}

MAX_STORED_EVENTS = 100   # per reply; anything beyond is counted in metadata.health_events_more so the card can say "N more"
KINDS = ("reply", "clarification", "emergency", "correction_ack", "daily_log_summary", "safe_harbor")


def _name(concept: str) -> str:
    return concept[7:] if concept.startswith("custom:") else display_name(concept)


def _log_failure(operation: str, error: Exception, user_id: str | None = None) -> None:
    try:
        from logging_util import logger
        logger.error(component="CHAT", operation=operation, error=error, user_id=user_id, fallback_action="continuing")
    except Exception:  # noqa: BLE001
        pass


# --------------------------------------------------------------------------
# Rate limit (per user, in-memory): protects free-provider quotas and the regex engine
# --------------------------------------------------------------------------

class RateLimiter:
    """Sliding-window limiter, safe to call from several threads. Stale keys are swept on a regular count of calls (not only when the
    table is already huge) and the table has a hard ceiling, so a flood of made-up keys cannot grow memory without bound."""

    SWEEP_EVERY = 500
    MAX_KEYS = 100_000

    def __init__(self, limit: int = 30, window: float = 60.0, clock: Callable[[], float] = time.monotonic):
        self.limit, self.window, self.clock = limit, window, clock
        self._hits: dict[str, deque[float]] = {}
        self._calls = 0
        self._lock = threading.Lock()

    def _trim(self, hits: deque[float], now: float) -> None:
        while hits and now - hits[0] > self.window:
            hits.popleft()

    def _sweep(self, now: float) -> None:
        for k in [k for k, v in self._hits.items() if not v or now - v[-1] > self.window]:
            self._hits.pop(k, None)

    def _tick(self, now: float) -> None:
        self._calls += 1
        if self._calls % self.SWEEP_EVERY == 0 or len(self._hits) > self.MAX_KEYS:
            self._sweep(now)

    def allow(self, key: str) -> bool:
        with self._lock:
            now = self.clock()
            self._tick(now)
            hits = self._hits.get(key)
            if hits is None:
                if len(self._hits) >= self.MAX_KEYS:  # still full after sweeping: refuse new keys rather than grow
                    return False
                hits = self._hits[key] = deque()
            self._trim(hits, now)
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            return True

    def over(self, key: str) -> bool:
        """True when this key is already at its limit. Does not count a hit."""
        with self._lock:
            hits = self._hits.get(key)
            if not hits:
                return False
            self._trim(hits, self.clock())
            return len(hits) >= self.limit

    def record(self, key: str) -> None:
        """Counts a hit without checking the limit (used for events such as a failed sign-in)."""
        with self._lock:
            now = self.clock()
            self._tick(now)
            if key not in self._hits and len(self._hits) >= self.MAX_KEYS:
                return
            hits = self._hits.setdefault(key, deque())
            self._trim(hits, now)
            hits.append(now)


# --------------------------------------------------------------------------
# History (L0): owner-scoped recent turns of this conversation
# --------------------------------------------------------------------------

def load_history(db: Any, user_id: str, conversation_id: str, limit: int = HISTORY_TURNS) -> list[dict[str, Any]]:
    """Recent messages of one conversation, oldest first. Never raises."""
    try:
        rows = (db.table("chat_messages").select("id,role,content,metadata,created_at")
                .eq("user_id", user_id).eq("conversation_id", conversation_id)
                .order("created_at", desc=True).limit(limit).execute().data or [])
    except Exception as error:  # noqa: BLE001
        _log_failure("load_history", error, user_id)
        return []
    return [r for r in reversed(rows) if isinstance(r, dict)]


LIVE_STATUSES = ("pending", "confirmed", "rejected", "retracted", "superseded")
_OVERLAY_CHUNK = 100


def settled_statuses(db: Any, user_id: str, event_ids: list[str]) -> dict[str, str]:
    """The real status of saved events, one owner-scoped query per 100 ids: ``{event_id: pending|confirmed|rejected|...}``.

    The reply's stored snapshot says "pending" forever (the decision is made later, on the event row), so a reader that shows
    saved cards must ask the rows. Another person's id is simply absent from the answer. Never raises: on a read problem the
    snapshot status stays (the caller keeps what it had)."""
    ids = [str(i) for i in dict.fromkeys(event_ids) if i]
    out: dict[str, str] = {}
    for start in range(0, len(ids), _OVERLAY_CHUNK):
        try:
            rows = (db.table("extracted_health_events").select("id,extraction_status,user_confirmed")
                    .eq("user_id", user_id).in_("id", ids[start:start + _OVERLAY_CHUNK]).execute().data or [])
        except Exception as error:  # noqa: BLE001
            _log_failure("settled_statuses", error, user_id)
            continue
        for row in rows:
            status = str(row.get("extraction_status") or "").strip().lower()
            if status not in LIVE_STATUSES:
                status = "pending"
            if status == "pending" and row.get("user_confirmed") is True:
                status = "confirmed"
            out[str(row.get("id"))] = status
    return out


def overlay_event_status(db: Any, user_id: str, events_by_message: list[list[dict[str, Any]]]) -> None:
    """Writes the settled status into every event dict (in place) with ONE round of queries for all the messages together."""
    ids = [str(e.get("id")) for events in events_by_message for e in events if isinstance(e, dict) and e.get("id")]
    if not ids:
        return
    settled = settled_statuses(db, user_id, ids)
    for events in events_by_message:
        for event in events:
            if isinstance(event, dict) and str(event.get("id")) in settled:
                event["status"] = settled[str(event["id"])]


def find_stored_reply(db: Any, user_id: str, conversation_id: str, user_message_id: str) -> dict[str, Any] | None:
    """The Bubbles reply already saved for this user message (an idempotent replay), if any."""
    try:
        rows = (db.table("chat_messages").select("id,content,metadata")
                .eq("user_id", user_id).eq("conversation_id", conversation_id).eq("role", "bubbles")
                .eq("metadata->>user_message_id", user_message_id).limit(1).execute().data or [])
    except Exception as error:  # noqa: BLE001
        _log_failure("find_stored_reply", error, user_id)
        return None
    if not rows:
        return None
    row = rows[0]
    meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    events = [dict(e) for e in meta.get("health_events") or [] if isinstance(e, dict)] if isinstance(meta.get("health_events"), list) else []
    overlay_event_status(db, user_id, [events])   # a replay must not bring back cards the person already settled
    replay = {
        "response": row.get("content") or "",
        "sentiment": "neutral",
        "kind": meta.get("kind") if meta.get("kind") in KINDS else "reply",
        "safety": {**{"level": "GREEN", "state": "NO_REDFLAG", "reasons": [], "retracted": False}, **(meta.get("safety") or {})},
        "health_events": events,
        "health_event_ids": [e.get("id") for e in events],
        "message_id": str(row.get("id")),
        "user_message_id": user_message_id,
        "conversation_id": conversation_id,
        "consent_required": meta.get("consent_required") is True,
        "evidence": [],
        "replayed": True,
        "suggestions": [s for s in meta.get("suggestions") or [] if isinstance(s, str)][:3] if isinstance(meta.get("suggestions"), list) else [],
    }
    if isinstance(meta.get("harbor"), dict):
        replay["harbor"] = {k: v for k, v in meta["harbor"].items() if k in ("tier", "mode", "step", "resources", "actions")}   # same as first time; nothing recomputed, no state written twice
    return replay


def message_age_hours(row: dict[str, Any], now: datetime | None = None) -> float | None:
    """Hours since a stored message was written (None when it has no readable time)."""
    raw = str(row.get("created_at") or "")
    try:
        when = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return ((now or datetime.now(timezone.utc)) - when).total_seconds() / 3600


def conversation_block(history: list[dict[str, Any]], max_chars: int = 2400, *, now: datetime | None = None) -> str:
    lines: list[str] = []
    hidden = safe_harbor.hidden_message_ids(history)   # Safe Harbor turns are private: they never reach the outside model, not even as "earlier"
    for row in [r for r in history if str(r.get("id") or "") not in hidden][-8:]:
        content = " ".join(str(row.get("content") or "").split())
        meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        if row.get("role") == "bubbles" and (meta.get("safety") or {}).get("retracted"):
            content = "[withdrawn: Bubbles misread the user here and retracted this warning]"
        label = "User" if row.get("role") == "user" else "Bubbles"
        age = message_age_hours(row, now)
        if age is not None and age > HISTORY_NOW_HOURS:
            label += f" (earlier, {int(age // 24)} days ago, not necessarily true now)"
        lines.append(f"{label}: {content[:360]}")
    while lines and sum(len(l) + 1 for l in lines) > max_chars:
        lines.pop(0)
    return "\n".join(lines)


def state_block(current: list[Fact], history_facts: list[Fact]) -> str:
    """Explicit user statements only. Anything not listed is UNKNOWN."""
    net = net_state(list(history_facts) + list(current))
    denied = [_name(c) for c, v in net.items() if v["assertion"] == "negated"]
    now = [f"{_name(c)}" + (f" ({v['severity']}/10)" if v.get("severity") else "") for c, v in net.items()
           if v["assertion"] == "present" and v["temporal"] in ACTIVE_TEMPORALS]
    past = [_name(c) for c, v in net.items() if v["assertion"] == "present" and v["temporal"] in {"past", "resolved"}]
    maybe = [_name(c) for c, v in net.items() if v["assertion"] == "possible"]
    if not (denied or now or past or maybe):
        return ""
    out = ["USER-REPORTED STATE (explicit statements from this conversation; anything not listed is UNKNOWN, never assume it):"]
    if denied:
        out.append("- Denied by the user (never say they have these): " + ", ".join(dict.fromkeys(denied)))
    if now:
        out.append("- Reported now or recently: " + ", ".join(dict.fromkeys(now)))
    if past:
        out.append("- Past or resolved (not current): " + ", ".join(dict.fromkeys(past)))
    if maybe:
        out.append("- Unsure / possible: " + ", ".join(dict.fromkeys(maybe)))
    return "\n".join(out)


_QUERY_STOPWORDS = frozenset(
    "what is are was how can could should would do does i me my mujhe mera meri mere a an the to of in on for it "
    "this that kya hai hain ho hoga karna chahiye please tell about".split())


def evidence_query(facts: list[Fact], message: str) -> str:
    """What to look up in the evidence base: topics the user raised, never denied or other people's symptoms."""
    topics = [_name(f.concept) for f in facts
              if f.experiencer == "self" and f.assertion in {"present", "possible", "question", "hypothetical"} and f.concept not in NON_SYMPTOM_CONCEPTS]
    if topics:
        return " ".join(dict.fromkeys(topics))[:200]
    text = " ".join(message.split())
    # Small talk is never looked up: it would pull whatever pages sit nearest in meaning ("hey bubbles" -> colposcopy).
    # Other short messages still are ("tell me about iron"); shown_evidence() keeps unrelated pages off the screen.
    if small_talk_kind(text) or not (text.endswith("?") or len(text) <= 160):
        return ""
    # Filler words dilute both the keyword and the embedding query; keep the content words.
    kept = [w for w in text.split() if w.lower().strip("?.,!") not in _QUERY_STOPWORDS]
    return " ".join(kept)[:300]


# --------------------------------------------------------------------------
# Understanding a turn
# --------------------------------------------------------------------------

@dataclass
class Turn:
    text: str
    facts: list[Fact]
    safety: SafetyAssessment
    correction: Correction
    conflicts: list[dict[str, Any]]
    log: DailyLog
    history_facts: list[Fact]
    route: str = "ai"
    timings_ms: dict[str, float] = field(default_factory=dict)
    pause_strict_plan: bool = False
    last_reply: dict[str, Any] | None = None   # the newest Bubbles message in this conversation (content + metadata)
    mode: str = "talk"    # "talk" or "orbit" (Heart-to-heart): set by the client, kept with the conversation
    topics: tuple[str, ...] = ()   # relationship / mind / body / fitness / cycle / care (topic_tags.py): a hint for chips and context, never for safety
    country: Any = None   # from the setup (None = not said = India); picks the emergency wording of the fixed replies
    brain: dict[str, Any] | None = None   # set with route own_data, knowledge or companion (brain.py): which local answer, so it can be answered, stored and learned from
    harbor: Harbor = field(default_factory=Harbor)   # partner or family violence: tier, whether this is a follow-up, what to store (safe_harbor.py)


def history_user_facts(history: list[dict[str, Any]], now: datetime | None = None) -> list[Fact]:
    out: list[Fact] = []
    users = [r for r in history if r.get("role") == "user" and r.get("content")][-HISTORY_FACT_MESSAGES:]
    for row in users:
        try:
            facts = analyze(str(row["content"])[:1500])
        except Exception as error:  # noqa: BLE001
            _log_failure("history_facts", error)
            continue
        age = message_age_hours(row, now)
        if age is not None and age > HISTORY_NOW_HOURS:
            # old news: what they had becomes "past", and an old denial or guess says nothing about today
            facts = [replace(f, temporal="past") for f in facts if f.assertion == "present"]
        out.extend(facts)
    return out


def analyze_turn(text: str, history: list[dict[str, Any]], *, now: datetime | None = None, harbor_ctx: HarborContext | None = None, mode: str = "talk") -> Turn:
    t0 = time.perf_counter()
    try:
        facts: list[Fact] | None = analyze(text)
    except Exception as error:  # noqa: BLE001
        _log_failure("analyze", error)
        facts = None
    safety = assess_safety(text, facts)  # never raises; falls back to a keyword fail-safe when facts is None
    facts = facts or []
    t1 = time.perf_counter()
    history_facts = history_user_facts(history, now)
    try:
        correction = detect_correction(text, facts, history)
    except Exception as error:  # noqa: BLE001
        _log_failure("detect_correction", error)
        correction = NOT_A_CORRECTION
    try:
        conflicts = [] if correction.is_correction else detect_contradictions(facts, history_facts)
    except Exception as error:  # noqa: BLE001
        _log_failure("detect_contradictions", error)
        conflicts = []
    try:
        log = parse_daily_log(text, facts, now=now)
    except Exception as error:  # noqa: BLE001
        _log_failure("parse_daily_log", error)
        log = DailyLog(log_date=(now or datetime.now(timezone.utc)).date().isoformat())
    turn = Turn(text, facts, safety, correction, conflicts, log, history_facts)
    turn.last_reply = next((r for r in reversed(history) if r.get("role") == "bubbles"), None)
    turn.topics = topic_tags.tags(text)
    turn.mode = "orbit" if mode == "orbit" else "talk"
    try:
        turn.harbor = safe_harbor.assess(text, history, harbor_ctx, now=now)
    except Exception as error:  # noqa: BLE001 - if the rules themselves fail, a plain keyword look decides (a fixed reply beats sending the message to a model)
        _log_failure("safe_harbor", error)
        turn.harbor = safe_harbor.fail_safe(text)
    if turn.harbor.followup and turn.harbor.followup != "urgent" and (facts or log.is_daily_log):
        turn.harbor = turn.harbor.without_followup()   # a plain health message inside a Safe Harbor conversation is answered as usual
    turn.route = route_turn(turn)
    turn.timings_ms = {"semantics_ms": round((t1 - t0) * 1000, 1), "turn_ms": round((time.perf_counter() - t0) * 1000, 1)}
    return turn


def _only_tells_a_fact(text: str) -> bool:
    """A short statement that only tells Bubbles something about the person or their people (no question, nothing else to answer)."""
    return "?" not in text and len(text.split()) <= 18 and bool(extract_explicit_personal_facts(text))


_TROUBLE = re.compile(r"\b(?:upset|angry|mad at|sad|hurt|hurting|fight|fighting|fought|argu\w*|cheat\w*|lie[sd]?|lying|trust|jealous|miss(?:ing)?|break\s?up|broke up|ignor\w*|silent|distant|distance|"
                      r"naraz|gussa|gusse|jhagd\w*|ladai|ladte|pareshan|dukhi|udaas|rooth\w*|baat nahi|bharosa|shak|chhod\w*)\b", re.I)


def _relationship_concern(turn: Turn) -> bool:
    """A message about a relationship that is a worry (a feeling, a problem word, or a known pattern), not a passing mention like a birthday gift."""
    if "relationship" not in turn.topics:
        return False
    return "mind" in turn.topics or bool(_TROUBLE.search(turn.text)) or bool(orbit_knowledge.cards_for(turn.text, limit=1))


def route_turn(turn: Turn) -> str:
    state = turn.safety.state
    if state == "EMERGENCY":
        return "emergency"
    if turn.harbor.deterministic:
        return "safe_harbor"   # partner or family violence (tier 2 and up) and the follow-ups after it: fixed copy, never an outside model
    if response_quality.manipulation_request(turn.text) and state != "URGENT":
        return "orbit_redirect"   # making someone jealous, checking up on them in secret, testing them: a fixed warm answer, never a model
    if turn.correction.is_correction:
        return "correction"
    if state == POTENTIAL:
        return "clarification"
    fitness = _fitness_route(turn.text)
    if fitness == "fitness_support" and state in ("URGENT", POTENTIAL):
        turn.pause_strict_plan = True    # the safety reply wins, but the strict plan is still paused (main.py)
    fitness = fitness if state != "URGENT" else None
    if fitness == "fitness_support":   # restriction language / below-floor requests come before logging anything
        return fitness
    if turn.log.is_daily_log and state != "URGENT":
        return "daily_log"
    # Telling Bubbles who someone is, or asking it to say who they are, is answered here from the person's saved facts: instant, free, and
    # never waiting on a consent question or an outside model. Only a message with no health fact in it, and never right after a safety reply.
    if not fitness and state != "URGENT" and not turn.facts and not standing_safety_reply(turn.last_reply):
        if recall_target(turn.text):
            return "recall"
        if _only_tells_a_fact(turn.text):
            return "remembered"
    kind = None if fitness or state == "URGENT" or turn.facts else small_talk_kind(turn.text)
    if kind:
        # "bye" or "ok" right after a safety reply must not get cheerful small talk: the concern is not settled by a goodbye.
        if standing_safety_reply(turn.last_reply):
            return "safety_followup"
        # "ok" after Bubbles asked something means yes: the real reply answers it.
        if kind == "ack" and "?" in str((turn.last_reply or {}).get("content") or ""):
            return "ai"
        return "small_talk"   # "hey bubbles", "thanks": answered here, no outside model and no consent question
    relationship = _relationship_concern(turn)
    if not fitness and state == "NO_REDFLAG" and (turn.mode == "orbit" or relationship):
        return "orbit"   # relationship support: the Heart-to-heart voice and the pattern cards, still behind the same consent as every model reply
    if not fitness and state == "NO_REDFLAG" and not standing_safety_reply(turn.last_reply):
        # Bubbles' own brain (brain.py): the person's own data, a reviewed self-care card, or the friend voice. Never for anything safety flagged.
        decided = brain.decide(turn.text, [f.concept for f in turn.facts], mode=turn.mode, harbor_tier=turn.harbor.tier, about_other=turn.harbor.about_other,
                               relationship=relationship)
        if decided:
            turn.brain = decided
            return decided["route"]
    return fitness or "ai"


_SAFETY_KINDS = frozenset({"emergency", "clarification"})
_SAFETY_STATES = frozenset({"EMERGENCY", "URGENT", POTENTIAL})


def standing_safety_reply(reply: dict[str, Any] | None) -> dict[str, Any] | None:
    """The reply's metadata when it was a safety reply that still stands (not retracted by a correction), else None."""
    meta = (reply or {}).get("metadata") or {}
    safety = meta.get("safety") or {}
    if not isinstance(safety, dict) or safety.get("retracted"):
        return None
    return meta if (meta.get("kind") in _SAFETY_KINDS or safety.get("state") in _SAFETY_STATES) else None


def safety_followup_reply(reply: dict[str, Any] | None, *, name: str | None, country: Any = None) -> str:
    """Fixed text for small talk right after a safety reply (no model): the earlier concern is restated, never waved off."""
    meta = standing_safety_reply(reply) or {}
    safety = meta.get("safety") or {}
    comma = f", {name}" if name else ""
    if any(c in CRISIS for c in safety.get("concepts") or []):
        return (f"I'm still here{comma}. If you might act on these thoughts or you are in immediate danger, please call your local emergency "
                f"number now. {locale_support.crisis_lines(country)} Would you tell me how you're feeling right now?")
    if meta.get("kind") == "emergency" or safety.get("state") == "EMERGENCY":
        return (f"I'm still here{comma}. If what you told me is still happening, or it feels severe, please contact your local emergency "
                "service now, and ask someone nearby to stay with you. How are you feeling right now?")
    if meta.get("kind") == "clarification" or safety.get("state") == POTENTIAL:
        return ("Before we move on, I want to check what you told me earlier: is it still happening right now, and how strong is it from "
                "0 to 10? If it's happening now and it's severe, call your local emergency number.")
    return (f"Before we go on{comma}: what you mentioned earlier deserves prompt attention, so please speak to a clinician or an "
            "urgent-care service today. If it gets worse, go to emergency care.")


def shown_evidence(rows: list[dict[str, Any]], limit: int = 3) -> list[dict[str, Any]]:
    """The sources shown under a reply: real matches only, one per title, at most `limit`.

    A row the keyword search did not find (only "nearest in meaning") is dropped unless it was tagged for the question's link:
    for short or vague questions the nearest pages are often unrelated, and a source chip claims relevance."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if row.get("semantic_rank") is not None and row.get("lexical_rank") is None and not row.get("linked"):
            continue
        key = " ".join(str(row.get("title") or row.get("source_url") or row.get("chunk_id") or "").lower().split())
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(row)
        if len(out) >= limit:
            break
    return out


_GREET = frozenset("hi hii hiii hey heyy heyyy hello helo hiya namaste namaskar yo sup".split())
_DISTRESS = frozenset("😭😢💔🤕😞😔🥺😣😖😩😫🤒🤢🤮😰😨😥")   # a crying face is not small talk
_THANKS = frozenset("thanks thank thx ty thankyou shukriya dhanyavad".split())
_BYE = frozenset("bye byee goodbye later tc gn".split())
_ACK = frozenset("ok okay okk cool alright great nice".split())   # not "sure"/"yes": after an offer they mean yes, and that needs the real reply
_FILLER = frozenset("there bubbles bubble buddy dear ji again you so much a lot very good morning afternoon evening night see ya got it".split())
_HOW_ARE_YOU = ("how are you doing", "how are you", "how r u", "how are u", "how r you", "hru", "how s it going", "hows it going",
                "kaise ho", "kaisi ho", "kya haal hai", "kya haal")


def _words(text: str) -> list[str]:
    return "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in (text or "").lower()).split()


def small_talk_kind(text: str) -> str | None:
    """'greeting' | 'how_are_you' | 'thanks' | 'bye' | 'ack' when the whole message is small talk (a few words, nothing about health), else None."""
    if any(ch in _DISTRESS for ch in text or ""):
        return None
    words = _words(text)
    joined = " ".join(words)
    for phrase in _HOW_ARE_YOU:   # "hey bubbles, how are you?" is small talk too, not a question for an outside model
        if f" {phrase} " in f" {joined} ":
            rest = f" {joined} ".replace(f" {phrase} ", " ").split()
            if all(w in _GREET | _FILLER for w in rest) and len(words) <= 8:
                return "how_are_you"
    if not words or len(words) > 6 or any(w not in _GREET | _THANKS | _BYE | _ACK | _FILLER for w in words):
        return None
    if set(words) & _THANKS:
        return "thanks"
    if set(words) & _BYE or "night" in words:
        return "bye"
    if set(words) & _GREET or {"morning", "afternoon", "evening"} & set(words):
        return "greeting"
    return "ack" if set(words) & _ACK or words == ["got", "it"] else None


def small_talk_reply(text: str, *, name: str | None) -> str:
    kind = small_talk_kind(text) or "greeting"
    words = set(_words(text))
    hi = f" {name}" if name else ""
    comma = f", {name}" if name else ""
    pick = int(hashlib.sha256(" ".join(_words(text)).encode("utf-8")).hexdigest(), 16)  # stable, so a retried message gets the same words
    if kind == "how_are_you":
        if words & {"kaise", "kaisi", "haal"}:
            return f"Main badhiya hoon{comma}! Aap batao, aaj kaisa feel ho raha hai?"
        return f"I'm good, thanks for asking{comma}! How are you feeling today?"
    if kind == "thanks":
        return ("Anytime" + comma + ". I'm here whenever you need me.", "You're welcome" + comma + "! Tell me whenever something comes up.")[pick % 2]
    if kind == "bye":
        if "night" in words or "gn" in words:
            return "Good night" + comma + ". Sleep well, and tell me tomorrow how you slept."
        return "Take care" + comma + ". I'll be here when you need me."
    if kind == "ack":
        return f"Okay{comma}! I'm right here if you need anything."
    if "morning" in words:
        return f"Good morning{hi}! How did you sleep?"
    for part in ("evening", "afternoon"):
        if part in words:
            return f"Good {part}{hi}! How's your day been?"
    if words & {"namaste", "namaskar"}:
        return f"Namaste{hi}! How are you feeling today?"
    return (
        f"Hi{hi}! Tell me how you're feeling, or log something like \"slept 7 hours\" and I'll note it.",
        f"Hey{hi}! Good to see you. How are you feeling today?",
        f"Hi{hi}! What's on your mind? I can note how you slept or ate, or we can just talk.",
    )[pick % 3]


def _fitness_route(text: str) -> str | None:
    try:
        from fitness_chat import route_for
        return route_for(text)
    except Exception as error:  # noqa: BLE001
        _log_failure("fitness_route", error)
        return None


# --------------------------------------------------------------------------
# Deterministic replies
# --------------------------------------------------------------------------

def first_name(user: Any) -> str | None:
    meta = getattr(user, "user_metadata", None) or {}
    name = str(meta.get("full_name") or meta.get("name") or "").strip()
    return name.split()[0][:40] if name else None


def reply_kind(route: str) -> str:
    return {"emergency": "emergency", "orbit_redirect": "orbit_redirect", "safe_harbor": "safe_harbor", "correction": "correction_ack", "clarification": "clarification",
            "daily_log": "daily_log_summary", "fitness_support": "fitness_support", "fitness_answer": "fitness_answer"}.get(route, "reply")


def deterministic_reply(turn: Turn, *, name: str | None, saved_events: int, status_note: str = "") -> str:
    route, safety = turn.route, turn.safety
    if route == "emergency":
        text = emergency_response(safety, turn.country)
        if turn.harbor.tier >= 2:
            text += "\n\n" + safe_harbor.resource_line(turn.harbor)   # "he hit me and I want to die": the crisis reply first, then the numbers for being unsafe at home
        return text
    if route == "safe_harbor":
        return safe_harbor.reply(turn.harbor, seed=turn.text, medical=safety.state == "URGENT")
    if route == "orbit_redirect":
        return orbit_redirect_reply(turn.text)
    if route == "small_talk":
        return small_talk_reply(turn.text, name=name)
    if route == "remembered":
        return remembered_reply(extract_explicit_personal_facts(turn.text), seed=turn.text)
    if route == "recall":
        return ""   # filled in by main._recall_text (needs the saved facts)
    if route == "safety_followup":
        return safety_followup_reply(turn.last_reply, name=name, country=turn.country)
    if route in ("fitness_support", "fitness_answer"):
        return ""   # filled in by main._fitness_text (needs the database)
    if route == "correction":
        text = correction_response(turn.correction)
        if safety.state == POTENTIAL:
            text += "\n\n" + clarification_response(safety, turn.country)
        return text
    if route == "clarification":
        text = clarification_response(safety, turn.country)
        if saved_events:
            text += "\n\nI've also noted the other things you told me."
        return text
    # daily log
    parts = [summarize_log(turn.log, turn.facts, name=name)]
    note = contradiction_note(turn.conflicts)
    if note:
        parts.append(note)
    pick = int(hashlib.sha256(parts[0].encode("utf-8")).hexdigest(), 16)   # stable per message, so a retried message gets the same words
    parts.append(_ONE_DAY[pick % len(_ONE_DAY)])
    if status_note:   # what was saved on its own and what needs the person's OK (event_autosave.status_note)
        parts.append(status_note)
    elif saved_events:
        parts.append(_SAVED_NOTES[(pick // 7) % len(_SAVED_NOTES)])
    return "\n\n".join(parts)


# Same meaning every time (one day is not a pattern; saved items are suggestions until confirmed), in a few warmer wordings.
_ONE_DAY = (
    "That's one day, so I won't read a pattern into it yet. I'll keep it alongside your next few days.",
    "One day on its own doesn't tell us much. Keep logging and I'll start comparing.",
    "It's early for patterns, since this is a single day. I'll watch how the next days line up.",
    "No pattern to point at yet, because this is just one day. A few more and I can compare.",
)
_SAVED_NOTES = (
    "I've saved these as notes you can review. Confirm anything you'd like kept in your records.",
    "These are saved as notes for you to look over. Nothing becomes a lasting record until you confirm it.",
)


def ai_failed_reply(turn: Turn, *, name: str | None, saved_events: int) -> str:
    """When the AI provider is unavailable: still acknowledge what was understood and saved."""
    if turn.safety.state == "URGENT":
        return urgent_fallback_response(turn.safety)
    if turn.log.metrics:
        text = summarize_log(turn.log, turn.facts, name=name)
        extra = " I can't reach my AI helper right now, so I'm not adding any interpretation."
        return text + extra + (" I've saved what you told me." if saved_events else "")
    return "I couldn't reach my AI helper just now, so I can't answer this properly. Please try again in a moment."


# --------------------------------------------------------------------------
# Events: provenance, rule-built events, reconciliation, persistence
# --------------------------------------------------------------------------

def _key(*parts: Any) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:16]


def _prov(extractor: str, message_id: str | None, key: str, now_iso: str, *, assertion: str = "present", temporal: str = "current") -> dict[str, Any]:
    return {"source": "user_message", "message_id": message_id, "extractor": extractor, "assertion": assertion,
            "temporal": temporal, "subject": "self", "recorded_at": now_iso, "key": key}


def _int_severity(value: Any) -> int | None:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return n if 1 <= n <= 10 else None


# Words that end one part of a sentence and start another: "on the 20th I had fever and today I have a cough".
_CLAUSE_BREAK = re.compile(r",|;|\b(?:and|but|then|while|whereas|aur|lekin|par|phir)\b", re.I)
_PASTISH_TEMPORALS = {"past", "resolved", "recent"}


def fact_day(turn: Turn, f: Fact, today: date) -> date | None:
    """The day the person said this symptom happened, or None when they named no day for it.

    The part of the sentence that holds the symptom decides first, then the whole sentence; a symptom told in the
    past tense with no day of its own takes the one day the message names ("On 20 September. I had a headache")."""
    sentences = split_sentences(turn.text)
    sentence = sentences[f.sentence_index] if 0 <= f.sentence_index < len(sentences) else ""
    dates = find_dates(sentence, today) if sentence else []
    if dates:
        cuts = [0, *(m.start() for m in _CLAUSE_BREAK.finditer(sentence)), len(sentence)]
        start = max(c for c in cuts if c <= f.span[0])
        end = min((c for c in cuts if c >= f.span[1]), default=len(sentence))
        own = {d for pos, d in dates if start <= pos < end}
        if len(own) == 1:
            return own.pop()
        named = {d for _pos, d in dates}
        if len(named) == 1:
            return named.pop()
        before = [d for pos, d in dates if pos < f.span[0]]
        return before[-1] if before else dates[0][1]
    if f.temporal in _PASTISH_TEMPORALS:
        return stated_date(turn.text, today)
    return None


_EXERCISE_NAME = {"walked": "walking", "ran": "running", "jogged": "jogging", "swam": "swimming", "cycled": "cycling", "danced": "dancing", "hiked": "hiking",
                  "stretched": "stretching", "worked out": "workout", "exercised": "exercise", "exercises": "exercise"}


def build_rule_events(turn: Turn, message_id: str | None, *, now: datetime | None = None) -> list[dict[str, Any]]:
    """Events from explicitly stated values only (nothing inferred). Denials become ONE symptom-screen event."""
    now = now or datetime.now(timezone.utc)
    now_iso = now.isoformat()
    mt, day = turn.log.metrics, turn.log.log_date
    today = user_today(now)
    out: list[dict[str, Any]] = []

    def add(event_type: str, data: dict[str, Any], confidence: float = 0.9, *, metric: str = "", temporal: str = "current") -> None:
        when = data.get("date", day)
        key = _key(message_id, event_type, metric or data.get("name") or data.get("symptom") or "", when)
        data = {**data, "date": when}
        data["_prov"] = _prov("rules", message_id, key, now_iso, temporal=temporal)
        out.append({"event_type": event_type, "extracted_data": data, "confidence": confidence})

    # ---- symptoms the user reports as current/recent/recurring
    # A symptom told with a day of its own ("on the 20th I had a headache") is logged on that day, even in the past tense.
    seen: dict[tuple[str, str], Fact] = {}
    for f in turn.facts:
        if f.experiencer != "self" or f.assertion != "present" or f.concept in NON_SYMPTOM_CONCEPTS or f.concept.startswith("custom:"):
            continue
        named = fact_day(turn, f, today)
        if not (f.temporal in ACTIVE_TEMPORALS or (f.temporal == "resolved" and f.same_day)
                or (f.temporal in _PASTISH_TEMPORALS and named is not None)):
            continue
        when = named.isoformat() if named else day
        prev = seen.get((f.concept, when))
        if prev is None or (f.severity or 0) > (prev.severity or 0):
            seen[(f.concept, when)] = f
    injured = paragraph_extras.injuries(turn.text)
    if injured and any(i["swollen"] for i in injured):
        seen = {k: v for k, v in seen.items() if k[0] != "swelling"}   # the swelling is part of the injury, asked about once
    for info in injured:   # always asked about, never saved unseen (event_policy)
        add("symptom", paragraph_extras.injury_event(info), 0.85, metric=f"injury-{info['part']}", temporal="recent")
    for (concept, when), f in seen.items():
        label = display_name(concept)
        data: dict[str, Any] = {"symptom": label, "name": label, "date": when}
        sev = _int_severity(f.severity)
        if sev is not None:
            data["severity"] = sev
        elif f.severity_label:
            data["details"] = f.severity_label
        if f.temporal in {"recurring", "resolved"}:
            data["details"] = (data.get("details", "") + f" ({f.temporal})").strip()
        kind = "menstrual_symptom" if concept in MENSTRUAL_CONCEPTS else "symptom"
        add(kind, data, 0.9 if sev is not None else 0.8, metric=concept, temporal=f.temporal)

    # ---- cycle state
    if mt.get("period_active") or "cycle_day" in mt or "flow" in mt:
        if mt.get("period_active") is not False:
            data = {"name": "period", "symptom": "menstrual flow", "phase": "period", "period_active": True, "is_start": False}
            if mt.get("flow"):
                data["flow"] = mt["flow"]
                data["details"] = f"{mt['flow']} flow"
            if "cycle_day" in mt:
                cd = int(mt["cycle_day"])
                data["cycle_day"] = cd
                data["is_start"] = True
                data["start_date"] = (datetime.fromisoformat(day) - timedelta(days=max(cd - 1, 0))).date().isoformat()
            add("menstrual_symptom", data, 0.9, metric="period")
    elif mt.get("period_active") is False and "cycle_day" not in mt:
        add("menstrual_symptom", {"name": "period end", "symptom": "period ended", "is_start": False, "end_date": day}, 0.8, metric="period_end")

    # ---- sleep
    if "sleep_minutes" in mt:
        m = int(mt["sleep_minutes"])
        hours = round(m / 60, 2)
        data = {"name": "sleep", "duration_minutes": m, "hours": hours, "duration_hours": hours, "value": hours, "amount": hours, "unit": "hours"}
        for src, dst in (("bedtime", "bedtime_local"), ("wake_time", "wake_time_local"), ("awakenings", "awakenings")):
            if mt.get(src) is not None:
                data[dst] = mt[src]
        if isinstance(mt.get("sleep_quality"), int) and "sleep_quality" not in turn.log.estimates:
            data["severity"] = mt["sleep_quality"]
        add("sleep", data, 0.95, metric="sleep")

    # ---- hydration / caffeine
    if "water_ml" in mt:
        ml = int(mt["water_ml"])
        add("hydration", {"name": "water", "amount_ml": ml, "water_ml": ml, "amount": ml, "value": ml, "unit": "ml"}, 0.9, metric="water")
    if mt.get("caffeine_cups"):
        add("lifestyle", {"name": "coffee", "category": "caffeine", "count": mt["caffeine_cups"], "unit": "cup"}, 0.85, metric="caffeine")

    # ---- activity
    if "steps" in mt:
        add("activity", {"name": "walking", "activity": "walking", "steps": mt["steps"], "unit": "steps"}, 0.95, metric="steps")
    if "exercise_minutes" in mt:
        types = mt.get("exercise_types") or []
        name = _EXERCISE_NAME.get(types[0], types[0]) if len(types) == 1 else "exercise"
        add("exercise", {"name": name, "activity": ", ".join(types) or name, "duration_minutes": mt["exercise_minutes"],
                         "minutes": mt["exercise_minutes"], "unit": "min",
                         **({"distance_km": mt["exercise_distance_km"], "minutes_estimated": True} if mt.get("exercise_minutes_estimated") else {})},
            0.7 if mt.get("exercise_minutes_estimated") else 0.9, metric="exercise")

    # ---- body / vitals (one reading per event, already converted to kg / Celsius)
    if "weight_kg" in mt:
        w = mt["weight_kg"]
        add("weight", {"name": "weight", "weight_kg": w, "value": w, "amount": w, "unit": "kg"}, 0.95, metric="weight")
    if "heart_rate_bpm" in mt:
        add("vital_sign", {"name": "heart rate", "value": mt["heart_rate_bpm"], "unit": "bpm"}, 0.95, metric="hr")
    if "systolic_bp" in mt:
        add("vital_sign", {"name": "systolic", "value": mt["systolic_bp"], "unit": "mmHg"}, 0.95, metric="sys")
        add("vital_sign", {"name": "diastolic", "value": mt["diastolic_bp"], "unit": "mmHg"}, 0.95, metric="dia")
    if "temperature_c" in mt:
        add("vital_sign", {"name": "temperature", "value": mt["temperature_c"], "unit": "C"}, 0.95, metric="temp")
    if "spo2_percent" in mt:
        add("vital_sign", {"name": "spo2", "value": mt["spo2_percent"], "unit": "%"}, 0.95, metric="spo2")

    # ---- mood / energy / stress
    if mt.get("mood") or "mood_score" in mt:
        data = {"name": mt.get("mood") or "mood", "category": "mood"}
        if "mood_score" in mt and _int_severity(mt["mood_score"]):
            data.update(score=mt["mood_score"], mood_score=mt["mood_score"], severity=mt["mood_score"])
        add("mood", data, 0.85, metric="mood")
    if mt.get("energy") or "energy_score" in mt:
        data = {"name": "energy", "category": "energy"}
        if mt.get("energy"):
            data["level"] = mt["energy"]
        if "energy_score" in mt:
            data["score"] = mt["energy_score"]
        add("lifestyle", data, 0.85, metric="energy")
    if mt.get("stress") or "stress_score" in mt:
        data = {"name": "stress"}
        if _int_severity(mt.get("stress_score")):
            data.update(severity=mt["stress_score"], score=mt["stress_score"])
        if mt.get("stress"):
            data["level"] = mt["stress"]
        add("stress", data, 0.85, metric="stress")

    # ---- food per meal
    for slot, foods in turn.log.meals.items():
        data = {"name": ", ".join(foods), "meal": slot, "foods": foods}
        est = _estimate_nutrition(foods, {slot: turn.log.meal_phrases.get(slot, [])})
        if est:
            data.update(calories=est["calories"], protein_g=est["protein_g"], estimate_basis=est["basis"])
            if est.get("calories_low") is not None:
                data.update(calories_low=est["calories_low"], calories_high=est["calories_high"])
        add("food", data, 0.85, metric=f"meal-{slot}")

    for slot in mt.get("skipped_meals") or []:
        add("food", {"name": f"skipped {slot}", "meal": slot, "skipped": True, "foods": []}, 0.85, metric=f"skipped-{slot}")

    # ---- supplements / medication (only explicitly named)
    for supp in mt.get("supplements") or []:
        add("supplement", {"name": supp}, 0.9, metric=f"supp-{supp}")
    for med in mt.get("medications") or []:
        add("medication", {"name": med}, 0.9, metric=f"med-{med}")

    # ---- explicit denials: ONE screen record, never symptom events
    denied = list(dict.fromkeys(_name(f.concept) for f in turn.facts
                                if f.experiencer == "self" and f.assertion == "negated" and f.concept not in NON_SYMPTOM_CONCEPTS
                                and not f.concept.startswith("custom:")))
    if denied:
        add("wellness_checkin", {"pertinent_negatives": denied, "screen": "symptom_screen"}, 1.0, metric="screen")
    return out


def reconcile_ai_events(ai_events: list[Any], turn: Turn, rule_events: list[dict[str, Any]], message_id: str | None,
                        *, now: datetime | None = None) -> list[dict[str, Any]]:
    """Keep only AI-proposed events the user actually asserted about themselves, as present, in THIS message."""
    if not ai_events:
        return []
    now_iso = (now or datetime.now(timezone.utc)).isoformat()
    day = turn.log.log_date
    today = user_today(now)
    # Days the message itself names: a date the model proposes is kept only when the person actually said that day.
    said_days = {d.isoformat() for _pos, d in find_dates(turn.text, today)}
    proposed = []
    for ev in ai_events:
        try:
            et = str(ev.event_type).strip().lower()
            data = ev.extracted_data.model_dump(exclude_none=True) if hasattr(ev.extracted_data, "model_dump") else dict(ev.extracted_data or {})
            proposed.append((et, data, float(ev.confidence)))
        except Exception:  # noqa: BLE001
            continue
    terms = []
    for et, data, _c in proposed:
        term = str(data.get("symptom") or data.get("name") or data.get("category") or "").strip()
        if et in SYMPTOMISH_TYPES and term and concept_for_text(term) is None:
            terms.append(term)
    try:
        facts = analyze(turn.text, extra_terms=terms) if terms else turn.facts
    except Exception:  # noqa: BLE001
        facts = turn.facts
    covered = {(e["event_type"], str(e["extracted_data"].get("name") or e["extracted_data"].get("symptom") or "").lower()) for e in rule_events}
    covered_types = {e["event_type"] for e in rule_events}
    kept: list[dict[str, Any]] = []
    for et, data, conf in proposed:
        span = str(data.pop("evidence_span", "") or "").strip()
        data.pop("assertion", None)
        data.pop("subject", None)
        if span and span.casefold() not in turn.text.casefold():
            continue  # the model quoted something the user never wrote
        term = str(data.get("symptom") or data.get("name") or data.get("category") or "").strip()
        temporal = "current"
        named: date | None = None
        if et in SYMPTOMISH_TYPES:
            if not term:
                continue
            concept = concept_for_text(term) or f"custom:{term.lower()[:40]}"
            mentions = [f for f in facts if f.concept == concept and f.experiencer == "self"]
            live = [f for f in mentions if f.assertion == "present"]
            if not mentions or not live:
                continue  # ungrounded, denied, hypothetical, a question, quoted, someone else's, or merely possible
            temporal = live[0].temporal
            named = fact_day(turn, live[0], today)
            if (et, term.lower()) in covered:
                continue  # the rule-built event already records exactly this
            if any(e["event_type"] in {"symptom", "menstrual_symptom"} and str(e["extracted_data"].get("name", "")).lower() == _name(concept).lower()
                   for e in rule_events):
                continue  # same symptom already recorded deterministically (possibly under the other symptom type)
        elif et in covered_types and et in {"sleep", "hydration", "weight", "activity", "exercise", "food", "vital_sign", "mood", "stress"}:
            continue  # the deterministic parser already captured this domain from the same message
        data = {k: v for k, v in data.items() if v not in (None, "")}
        proposed_day = str(data.get("date") or "")[:10]
        data["date"] = named.isoformat() if named else (proposed_day if proposed_day in said_days else day)
        key = _key(message_id, et, term or data.get("category") or "", data["date"])
        data["_prov"] = _prov("llm", message_id, key, now_iso, temporal=temporal)
        kept.append({"event_type": et, "extracted_data": data, "confidence": min(conf, 0.9)})
    return kept


def _existing_keys(db: Any, user_id: str, message_id: str | None) -> set[str]:
    if not message_id:
        return set()
    try:
        rows = (db.table("extracted_health_events").select("id,extracted_data")
                .eq("user_id", user_id).eq("message_id", message_id).execute().data or [])
    except Exception:  # noqa: BLE001
        return set()
    keys = set()
    for r in rows:
        prov = (r.get("extracted_data") or {}).get("_prov") if isinstance(r.get("extracted_data"), dict) else None
        if isinstance(prov, dict) and prov.get("key"):
            keys.add(prov["key"])
    return keys


def event_summary(event_type: str, data: dict[str, Any]) -> str:
    """One readable line for a saved event ("Slept 6h 42m"), so the UI never prints raw keys."""
    d = {k: v for k, v in data.items() if not str(k).startswith("_")}
    name = str(d.get("name") or d.get("symptom") or event_type.replace("_", " "))

    def num(v: Any) -> str:
        return f"{v:g}" if isinstance(v, (int, float)) else str(v)

    if event_type == "wellness_checkin":
        return "Not present: " + ", ".join(str(x) for x in d.get("pertinent_negatives", []))
    if event_type == "sleep" and d.get("duration_minutes"):
        h, m = divmod(int(d["duration_minutes"]), 60)
        return f"Slept {h}h {m:02d}m" if m else f"Slept {h}h"
    if event_type == "hydration" and d.get("amount_ml"):
        return f"Water: {d['amount_ml'] / 1000:.1f} L"
    if event_type == "activity" and d.get("steps"):
        return f"{int(d['steps']):,} steps"
    if event_type == "exercise" and d.get("duration_minutes"):
        return f"{name.capitalize()}: {int(d['duration_minutes'])} min"
    if event_type == "weight" and d.get("weight_kg") is not None:
        return f"Weight: {num(d['weight_kg'])} kg"
    if event_type == "vital_sign" and d.get("value") is not None:
        return f"{name.capitalize()}: {num(d['value'])} {d.get('unit', '')}".strip()
    if event_type in {"symptom", "menstrual_symptom"}:
        if name == "period":
            bits = [f"cycle day {d['cycle_day']}" if d.get("cycle_day") else "", f"{d['flow']} flow" if d.get("flow") else ""]
            return "Period: " + (", ".join(b for b in bits if b) or "active")
        if name == "period end":
            return "Period ended"
        sev = f" {d['severity']}/10" if d.get("severity") else (f" ({d['details']})" if d.get("details") else "")
        return f"{name.capitalize()}{sev}"
    if event_type == "food":
        cal = f" (about {int(d['calories'])} kcal)" if d.get("calories") else ""
        return f"{str(d.get('meal', 'Meal')).capitalize()}: {name}{cal}"
    if event_type == "mood":
        return f"Mood: {name}" + (f" {d['score']}/10" if d.get("score") else "")
    if event_type == "stress":
        return "Stress: " + (f"{d['severity']}/10" if d.get("severity") else str(d.get("level", "noted")))
    if event_type == "lifestyle":
        if d.get("category") == "caffeine":
            return f"{name.capitalize()}: {d.get('count', '')} cup(s)".replace("  ", " ")
        return f"{name.capitalize()}: {d.get('level', d.get('score', 'noted'))}"
    if event_type in {"supplement", "medication"}:
        return f"Took {name}"
    return name.capitalize()


def persist_events(db: Any, user_id: str, message_id: str | None, events: list[dict[str, Any]], *, fresh: bool = False) -> list[dict[str, Any]]:
    """Insert pending events (batch first, row-by-row on failure). Returns UI-ready events; id is None when not saved.

    ``fresh`` says the message was created a moment ago, so no events of it can exist yet and the duplicate check (a read) is skipped."""
    if not events:
        return []   # nothing to save: no need to read what is already stored (a round trip on every plain chat turn)
    existing = set() if fresh else _existing_keys(db, user_id, message_id)
    todo = []
    for ev in events:
        key = (ev["extracted_data"].get("_prov") or {}).get("key")
        if key and key in existing:
            continue  # a retry of the same message must not duplicate events
        try:
            todo.append((ev, prepare_db_row(user_id=user_id, message_id=message_id, event=ev)))
        except Exception as error:  # noqa: BLE001
            _log_failure("prepare_event", error, user_id)
    ids: list[str | None] = [None] * len(todo)
    if todo:
        try:
            res = db.table("extracted_health_events").insert([row for _e, row in todo]).select("id").execute()
            data = res.data or []
            if len(data) == len(todo):
                ids = [str(r.get("id")) if r.get("id") else None for r in data]
            else:
                raise RuntimeError("batch insert returned an unexpected row count")
        except Exception as batch_error:  # noqa: BLE001
            _log_failure("persist_events_batch", batch_error, user_id)
            for i, (_ev, row) in enumerate(todo):
                try:
                    res = db.table("extracted_health_events").insert(row).select("id").execute()
                    if res.data and res.data[0].get("id"):
                        ids[i] = str(res.data[0]["id"])
                except Exception as error:  # noqa: BLE001
                    _log_failure("persist_event", error, user_id)
    out = []
    for (ev, _row), event_id in zip(todo, ids):
        prov = ev["extracted_data"].get("_prov") or {}
        out.append({
            "id": event_id, "event_type": ev["event_type"], "extracted_data": clean_data(ev["extracted_data"]),
            "summary": event_summary(ev["event_type"], ev["extracted_data"]), "confidence": ev["confidence"], "assertion": prov.get("assertion", "present"), "temporal": prov.get("temporal", "current"),
            "status": "pending", "provenance": {k: prov.get(k) for k in ("source", "extractor", "recorded_at")},
        })
    return out


# --------------------------------------------------------------------------
# Response + stored metadata
# --------------------------------------------------------------------------

def safety_payload(safety: SafetyAssessment, *, correction: dict[str, Any] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"level": safety.level, "state": safety.state, "reasons": list(safety.reasons),
                           "concepts": list(safety.concepts), "retracted": False}
    if correction:
        out["correction"] = correction
    return out


def semantic_trace(turn: Turn) -> list[dict[str, Any]]:
    """Compact diagnostics for development: what was understood and why (never the user's text)."""
    return [{"concept": t.get("concept"), "assertion": t.get("assertion"), "temporal": t.get("temporal"),
             "reason": t.get("reason"), "decision": t.get("decision"), "why": t.get("why")}
            for t in turn.safety.trace][:40]


def stored_metadata(*, kind: str, user_message_id: str, safety: dict[str, Any], events: list[dict[str, Any]],
                    evidence_ids: list[Any], conflicts: list[dict[str, Any]], trace: list[dict[str, Any]],
                    package: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "source": "bubbles_api", "kind": kind, "user_message_id": user_message_id, "safety": safety,
        "evidence": evidence_ids, "health_event_ids": [e["id"] for e in events],
        "health_events": [{"id": e["id"], "event_type": e["event_type"], "extracted_data": e["extracted_data"],
                           "summary": e.get("summary"), "confidence": e["confidence"], "status": e["status"], "assertion": e["assertion"], "temporal": e["temporal"]}
                          for e in events][:MAX_STORED_EVENTS],
        **({"health_events_more": len(events) - MAX_STORED_EVENTS} if len(events) > MAX_STORED_EVENTS else {}),
        "conflicts": conflicts[:5], "semantic_trace": trace,
        **({"evidence_package": package} if package else {}),   # audit trail: which engines ran and which facts/evidence were used
    }


# ---------------------------------------------------------------------------------------------------------------------------------
# the prompt budget (plan 5.4)
# ---------------------------------------------------------------------------------------------------------------------------------

#: Characters for everything the prompt adds on top of the two fixed voice texts (SYSTEM_INSTRUCTION and the response style): the safety lines,
#: the setup style, the recent conversation, the person model, open threads, the person's own context and the evidence. Shorter prompts also answer faster.
PROMPT_BUDGET = 9000
RECENT = "recent_conversation"
MIN_RECENT_TURNS = 4
NL = chr(10)


def fit_blocks(blocks: list[tuple[str, str, int]], budget: int = PROMPT_BUDGET) -> dict[str, str]:
    """The text each block keeps once the whole fits in ``budget`` characters.

    ``blocks`` is ``(name, text, priority)`` in prompt order. Priority 0 is never dropped (safety, the setup voice). When over budget the
    block with the largest priority number goes first (ties: the later one), then the recent conversation is trimmed oldest line first down to
    ``MIN_RECENT_TURNS`` lines. Blocks are dropped whole, never cut in the middle, so no sentence is ever half-sent."""
    keep = {name: text for name, text, _p in blocks if text and text.strip()}
    priority = {name: p for name, _t, p in blocks}
    order = {name: i for i, (name, _t, _p) in enumerate(blocks)}

    def size() -> int:
        return sum(len(t) + 2 for t in keep.values())

    for name in sorted(keep, key=lambda n: (-priority[n], -order[n])):
        if size() <= budget:
            break
        if priority[name] > 0 and name != RECENT:
            del keep[name]
    if size() > budget and RECENT in keep:
        head, _, body = keep[RECENT].partition(NL)
        lines = body.split(NL) if body else []
        while len(lines) > MIN_RECENT_TURNS and size() - len(keep[RECENT]) + len(head) + len(NL.join(lines)) + 1 > budget:
            lines.pop(0)
        keep[RECENT] = head + NL + NL.join(lines) if lines else head
    return keep


def assemble_context(blocks: list[tuple[str, str, int]], budget: int = PROMPT_BUDGET) -> str:
    """The blocks that fit, in prompt order, separated by a blank line."""
    kept = fit_blocks(blocks, budget)
    return (NL + NL).join(kept[name] for name, _t, _p in blocks if name in kept)


# ---------------------------------------------------------------------------------------------------------------------------------
# suggestion chips (plan C7): deterministic, by route and topic, at most three, in the language the person writes in
# ---------------------------------------------------------------------------------------------------------------------------------

_NO_CHIPS = {"emergency", "safe_harbor", "safety_followup", "clarification", "correction", "orbit_redirect"}
_CHIPS: dict[str, dict[str, tuple[str, ...]]] = {
    "en": {
        "relationship": ("Help me work out what to say", "Why do I feel this way about it?", "Open in Heart-to-heart"),
        "mind": ("What could help me feel calmer?", "Can we talk it through?", "What can I do for the next hour?"),
        "cycle": ("What is normal in this phase?", "Help me log how I feel", "What should I ask my doctor?"),
        "body": ("What should I keep an eye on?", "When should I see a doctor?", "Can you explain that more simply?"),
        "fitness": ("Suggest a simple plan", "What should I eat today?", "How do I stay consistent?"),
        "care": ("Help me prepare questions for my doctor", "What should I keep track of?", "Can you explain that more simply?"),
        "log": ("How did my week look?", "Log something else", "What should I keep an eye on?"),
        "default": ("Can you explain that more simply?", "What should I keep an eye on?", "Help me prepare questions for my clinician"),
    },
    "hinglish": {
        "relationship": ("Kya bolna chahiye, samajhne mein madad karo", "Mujhe aisa kyun lag raha hai?", "Open in Heart-to-heart"),
        "mind": ("Mujhe shaant hone mein kya madad karega?", "Chalo isse baat karke dekhte hain", "Agle ek ghante ke liye kya kar sakta hoon?"),
        "cycle": ("Is phase mein kya normal hai?", "Meri feeling log karne mein madad karo", "Doctor se kya poochna chahiye?"),
        "body": ("Mujhe kis cheez par nazar rakhni chahiye?", "Doctor ko kab dikhana chahiye?", "Isse aasan shabdon mein samjhao"),
        "fitness": ("Ek simple plan batao", "Aaj kya khana chahiye?", "Main regular kaise rahun?"),
        "care": ("Doctor ke liye sawaal taiyaar karne mein madad karo", "Mujhe kya track karna chahiye?", "Isse aasan shabdon mein samjhao"),
        "log": ("Mera hafta kaisa raha?", "Kuch aur log karo", "Mujhe kis cheez par nazar rakhni chahiye?"),
        "default": ("Isse aasan shabdon mein samjhao", "Mujhe kis cheez par nazar rakhni chahiye?", "Doctor ke liye sawaal taiyaar karne mein madad karo"),
    },
}
_CHIP_ORDER = ("relationship", "mind", "cycle", "body", "fitness", "care")


def suggestions_for(turn: Turn, *, consent_required: bool = False) -> list[str]:
    """Up to three quick replies for the newest Bubbles message. Empty on safety replies and while a consent question is open; those are not a
    moment for chips. Language follows how the person wrote (Roman-script Hindi gets Hinglish chips)."""
    if turn.route in _NO_CHIPS or consent_required or turn.safety.state != "NO_REDFLAG" or turn.harbor.tier >= 1:
        return []
    lang = "hinglish" if safe_harbor.detect_language(turn.text) in ("hi", "hi-latn") else "en"
    bank = _CHIPS[lang]
    if turn.route == "daily_log":
        return list(bank["log"][:3])
    for topic in _CHIP_ORDER:
        if topic in turn.topics:
            return list(bank[topic][:3])
    return list(bank["default"][:3])


# ---------------------------------------------------------------------------------------------------------------------------------
# Orbit (relationship support): the voice block, and the fixed answer to a request to manipulate or secretly check someone
# ---------------------------------------------------------------------------------------------------------------------------------

ORBIT_BLOCK = """ORBIT MODE (relationship support):
- You are Bubbles, a warm friend who understands relationships well. The person is talking about someone they love or are close to. Only their side is known; never judge the other person or the relationship.
- First, show you heard the feeling under the words. Then help them see the pattern, not the villain: "it sounds like the more you reach out, the more they pull back" (the cycle is the problem, not either person).
- Offer at most one skill, in plain words: a soft start ("I feel ... about ... and I need ..."), a repair line, a pause when things are heated, turning toward small bids, asking instead of assuming.
- If they want to reply to their partner, offer to draft it in their language (Hinglish stays Hinglish).
- Use PATTERN CARDS only when the person's own words match them, and never name a pattern as a diagnosis.
- Never: tell them to stay or leave; label anyone (toxic, narcissist, manipulative); help them check, track, test or make their partner jealous; generalise about men, women, families, castes or star signs; reveal or guess anything about their partner's own Bubbles use.
- If they mention being hit, threatened, choked, forced or afraid, stop coaching and follow SAFE HARBOR (handled by the app).
- Keep it short: 3 to 5 sentences unless they ask for more. At most one question."""

_REDIRECT = {
    "en": ("I'd rather help you say what you need directly. Wanting to know where you stand is human, but checking up on someone, testing them or making them jealous "
           "tends to leave both of you feeling worse. If you tell me what you are hoping to find out, or what you are feeling, I can help you put it into an honest message to them."),
    "hinglish": ("Main chahunga ki tum jo chahte ho woh seedhe bol sako, aur main usme madad karunga. Jaanna ki hum kahan khade hain, ye bilkul insaani hai, par kisi pe nazar rakhna, "
                 "unhe test karna ya jealous karna aksar dono ko aur bura feel karata hai. Tum bataao ki tum kya jaanna chahte ho ya kya feel kar rahe ho, "
                 "toh main use ek sachche message mein likhne mein madad kar sakta hoon."),
}


_HINGLISH_HINTS = re.compile(r"\b(?:usse|use|unhe|uska|uski|uske|kaise|karna|karni|karun|karoon|hai|hain|chahta|chahti|mujhe|mera|meri|nahi|chupke)\b", re.I)


def orbit_redirect_reply(text: str) -> str:
    hinglish = safe_harbor.detect_language(text) in ("hi", "hi-latn") or len(_HINGLISH_HINTS.findall(text or "")) >= 2
    return _REDIRECT["hinglish" if hinglish else "en"]


def orbit_blocks(turn: Turn, history: list[dict[str, Any]]) -> list[tuple[str, str, int]]:
    """Prompt blocks for the orbit route: the voice (never dropped) and up to two pattern cards (dropped early if the prompt is full).
    The cards come from the new message, with the last two messages adding a little weight; relationship talk may use looser matching."""
    cards = orbit_knowledge.cards_for(turn.text, history, limit=2, loose=True)
    block = orbit_knowledge.prompt_block(cards, turn.country) if cards else orbit_knowledge.catalogue_block(turn.country)
    return [("orbit", ORBIT_BLOCK, 0), ("pattern_cards", block, 6)]
