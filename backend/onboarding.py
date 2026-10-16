"""First-run setup: the question bank, the rules that choose which questions a person sees, validation, and the experience profile
built from the answers.

Pure functions, no I/O (onboarding_api.py does the storing). Nothing here calls a model or diagnoses anything: answers only change
which parts of the app are shown, in what order, with what wording, and which "worth asking your doctor" items appear.

Rules that shape the bank:
  * Lean: a handful of required taps (body first, then date of birth, name, main goal, any condition, sleep, stress, and for a female
    body periods), one optional stage ("a little more, skip any"), and a "later" stage that only Me > Your setup shows.
  * Required is either always (`REQUIRED`) or only when a rule holds (`REQUIRED_IF`, for example periods for a female body).
  * Questions about periods, pregnancy, cervical screening and menopause are shown only to bodies that can have them (female, trans, other,
    and, for the period question itself, "prefer not to say"); a male body never sees them.
  * "Prefer not to say" is a valid answer wherever it is offered and never narrows a feature.
  * 18 and over only: a younger person gets a stop screen and nothing is stored (see onboarding_api.py).
  * Consent is never a question here: the "Your choices" step writes the consent ledger (consent*.py) on its own.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

BANK_VERSION = "2026-10b"
MIN_AGE = 18
MAX_AGE = 110
REQUIRED = ("body", "language", "birth_date", "preferred_name", "main_goal", "conditions_any", "sleep_pattern", "stress_level")
#: required only while the rule holds (and the question is shown)
REQUIRED_IF: dict[str, dict] = {"periods": {"body_in": ["female"]}}

BODIES = ("female", "male", "trans", "other", "prefer_not")
REPRO = ("female", "trans", "other", "prefer_not")   # may have periods: the question is asked and "I don't get periods" is an answer. Never a male body.
STRICT_REPRO = ("female",)                           # pregnancy, menopause and cervical-screening questions

#: free-text answers: each goes through the safety engine before it is stored (onboarding_api.py)
FREE_TEXT = ("conditions_other", "drains_other")

STEPS: list[dict[str, str]] = [
    {"id": "core", "title": "A few quick taps", "intro": ""},
    {"id": "extras", "title": "A little more", "intro": "Skip any of these, or all of them."},
    {"id": "later", "title": "Your health checks", "intro": "Optional, and only here in your setup."},
]


def _o(id_: str, label: str, show_if: dict | None = None) -> dict[str, Any]:
    option: dict[str, Any] = {"id": id_, "label": label}
    if show_if:
        option["show_if"] = show_if
    return option


def _q(id_: str, step: str, type_: str, title: str, why: str = "", *, options: list[dict] | None = None, show_if: dict | None = None,
       exclusive: tuple[str, ...] = (), **extra: Any) -> dict[str, Any]:
    q: dict[str, Any] = {"id": id_, "step": step, "type": type_, "title": title, "why": why, "required": id_ in REQUIRED}
    if id_ in REQUIRED_IF:
        q["required_if"] = REQUIRED_IF[id_]
    if options is not None:
        q["options"] = options
    if show_if:
        q["show_if"] = show_if
    if exclusive:
        q["exclusive"] = list(exclusive)
    q.update(extra)
    return q


QUESTIONS: list[dict[str, Any]] = [
    # ---- core: the first screen is the body question with the language row beside it; the date of birth is saved in the same request
    _q("body", "core", "single", "Which best describes you?",
       "This picks your body map and whether Cycle shows. You can change it any time.",
       options=[_o("female", "Female"), _o("male", "Male"), _o("trans", "Transgender"), _o("other", "Other"), _o("prefer_not", "Prefer not to say")]),
    _q("language", "core", "single", "Which language feels easiest?", screen_with="body",
       options=[_o("english", "English"), _o("hinglish", "Hinglish"), _o("hindi", "Hindi")]),
    _q("birth_date", "core", "date", "When were you born?", "Bubbles is for people 18 and over for now."),
    _q("preferred_name", "core", "text", "What should Bubbles call you?", maxlength=40),
    _q("main_goal", "core", "single", "What would you like help with most?", options=[
        _o("sleep", "Sleep"), _o("stress_mood", "Stress and mood"), _o("fitness_weight", "Fitness and weight"), _o("food", "Food"),
        _o("manage_condition", "Managing a condition"), _o("understand_symptoms", "Understanding symptoms"), _o("doctor_visits", "Doctor visits"),
        _o("cycle", "My cycle", {"body_in": list(REPRO)}), _o("just_exploring", "Just exploring")]),
    _q("conditions_any", "core", "single", "Has a doctor ever told you that you have a long-term condition?",
       options=[_o("yes", "Yes"), _o("no", "No"), _o("prefer_not", "Prefer not to say")]),
    _q("conditions", "core", "multi", "Which ones?", "Pick any that apply.", show_if={"answers": {"conditions_any": ["yes"]}}, options=[
        _o("diabetes", "Diabetes"), _o("prediabetes", "Prediabetes"), _o("high_bp", "High blood pressure"), _o("thyroid", "Thyroid condition"),
        _o("pcos", "PCOS or PCOD", {"body_in": list(STRICT_REPRO)}), _o("asthma_copd", "Asthma or COPD"), _o("heart", "Heart condition"),
        _o("migraine", "Migraine"), _o("anaemia", "Anaemia"), _o("depression_anxiety", "Depression or anxiety"), _o("kidney", "Kidney condition"),
        _o("liver", "Liver condition"), _o("arthritis", "Arthritis"), _o("other", "Something else")]),
    _q("conditions_other", "core", "text", "What else?", show_if={"answers": {"conditions": ["other"]}}, maxlength=80),
    _q("sleep_pattern", "core", "single", "How long do you usually sleep at night?", options=[
        _o("under_6", "Under 6 hours"), _o("six_seven", "6 to 7 hours"), _o("seven_eight", "7 to 8 hours"), _o("over_8", "Over 8 hours")]),
    _q("stress_level", "core", "single", "How stressed have you been feeling lately?", options=[
        _o("low", "Low"), _o("sometimes", "Sometimes"), _o("often", "Often"), _o("most_days", "Most days")]),
    _q("periods", "core", "single", "Do you get periods?", "So Cycle can be set up properly.", show_if={"body_in": list(REPRO), "age_gte": 18, "age_lt": 56},
       options=[_o("regular", "Yes, fairly regular"), _o("irregular", "Yes, but irregular"), _o("not_now", "Not at the moment"), _o("none", "I don't get periods"), _o("prefer_not", "Prefer not to say")]),
    _q("periods_reason", "core", "single", "What fits best?", show_if={"answers": {"periods": ["not_now"]}}, options=[
        _o("pregnant", "I am pregnant"), _o("recently_gave_birth", "I recently gave birth"), _o("breastfeeding", "I am breastfeeding"),
        _o("contraception", "Contraception stops them"), _o("menopause", "Menopause"), _o("other", "Something else"), _o("prefer_not", "Prefer not to say")]),
    # ---- extras: all optional, one stage, "skip all" is one tap
    _q("last_period", "extras", "date", "When did your last period start?", "Within the last four months.", show_if={"answers": {"periods": ["regular", "irregular"]}}),
    _q("pregnancy_plans", "extras", "single", "Are you trying to get pregnant?",
       show_if={"body_in": list(STRICT_REPRO), "age_gte": 18, "age_lt": 51, "not_answers": {"periods_reason": ["pregnant", "recently_gave_birth", "breastfeeding"]}},
       options=[_o("no", "No"), _o("trying", "Yes"), _o("prefer_not", "Prefer not to say")]),
    _q("due_date", "extras", "date", "Your due date", show_if={"answers": {"periods_reason": ["pregnant"]}}),
    _q("baby_birth_date", "extras", "date", "Your baby's date of birth", show_if={"answers": {"periods_reason": ["recently_gave_birth", "breastfeeding"]}}),
    _q("diet_style", "extras", "single", "How do you usually eat?", "So food ideas fit you.", options=[
        _o("vegetarian", "Vegetarian"), _o("eggetarian", "Eggetarian"), _o("non-vegetarian", "Non-vegetarian"), _o("vegan", "Vegan"), _o("jain", "Jain"), _o("none", "No particular style")]),
    _q("recent_blood_test", "extras", "single", "Have you had a blood test in the last year?",
       options=[_o("yes", "Yes"), _o("no", "No"), _o("not_sure", "Not sure")]),
    _q("height_weight", "extras", "number_pair", "Height and weight", "Used for fitness and food guidance."),
    _q("activity", "extras", "single", "How active is a usual week?", options=[
        _o("sedentary", "Mostly sitting"), _o("light", "Light: a little walking"), _o("moderate", "Moderate: exercise a few times a week"), _o("very_active", "Very active")]),
    _q("takes_medicines", "extras", "single", "Do you take any medicines or supplements regularly?", "You can add them in Care after setup.",
       options=[_o("yes", "Yes"), _o("no", "No"), _o("prefer_not", "Prefer not to say")]),
    _q("allergies", "extras", "single", "Any allergies?", options=[_o("no", "No"), _o("yes", "Yes"), _o("not_sure", "Not sure")]),
    _q("allergy_types", "extras", "multi", "Which kind?", show_if={"answers": {"allergies": ["yes"]}}, options=[
        _o("food", "Food"), _o("medicine", "Medicine"), _o("dust_pollen", "Dust or pollen"), _o("other", "Something else")]),
    _q("avoid_topics", "extras", "multi", "Anything you'd rather Bubbles didn't bring up unless you ask?", exclusive=("none",), options=[
        _o("weight", "My weight"), _o("calories_food_numbers", "Calories and food numbers"), _o("periods", "Periods", {"body_in": list(REPRO)}), _o("family", "My family"), _o("none", "Nothing in particular")]),
    _q("tone", "extras", "single", "How should Bubbles talk with you?", "Gentle and warm unless you say otherwise.", options=[
        _o("gentle_warm", "Gentle and warm"), _o("calm_direct", "Calm and direct"), _o("cheerful_playful", "Cheerful and playful")]),
    _q("reply_length", "extras", "single", "How long should replies be?", options=[_o("short", "Short"), _o("detailed", "Detailed")]),
    _q("support_people", "extras", "multi", "When something's on your mind, who do you usually turn to?", exclusive=("mostly_on_my_own", "rather_not_say"), options=[
        _o("family", "Family"), _o("partner", "My partner"), _o("friends", "Friends"), _o("colleagues_classmates", "Colleagues or classmates"), _o("online_communities", "Online communities"),
        _o("a_pet", "My pet"), _o("faith_or_community", "My faith or community"), _o("mostly_on_my_own", "I mostly work things through on my own"), _o("rather_not_say", "I'd rather not say")]),
    _q("drains", "extras", "multi", "What tends to drain or irritate you?", options=[
        _o("work_study_pressure", "Work or study pressure"), _o("money", "Money worries"), _o("family_or_relationship_tension", "Tension with family or a partner"), _o("not_enough_sleep", "Not enough sleep"),
        _o("health_worries", "Health worries"), _o("noise_or_crowds", "Noise or crowds"), _o("traffic_commute", "Traffic or commuting"), _o("screens_social_media", "Screens and social media"),
        _o("heat", "Heat"), _o("being_rushed", "Being rushed"), _o("something_else", "Something else")]),
    _q("drains_other", "extras", "text", "What else?", show_if={"answers": {"drains": ["something_else"]}}, maxlength=80),
    _q("checkins_wanted", "extras", "single", "Would you like Bubbles to check in on you now and then?", options=[_o("yes_daily", "Yes, daily"), _o("sometimes", "Sometimes"), _o("no", "No, thanks")]),
    # ---- later: not part of the first run. Me > Your setup (the edit view) shows them.
    _q("bp_sugar_check", "later", "single", "When did you last get your blood pressure and blood sugar checked?", show_if={"age_gte": 30},
       options=[_o("within_year", "In the last year"), _o("one_to_three_years", "One to three years ago"), _o("longer_or_never", "Longer ago, or never"), _o("not_sure", "Not sure")]),
    _q("cervical_screen", "later", "single", "Have you ever had a cervical screening test (Pap, HPV or VIA)?",
       show_if={"body_in": list(STRICT_REPRO), "age_gte": 30, "age_lt": 66}, options=[
        _o("last_5_years", "In the last five years"), _o("longer_ago", "Longer ago"), _o("never", "Never"), _o("not_sure", "Not sure"), _o("prefer_not", "Prefer not to say")]),
    _q("midlife_changes", "later", "multi", "In the last few months, have you noticed any of these?", exclusive=("none", "prefer_not"),
       show_if={"body_in": list(STRICT_REPRO), "age_gte": 40}, options=[
        _o("hot_flushes", "Hot flushes"), _o("night_sweats", "Night sweats"), _o("period_changes", "Changes in my periods"),
        _o("sleep_changes", "Changes in my sleep"), _o("none", "None of these"), _o("prefer_not", "Prefer not to say")]),
    _q("urinary_changes", "later", "single", "Do you often get up at night to pass urine, or notice a weaker flow?",
       show_if={"body_in": ["male"], "age_gte": 45}, options=[_o("yes", "Yes"), _o("no", "No"), _o("prefer_not", "Prefer not to say")]),
    _q("tobacco", "later", "multi", "Do you use tobacco in any form?", "Includes chewing forms such as gutka, paan with tobacco or khaini.", exclusive=("no", "prefer_not"), options=[
        _o("no", "No"), _o("smoke", "I smoke"), _o("chew", "I chew tobacco"), _o("used_to", "I used to"), _o("prefer_not", "Prefer not to say")]),
    _q("screen_hours", "later", "slider", "About how many hours a day are you on screens?", min=0, max=16, increment=0.5, unit="h"),
    _q("last_eye_exam", "later", "single", "When was your last eye check?", options=[
        _o("within_year", "In the last year"), _o("one_to_two_years", "One to two years ago"), _o("longer", "Longer ago"), _o("never_not_sure", "Never, or not sure")]),
]

BY_ID: dict[str, dict[str, Any]] = {q["id"]: q for q in QUESTIONS}
assert len(BY_ID) == len(QUESTIONS), "duplicate question id"
assert set(REQUIRED) <= set(BY_ID) and set(REQUIRED_IF) <= set(BY_ID)
assert set(FREE_TEXT) <= set(BY_ID)

#: Hinglish question titles (English is the fallback for any id not listed)
TITLES_HI: dict[str, str] = {
    "preferred_name": "Bubbles aapko kya bulaye?", "birth_date": "Aapka janm din kab hai?", "body": "Aap khud ko kaise batate hain?",
    "language": "Kaunsi bhasha aapko aasan lagti hai?", "main_goal": "Aap sabse zyada kis cheez mein madad chahte hain?",
    "conditions_any": "Kya kisi doctor ne kabhi bataya hai ki aapko koi lambi bimari hai?", "takes_medicines": "Kya aap regular koi dawai ya supplement lete hain?",
    "allergies": "Koi allergy hai?", "periods": "Kya aapko periods aate hain?", "sleep_pattern": "Aap raat ko aam taur par kitna sote hain?",
    "stress_level": "Pichhle dino mein aap kitna stress mehsoos kar rahe hain?", "support_people": "Jab mann mein kuch chal raha ho, to aap aam taur par kisse baat karte hain?",
    "drains": "Kis cheez se aap thak jate hain ya chidh jate hain?", "tone": "Bubbles aapse kaise baat kare?",
    "reply_length": "Jawab kitne lambe hon?", "diet_style": "Aap aam taur par kaisa khana khate hain?", "recent_blood_test": "Kya pichhle saal aapne blood test karwaya hai?",
}


# --------------------------------------------------------------------------------------------------
# rules
# --------------------------------------------------------------------------------------------------

def parse_day(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value.strip()):
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None


def age_on(birth: Any, today: date) -> int | None:
    born = parse_day(birth)
    if born is None or born > today:
        return None
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def _picked(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value]
    return [] if value in (None, "") else [str(value)]


def matches(rule: dict | None, answers: dict[str, Any], today: date) -> bool:
    """Every part of the rule must hold. A part that depends on an unanswered question does not hold, except `not_answers`."""
    if not rule:
        return True
    age = age_on(answers.get("birth_date"), today)
    if "age_gte" in rule and (age is None or age < rule["age_gte"]):
        return False
    if "age_lt" in rule and (age is None or age >= rule["age_lt"]):
        return False
    if "body_in" in rule and answers.get("body") not in rule["body_in"]:
        return False
    for qid, ids in (rule.get("answers") or {}).items():
        if not set(_picked(answers.get(qid))) & set(ids):
            return False
    for qid, ids in (rule.get("not_answers") or {}).items():
        if set(_picked(answers.get(qid))) & set(ids):
            return False
    return True


def visible_options(question: dict, answers: dict[str, Any], today: date) -> list[dict]:
    return [o for o in question.get("options", []) if matches(o.get("show_if"), answers, today)]


def visible_ids(answers: dict[str, Any], today: date) -> list[str]:
    return [q["id"] for q in QUESTIONS if matches(q.get("show_if"), answers, today)]


def is_required(q: dict, answers: dict[str, Any], today: date) -> bool:
    """Always for the `REQUIRED` questions, and for a `required_if` question while its rule holds."""
    return bool(q["required"] or (q.get("required_if") and matches(q["required_if"], answers, today)))


def required_missing(answers: dict[str, Any], today: date) -> list[str]:
    shown = set(visible_ids(answers, today))
    return [q["id"] for q in QUESTIONS if q["id"] in shown and is_required(q, answers, today) and answers.get(q["id"]) in (None, "", [])]


_GOAL_IDS = {o["id"] for o in BY_ID["main_goal"]["options"]}


def migrate_legacy(answers: dict[str, Any]) -> dict[str, Any]:
    """Answers saved under the earlier, longer bank, as answers to today's questions. What still means the same thing is carried over
    (the first goal, whether there is a condition, the sleep range); everything else the bank no longer asks is dropped, and so is the
    old bundled AI-consent answer: consent is only ever recorded by the consent ledger."""
    out = {k: v for k, v in answers.items() if k in BY_ID}
    goals = _picked(answers.get("goals"))
    if "main_goal" not in out:
        first = next((g for g in goals if g in _GOAL_IDS), None)
        if first:
            out["main_goal"] = first
    conds = _picked(answers.get("conditions"))
    if "conditions_any" not in out and conds:
        out["conditions_any"] = "no" if conds == ["none"] else "prefer_not" if conds == ["prefer_not"] else "yes"
    if {"none", "prefer_not"} & set(conds):
        out.pop("conditions", None)
    hours = answers.get("sleep_hours")
    if "sleep_pattern" not in out and isinstance(hours, (int, float)) and not isinstance(hours, bool):
        out["sleep_pattern"] = "under_6" if hours < 6 else "six_seven" if hours < 7 else "seven_eight" if hours <= 8 else "over_8"
    return out


# --------------------------------------------------------------------------------------------------
# validation
# --------------------------------------------------------------------------------------------------

class AnswerError(ValueError):
    def __init__(self, qid: str, message: str):
        super().__init__(message)
        self.qid = qid
        self.message = message


_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f<>]")


def _text(q: dict, value: Any) -> str:
    if not isinstance(value, str):
        raise AnswerError(q["id"], "Please type some text.")
    cleaned = re.sub(r"\s+", " ", _CONTROL.sub("", value.replace(chr(0), ""))).strip()
    cleaned = cleaned.encode("utf-8", "ignore").decode("utf-8")
    if not cleaned:
        raise AnswerError(q["id"], "Please type some text.")
    limit = q.get("maxlength", 300)
    if len(cleaned) > limit:
        raise AnswerError(q["id"], f"Please keep this under {limit} characters.")
    return cleaned


def _number(q: dict, value: Any, lo: float, hi: float, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value != value:
        raise AnswerError(q["id"], f"{label} must be a number.")
    if not lo <= float(value) <= hi:
        raise AnswerError(q["id"], f"{label} must be between {lo:g} and {hi:g}.")
    return float(value)


def clean_answer(q: dict, value: Any, answers: dict[str, Any], today: date) -> Any:
    """The stored form of one answer, or an AnswerError saying why not."""
    qid, kind = q["id"], q["type"]
    if kind == "text":
        return _text(q, value)
    if kind == "date":
        day = parse_day(value)
        if day is None:
            raise AnswerError(qid, "Please choose a real date.")
        if qid == "birth_date":
            age = age_on(day, today)
            if age is None or age > MAX_AGE:
                raise AnswerError(qid, "Please check your date of birth.")
        elif qid == "last_period":
            if not today - timedelta(days=120) <= day <= today:
                raise AnswerError(qid, "That should be within the last four months.")
        elif qid == "due_date":
            if not today <= day <= today + timedelta(days=300):
                raise AnswerError(qid, "Your due date should be within the next ten months.")
        elif qid == "baby_birth_date":
            if not today - timedelta(days=1100) <= day <= today:
                raise AnswerError(qid, "That should be within the last three years.")
        return day.isoformat()
    if kind in ("single", "multi"):
        allowed = {o["id"] for o in visible_options(q, answers, today)}
        picks = _picked(value) if kind == "multi" else ([value] if isinstance(value, str) and value else [])
        if kind == "single" and (not isinstance(value, str) or value not in allowed):
            raise AnswerError(qid, "Please choose one of the options.")
        if kind == "multi" and (not isinstance(value, list) or not picks):
            raise AnswerError(qid, "Please choose at least one option.")
        bad = [p for p in picks if p not in allowed]
        if bad:
            raise AnswerError(qid, "Please choose from the options shown.")
        if kind == "single":
            return picks[0]
        picks = list(dict.fromkeys(picks))
        exclusive = [p for p in picks if p in q.get("exclusive", [])]
        if exclusive:
            return [exclusive[0]]     # "None of these" / "Prefer not to say" stand alone
        if len(picks) > q.get("max_picks", 99):
            raise AnswerError(qid, f"Please pick at most {q['max_picks']}.")
        return picks
    if kind == "slider":
        n = _number(q, value, q["min"], q["max"], "That")
        step = q.get("increment", 1)
        return round(round(n / step) * step, 2)
    if kind == "faces":
        n = _number(q, value, 1, 5, "That")
        return int(round(n))
    if kind == "number_pair":
        if not isinstance(value, dict) or set(value) - {"height_cm", "weight_kg"}:
            raise AnswerError(qid, "Please enter height and weight.")
        out: dict[str, float] = {}
        for key, (lo, hi, label) in {"height_cm": (120, 230, "Height"), "weight_kg": (30, 300, "Weight")}.items():
            if value.get(key) not in (None, ""):
                out[key] = round(_number(q, value[key], lo, hi, label), 1)
        if not out:
            raise AnswerError(qid, "Please enter height or weight.")
        return out
    raise AnswerError(qid, "Unsupported question.")


def apply_answers(current: dict[str, Any], patch: dict[str, Any], today: date) -> tuple[dict[str, Any], list[str], list[str]]:
    """Merge `patch` into `current`. A value of None clears an answer (a skip). Returns (answers, dropped, skipped_now).

    Answers whose question stopped applying (for example `periods` after the body changes to male) are dropped, repeatedly, until
    nothing depends on a removed answer. Unknown ids raise AnswerError."""
    merged = dict(current)
    skipped: list[str] = []
    for qid, value in patch.items():
        q = BY_ID.get(qid)
        if q is None:
            raise AnswerError(str(qid), "Unknown question.")
        if value is None:
            if is_required(q, merged, today):
                raise AnswerError(qid, "This one can't be skipped.")
            merged.pop(qid, None)
            skipped.append(qid)
            continue
        # a patch may answer a question and the one it unlocks together, so validate against what the merged answers will be
        trial = {**merged, qid: value}
        if not matches(q.get("show_if"), trial, today):
            raise AnswerError(qid, "This question doesn't apply right now.")
        merged[qid] = clean_answer(q, value, trial, today)
    dropped: list[str] = []
    while True:
        gone = [qid for qid in list(merged) if qid in BY_ID and not matches(BY_ID[qid].get("show_if"), merged, today)]
        # an option that stopped applying also removes its answer
        for qid in list(merged):
            q = BY_ID.get(qid)
            if q and q["type"] in ("single", "multi") and qid not in gone:
                allowed = {o["id"] for o in visible_options(q, merged, today)}
                picks = _picked(merged[qid])
                if any(p not in allowed for p in picks):
                    kept = [p for p in picks if p in allowed]
                    if kept and q["type"] == "multi":
                        merged[qid] = kept
                    else:
                        gone.append(qid)
        if not gone:
            break
        for qid in gone:
            merged.pop(qid, None)
            dropped.append(qid)
    return merged, dropped, skipped


# --------------------------------------------------------------------------------------------------
# the experience profile
# --------------------------------------------------------------------------------------------------

#: which tracker a goal points to, in the order people see them on Today
GOAL_TRACKERS: dict[str, list[str]] = {
    "understand_symptoms": ["symptoms"], "sleep": ["sleep"], "stress_mood": ["mood", "mind"], "fitness_weight": ["activity", "weight"],
    "food": ["nutrition", "hydration"], "manage_condition": ["vitals", "medications"], "doctor_visits": ["care"], "cycle": ["cycle"],
}
#: body systems to light first on the body map, by what the person told us
CONDITION_FOCUS: dict[str, list[str]] = {
    "diabetes": ["pancreas", "eyes", "kidneys", "heart"], "prediabetes": ["pancreas", "heart"], "high_bp": ["heart", "kidneys", "brain", "eyes"],
    "thyroid": ["thyroid"], "asthma_copd": ["lungs"], "heart": ["heart"], "migraine": ["brain"], "kidney": ["kidneys"], "liver": ["liver"], "arthritis": ["skeleton_muscles"],
}


def _first(values: list[str] | None, wanted: str) -> bool:
    return wanted in (values or [])


def body_of(answers: dict[str, Any]) -> str | None:
    return answers.get("body") if answers.get("body") in BODIES else None


def build_experience(answers: dict[str, Any], today: date) -> dict[str, Any]:
    """Deterministic. Only reorders, shows, hides and words things; never infers a condition."""
    body = body_of(answers)
    age = age_on(answers.get("birth_date"), today)
    goal = answers.get("main_goal")
    conds = _picked(answers.get("conditions"))
    tob = _picked(answers.get("tobacco"))
    avoid = _picked(answers.get("avoid_topics"))
    reason = answers.get("periods_reason")
    periods = answers.get("periods")
    screen = answers.get("screen_hours") if isinstance(answers.get("screen_hours"), (int, float)) else None

    # -- the body the map and the guidance use
    # Female: a female body with uterus and ovaries. Male: a male body. Other / prefer not to say: the general body as it is. Trans: no body map at all.
    base = {"female": "female", "male": "male"}.get(body or "", "neutral")
    body_map = {"visible": body != "trans", "anatomy": base,
                "reproductive": {"female": "uterus_ovaries", "male": "none"}.get(body or "", "by_use")}   # by_use: the map decides from Cycle use, as before
    # -- which sections show. A male body never sees Cycle (it stays in Settings); "prefer not to say" keeps it available.
    hide: list[str] = []
    if body == "male":
        hide.append("cycle")
    visible = ["today", "talk", "patterns", "track", "cycle", "fitness", "care"]
    visible = [s for s in visible if s not in hide]

    # -- cycle
    cycle: dict[str, Any] = {"mode": "track", "visible": "cycle" not in hide, "last_period": answers.get("last_period")}
    if reason == "pregnant":
        cycle["mode"] = "pregnancy"
    elif reason in ("recently_gave_birth", "breastfeeding"):
        cycle["mode"] = "postpartum"
    elif reason == "contraception":
        cycle["mode"] = "birth_control"
    elif reason == "menopause":
        cycle["mode"] = "perimenopause"
    elif answers.get("pregnancy_plans") == "trying":
        cycle["mode"] = "conceive"
    cycle["midlife"] = bool(set(_picked(answers.get("midlife_changes"))) - {"none", "prefer_not"})
    cycle["tracks_periods"] = periods in ("regular", "irregular")

    # -- trackers to put in front of this person
    suggested: list[dict[str, str]] = []

    def suggest(tracker: str, why: str) -> None:
        if tracker not in {s["tracker"] for s in suggested} and not (tracker == "cycle" and "cycle" in hide):
            suggested.append({"tracker": tracker, "why": why})

    for tracker in GOAL_TRACKERS.get(goal, []):
        suggest(tracker, "You said you'd like help with this.")
    if answers.get("sleep_pattern") == "under_6":
        suggest("sleep", "You said your nights are short.")
    if answers.get("stress_level") in ("often", "most_days"):
        suggest("mood", "You said stress has been around a lot.")
    if answers.get("takes_medicines") == "yes":
        suggest("medications", "You said you take medicines or supplements regularly.")
    if screen is not None and screen >= 6:
        suggest("eyes", "Long screen days and tired eyes often go together.")
    if "diabetes" in conds or "prediabetes" in conds or "high_bp" in conds:
        suggest("vitals", "Regular readings help you and your doctor see changes.")

    # -- body map focus: systems to light first, with the reason
    focus: list[str] = []
    for cond in conds:
        for system in CONDITION_FOCUS.get(cond, []):
            if system not in focus:
                focus.append(system)
    for system in (["eyes"] if (screen is not None and screen >= 6) else []) + (["lungs", "mouth", "heart"] if ("smoke" in tob or "chew" in tob) else []):
        if system not in focus:
            focus.append(system)

    # -- Care checklist: "worth asking your doctor about", never orders
    care: list[dict[str, str]] = []

    def item(id_: str, title: str, why: str, source: str) -> None:
        care.append({"id": id_, "title": title, "why": why, "source": source})

    if age is not None and age >= 30 and answers.get("bp_sugar_check") in ("one_to_three_years", "longer_or_never", "not_sure"):
        item("bp_sugar", "Blood pressure and blood sugar check",
             "It is worth asking your doctor how often a blood pressure and sugar check is right for you.", "Bubbles")
    if body in STRICT_REPRO and age is not None and 30 <= age < 66 and answers.get("cervical_screen") in ("longer_ago", "never", "not_sure"):
        item("cervical_screening", "Cervical screening",
             "It is worth asking your doctor whether a cervical screening is due for you.", "Bubbles")
    if "diabetes" in conds and answers.get("last_eye_exam") != "within_year":
        item("eye_exam_diabetes", "Eye exam for diabetes",
             "With diabetes, a regular eye exam is worth asking your doctor about, including how often is right for you.", "Bubbles")
    elif answers.get("last_eye_exam") in ("longer", "never_not_sure") and screen is not None and screen >= 6:
        item("eye_check", "An eye check", "You spend long days on screens and haven't had an eye check in a while. An eye check is worth considering.", "Bubbles")
    if "chew" in tob or "smoke" in tob:
        item("oral_check", "A dental and oral check", "Tobacco in the mouth is hard on gums and teeth. A regular check is worth asking your dentist or doctor about.", "Bubbles")
    if body == "male" and age is not None and age >= 45 and answers.get("urinary_changes") == "yes":
        item("urinary_mention", "Mention night-time urination to a doctor", "Getting up often at night or a weaker flow is worth mentioning at your next visit.", "Bubbles")

    # -- companion style
    support = _picked(answers.get("support_people"))
    companion = {
        "name": answers.get("preferred_name"), "tone": answers.get("tone", "gentle_warm"), "reply_length": answers.get("reply_length", "short"),
        "language": answers.get("language", "english"), "avoid_topics": [a for a in avoid if a != "none"],
        "comfort_actions": _picked(answers.get("helps")), "check_ins": answers.get("checkins_wanted", "sometimes"),
        "works_alone": "mostly_on_my_own" in support, "stressors": [d for d in _picked(answers.get("drains")) if d != "something_else"],
    }

    # -- fitness guidance
    deficits_allowed = not (reason in ("pregnant", "recently_gave_birth", "breastfeeding") or {"weight", "calories_food_numbers"} & set(avoid))
    fitness = {"formula_basis": {"female": "female", "male": "male"}.get(body or "", "average"), "deficits_allowed": deficits_allowed,
               "hide_numbers": bool({"weight", "calories_food_numbers"} & set(avoid))}

    return {
        "version": BANK_VERSION,
        "anatomy": {"base": base, "reproductive": body_map["reproductive"]},
        "body_map": body_map,
        "sections": {"visible": visible, "hidden": hide},
        "cycle": cycle,
        "trackers_suggested": suggested[:6],
        "body_map_focus": focus[:6],
        "care_checklist": care,
        "companion": companion,
        "fitness": fitness,
        "goal": goal if goal in _GOAL_IDS else None,
        "mind": {"offer_checkin": answers.get("stress_level") in ("often", "most_days") or goal == "stress_mood"},
        "language": companion["language"],
    }


def setup_lines(experience: dict[str, Any]) -> list[str]:
    """Plain sentences describing what the experience profile really does, for the setup screen. Each is true of the saved profile."""
    lines: list[str] = []
    anatomy = experience["anatomy"]["base"]
    if not experience["body_map"]["visible"]:
        lines.append("The body map is switched off for your profile")
    else:
        lines.append({"female": "Your body map uses a female body", "male": "Your body map uses a male body"}.get(anatomy, "Your body map uses the general body"))
    cycle = experience["cycle"]
    if not cycle["visible"]:
        lines.append("Cycle and period tracking are tucked away")
    elif cycle["tracks_periods"] or cycle["mode"] != "track":
        lines.append("Cycle tracking is on" + ("" if cycle["mode"] == "track" else f" ({cycle['mode'].replace('_', ' ')} mode)"))
    tone = {"gentle_warm": "gently and warmly", "calm_direct": "calmly and directly", "cheerful_playful": "cheerfully"}[experience["companion"]["tone"]] if experience["companion"]["tone"] in ("gentle_warm", "calm_direct", "cheerful_playful") else "gently"
    language = {"english": "", "hinglish": " in Hinglish", "hindi": " in Hindi"}.get(experience["language"], "")
    lines.append(f"Bubbles will talk with you {tone}{language}")
    if experience["trackers_suggested"]:
        names = [t["tracker"].replace("_", " ") for t in experience["trackers_suggested"][:3]]
        lines.append("Your first trackers: " + ", ".join(names))
    if experience["body_map_focus"]:
        lines.append("Your body map will light up the areas that matter most to you first")
    if experience["care_checklist"]:
        n = len(experience["care_checklist"])
        lines.append(f"{n} check-up{'s' if n != 1 else ''} added to your Care list")
    if experience["fitness"]["hide_numbers"]:
        lines.append("Weight and calorie numbers stay out of sight")
    return lines


# --------------------------------------------------------------------------------------------------
# what the companion is told about how this person likes to be talked to
# --------------------------------------------------------------------------------------------------

_TONE_TEXT = {"gentle_warm": "gentle and warm", "calm_direct": "calm and direct, without filler",
              "cheerful_playful": "cheerful and lightly playful, but never playful about anything serious"}
_AVOID_TEXT = {"weight": "their weight", "calories_food_numbers": "calorie counts and food numbers", "periods": "periods", "family": "their family"}


def style_block(experience: dict[str, Any] | None) -> str:
    """A few plain lines for the model, from the saved experience profile. Only style: tone, reply length, language and topics to
    leave alone. Nothing about their health, their answers on stress or support, or their conditions is included."""
    if not isinstance(experience, dict) or not isinstance(experience.get("companion"), dict):
        return ""
    c = experience["companion"]
    lines = ["HOW THIS PERSON ASKED BUBBLES TO TALK (style only, never overrides safety):"]
    tone = _TONE_TEXT.get(c.get("tone"))
    if tone:
        lines.append(f"- Tone: {tone}.")
    if c.get("reply_length") == "detailed":
        lines.append("- Length: they like fuller answers; up to about 160 words when the question deserves it.")
    elif c.get("reply_length") == "short":
        lines.append("- Length: keep replies short, one to three sentences, unless it is a real health question.")
    language = {"hinglish": "simple Hinglish in Roman script", "hindi": "simple Hindi"}.get(c.get("language"))
    if language:
        lines.append(f"- Language: reply in {language} unless they write in English; keep medical terms in English.")
    avoid = [_AVOID_TEXT[a] for a in (c.get("avoid_topics") or []) if a in _AVOID_TEXT]
    if avoid:
        lines.append("- Do not bring up " + ", ".join(avoid) + " unless they ask about it first.")
    return "\n".join(lines) if len(lines) > 1 else ""
