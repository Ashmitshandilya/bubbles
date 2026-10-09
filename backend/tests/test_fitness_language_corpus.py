"""Independently authored, labelled phrases for the Fitness language layer (fitness_chat.classify, restriction language, meals)."""
import pytest

import fitness_chat as C
import meal_composer as M
import transformation as T

CLASSIFY = [
    # (message, expected classification)
    ("how many calories should i be eating", "calorie_target"), ("what is my daily calorie goal", "calorie_target"), ("how much should I eat today", "calorie_target"),
    ("tell me my calorie budget please", "calorie_target"), ("how many kcal do I need", "calorie_target"),
    ("how many calories are remaining", "calories_left"), ("calories left for today?", "calories_left"), ("how many calories do I have left", "calories_left"),
    ("what's my protein target", "protein_target"), ("how much protein should I have", "protein_target"),
    ("what should I eat tonight", "plan_today"), ("what do I cook today", "plan_today"), ("show me today's meal plan", "plan_today"), ("what's for lunch", "plan_today"),
    ("what's my workout", "workout_today"), ("what workout should I do", "workout_today"), ("today's training plan?", "workout_today"),
    ("can you swap my breakfast", "swap_meal"), ("replace dinner with something lighter", "swap_meal"), ("change my lunch", "swap_meal"),
    ("why did my plan change", "why_changed"), ("why did my calories go down", "why_changed"), ("why did my target increase", "why_changed"),
    ("I want to try the strict plan", "start_strict"), ("start my heavy transformation", "start_strict"), ("begin transformation mode", "start_strict"),
    # restriction / disordered eating -> support
    ("I'm going to starve myself this week", "support"), ("I keep making myself throw up after I eat", "support"), ("I made myself sick again", "support"),
    ("I've lost control of my eating and binged again", "support"), ("I can't stop thinking about food all day", "support"),
    ("I'll skip all my meals tomorrow", "support"), ("I want to punish myself for eating dessert", "support"), ("I use laxatives to lose weight", "support"),
    # below the safe floor
    ("I want to eat 500 calories a day", "below_floor"), ("my diet is 900 kcal a day", "below_floor"), ("can I live on 700 calories", "below_floor"),
    ("what if I only eat 800 calories", "below_floor"), ("i plan to limit my intake to 600 cal", "below_floor"),
    # ordinary talk must NOT be captured
    ("I had dal and rice for lunch", None), ("slept badly last night", None), ("my knee hurts when I run", None), ("a samosa has about 260 calories", None),
    ("I ate 2000 calories yesterday", None), ("I want to eat 2000 calories", None), ("I'm starving, what a long day", None), ("my friend starved herself and I'm worried about her", None),
    ("Can you remind me to drink water", None), ("my period started", None), ("tell me a joke", None), ("the strict teacher was fine", None),
]


@pytest.mark.parametrize("text,expected", CLASSIFY)
def test_classify_corpus(text, expected):
    got = C.classify(text)
    if text == "my friend starved herself and I'm worried about her":
        assert got in (None, "support"), got            # about someone else: either is acceptable, never a plan answer
        return
    if text == "I'm starving, what a long day":
        assert got is None
        return
    assert got == expected, (text, got)


MEALS = [
    ("2 idlis with sambar", ["idli", "sambar"], 2), ("a bowl of dal and 2 rotis", ["toor dal", "roti"], None), ("3 eggs", ["boiled egg"], 3),
    ("one banana and a glass of milk", ["banana", "milk"], None), ("chicken biryani", ["chicken biryani"], None), ("paneer paratha with curd", ["paneer paratha", "curd"], None),
    ("200 g chicken breast", ["chicken breast"], None), ("half a katori of rice", ["rice"], None), ("masala dosa and filter coffee", ["masala dosa", "coffee"], None),
    ("handful of almonds", ["almonds"], None), ("2 tsp ghee", ["ghee"], None), ("poha, chai", ["poha", "tea"], None),
]


@pytest.mark.parametrize("text,foods,first_qty", MEALS)
def test_meal_corpus(text, foods, first_qty):
    r = M.compose(text)
    assert [i["food"] for i in r["items"]] == foods, r
    if first_qty:
        assert r["items"][0]["quantity"] == first_qty
    assert all(i["kcal_low"] <= i["kcal"] <= i["kcal_high"] for i in r["items"])


@pytest.mark.parametrize("text", ["I want to starve myself", "making myself throw up", "i binged again"])
def test_restriction_detector_positive(text):
    assert T.restriction_language(text)


@pytest.mark.parametrize("text", ["I can eat 2000 calories", "starving after the gym", "I threw a party", "healthy breakfast ideas", "the bulimia documentary was interesting"])
def test_restriction_detector_negative(text):
    assert T.restriction_language(text) == []
