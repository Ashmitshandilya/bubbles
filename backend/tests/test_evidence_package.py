"""Orchestrator contract: planning, separation of information kinds, abstention and the audit trail."""
import calc_core as cc
import correlation_core as co
import evidence_package as ep


def test_plan_greeting_pulls_nothing_but_safety():
    p = ep.plan_task("hello!")
    assert p["intent"] == "greeting" and p["safety"] and not any(p[k] for k in ("personal_context", "calculation", "rag", "patterns"))


def test_plan_routes_engines_by_task():
    assert ep.plan_task("What is the normal range for ferritin?")["rag"] and not ep.plan_task("What is the normal range for ferritin?")["personal_context"]
    q = ep.plan_task("What is my BMI?")
    assert q["calculation"] and q["personal_context"]
    assert ep.plan_task("Why am I always tired after poor sleep?")["patterns"]
    assert ep.plan_task("anything")["safety"] is True


def test_calculation_that_cannot_be_computed_makes_the_package_unanswerable_and_explains():
    bmi = cc.calc_bmi(70, 20).to_dict()                                   # invalid height
    pkg = ep.build_package(plan=ep.plan_task("What is my BMI?"), calculations=[bmi])
    assert pkg["sufficiency"]["answerable"] is False and any("invalid_input" in u for u in pkg["uncertainties"])
    assert "INSUFFICIENT" in ep.render_for_model(pkg)


def test_kinds_of_information_stay_separate_and_are_labelled():
    ok = cc.calc_bmi(70, 170).to_dict()
    ev = [{"chunk_id": 7, "document_id": "d1", "title": "Ferritin", "source_name": "MedlinePlus", "source_url": "https://m", "evidence_level": "moderate", "policy": "no_diagnosis_explain_ranges"}]
    pkg = ep.build_package(plan=ep.plan_task("What does my ferritin mean?"), personal_facts=[{"concept": "fatigue", "assertion": "present", "temporal": "current"}],
                           calculations=[ok], evidence=ev)
    txt = ep.render_for_model(pkg)
    assert "USER-REPORTED FACTS" in txt and "CALCULATED (bmi v1.0" in txt and "GENERAL EVIDENCE (not about the user)" in txt
    assert pkg["retrieved_evidence"][0]["origin"] == "external_general_knowledge" and pkg["personal_facts"][0]["origin"] == "user_reported"
    assert 7 in pkg["facts_used"] and "bmi" in pkg["facts_used"] and "fatigue" in pkg["facts_used"]
    assert pkg["engine_versions"]["calc_versions"] == ["bmi@1.0"]


def test_only_real_patterns_are_surfaced_with_their_limits_and_abstention_is_explicit():
    weak = co.assess_pairs("sleep->energy", [(1, 2)] * 3).to_dict()        # insufficient_data
    pkg = ep.build_package(plan=ep.plan_task("Why am I always tired? My sleep is bad"), patterns=[weak])
    assert pkg["observed_patterns"] == [] and any("Not enough reliable data" in u for u in pkg["uncertainties"])
    good = co.analyze_batch([("sleep->energy", [(float(i % 12), float(i % 12) + (i % 3) * 0.1) for i in range(40)])])[0].to_dict()
    pkg2 = ep.build_package(plan=ep.plan_task("Why am I always tired? My sleep is bad"), patterns=[good])
    assert pkg2["observed_patterns"] and any("does not show that one thing causes" in x for x in pkg2["limitations"])


def test_missing_evidence_is_acknowledged_not_papered_over():
    pkg = ep.build_package(plan=ep.plan_task("Is it normal to have a headache before my period?"))
    assert any("Do not invent citations" in x for x in pkg["limitations"]) and pkg["sufficiency"]["answerable"] is False


def test_questions_quotes_and_other_people_are_not_personal_facts():
    facts = [{"concept": "headache", "assertion": "question", "experiencer": "self"}, {"concept": "chest_pain", "assertion": "quoted"},
             {"concept": "fever", "assertion": "present", "experiencer": "other"}, {"concept": "fatigue", "assertion": "present", "experiencer": "self"},
             {"concept": "nausea", "assertion": "negated"}]
    pkg = ep.build_package(plan=ep.plan_task("my fatigue"), personal_facts=facts)
    assert [f["concept"] for f in pkg["personal_facts"]] == ["fatigue", "nausea"]


def test_real_extractor_output_keeps_assertion_and_time():
    import health_semantics as hs
    facts = [f.to_dict() for f in hs.analyze("I had chest pain last month. I do not have a fever.")]
    pkg = ep.build_package(plan=ep.plan_task("my chest pain"), personal_facts=facts)
    got = {f["concept"]: (f["assertion"], f["temporal"]) for f in pkg["personal_facts"]}
    assert got["chest_pain"] == ("present", "past") and got["fever"][0] == "negated"
