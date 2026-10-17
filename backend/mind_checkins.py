"""Mind: one-tap mood check-ins, year-in-pixels, gentle PHQ-2 / GAD-2 check-ins, journal, breathing/grounding exercises, correlations.

Safety first: ANY free text (check-in note, journal) is passed to ``safety_engine.assess_safety`` before anything else.
If the state is URGENT or EMERGENCY (or crisis wording is present) the deterministic safety response is returned and no
mind logic runs and nothing is stored. Nothing here calls a model.

Storage (no schema change):
  * mood check-ins reuse the tracker: ``health_logs.save_domain('mood')``. Activities ride in the entry notes as
    ``Activities: exercise, social`` (fixed vocabulary, parsed back by ``parse_activities``);
  * ``mind_pixels`` / key = year: per-day mood averages so the year view is not limited by the tracker's 200-row read cap;
  * ``mind_screen`` / key = "<phq2|gad2>:<date>": score only, no free text;
  * ``journal`` / key = entry id: text-only entries with ``local_only`` (never sent to any model or included in AI context).
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

import clinical_constants as K
import doc_store
from health_logs import DOMAINS, list_domain
from safety_engine import CRISIS_LINES
from safety_gate import safety_gate  # noqa: F401 - re-exported: wellness_api and the tests call Mind.safety_gate
from wellness_common import InputError, choice, local_date_of, number, parse_date, text

SCREENS = {"phq2": {"questions": K.PHQ2_QUESTIONS, "positive_at": K.PHQ2_POSITIVE_AT, "topic": "low mood"},
           "gad2": {"questions": K.GAD2_QUESTIONS, "positive_at": K.GAD2_POSITIVE_AT, "topic": "worry"},
           # One direct question each, a score only (no labels, no sum). Thresholds are Bubbles' own, listed in docs/drafts/l3-clinical.md.
           "loneliness": {"questions": ("How often do you feel lonely?",), "scale": (1, 5), "positive_at": 4, "topic": "feeling lonely",
                          "labels": ("Never", "Rarely", "Sometimes", "Often", "Almost always")},
           "anxiety": {"questions": ("How anxious do you feel right now?",), "scale": (0, 10), "positive_at": 7, "topic": "anxiety",
                       "labels": {0: "0, calm", 10: "10, very anxious"}}}
ANSWER_LABELS = ("Not at all", "Several days", "More than half the days", "Nearly every day")
SCREEN_INTRO = "Over the last 2 weeks, how often have you been bothered by the following?"
FACES = [{"face": 1, "mood": 2, "label": "Rough"}, {"face": 2, "mood": 4, "label": "Low"}, {"face": 3, "mood": 6, "label": "Okay"},
         {"face": 4, "mood": 8, "label": "Good"}, {"face": 5, "mood": 10, "label": "Great"}]
EXERCISES = (
    {"id": "slow_breathing", "name": "Slow breathing", "kind": "breathing", "minutes": 3, "pattern": {"inhale": 4, "exhale": 6},
     "steps": ["Breathe in through your nose for 4.", "Breathe out gently through your mouth for 6.", "Let your belly soften. Repeat for a few minutes."]},
    {"id": "box_breathing", "name": "Box breathing", "kind": "breathing", "minutes": 3, "pattern": {"inhale": 4, "hold": 4, "exhale": 4, "hold_empty": 4},
     "steps": ["Sit comfortably and relax your shoulders.", "Breathe in through your nose for 4.", "Hold gently for 4.",
               "Breathe out slowly for 4.", "Rest for 4, then repeat for a few minutes."]},
    {"id": "four_seven_eight", "name": "4-7-8 breathing", "kind": "breathing", "minutes": 2, "pattern": {"inhale": 4, "hold": 7, "exhale": 8},
     "steps": ["Breathe in quietly for 4.", "Hold for 7 if that feels comfortable.", "Breathe out slowly for 8.", "Do a few rounds, then breathe normally."]},
    {"id": "grounding_54321", "name": "5-4-3-2-1 grounding", "kind": "grounding", "minutes": 4, "pattern": None,
     "steps": ["Notice 5 things you can see.", "Notice 4 things you can touch or feel.", "Notice 3 things you can hear.",
               "Notice 2 things you can smell.", "Notice 1 thing you can taste, then take a slow breath."]},
    {"id": "body_scan", "name": "Short body scan", "kind": "grounding", "minutes": 5, "pattern": None,
     "steps": ["Close your eyes if that feels okay.", "Move your attention slowly from your feet up to your head.",
               "Notice each area without trying to change it.", "Finish with three slow breaths."]},
    {"id": "muscle_release", "name": "Brief muscle release", "kind": "grounding", "minutes": 4, "pattern": None,
     "steps": ["Tighten your fists for a few seconds, then let go.", "Do the same for shoulders, then jaw, then legs.", "Notice the difference as you release."]},
)
EXERCISE_NOTE = "Stop and breathe normally if you feel dizzy or uncomfortable. These are relaxation tools, not treatment."
SUPPORT_NOTE = "If you ever feel you might harm yourself, please reach out right away. " + CRISIS_LINES


#: Static, label-free copy per topic for the Mind hub (friend voice, no diagnosis, no medicine). Every step names a tool that exists.
SUPPORT_COPY = {
    "loneliness": {"title": "Loneliness check-in",
                   "text": "Feeling lonely is more common than people say, and it doesn't mean something is wrong with you. A small reach-out often helps: a short message to one person, or a walk where other people are around.",
                   "steps": ["Send one short message to someone you like.", "Go somewhere with other people nearby, even for ten minutes.", "Say it here in chat. I'm happy to listen."]},
    "panic": {"title": "Breathe and ground",
              "text": "You are safe right now. This feeling is strong, and it passes. Let's slow it down together.",
              "steps": ["Breathe in through your nose for 4.", "Breathe out slowly for 6, longer than the breath in.", "Press your feet into the floor and name 3 things you can see."]},
    "apart": {"title": "Missing someone / apart",
              "text": "Missing someone you love is a sign of how much they matter. Being apart can feel heavy, and small rituals make it easier.",
              "steps": ["Pick a regular time to talk, so you have something to look forward to.", "Send a voice note or a photo of your day.", "Keep one small thing of theirs close, and do one kind thing for yourself today."]},
}

#: Same copy under the name the /wellness/mind/topics route serves.
TOPIC_COPY = SUPPORT_COPY


# --- safety gate ---------------------------------------------------------------------------------------------------------

# --- check-ins -----------------------------------------------------------------------------------------------------------

def normalize_checkin(body: dict) -> dict[str, Any]:
    if body.get("face") not in (None, "") and body.get("mood") in (None, ""):
        face = int(number(body.get("face"), 1, 5, "face", required=True))
        mood: float | None = FACES[face - 1]["mood"]
    else:
        mood = number(body.get("mood"), 1, 10, "mood", required=True)
    acts = body.get("activities") or []
    if not isinstance(acts, list) or len(acts) > 12:
        raise InputError("activities must be a short list")
    clean = []
    for a in acts:
        v = choice(a, K.MIND_ACTIVITIES, "activity")
        if v not in clean:
            clean.append(v)
    out: dict[str, Any] = {"mood": mood, "activities": clean, "notes": text(body.get("notes"), 1000, "note")}
    for key in ("stress", "anxiety"):
        v = number(body.get(key), 0, 10, key)
        if v is not None:
            out[key] = v
    return out


def tracker_body(c: dict, date_str: str | None) -> dict:
    """The body for health_logs.save_domain('mood')."""
    notes = " | ".join(p for p in ((f"Activities: {', '.join(c['activities'])}" if c["activities"] else None), c.get("notes")) if p) or None
    body = {"mood": c["mood"], "notes": notes}
    for key in ("stress", "anxiety"):
        if key in c:
            body[key] = c[key]
    if date_str:
        body["date"] = date_str
    return body


_ACT = re.compile(r"Activities: ([a-z_, ]+?)(?: \||$)")


def parse_activities(notes: Any) -> list[str]:
    m = _ACT.search(str(notes or ""))
    return [a.strip() for a in m.group(1).split(",") if a.strip() in K.MIND_ACTIVITIES] if m else []


def level_of(mood: float) -> int:
    """Pixel colour level 1 (rough) to 5 (great)."""
    return max(1, min(5, -(-int(round(mood)) // 2)))


# --- year in pixels ------------------------------------------------------------------------------------------------------

def per_day_moods(entries: list[dict], tz_offset_min: int = 0) -> dict[str, dict[str, Any]]:
    days: dict[str, list[float]] = {}
    for e in entries:
        d = local_date_of(e.get("date"), tz_offset_min)
        try:
            m = float(e.get("mood"))
        except (TypeError, ValueError):
            continue
        if d and 1 <= m <= 10:
            days.setdefault(d, []).append(m)
    return {d: {"m": round(sum(v) / len(v), 2), "n": len(v)} for d, v in days.items()}


def merge_pixels(stored: dict[str, dict], recent: dict[str, dict], truncated_oldest: str | None = None) -> dict[str, dict]:
    """The tracker rows are the source of truth for the days they cover; older days keep their stored value. When the read hit its
    row cap the oldest day may be partial, so it is not allowed to overwrite."""
    out = dict(stored)
    for d, v in recent.items():
        if d != truncated_oldest:
            out[d] = v
    return out


def year_pixels(days: dict[str, dict], year: int) -> dict[str, Any]:
    cells, counts = [], {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    d = date(year, 1, 1)
    while d.year == year:
        v = days.get(d.isoformat())
        lvl = level_of(v["m"]) if v else None
        if lvl:
            counts[lvl] += 1
        cells.append({"date": d.isoformat(), "mood": v["m"] if v else None, "level": lvl, "entries": v["n"] if v else 0})
        d += timedelta(days=1)
    return {"year": year, "days": cells, "logged_days": sum(counts.values()), "level_counts": counts,
            "legend": {"1": "Rough", "2": "Low", "3": "Okay", "4": "Good", "5": "Great"}}


# --- PHQ-2 / GAD-2 -------------------------------------------------------------------------------------------------------

def _options(spec: dict) -> list[dict[str, Any]]:
    lo_hi = spec.get("scale")
    if not lo_hi:
        return [{"value": i, "label": l} for i, l in enumerate(ANSWER_LABELS)]
    labels = spec["labels"]
    return [{"value": v, "label": labels[v - lo_hi[0]] if isinstance(labels, tuple) else labels.get(v, str(v))} for v in range(lo_hi[0], lo_hi[1] + 1)]


def screen_questions(kind: str) -> dict[str, Any]:
    kind = choice(kind, tuple(SCREENS), "check-in")
    spec = SCREENS[kind]
    return {"kind": kind, "intro": SCREEN_INTRO if "scale" not in spec else "", "questions": list(spec["questions"]), "options": _options(spec),
            "note": "This is a gentle check-in, not a medical assessment."}


_SINGLE_MESSAGES = {
    ("loneliness", True): "Thank you for being honest about that. Feeling lonely is more common than people say, and it doesn't mean something is wrong with you. "
                          "A short message to one person you like can help, and you can always talk to me here. " + SUPPORT_NOTE,
    ("loneliness", False): "Thanks for checking in. Feeling lonely now and then is part of life. Keep leaning on the people who make you feel good.",
    ("anxiety", True): "That sounds like a lot right now. Try the Breathe and ground tool: breathe in for 4, out for 6, a few times. "
                       "If it keeps coming back or feels too big, a counsellor or your doctor can really help. " + SUPPORT_NOTE,
    ("anxiety", False): "Thanks for checking in. It can change through the day, so check in again any time. "
                        "A slow breath out, longer than the breath in, can take the edge off.",
}


def score_screen(kind: str, answers: Any) -> dict[str, Any]:
    kind = choice(kind, tuple(SCREENS), "check-in")
    spec = SCREENS[kind]
    lo, hi = spec.get("scale", (0, 3))
    if not isinstance(answers, list) or len(answers) != len(spec["questions"]) or any(isinstance(a, bool) or not isinstance(a, int) or not lo <= a <= hi for a in answers):
        raise InputError(f"answer each of the {len(spec['questions'])} questions with {lo} to {hi}")
    total = sum(answers)
    positive = total >= spec["positive_at"]
    if "scale" in spec:
        return {"kind": kind, "score": total, "max_score": hi, "suggest_talking_to_someone": positive, "message": _SINGLE_MESSAGES[(kind, positive)]}
    if positive:
        msg = (f"Thank you for answering. Your answers suggest things around {spec['topic']} have felt heavy lately. "
               "This check-in isn't a medical assessment, but it may be worth talking to someone you trust, a counsellor or your doctor. "
               "You don't have to work it out alone. " + SUPPORT_NOTE)
    else:
        msg = "Thank you for checking in. Your answers don't suggest a lot of strain right now. Keep an eye on how you feel, and reach out any time that changes."
    return {"kind": kind, "score": total, "max_score": 3 * len(answers), "suggest_talking_to_someone": positive, "message": msg}


def screen_due(last: list[dict], today: date) -> dict[str, Any]:
    """Offer a check-in at most every MIND_SCREEN_INTERVAL_DAYS."""
    dates = [d["payload"].get("date") for d in last if d.get("payload", {}).get("date") and d["payload"].get("kind", "phq2") in ("phq2", "gad2")]
    latest = max(dates) if dates else None
    due = latest is None or (today - date.fromisoformat(latest)).days >= K.MIND_SCREEN_INTERVAL_DAYS
    return {"due": due, "last": latest, "every_days": K.MIND_SCREEN_INTERVAL_DAYS}


# --- journal -------------------------------------------------------------------------------------------------------------

def normalize_journal(body: dict) -> dict[str, Any]:
    body_text = text(body.get("text"), K.MIND_JOURNAL_MAX_CHARS, "entry")
    if not body_text:
        raise InputError("write something first")
    local_only = body.get("local_only", False)
    if not isinstance(local_only, bool):
        raise InputError("local_only must be true or false")
    out: dict[str, Any] = {"text": body_text, "local_only": local_only}
    mood = number(body.get("mood"), 1, 10, "mood")
    if mood is not None:
        out["mood"] = mood
    return out


def journal_for_ai(entries: list[dict]) -> list[dict]:
    """The only journal entries any model or AI context may ever see: none marked local_only. Callers that build AI context from
    journal entries MUST pass them through this."""
    return [e for e in entries if not (e.get("payload", e)).get("local_only")]


# --- correlations --------------------------------------------------------------------------------------------------------

def _group_diff(label_with: str, label_without: str, with_: list[float], without: list[float]) -> dict[str, Any] | None:
    if len(with_) < K.MIND_INSIGHT_MIN_PER_GROUP or len(without) < K.MIND_INSIGHT_MIN_PER_GROUP:
        return None
    if len(with_) + len(without) < K.MIND_INSIGHT_MIN_DAYS:
        return None
    diff = sum(with_) / len(with_) - sum(without) / len(without)
    if abs(diff) < K.MIND_INSIGHT_MIN_DIFF:
        return None
    higher = "higher" if diff > 0 else "lower"
    return {"diff": round(diff, 1), "with_n": len(with_), "without_n": len(without),
            "confidence": "moderate" if min(len(with_), len(without)) >= 7 else "low",
            "text": (f"On {label_with}, your mood tended to be about {abs(diff):.1f} points {higher} than on {label_without} "
                     f"({len(with_)} days compared with {len(without)}). It's a pattern in your own logs, not proof of a cause.")}


def correlations(mood_by_day: dict[str, float], *, sleep_hours: dict[str, float] | None = None, sleep_goal: float = 8.0,
                 exercise_days: set[str] | None = None, phase_by_day: dict[str, str] | None = None,
                 activities_by_day: dict[str, list[str]] | None = None) -> dict[str, Any]:
    """Mood against sleep, exercise, cycle phase and tagged activities. Each needs MIND_INSIGHT_MIN_DAYS paired days and
    MIND_INSIGHT_MIN_PER_GROUP days per group; wording is always a tendency."""
    out: list[dict[str, Any]] = []
    if sleep_hours:
        pair = [(mood_by_day[d], h) for d, h in sleep_hours.items() if d in mood_by_day]
        r = _group_diff("days after a night near your sleep goal", "days after shorter sleep",
                        [m for m, h in pair if h >= sleep_goal - K.SLEEP_ON_TRACK_TOLERANCE_H], [m for m, h in pair if h < sleep_goal - K.SLEEP_ON_TRACK_TOLERANCE_H])
        if r:
            out.append({"factor": "sleep", **r})
    if exercise_days is not None:
        r = _group_diff("days you were active", "days you weren't", [m for d, m in mood_by_day.items() if d in exercise_days],
                        [m for d, m in mood_by_day.items() if d not in exercise_days])
        if r:
            out.append({"factor": "exercise", **r})
    if phase_by_day:
        phased = {d: m for d, m in mood_by_day.items() if d in phase_by_day}
        for phase in sorted(set(phase_by_day.values())):
            r = _group_diff(f"days in the {phase} phase", "other days", [m for d, m in phased.items() if phase_by_day[d] == phase],
                            [m for d, m in phased.items() if phase_by_day[d] != phase])
            if r:
                out.append({"factor": f"cycle_phase:{phase}", **r})
    if activities_by_day:
        for act in K.MIND_ACTIVITIES:
            logged = {d: m for d, m in mood_by_day.items() if d in activities_by_day}
            r = _group_diff(f"days with {act}", f"days without {act}", [m for d, m in logged.items() if act in activities_by_day[d]],
                            [m for d, m in logged.items() if act not in activities_by_day[d]])
            if r:
                out.append({"factor": f"activity:{act}", **r})
    gaps = [] if out else [f"Not enough data yet for patterns: they need about {K.MIND_INSIGHT_MIN_DAYS} days of check-ins, "
                           f"including at least {K.MIND_INSIGHT_MIN_PER_GROUP} days on each side of a comparison."]
    return {"insights": sorted(out, key=lambda i: -abs(i["diff"])), "data_gaps": gaps}


# --- loaders -------------------------------------------------------------------------------------------------------------

def load_mood_entries(db: Any, uid: str, days: int) -> list[dict]:
    return list_domain(db, "mood", DOMAINS["mood"], uid, days)["entries"]


def load_pixels(db: Any, uid: str, year: int) -> dict[str, dict]:
    return (doc_store.get(db, uid, "mind_pixels", str(year)) or {}).get("days", {})


def save_pixels(db: Any, uid: str, year: int, days: dict[str, dict]) -> None:
    doc_store.put(db, uid, "mind_pixels", str(year), {"days": days})
