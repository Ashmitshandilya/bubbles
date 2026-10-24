"""The Person Model (plan section 6): the confidence rule, the observers, the prompt block, and the /me/understanding routes."""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

BACKEND = Path(__file__).resolve().parents[1]
for p in (str(BACKEND), str(BACKEND / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

import doc_store  # noqa: E402
import person_model as pm  # noqa: E402
from fake_db import FakeDB, grant_consent  # noqa: E402

NOW = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)
USER = "00000000-0000-0000-0000-0000000000bb"
H = {"Authorization": "Bearer tok"}


def model_with(tid="reply_length", value="short", source="setup", note="setup", weight=3.0, at=NOW, prior=False):
    m = pm.new_model()
    assert pm.add_evidence(m, tid, value, source, note, weight, at, prior=prior)
    return m


def reading(m, tid="reply_length", now=NOW):
    return pm.resolve(tid, m["traits"].get(tid), now)


# --- 6.3 the confidence rule ----------------------------------------------------------------------------------------------------------

def test_one_setup_answer_gives_three_quarters_and_is_used():
    r = reading(model_with())
    assert r["confidence"] == pytest.approx(0.75) and r["used"] and r["values"] == ["short"]


def test_evidence_fades_with_a_sixty_day_half_life():
    r = reading(model_with(at=NOW - timedelta(days=60)))
    assert r["confidence"] == pytest.approx(1.5 / 2.5)           # weight 3 -> 1.5
    r = reading(model_with(at=NOW - timedelta(days=120)))
    assert r["confidence"] == pytest.approx(0.75 / 1.75) and not r["used"]


def test_contradicting_evidence_lowers_confidence():
    m = model_with()
    pm.add_evidence(m, "reply_length", "detailed", "feedback", "too_long", 1.0, NOW)
    r = reading(m)
    assert r["values"] == ["short"] and r["confidence"] == pytest.approx(3 / (4 + 1))
    pm.add_evidence(m, "reply_length", "detailed", "chat", "message_language", 2.5, NOW)
    assert reading(m)["values"] == ["detailed"]


def test_priors_alone_never_pass_the_gate():
    m = model_with(source="prior", note="association", weight=0.3, prior=True)
    pm.add_evidence(m, "reply_length", "short", "prior", "association", 0.3, NOW, prior=True)
    r = reading(m)
    assert not r["used"] and r["non_prior"] == 0.0
    assert pm.prompt_lines(m, NOW) == []
    # a prior beside real evidence adds to support but the real evidence still has to reach 1.0 on its own
    m2 = model_with(source="feedback", note="too_long", weight=0.5)
    pm.add_evidence(m2, "reply_length", "short", "prior", "association", 0.3, NOW, prior=True)
    assert not reading(m2)["used"]


def test_a_single_thumbs_down_is_a_hint_and_two_are_a_trait():
    m = pm.new_model()
    pm.add_evidence(m, "reply_length", "short", "feedback", "too_long", 1.0, NOW)
    assert not reading(m)["used"]                                  # 1 / (1 + 1) = 0.5
    pm.add_evidence(m, "reply_length", "short", "feedback", "too_long", 1.0, NOW)
    assert reading(m)["used"]                                      # 2 / (2 + 1) = 0.67


def test_a_rejected_trait_never_comes_back():
    m = model_with()
    assert pm.reject(m, "reply_length")
    assert "reply_length" not in m["traits"] and "reply_length" in m["rejected"]
    assert not pm.add_evidence(m, "reply_length", "short", "setup", "setup", 3.0, NOW)
    assert pm.prompt_lines(m, NOW) == []


def test_confirming_makes_a_trait_used_even_when_it_has_faded():
    m = model_with(at=NOW - timedelta(days=200))
    assert not reading(m)["used"]
    assert pm.confirm(m, "reply_length", NOW)
    r = reading(m)
    assert r["used"] and r["state"] == "confirmed"
    assert pm.prompt_lines(m, NOW) == ["- prefers short replies (confirmed)"]
    assert not pm.confirm(pm.new_model(), "reply_length", NOW), "nothing to confirm"


def test_evidence_is_capped_and_setup_is_kept():
    m = model_with()
    for i in range(1000):
        pm.add_evidence(m, "reply_length", "short", "feedback", "too_long", 1.0, NOW + timedelta(seconds=i))
    ev = m["traits"]["reply_length"]["evidence"]
    assert len(ev) <= pm.MAX_EVIDENCE and any(e["source"] == "setup" for e in ev)


def test_a_multi_valued_trait_reads_each_value_on_its_own():
    m = pm.new_model()
    for v in ("work_study_pressure", "money"):
        pm.add_evidence(m, "drains", v, "setup", "setup", 3.0, NOW)
    r = reading(m, "drains")
    assert set(r["values"]) == {"work_study_pressure", "money"} and r["used"]
    assert pm.line_for("drains", sorted(r["values"])) == "Money worries and work or study pressure tend to drain you."


def test_unknown_traits_values_and_notes_are_refused():
    m = pm.new_model()
    assert not pm.add_evidence(m, "astrology_sign", "leo", "setup", "setup", 1, NOW)
    assert not pm.add_evidence(m, "tone", "angry", "setup", "setup", 1, NOW)
    assert not pm.add_evidence(m, "tone", "calm_direct", "setup", "a free text note", 1, NOW)
    assert m["traits"] == {}


# --- what the page and the prompt say ---------------------------------------------------------------------------------------------------

def test_the_sentence_and_the_reason_are_plain_and_quote_nothing():
    m = model_with()
    pm.add_evidence(m, "reply_length", "short", "feedback", "too_long", 1.0, NOW)
    [row] = pm.understanding(m, NOW)
    assert row["line"] == "You like short replies." and row["confidence"] == "Sure"
    assert row["why"] == "Why we think so: you chose it in setup, and you marked a reply too long."
    assert "%" not in row["line"] + row["why"]


def test_confidence_is_told_in_words_never_numbers():
    assert [pm.confidence_word(c) for c in (0.3, 0.6, 0.79, 0.8)] == ["Not sure yet", "Fairly sure", "Fairly sure", "Sure"]


def test_the_prompt_lines_put_confirmed_first_and_stop_at_eight():
    m = pm.new_model()
    for v in ("work_study_pressure", "money", "not_enough_sleep", "health_worries", "heat", "being_rushed", "noise_or_crowds", "traffic_commute"):
        pm.add_evidence(m, "drains", v, "setup", "setup", 3.0, NOW)
    for tid, v in (("tone", "calm_direct"), ("reply_length", "short"), ("language_mix", "hinglish"), ("stress_response", "goes_quiet")):
        pm.add_evidence(m, tid, v, "setup", "setup", 3.0, NOW)
    pm.confirm(m, "tone", NOW)
    lines = pm.prompt_lines(m, NOW)
    assert len(lines) <= pm.MAX_PROMPT_LINES and lines[0].endswith("(confirmed)")


# --- the observers (deferred housekeeping) ---------------------------------------------------------------------------------------------

@pytest.fixture()
def db():
    pm._cache.invalidate(USER)
    db = FakeDB({"tok": USER})
    grant_consent(db, USER, "health_memory_from_chat")
    return db


def stored(db):
    return doc_store.get(db, USER, pm.KIND, pm.KEY)


def test_setup_answers_become_weight_three_evidence_and_redoing_setup_replaces_them(db):
    pm.observe_setup(db, USER, {"tone": "calm_direct", "reply_length": "short", "language": "hinglish", "drains": ["money"], "support_people": ["friends", "mostly_on_my_own"]}, NOW)
    m = pm.load(db, USER, fresh=True)
    assert set(m["traits"]) == {"tone", "reply_length", "language_mix", "drains", "support_people"}
    assert set(m["traits"]["support_people"]["evidence"][0]) >= {"source", "value", "note", "at", "weight"}
    assert [e["value"] for e in m["traits"]["support_people"]["evidence"]] == ["friends"]       # "mostly on my own" is not a person
    pm.observe_setup(db, USER, {"tone": "gentle_warm"}, NOW + timedelta(days=1))
    m = pm.load(db, USER, fresh=True)
    assert set(m["traits"]) == {"tone"} and m["traits"]["tone"]["evidence"][0]["value"] == "gentle_warm"


def test_feedback_reasons_feed_the_model_and_other_ratings_do_not(db):
    pm.observe_feedback(db, USER, "up", None, NOW)
    pm.observe_feedback(db, USER, "down", "other", NOW)
    pm.observe_feedback(db, USER, "down", "not_helpful", NOW)
    assert stored(db) is None
    for _ in range(2):
        pm.observe_feedback(db, USER, "down", "too_long", NOW)
    pm.observe_feedback(db, USER, "down", "worried_me", NOW)
    pm.observe_feedback(db, USER, "down", "unclear", NOW)
    m = pm.load(db, USER, fresh=True)
    assert m["traits"]["reply_length"]["evidence"][0]["value"] == "short" and len(m["traits"]["reply_length"]["evidence"]) == 2
    assert set(m["traits"]) == {"reply_length", "tone", "wording"}


def test_a_message_teaches_the_hour_and_language_but_is_never_stored(db):
    text = "mujhe aaj bahut thakan hai aur kuch accha nahi lag raha"
    pm.observe_turn(db, USER, text, 330, NOW)                       # 12:00 UTC is 17:30 in India: evening
    m = pm.load(db, USER, fresh=True)
    assert m["traits"]["active_time"]["evidence"][0]["value"] == "evening"
    assert m["traits"]["language_mix"]["evidence"][0]["value"] == "hinglish"
    assert "thakan" not in repr(stored(db)) and text not in repr(stored(db))


def test_stress_phrases_are_read_and_two_different_ones_cancel_out():
    assert pm.stress_response_of("I just shut down when it gets like this") == "goes_quiet"
    assert pm.stress_response_of("I need to vent about today") == "talks_it_out"
    assert pm.stress_response_of("I keep myself busy so I don't think") == "keeps_busy"
    assert pm.stress_response_of("I shut down but I also need to vent") is None
    assert pm.stress_response_of("what is a good dinner") is None


def test_a_short_message_does_not_teach_a_language():
    assert pm.language_of("ok") is None and pm.language_of("hmm thanks") is None
    assert pm.language_of("मुझे आज बहुत थकान है") == "hindi"
    assert pm.language_of("I slept badly last night and feel tired") == "english"


def test_the_hour_buckets():
    assert [pm.hour_bucket(h) for h in (4, 5, 8, 9, 16, 17, 21, 22, 0)] == ["late_night", "early", "early", "day", "day", "evening", "evening", "late_night", "late_night"]


def test_observers_never_raise_even_when_storage_fails():
    class Broken:
        def table(self, *_a, **_k):
            raise RuntimeError("down")
    pm.observe_setup(Broken(), USER, {"tone": "calm_direct"}, NOW)
    pm.observe_feedback(Broken(), USER, "down", "too_long", NOW)
    pm.observe_turn(Broken(), USER, "this is a long enough message", 0, NOW)
    assert pm.prompt_block(Broken(), USER) == ""


def test_prompt_block_is_empty_until_something_passes_the_gate(db):
    assert pm.prompt_block(db, USER, NOW) == ""
    pm.observe_setup(db, USER, {"reply_length": "short"}, NOW)
    block = pm.prompt_block(db, USER, NOW)
    assert block.startswith("PERSON MODEL (how this person tends to be; use quietly, never recite):\n- prefers short replies")


def test_the_read_cache_is_dropped_on_every_write(db):
    pm.observe_setup(db, USER, {"reply_length": "short"}, NOW)
    assert "short" in pm.prompt_block(db, USER, NOW)
    pm.observe_setup(db, USER, {"reply_length": "detailed"}, NOW)
    assert "fuller" in pm.prompt_block(db, USER, NOW)


def test_concurrent_writes_last_one_wins_without_a_crash(db):
    a, b = pm.load(db, USER, fresh=True), pm.load(db, USER, fresh=True)
    pm.add_evidence(a, "tone", "calm_direct", "setup", "setup", 3.0, NOW)
    pm.add_evidence(b, "tone", "gentle_warm", "setup", "setup", 3.0, NOW)
    pm.save(db, USER, a)
    pm.save(db, USER, b)
    assert pm.load(db, USER, fresh=True)["traits"]["tone"]["evidence"][0]["value"] == "gentle_warm"


def test_a_damaged_document_reads_as_empty_not_an_error(db):
    doc_store.put(db, USER, pm.KIND, pm.KEY, {"traits": {"tone": {"evidence": [{"value": "nonsense"}]}, "ghost": {"evidence": []}}, "rejected": ["tone", "x"]})
    m = pm.load(db, USER, fresh=True)
    assert m["traits"] == {} and m["rejected"] == ["tone"]


# --- the routes ------------------------------------------------------------------------------------------------------------------------

@pytest.fixture()
def api(db):
    import understanding_api

    def get_user(authorization):
        if authorization != "Bearer tok":
            from fastapi import HTTPException
            raise HTTPException(status_code=401, detail="Invalid token")
        return SimpleNamespace(id=USER)

    app = FastAPI()
    app.include_router(understanding_api.build_router(get_user, db))
    return TestClient(app)


def test_every_route_needs_a_sign_in(api):
    assert api.get("/me/understanding").status_code == 401
    assert api.put("/me/understanding/tone", json={"action": "confirm"}).status_code == 401
    assert api.delete("/me/understanding").status_code == 401


def test_a_person_with_no_data_sees_the_waiting_page_and_what_it_would_use(api):
    body = api.get("/me/understanding", headers=H).json()
    assert body["empty"] is True and body["traits"] == [] and body["intro"] == "Bubbles is still getting to know you."
    assert "how long you like replies to be" in body["would_use"] and len(body["would_use"]) >= 4


def test_the_page_lists_sentences_and_confirm_then_reject_work(api, db):
    pm.observe_setup(db, USER, {"reply_length": "short", "tone": "calm_direct"})
    traits = api.get("/me/understanding", headers=H).json()["traits"]
    assert {t["id"] for t in traits} == {"reply_length", "tone"} and all(t["line"] and t["why"] for t in traits)
    assert api.put("/me/understanding/tone", json={"action": "confirm"}, headers=H).json()["traits"][0]["state"] == "confirmed"
    after = api.put("/me/understanding/reply_length", json={"action": "reject"}, headers=H).json()
    assert [t["id"] for t in after["traits"]] == ["tone"]
    pm.observe_setup(db, USER, {"reply_length": "short", "tone": "calm_direct"})
    assert "reply_length" not in {t["id"] for t in api.get("/me/understanding", headers=H).json()["traits"]}, "rejecting removes it for good"


def test_bad_requests_get_clear_errors(api, db):
    assert api.put("/me/understanding/astrology", json={"action": "confirm"}, headers=H).status_code == 404
    assert api.put("/me/understanding/tone", json={"action": "delete"}, headers=H).status_code == 422
    assert api.put("/me/understanding/tone", json={"action": "confirm"}, headers=H).status_code == 404, "nothing learned yet"


def test_delete_wipes_the_model_and_the_rejections(api, db):
    pm.observe_setup(db, USER, {"reply_length": "short"})
    api.put("/me/understanding/reply_length", json={"action": "reject"}, headers=H)
    assert api.delete("/me/understanding", headers=H).json()["empty"] is True
    assert stored(db) is None
    pm.observe_setup(db, USER, {"reply_length": "short"})
    assert api.get("/me/understanding", headers=H).json()["traits"][0]["id"] == "reply_length"


def test_it_is_part_of_delete_all_and_the_export(db):
    import data_rights
    pm.observe_setup(db, USER, {"reply_length": "short"})
    assert any(d["kind"] == pm.KIND for d in data_rights.export_documents(db, USER))
    doc_store.delete_everything(db, USER)
    assert stored(db) is None


def test_another_person_never_sees_it(api, db):
    pm.observe_setup(db, USER, {"reply_length": "short"})
    assert doc_store.get(db, "00000000-0000-0000-0000-0000000000cc", pm.KIND, pm.KEY) is None


def test_what_is_read_from_chat_needs_the_yes_to_chat_details():
    no = FakeDB({"tok": USER})
    pm.observe_turn(no, USER, "mujhe aaj bahut thakan hai aur kuch accha nahi lag raha", 330, NOW)
    assert stored(no) is None
    pm.observe_setup(no, USER, {"tone": "calm_direct"}, NOW)      # what the person chose in setup is theirs to give: no extra yes
    assert stored(no) is not None


def test_liked_replies_whisper_a_length_hint_from_the_word_count_only(db):
    pm.observe_liked(db, USER, 0, NOW)
    assert stored(db) is None
    pm.observe_liked(db, USER, 30, NOW)
    pm.observe_liked(db, USER, 200, NOW)
    ev = pm.load(db, USER, fresh=True)["traits"]["reply_length"]["evidence"]
    assert [e["value"] for e in ev] == ["short", "detailed"] and all(e["weight"] == 0.5 and e["note"] == "liked_reply" for e in ev)
