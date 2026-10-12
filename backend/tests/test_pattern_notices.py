"""Saved pattern notices: new / stronger / reversed / faded / returned, dismissals respected, stored per user."""
from datetime import date, timedelta

import association_insights as ai
import doc_store
import pattern_notices as pn
from tests.fake_db import FakeDB

D = date(2026, 10, 1)


def _insight(lid="sleep_hours->mood", status="candidate_association", direction="up", n=20):
    return {"id": lid, "domains": lid.split("->"), "lag_days": 0, "status": status, "strength": "moderate", "direction": direction,
            "n_days": n, "rho": 0.5 if direction == "up" else -0.5, "q": 0.01, "text": f"{lid} {direction} ({n} days logged)."}


def _res(*items):
    return {"insights": list(items)}


def test_lifecycle_new_then_quiet_then_stronger_then_reversed():
    notes, ev = pn.reconcile({}, _res(_insight()), D)
    assert [e["kind"] for e in ev] == ["new"] and notes["sleep_hours->mood"]["first_seen"] == D.isoformat()
    prev = notes
    notes, ev = pn.reconcile(prev, _res(_insight(n=22)), D + timedelta(days=1))
    assert ev == [] and notes["sleep_hours->mood"]["n_days"] == 22          # same pattern, just more data: no new event
    prev = {**prev, **notes}
    notes, ev = pn.reconcile(prev, _res(_insight(status="repeated_pattern", n=30)), D + timedelta(days=2))
    assert [e["kind"] for e in ev] == ["stronger"]
    prev = {**prev, **notes}
    notes, ev = pn.reconcile(prev, _res(_insight(status="repeated_pattern", direction="down", n=40)), D + timedelta(days=3))
    assert [e["kind"] for e in ev] == ["reversed"] and notes["sleep_hours->mood"]["first_seen"] == D.isoformat()


def test_fades_only_after_a_quiet_spell_then_can_return():
    prev, _ = pn.reconcile({}, _res(_insight()), D)
    notes, ev = pn.reconcile(prev, _res(), D + timedelta(days=pn.FADE_DAYS - 1))
    assert ev == [] and notes == {}                                          # dipping below the threshold briefly is not news
    notes, ev = pn.reconcile(prev, _res(), D + timedelta(days=pn.FADE_DAYS + 1))
    assert [e["kind"] for e in ev] == ["faded"] and notes["sleep_hours->mood"]["state"] == "faded"
    prev = {**prev, **notes}
    notes, ev = pn.reconcile(prev, _res(_insight()), D + timedelta(days=30))
    assert [e["kind"] for e in ev] == ["returned"] and notes["sleep_hours->mood"]["state"] == "active"


def test_dismissed_notice_stays_tracked_but_silent():
    prev, _ = pn.reconcile({}, _res(_insight()), D)
    prev["sleep_hours->mood"]["dismissed"] = True
    notes, ev = pn.reconcile(prev, _res(_insight(status="repeated_pattern")), D + timedelta(days=1))
    assert ev == [] and notes["sleep_hours->mood"]["status"] == "repeated_pattern" and notes["sleep_hours->mood"]["dismissed"]


def test_save_active_dismiss_round_trip_is_owner_scoped():
    db = FakeDB()
    ev = pn.save(db, "u1", _res(_insight(), _insight("activity_minutes->mood", status="repeated_pattern")), D)
    assert sorted(e["kind"] for e in ev) == ["new", "new"]
    assert [n["id"] for n in pn.active(db, "u1")] == ["activity_minutes->mood", "sleep_hours->mood"]   # repeated first
    assert pn.active(db, "u2") == []
    assert pn.save(db, "u1", _res(_insight(), _insight("activity_minutes->mood", status="repeated_pattern")), D) == []
    assert pn.dismiss(db, "u1", "sleep_hours->mood") and not pn.dismiss(db, "u1", "nope")
    assert [n["id"] for n in pn.active(db, "u1")] == ["activity_minutes->mood"]
    assert doc_store.delete_everything(db, "u1") >= 2 and pn.active(db, "u1") == []   # "delete all my data" removes them


def test_save_never_raises():
    class Broken:
        def table(self, *_a):
            raise RuntimeError("db down")
    assert pn.save(Broken(), "u1", _res(_insight()), D) == []


def test_real_engine_output_is_storable_and_carries_no_raw_values():
    hrs = {D + timedelta(days=i): 5 + (i * 7) % 5 for i in range(45)}
    mood = {d: 3 + h * 0.8 + (i % 3) * 0.1 for i, (d, h) in enumerate(hrs.items())}
    result = ai.analyze({"sleep_hours": hrs, "mood": mood})
    assert result["insights"]
    notes, ev = pn.reconcile({}, result, D)
    note = notes[result["insights"][0]["id"]]
    assert ev[0]["kind"] == "new" and "does not show that one thing causes" in note["text"]
    assert set(note) <= set(pn._KEEP) | {"id", "first_seen", "last_seen", "state", "dismissed", "change", "changed_on"}


def test_cycle_phase_symptom_link_is_checked():
    assert ("luteal", "symptom_severity") in {(x, y) for x, y, *_ in ai.PAIRS}
