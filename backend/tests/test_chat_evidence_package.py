"""POST /chat records an audit trail of which engines ran and which facts/evidence were used (no user text, ids and labels only).
Uses the real route with the stateful fake database from test_chat_http_flow."""
import json

from test_chat_http_flow import env, send  # noqa: F401  (pytest fixture + helper)

ROW = {"chunk_id": "c1", "document_id": "d1", "title": "Headache and periods", "source_name": "NHS (England)", "content": "Hormone changes can trigger headaches.",
       "source_url": "https://www.nhs.uk/x", "publisher": "NHS", "evidence_level": "moderate", "policy": "education_only_refer_clinician"}


def bubbles_meta(env):
    return env.db.rows("chat_messages", role="bubbles")[0]["metadata"]


def test_ai_route_reply_stores_the_evidence_package_audit_trail(env):
    env.main.hybrid_search = lambda **k: [dict(ROW)]
    message = "Is it normal to have a headache before my period?"
    res = send(env, message).json()
    assert res["kind"] != "emergency"
    pkg = bubbles_meta(env)["evidence_package"]
    assert "rag" in pkg["engines"] and "safety" in pkg["engines"] and "c1" in pkg["facts_used"]
    assert pkg["evidence"] == [{"chunk_id": "c1", "handling": "education_only_refer_clinician"}]
    assert pkg["answerable"] is True and pkg["version"] == "1.0"
    assert "headache before my period" not in json.dumps(pkg)               # ids/labels only, never the user's words


def test_no_evidence_is_recorded_as_unanswerable_not_hidden(env):
    env.main.hybrid_search = lambda **k: []
    send(env, "Is it normal to have a headache before my period?")
    pkg = bubbles_meta(env)["evidence_package"]
    assert pkg["answerable"] is False and "evidence" in pkg["needs"]


def test_emergency_route_still_skips_the_model_and_has_no_package(env):
    res = send(env, "I have severe chest pain right now.").json()
    assert res["kind"] == "emergency" and env.ai_calls == []
    assert "evidence_package" not in bubbles_meta(env)


def test_a_failure_in_the_package_never_breaks_the_reply(env):
    def boom(**k):
        raise RuntimeError("package bug")
    env.main.build_package = boom
    res = send(env, "Is it normal to have a headache before my period?")
    assert res.status_code == 200 and res.json()["response"]
    assert "evidence_package" not in bubbles_meta(env)


def test_audit_evidence_count_matches_results_and_retrieved_text_never_reaches_safety(env):
    rows = [dict(ROW), dict(ROW, chunk_id="c2", content="SECRET-RETRIEVED-TEXT")]
    env.main.hybrid_search = lambda **k: [dict(r) for r in rows]
    send(env, "Is it normal to have a headache before my period?")
    pkg = bubbles_meta(env)["evidence_package"]
    assert [e["chunk_id"] for e in pkg["evidence"]] == ["c1", "c2"]
    assert "SECRET-RETRIEVED-TEXT" not in json.dumps(pkg)
    assert "SECRET-RETRIEVED-TEXT" not in json.dumps(bubbles_meta(env).get("safety", {}))
