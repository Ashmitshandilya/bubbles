"""A value or name changed in one place is what every other place shows next (profile, setup, chat, trackers)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("SUPABASE_URL", "http://localhost:54321")
os.environ.setdefault("SUPABASE_SECRET_KEY", "test-key")
BACKEND = Path(__file__).resolve().parents[1]
for p in (str(BACKEND), str(BACKEND / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import doc_store  # noqa: E402
import main  # noqa: E402
from body_stats import auto_save_body_stats  # noqa: E402
from fake_db import FakeDB  # noqa: E402

USER = "00000000-0000-0000-0000-0000000000a1"
H = {"Authorization": "Bearer tok"}


@pytest.fixture()
def client(monkeypatch):
    import consent
    monkeypatch.setattr(consent, "is_granted", lambda db, uid, purpose: purpose == "health_memory_from_chat")
    db = FakeDB({"tok": USER})
    db.table("profiles").insert({"id": USER, "display_name": "Old name", "height_cm": None}).execute()
    monkeypatch.setattr(main, "supabase", db)
    return TestClient(main.app), db


def _profile(c):
    return c.get("/profile", headers=H).json()["profile"]


def test_the_name_told_in_setup_is_the_name_every_page_shows(client):
    c, db = client
    assert _profile(c)["display_name"] == "Old name"
    doc_store.put(db, USER, "experience", "main", {"name": "Ashmit"})            # what Settings shows
    assert _profile(c)["display_name"] == "Ashmit"
    assert db.rows("profiles", id=USER)[-1]["display_name"] == "Ashmit"          # the row other readers use caught up too (the fake inserts where the real upsert updates)
    assert _profile(c)["display_name"] == "Ashmit"                               # and it stays


def test_a_height_told_in_chat_shows_on_the_profile_page(client):
    c, db = client
    assert _profile(c).get("height_cm") is None
    notes = auto_save_body_stats(db, USER, "my height is 6'1", [])
    assert notes and "185.4 cm" in notes[0]
    assert _profile(c)["height_cm"] == 185.4
    auto_save_body_stats(db, USER, "actually I am 180 cm tall", [])             # a newer statement replaces it
    assert _profile(c)["height_cm"] == 180.0


def test_a_blank_or_missing_setup_name_never_blanks_the_profile(client):
    c, db = client
    doc_store.put(db, USER, "experience", "main", {"name": "  "})
    assert _profile(c)["display_name"] == "Old name"


def test_one_name_wins_everywhere():
    resolve_display_name = main.resolve_display_name
    assert resolve_display_name("Ashmit", "Old", "Signup") == "Ashmit"      # what the person last told Bubbles
    assert resolve_display_name(None, "  Old ", "Signup") == "Old"
    assert resolve_display_name("", None, "Signup") == "Signup"
    assert resolve_display_name(None, None, None) is None
    assert len(resolve_display_name("x" * 90, None, None)) == 40


def test_the_app_starts_up():
    """The startup hooks must run (a stray local import once made the first one raise UnboundLocalError and the server refuse to boot)."""
    with TestClient(main.app) as c:
        assert c.get("/health").status_code == 200
