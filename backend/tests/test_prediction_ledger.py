from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import prediction_ledger as pl  # noqa: E402
from test_chat_http_flow import env  # noqa: E402,F401

TODAY = date(2026, 10, 25)


def _history(days=30):
    """Sleep alternates 5 and 8 hours; mood is 3 after short sleep and 7 after long."""
    sleep, mood = {}, {}
    for i in range(days, 0, -1):
        d = TODAY - timedelta(days=i)
        short = i % 2 == 0
        sleep[d] = 5.0 if short else 8.0
        mood[d] = 3.0 if short else 7.0
    return sleep, mood


def test_a_clear_link_gives_a_guess_and_thin_history_gives_none():
    sleep, mood = _history()
    sleep[TODAY] = 4.5
    g = pl.forecast(sleep, mood, 0, TODAY)
    assert g and g["expected"] == "lower" and g["target"] == TODAY.isoformat()
    short, short_m = _history(8)
    short[TODAY] = 4.5
    assert pl.forecast(short, short_m, 0, TODAY) is None


def test_scoring_counts_hits_and_waits_for_the_answer_to_be_logged():
    sleep, mood = _history()
    sleep[TODAY] = 4.5
    ledger = {"entries": pl.make({"sleep_hours": sleep, "mood": mood}, TODAY, {})}
    assert len(ledger["entries"]) == 1
    assert pl.make({"sleep_hours": sleep, "mood": mood}, TODAY, ledger) == []   # not twice for the same day
    assert pl.score(ledger, {"mood": mood}, TODAY) == 0                       # today's mood is not logged yet
    mood[TODAY] = 2.0
    assert pl.score(ledger, {"mood": mood}, TODAY) == 1
    assert ledger["stats"]["sleep_hours->mood"] == {"hit": 1, "miss": 0}


def test_a_day_at_the_usual_is_a_tie_and_is_not_counted():
    sleep, mood = _history()
    sleep[TODAY] = 4.5
    ledger = {"entries": pl.make({"sleep_hours": sleep, "mood": mood}, TODAY, {})}
    mood[TODAY] = ledger["entries"][0]["y_usual"]
    assert pl.score(ledger, {"mood": mood}, TODAY) == 1
    assert ledger["entries"][0]["scored"] == "tie" and ledger["stats"] == {}


def test_a_link_is_earned_only_after_enough_right_guesses_and_doubted_when_it_fails():
    good = {"stats": {"sleep_hours->mood": {"hit": 8, "miss": 2}}}
    bad = {"stats": {"sleep_hours->mood": {"hit": 2, "miss": 6}}}
    few = {"stats": {"sleep_hours->mood": {"hit": 3, "miss": 0}}}
    assert pl.trust(good, "sleep_hours", "mood")["status"] == "earned"
    assert pl.trust(bad, "sleep_hours", "mood")["status"] == "doubted"
    assert pl.trust(few, "sleep_hours", "mood")["status"] == "learning"


def test_only_an_earned_link_gets_a_sentence_and_it_quotes_the_record():
    guess = {"link": ["sleep_hours", "mood"], "x_now": 4.5, "x_usual": 6.5, "expected": "lower"}
    assert pl.line({"stats": {"sleep_hours->mood": {"hit": 3, "miss": 0}}}, guess) == ""
    text = pl.line({"stats": {"sleep_hours->mood": {"hit": 8, "miss": 2}}}, guess)
    assert "a short night" in text and "lower than your usual" in text and "right 8 of 10" in text


def test_the_route_scores_yesterdays_guess_and_stores_only_numbers(env, monkeypatch):
    import association_loader
    import doc_store
    import prediction_api as api
    from test_chat_http_flow import USER

    sleep, mood = _history()
    sleep[TODAY] = 4.5
    monkeypatch.setattr(association_loader, "load_some", lambda db, uid, names, **k: ({"sleep_hours": sleep, "mood": mood, "activity_minutes": {}}, TODAY))
    first = api.run(env.db, USER)
    assert first["status"] == "success" and first["scored_now"] == 0 and first["today"] == []     # a new guess is never spoken before it is earned
    mood[TODAY] = 2.0
    second = api.run(env.db, USER)
    assert second["scored_now"] == 1
    stored = doc_store.get(env.db, USER, "prediction_ledger", "main")
    assert stored["stats"]["sleep_hours->mood"] == {"hit": 1, "miss": 0}
    assert not any(isinstance(v, str) and len(v) > 30 for e in stored["entries"] for v in e.values() if not isinstance(v, list))


def test_the_facts_sheet_gets_only_earned_links():
    ledger = {"stats": {"sleep_hours->mood": {"hit": 8, "miss": 2}, "hydration_ml->mood": {"hit": 1, "miss": 5}}}
    lines = pl.record_lines(ledger)
    assert len(lines) == 1 and "right 8 of 10" in lines[0] and "never a cause" in lines[0]


def test_the_newest_checked_guess_is_said_plainly_hit_or_miss_and_old_ones_are_not():
    base = {"link": ["sleep_hours", "mood"], "x_now": 4.0, "x_usual": 7.0, "y_usual": 3.0, "tie_band": 0.1, "expected": "lower"}
    miss = {**base, "made_on": "2026-10-23", "target": "2026-10-24", "scored": "miss"}
    old = {**base, "made_on": "2026-10-01", "target": "2026-10-02", "scored": "hit"}
    assert "did not hold" in pl.checked({"entries": [old, miss]}, TODAY)
    assert "it held" in pl.checked({"entries": [{**miss, "scored": "hit"}]}, TODAY)
    assert pl.checked({"entries": [old]}, TODAY) == ""


def test_every_link_reads_series_the_loader_can_serve_and_has_distinct_wording():
    import inspect, association_loader
    src = inspect.getsource(association_loader.load_some)
    for x, y, lag, ylabel, low, high in pl.LINKS:
        assert f'"{x}"' in src and f'"{y}"' in src and lag in (0, 1) and low != high and ylabel
    assert len({(x, y) for x, y, *_ in pl.LINKS}) == len(pl.LINKS)
