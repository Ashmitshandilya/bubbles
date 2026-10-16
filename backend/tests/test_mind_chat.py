import health_semantics as h
from mind_chat import mind_fixed_reply, mind_support_block, mind_topics


def facts(text):
    return h.analyze(text)


def test_self_and_current_topics_are_found_most_pressing_first():
    assert mind_topics(facts("I feel lonely and I had a panic attack today"))[0] == "panic_attack"
    assert mind_topics(facts("I feel lonely every night")) == ["loneliness"]


def test_other_people_the_past_and_denials_stay_quiet():
    for t in ("my friend is lonely", "I was lonely last year", "I don't feel lonely", "I had a good day"):
        assert mind_topics(facts(t)) == [], t
        assert mind_support_block(facts(t)) == "" and mind_fixed_reply(facts(t)) == "", t


def test_the_block_is_friendly_and_never_diagnoses_or_advises_medicine():
    block = mind_support_block(facts("I feel so lonely")).lower()
    assert "one small step" in block and "never name a condition" in block and "no medicine" in block


def test_the_fixed_reply_names_a_mind_tool_and_does_not_label():
    for t in ("I feel so lonely", "I had a panic attack", "I get anxious when my husband is away"):
        reply = mind_fixed_reply(facts(t))
        assert reply and "Mind" in reply, t
        assert "disorder" not in reply.lower() and "diagnos" not in reply.lower()


def test_the_loneliness_screen_is_one_question_scored_without_a_label():
    import mind_checkins as M
    q = M.screen_questions("loneliness")
    assert q["questions"] == ["How often do you feel lonely?"]
    high = M.score_screen("loneliness", [3])
    assert high["suggest_talking_to_someone"] and "14416" in high["message"] and "disorder" not in high["message"].lower()
    assert not M.score_screen("loneliness", [1])["suggest_talking_to_someone"]
    assert set(M.TOPIC_COPY) == {"anxiety", "panic", "loneliness", "apart"}
