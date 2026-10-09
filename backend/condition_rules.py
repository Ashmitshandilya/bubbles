"""Turn the free-text conditions / medicines a user recorded into rule tags. Pure; keyword lists live in clinical_constants."""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Iterable

import clinical_constants as K


@lru_cache(maxsize=512)
def _pattern(words: tuple[str, ...]) -> re.Pattern[str] | None:
    words = tuple(w for w in words if w)
    if not words:
        return None
    # long stems may carry a suffix (hypothyroid -> hypothyroidism); short ones must match a whole word (ckd, copd, pcos)
    parts = [re.escape(w) + (r"(?![a-z0-9])" if len(w) < 6 else "") for w in sorted(words, key=len, reverse=True)]
    return re.compile(r"(?<![a-z0-9])(?:" + "|".join(parts) + ")")


def _hits(rules: dict[str, tuple[str, ...]], texts: list[str]) -> list[str]:
    found = []
    for label, words in rules.items():
        pat = _pattern(tuple(words))
        if pat and any(pat.search(t) for t in texts):
            found.append(label)
    return found


def _norm(items: Iterable[str] | None) -> list[str]:
    return [str(i).lower().replace("_", " ").strip() for i in (items or []) if i and str(i).strip()][:200]


def classify(conditions: Iterable[str] | None = None, medications: Iterable[str] | None = None) -> dict:
    """{blocking: [...], cautions: [...], glp1, fluid_restricted, kidney, anticoagulant, insulin_like, pcos, diabetes, hypertension,
    asthma, joint, osteoporosis, pregnancy_hint, cycle_pill}. Labels are plain English for display."""
    conds, meds = _norm(conditions), _norm(medications)
    blocking = _hits(K.STRICT_BLOCKING_CONDITIONS, conds) + _hits(K.STRICT_BLOCKING_MEDICATIONS, meds)
    cautions = _hits(K.SOFT_CAUTION_CONDITIONS, conds)
    all_text = conds + meds

    def has(words: tuple[str, ...], texts: list[str]) -> bool:
        pat = _pattern(tuple(words))
        return bool(pat and any(pat.search(t) for t in texts))

    glp1 = has(K.GLP1_MEDICATIONS, meds)
    if glp1:
        cautions.append("GLP-1 medicine")
    return {
        "blocking": list(dict.fromkeys(blocking)),
        "cautions": list(dict.fromkeys(cautions)),
        "glp1": glp1,
        "fluid_restricted": has(K.FLUID_RESTRICTION_CONDITIONS, all_text),
        "kidney": "kidney disease" in blocking,
        "diabetes": "type 2 diabetes" in cautions or "type 1 diabetes" in blocking,
        "hypertension": "hypertension" in cautions or "uncontrolled hypertension" in blocking,
        "pcos": "pcos" in cautions,
        "asthma": "asthma" in cautions,
        "joint": "joint issue" in cautions,
        "osteoporosis": "osteoporosis" in cautions,
        "anaemia": "anaemia" in cautions,
        "pregnancy_hint": "pregnancy or breastfeeding" in blocking,
        "cycle_pill": has(K.CONTRACEPTIVE_PILL_KEYWORDS, meds),
    }
