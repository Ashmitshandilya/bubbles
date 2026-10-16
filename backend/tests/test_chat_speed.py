"""The chat's speed work, proven by behaviour: fewer database trips, the same answers, honest stage numbers, and the stream's event order."""
from __future__ import annotations

import json

import pytest

import ops_telemetry
from fake_db import FakeDB
from test_chat_http_flow import H, USER, env, send  # noqa: F401  (env is a fixture)

AI_MESSAGE = "I have had a mild headache since morning, what could help?"


class Counting(FakeDB):
    """A FakeDB that remembers every (table, operation) pair it was asked for."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.log: list[tuple[str, str]] = []

    def table(self, name):
        query = super().table(name)
        original = query.execute

        def execute():
            self.log.append((name, query.op))
            return original()
        query.execute = execute
        return query


def _events(env):
    return [e for e in ops_telemetry.recent(0, 5000)]


def test_saving_no_events_touches_nothing():
    from chat_pipeline import persist_events

    class Untouchable:
        def table(self, name):
            raise AssertionError("database touched for an empty list")
    assert persist_events(Untouchable(), USER, "m1", []) == []


def _symptom(name="headache"):
    return {"event_type": "symptom", "extracted_data": {"name": name, "severity": 2, "_prov": {"key": f"k-{name}", "assertion": "present"}}, "confidence": 0.8}


def test_a_fresh_message_skips_the_duplicate_read_and_a_retry_does_not():
    from chat_pipeline import persist_events
    db = Counting({"tok": USER})
    first = persist_events(db, USER, "00000000-0000-0000-0000-00000000aaaa", [_symptom()], fresh=True)
    assert first[0]["id"] and ("extracted_health_events", "select") not in db.log
    db.log.clear()
    again = persist_events(db, USER, "00000000-0000-0000-0000-00000000aaaa", [_symptom()])   # a retry: the read finds it and saves nothing twice
    assert again == [] and ("extracted_health_events", "select") in db.log
    assert len(db.rows("extracted_health_events")) == 1


def test_a_new_message_is_one_insert_and_a_repeat_reads_the_winner_only_after_it_fails(env):
    main = env.main
    conv = main._ensure_conversation(USER, None, "hi")
    env.db.log = []
    original = env.db.table

    def table(name):
        query = original(name)
        run = query.execute

        def execute():
            env.db.log.append((name, query.op))
            return run()
        query.execute = execute
        return query
    env.db.table = table
    mid = "client-message-00000001"
    first_id, created = main._persist_chat_message(user_id=USER, conversation_id=conv, role="user", content="hello", client_message_id=mid, return_created=True)
    assert created and env.db.log == [("chat_messages", "insert")]          # no read before the write
    env.db.log.clear()
    again_id, created_again = main._persist_chat_message(user_id=USER, conversation_id=conv, role="user", content="hello", client_message_id=mid, return_created=True)
    assert again_id == first_id and created_again is False                  # the repeat finds the first one
    assert ("chat_messages", "select") in env.db.log
    with pytest.raises(Exception) as clash:
        main._persist_chat_message(user_id=USER, conversation_id=conv, role="user", content="something else", client_message_id=mid)
    assert getattr(clash.value, "status_code", None) == 409


def test_the_parallel_context_builder_returns_what_the_sequential_reads_would(env):
    import context_engine
    import memory_retrieval
    from event_filters import counts_as_observation
    db = env.db
    db.table("profiles").insert({"id": USER, "display_name": "Riya", "gender": "female", "timezone": "Asia/Kolkata"}).execute()
    db.table("user_preferences").insert({"user_id": USER, "language": "English"}).execute()
    for i, name in enumerate(["headache", "tiredness", "nausea"]):
        db.table("extracted_health_events").insert({
            "user_id": USER, "event_type": "symptom", "confidence": 0.8, "user_confirmed": True, "extraction_status": "confirmed",
            "extracted_data": {"name": name, "severity": 3, "_prov": {"assertion": "present", "subject": "self", "temporal": "current"}},
            "created_at": f"2026-10-1{i}T08:00:00+00:00"}).execute()
    db.table("memory_items").insert({"user_id": USER, "memory_type": "L1", "content": "Often wakes with a headache", "is_active": True,
                                     "updated_at": "2026-10-10T08:00:00+00:00", "source_id": "x"}).execute()
    context_engine.forget_profile(USER)
    got = context_engine.build_user_context(USER, "headache since morning")
    rows = memory_retrieval.fetch_event_rows(USER)
    expected_events = [context_engine._compact_event(r) for r in rows[:40] if counts_as_observation(r)][:20]
    assert got["recent_events"] == expected_events and len(expected_events) == 3
    assert got["profile"]["display_name"] == "Riya" and got["preferences"]["language"] == "English"
    assert got["pertinent_negatives"] == context_engine._denials(rows[:40])
    expected_memory = memory_retrieval.get_relevant_memories(user_id=USER, query="headache since morning", event_rows=rows,
                                                             memory_rows=memory_retrieval.fetch_memory_rows(USER))
    assert got["relevant_memories"] == expected_memory
    again = context_engine.build_user_context(USER, "headache since morning")      # second time the profile comes from the 60 s cache
    assert again["profile"] == got["profile"] and again["recent_events"] == got["recent_events"]


def test_a_just_saved_symptom_is_in_the_next_turns_context(env):
    import context_engine
    context_engine.build_user_context(USER, "hello")   # warms whatever is cached
    env.db.table("extracted_health_events").insert({
        "user_id": USER, "event_type": "symptom", "confidence": 0.8, "extraction_status": "pending",
        "extracted_data": {"name": "dizziness", "severity": 2, "_prov": {"assertion": "present", "subject": "self", "temporal": "current"}}}).execute()
    names = [e["data"].get("name") for e in context_engine.build_user_context(USER, "hello")["recent_events"]]
    assert "dizziness" in names


def test_a_slow_evidence_lookup_is_dropped_but_the_reply_still_goes_out(env, monkeypatch):
    import time as _t
    monkeypatch.setattr(env.main, "RAG_BUDGET_S", 0.5)
    env.main.hybrid_search = lambda **k: (_t.sleep(1.5), [{"chunk_id": "c1", "title": "Late", "content": "x"}])[1]
    started = _t.perf_counter()
    res = send(env, AI_MESSAGE)
    assert res.status_code == 200 and res.json()["evidence"] == [] and _t.perf_counter() - started < 1.4


def test_the_model_sees_at_most_the_three_sources_the_screen_shows(env):
    rows = [{"chunk_id": f"c{i}", "title": f"Page {i}", "source_name": "S", "publisher": "P", "source_url": f"https://e.org/{i}",
             "content": "word " * 600, "lexical_rank": 1, "semantic_rank": 1, "fused_score": 1.0 - i / 10} for i in range(6)]
    env.main.hybrid_search = lambda **k: rows
    seen = {}
    original = env.main.ask_bubbles

    def spy(message, **kw):
        seen.update(kw)
        return original(message, **kw)
    env.main.ask_bubbles = spy
    body = send(env, AI_MESSAGE).json()
    assert len(body["evidence"]) == 3
    context = seen["evidence_context"]
    assert context.count("Page ") == 3 and len(context) < 6000


def test_the_chat_event_carries_numeric_stage_timings_and_nothing_else(env):
    assert send(env, AI_MESSAGE).status_code == 200
    chat = [e for e in _events(env) if e["kind"] == "api" and e["data"].get("route") == "/chat"][-1]["data"]
    stages = {k: v for k, v in chat.items() if k.startswith("stage_")}
    assert set(stages) == {"stage_pre_ms", "stage_ctx_ms", "stage_rag_ms", "stage_ai_ms", "stage_post_ms"}
    assert all(isinstance(v, float) and v >= 0 for v in stages.values())
    assert set(chat) <= ops_telemetry.FIELDS["api"]


def test_stage_notes_refuse_text_and_out_of_range_numbers():
    tokens = ops_telemetry.begin_request()[1:]
    try:
        ops_telemetry.note(stage_ai_ms="I have chest pain", stage_ctx_ms=-5, stage_rag_ms=10 ** 9, stage_pre_ms=True, stage_post_ms=12.34, stage_other_ms=3)
        assert ops_telemetry.current_note() == {"stage_post_ms": 12.3}
    finally:
        ops_telemetry.end_request(tuple(tokens))


# ---- /chat/stream -----------------------------------------------------------------------------------------------------------

def _sse(res):
    events, name = [], None
    for line in res.text.split("\n"):
        if line.startswith("event: "):
            name = line[7:]
        elif line.startswith("data: ") and name:
            events.append((name, json.loads(line[6:])))
            name = None
    return events


def _stream(env, text, **extra):
    return env.client.post("/chat/stream", json={"message": text, **extra}, headers=H)


def test_the_stream_sends_meta_then_deltas_then_done_and_done_equals_chat(env):
    res = _stream(env, AI_MESSAGE)
    assert res.status_code == 200 and res.headers["content-type"].startswith("text/event-stream")
    assert res.headers["cache-control"] == "no-store" and res.headers["x-accel-buffering"] == "no"
    events = _sse(res)
    names = [n for n, _ in events]
    assert names[0] == "meta" and names[-1] == "done" and set(names[1:-1]) == {"delta"} and len(names) >= 3
    meta, done = events[0][1], events[-1][1]
    assert meta["conversation_id"] == done["conversation_id"] and meta["user_message_id"] == done["user_message_id"]
    assert meta["safety"]["level"] == done["safety"]["level"] and meta["kind"] == done["kind"] and meta["consent_required"] is False
    assert "".join(d["text"] for n, d in events if n == "delta") == done["response"]
    plain = send(env, AI_MESSAGE).json()
    assert set(plain) == set(done)


def test_deterministic_routes_send_meta_and_done_only(env):
    events = _sse(_stream(env, "I have crushing chest pain and cannot breathe"))
    assert [n for n, _ in events] == ["meta", "done"]
    assert events[0][1]["safety"]["level"] == "RED" and env.ai_calls == []
    assert [n for n, _ in _sse(_stream(env, "Slept 7 hours, drank 1.5 L of water and walked 5,000 steps."))] == ["meta", "done"]


def test_the_stream_never_shows_text_that_failed_the_checks(env):
    from bubbles_ai import BubblesAIResponse
    env.main.ask_bubbles = lambda m, **k: BubblesAIResponse(response="NHS guidance says drink water. Take paracetamol 500 mg twice a day. Studies show it helps.",
                                                            sentiment="neutral", health_events=[])
    events = _sse(_stream(env, AI_MESSAGE))
    shown = "".join(d["text"] for n, d in events if n == "delta")
    assert "500 mg" not in shown and "NHS" not in shown and "Studies show" not in shown
    assert shown == events[-1][1]["response"]
    plain = send(env, AI_MESSAGE).json()["response"]
    assert "NHS" not in plain and "Studies show" not in plain and "500 mg" not in plain


def test_an_empty_message_and_a_replayed_retry_stream_meta_and_done(env):
    assert [n for n, _ in _sse(_stream(env, "   "))] == ["meta", "done"]
    first = _stream(env, AI_MESSAGE, message_id="client-message-00000002")
    conv = _sse(first)[0][1]["conversation_id"]
    again = _stream(env, AI_MESSAGE, message_id="client-message-00000002", conversation_id=conv)
    assert [n for n, _ in _sse(again)] == ["meta", "done"] and len(env.ai_calls) == 1
    assert _sse(again)[-1][1]["response"] == _sse(first)[-1][1]["response"]


def test_stream_errors_before_it_opens_are_ordinary_http_errors(env):
    assert env.client.post("/chat/stream", json={"message": "hi"}).status_code in (401, 403)
    res = _stream(env, "hi", conversation_id="00000000-0000-4000-8000-000000000999")
    assert res.status_code == 404


def test_the_tone_settings_are_remembered_until_the_setup_is_saved(env, monkeypatch):
    import chat_cache
    import onboarding_api
    calls = []
    monkeypatch.setattr(onboarding_api, "style_block_for", lambda db, uid: calls.append(uid) or "- Length: short")
    chat_cache.forget_user(USER)
    assert chat_cache.style_block(env.db, USER) == chat_cache.style_block(env.db, USER) == "- Length: short" and len(calls) == 1
    chat_cache.forget_user(USER)
    chat_cache.style_block(env.db, USER)
    assert len(calls) == 2


def test_an_empty_tone_answer_is_never_remembered(env, monkeypatch):
    import chat_cache
    import onboarding_api
    answers = iter(["", "- Length: short"])
    monkeypatch.setattr(onboarding_api, "style_block_for", lambda db, uid: next(answers))
    chat_cache.forget_user(USER)
    assert chat_cache.style_block(env.db, USER) == "" and chat_cache.style_block(env.db, USER) == "- Length: short"


def test_forgetting_a_person_clears_the_cached_tone_and_profile(env):
    import chat_cache
    import context_engine
    chat_cache._style.put(USER, "old tone")
    context_engine._profile_cache.put(USER, ({"display_name": "Old"}, {}))
    chat_cache.forget_user(USER)
    assert chat_cache._style.peek(USER) is None and context_engine._profile_cache.peek(USER) is None


def test_an_urgent_reply_that_forgot_the_call_to_action_gets_it(env):
    from bubbles_ai import BubblesAIResponse
    env.main.ask_bubbles = lambda m, **k: BubblesAIResponse(response="That sounds uncomfortable. Rest and sip water.", sentiment="neutral", health_events=[])
    body = send(env, "I have a fever of 104 for three days").json()
    assert body["safety"]["state"] == "URGENT" and body["response"].endswith("Please speak to a clinician or an urgent-care service today.")
    env.main.ask_bubbles = lambda m, **k: BubblesAIResponse(response="Please see a doctor today.", sentiment="neutral", health_events=[])
    assert send(env, "I have a fever of 104 for three days again").json()["response"] == "Please see a doctor today."


def test_every_sentence_loses_its_attribution_not_only_the_first_and_who_the_pronoun_is_safe():
    from response_quality import lint, strip_attribution
    assert strip_attribution("NHS guidance says drink water. Studies show it helps.") == "Drink water. It helps."
    assert strip_attribution("Water helps.\nAccording to the NHS, rest also helps.") == "Water helps.\nRest also helps."
    assert "authority_citation" not in lint("Who is it that you spoke to? Anyone who feels dizzy should sit down.")
    assert strip_attribution("The doctor who prescribed it can tell you.") == "The doctor who prescribed it can tell you."
