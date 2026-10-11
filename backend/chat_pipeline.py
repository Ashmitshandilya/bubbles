"""Chat turn orchestration: understand -> decide -> respond -> save.

``main.chat`` stays a thin HTTP wrapper around this module. Everything here is plain
Python over an injected ``db`` handle so it is unit-testable without FastAPI.

Flow for one user message:

1. ``analyze_turn``   - semantic facts, safety state, correction?, contradictions, daily-log metrics
2. ``route_turn``     - emergency | correction | clarification | daily_log | ai
3. build the reply    - deterministic copy for the first four (no model call, no health data
                        leaves the server); the model only handles the "ai" route, with a
                        controlled context (recent turns + explicit user state + labelled evidence)
4. save               - rule-built events (explicit values only) and AI-proposed events after
                        reconciliation against what the user actually said; denials are stored
                        once as a symptom screen, never as symptoms.
"""
from __future__ import annotations

import hashlib
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from conversation_correction import (
    Correction, NOT_A_CORRECTION, contradiction_note, correction_response, detect_contradictions, detect_correction,
)
from daily_log_parser import DailyLog, _estimate_nutrition, parse_daily_log, summarize_log
from event_filters import DEAD_STATUSES, clean_data
from health_event_pipeline import prepare_db_row
from health_semantics import Fact, analyze, concept_for_text, display_name, net_state
from safety_engine import (
    POTENTIAL, SafetyAssessment, assess_safety, clarification_response, emergency_response, urgent_fallback_response,
)

HISTORY_TURNS = 10
HISTORY_FACT_MESSAGES = 6
ACTIVE_TEMPORALS = {"current", "recent", "recurring", "unknown"}
SYMPTOMISH_TYPES = {"symptom", "menstrual_symptom", "medical_condition", "allergy", "medication", "supplement", "family_medical_history"}
MENSTRUAL_CONCEPTS = {"cramps", "spotting"}
NON_SYMPTOM_CONCEPTS = {"period", "medication_use"}

KINDS = ("reply", "clarification", "emergency", "correction_ack", "daily_log_summary")


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
    events = meta.get("health_events") if isinstance(meta.get("health_events"), list) else []
    return {
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
    }


def conversation_block(history: list[dict[str, Any]], max_chars: int = 2400) -> str:
    lines: list[str] = []
    for row in history[-8:]:
        content = " ".join(str(row.get("content") or "").split())
        meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        if row.get("role") == "bubbles" and (meta.get("safety") or {}).get("retracted"):
            content = "[withdrawn: Bubbles misread the user here and retracted this warning]"
        label = "User" if row.get("role") == "user" else "Bubbles"
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
    if not (text.endswith("?") or len(text) <= 160):
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


def history_user_facts(history: list[dict[str, Any]]) -> list[Fact]:
    out: list[Fact] = []
    users = [r for r in history if r.get("role") == "user" and r.get("content")][-HISTORY_FACT_MESSAGES:]
    for row in users:
        try:
            out.extend(analyze(str(row["content"])[:1500]))
        except Exception as error:  # noqa: BLE001
            _log_failure("history_facts", error)
    return out


def analyze_turn(text: str, history: list[dict[str, Any]], *, now: datetime | None = None) -> Turn:
    t0 = time.perf_counter()
    try:
        facts: list[Fact] | None = analyze(text)
    except Exception as error:  # noqa: BLE001
        _log_failure("analyze", error)
        facts = None
    safety = assess_safety(text, facts)  # never raises; falls back to a keyword fail-safe when facts is None
    facts = facts or []
    t1 = time.perf_counter()
    history_facts = history_user_facts(history)
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
    turn.route = route_turn(turn)
    turn.timings_ms = {"semantics_ms": round((t1 - t0) * 1000, 1), "turn_ms": round((time.perf_counter() - t0) * 1000, 1)}
    return turn


def route_turn(turn: Turn) -> str:
    state = turn.safety.state
    if state == "EMERGENCY":
        return "emergency"
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
    return fitness or "ai"


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
    return {"emergency": "emergency", "correction": "correction_ack", "clarification": "clarification",
            "daily_log": "daily_log_summary", "fitness_support": "fitness_support", "fitness_answer": "fitness_answer"}.get(route, "reply")


def deterministic_reply(turn: Turn, *, name: str | None, saved_events: int) -> str:
    route, safety = turn.route, turn.safety
    if route == "emergency":
        return emergency_response(safety)
    if route in ("fitness_support", "fitness_answer"):
        return ""   # filled in by main._fitness_text (needs the database)
    if route == "correction":
        text = correction_response(turn.correction)
        if safety.state == POTENTIAL:
            text += "\n\n" + clarification_response(safety)
        return text
    if route == "clarification":
        text = clarification_response(safety)
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
    if saved_events:
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


def build_rule_events(turn: Turn, message_id: str | None, *, now: datetime | None = None) -> list[dict[str, Any]]:
    """Events from explicitly stated values only (nothing inferred). Denials become ONE symptom-screen event."""
    now = now or datetime.now(timezone.utc)
    now_iso = now.isoformat()
    mt, day = turn.log.metrics, turn.log.log_date
    out: list[dict[str, Any]] = []

    def add(event_type: str, data: dict[str, Any], confidence: float = 0.9, *, metric: str = "", temporal: str = "current") -> None:
        key = _key(message_id, event_type, metric or data.get("name") or data.get("symptom") or "", day)
        data = {**data, "date": data.get("date", day)}
        data["_prov"] = _prov("rules", message_id, key, now_iso, temporal=temporal)
        out.append({"event_type": event_type, "extracted_data": data, "confidence": confidence})

    # ---- symptoms the user reports as current/recent/recurring
    seen: dict[str, Fact] = {}
    for f in turn.facts:
        if f.experiencer != "self" or f.assertion != "present" or f.concept in NON_SYMPTOM_CONCEPTS or f.concept.startswith("custom:"):
            continue
        if not (f.temporal in ACTIVE_TEMPORALS or (f.temporal == "resolved" and f.same_day)):
            continue
        prev = seen.get(f.concept)
        if prev is None or (f.severity or 0) > (prev.severity or 0):
            seen[f.concept] = f
    for concept, f in seen.items():
        label = display_name(concept)
        data: dict[str, Any] = {"symptom": label, "name": label}
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
        name = types[0] if len(types) == 1 else "exercise"
        add("exercise", {"name": name, "activity": ", ".join(types) or name, "duration_minutes": mt["exercise_minutes"],
                         "minutes": mt["exercise_minutes"], "unit": "min"}, 0.9, metric="exercise")

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
        if et in SYMPTOMISH_TYPES:
            if not term:
                continue
            concept = concept_for_text(term) or f"custom:{term.lower()[:40]}"
            mentions = [f for f in facts if f.concept == concept and f.experiencer == "self"]
            live = [f for f in mentions if f.assertion == "present"]
            if not mentions or not live:
                continue  # ungrounded, denied, hypothetical, a question, quoted, someone else's, or merely possible
            temporal = live[0].temporal
            if (et, term.lower()) in covered:
                continue  # the rule-built event already records exactly this
            if any(e["event_type"] in {"symptom", "menstrual_symptom"} and str(e["extracted_data"].get("name", "")).lower() == _name(concept).lower()
                   for e in rule_events):
                continue  # same symptom already recorded deterministically (possibly under the other symptom type)
        elif et in covered_types and et in {"sleep", "hydration", "weight", "activity", "exercise", "food", "vital_sign", "mood", "stress"}:
            continue  # the deterministic parser already captured this domain from the same message
        data = {k: v for k, v in data.items() if v not in (None, "")}
        data.setdefault("date", day)
        key = _key(message_id, et, term or data.get("category") or "", day)
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


def persist_events(db: Any, user_id: str, message_id: str | None, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Insert pending events (batch first, row-by-row on failure). Returns UI-ready events; id is None when not saved."""
    existing = _existing_keys(db, user_id, message_id)
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
                          for e in events][:30],
        "conflicts": conflicts[:5], "semantic_trace": trace,
        **({"evidence_package": package} if package else {}),   # audit trail: which engines ran and which facts/evidence were used
    }
