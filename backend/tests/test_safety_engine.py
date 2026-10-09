from safety_engine import assess_safety


def test_red_chest_pain():
    result = assess_safety("I have chest pain and trouble breathing")
    assert result.level == "RED"
    assert "chest pain or pressure" in result.reasons
    assert "breathing difficulty" in result.reasons


def test_amber_severe_pain():
    result = assess_safety("This is severe headache")
    assert result.level == "AMBER"


def test_green_normal_wellness():
    result = assess_safety("I slept 7 hours")
    assert result.level == "GREEN"
