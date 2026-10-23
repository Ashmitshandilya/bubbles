"""The Person Model: what Bubbles has learned about how one person likes to be talked to, in a list the person can read and correct.

One signed document per person (``doc_store`` kind ``person_model``, key ``v1``), so there is no schema change and "delete all my data" and the
data export already cover it. Each trait is a list of dated pieces of evidence, never a message: a note is a fixed template ("you chose this in
setup"), never anything the person wrote. Confidence is computed from the evidence on every read (plan 6.3), so it fades with time:

    effective(e) = weight * 0.5 ** (age_days / 60)           half-life of 60 days
    confidence   = support(top value) / (support(all values) + 1)       the +1 keeps thin evidence humble
    used         = not rejected and (confirmed or (confidence >= 0.6 and non_prior_weight >= 1.0))

A "prior" (a weak hint such as culture) can order the questions Bubbles asks but never passes that gate alone, because only non-prior evidence
counts toward ``non_prior_weight``. A person can confirm ("That's me", always used) or reject ("Not me": removed and never inferred again).

Writes happen after the reply is sent (``observe_*`` run as deferred housekeeping) and never raise into a request.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

import doc_store
from ttl_cache import TTLCache

KIND, KEY = "person_model", "v1"
HALF_LIFE_DAYS = 60.0
GATE_CONFIDENCE = 0.6
GATE_NON_PRIOR = 1.0
MAX_EVIDENCE = 12
PINNED = ("setup", "confirmed")        # kept even when the rest is trimmed; at most one of each per value
MAX_PROMPT_LINES = 8
CONFIRM_WEIGHT = 3.0

_cache = TTLCache("person_model", ttl_s=30, max_entries=5000)

# ---- the catalogue: every trait Bubbles can hold, with the sentence the person reads -------------------------------------------------

_DRAINS = {"work_study_pressure": "work or study pressure", "money": "money worries", "family_or_relationship_tension": "tension with family or a partner",
           "not_enough_sleep": "not enough sleep", "health_worries": "health worries", "noise_or_crowds": "noise or crowds", "traffic_commute": "traffic or commuting",
           "screens_social_media": "screens and social media", "heat": "heat", "being_rushed": "being rushed"}
_SUPPORT = {"family": "family", "partner": "your partner", "friends": "friends", "colleagues_classmates": "colleagues or classmates",
            "online_communities": "online communities", "a_pet": "your pet", "faith_or_community": "your faith or community"}
_CARED = {"words": "kind words", "time": "time together", "help": "someone helping out", "touch": "a hug or a touch", "gifts": "thoughtful gifts"}

#: id -> {values: {value: sentence}, multi: bool, learns: what the empty page says Bubbles would use it for, prompt: {value: line for the model}}
TRAITS: dict[str, dict[str, Any]] = {
    "reply_length": {
        "values": {"short": "You like short replies.", "balanced": "You like replies that are not too short and not too long.", "detailed": "You like fuller, detailed replies."},
        "prompt": {"short": "prefers short replies", "balanced": "likes medium-length replies", "detailed": "likes fuller, detailed replies"},
        "learns": "how long you like replies to be"},
    "tone": {
        "values": {"gentle_warm": "You like it when Bubbles is gentle and warm.", "calm_direct": "You like a calm, direct tone.", "cheerful_playful": "You like a cheerful, lightly playful tone."},
        "prompt": {"gentle_warm": "responds best to a gentle, warm tone", "calm_direct": "likes calm and direct, without filler", "cheerful_playful": "likes a cheerful tone (never about serious things)"},
        "learns": "the tone you like"},
    "wording": {
        "values": {"simple": "You like simple, plain words."},
        "prompt": {"simple": "likes simple, plain words and short sentences"},
        "learns": "whether plain words suit you"},
    "language_mix": {
        "values": {"english": "You usually write in English.", "hinglish": "You usually write in Hinglish.", "hindi": "You usually write in Hindi."},
        "prompt": {"english": "writes in English", "hinglish": "writes in Hinglish (Roman script)", "hindi": "writes in Hindi (Devanagari)"},
        "learns": "the language you write in"},
    "active_time": {
        "values": {"early": "You tend to be around early in the morning.", "day": "You tend to be around during the day.", "evening": "You tend to be around in the evening.",
                   "late_night": "You tend to be around late at night."},
        "prompt": {"early": "is usually around early morning", "day": "is usually around in the daytime", "evening": "is usually around in the evening", "late_night": "is often up late at night"},
        "learns": "when you are usually around"},
    "stress_response": {
        "values": {"talks_it_out": "When you are stressed, you like to talk it out.", "goes_quiet": "When you are stressed, you tend to go quiet.",
                   "keeps_busy": "When you are stressed, you tend to keep yourself busy."},
        "prompt": {"talks_it_out": "talks things out when stressed", "goes_quiet": "often goes quiet when stressed (do not push)", "keeps_busy": "keeps busy when stressed"},
        "learns": "what you do when you are stressed"},
    "sleep_sensitive_mood": {
        "values": {"yes": "Your mood seems to follow how well you sleep.", "no": "Your mood does not seem to follow how well you sleep."},
        "prompt": {"yes": "mood tends to follow sleep", "no": "mood does not clearly follow sleep"},
        "learns": "whether your sleep and mood move together"},
    "reassurance_need": {
        "values": {"high": "You often like to hear that things are okay between you and someone close.", "usual": "You do not need a lot of reassurance from the people close to you."},
        "prompt": {"high": "values reassurance about close relationships", "usual": "does not look for much reassurance"},
        "learns": "how you feel about reassurance"},
    "conflict_style": {
        "values": {"pursues": "In a disagreement, you tend to want to talk it through right away.", "withdraws": "In a disagreement, you tend to need space first.",
                   "balanced": "In a disagreement, you are somewhere in between."},
        "prompt": {"pursues": "in a disagreement wants to talk it through at once", "withdraws": "in a disagreement needs space first", "balanced": "balanced in disagreements"},
        "learns": "how you handle a disagreement"},
    "cared_for_by": {
        "multi": True, "values": {k: f"You feel cared for by {v}." for k, v in _CARED.items()}, "prompt": {k: f"feels cared for by {v}" for k, v in _CARED.items()},
        "learns": "what makes you feel cared for"},
    "drains": {
        "multi": True, "values": {k: f"{v[0].upper()}{v[1:]} tends to drain you." for k, v in _DRAINS.items()}, "prompt": {k: f"drained by {v}" for k, v in _DRAINS.items()},
        "learns": "what tends to drain you"},
    "support_people": {
        "multi": True, "values": {k: f"You usually turn to {v} when something is on your mind." for k, v in _SUPPORT.items()},
        "prompt": {k: f"usually turns to {v}" for k, v in _SUPPORT.items()}, "learns": "who you turn to"},
}

#: the short reason for a piece of evidence, shown as "Why we think so" (singular, plural with {n}). Never message text.
NOTES: dict[str, tuple[str, str]] = {
    "setup": ("you chose it in setup", "you chose it in setup"),
    "too_long": ("you marked a reply too long", "you marked {n} replies too long"),
    "worried_me": ("you said a reply worried you", "you said {n} replies worried you"),
    "unclear": ("you said a reply was unclear", "you said {n} replies were unclear"),
    "message_language": ("it is how you write", "it is how you write in most messages"),
    "message_time": ("you chat at these times", "you chat at these times"),
    "stress_phrase": ("you said so", "you have said so {n} times"),
    "orbit_checkin": ("you said so in a check-in", "you said so in {n} check-ins"),
    "association": ("your own logs show it", "your own logs show it"),
    "confirmed": ("you told us it is right", "you told us it is right"),
}

_STRESS = (
    ("talks_it_out", re.compile(r"\b(?:i )?(?:need|want|have) to (?:vent|talk (?:it|things) (?:out|through)|talk about it)\b|\bjust (?:want|need) to talk\b|baat karna (?:hai|chahta|chahti)|kisi se baat karna", re.I)),
    ("goes_quiet", re.compile(r"\bi (?:just |always )?(?:shut down|go quiet|go silent|withdraw|isolate myself)\b|\bi (?:don'?t|do not) (?:want to|wanna) talk\b|chup (?:ho jata|ho jati|rehta|rehti)|baat karne ka mann nahi", re.I)),
    ("keeps_busy", re.compile(r"\b(?:i )?(?:keep|keeping) myself busy\b|\b(?:bury|throw) myself (?:in|into) (?:my )?work\b|kaam mein lag (?:jata|jati)|khud ko busy rakh", re.I)),
)


# ---- pure rules -----------------------------------------------------------------------------------------------------------------------

def _parse(at: Any) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(at).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def effective_weight(e: dict[str, Any], now: datetime) -> float:
    at = _parse(e.get("at"))
    age = max(0.0, (now - at).total_seconds() / 86400.0) if at else 0.0
    try:
        return float(e.get("weight", 0.0)) * 0.5 ** (age / HALF_LIFE_DAYS)
    except (TypeError, ValueError):
        return 0.0


def new_model() -> dict[str, Any]:
    return {"version": 1, "updated_at": None, "traits": {}, "rejected": []}


def _clean_model(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return new_model()
    model = new_model()
    model["updated_at"] = raw.get("updated_at")
    model["rejected"] = [t for t in raw.get("rejected", []) if t in TRAITS] if isinstance(raw.get("rejected"), list) else []
    traits = raw.get("traits") if isinstance(raw.get("traits"), dict) else {}
    for tid, entry in traits.items():
        if tid in TRAITS and isinstance(entry, dict) and isinstance(entry.get("evidence"), list):
            ev = [e for e in entry["evidence"] if isinstance(e, dict) and e.get("value") in TRAITS[tid]["values"]]
            if ev:
                model["traits"][tid] = {**{k: entry.get(k) for k in ("state", "first_seen", "last_seen")}, "state": "confirmed" if entry.get("state") == "confirmed" else "inferred", "evidence": ev}
    return model


def resolve(tid: str, entry: dict[str, Any] | None, now: datetime) -> dict[str, Any] | None:
    """The current reading of one trait: ``{values, confidence, non_prior, used, state}`` or None when there is no evidence.

    For a single-valued trait ``values`` is the top value and ``confidence`` is the plan's formula. For a multi-valued trait every value is read on its own
    (``support / (support + 1)``) and ``values`` lists those that pass the gate (or all of them, when none does, so the page can still show them)."""
    if not entry or not entry.get("evidence"):
        return None
    spec = TRAITS[tid]
    support: dict[str, float] = {}
    non_prior: dict[str, float] = {}
    for e in entry["evidence"]:
        w = effective_weight(e, now)
        support[e["value"]] = support.get(e["value"], 0.0) + w
        if not e.get("prior"):
            non_prior[e["value"]] = non_prior.get(e["value"], 0.0) + w
    confirmed = entry.get("state") == "confirmed"
    if spec.get("multi"):
        rows = {v: (s / (s + 1.0), non_prior.get(v, 0.0)) for v, s in support.items()}
        passing = [v for v, (c, n) in rows.items() if confirmed or (c >= GATE_CONFIDENCE and n >= GATE_NON_PRIOR)]
        shown = passing or sorted(rows, key=lambda v: -rows[v][0])
        top = max(rows[v][0] for v in shown)
        return {"values": sorted(shown, key=lambda v: -rows[v][0]), "confidence": top, "non_prior": max(rows[v][1] for v in shown), "used": bool(passing), "state": entry.get("state")}
    top_value = max(support, key=lambda v: support[v])
    total = sum(support.values())
    confidence = support[top_value] / (total + 1.0)
    npw = non_prior.get(top_value, 0.0)
    return {"values": [top_value], "confidence": confidence, "non_prior": npw, "state": entry.get("state"),
            "used": confirmed or (confidence >= GATE_CONFIDENCE and npw >= GATE_NON_PRIOR)}


def confidence_word(c: float, confirmed: bool = False) -> str:
    if confirmed:
        return "Sure"
    return "Sure" if c >= 0.8 else "Fairly sure" if c >= GATE_CONFIDENCE else "Not sure yet"


def add_evidence(model: dict[str, Any], tid: str, value: str, source: str, note: str, weight: float, now: datetime, *, prior: bool = False, replace_source: bool = False) -> bool:
    """Add one piece of evidence (pure: changes ``model``). False when the trait or value is unknown or the person rejected the trait.
    ``replace_source`` first removes this trait's earlier evidence from the same source (a person who redoes setup replaces their old answer)."""
    spec = TRAITS.get(tid)
    if spec is None or value not in spec["values"] or tid in model["rejected"] or note not in NOTES:
        return False
    stamp = now.astimezone(timezone.utc).isoformat()
    entry = model["traits"].setdefault(tid, {"state": "inferred", "first_seen": stamp, "evidence": []})
    if replace_source:
        entry["evidence"] = [e for e in entry["evidence"] if e.get("source") != source]
    entry["evidence"].append({"source": source, "value": value, "note": note, "at": stamp, "weight": float(weight), **({"prior": True} if prior else {})})
    pinned = [e for e in entry["evidence"] if e["source"] in PINNED]
    rest = [e for e in entry["evidence"] if e["source"] not in PINNED]
    room = max(0, MAX_EVIDENCE - len(pinned))
    rest = sorted(rest, key=lambda e: str(e.get("at")))[-room:] if room else []
    entry["evidence"] = sorted(pinned + rest, key=lambda e: str(e.get("at")))
    entry["last_seen"] = stamp
    model["updated_at"] = stamp
    return True


def forget_source(model: dict[str, Any], tid: str, source: str) -> None:
    entry = model["traits"].get(tid)
    if entry:
        entry["evidence"] = [e for e in entry["evidence"] if e.get("source") != source]
        if not entry["evidence"]:
            model["traits"].pop(tid, None)


def confirm(model: dict[str, Any], tid: str, now: datetime) -> bool:
    """"That's me": the trait is used from now on, and the person's word is evidence. False when there is nothing to confirm."""
    entry = model["traits"].get(tid)
    reading = resolve(tid, entry, now)
    if tid not in TRAITS or reading is None or tid in model["rejected"]:
        return False
    for value in reading["values"]:
        add_evidence(model, tid, value, "confirmed", "confirmed", CONFIRM_WEIGHT, now, replace_source=False)
    # one confirmed item per value is enough: drop older duplicates
    seen: set[str] = set()
    kept = []
    for e in sorted(model["traits"][tid]["evidence"], key=lambda e: str(e.get("at")), reverse=True):
        if e["source"] == "confirmed":
            if e["value"] in seen:
                continue
            seen.add(e["value"])
        kept.append(e)
    model["traits"][tid]["evidence"] = sorted(kept, key=lambda e: str(e.get("at")))
    model["traits"][tid]["state"] = "confirmed"
    return True


def reject(model: dict[str, Any], tid: str) -> bool:
    """"Not me": removed, and never inferred again."""
    if tid not in TRAITS:
        return False
    model["traits"].pop(tid, None)
    if tid not in model["rejected"]:
        model["rejected"].append(tid)
    return True


def _label(tid: str, values: list[str], key: str) -> str:
    return TRAITS[tid][key][values[0]]


def line_for(tid: str, values: list[str]) -> str:
    """The sentence the person reads. A multi-valued trait joins its values into one sentence."""
    spec = TRAITS[tid]
    if spec.get("multi") and len(values) > 1:
        names = {"drains": _DRAINS, "support_people": _SUPPORT, "cared_for_by": _CARED}[tid]
        parts = [names[v] for v in values]
        joined = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]
        return {"drains": f"{joined[0].upper()}{joined[1:]} tend to drain you.", "support_people": f"You usually turn to {joined} when something is on your mind.",
                "cared_for_by": f"You feel cared for by {joined}."}[tid]
    return _label(tid, values, "values")


def why_for(entry: dict[str, Any], values: list[str], setup_labels: dict[str, str] | None = None) -> str:
    """"Why we think so: ..." from the notes only, counted ("you marked 2 replies too long")."""
    counts: dict[str, int] = {}
    for e in entry["evidence"]:
        if e["value"] in values and not e.get("prior"):
            counts[e["note"]] = counts.get(e["note"], 0) + 1
    parts = []
    for note in ("setup", "confirmed", "too_long", "worried_me", "unclear", "stress_phrase", "orbit_checkin", "association", "message_language", "message_time"):
        n = counts.get(note, 0)
        if n:
            single, many = NOTES[note]
            parts.append(single if n == 1 else many.format(n=n))
    if not parts:
        return ""
    text = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + ", and " + parts[-1]
    return f"Why we think so: {text}."


def understanding(model: dict[str, Any], now: datetime) -> list[dict[str, Any]]:
    """What the page shows: one entry per trait with evidence, strongest first. No percentages, nothing from a message."""
    out = []
    for tid, entry in model["traits"].items():
        reading = resolve(tid, entry, now)
        if reading is None:
            continue
        confirmed = reading["state"] == "confirmed"
        out.append({"id": tid, "line": line_for(tid, reading["values"]), "why": why_for(entry, reading["values"]), "confidence": confidence_word(reading["confidence"], confirmed),
                    "state": reading["state"], "used": reading["used"], "_c": reading["confidence"]})
    out.sort(key=lambda r: (r["state"] != "confirmed", -r["_c"]))
    for r in out:
        r.pop("_c")
    return out


def prompt_lines(model: dict[str, Any], now: datetime) -> list[str]:
    rows = []
    for tid, entry in model["traits"].items():
        if tid in model["rejected"]:
            continue
        reading = resolve(tid, entry, now)
        if reading is None or not reading["used"]:
            continue
        spec = TRAITS[tid]
        text = "; ".join(spec["prompt"][v] for v in reading["values"][:3])
        rows.append((reading["state"] != "confirmed", -reading["confidence"], f"- {text}" + (" (confirmed)" if reading["state"] == "confirmed" else "")))
    rows.sort()
    return [r[2] for r in rows[:MAX_PROMPT_LINES]]


# ---- signals read from a message (the message itself is never stored) ------------------------------------------------------------------

def hour_bucket(hour: int) -> str:
    return "early" if 5 <= hour <= 8 else "day" if 9 <= hour <= 16 else "evening" if 17 <= hour <= 21 else "late_night"


def stress_response_of(text: str) -> str | None:
    hits = [tid for tid, rx in _STRESS if rx.search(text or "")]
    return hits[0] if len(hits) == 1 else None      # two different answers in one message say nothing


def language_of(text: str) -> str | None:
    """english / hinglish / hindi from the script and a few common words, or None when the message is too short to tell."""
    if len(re.findall(r"[A-Za-zऀ-ॿ]+", text or "")) < 3:
        return None
    from safe_harbor import detect_language
    return {"hi": "hindi", "hi-latn": "hinglish"}.get(detect_language(text), "english")


def signals_from_message(text: str, local_hour: int) -> list[tuple[str, str, str, float]]:
    """(trait, value, note, weight) for what one message shows. Fixed templates only."""
    out = [("active_time", hour_bucket(local_hour), "message_time", 0.2)]
    lang = language_of(text)
    if lang:
        out.append(("language_mix", lang, "message_language", 0.2))
    stress = stress_response_of(text)
    if stress:
        out.append(("stress_response", stress, "stress_phrase", 1.0))
    return out


def setup_signals(answers: dict[str, Any]) -> list[tuple[str, str, str, float]]:
    """What the setup answers say (weight 3: the person told us directly)."""
    out: list[tuple[str, str, str, float]] = []
    if answers.get("tone") in TRAITS["tone"]["values"]:
        out.append(("tone", answers["tone"], "setup", 3.0))
    if answers.get("reply_length") in ("short", "detailed"):
        out.append(("reply_length", answers["reply_length"], "setup", 3.0))
    if answers.get("language") in TRAITS["language_mix"]["values"]:
        out.append(("language_mix", answers["language"], "setup", 3.0))
    for tid in ("drains", "support_people"):
        picks = answers.get(tid)
        for v in (picks if isinstance(picks, list) else []):
            if v in TRAITS[tid]["values"]:
                out.append((tid, v, "setup", 3.0))
    return out


#: the traits setup can write, so a redo of setup can clear an answer the person later skipped
SETUP_TRAITS = ("tone", "reply_length", "language_mix", "drains", "support_people")


# ---- storage -------------------------------------------------------------------------------------------------------------------------

def _log(operation: str, error: Exception) -> None:
    try:
        from logging_util import logger
        logger.warning(component="PERSON_MODEL", operation=operation, error=error, fallback_action="continue")   # never the evidence
    except Exception:  # noqa: BLE001
        pass


def load(db: Any, uid: str, *, fresh: bool = False) -> dict[str, Any]:
    """The person's model (a new empty one when there is none or it cannot be read). Remembered for 30 seconds; every write forgets it."""
    def read() -> dict[str, Any]:
        return _clean_model(doc_store.get(db, uid, KIND, KEY))
    try:
        if fresh:
            return read()
        return _cache.get_or_compute(str(uid), read)
    except Exception as error:  # noqa: BLE001
        _log("load", error)
        return new_model()


def forget(uid: str) -> None:
    _cache.invalidate(str(uid))


def save(db: Any, uid: str, model: dict[str, Any]) -> None:
    doc_store.put(db, uid, KIND, KEY, model)
    forget(uid)


def wipe(db: Any, uid: str) -> bool:
    """Delete the whole model, rejections included (a fresh start)."""
    forget(uid)
    return doc_store.delete(db, uid, KIND, KEY)


def prompt_block(db: Any, uid: str, now: datetime | None = None) -> str:
    """The PERSON MODEL lines for the chat prompt (at most 8, confirmed first), or "". Never raises."""
    try:
        lines = prompt_lines(load(db, uid), now or datetime.now(timezone.utc))
        return ("PERSON MODEL (how this person tends to be; use quietly, never recite):\n" + "\n".join(lines)) if lines else ""
    except Exception as error:  # noqa: BLE001
        _log("prompt_block", error)
        return ""


def _apply(db: Any, uid: str, change) -> None:
    """Read fresh, let ``change(model)`` edit it, save if anything changed. Last write wins; a failure is logged and swallowed."""
    try:
        model = load(db, uid, fresh=True)
        before = repr(model)
        change(model)
        if repr(model) != before:
            save(db, uid, model)
    except Exception as error:  # noqa: BLE001
        _log("apply", error)


def observe_setup(db: Any, uid: str, answers: dict[str, Any], now: datetime | None = None) -> None:
    """After setup is completed: what the person chose becomes weight-3 evidence, replacing their earlier setup answers."""
    now = now or datetime.now(timezone.utc)

    def change(model: dict[str, Any]) -> None:
        for tid in SETUP_TRAITS:
            forget_source(model, tid, "setup")
        for tid, value, note, weight in setup_signals(answers or {}):
            add_evidence(model, tid, value, "setup", note, weight, now)

    _apply(db, uid, change)


def observe_feedback(db: Any, uid: str, rating: str, reason: str | None, now: datetime | None = None) -> None:
    """After a thumbs-down with a reason: too long, worried me, unclear. Each counts 1, so one tap is a hint and two are a trait."""
    if rating != "down" or reason not in ("too_long", "worried_me", "unclear"):
        return
    now = now or datetime.now(timezone.utc)
    trait, value = {"too_long": ("reply_length", "short"), "worried_me": ("tone", "gentle_warm"), "unclear": ("wording", "simple")}[reason]
    _apply(db, uid, lambda m: add_evidence(m, trait, value, "feedback", reason, 1.0, now))


def _may_learn_from_chat(db: Any, uid: str) -> bool:
    """What is read from chat messages (when and how someone writes, how they cope) is learned only with the same yes as the other details noticed in chat."""
    try:
        from consent import is_granted
        return bool(is_granted(db, uid, "health_memory_from_chat"))
    except Exception:  # noqa: BLE001 - no clear yes means nothing is learned
        return False


def observe_turn(db: Any, uid: str, text: str, offset_min: int = 0,  now: datetime | None = None) -> None:
    """After a reply is sent: what this message shows about when and how the person writes. Only fixed notes are stored, never the message."""
    if not _may_learn_from_chat(db, uid):
        return
    now = now or datetime.now(timezone.utc)
    hour = (now + timedelta(minutes=max(-840, min(840, int(offset_min))))).hour

    def change(model: dict[str, Any]) -> None:
        for tid, value, note, weight in signals_from_message(str(text or "")[:1500], hour):
            add_evidence(model, tid, value, "chat", note, weight, now)

    _apply(db, uid, change)


def observe_evidence(db: Any, uid: str, items: list[tuple[str, str, str, str, float]], now: datetime | None = None) -> None:
    """For Orbit check-ins and the association engine: ``(trait, value, source, note, weight)`` items, added together."""
    now = now or datetime.now(timezone.utc)
    _apply(db, uid, lambda m: [add_evidence(m, t, v, s, n, w, now) for t, v, s, n, w in items])
