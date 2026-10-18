"""Organ map: what the user's own logs say about ten areas of the body, in plain words, with the receipts.

NOT a diagnosis. Every organ gets one of four statuses, and the exact entries that decided it:

    no_data          nothing in the window touches this area. A gap, never "healthy".
    steady           there is data and none of the rules below fired. Not a clean bill of health.
    worth_watching   a documented threshold was crossed, or a symptom keeps coming back.
    talk_to_doctor   a red flag (re-checked by the safety engine) or a threshold that clinical guidance says
                     deserves a clinician. Safety guidance is returned FIRST in the organ payload.

Pure functions over data the caller already loaded (no database access here, see organ_map_api.py):

    events      extracted_health_events rows. Only live, positive, first-person observations count
                (event_filters.counts_as_observation); dates come from event_filters.event_moment.
    labs        tracker lab entries   {id, date, test_name, value, unit, reference_range}  (any age)
    conditions  tracker condition entries {id, date, condition_name, status}               (any age)
    cycle       None, or {"phase", "cycle_day", "flags": [cycle_flags.compute_flags() dicts]}

Thresholds live in clinical_constants (ORGAN MAP block, pending clinician review). Recent symptoms are re-assessed with
safety_engine.assess_safety, the same deterministic triage chat uses, so the map can never be calmer than chat.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from statistics import mean, median
from typing import Any, Iterable

import clinical_constants as K
from event_filters import clean_data, counts_as_observation, event_moment, parse_moment, provenance
from food_db import find_food
from health_semantics import analyze
from safety_engine import assess_safety

STATUSES = ("no_data", "steady", "worth_watching", "talk_to_doctor")
_RANK = {s: i for i, s in enumerate(STATUSES)}

ORGANS: dict[str, str] = {
    "heart": "Heart",
    "lungs": "Lungs",
    "brain": "Brain",
    "eyes": "Eyes",
    "stomach_intestines": "Stomach and intestines",
    "liver_pancreas": "Liver and pancreas",
    "kidneys_bladder": "Kidneys and bladder",
    "thyroid": "Thyroid",
    "uterus_ovaries": "Uterus and ovaries",
    "skeleton_muscles": "Bones and muscles",
    "skin": "Skin",
}
CHAT_NAMES = {"stomach_intestines": "stomach and intestines", "liver_pancreas": "liver and pancreas",
              "kidneys_bladder": "kidneys and bladder", "uterus_ovaries": "uterus and ovaries", "skeleton_muscles": "bones and muscles"}

# Shown only to people who use Cycle or have logged something for the area (not everyone has these organs).
OPT_IN_ORGANS = frozenset({"uterus_ovaries"})


def _uses_cycle(cycle: dict | None) -> bool:
    return bool(cycle and (cycle.get("phase") or cycle.get("flags")))


NOT_A_DIAGNOSIS = ("This map only reflects what you have logged. It is not a diagnosis, and an area with no entries "
                   "is a gap, not a sign that all is well.")

# safety-engine concepts -> body areas
CONCEPT_ORGANS: dict[str, tuple[str, ...]] = {
    "chest_pain": ("heart",), "heart_attack": ("heart",), "palpitations": ("heart",), "fainting": ("heart", "brain"),
    "shortness_of_breath": ("lungs",), "cough": ("lungs",), "sore_throat": ("lungs",), "allergic_reaction": ("lungs", "skin"),
    "headache": ("brain",), "dizziness": ("brain",), "seizure": ("brain",), "stroke_signs": ("brain",), "confusion": ("brain",),
    "numbness": ("brain",), "blurred_vision": ("brain", "eyes"), "anxiety": ("brain",), "panic_attack": ("brain",), "loneliness": ("brain",), "separation_anxiety": ("brain",), "low_mood": ("brain",), "insomnia": ("brain",),
    "suicidal_ideation": ("brain",), "self_harm": ("brain",),
    "nausea": ("stomach_intestines",), "vomiting": ("stomach_intestines",), "persistent_vomiting": ("stomach_intestines",),
    "vomiting_blood": ("stomach_intestines",), "abdominal_pain": ("stomach_intestines",), "bloating": ("stomach_intestines",),
    "diarrhea": ("stomach_intestines",), "constipation": ("stomach_intestines",),
    "cramps": ("uterus_ovaries",), "pelvic_pain": ("uterus_ovaries",), "heavy_bleeding": ("uterus_ovaries",),
    "spotting": ("uterus_ovaries",), "unusual_bleeding": ("uterus_ovaries",),
    "back_pain": ("skeleton_muscles",), "joint_pain": ("skeleton_muscles",), "muscle_pain": ("skeleton_muscles",),
    "rash": ("skin",),
    "eye_strain": ("eyes",), "dry_eyes": ("eyes",), "red_eye": ("eyes",), "eye_pain": ("eyes",), "eye_itch": ("eyes",),
}
# words the safety vocabulary does not cover (tracker symptoms are free text)
EXTRA_TERMS: dict[str, re.Pattern] = {organ: re.compile(rf"\b(?:{words})\b", re.I) for organ, words in {
    "lungs": r"wheez\w*|asthma\w*|breathless\w*|phlegm|congest\w*",
    "brain": r"migraines?|brain fog",
    "stomach_intestines": r"acidity|heartburn|reflux|indigestion|gas|gastric|loose motions?|stomach ?ache|tummy ache",
    "kidneys_bladder": r"urin\w*|pee|peeing|bladder|uti|kidney\w*|burning (?:pee|urine|urination)",
    "skin": r"acne|pimples?|eczema|itch\w*|hives|psoriasis|dry skin|skin \w+|sunburn",
    "skeleton_muscles": r"sprain\w*|stiff\w*|knee pain|shoulder pain|neck pain|backache|sore muscles?",
}.items()}
# the Eyes tracker's symptom chips (health_logs.EYE_SYMPTOMS) in the words the rest of the map uses; "headache" is a brain symptom, not read as an eye one
EYE_CHIPS = {"dry": "dry eyes", "itchy": "itchy eyes", "red": "red eyes", "strained": "eye strain", "blurry": "blurred vision", "watery": "watery eyes"}
URINARY_TALK = re.compile(r"\b(?:blood in (?:my |the )?(?:urine|pee)|ha?ematuria|bloody (?:urine|pee))\b", re.I)
THYROID_WORDS = re.compile(r"\b(?:thyroid\w*|hypothyroid\w*|hyperthyroid\w*|hashimoto\w*|graves)\b", re.I)
PCOS_WORDS = re.compile(r"\b(?:pcos|pcod|polycystic ovar\w*)\b", re.I)
TSH_WORDS = re.compile(r"\b(?:tsh|thyroid stimulating hormone|thyrotropin)\b", re.I)
_ALCOHOL = re.compile(r"\b(?:" + "|".join(re.escape(w) for w in K.ORGAN_ALCOHOL_TERMS) + r")\b", re.I)
_SUGARY = re.compile(r"\b(?:" + "|".join(re.escape(w) for w in K.ORGAN_SUGARY_TERMS) + r")\b", re.I)
_CYCLE_NAMES = {"period", "period end", "cycle phase", "cycle day log"}
_SOURCES = {"user_message": "chat", "tracker": "tracker"}


# --------------------------------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------------------------------

def _num(*values: Any) -> float | None:
    for v in values:
        if isinstance(v, bool) or v in (None, ""):
            continue
        try:
            n = float(v)
        except (TypeError, ValueError):
            continue
        if n == n and abs(n) < 1e9:  # not NaN, not absurd
            return n
    return None


def _day(value: Any) -> date | None:
    moment = parse_moment(str(value)[:10]) if value else None
    return moment.date() if moment else None


def _fmt(d: date) -> str:
    return f"{d.day} {d.strftime('%b')}"


def _g(n: float) -> str:
    return f"{n:g}" if n == int(n) else f"{n:.1f}"


def _plural(n: int, word: str, many: str | None = None) -> str:
    return f"{n} {word if n == 1 else (many or word + 's')}"


def _raise(current: str, new: str) -> str:
    return new if _RANK[new] > _RANK[current] else current


def _item(o: dict, label: str | None = None, value: Any = None, unit: str | None = None) -> dict:
    return {"id": o.get("id"), "date": o["date"].isoformat(), "label": label or o["label"],
            "value": o.get("value") if value is None else value, "unit": o.get("unit") if unit is None else unit,
            "source": o["source"]}


# --------------------------------------------------------------------------------------------------
# rows -> observations
# --------------------------------------------------------------------------------------------------

def _text_of(data: dict) -> str:
    parts = [data.get(k) for k in ("name", "description", "drink_type", "meal")]
    foods = data.get("foods")
    if isinstance(foods, list):
        parts += foods
    return " ".join(str(p) for p in parts if isinstance(p, (str, int, float)))


def _is_sugary(data: dict) -> bool:
    text = _text_of(data)
    if _SUGARY.search(text):
        return True
    items = data.get("foods") if isinstance(data.get("foods"), list) else [data.get("name") or data.get("description")]
    return any(isinstance(i, str) and (find_food(i) or {}).get("category") == "sweet" for i in items)


def _symptom_obs(base: dict, name: str, severity: Any, details: Any) -> dict:
    sev = _num(severity)
    text = " ".join(p for p in (name, f"{_g(sev)}/10" if sev is not None and 0 <= sev <= 10 else "",
                                str(details) if isinstance(details, str) else "") if p)
    facts = analyze(text)
    concepts = {f.concept for f in facts if f.assertion == "present"}
    organs = {o for c in concepts for o in CONCEPT_ORGANS.get(c, ())}
    organs |= {o for o, rx in EXTRA_TERMS.items() if rx.search(name)}
    return {**base, "kind": "symptom", "label": name[:1].upper() + name[1:], "value": None if sev is None else f"{_g(sev)}/10",
            "unit": None, "text": text, "facts": facts, "concepts": concepts, "organs": organs, "severity": sev}


def observations(events: Iterable[dict], labs: Iterable[dict] = (), conditions: Iterable[dict] = (),
                 *, today: date, window_days: int) -> list[dict]:
    """Normalise every row into flat observations {kind, id, date, label, value, unit, source, ...} inside the window.

    Labs and conditions keep their full history (a thyroid test from last year still matters); everything else is
    limited to the window. Duplicates (the same thing saved by the tracker and mirrored for analytics) are dropped.
    """
    since = today - timedelta(days=window_days - 1)
    out: list[dict] = []
    pending_bp: dict[tuple, dict] = {}
    for row in events or ():
        if not isinstance(row, dict) or not counts_as_observation(row):
            continue
        moment = event_moment(row)
        if moment is None:
            continue
        d = moment.date()
        kind = str(row.get("event_type") or "").lower()
        data = clean_data(row.get("extracted_data") if isinstance(row.get("extracted_data"), dict) else {})
        prov = provenance(row)
        base = {"id": str(row.get("id")) if row.get("id") is not None else None, "date": d,
                "source": "cycle log" if prov.get("feature") == "cycle_day" else _SOURCES.get(prov.get("source"), prov.get("source") or "record")}
        if kind == "lab_result":
            name = str(data.get("test_name") or data.get("name") or "").strip()
            if name:
                out.append({**base, "kind": "lab", "label": name, "value": _num(data.get("value")) if _num(data.get("value")) is not None else data.get("value"),
                            "unit": data.get("unit"), "ref": (_num(data.get("reference_min")), _num(data.get("reference_max")))})
            continue
        if kind == "medical_condition":
            name = str(data.get("condition_name") or data.get("name") or "").strip()
            if name:
                out.append({**base, "kind": "condition", "label": name, "value": data.get("status"), "unit": None})
            continue
        if not since <= d <= today:
            continue
        name = str(data.get("name") or "").strip().lower()
        if kind == "vital_sign":
            sys_bp, dia_bp = _num(data.get("systolic_bp"), data.get("systolic")), _num(data.get("diastolic_bp"), data.get("diastolic"))
            if name in ("systolic", "diastolic") and sys_bp is None and dia_bp is None:  # chat saves the two halves apart
                slot = pending_bp.setdefault((prov.get("message_id") or base["id"], d), {**base, "kind": "bp", "sys": None, "dia": None})
                slot["sys" if name == "systolic" else "dia"] = _num(data.get("value"))
            elif sys_bp is not None or dia_bp is not None:
                out.append({**base, "kind": "bp", "sys": sys_bp, "dia": dia_bp})
            hr = _num(data.get("heart_rate_bpm"), data.get("heart_rate"), data.get("value") if name == "heart rate" else None)
            if hr is not None:
                out.append({**base, "kind": "hr", "label": "Heart rate", "value": hr, "unit": "bpm"})
            spo2 = _num(data.get("spo2_percent"), data.get("value") if name == "spo2" else None)
            if spo2 is not None:
                out.append({**base, "kind": "spo2", "label": "Oxygen level", "value": spo2, "unit": "%"})
        elif kind == "sleep":
            minutes = _num(data.get("duration_minutes"))
            hours = _num(data.get("hours"), data.get("duration_hours"), minutes / 60 if minutes is not None else None)
            if hours is not None and 0 < hours <= 24:
                out.append({**base, "kind": "sleep", "label": "Sleep", "value": round(hours, 1), "unit": "hours"})
        elif kind == "mood":
            score = _num(data.get("mood_score"), data.get("score"))
            if score is not None and 0 <= score <= 10:
                out.append({**base, "kind": "mood", "label": "Mood", "value": score, "unit": "/10"})
            for extra, label in (("stress_score", "Stress"), ("anxiety_score", "Anxiety")):   # the same check-in can carry these
                v = _num(data.get(extra))
                if v is not None and 0 <= v <= 10:
                    out.append({**base, "kind": extra.split("_")[0], "label": label, "value": v, "unit": "/10"})
        elif kind == "stress":
            score = _num(data.get("score"), data.get("severity"))
            if score is not None and 0 <= score <= 10:
                out.append({**base, "kind": "stress", "label": "Stress", "value": score, "unit": "/10"})
            elif data.get("level"):
                out.append({**base, "kind": "stress_word", "label": "Stress", "value": str(data["level"]), "unit": None})
        elif kind in ("activity", "exercise"):
            minutes = _num(data.get("duration_minutes"), data.get("minutes"))
            label = str(data.get("activity") or data.get("name") or "Activity").strip().capitalize()
            if minutes is not None and 0 < minutes <= 1440:
                out.append({**base, "kind": "activity", "label": label, "value": minutes, "unit": "min"})
            elif _num(data.get("steps")) is not None:
                out.append({**base, "kind": "steps", "label": "Steps", "value": _num(data.get("steps")), "unit": "steps"})
        elif kind in ("food", "nutrition", "lifestyle", "hydration"):
            text = _text_of(data)
            if kind == "hydration":
                ml = _num(data.get("amount_ml"), data.get("water_ml"))
                if ml is not None and 0 < ml <= K.HYDRATION_SINGLE_LOG_MAX_ML:
                    out.append({**base, "kind": "water", "label": "Water", "value": ml, "unit": "ml"})
            elif kind != "lifestyle" and text:
                out.append({**base, "kind": "food", "label": text[:80], "value": None, "unit": None})
            if _ALCOHOL.search(text):
                out.append({**base, "kind": "alcohol", "label": text[:80] or "A drink", "value": None, "unit": None})
            elif kind != "hydration" and _is_sugary(data):
                out.append({**base, "kind": "sugary", "label": text[:80], "value": None, "unit": None})
        elif kind == "eye_check":
            hours = _num(data.get("screen_hours"))
            if hours is not None and 0 <= hours <= 18:
                out.append({**base, "kind": "screen", "label": "Screen time", "value": hours, "unit": "hours"})
            comfort = _num(data.get("eye_comfort"))
            if comfort is not None and 1 <= comfort <= 5:
                out.append({**base, "kind": "eye_comfort", "label": "Eye comfort", "value": comfort, "unit": "/5"})
            for chip in str(data.get("eye_symptoms") or "").split(","):
                word = EYE_CHIPS.get(chip.strip().lower())
                if word:
                    out.append({**_symptom_obs(base, word, None, None), "organs": {"eyes"}})
            exam = _day(data.get("last_exam"))
            if exam:
                out.append({**base, "date": exam, "kind": "eye_exam", "label": "Eye exam", "value": None, "unit": None})
        elif kind in ("symptom", "menstrual_symptom"):
            if kind == "menstrual_symptom" and (name in _CYCLE_NAMES or data.get("symptom") == "menstrual flow"):
                flow = data.get("flow")
                out.append({**base, "kind": "cycle", "label": "Period" if (flow or name == "period" or data.get("phase") == "period") else "Cycle",
                            "value": flow or data.get("phase"), "unit": None})
                ticked = [label.strip().lower() for label in data.get("symptoms") or [] if isinstance(label, str) and label.strip()]
                for label in ticked:  # symptoms ticked on a cycle day log
                    out.append(_symptom_obs(base, label, None, None))
                if not ticked and _num(data.get("severity")):  # a pain score alone (the mirror drops pain types) is still period pain
                    pain = _symptom_obs(base, "period pain", data.get("severity"), None)
                    pain["organs"] = pain["organs"] | {"uterus_ovaries"}
                    out.append(pain)
                continue
            label = str(data.get("symptom") or data.get("name") or "").strip()
            if label:
                out.append(_symptom_obs(base, label.lower(), data.get("severity"), data.get("details")))
    for slot in pending_bp.values():
        if slot["sys"] is not None or slot["dia"] is not None:
            out.append(slot)
    for bp in (o for o in out if o["kind"] == "bp"):
        bp.update(label="Blood pressure", unit="mmHg",
                  value=f"{_g(bp['sys']) if bp['sys'] is not None else '?'}/{_g(bp['dia']) if bp['dia'] is not None else '?'}")

    for row in labs or ():
        d = _day(row.get("date"))
        name = str(row.get("test_name") or "").strip()
        if d and name:
            ref = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)\s*-\s*(-?\d+(?:\.\d+)?)\s*", str(row.get("reference_range") or ""))
            out.append({"id": str(row.get("id")), "date": d, "source": "tracker", "kind": "lab", "label": name,
                        "value": _num(row.get("value")) if _num(row.get("value")) is not None else row.get("value"), "unit": row.get("unit"),
                        "ref": (float(ref[1]), float(ref[2])) if ref else (None, None)})
    for row in conditions or ():
        name = str(row.get("condition_name") or "").strip()
        if name:
            out.append({"id": str(row.get("id")), "date": _day(row.get("date")) or today, "source": "tracker", "kind": "condition",
                        "label": name, "value": row.get("status"), "unit": None})

    seen: set[tuple] = set()
    unique = []
    for o in sorted(out, key=lambda o: (o["source"] != "tracker", o["date"]), reverse=False):
        # A condition is a standing fact: its tracker row and the analytics mirror carry different dates, so the date is not part of its key.
        key = (o["kind"], str(o.get("label")).lower(), None if o["kind"] == "condition" else o["date"], str(o.get("value")))
        if key not in seen:
            seen.add(key)
            unique.append(o)
    return sorted(unique, key=lambda o: o["date"], reverse=True)


# --------------------------------------------------------------------------------------------------
# shared organ machinery
# --------------------------------------------------------------------------------------------------

class _Organ:
    """Collects evidence, reasons and the status for one organ while its rules run."""

    def __init__(self, organ_id: str, window_days: int, today: date):
        self.id, self.window, self.today = organ_id, window_days, today
        self.status = "no_data"
        self.evidence: list[dict] = []
        self.flagged: list[dict] = []
        self.reasons: list[str] = []
        self.notes: list[str] = []
        self.missing: list[str] = []
        self.kinds: set[str] = set()
        self.safety: dict | None = None
        self.next_step = ""

    def add(self, kind: str, items: Iterable[dict]) -> None:
        items = list(items)
        if items:
            self.kinds.add(kind)
            self.evidence += items
            self.status = _raise(self.status, "steady")

    def need(self, present: bool, what: str) -> None:
        if not present:
            self.missing.append(what)

    def flag(self, status: str, reason: str, items: Iterable[dict] = ()) -> None:
        self.status = _raise(self.status, status)
        self.reasons.append(reason)
        self.flagged += [i for i in items if i not in self.flagged]


def _confidence(org: _Organ) -> dict:
    n = len(org.evidence)
    start = (org.today - timedelta(days=org.window - 1)).isoformat()
    # Labs and conditions count from any date, so only an all-recent set can be described as "the last N days".
    window = f"the last {org.window} days" if all(e["date"] >= start for e in org.evidence) else "your records"
    if n == 0:
        return {"level": "low", "reason": f"Nothing logged in {window} touches this area."}
    span = f"{_plural(n, 'entry', 'entries')} from {_plural(len(org.kinds), 'kind')} of data"
    if org.safety:
        return {"level": "high", "reason": f"A recent entry needs attention whatever else the data says ({span})."}
    if n >= K.ORGAN_CONFIDENCE_HIGH_ENTRIES and len(org.kinds) >= 2:
        return {"level": "high", "reason": f"Based on {span} in {window}."}
    if n >= K.ORGAN_CONFIDENCE_MEDIUM_ENTRIES:
        reason = f"Based on {span} in {window}."
        if len(org.kinds) < 2:
            reason += " More than one kind of data would make it firmer."
        return {"level": "medium", "reason": reason}
    return {"level": "low", "reason": f"Only {span} in {window}, so this is a first impression."}


def _red_flags(org: _Organ, symptoms: list[dict]) -> None:
    """Recent symptoms re-checked by the safety engine. URGENT / EMERGENCY makes the organ talk_to_doctor, safety first."""
    lookback = org.today - timedelta(days=K.ORGAN_RED_FLAG_LOOKBACK_DAYS - 1)
    worst: tuple[int, dict, Any] | None = None
    for o in symptoms:
        if o["date"] < lookback:
            continue
        a = assess_safety(o["text"], facts=o["facts"])
        rank = {"EMERGENCY": 3, "URGENT": 2, "POTENTIAL_REDFLAG_NEEDS_CLARIFICATION": 1}.get(a.state, 0)
        if rank >= 2:
            org.flag("talk_to_doctor", f"You logged {o['label'].lower()} on {_fmt(o['date'])}, which can be serious.", [_item(o)])
            if worst is None or rank > worst[0] or (rank == worst[0] and o["date"] > worst[1]["date"]):
                worst = (rank, o, a)
        elif rank == 1:
            org.flag("worth_watching", f"You logged {o['label'].lower()} on {_fmt(o['date'])}. It is worth keeping an eye on how it goes.", [_item(o)])
    if worst:
        rank, o, a = worst
        what, when = o["label"].lower(), _fmt(o["date"])
        if a.crisis:
            message = (f"On {when} you logged {what}. If you might act on these thoughts or feel unsafe, please call your local "
                       "emergency number now (112 in India). Tele-MANAS on 14416 is free and open day and night in India; "
                       "elsewhere, findahelpline.com lists free local lines. You don't have to handle this alone.")
        elif rank == 3:
            message = (f"On {when} you logged {what}. If it is happening now or feels severe, call your local emergency number "
                       "or go to the nearest emergency department. If it has passed, please still talk to a doctor soon about it.")
        else:
            message = (f"On {when} you logged {what}. This deserves prompt attention: please speak to a doctor or an urgent-care "
                       "service today. If it gets worse, go to emergency care.")
        org.safety = {"state": a.state, "level": a.level, "message": message}


def _unflagged(org: _Organ, items: list[dict]) -> list[dict]:
    """Items no earlier rule (usually the red-flag check) already counted."""
    done = {(f["id"], f["date"]) for f in org.flagged}
    return [o for o in items if (o.get("id"), o["date"].isoformat()) not in done]


def _names(items: list[dict]) -> str:
    return ", ".join(dict.fromkeys(o["label"].lower() for o in items))


def _symptoms_for(obs: list[dict], organ: str) -> list[dict]:
    return [o for o in obs if o["kind"] == "symptom" and organ in o["organs"]]


def _days(items: Iterable[dict]) -> int:
    return len({o["date"] for o in items})


def _week_rate(items: list[dict], window: int) -> float:
    return _days(items) * 7 / window


# --------------------------------------------------------------------------------------------------
# organ rules
# --------------------------------------------------------------------------------------------------

def _heart(org: _Organ, obs: list[dict]) -> None:
    bps = [o for o in obs if o["kind"] == "bp"]
    hrs = [o for o in obs if o["kind"] == "hr"]
    acts = [o for o in obs if o["kind"] == "activity"]
    symptoms = _symptoms_for(obs, "heart")
    org.add("blood pressure", map(_item, bps))
    org.add("heart rate", map(_item, hrs))
    org.add("symptoms", map(_item, symptoms))
    org.add("activity", map(_item, acts))
    org.need(bool(bps), "Blood pressure readings (a home cuff, sitting and rested)")
    org.need(bool(hrs), "Resting heart rate")
    org.need(bool(acts), "Activity or workouts")
    _red_flags(org, symptoms)

    (hs, hd), (vs, vd) = K.BP_HIGH_MMHG, K.BP_VERY_HIGH_MMHG
    very = [o for o in bps if (o["sys"] or 0) >= vs or (o["dia"] or 0) >= vd]
    high = [o for o in bps if (o["sys"] or 0) >= hs or (o["dia"] or 0) >= hd]
    low = [o for o in bps if o["sys"] is not None and o["sys"] < K.BP_LOW_SYSTOLIC_MMHG]
    if very:
        o = very[0]
        org.flag("talk_to_doctor", f"Your reading of {o['value']} on {_fmt(o['date'])} is at or above {vs}/{vd}. A reading this high "
                 "should be checked by a doctor soon, and straight away if you also have chest pain, breathlessness, a bad headache or weakness.", map(_item, very))
    if len(high) >= K.BP_HIGH_READINGS_TALK:
        org.flag("talk_to_doctor", f"{len(high)} of your {_plural(len(bps), 'reading')} were {hs}/{hd} or higher. Repeated high readings are worth showing a doctor.", map(_item, high))
    elif high and not very:
        org.flag("worth_watching", f"{len(high)} of your {_plural(len(bps), 'reading')} {'was' if len(high) == 1 else 'were'} {hs}/{hd} or higher. "
                 "One-off highs are common (coffee, stress, a rushed reading), so a few calm repeat readings will tell more.", map(_item, high))
    if low:
        org.flag("worth_watching", f"{_plural(len(low), 'reading')} had a top number below {K.BP_LOW_SYSTOLIC_MMHG}. That matters most if you felt dizzy or faint.", map(_item, low))
    if bps and not (very or high or low):
        org.reasons.append(f"All {_plural(len(bps), 'blood pressure reading')} sat below {hs}/{hd}.")

    if hrs:
        mid = median(o["value"] for o in hrs)
        (sl, sh), (tl, th) = K.HEART_RATE_STEADY_BPM, K.HEART_RATE_TALK_BPM
        if not tl <= mid <= th:
            org.flag("talk_to_doctor", f"Your heart rate readings centre on {_g(mid)} bpm, outside {tl} to {th}. That is worth checking with a doctor.", map(_item, hrs))
        elif not sl <= mid <= sh:
            org.flag("worth_watching", f"Your heart rate readings centre on {_g(mid)} bpm, outside the usual resting {sl} to {sh}. "
                     "Very fit people can sit lower; how you feel matters too.", map(_item, hrs))
        else:
            odd = [o for o in hrs if not tl <= o["value"] <= th]
            if odd:
                org.flag("worth_watching", f"{_plural(len(odd), 'heart rate reading')} fell outside {tl} to {th} bpm. If that was at rest, it is worth noting.", map(_item, odd))
            else:
                org.reasons.append(f"Your heart rate readings centre on {_g(mid)} bpm, inside the usual resting {sl} to {sh}.")
    calm = _unflagged(org, symptoms)
    if calm:
        org.flag("worth_watching", f"You logged {_names(calm)} on {_plural(_days(calm), 'day')}.", map(_item, calm))
    if acts:
        org.notes.append(f"{_g(sum(o['value'] for o in acts))} minutes of activity logged; about {K.WHO_MODERATE_MIN_PER_WEEK[0]} a week is the usual goal.")
        if not (bps or hrs or symptoms):
            org.reasons.append("Only activity was logged. It helps your heart, but says little about how it is doing.")
    org.next_step = {
        "talk_to_doctor": "Book a check with your doctor and take these readings with you.",
        "worth_watching": "Take two calm readings, morning and evening, for the next week. Sit quietly for five minutes first.",
        "steady": "Keep logging a reading now and then; a week of morning readings makes this clearer." if bps else "If you have a blood pressure cuff, a few rested readings would tell much more.",
        "no_data": "Log a blood pressure or resting heart rate reading to start this area.",
    }[org.status]


def _lungs(org: _Organ, obs: list[dict]) -> None:
    spo2 = [o for o in obs if o["kind"] == "spo2"]
    acts = [o for o in obs if o["kind"] == "activity"]
    symptoms = _symptoms_for(obs, "lungs")
    org.add("oxygen level", map(_item, spo2))
    org.add("symptoms", map(_item, symptoms))
    org.add("activity", map(_item, acts))
    org.need(bool(symptoms), "Breathing symptoms such as cough or wheeze, if you have any")
    org.need(bool(spo2), "Oxygen level from a finger monitor, if you have one")
    org.need(bool(acts), "Activity, and how your breathing feels during it")
    _red_flags(org, symptoms)
    if spo2:
        lowest = min(spo2, key=lambda o: o["value"])
        if lowest["value"] <= K.SPO2_TALK_BELOW_PCT:
            org.flag("talk_to_doctor", f"An oxygen reading of {_g(lowest['value'])}% on {_fmt(lowest['date'])} is {K.SPO2_TALK_BELOW_PCT}% or lower. "
                     "Please get medical advice promptly, and urgently if you are breathless.", [_item(lowest)])
        elif lowest["value"] < K.SPO2_WATCH_BELOW_PCT:
            org.flag("worth_watching", f"Your lowest oxygen reading was {_g(lowest['value'])}%, a little under {K.SPO2_WATCH_BELOW_PCT}%. Check the finger is warm and still, then re-measure.", [_item(lowest)])
        else:
            org.reasons.append(f"Your oxygen readings stayed at {K.SPO2_WATCH_BELOW_PCT}% or above.")
    calm = _unflagged(org, symptoms)
    if calm:
        org.flag("worth_watching", f"You logged breathing symptoms on {_plural(_days(calm), 'day')}.", map(_item, calm))
    cough = sorted((o for o in symptoms if "cough" in o["concepts"]), key=lambda o: o["date"])
    if cough and (cough[-1]["date"] - cough[0]["date"]).days + 1 >= K.COUGH_TALK_SPAN_DAYS:
        org.flag("talk_to_doctor", f"A cough has come up from {_fmt(cough[0]['date'])} to {_fmt(cough[-1]['date'])}, three weeks or more. "
                 "A cough that lasts that long is worth showing a doctor.", map(_item, cough))
    if acts and not (spo2 or symptoms):
        org.reasons.append("Only activity was logged, with no breathing symptoms noted alongside it.")
    org.next_step = {
        "talk_to_doctor": "Please talk to a doctor about your breathing, and take this list with you.",
        "worth_watching": "Note when the symptom shows up (time, activity, weather) so the pattern is easier to see.",
        "steady": "Keep moving in ways you enjoy, and note anything that leaves you unusually short of breath.",
        "no_data": "Mention any cough or breathlessness in chat, or log a walk, to start this area.",
    }[org.status]


def _brain(org: _Organ, obs: list[dict]) -> None:
    sleep = [o for o in obs if o["kind"] == "sleep"]
    mood = [o for o in obs if o["kind"] == "mood"]
    stress = [o for o in obs if o["kind"] in ("stress", "stress_word")]
    anxiety = [o for o in obs if o["kind"] == "anxiety"]
    symptoms = _symptoms_for(obs, "brain")
    for kind, items in (("sleep", sleep), ("mood", mood), ("stress", stress), ("anxiety", anxiety), ("symptoms", symptoms)):
        org.add(kind, map(_item, items))
    org.need(bool(sleep), "Sleep: how long and how well")
    org.need(bool(mood), "Mood check-ins (0 to 10)")
    org.need(bool(stress), "Stress levels")
    _red_flags(org, symptoms)
    least = K.ORGAN_MIN_ENTRIES_FOR_AVERAGE
    if len(sleep) >= least:
        avg = mean(o["value"] for o in sleep)
        if avg < K.SLEEP_HOURS_ADULT[0]:
            org.flag("worth_watching", f"You averaged {_g(round(avg, 1))} hours of sleep over {_plural(len(sleep), 'night')}, under the {_g(K.SLEEP_HOURS_ADULT[0])} to {_g(K.SLEEP_HOURS_ADULT[1])} most adults need.", map(_item, sleep))
        else:
            org.reasons.append(f"You averaged {_g(round(avg, 1))} hours of sleep over {_plural(len(sleep), 'night')}.")
    numbers = [o for o in mood if isinstance(o["value"], (int, float))]
    low_days = [o for o in numbers if o["value"] <= K.MOOD_LOW_DAY_SCORE]
    if _days(low_days) >= K.MOOD_LOW_DAYS_TALK:
        org.flag("talk_to_doctor", f"Your mood was {K.MOOD_LOW_DAY_SCORE}/10 or lower on {_days(low_days)} days. Feeling low most days for two weeks or more "
                 "is worth talking through with a doctor; it is common and help works.", map(_item, low_days))
    elif len(numbers) >= least and mean(o["value"] for o in numbers) <= K.MOOD_LOW_AVERAGE:
        org.flag("worth_watching", f"Your mood averaged {_g(round(mean(o['value'] for o in numbers), 1))}/10 across {_plural(len(numbers), 'check-in')}.", map(_item, numbers))
    elif len(numbers) >= least:
        org.reasons.append(f"Your mood averaged {_g(round(mean(o['value'] for o in numbers), 1))}/10 across {_plural(len(numbers), 'check-in')}.")
    scored = [o for o in stress if o["kind"] == "stress"]
    if len(scored) >= least and mean(o["value"] for o in scored) >= K.STRESS_HIGH_AVERAGE:
        org.flag("worth_watching", f"Your stress averaged {_g(round(mean(o['value'] for o in scored), 1))}/10 across {_plural(len(scored), 'entry', 'entries')}.", map(_item, scored))
    if len(anxiety) >= least and mean(o["value"] for o in anxiety) >= K.STRESS_HIGH_AVERAGE:
        org.flag("worth_watching", f"Your anxiety scores averaged {_g(round(mean(o['value'] for o in anxiety), 1))}/10 across {_plural(len(anxiety), 'check-in')}. "
                 "If it keeps feeling like a lot, talking to someone can help.", map(_item, anxiety))
    headaches = [o for o in symptoms if "headache" in o["concepts"] or "migraine" in o["text"].lower()]
    if _days(headaches) >= K.HEADACHE_DAYS_TALK:
        org.flag("talk_to_doctor", f"You logged headaches on {_days(headaches)} days. Headaches that often are worth a doctor's view.", map(_item, headaches))
    elif _days(headaches) >= K.HEADACHE_DAYS_WATCH:
        org.flag("worth_watching", f"You logged headaches on {_days(headaches)} days.", map(_item, headaches))
    others = [o for o in _unflagged(org, symptoms) if o not in headaches]
    if others:
        org.flag("worth_watching", f"You logged {_names(others)}.", map(_item, others))
    org.next_step = {
        "talk_to_doctor": "Please talk to a doctor; these entries are a good place to start the conversation.",
        "worth_watching": "Pick one small thing for this week: a steady bedtime, a short walk, or a few minutes to unwind.",
        "steady": "Keep checking in; a line about sleep and mood each day shows patterns quickly.",
        "no_data": "Log last night's sleep or how you feel today to start this area.",
    }[org.status]


def _eyes(org: _Organ, obs: list[dict]) -> None:
    """Screen time, eye comfort and eye symptoms from the Eyes tracker and from chat. A recorded eye exam is never read as healthy eyes."""
    recent = org.today - timedelta(days=K.ORGAN_EYE_WINDOW_DAYS - 1)
    screen = [o for o in obs if o["kind"] == "screen"]
    comfort = [o for o in obs if o["kind"] == "eye_comfort"]
    symptoms = _symptoms_for(obs, "eyes")
    for kind, items in (("screen time", screen), ("comfort", comfort), ("symptoms", symptoms)):
        org.add(kind, map(_item, items))
    org.need(bool(screen), "Screen time per day")
    org.need(bool(comfort) or bool(symptoms), "How your eyes feel (comfort 1 to 5, or any symptoms)")
    _red_flags(org, symptoms)
    by_day: dict[date, dict] = {}
    for o in screen:
        if o["date"] >= recent and (o["date"] not in by_day or o["value"] > by_day[o["date"]]["value"]):
            by_day[o["date"]] = o  # one value a day: the longest logged
    if len(by_day) >= K.ORGAN_EYE_MIN_SCREEN_DAYS:
        avg = mean(o["value"] for o in by_day.values())
        if avg >= K.ORGAN_EYE_SCREEN_HOURS_WATCH:
            org.flag("worth_watching", f"Your screen time averaged {_g(round(avg, 1))} hours a day over {_plural(len(by_day), 'day')}.", map(_item, by_day.values()))
        else:
            org.reasons.append(f"Your screen time averaged {_g(round(avg, 1))} hours a day over {_plural(len(by_day), 'day')}.")
    sore = [o for o in comfort if o["value"] <= K.ORGAN_EYE_COMFORT_LOW]
    bothered = [o for o in symptoms + sore if o["date"] >= recent]
    if _days(bothered) >= K.ORGAN_EYE_SYMPTOM_DAYS_WATCH:
        org.flag("worth_watching", f"Your eyes bothered you on {_days(bothered)} of the last {K.ORGAN_EYE_WINDOW_DAYS} days.", map(_item, bothered))
    others = [o for o in _unflagged(org, symptoms) if o["date"] >= recent]
    if others and org.status == "steady":
        org.reasons.append(f"You logged {_names(others)}.")
    exam = max((o["date"] for o in obs if o["kind"] == "eye_exam"), default=None)
    if exam:
        org.notes.append(f"You recorded an eye exam on {_fmt(exam)}. A visit date says when you were checked, not how your eyes are now.")
    org.next_step = {
        "talk_to_doctor": "Please see a doctor or an eye clinic soon. Bring these entries.",
        "worth_watching": "Short breaks help tired eyes: look at something about 6 metres away for 20 seconds every 20 minutes. If it keeps coming back, an eye check is worth it.",
        "steady": "Keep logging screen time and how your eyes feel; Bubbles will tell you if something shifts.",
        "no_data": "Log screen time or how your eyes feel in Track > Eyes to start this area.",
    }[org.status]


def _gut(org: _Organ, obs: list[dict]) -> None:
    food = [o for o in obs if o["kind"] == "food"]
    symptoms = _symptoms_for(obs, "stomach_intestines")
    org.add("food", map(_item, food))
    org.add("symptoms", map(_item, symptoms))
    org.need(bool(food), "Meals: what you ate and when")
    org.need(bool(symptoms), "Digestion: bloating, acidity, loose motions or constipation, if any")
    _red_flags(org, symptoms)
    days = _days(symptoms)
    if days >= K.DIGESTIVE_DAYS_TALK:
        org.flag("talk_to_doctor", f"Digestive symptoms came up on {days} days. Ongoing tummy trouble is worth a doctor's view.", map(_item, symptoms))
    elif days >= K.DIGESTIVE_DAYS_WATCH:
        org.flag("worth_watching", f"Digestive symptoms came up on {days} days.", map(_item, symptoms))
    elif symptoms:
        org.reasons.append(f"Digestive symptoms came up on {_plural(days, 'day')}, below the {K.DIGESTIVE_DAYS_WATCH} days that would make this worth watching.")
    if food:
        org.reasons.append(f"{_plural(len(food), 'meal')} logged.")
    org.next_step = {
        "talk_to_doctor": "Please see a doctor about these symptoms, sooner if there is blood, black stools or weight loss.",
        "worth_watching": "Note what you ate a few hours before each episode; patterns often show within two weeks.",
        "steady": "Keep logging meals and any tummy trouble side by side.",
        "no_data": "Log a meal or mention any tummy trouble in chat to start this area.",
    }[org.status]


def _liver(org: _Organ, obs: list[dict]) -> None:
    food = [o for o in obs if o["kind"] == "food"]
    alcohol = [o for o in obs if o["kind"] == "alcohol"]
    sugary = [o for o in obs if o["kind"] == "sugary"]
    org.add("alcohol", map(_item, alcohol))
    org.add("sugary food", map(_item, sugary))
    if food and not (alcohol or sugary):
        org.add("food", map(_item, food[:3]))
        org.reasons.append("Your logged meals show no alcohol or sweet pattern. Meals alone say little about these organs.")
    org.need(bool(food), "Meals and drinks, including alcohol and sweets")
    rate = _week_rate(alcohol, org.window)
    if alcohol and rate >= K.ALCOHOL_DAYS_PER_WEEK_WATCH:
        org.flag("worth_watching", f"Alcohol came up on about {_g(round(rate, 1))} days a week. Having several drink-free days each week is kinder to your liver.", map(_item, alcohol))
    elif alcohol:
        org.reasons.append(f"Alcohol came up on {_plural(_days(alcohol), 'day')}.")
    srate = _week_rate(sugary, org.window)
    if sugary and srate >= K.SUGARY_DAYS_PER_WEEK_WATCH:
        org.flag("worth_watching", f"Sweets or sugary drinks came up on about {_g(round(srate, 1))} days a week.", map(_item, sugary))
    elif sugary:
        org.reasons.append(f"Sweets or sugary drinks came up on {_plural(_days(sugary), 'day')}.")
    org.next_step = {
        "talk_to_doctor": "Please talk to a doctor.",
        "worth_watching": "Try swapping one drink or sweet a week for something you enjoy just as much.",
        "steady": "Keep logging meals and drinks honestly; that is what keeps this view useful.",
        "no_data": "Log your meals and drinks for a few days to start this area.",
    }[org.status]


def _kidneys(org: _Organ, obs: list[dict]) -> None:
    water = [o for o in obs if o["kind"] == "water"]
    symptoms = _symptoms_for(obs, "kidneys_bladder")
    conditions = [o for o in obs if o["kind"] == "condition"]
    restricted = [o for o in conditions if any(w in o["label"].lower() for w in K.FLUID_RESTRICTION_CONDITIONS)]
    org.add("water", map(_item, water))
    org.add("symptoms", map(_item, symptoms))
    org.need(bool(water), "Water and other drinks through the day")
    org.need(bool(symptoms), "Peeing changes such as burning or going much more often, if any")
    _red_flags(org, symptoms)
    blood = [o for o in symptoms if URINARY_TALK.search(o["text"])]
    if blood:
        org.flag("talk_to_doctor", f"You logged blood in your urine on {_fmt(blood[0]['date'])}. That should always be checked by a doctor, even if it stopped.", map(_item, blood))
    calm = [o for o in _unflagged(org, symptoms) if o not in blood]
    if calm:
        org.flag("worth_watching", f"You logged {_names(calm)}. If it burns, smells strong or comes with fever, see a doctor.", map(_item, calm))
    if water:
        by_day: dict[date, float] = {}
        for o in water:
            by_day[o["date"]] = by_day.get(o["date"], 0) + o["value"]
        avg = mean(by_day.values())
        if restricted:
            org.reasons.append(f"You drank about {_g(round(avg))} ml on the days you logged water.")
        elif avg < K.WATER_LOW_ML_PER_DAY and len(by_day) >= K.ORGAN_MIN_ENTRIES_FOR_AVERAGE:
            org.flag("worth_watching", f"You drank about {_g(round(avg))} ml a day on the {_plural(len(by_day), 'day')} you logged, under {_g(K.WATER_LOW_ML_PER_DAY)} ml.", map(_item, water))
        else:
            org.reasons.append(f"You drank about {_g(round(avg))} ml a day on the {_plural(len(by_day), 'day')} you logged.")
    if restricted:
        org.notes.append(f"You have noted {restricted[0]['label']}, so follow your care team's advice on fluids rather than general water goals.")
    org.next_step = {
        "talk_to_doctor": "Please see a doctor about this soon.",
        "worth_watching": "Follow your care team's fluid advice, and note any changes when you pee." if restricted else "Keep a glass of water nearby and log it; small sips through the day add up.",
        "steady": "Keep logging drinks; a week of entries makes this clearer.",
        "no_data": "Log your water for a day to start this area.",
    }[org.status]


def _thyroid(org: _Organ, obs: list[dict]) -> None:
    conditions = [o for o in obs if o["kind"] == "condition" and THYROID_WORDS.search(o["label"])]
    tsh = sorted((o for o in obs if o["kind"] == "lab" and TSH_WORDS.search(o["label"])), key=lambda o: o["date"], reverse=True)
    org.add("conditions", map(_item, conditions))
    org.add("TSH", map(_item, tsh))
    org.need(bool(tsh), "A TSH blood test result with its date")
    if conditions:
        org.flag("worth_watching", f"You have noted {conditions[0]['label']}. Regular check-ups and taking medicine as agreed with your doctor matter most here.", map(_item, conditions))
    if tsh:
        latest = tsh[0]
        value = latest["value"] if isinstance(latest["value"], (int, float)) else None
        lo, hi = latest.get("ref") or (None, None)
        lo, hi = (lo, hi) if lo is not None and hi is not None else K.TSH_RANGE_MIU_L
        tlo, thi = K.TSH_TALK_MIU_L
        when = _fmt(latest["date"])
        if value is None:
            org.reasons.append(f"Your TSH result from {when} has no number Bubbles can read.")
        elif not tlo <= value <= thi:
            org.flag("talk_to_doctor", f"Your TSH of {_g(value)} on {when} is well outside the usual range. Please go over it with a doctor.", [_item(latest)])
        elif not lo <= value <= hi:
            org.flag("worth_watching", f"Your TSH of {_g(value)} on {when} is outside the range of {_g(lo)} to {_g(hi)}. A doctor may want to repeat it.", [_item(latest)])
        else:
            org.reasons.append(f"Your TSH of {_g(value)} on {when} is inside the range of {_g(lo)} to {_g(hi)}.")
        if (org.today - latest["date"]).days > K.ORGAN_LAB_STALE_DAYS:
            org.notes.append(f"Your latest TSH is from {latest['date'].isoformat()}, more than a year ago.")
    org.next_step = {
        "talk_to_doctor": "Please book a review with your doctor and bring this result.",
        "worth_watching": "Keep your thyroid check-ups on the calendar and log new results when they come.",
        "steady": "Log your next thyroid result when you have one.",
        "no_data": "If you have had a thyroid blood test (TSH), add it under Labs to start this area.",
    }[org.status]


def _uterus(org: _Organ, obs: list[dict], cycle: dict | None) -> None:
    cycle_obs = [o for o in obs if o["kind"] == "cycle"]
    symptoms = _symptoms_for(obs, "uterus_ovaries")
    pcos = [o for o in obs if o["kind"] == "condition" and PCOS_WORDS.search(o["label"])]
    org.add("cycle", map(_item, cycle_obs))
    org.add("symptoms", map(_item, symptoms))
    org.add("conditions", map(_item, pcos))
    cycle = cycle or {}
    if cycle.get("phase"):  # a prediction from past period starts, not an entry: a note, never evidence or "last entry"
        day = f", day {cycle['cycle_day']}" if cycle.get("cycle_day") else ""
        org.notes.append(f"Cycle predicts you are in the {cycle['phase']} phase{day}. That is an estimate from the period starts you marked, not an entry.")
    org.need(bool(cycle_obs or cycle.get("phase")), "Period start dates")
    org.need(bool(symptoms), "Cramps, pain or flow on period days")
    _red_flags(org, symptoms)
    flags = [f for f in cycle.get("flags") or [] if isinstance(f, dict)]
    urgent = [f for f in flags if f.get("severity") == "urgent"]
    if urgent:  # cycle_flags' own urgent copy (heavy bleeding), unless a logged symptom already reads as an emergency
        org.flag("talk_to_doctor", urgent[0].get("title") or "A cycle entry needs urgent advice.")
        if not org.safety or org.safety["state"] != "EMERGENCY":
            org.safety = {"state": "URGENT", "level": "AMBER", "message": urgent[0].get("message")}
    for f in flags:
        if f.get("severity") == "talk":
            org.flag("worth_watching", f.get("message") or f.get("title"))
        elif f.get("severity") == "info" and f.get("message"):
            org.notes.append(f["message"])
    if pcos:
        org.flag("worth_watching", f"You have noted {pcos[0]['label']}. Steady routines and regular check-ins with your doctor help most.", map(_item, pcos))
    if symptoms and org.status in ("no_data", "steady"):
        org.reasons.append(f"You logged {_names(symptoms)}, which is common around a period.")
    org.next_step = {
        "talk_to_doctor": "Please contact a doctor today; the details above will help them.",
        "worth_watching": "Keep logging period days and pain; two or three cycles of notes make a doctor's visit much more useful.",
        "steady": "Keep marking period starts; predictions get sharper with each cycle.",
        "no_data": ("Log period days, flow or pain in Cycle to fill this area in." if cycle.get("phase")
                    else "Mark the first day of your last period in Cycle to start this area."),
    }[org.status]


def _skeleton(org: _Organ, obs: list[dict]) -> None:
    acts = [o for o in obs if o["kind"] == "activity"]
    symptoms = _symptoms_for(obs, "skeleton_muscles")
    org.add("workouts", map(_item, acts))
    org.add("pain", map(_item, symptoms))
    org.need(bool(acts), "Workouts or walks")
    org.need(bool(symptoms), "Aches or pain in joints, back or muscles, if any")
    _red_flags(org, symptoms)
    calm = _unflagged(org, symptoms)
    if _days(calm) >= K.HEADACHE_DAYS_WATCH:  # same "four days in the window" bar as headaches
        org.flag("worth_watching", f"Pain came up on {_days(calm)} days.", map(_item, calm))
    elif calm:
        org.reasons.append(f"Pain came up on {_plural(_days(calm), 'day')}.")
    if acts:
        weekly = sum(o["value"] for o in acts) * 7 / org.window
        org.reasons.append(f"About {_g(round(weekly))} minutes of movement a week; strength work on {K.WHO_STRENGTH_DAYS_MIN} days a week keeps bones and muscles strong.")
    org.next_step = {
        "talk_to_doctor": "Please get this pain checked by a doctor.",
        "worth_watching": "Ease the load on whatever hurts for a few days and note what makes it better or worse.",
        "steady": "Keep moving; adding two short strength sessions a week helps bones and muscles.",
        "no_data": "Log a walk or workout to start this area.",
    }[org.status]


def _skin(org: _Organ, obs: list[dict]) -> None:
    symptoms = _symptoms_for(obs, "skin")
    org.add("symptoms", map(_item, symptoms))
    org.need(bool(symptoms), "Skin changes such as rashes, itching or breakouts, if you notice any")
    _red_flags(org, symptoms)
    calm = _unflagged(org, symptoms)
    if calm:
        org.flag("worth_watching", f"You logged {_names(calm)}. "
                 "A rash that spreads fast, blisters or comes with fever needs a doctor quickly.", map(_item, calm))
    org.next_step = {
        "talk_to_doctor": "Please get your skin checked by a doctor.",
        "worth_watching": "A dated photo each day makes changes easy to show a doctor.",
        "steady": "Nothing to do here; mention any skin changes when you notice them.",
        "no_data": "Bubbles only knows about your skin if you mention it. Nothing logged here is normal.",
    }[org.status]


RULES = {"heart": _heart, "lungs": _lungs, "brain": _brain, "eyes": _eyes, "stomach_intestines": _gut, "liver_pancreas": _liver,
         "kidneys_bladder": _kidneys, "thyroid": _thyroid, "skeleton_muscles": _skeleton, "skin": _skin}


# --------------------------------------------------------------------------------------------------
# public API
# --------------------------------------------------------------------------------------------------

def assess_organ(organ_id: str, obs: list[dict], *, today: date, window_days: int, cycle: dict | None = None) -> dict:
    if organ_id not in ORGANS:
        raise KeyError(organ_id)
    org = _Organ(organ_id, window_days, today)
    if organ_id == "uterus_ovaries":
        _uterus(org, obs, cycle)
    else:
        RULES[organ_id](org, obs)
    if org.status == "no_data":
        org.reasons = [f"Nothing in the last {window_days} days touches this area yet. That is a gap, not a sign that all is well."]
    elif org.status == "steady" and not org.reasons:
        org.reasons.append("None of the checks for this area were crossed.")

    flagged_keys = {(f["id"], f["date"], f["label"]) for f in org.flagged}
    rest = sorted((e for e in org.evidence if (e["id"], e["date"], e["label"]) not in flagged_keys), key=lambda e: e["date"], reverse=True)
    evidence = (sorted(org.flagged, key=lambda e: e["date"], reverse=True) + rest)[:K.ORGAN_EVIDENCE_MAX]
    name = ORGANS[organ_id]
    updated = max((e["date"] for e in org.evidence), default=None)
    out: dict[str, Any] = {}
    if org.safety:  # safety guidance first, always
        out["safety"] = org.safety
    out.update({
        "organ_id": organ_id,
        "name": name,
        "status": org.status,
        "summary": org.reasons[0],
        "reasons": org.reasons,
        "evidence": evidence,
        "evidence_count": len(org.evidence),
        "confidence": _confidence(org),
        "missing": org.missing,
        "notes": org.notes,
        "next_step": org.next_step,
        "not_a_diagnosis": True,
        "updated_at": updated,
        "chat_prompt": {"text": f"Explain my {CHAT_NAMES.get(organ_id, name.lower())}", "organ_id": organ_id, "status": org.status,
                        "evidence": evidence},
    })
    if "safety" not in out:
        out = {"safety": None, **out}
    return out


def build_organ_map(events: Iterable[dict] = (), *, labs: Iterable[dict] = (), conditions: Iterable[dict] = (),
                    cycle: dict | None = None, today: date, window_days: int = K.ORGAN_WINDOW_DEFAULT_DAYS,
                    reproductive: str | None = None) -> dict:
    """Every organ, in a fixed order. ``window_days`` is clamped to clinical_constants.ORGAN_WINDOW_DAYS.

    ``reproductive`` comes from the person's first-run setup: "uterus_ovaries" always shows the uterus and ovaries (a female body),
    "none" never does (a male body), anything else keeps the earlier rule (shown once they use Cycle or log something for the area)."""
    lo, hi = K.ORGAN_WINDOW_DAYS
    window_days = max(lo, min(hi, int(window_days)))
    obs = observations(events, labs, conditions, today=today, window_days=window_days)
    organs = [assess_organ(o, obs, today=today, window_days=window_days, cycle=cycle) for o in ORGANS]
    if reproductive == "none":
        organs = [o for o in organs if o["organ_id"] not in OPT_IN_ORGANS]
    else:
        always = reproductive == "uterus_ovaries"
        organs = [o for o in organs if o["organ_id"] not in OPT_IN_ORGANS or always or o["status"] != "no_data" or _uses_cycle(cycle)]
    return {
        "window_days": window_days,
        "as_of": today.isoformat(),
        "not_a_diagnosis": True,
        "notice": NOT_A_DIAGNOSIS,
        "review_status": K.REVIEW_STATUS,
        "counts": {s: sum(1 for o in organs if o["status"] == s) for s in STATUSES},
        "organs": organs,
    }
