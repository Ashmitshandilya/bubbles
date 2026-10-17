"""Vitamins, minerals, blood markers and hormones: what each can touch, and soft "might be worth a blood test" nudges.

Pure and deterministic: no database, no network, no model. It never diagnoses, never gives a dose, and a missing piece of data is
reported as a gap, never as "fine". The reference ranges it talks about are only ever the ones the person typed in from their own
lab report (the entries carry `range_source: "report"`); Bubbles keeps no range table of its own and interprets nothing.

Two outputs, both built from the same signals dict:

    evaluate(signals)  -> {"nudges": [...], "lab_notes": [...]}   closed row on Today
    chat_hint(events, profile_signals) -> str | None              at most one sentence for the chat context

`signals_from_rows()` shapes stored rows (tracker events, labs, onboarding answers) into the signals dict. Every field of the dict is
optional; leaving one out can only remove a nudge, never invent one. The rules, thresholds and sentence templates are written out in
docs/drafts/l7-clinical.md for clinician sign-off.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any, Iterable

WINDOW_DAYS = 30        # symptom days are counted over the last 30 days
MIN_SIGN_DAYS = 2       # a sign counts only when it was logged on at least 2 different days
LAB_FRESH_DAYS = 365    # an older result is treated as "no recent result"
LAB_RECENT_OK_DAYS = 90  # a result this recent that sits inside the entered range silences the sign-based nudge
HEAVY_PERIOD_DAYS = 2   # heavy-flow days in the last 90 that count as a "heavy periods" risk factor
MAX_NUDGES = 3
CHAT_MIN_SIGNS = 3      # a low-sureness nudge reaches the chat context only with this many distinct signs

# ----------------------------------------------------------------------------------------------------------------------------
# everyday signs: key -> plain label, wording patterns (English + common Hinglish), safety-engine concepts, general?
# A "general" sign (tired, low mood...) fits almost anything, so on its own it never starts a nudge.
# ----------------------------------------------------------------------------------------------------------------------------
_S = dict
SIGNS: dict[str, dict[str, Any]] = {
    "tired": _S(label="feeling tired", general=True, concepts={"fatigue"},
                rx=r"tired|fatigue|exhaust|low energy|no energy|lethargic|weakness|thakan|kamzori|\bweak\b"),
    "dizzy": _S(label="feeling dizzy", general=True, concepts={"dizziness"}, rx=r"dizz|light.?headed|giddy|chakkar"),
    "low_mood": _S(label="low mood", general=True, concepts={"low_mood"}, rx=r"low mood|feeling low|\bsad\b|irritab|udaas"),
    "poor_sleep": _S(label="poor sleep", general=True, concepts={"insomnia"}, rx=r"can.?t sleep|poor sleep|trouble sleeping|insomnia|neend nahi"),
    "brain_fog": _S(label="trouble concentrating", general=True, concepts=set(),
                    rx=r"brain fog|can.?t concentrate|poor concentration|trouble concentrating|forgetful|memory"),
    "hair": _S(label="hair fall", general=False, concepts=set(), rx=r"hair (?:fall|loss|thinning|shedding)|losing hair|baal jhad|balo? ?ka jhadna|hairfall"),
    "pale": _S(label="looking pale", general=False, concepts=set(), rx=r"\bpale\b|pallor|paleness|peela|safed pad"),
    "breathless": _S(label="getting out of breath easily", general=False, concepts={"shortness_of_breath"},
                     rx=r"out of breath|breathless|short of breath on|saans phool"),
    "palpitations": _S(label="a racing heartbeat", general=False, concepts={"palpitations"}, rx=r"palpitation|racing heart|heart racing|dhadkan"),
    "tingling": _S(label="tingling or numbness", general=False, concepts={"numbness"}, rx=r"tingl|pins and needles|numb|jhunjhuni"),
    "mouth": _S(label="mouth sores or a sore tongue", general=False, concepts={"mouth_ulcer"},
                rx=r"mouth ulcer|mouth sore|sore tongue|cracked lips|angular|chhale|chaale"),
    "cold": _S(label="feeling cold often", general=False, concepts=set(), rx=r"always cold|feel(?:ing)? cold|cold hands|cold feet|cold intoleran"),
    "nails": _S(label="brittle nails", general=False, concepts=set(), rx=r"brittle nail|nails? (?:break|crack|ridge|split)|spoon nail"),
    "cramps": _S(label="muscle cramps or twitching", general=False, concepts=set(), rx=r"muscle (?:cramp|twitch|spasm)|leg cramp|calf cramp|eyelid twitch"),
    "bone": _S(label="bone or joint aches", general=False, concepts={"joint_pain"}, rx=r"bone (?:pain|ache)|joint pain|joints? ach|body ache|backache|jodon ka dard"),
    "weight_gain": _S(label="weight gain", general=False, concepts=set(), rx=r"weight gain|gaining weight|put on weight|motapa"),
    "constipation": _S(label="constipation", general=False, concepts={"constipation"}, rx=r"constipat|kabz"),
    "dry_skin": _S(label="dry skin", general=False, concepts=set(), rx=r"dry skin|skin (?:is )?dry|itchy skin|flaky skin"),
    "thirst": _S(label="frequent thirst or urination", general=False, concepts={"frequent_urination"},
                 rx=r"very thirsty|thirsty all|always thirsty|excess thirst|passing urine a lot|urinat\w* (?:a lot|often|frequent)"),
    "infections": _S(label="catching infections often", general=False, concepts=set(),
                     rx=r"frequent (?:cold|infection|illness)|keep(?:s)? getting (?:sick|ill|infection)|often fall(?:ing)? sick|baar baar bimar"),
    "slow_healing": _S(label="cuts that heal slowly", general=False, concepts=set(), rx=r"slow(?:ly)? heal|wounds? (?:take|heal)|cuts? (?:take|heal)"),
    "irregular_period": _S(label="irregular periods", general=False, concepts=set(),
                           rx=r"irregular period|periods? (?:are )?irregular|missed period|late period|periods? (?:late|delayed|stopped)"),
    "acne": _S(label="acne", general=False, concepts=set(), rx=r"\bacne\b|pimple|breakout"),
    "excess_hair": _S(label="extra facial or body hair", general=False, concepts=set(), rx=r"facial hair|hirsut|excess hair|chin hair"),
    "neck": _S(label="swelling at the front of the neck", general=False, concepts=set(), rx=r"goit|neck swelling|swelling (?:in|at) (?:the )?(?:front of )?(?:the )?neck"),
}
for _k, _v in SIGNS.items():
    _v["rx"] = re.compile(_v["rx"], re.I)

# ----------------------------------------------------------------------------------------------------------------------------
# risk factors (things that make a nutrient more likely to run low): id -> plain sentence shown as a reason
# ----------------------------------------------------------------------------------------------------------------------------
RISK_TEXT = {
    "diet_veg": "You said you eat vegetarian or Jain food.",
    "diet_vegan": "You said you eat vegan food.",
    "diet_veg_egg": "You said you eat vegetarian or egg-and-vegetable food.",
    "heavy_periods": "Your cycle log shows heavy flow on {n} days in the last 3 months.",
    "pregnancy": "You said you are pregnant, breastfeeding, recently had a baby or are planning a pregnancy.",
    "postpartum": "You said you recently had a baby.",
    "metformin": "Your medicines list includes metformin.",
    "acid_reducer": "Your medicines list includes an acid reducer.",
    "low_sun": "You said you get little sun.",
    "alcohol_often": "You said you drink alcohol most weeks.",
    "diabetes_known": "You listed diabetes as a condition.",
    "screening_gap": "Your last sugar and blood pressure check was a while ago, or never.",
}
_METFORMIN = re.compile(r"metformin|glycomet|glucophage|obimet", re.I)
_ACID_REDUCER = re.compile(r"omeprazole|pantoprazole|pantop|rabeprazole|esomeprazole|lansoprazole|ranitidine|famotidine|\bppi\b|acid reducer|\bpan[- ]?d\b", re.I)

_LOW = {"vegetarian", "jain", "vegan"}

# ----------------------------------------------------------------------------------------------------------------------------
# the map: one entry per nutrient / hormone
# ----------------------------------------------------------------------------------------------------------------------------
ENTRIES: dict[str, dict[str, Any]] = {
    "iron": dict(
        name="Iron", nudge=True, marker_rx=r"ferritin|hae?moglobin|\bhb\b|\bhgb\b|serum iron|\biron\b|tibc|transferrin",
        markers="ferritin or haemoglobin", signs=["tired", "hair", "pale", "dizzy", "breathless", "palpitations", "cold", "nails", "brain_fog"],
        risks=["heavy_periods", "pregnancy", "diet_veg"],
        foods=["ragi", "spinach (palak)", "jaggery", "dal, rajma and chana", "eggs", "fish"],
        more_likely=["heavy periods", "pregnancy", "vegetarian or vegan eating", "teenage years"],
        touches=["energy", "hair", "skin", "immunity", "mood", "sleep"], organs=["heart", "brain", "skin"],
        interacts=[(None, "Tea or coffee with meals can make it harder to take in iron. Lemon, amla or other vitamin C foods help.")],
        links=["link:fatigue-nutrient", "link:hair-iron", "link:cycle-fatigue"],
        ask="An iron blood test (ferritin and haemoglobin) could tell. It is worth asking a doctor about."),
    "b12": dict(
        name="Vitamin B12", nudge=True, marker_rx=r"b[- ]?12|cobalamin|homocysteine|methylmalonic|vitamin b test",
        markers="vitamin B12", signs=["tingling", "tired", "mouth", "low_mood", "brain_fog", "pale", "dizzy"],
        risks=["diet_vegan", "diet_veg_egg", "metformin", "acid_reducer"],
        foods=["milk, curd and paneer", "eggs", "fish", "fortified foods"],
        more_likely=["vegan or vegetarian eating", "long-term metformin or acid reducers", "older age"],
        touches=["energy", "nerves", "mood", "memory", "mouth", "blood"], organs=["brain", "stomach_intestines"],
        interacts=[("metformin", "Metformin can lower B12 over time. Worth asking your doctor whether to check it. Please do not change any medicine on your own."),
                   ("acid_reducer", "Acid reducers can lower B12 over time. Worth asking your doctor whether to check it. Please do not change any medicine on your own.")],
        links=["link:fatigue-nutrient", "link:b12-diet"],
        ask="A vitamin B12 blood test could tell. It is worth asking a doctor about."),
    "folate": dict(
        name="Folate", nudge=True, marker_rx=r"folate|folic|vitamin b ?9|\bb9\b",
        markers="folate", signs=["tired", "mouth", "low_mood", "pale", "brain_fog"],
        risks=["pregnancy", "alcohol_often"],
        foods=["dal", "green leafy vegetables", "chana and rajma", "sprouts", "oranges"],
        more_likely=["pregnancy or planning one", "regular alcohol", "very few greens or pulses"],
        touches=["energy", "mood", "blood", "mouth"], organs=["brain", "stomach_intestines"],
        interacts=[], links=["link:fatigue-nutrient"],
        ask="A folate blood test could tell. It is worth asking a doctor about."),
    "vitamin_d": dict(
        name="Vitamin D", nudge=True, marker_rx=r"vitamin d|25.?(?:oh|hydroxy)|cholecalciferol|\bvit\.? ?d\b",
        markers="vitamin D", signs=["tired", "bone", "cramps", "low_mood", "infections", "hair"],
        risks=["low_sun", "diet_vegan", "pregnancy"],
        foods=["morning sunlight on bare skin", "eggs", "fatty fish", "fortified milk"],
        more_likely=["little time in the sun", "covered clothing or mostly indoors", "pregnancy", "older age"],
        touches=["bones", "muscles", "mood", "immunity", "energy"], organs=["skeleton_muscles", "brain"],
        interacts=[], links=["link:fatigue-nutrient", "link:mood-vitamind"],
        ask="A vitamin D blood test could tell. It is worth asking a doctor about."),
    "magnesium": dict(
        name="Magnesium", nudge=True, marker_rx=r"magnesium",
        markers="magnesium", signs=["cramps", "poor_sleep", "tired", "palpitations", "constipation"],
        risks=["alcohol_often", "acid_reducer", "diabetes_known"],
        foods=["nuts and seeds", "ragi and whole grains", "green leafy vegetables", "dal"],
        more_likely=["regular alcohol", "long-term acid reducers", "diabetes"],
        touches=["muscles", "sleep", "energy", "heart rhythm"], organs=["skeleton_muscles", "heart"],
        interacts=[("acid_reducer", "Acid reducers can lower magnesium over time. Worth asking your doctor. Please do not change any medicine on your own.")],
        links=["link:fatigue-nutrient"],
        ask="A magnesium blood test can be part of it, though it does not show the whole picture. It is worth asking a doctor about."),
    "zinc": dict(
        name="Zinc", nudge=True, marker_rx=r"\bzinc\b",
        markers="zinc", signs=["hair", "slow_healing", "infections", "mouth"],
        risks=["diet_veg", "pregnancy"],
        foods=["dal and chana", "pumpkin seeds and nuts", "curd", "eggs"],
        more_likely=["vegetarian or vegan eating", "pregnancy"],
        touches=["skin", "hair", "immunity", "healing"], organs=["skin"],
        interacts=[], links=["link:hair-iron"],
        ask="A zinc blood test could tell. It is worth asking a doctor about."),
    "iodine": dict(
        name="Iodine", nudge=False, marker_rx=r"iodine",
        markers="iodine", signs=["tired", "weight_gain", "cold", "constipation", "dry_skin", "neck"],
        risks=["pregnancy"],
        foods=["iodised salt", "milk and curd", "fish", "eggs"],
        more_likely=["pregnancy", "salt without iodine", "living far from the sea with little iodised salt"],
        touches=["thyroid", "energy", "weight", "pregnancy"], organs=["thyroid"],
        interacts=[], links=["link:cycle-thyroid"],
        ask="Iodine is usually looked at through a thyroid test. It is worth asking a doctor about."),
    "thyroid": dict(
        name="Thyroid hormones", nudge=True, marker_rx=r"\btsh\b|thyroid stimulating|thyrotropin|\bt3\b|\bt4\b|free t[34]|\bft[34]\b|thyroxine|triiodothyronine",
        markers="thyroid (TSH)", signs=["tired", "weight_gain", "cold", "constipation", "dry_skin", "hair", "low_mood", "brain_fog", "irregular_period", "palpitations", "neck"],
        risks=["postpartum"],
        foods=["iodised salt", "milk and curd", "eggs"],
        more_likely=["after a pregnancy", "a family history of thyroid problems", "being a woman over 30"],
        touches=["energy", "weight", "mood", "hair", "skin", "periods", "sleep"], organs=["thyroid", "uterus_ovaries"],
        interacts=[], links=["link:cycle-thyroid", "link:fatigue-labs"],
        ask="A thyroid blood test (TSH) could tell. It is worth asking a doctor about."),
    "blood_sugar": dict(
        name="Blood sugar", nudge=True, marker_rx=r"hba1c|\ba1c\b|glycated|glycosylated|fasting (?:blood )?(?:glucose|sugar)|blood sugar|\bglucose\b|\binsulin\b|\bfbs\b|\bppbs\b",
        markers="HbA1c or fasting sugar", signs=["thirst", "tired", "slow_healing", "infections"],
        risks=["screening_gap"],
        foods=["dal and vegetables", "whole grains instead of refined ones", "nuts"],
        more_likely=["a family history of diabetes", "extra weight around the waist", "low activity", "PCOS"],
        touches=["energy", "thirst", "eyes", "kidneys", "healing"], organs=["liver_pancreas", "eyes", "kidneys_bladder"],
        interacts=[], links=["link:fatigue-labs"],
        ask="A blood sugar test (HbA1c or fasting sugar) could tell. It is worth asking a doctor about."),
    "sex_hormones": dict(
        name="Reproductive hormones", nudge=True, marker_rx=r"estradiol|oestradiol|estrogen|oestrogen|progesterone|testosterone|\bfsh\b|\blh\b|prolactin|\bamh\b|dhea",
        markers="hormone", signs=["irregular_period", "acne", "excess_hair", "weight_gain", "low_mood", "hair"],
        risks=[],
        foods=[], more_likely=["PCOS", "changes after pregnancy", "perimenopause", "high stress or big weight change"],
        touches=["periods", "skin", "hair", "mood", "weight", "fertility"], organs=["uterus_ovaries", "skin"],
        interacts=[], links=["link:cycle-hormones", "link:cycle-fatigue"],
        ask="Hormone blood tests could tell. It is worth asking a doctor which ones fit."),
    "cortisol": dict(
        name="Cortisol", nudge=False, marker_rx=r"cortisol",
        markers="cortisol", signs=["poor_sleep", "tired", "weight_gain", "low_mood"],
        risks=[],
        foods=[], more_likely=["long periods of stress", "poor sleep"],
        touches=["stress response", "sleep", "energy", "weight", "mood"], organs=["brain"],
        interacts=[], links=["link:cycle-stress", "link:stress-weight"],
        ask="Cortisol is rarely a first test. If it worries you, a doctor can tell you whether it is worth checking."),
}
for _k, _e in ENTRIES.items():
    _e["id"] = _k
    _e["range_source"] = "report"   # ranges are only ever the person's own, copied from their lab report
    _e["marker_re"] = re.compile(_e.pop("marker_rx"), re.I)
# conditions the person already knows about: a nudge to "get it checked" would be noise
_KNOWN = {"thyroid": re.compile(r"thyroid", re.I), "blood_sugar": re.compile(r"diabet|prediabet|sugar", re.I)}
_DIABETES = re.compile(r"diabet", re.I)


# ----------------------------------------------------------------------------------------------------------------------------
# shaping stored rows into signals
# ----------------------------------------------------------------------------------------------------------------------------
def _answers_flag(answers: dict, key: str, *values: str) -> bool:
    v = answers.get(key)
    items = v if isinstance(v, (list, tuple, set)) else [v]
    return any(str(i).lower() in values for i in items if i is not None)


def _first(answers: dict, *keys: str) -> Any:
    for k in keys:
        if answers.get(k) not in (None, "", []):
            return answers[k]
    return None


def signals_from_rows(events: Iterable[dict] = (), profile: dict | None = None, *, today: date | None = None) -> dict[str, Any]:
    """Build the signals dict from stored rows.

    events   extracted_health_events rows (tracker saves are mirrored there, chat observations live there)
    profile  optional: labs (tracker lab entries), answers (onboarding answers), meds (names), conditions (names)
    Missing keys are simply gaps. Onboarding answers are read defensively: any key may be absent or have a different shape.
    """
    import organ_map_engine as OM   # pure module; imported late so deficiency_map has no import-time dependencies
    p = profile if isinstance(profile, dict) else {}
    today = today or date.today()
    p = {**p, "labs": [x for x in p["labs"] if isinstance(x, dict)] if isinstance(p.get("labs"), (list, tuple)) else [],
         "meds": [m for m in p["meds"] if m] if isinstance(p.get("meds"), (list, tuple)) else [],
         "conditions": [c for c in p["conditions"] if c] if isinstance(p.get("conditions"), (list, tuple)) else []}
    answers = p.get("answers") if isinstance(p.get("answers"), dict) else {}
    conditions = [str(c) for c in (p.get("conditions") or []) if c]
    obs = OM.observations([e for e in events or () if isinstance(e, dict)], labs=p.get("labs") or (),
                          conditions=[{"condition_name": c} for c in conditions], today=today, window_days=90)
    since = today - timedelta(days=WINDOW_DAYS - 1)
    sign_days: dict[str, set[date]] = {}
    heavy: set[date] = set()
    saw_cycle = False
    labs: list[dict] = []
    for o in obs:
        kind, d = o.get("kind"), o.get("date")
        if not isinstance(d, date):
            continue
        if kind == "lab":
            lo, hi = (o.get("ref") or (None, None))[:2]
            labs.append({"label": str(o.get("label") or ""), "value": o.get("value"), "unit": o.get("unit"), "date": d, "ref": (lo, hi)})
        elif kind == "cycle":
            saw_cycle = True
            if str(o.get("value") or "").lower() == "heavy":
                heavy.add(d)
        elif kind == "symptom" and since <= d <= today:
            text = str(o.get("text") or o.get("label") or "").lower()
            concepts = set(o.get("concepts") or ())
            if "heavy_bleeding" in concepts:
                heavy.add(d)
            for key, s in SIGNS.items():
                if s["rx"].search(text) or (s["concepts"] & concepts):
                    sign_days.setdefault(key, set()).add(d)
        elif kind == "sleep" and since <= d <= today and isinstance(o.get("value"), (int, float)) and o["value"] < 5:
            pass   # short sleep is not a deficiency sign on its own; the sleep log feeds patterns elsewhere
    standing: set[str] = set()
    if str(answers.get("periods") or "").lower() == "irregular":
        standing.add("irregular_period")
    diet = str(_first(answers, "diet_style", "diet") or "").lower() or None
    meds = [str(m) for m in (p.get("meds") or []) if m]
    sun = str(_first(answers, "sun_exposure", "sun") or "").lower()
    alc = str(answers.get("alcohol_freq") or "").lower()
    test = str(_first(answers, "recent_blood_test", "blood_test_recent", "last_blood_test", "blood_test") or "").lower()
    return {
        "today": today, "sign_days": sign_days, "standing_signs": standing,
        "heavy_period_days": len(heavy) if (saw_cycle or heavy) else None,
        "diet": diet if diet and diet != "none" else None,
        "pregnancy": (_answers_flag(answers, "periods_reason", "pregnant", "recently_gave_birth", "breastfeeding")
                      or _answers_flag(answers, "pregnancy_plans", "trying")) if answers else None,
        "postpartum": _answers_flag(answers, "periods_reason", "recently_gave_birth") if answers else None,
        "meds": meds, "conditions": conditions,
        "low_sun": True if sun in ("low", "little", "rarely", "indoors", "mostly_indoors", "none") else (False if sun else None),
        "alcohol_often": (alc in ("two_three_week", "four_plus_week")) if alc else None,
        "screening_gap": (str(answers.get("bp_sugar_check") or "").lower() == "longer_or_never") if answers.get("bp_sugar_check") else None,
        "blood_test_recent": "yes" if test in ("yes", "within_year", "recent", "last_year", "within_6_months", "within_3_months") else ("no" if test else None),
        "labs": sorted(labs, key=lambda x: x["date"], reverse=True),
    }


# ----------------------------------------------------------------------------------------------------------------------------
# labs: link a result to its map entry and describe it against the person's own range (no interpretation)
# ----------------------------------------------------------------------------------------------------------------------------
def entry_for_lab(label: str) -> str | None:
    """The map entry whose marker words match a lab name, or None."""
    text = str(label or "")
    for eid, e in ENTRIES.items():
        if e["marker_re"].search(text):
            return eid
    return None


def _g(n: Any) -> str:
    f = _finite(n)
    if f is None:
        return "?"
    return f"{f:g}" if f == int(f) else f"{f:.2f}".rstrip("0").rstrip(".")


def _finite(n: Any) -> float | None:
    """A real, finite, non-negative, not absurd number, else None (a lab value or range end can never be negative or 1e9+)."""
    if isinstance(n, bool) or not isinstance(n, (int, float)):
        return None
    return float(n) if n == n and 0 <= n < 1e9 else None


_SAFE = re.compile(r"[^A-Za-z0-9 ()%/.,+\-]")


def clean_text(text: Any, limit: int = 40) -> str:
    """Free text that came from the person (test name, unit) before it goes into a sentence or the chat context: letters, digits
    and a few marks only, one line, short. Instruction-like text cannot survive as a sentence."""
    return " ".join(_SAFE.sub("", re.sub(r"\s+", " ", str(text or ""))).split())[:limit]


def _plain(text: Any, limit: int = 40) -> str:
    """The text itself when it is already short and plain, else "" (never a trimmed-down remnant of something odd)."""
    t = " ".join(str(text or "").split())
    return t if 0 < len(t) <= limit and not _SAFE.search(t) else ""


def lab_status(lab: dict) -> str:
    """below | above | within | no_range | no_number, against the range the person entered.
    A value that is not a sane number is no_number; a missing, half-empty, negative or reversed range is no_range."""
    v = _finite(lab.get("value"))
    if v is None:
        return "no_number"
    pair = lab.get("ref")
    lo, hi = (_finite(pair[0]), _finite(pair[1])) if isinstance(pair, (list, tuple)) and len(pair) >= 2 else (None, None)
    if lo is None or hi is None or lo > hi:
        return "no_range"
    return "below" if v < lo else "above" if v > hi else "within"


def lab_note(lab: dict) -> dict[str, Any] | None:
    """Plain note for one lab entry linked to a map entry; None when the test is not one the map knows."""
    eid = entry_for_lab(lab.get("label"))
    if not eid:
        return None
    status = lab_status(lab)
    label = _plain(lab.get("label")) or f"{ENTRIES[eid]['name']} result"
    unit = f" {_plain(lab.get('unit'), 15)}" if _plain(lab.get("unit"), 15) else ""
    lo, hi = (lab.get("ref") or (None, None))[:2]
    value = f"{_g(lab.get('value'))}{unit}"
    text = {
        "below": f"Your {label} of {value} is below the range you entered ({_g(lo)} to {_g(hi)}).",
        "above": f"Your {label} of {value} is above the range you entered ({_g(lo)} to {_g(hi)}).",
        "within": f"Your {label} of {value} is inside the range you entered ({_g(lo)} to {_g(hi)}).",
        "no_range": f"Your {label} has no range entered, so Bubbles cannot compare it. The range is printed on your report.",
        "no_number": f"Your {label} has no number Bubbles can read.",
    }[status]
    d = lab.get("date")
    return {"entry": eid, "entry_name": ENTRIES[eid]["name"], "label": label, "status": status, "text": text,
            "date": d.isoformat() if isinstance(d, date) else d,
            "ask": "Worth going over it with a doctor." if status in ("below", "above") else None}


def lab_notes(signals: dict, limit: int = 6) -> list[dict]:
    """Latest result per test name, newest first, only for tests that match a map entry."""
    seen: set[str] = set()
    out: list[dict] = []
    for lab in signals.get("labs") or []:
        key = str(lab.get("label") or "").lower()
        if key in seen:
            continue
        seen.add(key)
        n = lab_note(lab)
        if n:
            out.append(n)
    return out[:limit]


# ----------------------------------------------------------------------------------------------------------------------------
# the nudges
# ----------------------------------------------------------------------------------------------------------------------------
def _risk_hits(eid: str, s: dict) -> list[tuple[str, str]]:
    diet, meds = s.get("diet"), " ".join(s.get("meds") or [])
    cond = " ".join(s.get("conditions") or [])
    checks = {
        "diet_vegan": diet == "vegan",
        "diet_veg": diet in _LOW,
        "diet_veg_egg": diet in _LOW | {"eggetarian"},
        "heavy_periods": (s.get("heavy_period_days") or 0) >= HEAVY_PERIOD_DAYS,
        "pregnancy": bool(s.get("pregnancy")),
        "postpartum": bool(s.get("postpartum")),
        "metformin": bool(_METFORMIN.search(meds)),
        "acid_reducer": bool(_ACID_REDUCER.search(meds)),
        "low_sun": bool(s.get("low_sun")),
        "alcohol_often": bool(s.get("alcohol_often")),
        "diabetes_known": bool(_DIABETES.search(cond)),
        "screening_gap": bool(s.get("screening_gap")),
    }
    hits = []
    for r in ENTRIES[eid]["risks"]:
        if checks.get(r):
            hits.append((r, RISK_TEXT[r].format(n=s.get("heavy_period_days") or 0)))
    if eid == "b12" and any(r == "diet_vegan" for r, _ in hits):   # vegan already says it; do not list the milder diet line too
        hits = [h for h in hits if h[0] != "diet_veg_egg"]
    return hits


def _sign_lines(eid: str, s: dict) -> tuple[list[str], int, int]:
    """(reason sentences, specific sign count, general sign count) for the signs this entry cares about."""
    since = s["today"] - timedelta(days=WINDOW_DAYS - 1)
    lines, spec, gen = [], 0, 0
    for key in ENTRIES[eid]["signs"]:
        days = {d for d in s.get("sign_days", {}).get(key, ()) if since <= d <= s["today"]}
        standing = key in (s.get("standing_signs") or ())
        if len(days) >= MIN_SIGN_DAYS:
            lines.append(f"You logged {SIGNS[key]['label']} on {len(days)} of the last {WINDOW_DAYS} days.")
        elif standing:
            lines.append("You said your periods are irregular.")
        else:
            continue
        if SIGNS[key]["general"]:
            gen += 1
        else:
            spec += 1
    return lines, spec, gen


def _level(spec: int, gen: int, risks: int) -> str | None:
    n = spec + gen
    if spec >= 1 and n >= 2 and risks >= 1:
        return "medium"
    if spec >= 2 or (spec >= 1 and (gen >= 1 or risks >= 1)) or (gen >= 2 and risks >= 1) or (gen >= 1 and risks >= 2):
        return "low"
    return None


def _nudge(eid: str, s: dict) -> dict | None:
    e = ENTRIES[eid]
    today = s["today"]
    related = [l for l in (s.get("labs") or []) if entry_for_lab(l.get("label")) == eid and isinstance(l.get("date"), date)]
    fresh = [l for l in related if 0 <= (today - l["date"]).days <= LAB_FRESH_DAYS]
    outside = next((l for l in fresh if lab_status(l) in ("below", "above")), None)
    lines, spec, gen = _sign_lines(eid, s)
    risks = _risk_hits(eid, s)
    gaps: list[str] = []
    if outside is not None:
        note = lab_note(outside)
        d = outside["date"]
        out = {"id": eid, "name": e["name"], "kind": "lab", "level": "medium",
               "headline": f"Your {note['label']} is {lab_status(outside)} the range you entered",
               "reasons": [note["text"]] + lines[:1], "gaps": gaps, "ask": "Worth going over it with a doctor."}
        out["date"] = d.isoformat()
    else:
        if not e["nudge"] or (eid in _KNOWN and _KNOWN[eid].search(" ".join(s.get("conditions") or []))):
            return None
        level = _level(spec, gen, len(risks))
        if level is None:
            return None
        quiet = [l for l in fresh if lab_status(l) == "within" and (today - l["date"]).days <= LAB_RECENT_OK_DAYS]
        if quiet:   # a recent result inside their own range: do not nag, and do not call it "fine" either
            return None
        out = {"id": eid, "name": e["name"], "kind": "signs", "level": level, "headline": f"{e['name']} might be worth a blood test",
               "reasons": lines[:3] + [t for _r, t in risks][:2], "gaps": gaps, "ask": e["ask"]}
        if not fresh:
            if s.get("blood_test_recent") == "yes":
                gaps.append(f"You mentioned a recent blood test, but no {e['markers']} result is logged here. Add it under Labs.")
            else:
                gaps.append(f"No recent {e['markers']} result is logged yet.")
    if outside is None and fresh and all(lab_status(l) == "no_range" for l in fresh):
        gaps.append(f"Your {_plain(fresh[0]['label']) or 'result'} has no range entered, so Bubbles cannot compare it.")
    if not s.get("diet") and any(r.startswith("diet_") for r in e["risks"]) and out["kind"] == "signs":
        gaps.append("Bubbles does not know how you usually eat.")
    risk_ids = {r for r, _ in risks}
    out.update(
        signs=spec + gen, foods=e["foods"], touches=e["touches"], organs=e["organs"], links=e["links"], more_likely=e["more_likely"],
        interacts=[t for when, t in e["interacts"] if when is None or when in risk_ids],
        gaps=gaps[:2],
    )
    out["_rank"] = (0 if out["kind"] == "lab" else 1, 0 if out["level"] == "medium" else 1, -(spec + gen), eid)
    return out


def evaluate(signals: dict) -> dict[str, Any]:
    """{"nudges": up to 3 soft items (strongest first), "lab_notes": plain notes for logged results}.

    No data in, nothing out. A nudge is never a verdict: it carries how sure it is (low or medium), why, what is missing, and the
    one next step (ask a doctor about a blood test).
    """
    s = dict(signals or {})
    s.setdefault("today", date.today())
    nudges = [n for n in (_nudge(eid, s) for eid in ENTRIES) if n]
    nudges.sort(key=lambda n: n["_rank"])
    for n in nudges:
        n.pop("_rank", None)
    return {"nudges": nudges[:MAX_NUDGES], "lab_notes": lab_notes(s)}


# ----------------------------------------------------------------------------------------------------------------------------
# chat
# ----------------------------------------------------------------------------------------------------------------------------
def hint_text(nudge: dict) -> str:
    why = " ".join(nudge["reasons"][:2])
    return (f"Possible gentle note (not a diagnosis; mention it in at most one soft sentence and only if it fits what they asked; "
            f"let them decide; no doses or supplements): {why} {nudge['ask']}").strip()


def chat_hint(events: Iterable[dict] = (), profile_signals: dict | None = None) -> str | None:
    """At most one sentence of context for the reply, or None. Medium nudges, or low ones backed by three signs, qualify."""
    try:
        res = evaluate(signals_from_rows(events, profile_signals))
    except Exception:  # noqa: BLE001 - an extra for chat; never a reason for a reply to fail
        return None
    for n in res["nudges"]:
        if n["level"] == "medium" or n["signs"] >= CHAT_MIN_SIGNS:
            return hint_text(n)
    return None
