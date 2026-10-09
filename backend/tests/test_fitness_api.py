"""Fitness API through real FastAPI routes with the stateful fake database."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import clinical_constants as K
import fitness_api
import health_logs
from db_access import register_db_error_handlers
from tests.fake_db import FakeDB

H1 = {"Authorization": "Bearer user-1"}
H2 = {"Authorization": "Bearer user-2"}
PROFILE = {"birth_date": "1994-05-10", "height_cm": 165, "weight_kg": 80, "target_weight_kg": 68, "formula_basis": "female", "activity_level": "light",
           "diet_style": "vegetarian", "menstruating": True}
SCOFF_OK = [False] * 5


@pytest.fixture
def env():
    db = FakeDB()

    def get_user(authorization):
        if not authorization:
            raise HTTPException(status_code=401, detail="Missing token")
        return SimpleNamespace(id=authorization.removeprefix("Bearer "))

    app = FastAPI()
    register_db_error_handlers(app)
    app.include_router(health_logs.build_router(get_user, db))
    app.include_router(fitness_api.build_router(get_user, db))
    return TestClient(app, raise_server_exceptions=False), db


def put_profile(client, headers=H1, **over):
    r = client.put("/profile/body", json={**PROFILE, **over}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["profile"]


def test_every_route_requires_a_token(env):
    c, _ = env
    for method, path in [("get", "/profile/body"), ("put", "/profile/body"), ("get", "/fitness/targets"), ("get", "/fitness/summary"), ("post", "/fitness/meal/parse"),
                         ("post", "/fitness/food-log"), ("get", "/fitness/food-log"), ("post", "/fitness/diet/plan"), ("get", "/fitness/diet/plan"),
                         ("post", "/fitness/workouts/plan"), ("post", "/fitness/transform/screen"), ("post", "/fitness/transform/start"), ("get", "/fitness/transform/plan"),
                         ("get", "/fitness/progress"), ("get", "/fitness/exercises"), ("get", "/fitness/foods/search")]:
        assert getattr(c, method)(path, **({"json": {}} if method in ("post", "put") else {})).status_code == 401, path


def test_profile_validation(env):
    c, _ = env
    for bad in [{"height_cm": 20}, {"weight_kg": "x"}, {"formula_basis": "robot"}, {"birth_date": "2090-01-01"}, {"diet_style": "carnivore-only"},
                {"likes": "rajma"}, {"pregnant": "yes"}, {"level": 9}, {"clinician_clearance": {"cleared": "maybe"}}]:
        r = c.put("/profile/body", json=bad, headers=H1)
        assert r.status_code == 422 and isinstance(r.json()["detail"], str), bad
    assert c.put("/profile/body", data="not json", headers=H1).status_code == 422


def test_profile_roundtrip_known_records_and_isolation(env):
    c, _ = env
    put_profile(c)
    c.post("/health/conditions", json={"condition_name": "PCOS"}, headers=H1)
    c.post("/health/allergies", json={"allergen": "peanut"}, headers=H1)
    c.post("/health/weight", json={"weight": 176.4}, headers=H1)         # lbs, as the tracker form sends
    body = c.get("/profile/body", headers=H1).json()
    assert body["age"] >= 30 and body["known"]["conditions"] == ["PCOS"] and body["known"]["allergies"] == ["peanut"]
    assert body["known"]["latest_weight_kg"] == pytest.approx(80.0, abs=0.1) and body["missing"] == []
    assert len(body["scoff_questions"]) == 5 and any(q["blocking"] for q in body["parq_questions"])
    other = c.get("/profile/body", headers=H2).json()
    assert other["profile"] == {} and other["known"]["conditions"] == []


def test_targets_need_a_complete_profile_then_work_and_carry_the_review_banner(env):
    c, _ = env
    r = c.get("/fitness/targets", headers=H1).json()
    assert r["targets"] is None and "birth date" in r["message"]
    put_profile(c)
    r = c.get("/fitness/targets", headers=H1).json()
    t = r["targets"]
    assert t["kcal"] >= t["floor_kcal"] and r["review"]["status"] == K.REVIEW_STATUS and t["goal"] == "lose"
    assert any("PCOS" in n or "pcos" in n for n in t["notes"]) is False   # no condition recorded yet
    c.post("/health/conditions", json={"condition_name": "PCOS"}, headers=H1)
    assert any("pcos" in n.lower() for n in c.get("/fitness/targets", headers=H1).json()["targets"]["notes"])


def test_unsafe_target_weight_is_explained_not_planned(env):
    c, _ = env
    put_profile(c, target_weight_kg=40)
    r = c.get("/fitness/targets", headers=H1).json()
    assert r["targets"] is None and "healthy range" in r["message"]


def test_food_search_and_meal_parse(env):
    c, _ = env
    put_profile(c, diet_style="vegetarian")
    r = c.get("/fitness/foods/search?q=paneer", headers=H1).json()
    assert r["results"] and r["label"] == "estimate"
    p = c.post("/fitness/meal/parse", json={"text": "2 rotis, dal, sabzi and chicken curry"}, headers=H1).json()
    assert [i["food"] for i in p["items"]][:3] == ["roti", "toor dal", "mixed vegetable"] and p["totals"]["kcal_low"] < p["totals"]["kcal"] < p["totals"]["kcal_high"]
    assert any("chicken curry is not vegetarian" in w for w in p["warnings"])
    assert c.post("/fitness/meal/parse", json={"text": "   "}, headers=H1).status_code == 422
    sup = c.post("/fitness/meal/parse", json={"text": "I want to starve myself, just a roti"}, headers=H1).json()
    assert "support" in sup


def test_allergy_warning_uses_recorded_allergies(env):
    c, _ = env
    put_profile(c)
    c.post("/health/allergies", json={"allergen": "dairy"}, headers=H1)
    p = c.post("/fitness/meal/parse", json={"text": "a katori of curd"}, headers=H1).json()
    assert any("allergy" in w for w in p["warnings"])


def test_food_log_add_total_delete_and_mirror(env):
    c, db = env
    put_profile(c)
    today = datetime.now(timezone.utc).date().isoformat()
    r = c.post("/fitness/food-log", json={"text": "2 rotis and dal", "meal": "lunch"}, headers=H1)
    assert r.status_code == 201
    entry = r.json()["entry"]
    log = c.get("/fitness/food-log", headers=H1).json()
    assert log["date"] == today and len(log["entries"]) == 1 and log["totals"]["kcal"] == entry["totals"]["kcal"] and log["budget"]["remaining_kcal"] < log["budget"]["budget_kcal"]
    mirrors = [r for r in db.tables.get("extracted_health_events", []) if r["extracted_data"]["_prov"]["domain"] == "food_log"]
    assert len(mirrors) == 1 and mirrors[0]["event_type"] == "food" and mirrors[0]["extracted_data"]["calories"] == entry["totals"]["kcal"]
    assert c.get("/fitness/food-log", headers=H2).json()["entries"] == []                 # isolation
    assert c.delete(f"/fitness/food-log/{entry['id']}", headers=H2).status_code == 404
    gone = c.delete(f"/fitness/food-log/{entry['id']}", headers=H1).json()
    assert gone["entries"] == [] and mirrors[0]["extraction_status"] == "retracted"
    assert c.post("/fitness/food-log", json={"text": "zzzz qqqq"}, headers=H1).status_code == 422
    assert c.post("/fitness/food-log", json={"text": "roti", "meal": "brunch"}, headers=H1).status_code == 422
    assert c.post("/fitness/food-log", json={"text": "roti", "date": "nope"}, headers=H1).status_code == 422


def test_custom_foods_are_private_and_validated(env):
    c, _ = env
    ok = c.post("/fitness/foods/custom", json={"name": "Amma's laddoo", "serving": "1 ladoo", "serving_g": 40, "kcal": 160, "protein_g": 3, "carbs_g": 20, "fat_g": 7.5}, headers=H1)
    assert ok.status_code == 201
    assert c.post("/fitness/foods/custom", json={"name": "bad", "serving_g": 0, "kcal": 10}, headers=H1).status_code == 422
    # missing calories are rejected, never saved as 0 kcal (that would understate intake)
    assert c.post("/fitness/foods/custom", json={"name": "mystery sweet", "serving_g": 40}, headers=H1).status_code == 422
    assert c.post("/fitness/foods/custom", json={"name": "plain water", "serving_g": 250, "kcal": 0}, headers=H1).status_code == 201
    assert any("laddoo" in f["name"] for f in c.get("/fitness/foods/search?q=laddoo", headers=H1).json()["results"])
    assert not any("amma" in f["name"] for f in c.get("/fitness/foods/search?q=amma", headers=H2).json()["results"])
    log = c.post("/fitness/food-log", json={"text": "1 amma's laddoo"}, headers=H1)
    assert log.status_code == 201 and log.json()["entry"]["totals"]["kcal"] == 160


def test_diet_plan_swap_and_grocery(env):
    c, _ = env
    assert c.post("/fitness/diet/plan", json={}, headers=H1).status_code == 422          # no profile yet
    put_profile(c, diet_style="vegan")
    r = c.post("/fitness/diet/plan", json={"must_include": ["rajma"], "meals_per_day": 4}, headers=H1)
    assert r.status_code == 200
    plan = r.json()["plan"]
    t = c.get("/fitness/targets", headers=H1).json()["targets"]
    assert len(plan["days"]) == 7 and all(t["kcal"] <= d["totals"]["kcal"] <= t["kcal"] * 1.06 for d in plan["days"])
    assert c.get("/fitness/diet/plan", headers=H1).json()["exists"] is True and c.get("/fitness/diet/plan", headers=H2).json()["exists"] is False
    first = plan["days"][0]["meals"][0]
    opts = c.post("/fitness/diet/swap-options", json={"day": 1, "slot": first["slot"]}, headers=H1).json()["options"]
    assert opts
    sw = c.post("/fitness/diet/swap", json={"day": 1, "slot": first["slot"], "template_id": opts[0]["template_id"]}, headers=H1)
    assert sw.status_code == 200 and sw.json()["day"]["meals"][0]["template_id"] == opts[0]["template_id"]
    assert c.post("/fitness/diet/swap", json={"day": 1, "slot": first["slot"], "template_id": "b-eggs"}, headers=H1).status_code == 422   # not vegan: refused
    g = c.get("/fitness/diet/grocery?people=2", headers=H1).json()
    assert "Fresh produce" in g["aisles"]
    assert c.get("/fitness/diet/grocery", headers=H2).status_code == 404


def test_workout_flow_screen_plan_adapt_log(env):
    c, _ = env
    put_profile(c, equipment=["home"], level=2, days_per_week=4)
    assert c.post("/fitness/workouts/plan", json={}, headers=H1).status_code == 409                      # screen first
    answers = {k: False for k, _q in K.PARQ_QUESTIONS}
    assert c.post("/fitness/workouts/screen", json={"answers": {"heart": False}}, headers=H1).json()["mode"] == "incomplete"
    assert c.post("/fitness/workouts/screen", json={"answers": {"heart": "no"}}, headers=H1).status_code == 422
    assert c.post("/fitness/workouts/screen", json={"answers": answers}, headers=H1).json()["mode"] == "full"
    r = c.post("/fitness/workouts/plan", json={}, headers=H1)
    assert r.status_code == 200 and r.json()["plan"]["ok"] and len(r.json()["plan"]["sessions"]) == 4
    nxt = c.post("/fitness/workouts/plan", json={"next_week": True}, headers=H1).json()["plan"]
    assert nxt["week_index"] == 2
    stop = c.post("/fitness/workouts/adapt", json={"session": 0, "feedback": {"chest_pain": True}}, headers=H1).json()
    assert stop["stop"] is True
    short = c.post("/fitness/workouts/adapt", json={"session": 0, "minutes": 20, "feedback": {"low_energy": True}}, headers=H1).json()
    assert short["session"]["minutes"] == 20 and not short["stop"]
    logged = c.post("/fitness/workouts/log", json={"title": "Brisk walk", "activity": "walking_brisk", "minutes": 30, "rpe": 4}, headers=H1)
    assert logged.status_code == 201 and logged.json()["session"]["burn"]["label"] == "estimate"
    assert c.get("/health/activity", headers=H1).json()["entries"][0]["type"] == "Brisk walk"
    assert c.get("/fitness/workouts/log", headers=H1).json()["days"][0]["sessions"][0]["title"] == "Brisk walk"
    assert c.post("/fitness/workouts/log", json={"title": "x"}, headers=H1).status_code == 422


def test_blocking_screen_answer_limits_the_plan(env):
    c, _ = env
    put_profile(c)
    ans = {k: False for k, _q in K.PARQ_QUESTIONS} | {"chest": True}
    s = c.post("/fitness/workouts/screen", json={"answers": ans}, headers=H1).json()
    assert s["mode"] == "clinician_first" and "doctor" in s["message"]
    plan = c.post("/fitness/workouts/plan", json={}, headers=H1).json()["plan"]
    assert plan["mode"] == "clinician_first"


# --- strict mode over HTTP ----------------------------------------------------------------------------------

def start_body(**over):
    body = {"scoff": SCOFF_OK, "acknowledged": True, "selections": {"foods": ["rajma"], "meals_per_day": 4, "equipment": "home", "level": 2, "days_per_week": 4}}
    body.update(over)
    return body


def test_transform_screen_refuses_with_kind_reasons(env):
    c, _ = env
    put_profile(c, birth_date="2011-01-01")
    r = c.post("/fitness/transform/screen", json={"scoff": SCOFF_OK}, headers=H1).json()
    assert r["decision"] == "refused" and r["exclusions"][0]["code"] == "under_18"
    assert c.post("/fitness/transform/start", json=start_body(), headers=H1).status_code == 403
    assert c.post("/fitness/transform/screen", json={"scoff": [True]}, headers=H1).status_code == 422


def test_server_rechecks_screening_even_if_the_client_claims_ok(env):
    c, _ = env
    put_profile(c)
    c.post("/health/conditions", json={"condition_name": "Type 1 diabetes"}, headers=H1)
    r = c.post("/fitness/transform/start", json=start_body(), headers=H1)
    assert r.status_code == 403 and c.get("/fitness/transform/plan", headers=H1).json()["exists"] is False
    pos = c.post("/fitness/transform/screen", json={"scoff": [True, True, False, False, False]}, headers=H2)
    assert pos.status_code == 422                                                            # H2 has no profile yet: asked to complete it
    put_profile(c, headers=H2)
    assert c.post("/fitness/transform/screen", json={"scoff": [True, True, False, False, False]}, headers=H2).json()["alternative"] == "support"


def test_full_strict_mode_lifecycle(env):
    c, db = env
    put_profile(c)
    pv = c.post("/fitness/transform/preview", json=start_body(), headers=H1).json()
    assert pv["screening"]["decision"] == "allowed" and pv["preview"]["diet"]["ok"] and pv["review"]["status"] == K.REVIEW_STATUS
    assert c.post("/fitness/transform/start", json=start_body(acknowledged=False), headers=H1).status_code == 422
    s = c.post("/fitness/transform/start", json=start_body(), headers=H1)
    assert s.status_code == 201
    plan = s.json()["plan"]
    assert plan["status"] == "active" and plan["acknowledged_at"] and plan["constants_status"] == K.REVIEW_STATUS
    assert c.post("/fitness/transform/start", json=start_body(), headers=H1).status_code == 409           # one plan at a time
    assert c.get("/fitness/diet/plan", headers=H1).json()["exists"]                                         # the diet plan is synced in
    today = c.get("/fitness/transform/today", headers=H1).json()
    assert today["view"]["budget"]["budget_kcal"] == plan["targets"]["kcal"] and today["meals"]["meals"]
    # not enough data yet: nothing changes
    chk = c.post("/fitness/transform/checkin", json={}, headers=H1).json()
    assert chk["decision"] == "insufficient_data" and chk["applied"] is False
    # an alarming note pauses the plan immediately, kindly
    risky = c.post("/fitness/transform/checkin", json={"note": "I want to starve myself"}, headers=H1).json()
    assert risky["decision"] == "pause" and risky["applied"] is True and "Bubbles is pausing" in risky["messages"][0]
    assert c.get("/fitness/transform/plan", headers=H1).json()["plan"]["status"] == "paused"
    assert c.post("/fitness/transform/resume", json={"scoff": SCOFF_OK}, headers=H1).status_code == 409    # safety cooldown
    assert c.post("/fitness/transform/checkin", json={}, headers=H1).status_code == 409
    other = c.get("/fitness/transform/plan", headers=H2).json()
    assert other["exists"] is False


def test_checkin_proposal_requires_confirmation_before_changing_calories(env):
    c, db = env
    put_profile(c)
    c.post("/fitness/transform/start", json=start_body(), headers=H1)
    base = c.get("/fitness/transform/plan", headers=H1).json()["plan"]["targets"]["kcal"]
    today = datetime.now(timezone.utc).date()
    for i in range(14):
        d = today - timedelta(days=13 - i)
        c.post("/health/weight", json={"weight": 176.4 - 0.03 * i * 2.2046, "date": d.isoformat() + "T08:00:00Z"}, headers=H1)
        c.post("/fitness/food-log", json={"text": "chicken biryani, 2 rotis", "date": d.isoformat()}, headers=H1)
    chk = c.post("/fitness/transform/checkin", json={}, headers=H1).json()
    assert chk["decision"] in ("adjust", "continue", "pause") and chk["applied"] is False or chk["decision"] == "pause"
    after = c.get("/fitness/transform/plan", headers=H1).json()["plan"]
    if chk["decision"] != "pause":
        assert after["targets"]["kcal"] == base                      # unchanged until the user confirms
        assert abs(chk["change_kcal"]) <= K.MAX_WEEKLY_CALORIE_CHANGE
        applied = c.post("/fitness/transform/checkin/apply", json={"accept": True}, headers=H1).json()["plan"]
        assert applied["targets"]["kcal"] >= applied["targets"]["floor_kcal"] and applied["weeks_on_plan"] == 1


def test_pause_finish_goal_and_report(env):
    c, _ = env
    put_profile(c)
    c.post("/fitness/transform/start", json=start_body(), headers=H1)
    assert c.post("/fitness/transform/pause", json={"reason": "holiday"}, headers=H1).json()["plan"]["status"] == "paused"
    assert c.post("/fitness/transform/resume", json={"scoff": SCOFF_OK}, headers=H1).json()["plan"]["status"] == "active"
    g = c.put("/fitness/transform/goal", json={"target_weight_kg": 70, "scoff": SCOFF_OK}, headers=H1)
    assert g.status_code == 200 and g.json()["plan"]["target_weight_kg"] == 70
    assert c.put("/fitness/transform/goal", json={"target_weight_kg": 38, "scoff": SCOFF_OK}, headers=H1).status_code == 403
    assert "diagnosis" in c.get("/fitness/transform/report", headers=H1).json()["report"]["note"]
    done = c.post("/fitness/transform/finish", headers=H1).json()["plan"]
    assert done["status"] == "completed" and done["maintenance"]
    assert c.post("/fitness/transform/start", json=start_body(), headers=H1).status_code == 201           # a finished plan can be followed by a new one


def test_progress_and_measurements(env):
    c, _ = env
    put_profile(c)
    for i, lbs in enumerate([176.0, 175.0, 174.5]):
        d = (datetime.now(timezone.utc) - timedelta(days=10 - i * 3)).date().isoformat()
        c.post("/health/weight", json={"weight": lbs, "date": d + "T08:00:00Z"}, headers=H1)
    assert c.post("/fitness/measurements", json={"waist_cm": 84}, headers=H1).status_code == 201
    assert c.post("/fitness/measurements", json={}, headers=H1).status_code == 422
    p = c.get("/fitness/progress", headers=H1).json()
    assert len(p["weights"]) == 3 and p["trend"][-1]["trend_kg"] and p["measurements"][0]["waist_cm"] == 84 and "consistency" in p["adherence"]["label"]


def test_summary_pulls_everything_together(env):
    c, _ = env
    put_profile(c)
    c.post("/fitness/food-log", json={"text": "poha and chai"}, headers=H1)
    s = c.get("/fitness/summary", headers=H1).json()
    assert s["targets"] and s["eaten"]["kcal"] > 0 and s["budget"]["remaining_kcal"] < s["budget"]["budget_kcal"] and s["transform"] is None


def test_errors_do_not_leak_internals(env):
    c, db = env
    put_profile(c)
    db.failures["health_events"] = RuntimeError("secret database detail")
    r = c.get("/fitness/diet/plan", headers=H1)
    assert r.status_code >= 500 and "secret" not in r.text


def test_meals_mentioned_in_chat_count_toward_the_day(env):
    c, db = env
    put_profile(c)
    today = datetime.now(timezone.utc).date().isoformat()
    db.tables.setdefault("extracted_health_events", []).append({
        "id": "e1", "user_id": "user-1", "event_type": "food", "extraction_status": "confirmed", "created_at": "2026-03-01T10:00:00+00:00",
        "extracted_data": {"name": "rice, dal", "meal": "lunch", "calories": 330, "protein_g": 12, "date": today,
                           "_prov": {"source": "user_message", "extractor": "rules", "assertion": "present", "subject": "self"}}})
    log = c.get("/fitness/food-log", headers=H1).json()
    assert log["totals"]["kcal"] == 330 and log["entries"][0]["source"] == "chat"
    assert c.get("/fitness/food-log", headers=H2).json()["totals"]["kcal"] == 0
    # a retracted chat event no longer counts
    db.tables["extracted_health_events"][0]["extraction_status"] = "retracted"
    assert c.get("/fitness/food-log", headers=H1).json()["totals"]["kcal"] == 0


def test_barcode_endpoint_validates_and_degrades(env, monkeypatch):
    c, _ = env
    import open_food_facts as O
    assert c.get("/fitness/foods/barcode/12", headers=H1).status_code == 422
    monkeypatch.setattr(O, "_fetch", lambda url: {"status": 1, "product": {"product_name": "Oat bar", "nutriments": {"energy-kcal_100g": 400}}})
    ok = c.get("/fitness/foods/barcode/8901063020017", headers=H1)
    assert ok.status_code == 200 and ok.json()["food"]["kcal"] == 400 and "Check it" in ok.json()["note"]
    monkeypatch.setattr(O, "_fetch", lambda url: (_ for _ in ()).throw(OSError("down")))
    assert c.get("/fitness/foods/barcode/8901063020999", headers=H1).status_code == 404


def test_custom_foods_cannot_be_used_to_distort_intake(env):
    c, _ = env
    bad = [{"name": "x", "serving_g": 1, "kcal": 5000}, {"name": "y", "serving_g": 100, "kcal": 800, "protein_g": 1, "carbs_g": 1, "fat_g": 1}]
    for b in bad:
        r = c.post("/fitness/foods/custom", json=b, headers=H1)
        assert r.status_code == 422 and isinstance(r.json()["detail"], str), b
