"""Documents are signed by the server: rows a browser wrote straight to the database, edited, or copied to another user are ignored."""
import copy

import doc_store
from tests.fake_db import FakeDB


def rows(db):
    return db.tables["health_events"]


def test_forged_unsigned_row_is_ignored():
    db = FakeDB()
    db.table("health_events").insert({"user_id": "u1", "event_type": "bubbles_doc", "title": "transform_plan:current", "data": {
        "kind": "transform_plan", "key": "current", "payload": {"status": "active", "targets": {"kcal": 300, "floor_kcal": 0}}, "version": 1}}).execute()
    assert doc_store.get(db, "u1", "transform_plan", "current") is None
    assert doc_store.list_docs(db, "u1", "transform_plan") == []


def test_tampered_payload_or_version_is_ignored():
    db = FakeDB()
    doc_store.put(db, "u1", "profile", "me", {"height_cm": 170})
    row = rows(db)[0]
    row["data"]["payload"]["height_cm"] = 120
    assert doc_store.get(db, "u1", "profile", "me") is None
    row["data"]["payload"]["height_cm"] = 170
    assert doc_store.get(db, "u1", "profile", "me") == {"height_cm": 170}
    row["data"]["version"] = 9
    assert doc_store.get(db, "u1", "profile", "me") is None


def test_a_row_copied_to_another_user_is_ignored():
    db = FakeDB()
    doc_store.put(db, "u1", "profile", "me", {"height_cm": 170})
    clone = copy.deepcopy(rows(db)[0])
    clone["user_id"], clone["id"] = "u2", "other"
    rows(db).append(clone)
    assert doc_store.get(db, "u2", "profile", "me") is None and doc_store.get(db, "u1", "profile", "me") == {"height_cm": 170}


def test_a_different_signing_key_invalidates_old_rows(monkeypatch):
    db = FakeDB()
    monkeypatch.setenv("BUBBLES_DOC_SIGNING_KEY", "key-one")
    doc_store.put(db, "u1", "profile", "me", {"a": 1})
    assert doc_store.get(db, "u1", "profile", "me") == {"a": 1}
    monkeypatch.setenv("BUBBLES_DOC_SIGNING_KEY", "key-two")
    assert doc_store.get(db, "u1", "profile", "me") is None


def test_strings_are_scrubbed_and_delete_removes_duplicates():
    db = FakeDB()
    doc_store.put(db, "u1", "note", "n", {"text": "a\x00b\ud800c", "nested": [{"x": "y\x00"}]})
    assert doc_store.get(db, "u1", "note", "n") == {"text": "abc", "nested": [{"x": "y"}]}
    rows(db).append(copy.deepcopy(rows(db)[0]) | {"id": "dup"})        # a duplicate from a concurrent write
    assert doc_store.delete(db, "u1", "note", "n") and [r for r in rows(db) if r["title"] == "note:n"] == []
