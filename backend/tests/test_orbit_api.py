"""Orbit API (WP2.2): every route is signed-in and owner-scoped; nothing one partner tells Bubbles reaches the other; safety comes first; the model is
only used with a yes and never sees a name."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

BACKEND = Path(__file__).resolve().parents[1]
for p in (str(BACKEND), str(BACKEND / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

import consent  # noqa: E402
import doc_store  # noqa: E402
import orbit  # noqa: E402
import orbit_weather  # noqa: E402
import partner_sharing as ps  # noqa: E402
from db_access import register_db_error_handlers  # noqa: E402
from fake_db import FakeDB, grant_consent  # noqa: E402

A, B, C = "00000000-0000-0000-0000-00000000000a", "00000000-0000-0000-0000-00000000000b", "00000000-0000-0000-0000-00000000000c"
HA, HB, HC = {"Authorization": "Bearer ta"}, {"Authorization": "Bearer tb"}, {"Authorization": "Bearer tc"}


@pytest.fixture()
def env(monkeypatch):
    monkeypatch.setenv("BUBBLES_DOC_SIGNING_KEY", "orbit-test-key")
    ps._attempts.clear()
    orbit._limiter = orbit.RateLimiter(limit=10_000, window=60.0)
    import chat_cache
    for u in (A, B, C):
        chat_cache.forget_user(u)
    db = FakeDB({"ta": A, "tb": B, "tc": C})
    app = FastAPI()
    register_db_error_handlers(app)

    def get_user(authorization):
        uid = db.auth.tokens.get((authorization or "").removeprefix("Bearer ").strip())
        if not uid:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return type("U", (), {"id": uid})()

    app.include_router(ps.build_router(get_user, db))
    app.include_router(orbit.build_router(get_user, db))
    for person in (A, B, C):
        grant_consent(db, person, "partner_sharing")
    calls: list[tuple[str, str]] = []

    def fake_json(system, message, validate):
        calls.append((system[:40], message))
        try:                                   # like the real thing: anything unusable is "no answer"
            return validate(fake_json.answer) if fake_json.answer is not None else None
        except Exception:
            return None
    fake_json.answer = None
    monkeypatch.setattr(orbit.ai_json, "ask_json", fake_json)
    client = TestClient(app, raise_server_exceptions=False)
    from types import SimpleNamespace
    return SimpleNamespace(client=client, db=db, calls=calls, ai=fake_json)


def pair(env, a_rituals=True, b_rituals=True, a_weather=False, b_weather=False):
    """A invites, B connects; each switches on what they want (and gives the Orbit yes first)."""
    c, db = env.client, env.db
    grant_consent(db, A, "orbit_partner_signals")
    grant_consent(db, B, "orbit_partner_signals")
    cats_a = ["sleep"] + (["orbit_rituals"] if a_rituals else []) + (["orbit_weather"] if a_weather else [])
    cats_b = ["sleep"] + (["orbit_rituals"] if b_rituals else []) + (["orbit_weather"] if b_weather else [])
    assert c.put("/partner-sharing/settings", json={"categories": cats_a, "owner_name": "Riya"}, headers=HA).status_code == 200
    assert c.put("/partner-sharing/settings", json={"categories": cats_b, "owner_name": "Ashmit"}, headers=HB).status_code == 200
    code = c.post("/partner-sharing/invite", headers=HA).json()["code"]
    assert c.post("/partner-sharing/connect", json={"code": code, "name": "Ashmit"}, headers=HB).status_code == 200


def leave(env):
    share_id = env.client.get("/partner-sharing/shared-with-me", headers=HB).json()["shares"][0]["id"]
    assert env.client.delete(f"/partner-sharing/shared-with-me/{share_id}", headers=HB).status_code == 200


ROUTES = (("get", "/orbit"), ("put", "/orbit/profile"), ("post", "/orbit/reply-helper"), ("post", "/orbit/cooldown"), ("get", "/orbit/love-map"), ("post", "/orbit/repair"),
          ("get", "/orbit/question"), ("post", "/orbit/question"), ("get", "/orbit/checkin"), ("post", "/orbit/checkin"), ("get", "/orbit/weather"), ("get", "/orbit/weather/preview"),
          ("get", "/orbit/notes"), ("post", "/orbit/notes"), ("get", "/orbit/notes/received"), ("get", "/orbit/harbor"))


def test_every_route_needs_a_sign_in(env):
    for method, path in ROUTES:
        r = getattr(env.client, method)(path, **({"json": {}} if method in ("put", "post") else {}))
        assert r.status_code == 401, (method, path, r.status_code)
    assert env.client.delete("/orbit/notes/0123456789abcdef").status_code == 401


# ---- profile -----------------------------------------------------------------------------------------------------------------------------

def test_the_profile_is_saved_validated_and_joins_the_person_model(env):
    r = env.client.put("/orbit/profile", json={"status": "dating", "partner_word": "my girlfriend", "cared_for_by": ["words", "time"], "conflict_style": "withdraws"}, headers=HA)
    assert r.status_code == 200 and r.json()["status"] == "success" and r.json()["profile"]["cared_for_by"] == ["words", "time"]
    assert env.client.get("/orbit", headers=HA).json()["profile"]["status"] == "dating"
    import person_model
    model = person_model.load(env.db, A, fresh=True)
    assert model["traits"]["conflict_style"]["evidence"][0]["value"] == "withdraws" and set(model["traits"]["cared_for_by"]["evidence"][0]) >= {"source", "note", "weight"}
    for bad in ({"status": "engaged"}, {"cared_for_by": ["money"]}, {"conflict_style": "fights"}, {"partner_word": "x" * 40}):
        assert env.client.put("/orbit/profile", json=bad, headers=HA).status_code == 422, bad


def test_the_profile_is_private(env):
    env.client.put("/orbit/profile", json={"status": "married"}, headers=HA)
    assert env.client.get("/orbit", headers=HB).json()["profile"]["status"] is None


# ---- the shared question and the weekly check-in ----------------------------------------------------------------------------------------

def test_solo_question_and_checkin_work_for_one_person(env):
    q = env.client.get("/orbit/question", headers=HA).json()
    assert q["state"] == "solo" and q["text"] and not q["answered"]
    done = env.client.post("/orbit/question", json={"answer": "A quiet walk."}, headers=HA).json()
    assert done["answered"] and done["my_answer"] == "A quiet walk." and done["partner_answer"] is None
    c = env.client.post("/orbit/checkin", json={"answers": {"appreciate": "He cooked", "wish": ""}}, headers=HA).json()
    assert c["answered"] and c["my_answers"] == {"appreciate": "He cooked"} and c["state"] == "solo"
    assert env.client.post("/orbit/checkin", json={"answers": {}}, headers=HA).status_code == 422
    assert env.client.post("/orbit/checkin", json={"answers": {"mood": "x"}}, headers=HA).status_code == 422
    assert env.client.post("/orbit/question", json={"answer": "x" * 600}, headers=HA).status_code == 422


def test_the_question_is_the_same_for_both_and_answers_are_revealed_only_when_both_have_answered(env):
    pair(env)
    qa, qb = env.client.get("/orbit/question", headers=HA).json(), env.client.get("/orbit/question", headers=HB).json()
    assert qa["id"] == qb["id"] and qa["paired"] and qa["state"] == "waiting"
    env.client.post("/orbit/question", json={"answer": "SECRET-A-ANSWER"}, headers=HA)
    before = env.client.get("/orbit/question", headers=HB).json()
    assert before["state"] == "waiting" and before["partner_answer"] is None and "SECRET-A-ANSWER" not in json.dumps(before)
    assert env.client.get("/orbit/question", headers=HA).json()["partner_answer"] is None, "the first to answer sees nothing until the other has"
    env.client.post("/orbit/question", json={"answer": "B-ANSWER"}, headers=HB)
    a_view, b_view = env.client.get("/orbit/question", headers=HA).json(), env.client.get("/orbit/question", headers=HB).json()
    assert a_view["partner_answer"] == "B-ANSWER" and b_view["partner_answer"] == "SECRET-A-ANSWER" and a_view["state"] == b_view["state"] == "revealed"


def test_the_checkin_reveals_together_and_a_question_may_be_skipped(env):
    pair(env)
    env.client.post("/orbit/checkin", json={"answers": {"appreciate": "A-APPRECIATES", "weighing": "A-WEIGHS"}}, headers=HA)
    waiting = env.client.get("/orbit/checkin", headers=HB).json()
    assert waiting["state"] == "waiting" and waiting["partner_answers"] is None and "A-APPRECIATES" not in json.dumps(waiting)
    env.client.post("/orbit/checkin", json={"answers": {"wish": "B-WISH"}}, headers=HB)
    assert env.client.get("/orbit/checkin", headers=HA).json()["partner_answers"] == {"wish": "B-WISH"}
    assert env.client.get("/orbit/checkin", headers=HB).json()["partner_answers"] == {"appreciate": "A-APPRECIATES", "weighing": "A-WEIGHS"}


def test_nothing_is_revealed_unless_both_people_switched_rituals_on(env):
    pair(env, b_rituals=False)
    env.client.post("/orbit/question", json={"answer": "A-ANSWER"}, headers=HA)
    env.client.post("/orbit/question", json={"answer": "B-ANSWER"}, headers=HB)
    for h in (HA, HB):
        v = env.client.get("/orbit/question", headers=h).json()
        assert v["partner_answer"] is None and v["state"] == "waiting"
    assert "B-ANSWER" not in env.client.get("/orbit/question", headers=HA).text


def test_withdrawing_the_yes_or_leaving_the_pair_hides_everything_at_the_next_read(env):
    pair(env)
    env.client.post("/orbit/question", json={"answer": "A-ANSWER"}, headers=HA)
    env.client.post("/orbit/question", json={"answer": "B-ANSWER"}, headers=HB)
    assert env.client.get("/orbit/question", headers=HA).json()["partner_answer"] == "B-ANSWER"
    consent.set_purpose(env.db, B, "orbit_partner_signals", False, source="system", hash_seen=consent.text_hash("orbit_partner_signals"))
    consent.forget(B)
    assert env.client.get("/orbit/question", headers=HA).json()["partner_answer"] is None
    grant_consent(env.db, B, "orbit_partner_signals")
    consent.forget(B)
    assert env.client.get("/orbit/question", headers=HA).json()["partner_answer"] == "B-ANSWER"
    leave(env)
    after = env.client.get("/orbit/question", headers=HA).json()
    assert after["partner_answer"] is None and after["state"] == "solo" and not after["paired"]
    assert env.client.get("/orbit", headers=HB).json()["paired"] is False


def test_a_forged_row_cannot_make_an_answer_appear(env):
    pair(env)
    env.client.post("/orbit/question", json={"answer": "A-ANSWER"}, headers=HA)
    day = datetime.now(timezone.utc).date().isoformat()
    qid = env.client.get("/orbit/question", headers=HA).json()["id"]
    env.db.table(doc_store.TABLE).insert({"user_id": B, "event_type": doc_store.EVENT_TYPE, "title": f"orbit_question:{day}", "source": doc_store.SOURCE, "user_confirmed": True,
                                          "event_date": day, "data": {"kind": "orbit_question", "key": day, "payload": {"question_id": qid, "my_answer": "FORGED"}, "version": 1, "sig": "x"}}).execute()
    assert "FORGED" not in env.client.get("/orbit/question", headers=HA).text


def test_nothing_private_ever_appears_in_the_partners_responses(env):
    pair(env)
    secrets = {"reply": "ZZ-PASTE-SECRET", "repair": "ZZ-REPAIR-SECRET", "note": "ZZ-NOTE-SECRET", "love": "ZZ-LOVE-SECRET"}
    grant_consent(env.db, A, "ai_chat_processing")
    env.ai.answer = {"feelings": ["f"], "replies": [{"tone": "gentle", "text": "ok text one", "why": "w"}, {"tone": "light", "text": "ok text two", "why": "w"}]}
    env.client.post("/orbit/reply-helper", json={"their_message": secrets["reply"]}, headers=HA)
    env.client.post("/orbit/repair", json={"happened": secrets["repair"], "felt": "hurt", "needed": "space", "own": "I snapped"}, headers=HA)
    env.client.post("/orbit/notes", json={"kind": "repair", "text": secrets["note"]}, headers=HA)
    env.client.post("/orbit/notes", json={"kind": "love_map", "text": secrets["love"]}, headers=HA)
    env.client.put("/orbit/profile", json={"status": "committed", "partner_word": "ZZ-WORD-SECRET"}, headers=HA)
    seen = ""
    for method, path in ROUTES:
        if method == "get":
            seen += getattr(env.client, method)(path, headers=HB).text
    seen += env.client.get("/partner-sharing/shared-with-me", headers=HB).text
    for secret in list(secrets.values()) + ["ZZ-WORD-SECRET"]:
        assert secret not in seen, secret


# ---- safety first -------------------------------------------------------------------------------------------------------------------------

def test_crisis_and_harm_at_home_get_the_fixed_answer_and_are_never_stored(env):
    r = env.client.post("/orbit/question", json={"answer": "I want to end my life tonight"}, headers=HA).json()
    assert r["status"] == "safety" and r["kind"] == "emergency" and "Tele-MANAS" in r["message"]
    r = env.client.post("/orbit/checkin", json={"answers": {"weighing": "he choked me last night and said he will kill me"}}, headers=HA).json()
    assert r["status"] == "safety" and r["kind"] == "safe_harbor" and r["harbor"]["tier"] == 3
    assert env.client.get("/orbit/question", headers=HA).json()["answered"] is False
    assert env.client.get("/orbit/checkin", headers=HA).json()["answered"] is False
    assert env.client.post("/orbit/notes", json={"kind": "repair", "text": "my husband hits me every day"}, headers=HA).json()["status"] == "safety"
    assert env.client.get("/orbit/notes", headers=HA).json()["notes"] == []


def test_a_threatening_paste_in_the_reply_helper_is_not_sent_to_a_model(env):
    grant_consent(env.db, A, "ai_chat_processing")
    env.ai.answer = {"feelings": [], "replies": []}
    r = env.client.post("/orbit/reply-helper", json={"their_message": "he choked me last night and said he will kill me if I leave"}, headers=HA).json()
    assert r["status"] == "safety" and r["kind"] == "safe_harbor" and env.calls == []


# ---- reply helper -------------------------------------------------------------------------------------------------------------------------

GOOD = {"feelings": ["they may be feeling overlooked", "they may be tired"],
        "replies": [{"tone": "gentle", "text": "I hear you, and I care about this.", "why": "Warm."}, {"tone": "light", "text": "Hey, thinking of you.", "why": "Easy."},
                    {"tone": "clear", "text": "I need a little time, then let's talk.", "why": "Direct."}]}


def test_the_reply_helper_needs_the_ai_yes_and_says_so_the_usual_way(env):
    r = env.client.post("/orbit/reply-helper", json={"their_message": "you never listen to me"}, headers=HA)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "consent_required" and r.json()["detail"]["purpose"] == "ai_chat_processing"
    assert env.calls == []


def test_the_reply_helper_returns_feelings_and_three_replies_and_saves_nothing(env):
    grant_consent(env.db, A, "ai_chat_processing")
    env.ai.answer = GOOD
    before = len(env.db.rows(doc_store.TABLE))
    r = env.client.post("/orbit/reply-helper", json={"their_message": "you never listen to me", "context": "we argued about plans"}, headers=HA).json()
    assert r["source"] == "ai" and [x["tone"] for x in r["replies"]] == ["gentle", "light", "clear"] and len(r["feelings"]) == 2
    assert len(env.db.rows(doc_store.TABLE)) == before, "ephemeral: nothing is stored"


def test_names_are_replaced_before_the_model_and_put_back_in_the_answer(env):
    grant_consent(env.db, A, "ai_chat_processing")
    env.db.table("memory_items").insert({"user_id": A, "memory_type": "L2", "is_active": True, "verification_status": "user_confirmed",
                                         "structured_data": {"key": "partner", "value": "Ashmit", "source": "explicit_user_statement", "relation": "boyfriend"}}).execute()
    env.ai.answer = {"feelings": ["[PARTNER] may feel overlooked"], "replies": [{"tone": "gentle", "text": "Hey [PARTNER], I hear you.", "why": "Warm."},
                                                                                  {"tone": "light", "text": "Thinking of you, [PARTNER].", "why": "Easy."}]}
    r = env.client.post("/orbit/reply-helper", json={"their_message": "Ashmit says I never make time for him"}, headers=HA).json()
    assert "Ashmit" not in env.calls[0][1] and "[PARTNER]" in env.calls[0][1]
    assert r["replies"][0]["text"] == "Hey Ashmit, I hear you." and r["feelings"] == ["Ashmit may feel overlooked"]


def test_a_verdict_in_a_draft_loses_that_sentence_and_a_bad_draft_falls_back_to_templates(env):
    grant_consent(env.db, A, "ai_chat_processing")
    env.ai.answer = {"feelings": [], "replies": [{"tone": "gentle", "text": "He is toxic. I care about this.", "why": "w"}, {"tone": "light", "text": "Hey, thinking of you.", "why": "w"},
                                                 {"tone": "clear", "text": "Make him jealous so he misses you.", "why": "w"}]}
    r = env.client.post("/orbit/reply-helper", json={"their_message": "you never listen to me"}, headers=HA).json()
    assert [x["text"] for x in r["replies"]] == ["I care about this.", "Hey, thinking of you."] and r["source"] == "ai"
    env.ai.answer = {"feelings": [], "replies": [{"tone": "gentle", "text": "You are lazy and selfish.", "why": "w"}, {"tone": "light", "text": "Women are always dramatic.", "why": "w"}]}
    r = env.client.post("/orbit/reply-helper", json={"their_message": "you never listen to me"}, headers=HA).json()
    assert r["source"] == "template" and len(r["replies"]) == 3


def test_no_answer_from_any_model_gives_the_fixed_replies_in_the_persons_language(env):
    grant_consent(env.db, A, "ai_chat_processing")
    env.ai.answer = None
    en = env.client.post("/orbit/reply-helper", json={"their_message": "you never listen to me"}, headers=HA).json()
    hi = env.client.post("/orbit/reply-helper", json={"their_message": "tum meri baat kabhi nahi sunte aur main kya karun"}, headers=HA).json()
    assert en["source"] == hi["source"] == "template" and "Can we talk" in en["replies"][0]["text"] and "baat karein" in hi["replies"][0]["text"]


def test_input_limits_and_the_decline(env):
    grant_consent(env.db, A, "ai_chat_processing")
    assert env.client.post("/orbit/reply-helper", json={"their_message": "x" * 1600}, headers=HA).status_code == 422
    assert env.client.post("/orbit/reply-helper", json={"their_message": ""}, headers=HA).status_code == 422
    assert env.client.post("/orbit/reply-helper", json=["a"], headers=HA).status_code == 422
    r = env.client.post("/orbit/reply-helper", json={"their_message": "he is ignoring me", "context": "help me make him jealous"}, headers=HA).json()
    assert r["status"] == "declined" and "directly" in r["message"] and env.calls == []


def test_the_throttle(env):
    orbit._limiter = orbit.RateLimiter(limit=2, window=60.0)
    grant_consent(env.db, A, "ai_chat_processing")
    env.ai.answer = GOOD
    codes = [env.client.post("/orbit/reply-helper", json={"their_message": "hello there"}, headers=HA).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


# ---- before I text them, repair, love map, notes ----------------------------------------------------------------------------------------

def test_cooldown_only_steps_in_when_the_draft_is_heated(env):
    calm = env.client.post("/orbit/cooldown", json={"draft": "Can we talk tonight about the weekend plans?"}, headers=HA).json()
    assert calm == {"status": "success", "heated": False, "rewrite": None, "pause_minutes": 0}
    for draft in ("YOU NEVER LISTEN TO ME AT ALL", "I hate how you always do this!!!", "tum bewakoof ho aur main tang aa gaya", "are you serious?! again?!"):
        r = env.client.post("/orbit/cooldown", json={"draft": draft}, headers=HA).json()
        assert r["heated"] is True and r["pause_minutes"] == 20 and r["rewrite"] and r["source"] == "template", draft
    assert "baad mein" in env.client.post("/orbit/cooldown", json={"draft": "tum bewakoof ho aur main tang aa gaya"}, headers=HA).json()["rewrite"]


def test_cooldown_uses_the_model_only_with_the_yes(env):
    env.ai.answer = {"rewrite": "I feel hurt about the plans and I need us to talk."}
    r = env.client.post("/orbit/cooldown", json={"draft": "YOU ALWAYS RUIN EVERYTHING"}, headers=HA).json()
    assert r["source"] == "template" and env.calls == []
    grant_consent(env.db, A, "ai_chat_processing")
    r = env.client.post("/orbit/cooldown", json={"draft": "YOU ALWAYS RUIN EVERYTHING"}, headers=HA).json()
    assert r["source"] == "ai" and r["rewrite"] == "I feel hurt about the plans and I need us to talk."


def test_repair_writes_a_template_without_the_yes_and_a_model_draft_with_it(env):
    body = {"happened": "We fought about money", "felt": "unheard", "needed": "a calm talk", "own": "I raised my voice"}
    t = env.client.post("/orbit/repair", json=body, headers=HA).json()
    assert t["source"] == "template" and "I raised my voice." in t["draft"] and "unheard" in t["draft"] and env.calls == []
    grant_consent(env.db, A, "ai_chat_processing")
    env.ai.answer = {"draft": "I have been thinking about our fight and I am sorry I raised my voice. Can we talk tonight?"}
    m = env.client.post("/orbit/repair", json=body, headers=HA).json()
    assert m["source"] == "ai" and m["draft"].startswith("I have been thinking")
    assert env.client.post("/orbit/repair", json={**body, "own": ""}, headers=HA).status_code == 422


def test_love_map_lists_what_is_known_and_what_to_ask_and_keeps_notes_private(env):
    env.db.table("memory_items").insert({"user_id": A, "memory_type": "L2", "is_active": True, "verification_status": "user_confirmed",
                                         "structured_data": {"key": "partner", "value": "Ashmit", "source": "explicit_user_statement", "relation": "boyfriend"}}).execute()
    m = env.client.get("/orbit/love-map", headers=HA).json()
    assert m["known"] == [{"id": "name", "text": "Their name: Ashmit"}] and len(m["ask"]) == 3
    env.client.post("/orbit/notes", json={"kind": "love_map", "text": "He is stressed about his promotion", "question_id": m["ask"][0]["id"]}, headers=HA)
    again = env.client.get("/orbit/love-map", headers=HA).json()
    assert any("promotion" in k["text"] for k in again["known"]) and m["ask"][0]["id"] not in {q["id"] for q in again["ask"]}


def test_notes_are_listed_deleted_and_limited(env):
    first = env.client.post("/orbit/notes", json={"kind": "repair", "text": "my draft"}, headers=HA).json()["notes"][0]
    assert env.client.post("/orbit/notes", json={"kind": "poem", "text": "x"}, headers=HA).status_code == 422
    assert env.client.delete(f"/orbit/notes/{first['id']}", headers=HA).json()["notes"] == []
    assert env.client.delete("/orbit/notes/not-an-id", headers=HA).status_code == 404
    for i in range(orbit.MAX_NOTES):
        orbit.add_note(env.db, A, {"kind": "repair", "text": f"n{i}"})
    assert env.client.post("/orbit/notes", json={"kind": "repair", "text": "one more"}, headers=HA).status_code == 422
    assert env.client.get("/orbit/notes", headers=HC).json()["notes"] == []


def test_a_gratitude_note_is_shared_only_when_chosen_and_only_with_the_connected_person(env):
    pair(env)
    env.client.post("/orbit/notes", json={"kind": "gratitude", "text": "Thank you for the tea", "share": True}, headers=HA)
    env.client.post("/orbit/notes", json={"kind": "gratitude", "text": "PRIVATE-GRATITUDE", "share": False}, headers=HA)
    got = env.client.get("/orbit/notes/received", headers=HB).json()["notes"]
    assert [n["text"] for n in got] == ["Thank you for the tea"]
    assert env.client.get("/orbit/notes/received", headers=HC).json()["notes"] == []
    leave(env)
    assert env.client.get("/orbit/notes/received", headers=HB).json()["notes"] == []


# ---- partner weather ------------------------------------------------------------------------------------------------------------------------

def log_mood(db, uid, intensity, stress=None, hours_ago=48):
    when = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()
    db.table("mood_logs").insert({"user_id": uid, "intensity": intensity, "mood": f"{intensity}/10", "logged_at": when,
                                  "notes": f"Stress {stress}/10" if stress is not None else None}).execute()


def test_weather_needs_a_pair_a_yes_and_the_switch(env):
    assert env.client.get("/orbit/weather", headers=HB).json() == {"status": "success", "line": None}
    pair(env, a_weather=False)
    assert env.client.get("/orbit/weather", headers=HB).json()["line"] is None
    pair2 = env.client.put("/partner-sharing/settings", json={"categories": ["sleep", "orbit_weather"]}, headers=HA)
    assert pair2.status_code == 200
    seen = {env.client.get("/orbit/weather", headers=HB).json()["line"] for _ in range(3)}
    assert len(seen) == 1, "the same answer all through the window"


def test_a_line_is_one_of_the_fixed_lines_and_is_stable_for_three_days(env):
    pair(env, a_weather=True)
    log_mood(env.db, A, 2, stress=8)
    now = datetime.now(timezone.utc)
    for _ in range(5):
        line = orbit.weather_for(env.db, B, now)["line"]
        assert line is None or line in orbit_weather.LINE_TEXT.values()
    state = doc_store.get(env.db, A, "orbit_weather", "main")
    assert state["window"] == orbit_weather.window_index(now)
    assert "mood" not in json.dumps(state) and "stress" not in json.dumps(state).lower()


def test_enabling_weather_needs_the_orbit_yes(env):
    r = env.client.put("/partner-sharing/settings", json={"categories": ["orbit_weather"]}, headers=HA)
    assert r.status_code == 403 and "Orbit" in r.json()["detail"]
    grant_consent(env.db, A, "orbit_partner_signals")
    assert env.client.put("/partner-sharing/settings", json={"categories": ["orbit_weather"]}, headers=HA).status_code == 200


def test_a_safe_harbor_flag_silences_weather_without_any_visible_change_for_the_partner(env):
    pair(env, a_weather=True)
    now = datetime.now(timezone.utc)
    doc_store.put(env.db, A, "harbor_flag", "v1", {"last_tier": 2, "last_at": (now - timedelta(days=10)).isoformat(), "pause_partner_signals": True, "events": []})
    assert env.client.get("/orbit/weather", headers=HB).json() == {"status": "success", "line": None}
    home_b = env.client.get("/orbit", headers=HB).json()
    assert home_b["weather"] is None and "paused" not in json.dumps({k: v for k, v in home_b.items() if k != "weather_paused"})
    assert home_b["weather_paused"] is False, "the pause flag is shown to the sharer only"
    assert env.client.get("/orbit", headers=HA).json()["weather_paused"] is True
    doc_store.put(env.db, A, "harbor_flag", "v1", {"last_tier": 2, "last_at": (now - timedelta(days=100)).isoformat(), "pause_partner_signals": True, "events": []})
    assert env.client.get("/orbit", headers=HA).json()["weather_paused"] is False, "after ninety days it resumes"


def test_a_line_is_not_first_chosen_within_twelve_hours_of_a_log(env):
    pair(env, a_weather=True)
    log_mood(env.db, A, 3, hours_ago=2)
    now = datetime.now(timezone.utc)
    assert orbit.weather_for(env.db, B, now)["line"] is None and doc_store.get(env.db, A, "orbit_weather", "main") is None
    later = now + timedelta(hours=11)
    assert doc_store.get(env.db, A, "orbit_weather", "main") is None
    orbit.weather_for(env.db, B, later)
    assert doc_store.get(env.db, A, "orbit_weather", "main") is not None


def test_leaving_the_pair_stops_weather_at_the_next_read(env):
    pair(env, a_weather=True)
    now = datetime.now(timezone.utc)
    window = orbit_weather.window_index(now)
    for k in range(60):
        line = orbit_weather.pick(False, f"k{k}", window)
        if line:
            break
    doc_store.put(env.db, A, "orbit_weather", "main", {"window": window, "line": line})
    assert env.client.get("/orbit/weather", headers=HB).json()["line"] == orbit_weather.LINE_TEXT[line]
    leave(env)
    assert env.client.get("/orbit/weather", headers=HB).json()["line"] is None


def test_the_sharer_can_preview_exactly_what_a_partner_could_see(env):
    pair(env, a_weather=True)
    p = env.client.get("/orbit/weather/preview", headers=HA).json()
    assert p["on"] is True and len(p["possible_lines"]) == 20 and "never tells them how you are" in p["how"]
    assert env.client.get("/orbit/weather/preview", headers=HB).json()["on"] is False


def test_orbit_categories_never_appear_in_the_shared_with_you_view_or_a_quick_link(env):
    pair(env, a_rituals=True, a_weather=True)
    shares = env.client.get("/partner-sharing/shared-with-me", headers=HB).json()["shares"]
    assert [s["key"] for sec in [shares[0]["sections"]] for s in sec] == ["sleep"]
    link = env.client.post("/partner-sharing/link", json={"expires_in_days": 7}, headers=HA).json()
    public = env.client.get(link["share_path"]).json()
    assert [s["key"] for s in public["sections"]] == ["sleep"]


# ---- the home screen --------------------------------------------------------------------------------------------------------------------

def test_home_for_a_solo_person_and_for_a_pair(env):
    h = env.client.get("/orbit", headers=HA).json()
    assert h["paired"] is False and h["partner_name"] is None and h["weather"] is None and h["harbor_title"] == "Feeling unsafe at home?"
    assert set(h["question"]) == {"id", "text", "answered", "state"} and set(h["checkin"]) == {"week", "answered", "state"}
    pair(env)
    hb = env.client.get("/orbit", headers=HB).json()
    assert hb["paired"] is True and hb["partner_name"] == "Riya" and hb["sharing"]["rituals"] is True
    assert env.client.get("/orbit", headers=HA).json()["partner_name"] == "Ashmit"


def test_the_harbor_resources_follow_country_and_gender(env):
    india = env.client.get("/orbit/harbor", headers=HA).json()
    assert india["title"] == "Feeling unsafe at home?" and [r["number"] for r in india["resources"]] == ["112", "181", "14490"]
    doc_store.put(env.db, A, "experience", "main", {"identity": {"country": "other", "gender": "woman"}})
    import chat_cache
    chat_cache.forget_user(A)
    assert [r["number"] for r in env.client.get("/orbit/harbor", headers=HA).json()["resources"]] == [""]


def test_it_is_deleted_with_everything_else(env):
    env.client.put("/orbit/profile", json={"status": "dating"}, headers=HA)
    env.client.post("/orbit/question", json={"answer": "x walk"}, headers=HA)
    env.client.post("/orbit/checkin", json={"answers": {"wish": "rest"}}, headers=HA)
    env.client.post("/orbit/notes", json={"kind": "repair", "text": "n"}, headers=HA)
    doc_store.put(env.db, A, "orbit_weather", "main", {"window": 1, "line": None})
    kinds = {d["kind"] for d in __import__("data_rights").export_documents(env.db, A)}
    assert {"orbit_profile", "orbit_question", "orbit_checkin", "orbit_note", "orbit_weather"} <= kinds
    doc_store.delete_everything(env.db, A)
    assert not {"orbit_profile", "orbit_question", "orbit_checkin", "orbit_note", "orbit_weather"} & {d["kind"] for d in __import__("data_rights").export_documents(env.db, A)}
