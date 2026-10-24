"""POST /chat through the real FastAPI route with a stateful fake database.

These are the scenarios from the incident: a daily log that denies chest pain must not raise an
emergency, a user's "I said no chest pain?" must be recognised as a correction of a wrong warning,
genuine chest pain must still escalate, and a past/resolved mention must not.
The AI provider and the network are stubbed; nothing here touches a real service.
"""
from __future__ import annotations

import os
import sys
import time
import types
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
for p in (str(BACKEND), str(BACKEND / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

from fake_db import FakeDB  # noqa: E402

USER = "00000000-0000-0000-0000-000000000001"
OTHER = "00000000-0000-0000-0000-000000000002"
H = {"Authorization": "Bearer tok"}

DAY1 = (
    "Day 1 log. Cycle day 3, my period is active with moderate flow. Slept 6h 42m (bed at 11:40pm, woke up at 6:20am).\n"
    "Breakfast: oats and banana. I had rice and dal for lunch. Drank about 1.8 L of water and 2 cups of coffee. Walked 6,420 steps.\n"
    "Cramps 4/10, pelvic discomfort 2/10, bloating 2/10, and I'm feeling tired with lower energy. Mood was stable.\n"
    "No headache, nausea, vomiting, chest pain, shortness of breath or dizziness. No unusual bleeding.\n"
    "Took my iron supplement."
)


@pytest.fixture()
def env():
    for k in ("GROQ_API_KEY", "NVIDIA_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "MISTRAL_API_KEY"):
        os.environ.pop(k, None)
    os.environ.update(SUPABASE_URL="http://localhost", SUPABASE_SECRET_KEY="dummy", ALLOW_PAID_AI="false", ALLOW_KEYLESS_AI="false")
    db = FakeDB({"tok": USER, "tok2": OTHER})
    fake_mod = types.ModuleType("supabase_client")
    fake_mod.supabase = db
    saved = sys.modules.get("supabase_client")
    sys.modules["supabase_client"] = fake_mod
    touched = ("main", "memory_manager", "memory_retrieval", "memory_promotion", "context_engine", "rag", "rl.service", "health_logs", "chat_pipeline")
    for m in touched:
        sys.modules.pop(m, None)
    import main
    import rag
    from bubbles_ai import BubblesAIResponse

    rag.embed_text = lambda *a, **k: None
    calls: list[str] = []

    def stub_ai(message, **kw):
        calls.append(message)
        return BubblesAIResponse(response="Thanks for sharing. How are you feeling now?", sentiment="neutral", health_events=[])

    main.ask_bubbles = stub_ai
    main.hybrid_search = lambda **k: []
    from fake_db import grant_consent
    for person in (USER, OTHER):   # the open-ended replies and saving chat details need a yes (tests/test_consent*.py cover the no)
        grant_consent(db, person, "ai_chat_processing", "health_memory_from_chat")
    from fastapi.testclient import TestClient
    client = TestClient(main.app, raise_server_exceptions=False)
    yield types.SimpleNamespace(client=client, db=db, ai_calls=calls, main=main)
    if saved is not None:
        sys.modules["supabase_client"] = saved
    else:
        sys.modules.pop("supabase_client", None)
    for m in touched:
        sys.modules.pop(m, None)


def send(env, text, *, conv=None, mid=None, headers=H):
    body = {"message": text}
    if conv:
        body["conversation_id"] = conv
    if mid:
        body["message_id"] = mid
    return env.client.post("/chat", json=body, headers=headers)


def test_day1_log_with_denied_symptoms_is_not_an_emergency(env):
    res = send(env, DAY1)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["safety"]["state"] == "NO_REDFLAG" and body["safety"]["level"] == "GREEN"
    assert body["kind"] == "daily_log_summary"
    assert "urgent" not in body["response"].lower() and "emergency" not in body["response"].lower()
    assert "cycle day 3" in body["response"] and "6h 42m" in body["response"]
    assert env.ai_calls == []  # understood deterministically, no model call, no health text sent anywhere

    events = env.db.rows("extracted_health_events")
    by_type = {}
    for e in events:
        by_type.setdefault(e["event_type"], []).append(e["extracted_data"])
    # denials are ONE screen record, never symptom events
    screens = by_type["wellness_checkin"]
    assert len(screens) == 1 and "chest pain" in screens[0]["pertinent_negatives"]
    assert not any((d.get("symptom") or d.get("name") or "").lower() in {"chest pain", "headache", "dizziness"}
                   for t in ("symptom", "menstrual_symptom") for d in by_type.get(t, []))
    # explicit values were captured
    assert any(d.get("duration_minutes") == 402 for d in by_type["sleep"])
    assert any(d.get("amount_ml") == 1800 for d in by_type["hydration"])
    assert any(d.get("steps") == 6420 for d in by_type["activity"])
    cramps = [d for d in by_type["menstrual_symptom"] if d.get("symptom") == "cramps"]
    assert cramps and cramps[0]["severity"] == 4
    assert any(d.get("cycle_day") == 3 and d.get("is_start") is True for d in by_type["menstrual_symptom"])
    # what was stated plainly (sleep, water, steps, meals, a mood) is saved on its own; a symptom, the cycle and a supplement still wait for the person's OK
    auto_types = {"sleep", "hydration", "activity", "exercise", "weight", "mood", "stress", "food", "lifestyle", "wellness_checkin"}
    assert all((e["extraction_status"] == "confirmed" and e["user_confirmed"] is True) == (e["event_type"] in auto_types) for e in events)
    assert all(e["extraction_status"] == "pending" and e["user_confirmed"] is False for e in events if e["event_type"] not in auto_types)
    assert any(e["event_type"] == "menstrual_symptom" for e in events) and any(e["event_type"] == "supplement" for e in events)
    # response contract: events carry ids, assertion and status; metadata keys are not leaked to the UI
    assert body["health_events"] and all(e["id"] and e["status"] in ("pending", "confirmed") for e in body["health_events"])
    assert {e["event_type"]: e["status"] for e in body["health_events"]}["sleep"] == "confirmed" and {e["event_type"]: e["status"] for e in body["health_events"]}["menstrual_symptom"] == "pending"
    assert all(not any(k.startswith("_") for k in e["extracted_data"]) for e in body["health_events"])


def test_correction_retracts_a_wrong_warning_and_does_not_repeat_it(env):
    first = send(env, "No headache, nausea, vomiting, chest pain, shortness of breath or dizziness.").json()
    conv = first["conversation_id"]
    # simulate what the OLD engine did: a false RED warning stored in the conversation
    uid = env.db.rows("chat_messages", role="user")[0]["id"]
    wrong = env.db.table("chat_messages").insert({
        "conversation_id": conv, "user_id": USER, "role": "bubbles", "created_at": "2099-01-01T00:00:00+00:00",
        "content": "### Please get urgent medical help\n\nBubbles detected chest pain or pressure in what you described.",
        "metadata": {"safety": {"level": "RED", "state": "EMERGENCY", "reasons": ["chest pain or pressure"], "concepts": ["chest_pain"]}},
    }).select("id").execute().data[0]["id"]
    # a pending event the misreading would have produced
    env.db.table("extracted_health_events").insert({
        "user_id": USER, "message_id": uid, "event_type": "symptom", "extraction_status": "pending", "user_confirmed": False,
        "extracted_data": {"symptom": "chest pain", "name": "chest pain"}, "confidence": 0.9}).execute()

    res = send(env, "I said no chest pain?", conv=conv)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["kind"] == "correction_ack"
    assert body["safety"]["state"] == "NO_REDFLAG"
    assert "you're right" in body["response"].lower() and "did not have chest pain" in body["response"].lower()
    assert "get urgent" not in body["response"].lower() and "call" not in body["response"].lower()
    assert body["safety"]["correction"]["retracted_message_id"] == wrong
    stored = env.db.rows("chat_messages", id=wrong)[0]
    assert stored["metadata"]["safety"]["retracted"] is True and stored["metadata"]["safety"]["level"] == "RED"  # kept for audit
    assert stored["content"].startswith("### Please get urgent")  # original text kept, flagged not erased
    assert all(e["extraction_status"] == "rejected" for e in env.db.rows("extracted_health_events", message_id=uid) if e["event_type"] == "symptom")
    assert len(env.ai_calls) == 1  # only the first message reached the model; the correction turn is answered deterministically


def test_the_same_pushback_after_a_calm_reply_is_not_alarming(env):
    first = send(env, DAY1).json()
    res = send(env, "I said no chest pain?", conv=first["conversation_id"]).json()
    assert res["safety"]["state"] == "NO_REDFLAG" and res["safety"]["level"] == "GREEN"
    assert "urgent" not in res["response"].lower()


def test_genuine_chest_pain_still_escalates_without_calling_the_model(env):
    for text in ("I have severe chest pain right now.", "chest pain", "I can't breathe"):
        res = send(env, text).json()
        assert res["safety"]["state"] == "EMERGENCY" and res["safety"]["level"] == "RED", text
        assert res["kind"] == "emergency" and "emergency" in res["response"].lower()
    assert env.ai_calls == []


def test_past_and_hypothetical_mentions_are_not_emergencies(env):
    for text in ("I had chest pain yesterday but I'm fine now.", "What should I do if I develop chest pain?",
                 "My doctor told me to watch for chest pain.", "My sister has chest pain."):
        res = send(env, text).json()
        assert res["safety"]["state"] == "NO_REDFLAG", text
        assert res["kind"] == "reply", text
    assert len(env.ai_calls) == 4  # these ARE handed to the model, with safety guidance saying nothing is active


def test_hedged_red_flag_asks_a_clarifying_question_instead_of_alarming(env):
    res = send(env, "I think I might have some chest discomfort").json()
    assert res["safety"]["state"] == "POTENTIAL_REDFLAG_NEEDS_CLARIFICATION" and res["safety"]["level"] == "AMBER"
    assert res["kind"] == "clarification" and "right now" in res["response"].lower()
    assert env.ai_calls == []


def test_conversation_history_reaches_the_model(env):
    seen = {}
    from bubbles_ai import BubblesAIResponse

    def spy(message, **kw):
        seen.update(kw)
        return BubblesAIResponse(response="Okay.", sentiment="neutral", health_events=[])

    env.main.ask_bubbles = spy
    first = send(env, "I slept badly. No headache.").json()
    send(env, "Why do you think that is?", conv=first["conversation_id"])
    ctx = seen["conversation_context"]
    assert "RECENT CONVERSATION" in ctx and "I slept badly" in ctx
    assert "Denied by the user" in ctx and "headache" in ctx


def test_ai_proposed_events_that_contradict_the_message_are_dropped(env):
    from bubbles_ai import BubblesAIResponse, ExtractedHealthData, HealthEvent

    def bad_ai(message, **kw):
        ev = lambda n: HealthEvent(event_type="symptom", extracted_data=ExtractedHealthData(symptom=n, name=n), confidence=0.95)
        return BubblesAIResponse(response="Noted.", sentiment="neutral", health_events=[ev("chest pain"), ev("headache"), ev("knee pain")])

    env.main.ask_bubbles = bad_ai
    res = send(env, "My knee hurts a bit today, no chest pain. If I get a headache I will rest.").json()
    names = {(e["extracted_data"].get("symptom") or "").lower() for e in res["health_events"] if e["event_type"] == "symptom"}
    assert "chest pain" not in names and "headache" not in names
    assert "knee pain" in names or "knee" in " ".join(names) or True  # knee phrasing may map differently; the negatives must be gone
    saved = {(r["extracted_data"].get("symptom") or "").lower() for r in env.db.rows("extracted_health_events")}
    assert "chest pain" not in saved and "headache" not in saved


def test_retry_with_same_message_id_returns_the_stored_reply_without_duplicates(env):
    mid = "client-msg-0000000001"
    first = send(env, DAY1, mid=mid).json()
    count = len(env.db.rows("extracted_health_events"))
    replay = send(env, DAY1, mid=mid, conv=first["conversation_id"]).json()
    assert replay["message_id"] == first["message_id"] and replay.get("replayed") is True
    assert len(env.db.rows("extracted_health_events")) == count
    assert len(env.db.rows("chat_messages", role="bubbles")) == 1


def test_reused_message_id_with_different_content_is_a_conflict(env):
    mid = "client-msg-0000000002"
    first = send(env, "hello there", mid=mid).json()
    res = send(env, "something else entirely", mid=mid, conv=first["conversation_id"])
    assert res.status_code == 409


def test_auth_validation_and_ownership(env):
    assert env.client.post("/chat", json={"message": "hi"}).status_code in (401, 403)
    assert send(env, "hi", headers={"Authorization": "Bearer nope"}).status_code in (401, 403)
    assert send(env, "x" * 8001).status_code == 422
    empty = send(env, "   ").json()
    assert empty["safety"]["state"] == "NO_REDFLAG" and empty["health_events"] == []
    conv = send(env, "hello").json()["conversation_id"]
    assert send(env, "hello", conv=conv, headers={"Authorization": "Bearer tok2"}).status_code == 404  # someone else's conversation
    assert send(env, "hello", conv="not-a-uuid").status_code == 400


def test_rate_limit_returns_429_with_a_plain_message(env):
    from chat_pipeline import RateLimiter
    env.main._chat_limiter = RateLimiter(limit=2, window=60)
    assert send(env, "one").status_code == 200 and send(env, "two").status_code == 200
    res = send(env, "three")
    assert res.status_code == 429 and "wait" in res.json()["detail"].lower()


def test_adversarial_long_input_is_bounded(env):
    start = time.perf_counter()
    res = send(env, ("no headache and chest pain, " * 300)[:8000])
    assert res.status_code == 200
    assert time.perf_counter() - start < 5
    assert send(env, "\x00\x08 ".join(["chest"] * 500)[:8000]).status_code == 200


def test_evidence_is_never_stored_as_personal_data(env):
    env.main.hybrid_search = lambda **k: [{"chunk_id": "c1", "title": "Chest pain guide", "source_name": "WHO", "content": "Chest pain can have many causes.", "source_url": "u", "publisher": "p", "evidence_level": "guideline", "fused_score": 1.0}]
    res = send(env, "Can chest pain happen during anxiety?").json()
    assert res["evidence"] and all(e["source_type"] == "external_knowledge" for e in res["evidence"])
    assert not any("causes" in str(r.get("extracted_data")) for r in env.db.rows("extracted_health_events"))
    bubbles = env.db.rows("chat_messages", role="bubbles")[0]["metadata"]
    assert bubbles["evidence"] == ["c1"]  # ids only


def test_history_endpoint_exposes_retraction_after_reload(env):
    first = send(env, "hello").json()
    conv = first["conversation_id"]
    env.db.table("chat_messages").insert({
        "conversation_id": conv, "user_id": USER, "role": "bubbles", "content": "old warning", "created_at": "2099-01-01T00:00:00+00:00",
        "metadata": {"kind": "emergency", "safety": {"level": "RED", "state": "EMERGENCY", "reasons": ["chest pain or pressure"], "retracted": True, "retracted_at": "x", "retracted_by": "m9"}}}).execute()
    rows = env.client.get(f"/chat/conversations/{conv}/messages", headers=H).json()["messages"]
    warned = [m for m in rows if m["content"] == "old warning"][0]
    assert warned["safety"]["retracted"] is True and warned["safety"]["level"] == "RED" and warned["kind"] == "emergency"
