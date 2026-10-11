"""Small talk is answered by Bubbles itself, and sources are shown only when they really match."""
import chat_pipeline as cp
from consent import consent_needed_reply


def test_small_talk_kinds():
    for text in ["Hey bubbles", "hi", "Hii!!", "hello there", "good morning", "namaste bubbles", "hey bubbles 💗"]:
        assert cp.small_talk_kind(text) == "greeting", text
    for text in ["thanks", "Thank you so much!", "thx bubbles"]:
        assert cp.small_talk_kind(text) == "thanks", text
    assert cp.small_talk_kind("good night") == "bye"
    assert cp.small_talk_kind("bye bubbles") == "bye"
    assert cp.small_talk_kind("ok") == "ack"
    assert cp.small_talk_kind("got it") == "ack"
    assert cp.small_talk_kind("sure") is None          # after an offer, "sure" means yes: the real reply handles it
    for text in ["Hey bubbles, how are you?", "kaise ho", "hello ji kaisi ho", "how r u"]:
        assert cp.small_talk_kind(text) == "how_are_you", text
    assert cp.small_talk_kind("how are you so sure my period is late") is None


def test_punctuation_does_not_change_the_reply():
    assert cp.small_talk_reply("Good night!", name="A") == cp.small_talk_reply("good night", name="A")
    assert cp.small_talk_reply("Good night!", name="A").startswith("Good night")
    assert cp.small_talk_reply("Good morning!!", name=None) == "Good morning! How did you sleep?"
    assert "badhiya" in cp.small_talk_reply("kaise ho bubbles", name=None)


def test_health_content_is_never_small_talk():
    for text in ["hey bubbles I have a headache", "hi, chest pain since morning", "hello what is PCOS?", "good", "no", "", "thanks but my stomach hurts"]:
        assert cp.small_talk_kind(text) is None, text


def test_greeting_routes_locally_and_names_the_person():
    turn = cp.analyze_turn("Hey bubbles", [])
    assert turn.route == "small_talk"
    reply = cp.deterministic_reply(turn, name="Sudiksha", saved_events=0)
    assert "Sudiksha" in reply and "AI" not in reply
    assert cp.deterministic_reply(turn, name="Sudiksha", saved_events=0) == reply  # stable for a retried message
    assert "Riya" not in cp.small_talk_reply("thanks", name=None)


def test_emergency_words_still_win_over_a_greeting():
    turn = cp.analyze_turn("hi I have crushing chest pain and can't breathe", [])
    assert turn.route != "small_talk"


def test_no_evidence_lookup_for_small_talk_or_remarks():
    assert cp.evidence_query([], "Hey bubbles") == ""
    assert cp.evidence_query([], "thanks") == ""
    assert cp.evidence_query([], "I went for a walk with my friend") == ""
    assert cp.evidence_query([], "Is it normal to feel tired after lunch?")
    assert cp.evidence_query([], "what is colposcopy")


def test_shown_evidence_keeps_real_matches_once_and_at_most_three():
    rows = [
        {"chunk_id": 1, "title": "Colposcopy: causes", "lexical_rank": None, "semantic_rank": 1},          # nearest in meaning only: dropped
        {"chunk_id": 2, "title": "Sleep and mood", "lexical_rank": 1, "semantic_rank": 2},
        {"chunk_id": 3, "title": "Sleep and Mood ", "lexical_rank": 2, "semantic_rank": 3},              # same title: dropped
        {"chunk_id": 4, "title": "Linked page", "lexical_rank": None, "semantic_rank": 4, "linked": True},  # tagged for this question: kept
        {"chunk_id": 5, "title": "Caffeine", "lexical_rank": 3, "semantic_rank": None},
        {"chunk_id": 6, "title": "Fourth", "lexical_rank": 4, "semantic_rank": 5},
    ]
    assert [r["chunk_id"] for r in cp.shown_evidence(rows)] == [2, 4, 5]
    assert cp.shown_evidence([]) == []


def test_consent_text_is_short_and_still_says_what_is_sent():
    text = consent_needed_reply("Sudiksha")
    assert text.startswith("Sudiksha, to answer this")
    for part in ("outside AI model", "your message", "recent messages", "summary of your notes", "unless you say yes", "Settings"):
        assert part in text
    assert len(text.split()) <= 70 and "urgent" in text   # the safety pointer stays
    assert "—" not in text and "–" not in text
    assert consent_needed_reply(None).startswith("To answer this")
