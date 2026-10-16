import health_semantics as h
import organ_map_engine as organs


def concepts(text):
    return {f.concept for f in h.analyze(text)}


def test_loneliness_in_plain_words_and_hinglish():
    for t in ("I feel so lonely", "nobody talks to me", "mujhe bahut akela lagta hai", "I have no one to talk to"):
        assert "loneliness" in concepts(t), t


def test_panic_is_its_own_concept_and_ordinary_anxiety_stays_anxiety():
    assert "panic_attack" in concepts("I had a panic attack today")
    assert "panic_attack" in concepts("Mujhe ghabrahat ho rahi hai")
    assert concepts("I am anxious about exams") == {"anxiety"}


def test_separation_anxiety_needs_the_being_apart_context():
    assert "separation_anxiety" in concepts("I get anxious when my husband is away")
    assert "separation_anxiety" in concepts("I panic when my mom leaves")
    assert not concepts("my husband is away this week")


def test_none_of_them_is_an_emergency_alone_and_all_map_to_the_brain():
    from safety_engine import assess_safety
    for t in ("I feel so lonely", "I get anxious when my husband is away", "I had a panic attack today"):
        assert not assess_safety(t).crisis, t
    for c in ("loneliness", "panic_attack", "separation_anxiety"):
        assert organs.CONCEPT_ORGANS[c] == ("brain",)
        assert h.display_name(c)
