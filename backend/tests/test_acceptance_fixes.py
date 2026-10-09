"""Sir Noah acceptance must-fixes: delete-all cannot erase safety holds; Cycle modes switch off deficits."""
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import data_rights
import doc_store
from tests.test_fitness_api import H1, SCOFF_OK, env, put_profile, start_body  # noqa: F401


def delete_all(db):
    app = FastAPI()
    app.include_router(data_rights.build_router(lambda a: SimpleNamespace(id="user-1"), db))
    return TestClient(app).delete("/me/whole-health/data?confirm=true").json()


def test_delete_all_keeps_the_safety_pause_and_positive_screen(env):
    c, db = env
    put_profile(c)
    c.post("/fitness/transform/start", json=start_body(), headers=H1)
    c.post("/fitness/transform/checkin", json={"note": "I want to starve myself"}, headers=H1)
    out = delete_all(db)
    assert "safety hold" in out["note"]
    assert doc_store.get(db, "user-1", "safety_pause", "last") and doc_store.get(db, "user-1", "transform_plan", "current") is None
    put_profile(c)
    r = c.post("/fitness/transform/screen", json={"scoff": SCOFF_OK}, headers=H1).json()
    assert r["decision"] == "refused" and any(e["code"] == "recent_safety_pause" for e in r["exclusions"])
    assert c.post("/fitness/transform/start", json=start_body(), headers=H1).status_code == 403


@pytest.mark.parametrize("mode", ["pregnancy", "conceive", "postpartum"])
def test_cycle_modes_block_strict_mode_and_deficits(env, mode):
    c, db = env
    put_profile(c)
    doc_store.put(db, "user-1", "cycle_settings", "main", {"mode": mode})
    r = c.post("/fitness/transform/screen", json={"scoff": SCOFF_OK}, headers=H1).json()
    assert r["decision"] == "refused" and any(e["code"] == "pregnancy" for e in r["exclusions"])
    if mode != "conceive":          # trying to conceive blocks STRICT mode; a gentle plan is still allowed (packet 6.1)
        t = c.get("/fitness/targets", headers=H1).json()["targets"]
        assert t["goal"] == "maintain" and t["deficit_kcal"] == 0
