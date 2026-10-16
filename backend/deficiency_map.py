"""Soft nudges about nutrients, blood markers and hormone-linked signs. Pure and deterministic; not a diagnosis, never an order.

What it does: for each nutrient it knows the everyday signs, who is a bit more likely to run low, what it can touch, India-relevant
foods and the blood test that would settle it. From a person's own logs it can say "might be worth asking about a blood test for iron",
with how sure (low or medium, never high) and the plain reasons. A logged lab value outside the range the person entered is stated as
exactly that; a missing result is a gap, never "fine". Every sentence and threshold is listed in the clinical packet for sign-off."""
from __future__ import annotations

from typing import Any, Iterable

MAX_NUDGES = 3
DAYS_FOR_SIGN = 2          # a sign counts when it was logged or said on at least this many days

#: key -> definition. `markers` are lowercase words that identify its lab test; `signs` are health_semantics concepts.
NUTRIENTS: dict[str, dict[str, Any]] = {
    "iron": {
        "name": "Iron", "markers": ("ferritin", "iron", "haemoglobin", "hemoglobin", "hb"),
        "signs": ("fatigue", "dizziness", "hair_loss", "shortness_of_breath", "palpitations", "headache"),
        "risk": {"diet": ("vegetarian", "vegan", "jain", "eggetarian"), "heavy_periods": True, "pregnancy": True},
        "touches": ("energy", "hair", "skin", "mood", "immunity"), "organs": ("blood", "heart"),
        "foods": ("dal", "spinach (palak)", "ragi", "jaggery", "dates", "eggs", "fish", "lemon with meals"),
        "ask": "Tea or coffee with meals can lower iron absorption, and vitamin C (like lemon) helps. Iron tablets are best started only after a test.",
    },
    "b12": {
        "name": "Vitamin B12", "markers": ("b12", "cobalamin"),
        "signs": ("fatigue", "numbness", "mouth_ulcer", "low_mood", "dizziness"),
        "risk": {"diet": ("vegetarian", "vegan", "jain"), "age_gte": 50},
        "touches": ("energy", "nerves", "mood", "blood"), "organs": ("blood", "brain"),
        "foods": ("milk and curd", "paneer", "eggs", "fish", "fortified foods"),
        "ask": "Metformin and long-term acid reducers can lower B12. Worth mentioning to your doctor if you take either.",
    },
    "vitamin_d": {
        "name": "Vitamin D", "markers": ("vitamin d", "25-oh", "25(oh)", "vit d"),
        "signs": ("muscle_pain", "joint_pain", "fatigue", "low_mood"),
        "risk": {"age_gte": 50, "little_sun": True},
        "touches": ("bones", "muscles", "mood", "immunity"), "organs": ("skeleton_muscles",),
        "foods": ("eggs", "fish", "fortified milk", "a little morning sun on arms and face"),
        "ask": "Sunlight, skin tone and where you live all matter. A test shows whether you actually need more.",
    },
    "folate": {
        "name": "Folate", "markers": ("folate", "folic"),
        "signs": ("fatigue", "mouth_ulcer", "low_mood"),
        "risk": {"pregnancy": True, "diet": ("vegan",)},
        "touches": ("energy", "blood", "pregnancy"), "organs": ("blood",),
        "foods": ("dal", "green leafy vegetables", "beans", "oranges"),
        "ask": "If you may become pregnant, folate matters before and early in pregnancy. Ask your doctor about it.",
    },
    "magnesium": {
        "name": "Magnesium", "markers": ("magnesium",),
        "signs": ("muscle_pain", "cramps", "insomnia", "palpitations", "headache"),
        "risk": {},
        "touches": ("muscles", "sleep", "nerves", "heart rhythm"), "organs": ("skeleton_muscles", "heart"),
        "foods": ("nuts and seeds", "whole grains (ragi, bajra)", "green leafy vegetables", "legumes"),
        "ask": "Palpitations are worth a doctor's look first. Do not start magnesium supplements without asking, especially with kidney problems.",
    },
    "zinc": {
        "name": "Zinc", "markers": ("zinc",),
        "signs": ("hair_loss", "mouth_ulcer", "fatigue"),
        "risk": {"diet": ("vegetarian", "vegan", "jain")},
        "touches": ("immunity", "skin", "hair", "taste"), "organs": ("skin",),
        "foods": ("pulses", "seeds (pumpkin, sesame)", "nuts", "whole grains", "curd"),
        "ask": None,
    },
    "iodine_thyroid": {
        "name": "Thyroid (TSH)", "markers": ("tsh", "t3", "t4", "thyroid", "iodine"),
        "signs": ("fatigue", "constipation", "hair_loss", "low_mood", "palpitations", "insomnia"),
        "risk": {"female_over": 30},
        "touches": ("energy", "mood", "weight", "cycle", "hair"), "organs": ("thyroid",),
        "foods": ("iodised salt", "milk and curd", "eggs"),
        "ask": "Thyroid changes are common and easy to check with a TSH test. Do not take thyroid or iodine supplements without a test.",
    },
    "blood_sugar": {
        "name": "Blood sugar (HbA1c)", "markers": ("hba1c", "a1c", "glucose", "sugar"),
        "signs": ("fatigue", "frequent_urination", "blurred_vision"),
        "risk": {"age_gte": 35},
        "touches": ("energy", "eyes", "kidneys", "heart"), "organs": ("pancreas",),
        "foods": ("whole grains", "dal and beans", "vegetables", "fewer sugary drinks"),
        "ask": "A fasting sugar or HbA1c test is quick. If you already have a diagnosis, follow your doctor's plan.",
    },
    "hormones": {
        "name": "Hormones (cycle, PCOS, testosterone)", "markers": ("estradiol", "oestrogen", "estrogen", "progesterone", "testosterone", "lh", "fsh", "prolactin", "amh", "cortisol"),
        "signs": ("hair_loss", "low_mood", "insomnia", "unusual_bleeding", "spotting"),
        "risk": {"irregular_periods": True},
        "touches": ("cycle", "mood", "sleep", "skin", "hair"), "organs": ("uterus", "thyroid"),
        "foods": ("balanced meals", "enough protein", "fibre"),
        "ask": "Hormone tests depend on the day of your cycle. Your doctor can tell you which day and which tests make sense.",
    },
}


def _marker_hit(test_name: str, markers: Iterable[str]) -> bool:
    words = test_name.lower().replace("-", " ").split()
    text = " ".join(words)
    return any((m in text) if len(m) > 3 else (m in words) for m in markers)


def lab_status(lab: dict) -> str | None:
    """"below" or "above" the range the person entered, "within", or None when there is no number or no range."""
    value, lo, hi = lab.get("value"), lab.get("reference_min"), lab.get("reference_max")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    if isinstance(lo, (int, float)) and value < lo:
        return "below"
    if isinstance(hi, (int, float)) and value > hi:
        return "above"
    return "within" if isinstance(lo, (int, float)) or isinstance(hi, (int, float)) else None


def latest_lab(labs: Iterable[dict], markers: Iterable[str]) -> dict | None:
    hits = [lab for lab in labs if _marker_hit(str(lab.get("test_name") or ""), markers)]
    return max(hits, key=lambda lab: str(lab.get("tested_at") or "")) if hits else None


def _risk_reasons(key: str, p: dict) -> list[str]:
    risk, out = NUTRIENTS[key]["risk"], []
    if p.get("diet") in risk.get("diet", ()):
        out.append(f"your eating style ({str(p['diet']).replace('-', ' ')}) can make it easier to run low")
    if risk.get("heavy_periods") and p.get("heavy_periods"):
        out.append("you have logged heavy bleeding")
    if risk.get("pregnancy") and p.get("pregnancy"):
        out.append("needs rise in pregnancy")
    if isinstance(p.get("age"), int) and isinstance(risk.get("age_gte"), int) and p["age"] >= risk["age_gte"]:
        out.append(f"it becomes a little more common from about {risk['age_gte']}")
    if risk.get("female_over") and p.get("body") == "female" and isinstance(p.get("age"), int) and p["age"] >= risk["female_over"]:
        out.append("thyroid changes are more common in women over 30")
    if risk.get("little_sun") and p.get("little_sun"):
        out.append("you spend little time in daylight")
    if risk.get("irregular_periods") and p.get("irregular_periods"):
        out.append("you said your periods are irregular")
    return out


def nudges(profile: dict[str, Any], labs: Iterable[dict] = ()) -> dict[str, Any]:
    """The soft nudges for one person. `profile` keys (all optional): diet, body, age, pregnancy, heavy_periods, irregular_periods,
    little_sun, concepts {concept: days}, avoid_topics. Returns {"nudges": [...], "labs_noted": [...], "gaps": [...]}."""
    labs = list(labs)
    concepts = profile.get("concepts") or {}
    out, noted, gaps = [], [], []
    for key, spec in NUTRIENTS.items():
        lab = latest_lab(labs, spec["markers"])
        status = lab_status(lab) if lab else None
        if lab and status in ("below", "above"):
            noted.append({"id": key, "nutrient": spec["name"], "status": status, "test_name": lab.get("test_name"), "value": lab.get("value"),
                          "reference_min": lab.get("reference_min"), "reference_max": lab.get("reference_max"), "tested_at": lab.get("tested_at"),
                          "sentence": f"Your logged {lab.get('test_name')} is {status} the range you entered. Worth showing your doctor."})
        if status is not None:
            continue                     # a result with a range is the answer (noted above if outside it); no nudge to ask for the same test
        signs = [s for s in spec["signs"] if concepts.get(s, 0) >= DAYS_FOR_SIGN]
        risks = _risk_reasons(key, profile)
        points = len(signs) + len(risks)
        if len(signs) < 1 or points < 2:
            continue                     # at least one sign, and something more; risk factors alone never nudge
        reasons = [f"you mentioned {s.replace('_', ' ')} on several days" for s in signs] + risks
        out.append({
            "id": key, "nutrient": spec["name"], "how_sure": "medium" if points >= 4 else "low",
            "sentence": f"It might be worth asking about a blood test for {spec['name'].lower()}.",
            "reasons": reasons[:4], "touches": list(spec["touches"]), "foods": list(spec["foods"]), "ask": spec["ask"],
            "organs": list(spec["organs"]), "points": points,
            "gap": f"No recent {spec['name'].lower()} result is logged." if lab is None else None,
            "not": "This is not a diagnosis. Many things cause these signs, and a test is the only way to know.",
        })
    out.sort(key=lambda n: -n["points"])
    for n in out:
        n.pop("points")
        if n["gap"]:
            gaps.append(n["gap"])
    return {"nudges": out[:MAX_NUDGES], "labs_noted": noted, "gaps": gaps[:MAX_NUDGES]}


def chat_sentence(result: dict[str, Any]) -> str:
    """At most one sentence for the chat context, or "" when there is nothing to say."""
    items = result.get("nudges") or []
    if not items:
        return ""
    top = items[0]
    return f"Possible gentle mention (only if relevant, never as a diagnosis): {top['sentence'].lower()[:-1]}, because {top['reasons'][0]}."
