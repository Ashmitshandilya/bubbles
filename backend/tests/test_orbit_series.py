"""WP5.1: Orbit gives the association engine two 0/1 series (tension days, connection days) built from dates only."""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
for p in (str(BACKEND), str(BACKEND / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

import association_insights as ai  # noqa: E402
import association_loader as loader  # noqa: E402
import doc_store  # noqa: E402
from fake_db import FakeDB  # noqa: E402

U = "00000000-0000-0000-0000-00000000000a"
TODAY = date(2026, 10, 24)


def _db(monkeypatch):
    monkeypatch.setenv("BUBBLES_DOC_SIGNING_KEY", "orbit-series-key")
    return FakeDB({"ta": U})


def test_no_orbit_use_means_no_series(monkeypatch):
    assert loader._orbit_series(_db(monkeypatch), U, TODAY, 90) == {}


def test_series_cover_days_since_first_use_and_missing_before(monkeypatch):
    db = _db(monkeypatch)
    for back in (6, 4):
        doc_store.put(db, U, "orbit_question", (TODAY - timedelta(days=back)).isoformat(), {"my_answer": "x"})
    doc_store.put(db, U, "orbit_tension", (TODAY - timedelta(days=3)).isoformat(), {"marked": True})
    out = loader._orbit_series(db, U, TODAY, 90)
    tension, connection = out["orbit_tension"], out["orbit_connection"]
    assert min(tension) == TODAY - timedelta(days=6)           # nothing before the first Orbit day
    assert len(tension) == 7
    assert tension[TODAY - timedelta(days=3)] == 1.0 and tension[TODAY] == 0.0
    assert connection[TODAY - timedelta(days=4)] == 1.0 and connection[TODAY - timedelta(days=5)] == 0.0


def test_the_series_never_hold_words(monkeypatch):
    db = _db(monkeypatch)
    doc_store.put(db, U, "orbit_question", TODAY.isoformat(), {"my_answer": "a private sentence"})
    assert "private" not in repr(loader._orbit_series(db, U, TODAY, 90))


def test_new_links_are_curated_and_labelled():
    ids = {(x, y) for x, y, *_ in ai.PAIRS}
    assert {("orbit_tension", "sleep_hours"), ("orbit_connection", "mood"), ("luteal", "orbit_tension")} <= ids
    assert all(k in ai.TOPIC for k in ("orbit_tension", "orbit_connection"))


def test_partner_sharing_never_reads_tension():
    text = (BACKEND / "partner_sharing.py").read_text(encoding="utf8") + (BACKEND / "orbit_weather.py").read_text(encoding="utf8")
    assert "orbit_tension" not in text and "association" not in text
