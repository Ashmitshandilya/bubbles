"""Reads that used to run one after another now run side by side or in one trip, with the same answers."""
import contextvars
import threading
import time

import pytest

import doc_store
from parallel import together
from tests.fake_db import FakeDB


def test_together_keeps_order_and_overlaps_the_waiting():
    started = time.perf_counter()
    out = together(*[(lambda i=i: (time.sleep(0.2), i)[1]) for i in range(5)])
    assert out == [0, 1, 2, 3, 4]
    assert time.perf_counter() - started < 0.7   # five 0.2 s reads one after another would take 1.0 s


def test_together_raises_the_first_error_like_a_plain_call():
    def boom():
        raise ValueError("no")
    with pytest.raises(ValueError):
        together(lambda: 1, boom)


def test_together_carries_the_callers_context_into_each_job():
    var: contextvars.ContextVar[str] = contextvars.ContextVar("tz", default="none")
    var.set("Asia/Kolkata")
    seen = together(lambda: var.get(), lambda: var.get())
    assert seen == ["Asia/Kolkata", "Asia/Kolkata"]
    assert threading.current_thread() is threading.main_thread()


def test_get_pairs_reads_documents_of_different_kinds_in_one_trip_and_matches_get():
    db = FakeDB()
    doc_store.put(db, "u1", "profile", "me", {"height_cm": 170})
    doc_store.put(db, "u1", "cycle_settings", "main", {"mode": "pregnancy"})
    doc_store.put(db, "u2", "profile", "me", {"height_cm": 99})   # another person's document is never returned
    trips = []
    original = db.table

    def counting(name):
        query = original(name)
        run = query.execute
        query.execute = lambda: (trips.append(name), run())[1]
        return query
    db.table = counting
    pairs = [("profile", "me"), ("eating_screen", "current"), ("cycle_settings", "main")]
    got = doc_store.get_pairs(db, "u1", pairs)
    assert len(trips) == 1
    assert got == {("profile", "me"): {"height_cm": 170}, ("cycle_settings", "main"): {"mode": "pregnancy"}}
    for kind, key in pairs:   # same answer as asking one by one (a missing document is simply absent)
        assert got.get((kind, key)) == doc_store.get(db, "u1", kind, key)


def test_get_pairs_ignores_unsigned_rows_and_an_empty_list_reads_nothing():
    db = FakeDB()
    db.table("health_events").insert({"user_id": "u1", "event_type": "bubbles_doc", "title": "profile:me", "data": {
        "kind": "profile", "key": "me", "payload": {"height_cm": 1}, "version": 1}}).execute()
    assert doc_store.get_pairs(db, "u1", [("profile", "me")]) == {}
    assert doc_store.get_pairs(object(), "u1", []) == {}
