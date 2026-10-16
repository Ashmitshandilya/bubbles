"""A5 topics: loneliness and anxiety quick scores, static support copy, numbers into the brain map, and Mind behaviour in chat."""
from __future__ import annotations

import os
import re
import sys
import types

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import doc_store
import health_logs
import mind_checkins as Mind
import wellness_api
from health_semantics import analyze
from mind_chat import loneliness_no_consent_reply, mind_concept, mind_support_block
from tests.fake_db import FakeDB
from tests.test_organ_map_engine import ev, organ

U1 = "00000000-0000-0000-0000-000000000001"
H1 = {"Authorization": "Bearer t1"}
AUTHORITY = re.compile(r"\b(NHS|WHO|CDC|NICE|ICMR|guidelines? say|studies show|according to)\b", re.I)


# --- quick scores ------------------------------------------------------------------------------------------------------------------

def test_loneliness_and_anxiety_are_screens_with_their_own_scales():
    lone, anx = Mind.screen_questions("loneliness"), Mind.screen_questions("anxiety")
    assert lone["questions"] == ["How often do you feel lonely?"] and [o["value"] for o in lone["options"]] == [1, 2, 3, 4, 5]
    assert [o["value"] for o in anx["options"]] == list(range(0, 11))
    assert Mind.score_screen("loneliness", [4])["suggest_talking_to_someone"] is True
    assert Mind.score_screen("loneliness", [3])["suggest_talking_to_someone"] is False
    assert Mind.score_screen("anxiety", [7])["suggest_talking_to_someone"] is True
    assert Mind.score_screen("anxiety", [6])["suggest_talking_to_someone"] is False


@pytest.mark.parametrize("kind,bad", [("loneliness", [0]), ("loneliness", [6]), ("loneliness", [1, 2]), ("anxiety", [11]), ("anxiety", [-1]),
                                      ("anxiety", [True]), ("anxiety", ["5"]), ("phq2", [4, 0])])
def test_scores_outside_the_scale_are_rejected(kind, bad):
    with pytest.raises(Mind.InputError):
        Mind.score_screen(kind, bad)


def test_messages_are_label_free_and_only_the_heavy_ones_carry_the_crisis_line():
    for kind, high, low in (("loneliness", 5, 1), ("anxiety", 10, 0)):
        hi, lo = Mind.score_screen(kind, [high])["message"], Mind.score_screen(kind, [low])["message"]
        assert "14416" in hi and "14416" not in lo
        for m in (hi, lo):
            assert not re.search(r"disorder|diagnos|depress|you have", m, re.I) and "—" not in m and not AUTHORITY.search(m)


def test_support_copy_is_plain_and_complete():
    assert set(Mind.SUPPORT_COPY) == {"loneliness", "panic", "apart"}
    for topic in Mind.SUPPORT_COPY.values():
        blob = " ".join([topic["title"], topic["text"], *topic["steps"]])
        assert len(topic["steps"]) == 3 and "—" not in blob and not AUTHORITY.search(blob)


def test_longer_exhale_comes_first():
    first = Mind.EXERCISES[0]
    assert first["id"] == "slow_breathing" and first["pattern"]["exhale"] > first["pattern"]["inhale"]


@pytest.fixture()
def env():
    db = FakeDB({"t1": U1})

    def get_user(authorization):
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid token")
        return db.auth.get_user(authorization[7:]).user

    app = FastAPI()
    app.include_router(wellness_api.build_router(get_user, db))
    return TestClient(app, raise_server_exceptions=False), db


def test_loneliness_score_is_stored_as_a_score_only_under_mind_screen(env):
    client, db = env
    r = client.post("/wellness/mind/screen", json={"kind": "loneliness", "answers": [4]}, headers=H1)
    assert r.status_code == 201 and r.json()["score"] == 4
    docs = doc_store.list_docs(db, U1, "mind_screen", limit=10)
    assert len(docs) == 1 and docs[0]["key"].startswith("loneliness:")
    assert set(docs[0]["payload"]) == {"kind", "score", "positive", "date"}


def test_a_loneliness_score_does_not_move_the_two_week_check_in_timer(env):
    client, _db = env
    client.post("/wellness/mind/screen", json={"kind": "loneliness", "answers": [2]}, headers=H1)
    client.post("/wellness/mind/screen", json={"kind": "anxiety", "answers": [3]}, headers=H1)
    o = client.get("/wellness/mind/overview", headers=H1).json()
    assert o["screen"]["due"] is True and o["screen"]["last"] is None
    assert set(o["support"]) == {"loneliness", "panic", "apart"}


# --- numbers into the brain map ----------------------------------------------------------------------------------------------------

def test_mood_events_carry_stress_and_anxiety_numbers():
    row = {"intensity": 6, "logged_at": "2026-10-14T08:00:00+00:00", "notes": "tough | Stress 4/10; Anxiety 8/10"}
    e = health_logs._ev_mood(row)
    assert e["anxiety_score"] == 8 and e["stress_score"] == 4 and e["score"] == 6
    assert "anxiety_score" not in health_logs._ev_mood({"intensity": 6, "logged_at": "2026-10-14T08:00:00+00:00", "notes": "Anxiety is a word"})


def _checkin(anxiety, ago):
    return ev("mood", {"score": 6, "anxiety_score": anxiety}, ago)


def test_brain_watches_high_anxiety_scores_softly_and_stays_quiet_otherwise():
    high = organ("brain", [_checkin(8, i) for i in (1, 2, 3)])
    assert high["status"] == "worth_watching"
    assert "anxiety" in str(high).lower() and "—" not in str(high)
    assert organ("brain", [_checkin(5, i) for i in (1, 2, 3)])["status"] != "worth_watching"
    assert organ("brain", [_checkin(9, 1)])["status"] != "worth_watching"   # one number is not a pattern


def test_mood_stress_number_reaches_the_stress_rule():
    assert organ("brain", [ev("mood", {"score": 6, "stress_score": 8}, i) for i in (1, 2, 3)])["status"] == "worth_watching"


# --- Mind in chat ------------------------------------------------------------------------------------------------------------------

def turn(text):
    return types.SimpleNamespace(facts=analyze(text))


@pytest.mark.parametrize("text,concept", [
    ("I feel so lonely lately", "loneliness"),
    ("I had a panic attack on the train", "panic_attack"),
    ("I miss my mom so much", "separation_anxiety"),
    ("I am anxious about the exam", "anxiety"),
    ("mujhe bahut akela lagta hai", "loneliness"),
    ("mujhe bahut ghabrahat ho rahi hai", "anxiety"),
])
def test_block_appears_for_own_current_feelings(text, concept):
    assert mind_concept(turn(text)) == concept
    block = mind_support_block(turn(text))
    assert block.startswith("MIND SUPPORT") and "Never name or label a condition" in block and "No medicine" in block


@pytest.mark.parametrize("text", [
    "my sister had a panic attack", "I'm not lonely", "I don't feel anxious anymore", "I live alone and I like it",
    "I had a headache today", "what is separation anxiety?", "I felt lonely years ago",
])
def test_block_stays_empty_otherwise(text):
    assert mind_support_block(turn(text)) == ""


def test_panic_beats_the_anxiety_parent():
    assert mind_concept(turn("I am anxious and I keep having panic attacks")) == "panic_attack"


def test_loneliness_has_a_fixed_reply_that_keeps_the_frozen_consent_ask():
    from consent import consent_needed_reply
    reply = loneliness_no_consent_reply(turn("I feel so lonely"), "Asha")
    assert reply.startswith("I'm really glad you said that, Asha.") and reply.endswith(consent_needed_reply("Asha"))
    assert "Loneliness check-in" in reply and not AUTHORITY.search(reply) and "—" not in reply
    assert loneliness_no_consent_reply(turn("I am anxious about the exam"), "Asha") is None


# --- through /chat -----------------------------------------------------------------------------------------------------------------

@pytest.fixture()
def chat():
    for k in ("GROQ_API_KEY", "NVIDIA_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "MISTRAL_API_KEY"):
        os.environ.pop(k, None)
    os.environ.update(SUPABASE_URL="http://localhost", SUPABASE_SECRET_KEY="dummy", ALLOW_PAID_AI="false", ALLOW_KEYLESS_AI="false")
    db = FakeDB({"tok": U1})
    fake = types.ModuleType("supabase_client")
    fake.supabase = db
    saved = sys.modules.get("supabase_client")
    sys.modules["supabase_client"] = fake
    touched = ("main", "memory_manager", "memory_retrieval", "memory_promotion", "context_engine", "rag", "rl.service", "health_logs", "chat_pipeline")
    for m in touched:
        sys.modules.pop(m, None)
    import main
    import rag
    from bubbles_ai import BubblesAIResponse
    rag.embed_text = lambda *a, **k: None
    seen: list[dict] = []

    def stub_ai(message, **kw):
        seen.append(kw)
        return BubblesAIResponse(response="I hear you.", sentiment="neutral", health_events=[])

    main.ask_bubbles = stub_ai
    main.hybrid_search = lambda **k: []
    client = TestClient(main.app, raise_server_exceptions=False)
    yield types.SimpleNamespace(client=client, db=db, seen=seen)
    if saved is not None:
        sys.modules["supabase_client"] = saved
    else:
        sys.modules.pop("supabase_client", None)
    for m in touched:
        sys.modules.pop(m, None)


def _post(chat, text):
    return chat.client.post("/chat", json={"message": text}, headers={"Authorization": "Bearer tok"})


def test_chat_loneliness_without_ai_consent_gets_the_supportive_reply_and_the_card(chat):
    r = _post(chat, "I feel so lonely lately")
    assert r.status_code == 200
    body = r.json()
    assert body["consent_required"] is True and "Loneliness check-in" in body["response"] and chat.seen == []


def test_chat_anxiety_without_consent_still_gets_only_the_consent_wall(chat):
    body = _post(chat, "I am anxious about the exam").json()
    assert body["consent_required"] is True and "Loneliness check-in" not in body["response"] and chat.seen == []


def test_chat_with_consent_gives_the_model_the_mind_block_in_the_safety_context(chat):
    import consent
    consent.set_ai_chat(chat.db, "00000000-0000-0000-0000-000000000001", True)
    assert _post(chat, "I feel so lonely lately").status_code == 200
    assert "MIND SUPPORT" in chat.seen[0]["safety_context"]
    chat.seen.clear()
    _post(chat, "I had a headache today")
    assert "MIND SUPPORT" not in chat.seen[0]["safety_context"]
