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


def test_export_includes_only_my_community_posts_and_comments():
    c, db = make()
    db.tables["community_posts"] = [
        {"id": "p1", "author_id": "user-1", "alias": "Quiet Otter 4821", "display_mode": "anonymous", "topic": "sleep", "body": "my own post", "status": "visible", "created_at": "2026-10-01T10:00:00+00:00"},
        {"id": "p2", "author_id": "user-1", "alias": "x", "display_mode": "named", "topic": "mind", "body": "[deleted]", "status": "removed", "reason_code": "deleted", "created_at": "2026-10-02T10:00:00+00:00"},
        {"id": "p3", "author_id": "user-2", "alias": "Calm Heron 1234", "display_mode": "anonymous", "topic": "food", "body": "a stranger post", "status": "visible", "created_at": "2026-10-03T10:00:00+00:00"}]
    db.tables["community_comments"] = [
        {"id": "c1", "post_id": "p3", "author_id": "user-1", "alias": "Kind Fox 1111", "body": "my comment on theirs", "status": "held", "created_at": "2026-10-04T10:00:00+00:00"},
        {"id": "c2", "post_id": "p1", "author_id": "user-2", "alias": "Calm Heron 1234", "body": "their comment on mine", "status": "visible", "created_at": "2026-10-05T10:00:00+00:00"}]
    out = c.get("/me/whole-health/export", headers=H1).json()
    assert out["community_included"] is True
    assert out["community"] == {"posts": [{"topic": "sleep", "body": "my own post", "status": "visible", "created_at": "2026-10-01T10:00:00+00:00"}],
                                "comments": [{"body": "my comment on theirs", "status": "held", "created_at": "2026-10-04T10:00:00+00:00"}]}
    text = str(out["community"])
    assert "stranger" not in text and "their comment" not in text and "user-2" not in text and "Heron" not in text and "p3" not in text


def test_export_says_so_when_the_community_part_could_not_be_read_and_skips_tables_not_created_yet():
    c, db = make()
    db.failures["community_posts"] = RuntimeError('relation "community_posts" does not exist')
    assert c.get("/me/whole-health/export", headers=H1).json()["community"] == {"posts": [], "comments": []}
    db.failures["community_posts"] = RuntimeError("connection reset")
    out = c.get("/me/whole-health/export", headers=H1).json()
    assert out["community"] is None and out["community_included"] is False and out["status"] == "success"


def test_delete_all_is_a_503_not_a_success_when_the_community_wipe_still_fails(monkeypatch):
    import community_api
    c, db = make()
    doc_store.put(db, "user-1", "profile", "me", {"height_cm": 170})
    monkeypatch.setattr(community_api, "forget", lambda d, u: ({}, ["community_posts"]))
    res = c.delete("/me/whole-health/data?confirm=true", headers=H1)
    assert res.status_code == 503 and "community" in res.json()["detail"]
    assert doc_store.get(db, "user-1", "profile", "me") is None                       # the rest was deleted
