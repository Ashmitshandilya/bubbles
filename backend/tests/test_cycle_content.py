"""cycle_content: the chip catalogue, search, education and copy hygiene (kind, hedged, never diagnostic, never contraception)."""
from __future__ import annotations

import re

import pytest

import clinical_constants as K
import cycle_content as C

GROUP_IDS = {g for g, _ in C.CHIP_GROUPS}
SIGNALS = {"symptom", "mood_positive", "mood_negative", "positive", "neutral", "lifestyle"}
MODES = {"track", "birth_control", "conceive", "pregnancy", "postpartum", "perimenopause"}


def test_catalogue_is_big_unique_and_well_formed():
    ids = [c["id"] for c in C.CHIP_CATALOGUE]
    assert len(ids) >= 120 and len(set(ids)) == len(ids) and set(C.CHIP_BY_ID) == set(ids)
    for chip in C.CHIP_CATALOGUE:
        assert set(chip) == {"id", "label", "group", "keywords", "signal", "disturbs_bbt"}
        assert re.fullmatch(r"[a-z][a-z0-9_]*", chip["id"]) and chip["label"].strip()
        assert chip["group"] in GROUP_IDS and chip["signal"] in SIGNALS and isinstance(chip["disturbs_bbt"], bool)
        assert 1 <= len(chip["keywords"]) <= 6 and all(k == k.lower() for k in chip["keywords"])
    for group in GROUP_IDS:
        assert sum(c["group"] == group for c in C.CHIP_CATALOGUE) >= 4, group


def test_core_chips_exist_with_sensible_signals():
    required = ("bloating breast_tenderness nausea acne constipation diarrhoea cravings_sweet cravings_salty low_appetite headache fatigue insomnia "
                "anxious irritable sad calm happy energetic motivated brain_fog mood_swings hot_flashes night_sweats exercised alcohol caffeine "
                "stress_high travel illness fever late_night poor_sleep took_painkiller took_supplement dizzy joint_pain back_pain hair_loss "
                "oily_skin dry_skin gas heartburn water_retention").split()
    missing = [i for i in required if i not in C.CHIP_BY_ID]
    assert not missing, missing
    assert C.CHIP_BY_ID["bloating"]["signal"] == "symptom" and C.CHIP_BY_ID["happy"]["signal"] == "mood_positive"
    assert C.CHIP_BY_ID["irritable"]["signal"] == "mood_negative"


def test_only_temperature_disturbing_chips_are_marked():
    marked = {c["id"] for c in C.CHIP_CATALOGUE if c["disturbs_bbt"]}
    assert len(marked) >= 6 and {"illness", "fever", "alcohol", "late_night", "poor_sleep"} <= marked
    assert not marked & {"happy", "bloating", "calm", "cramps"}


def test_search_matches_label_keywords_and_prefixes():
    assert any(c["id"] == "bloating" for c in C.search_chips("tummy"))
    assert any(c["id"] == "bloating" for c in C.search_chips("BLOAT"))
    assert C.search_chips("bloating")[0]["id"] == "bloating"          # exact label ranks first
    assert all(c["group"] == "mood" for c in C.search_chips("", group="mood")) and C.search_chips("", group="mood")
    assert len(C.search_chips(None)) == min(60, len(C.CHIP_CATALOGUE)) and len(C.search_chips(None, limit=1000)) == len(C.CHIP_CATALOGUE)
    assert C.search_chips("zzzzzz") == [] and len(C.search_chips(None, limit=0)) == 1


@pytest.mark.parametrize("query", ["%", "'", "x" * 500, None, "", "  ", "[", "\\", "\u0000", "SELECT * FROM chips;--"])
def test_search_never_raises(query):
    assert isinstance(C.search_chips(query), list)
    assert isinstance(C.chips_by_group(query), list)


def test_chips_by_group_keeps_display_order_and_filters():
    groups = C.chips_by_group()
    assert [g["id"] for g in groups] == [g for g, _ in C.CHIP_GROUPS if any(c["group"] == g for c in C.CHIP_CATALOGUE)]
    assert sum(len(g["chips"]) for g in groups) == len(C.CHIP_CATALOGUE)
    only = C.chips_by_group("tummy", "body")
    assert [g["id"] for g in only] == ["body"] and any(c["id"] == "bloating" for c in only[0]["chips"])
    assert C.chips_by_group("zzzzzz") == []


def test_weather_lines_cover_every_tone_and_phase():
    assert set(C.WEATHER_LINES) == {"bright", "steady", "heavier"}
    for tone, phases in C.WEATHER_LINES.items():
        assert set(phases) == {"menstrual", "follicular", "ovulatory", "luteal", "none"}
        for phase, lines in phases.items():
            assert len(lines) >= 2 and all(0 < len(line) <= 110 for line in lines), (tone, phase)


def test_phase_and_mode_labels():
    assert set(C.PHASE_INFO) == {"menstrual", "follicular", "ovulatory", "luteal"}
    assert all(p["label"] and len(p["summary"]) <= 200 for p in C.PHASE_INFO.values())
    assert set(C.MODE_LABELS) == MODES


def test_education_articles():
    arts = C.EDUCATION_ARTICLES
    assert len(arts) >= 16 and len({a["id"] for a in arts}) == len(arts)
    for a in arts:
        assert a["label"] == C.GENERAL_KNOWLEDGE_LABEL and a["source_class"] == "EXTERNAL_KNOWLEDGE"
        assert 0 < len(a["summary"]) <= 160 and 3 <= len(a["body"]) <= 6 and all(0 < len(p) <= 420 for p in a["body"])
        assert a["modes"] and set(a["modes"]) <= MODES
    assert len(C.articles()) == len(arts)
    preg = C.articles(mode="pregnancy")
    assert 0 < len(preg) <= len(arts) and all("pregnancy" in a["modes"] for a in preg)
    assert C.articles(topic="pain") and isinstance(C.articles(topic="pain")[0]["body"], list)
    assert C.articles(topic="zzzzzz") == [] and C.articles(mode="nonsense") == []


def test_pregnancy_and_postpartum_copy():
    assert set(C.PREGNANCY_WEEK_NOTES) == set(range(1, 43)) and all(0 < len(n) <= 170 for n in C.PREGNANCY_WEEK_NOTES.values())
    assert set(C.TRIMESTER_NOTES) == {1, 2, 3} and set(C.PREGNANCY_NEXT_STEPS) == {1, 2, 3}
    assert "urgent" in C.PREGNANCY_URGENT_NOTE.lower()
    assert {"lochia", "settling", "low_confidence"} <= set(C.POSTPARTUM_NOTES)
    assert "urgent" in C.POSTPARTUM_NOTES["lochia"].lower()


def test_notice_text_is_exact():
    assert C.NOT_CONTRACEPTION_NOTICE == ("These are estimates from your own logs. They are not birth control and can be wrong, "
                                          "so do not rely on them to prevent pregnancy.")


def _strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from _strings(k)
            yield from _strings(v)
    elif isinstance(obj, (list, tuple, set, frozenset)):
        for v in obj:
            yield from _strings(v)


def test_copy_hygiene_across_the_whole_module():
    everything = [s for name in C.__all__ for s in _strings(getattr(C, name))]
    assert len(everything) > 1000
    banned = [*K.FORBIDDEN_ADVICE, "safe days", "safe period", "guarantee", "you have pcos", "you have endometriosis", "you are pregnant"]
    for text in everything:
        low = text.lower()
        for phrase in banned:
            assert phrase not in low, (phrase, text)
        if "diagnos" in low:
            assert " not " in f" {low} " or "n't" in low or "cannot" in low, text
        if "birth control" in low and "prevent" in low:
            assert " not " in f" {low} ", text
        assert "!!" not in text and "failure" not in low and "abnormal" not in low, text
