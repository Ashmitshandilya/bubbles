"""Small talk is answered by Bubbles itself, never waves off an earlier safety reply, and sources are shown only when they really match."""
import chat_pipeline as cp
from consent import consent_needed_reply


def test_small_talk_kinds():
    for text in ["Hey bubbles", "hi", "Hii!!", "hello there", "good morning", "namaste bubbles", "hey bubbles 💗", "sup"]:
        assert cp.small_talk_kind(text) == "greeting", text
    for text in ["thanks", "Thank you so much!", "thx bubbles"]:
        assert cp.small_talk_kind(text) == "thanks", text
    assert cp.small_talk_kind("good night") == "bye"
    assert cp.small_talk_kind("bye bubbles") == "bye"
    assert cp.small_talk_kind("ok") == "ack"
    assert cp.small_talk_kind("got it") == "ack"
    assert cp.small_talk_kind("sure") is None          # after an offer, "sure" means yes: the real reply handles it
    for text in ["Hey bubbles, how are you?", "kaise ho", "hello ji kaisi ho", "how r u", "how are you doing?", "hru", "how's it going"]:
        assert cp.small_talk_kind(text) == "how_are_you", text
    assert cp.small_talk_kind("how are you so sure my period is late") is None


def test_health_content_or_distress_is_never_small_talk():
    for text in ["hey bubbles I have a headache", "hi, chest pain since morning", "hello what is PCOS?", "good", "no", "",
                 "thanks but my stomach hurts", "hi 😭", "ok 😢", "bye 💔"]:
        assert cp.small_talk_kind(text) is None, text


def test_punctuation_does_not_change_the_reply():
    assert cp.small_talk_reply("Good night!", name="A") == cp.small_talk_reply("good night", name="A")
    assert cp.small_talk_reply("Good night!", name="A").startswith("Good night")
    assert cp.small_talk_reply("Good morning!!", name=None) == "Good morning! How did you sleep?"
    assert "badhiya" in cp.small_talk_reply("kaise ho bubbles", name=None)


def test_greeting_routes_locally_and_names_the_person():
    turn = cp.analyze_turn("Hey bubbles", [])
    assert turn.route == "small_talk"
    reply = cp.deterministic_reply(turn, name="Sudiksha", saved_events=0)
    assert "Sudiksha" in reply and "AI" not in reply
    assert cp.deterministic_reply(turn, name="Sudiksha", saved_events=0) == reply  # stable for a retried message


def test_emergency_words_still_win_over_a_greeting():
    assert cp.analyze_turn("hi I have crushing chest pain and can't breathe", []).route == "emergency"


# ---- an earlier safety reply is never waved off by small talk

def _bubbles(content, *, kind="reply", state="NO_REDFLAG", concepts=(), retracted=False):
    return {"role": "bubbles", "content": content,
            "metadata": {"kind": kind, "safety": {"state": state, "concepts": list(concepts), "retracted": retracted}}}


def _history(*bubbles_rows):
    rows = []
    for row in bubbles_rows:
        rows += [{"role": "user", "content": "..."}, row]
    return rows


def _crisis_concept():
    return next(iter(cp.CRISIS))


CRISIS_REPLY = _bubbles("I'm really glad you told me...", kind="emergency", state="EMERGENCY", concepts=[_crisis_concept()])
CHEST_REPLY = _bubbles("Please get urgent medical help...", kind="emergency", state="EMERGENCY", concepts=["chest_pain"])
CLARIFY_REPLY = _bubbles("Is the chest pain still happening right now, or has it stopped?", kind="clarification",
                         state="POTENTIAL_REDFLAG_NEEDS_CLARIFICATION", concepts=["chest_pain"])
URGENT_REPLY = _bubbles("This deserves prompt attention...", state="URGENT", concepts=["fever"])


def test_small_talk_after_a_crisis_reply_restates_the_help_not_a_goodbye():
    for text in ["bye", "goodbye", "good night", "ok", "thanks"]:
        turn = cp.analyze_turn(text, _history(CRISIS_REPLY))
        assert turn.route == "safety_followup", text
        reply = cp.deterministic_reply(turn, name="Sudiksha", saved_events=0)
        assert "emergency" in reply and "988" in reply and "Sleep well" not in reply and "Take care" not in reply, text


def test_small_talk_after_an_emergency_or_clarification_or_urgent_reply():
    reply = cp.deterministic_reply(cp.analyze_turn("good night", _history(CHEST_REPLY)), name=None, saved_events=0)
    assert "still happening" in reply and "emergency" in reply and "Sleep well" not in reply
    reply = cp.deterministic_reply(cp.analyze_turn("ok", _history(CLARIFY_REPLY)), name=None, saved_events=0)
    assert "still happening right now" in reply and "0 to 10" in reply
    reply = cp.deterministic_reply(cp.analyze_turn("thanks", _history(URGENT_REPLY)), name=None, saved_events=0)
    assert "clinician" in reply and "today" in reply


def test_a_retracted_safety_reply_no_longer_holds_small_talk_back():
    retracted = _bubbles("Please get urgent medical help...", kind="emergency", state="EMERGENCY", retracted=True)
    assert cp.analyze_turn("thanks", _history(retracted)).route == "small_talk"


def test_only_the_newest_reply_counts():
    later = _bubbles("Glad you're feeling better. Anything else?")
    assert cp.analyze_turn("hi", _history(CHEST_REPLY, later)).route == "small_talk"


def test_ok_after_a_question_is_a_yes_for_the_real_reply():
    offer = _bubbles("Would you like a few ideas for a calmer wind-down routine?")
    for text in ["ok", "okay", "alright", "got it"]:
        assert cp.analyze_turn(text, _history(offer)).route == "ai", text
    assert cp.analyze_turn("thanks", _history(offer)).route == "small_talk"   # thanks is not a yes
    assert cp.analyze_turn("ok", _history(_bubbles("Saved your sleep."))).route == "small_talk"


# ---- evidence

def test_no_evidence_lookup_for_small_talk_but_short_requests_still_get_it():
    assert cp.evidence_query([], "Hey bubbles") == ""
    assert cp.evidence_query([], "thanks") == ""
    for text in ["tell me about iron", "benefits of turmeric", "explain insulin resistance", "foods for anemia",
                 "Is it normal to feel tired after lunch?", "what is colposcopy"]:
        assert cp.evidence_query([], text), text


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


# ---- consent wording

def test_consent_text_is_short_and_says_everything_that_is_sent():
    text = consent_needed_reply("Sudiksha")
    assert text.startswith("Sudiksha, to answer this")
    for part in ("outside AI model", "your message", "recent messages", "summary of your profile and notes", "date of birth", "gender",
                 "unless you say yes", "Settings"):
        assert part in text, part
    assert len(text.split()) <= 80 and "urgent" in text   # the safety pointer stays
    assert "—" not in text and "–" not in text
    assert consent_needed_reply(None).startswith("To answer this")
