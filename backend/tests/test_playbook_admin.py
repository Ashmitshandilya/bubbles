"""WP6.2: the Playbook review routes sit behind the same two-step admin gate (a 404 for everyone else) and work on drafts."""
from __future__ import annotations

import pytest

import playbook as pb
from test_admin_portal import admin_env, bearer  # noqa: F401  (the gate fixtures)
from test_chat_http_flow import env  # noqa: F401


def _db(e):
    return e.main.supabase


@pytest.fixture()
def draft(admin_env):
    db = _db(admin_env)
    pb._cache.clear()
    row = db.table(pb.ENTRIES).insert({"intent": "app.greeting", "language": "english", "guidance_text": "", "example_text": "Hello! I can help you log.",
                                       "status": "draft", "uses": 0, "helpful": 0}).execute().data[0]
    for i in range(3):
        db.table(pb.CANDIDATES).insert({"intent": "app.greeting", "language": "english", "route": "small_talk", "reply_text": "Hello!", "rating": "up",
                                        "outcome": "helpful", "cohort_hash": f"p{i}"}).execute()
    return admin_env, row["id"]


def test_everyone_but_the_admin_gets_a_404(admin_env):
    c, t = admin_env.client, admin_env.tokens
    for headers in ({}, bearer(t.user), bearer(t.aal1)):
        assert c.get("/admin/playbook", headers=headers).status_code == 404
        assert c.post("/admin/playbook/abc12345", json={"action": "approve"}, headers=headers).status_code == 404


def test_the_list_shows_counts_of_people_never_ids(draft):
    e, _ = draft
    body = e.client.get("/admin/playbook", headers=bearer(e.tokens.admin)).json()
    assert body["ready"] is True and body["entries"][0]["people"] == 3 and body["entries"][0]["status"] == "draft"
    assert "p0" not in repr(body) and "cohort" not in repr(body)


def test_approve_edit_and_retire(draft):
    e, entry_id = draft
    h = bearer(e.tokens.admin)
    r = e.client.post(f"/admin/playbook/{entry_id}", json={"action": "approve", "guidance_text": "Greet warmly in one short line."}, headers=h)
    assert r.status_code == 200 and r.json()["status"] == "approved"
    pb._cache.clear()
    assert pb.approved_for(_db(e), "app.greeting", "english")["guidance_text"].startswith("Greet warmly")
    assert e.client.post(f"/admin/playbook/{entry_id}", json={"action": "retire"}, headers=h).json()["status"] == "retired"
    pb._cache.clear()
    assert pb.approved_for(_db(e), "app.greeting", "english") is None


def test_bad_changes_are_refused(draft):
    e, entry_id = draft
    h = bearer(e.tokens.admin)
    assert e.client.post(f"/admin/playbook/{entry_id}", json={"action": "delete"}, headers=h).status_code == 422
    assert e.client.post(f"/admin/playbook/{entry_id}", json={"action": "edit", "guidance_text": "mail me at a@b.com"}, headers=h).status_code == 422
    assert e.client.post("/admin/playbook/00000000-0000-0000-0000-000000000000", json={"action": "approve"}, headers=h).status_code == 404
