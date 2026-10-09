from types import SimpleNamespace

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import data_rights
import doc_store
from tests.fake_db import FakeDB

H1, H2 = {"Authorization": "Bearer user-1"}, {"Authorization": "Bearer user-2"}


def make():
    db = FakeDB()

    def get_user(a):
        if not a:
            raise HTTPException(status_code=401, detail="Missing token")
        return SimpleNamespace(id=a.removeprefix("Bearer "))

    app = FastAPI()
    app.include_router(data_rights.build_router(get_user, db))
    return TestClient(app), db


def test_export_and_delete_are_owner_scoped_and_need_confirmation():
    c, db = make()
    doc_store.put(db, "user-1", "profile", "me", {"height_cm": 170})
    doc_store.put(db, "user-1", "food_log", "2026-03-01", {"entries": []})
    doc_store.put(db, "user-2", "profile", "me", {"height_cm": 150})
    out = c.get("/me/whole-health/export", headers=H1).json()
    assert out["count"] == 2 and out["kinds"] == {"profile": 1, "food_log": 1} and all("id" not in d for d in out["documents"])
    assert c.get("/me/whole-health/export").status_code == 401
    assert c.delete("/me/whole-health/data", headers=H1).status_code == 422
    assert doc_store.get(db, "user-1", "profile", "me")                      # nothing deleted without confirm
    assert c.delete("/me/whole-health/data?confirm=true", headers=H1).json()["deleted"] == 2
    assert doc_store.get(db, "user-1", "profile", "me") is None and doc_store.get(db, "user-2", "profile", "me")
