"""Chat as the front door to Fitness: intent routing, deterministic answers, and safety behaviour (no model involved)."""
from datetime import date

import pytest

import doc_store
import fitness_chat as C
import transformation as T
from tests.fake_db import FakeDB
from test_chat_http_flow import env, H, USER  # noqa: F401  (fixture reused for the HTTP-level tests)

PROFILE = {"birth_date": "1994-05-10", "height_cm": 165, "weight_kg": 80, "target_weight_kg": 68, "formula_basis": "female", "activity_level": "light"}


@pytest.mark.parametrize("text,expected", [
    ("how many calories should I eat?", "calorie_target"), ("what's my calorie target", "calorie_target"), ("how many calories do I have left today", "calories_left"),
    ("calories left?", "calories_left"), ("how much protein do I need", "protein_target"), ("what should I eat for dinner", "plan_today"),
    ("what's my workout today", "workout_today"), ("swap my dinner please", "swap_meal"), ("why did my calories change", "why_changed"),
    ("I want to start strict mode", "start_strict"), ("start my transformation", "start_strict"),
    ("I want to starve myself", "support"), ("I made myself throw up after lunch", "support"), ("I can't stop thinking about food", "support"),
    ("I want to eat 800 calories a day", "below_floor"), ("what if I eat 600 kcal", "below_floor"),
    ("I had 2 rotis and dal for lunch", None), ("I ate 500 calories today", None), ("my sleep was bad", None), ("a banana has 105 calories", None),
    ("I want to eat 1800 calories", None),
])
def test_classify(text, expected):
    assert C.classify(text) == expected


def test_route_names():
    assert C.route_for("I want to starve myself") == "fitness_support" and C.route_for("calories left?") == "fitness_answer" and C.route_for("hello") is None


def seeded(profile=True):
    db = FakeDB()
    if profile:
        doc_store.put(db, "u1", "profile", "me", PROFILE)
    return db


def test_calorie_answers_need_a_profile_then_use_plan_engine():
    assert "birth date" in C.reply(seeded(False), "u1", "how many calories should I eat?")
    out = C.reply(seeded(), "u1", "how many calories should I eat?")
    assert "kcal" in out and "estimate" in out and "Bubbles won't go below 1200" in out and "clinician" in out
    assert "protein" in C.reply(seeded(), "u1", "how much protein do I need").lower()


def test_calories_left_uses_the_food_log():
    db = seeded()
    doc_store.put(db, "u1", "food_log", date(2026, 3, 1).isoformat(), {"entries": [{"id": "a", "totals": {"kcal": 500, "protein_g": 20}}]})
    out = C.reply(db, "u1", "how many calories do I have left today", today=date(2026, 3, 1))
    assert "500" in out and "left" in out


def test_over_budget_is_never_shaming():
    db = seeded()
    doc_store.put(db, "u1", "food_log", "2026-03-01", {"entries": [{"id": "a", "totals": {"kcal": 4000, "protein_g": 20}}]})
    out = C.reply(db, "u1", "calories left today?", today=date(2026, 3, 1))
    assert "okay" in out and "fresh start" in out and "!" not in out


def test_support_reply_pauses_an_active_strict_plan_and_is_kind():
    db = seeded()
    plan = T.make_plan({**PROFILE, "conditions": [], "medications": []}, {}, T.screen({**PROFILE}, [False] * 5, today=date(2026, 3, 1)), True, date(2026, 3, 1))
    doc_store.put(db, "u1", "transform_plan", "current", plan)
    out = C.reply(db, "u1", "I want to starve myself")
    assert "paused your strict plan" in out and "doctor" in out and "emergency number" in out
    assert doc_store.get(db, "u1", "transform_plan", "current")["status"] == "paused"
    assert not any(w in out.lower() for w in ("fat", "lazy", "disgust", "willpower", "failure"))


def test_below_floor_request_is_refused_politely_with_alternatives():
    out = C.reply(seeded(), "u1", "I want to eat 800 calories a day")
    assert "can't plan around 800" in out and "medical supervision" in out and "steady plan" in out


def test_plan_questions_point_to_screens_instead_of_changing_anything():
    db = seeded()
    assert "Diet planner" in C.reply(db, "u1", "swap my dinner please")
    assert "Diet planner" in C.reply(db, "u1", "what should I eat for dinner")
    assert "Workouts" in C.reply(db, "u1", "what's my workout today")
    assert "Fitness" in C.reply(db, "u1", "start strict mode")
    assert "don't see a plan change" in C.reply(db, "u1", "why did my calories change")


# --- through the real /chat route ------------------------------------------------------------------------------------

def post(env, text):
    r = env.client.post("/chat", json={"message": text}, headers=H)
    assert r.status_code == 200, r.text
    return r.json()


def test_chat_route_answers_fitness_questions_without_calling_the_model(env):
    doc_store.put(env.db, USER, "profile", "me", PROFILE)
    body = post(env, "how many calories should I eat?")
    assert "kcal" in body["response"] and env.ai_calls == []
    assert body["kind"] == "fitness_answer" if "kind" in body else True


def test_chat_route_support_reply_beats_daily_log_and_skips_the_model(env):
    body = post(env, "I ate nothing today and I want to starve myself")
    assert "doctor" in body["response"] and env.ai_calls == []
    assert "kcal" not in body["response"]


def test_chat_route_below_floor_is_refused(env):
    body = post(env, "I want to eat 700 calories a day to lose weight fast")
    assert "can't plan around 700" in body["response"] and env.ai_calls == []


def test_ordinary_meal_logging_still_works_and_emergencies_still_win(env):
    post(env, "I had 2 rotis and dal for lunch")
    foods = [r for r in env.db.tables.get("extracted_health_events", []) if r["event_type"] == "food"]
    assert foods and foods[0]["extracted_data"].get("calories")        # logged with a reference estimate, not routed to fitness answers
    before = len(env.ai_calls)
    urgent = post(env, "I have crushing chest pain and my arm is numb")
    assert urgent["safety"]["state"] in ("EMERGENCY", "URGENT") and len(env.ai_calls) == before
