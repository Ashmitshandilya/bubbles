import deficiency_map as d


def ids(result):
    return [n["id"] for n in result["nudges"]]


def test_signs_plus_a_risk_factor_make_a_soft_nudge_with_reasons_and_never_high():
    r = d.nudges({"diet": "vegetarian", "age": 28, "body": "female", "heavy_periods": True, "concepts": {"fatigue": 5, "hair_loss": 3}})
    assert ids(r)[0] == "iron" and len(r["nudges"]) <= d.MAX_NUDGES
    top = r["nudges"][0]
    assert top["how_sure"] in ("low", "medium") and "might be worth asking" in top["sentence"] and top["reasons"] and "not a diagnosis" in top["not"]
    assert top["gap"] == "No recent iron result is logged."


def test_a_risk_factor_alone_or_a_sign_alone_never_nudges():
    assert ids(d.nudges({"diet": "vegetarian", "concepts": {}})) == []
    assert ids(d.nudges({"concepts": {"fatigue": 9}})) == []
    assert ids(d.nudges({"diet": "vegetarian", "concepts": {"fatigue": 1}})) == []     # one day is not a pattern


def test_a_lab_in_range_silences_the_nudge_and_one_outside_is_stated_plainly():
    base = {"diet": "vegetarian", "heavy_periods": True, "concepts": {"fatigue": 5, "hair_loss": 3}}
    fine = d.nudges(base, [{"test_name": "Ferritin", "value": 60, "reference_min": 15, "reference_max": 150, "tested_at": "2026-10-01"}])
    assert "iron" not in ids(fine) and fine["labs_noted"] == []
    low = d.nudges(base, [{"test_name": "Ferritin", "value": 9, "reference_min": 15, "reference_max": 150, "tested_at": "2026-10-01"}])
    assert low["labs_noted"][0]["status"] == "below" and "below the range you entered" in low["labs_noted"][0]["sentence"]
    assert "iron" not in ids(low)


def test_a_lab_without_a_range_is_not_interpreted():
    assert d.lab_status({"value": 9}) is None
    assert d.lab_status({"value": "x", "reference_min": 1}) is None
    assert d.lab_status({"value": 5, "reference_min": 1, "reference_max": 4}) == "above"


def test_marker_matching_is_by_word_for_short_names():
    assert d.latest_lab([{"test_name": "Hb", "tested_at": "1"}], d.NUTRIENTS["iron"]["markers"])
    assert d.latest_lab([{"test_name": "Vitamin D 25-OH", "tested_at": "1"}], d.NUTRIENTS["vitamin_d"]["markers"])
    assert not d.latest_lab([{"test_name": "Hbsag", "tested_at": "1"}], d.NUTRIENTS["iron"]["markers"])


def test_the_chat_sentence_is_one_hedged_line_or_nothing():
    assert d.chat_sentence({"nudges": []}) == ""
    line = d.chat_sentence(d.nudges({"diet": "vegan", "concepts": {"fatigue": 4, "numbness": 3}}))
    assert line.startswith("Possible gentle mention") and line.count("\n") == 0 and "never as a diagnosis" in line


def test_no_text_diagnoses_or_doses():
    import json
    import re
    blob = json.dumps(d.NUTRIENTS).lower()
    assert not re.search(r"\d\s?(mg|mcg|iu|g)\b", blob)
    for bad in ("you have a deficiency", "you are deficient", "you are diagnosed", "should take", "start taking"):
        assert bad not in blob, bad


def test_the_loader_builds_nudges_from_symptoms_setup_answers_and_labs():
    from types import SimpleNamespace
    import nutrient_loader as NL

    class Q:
        def __init__(self, rows): self.rows = rows
        def select(self, *a, **k): return self
        def eq(self, *a, **k): return self
        def order(self, *a, **k): return self
        def limit(self, *a, **k): return self
        def execute(self): return SimpleNamespace(data=self.rows)

    class DB:
        def table(self, name):
            return Q([{"content": "I feel so tired, fatigue again", "created_at": "2026-10-01T10:00:00Z"},
                      {"content": "my hair is falling out and I feel exhausted", "created_at": "2026-10-03T10:00:00Z"},
                      {"content": "fatigue all day", "created_at": "2026-10-05T10:00:00Z"}] if name == "chat_messages" else [])

    NL._cache.clear()
    out = NL.compute(DB(), "u1")
    assert out["window_days"] == 90 and isinstance(out["nudges"], list) and out["labs_noted"] == []
    assert NL.cached("u1") is out
    assert NL.chat_block(DB(), "u1") in ("", NL.chat_block(DB(), "u1"))
