import random
import threading
from datetime import date, timedelta

import association_insights as ai
import association_loader as al

D0 = date(2026, 7, 1)


def day(i):
    return D0 + timedelta(days=i)


def test_lagged_link_is_found_with_the_right_direction_and_wording():
    rng = random.Random(4)
    act = {day(i): float(10 + (i * 7) % 50) for i in range(60)}
    sleep_q = {day(i + 1): 1 + act[day(i)] / 14 + rng.random() * 0.3 for i in range(60)}   # next day's sleep rating follows activity
    out = ai.analyze({"activity_minutes": act, "sleep_quality": sleep_q})
    hit = next(i for i in out["insights"] if i["id"] == "activity_minutes->sleep_quality")
    assert hit["lag_days"] == 1 and hit["direction"] == "up" and "next sleep rating tended to be better" in hit["text"]
    assert "does not show that one thing causes" in hit["text"] and hit["n_days"] >= 55


def test_unrelated_logs_give_no_insight_across_all_pairs():
    rng = random.Random(11)
    names = ["sleep_hours", "sleep_quality", "mood", "activity_minutes", "hydration_ml", "calories", "symptom_severity", "resting_hr", "luteal"]
    series = {n: {day(i): rng.uniform(1, 10) for i in range(60)} for n in names}
    out = ai.analyze(series)
    assert out["insights"] == [] and out["message"] and out["pairs_checked"] == len(ai.PAIRS)


def test_too_little_data_says_what_to_log_and_never_zero_fills():
    out = ai.analyze({"sleep_hours": {day(i): 7.0 + i % 3 for i in range(6)}, "mood": {day(i): 5.0 + i % 4 for i in range(6)}})
    assert out["insights"] == []
    gap = next(g for g in out["gaps"] if g["id"] == "sleep_hours->mood")
    assert gap["n_days"] == 6 and "6 of the 10 days needed" in gap["text"]
    # a missing day stays missing: 20 mood days against 10 sleep days pairs on only the 10
    sleep = {day(i): float(5 + i % 5) for i in range(0, 20, 2)}
    mood = {day(i): float(3 + i % 6) for i in range(20)}
    f = next(f for f in ai.cc.analyze_batch([("x", ai.cc.paired(sleep, mood))]))
    assert f.n == 10


def test_empty_input_is_safe():
    out = ai.analyze({})
    assert out["insights"] == [] and out["gaps"] == [] and "Log" in out["message"]


def test_chat_lines_carry_no_raw_values_and_say_association():
    rng = random.Random(1)
    hrs = {day(i): float(5 + (i * 7) % 5) for i in range(50)}
    mood = {day(i): 3 + hrs[day(i)] * 0.8 + rng.random() for i in range(50)}
    lines = ai.chat_lines(ai.analyze({"sleep_hours": hrs, "mood": mood}))
    assert lines and all("not a cause" in ln and "association" in ln for ln in lines)


def test_loader_aggregates_by_day_and_skips_unreadable_domains(monkeypatch):
    def fake_list_domain(db, slug, domain, uid, days):
        if slug == "symptoms":
            raise RuntimeError("table unreadable")
        rows = {"hydration": [{"date": "2026-07-02T08:00:00+00:00", "volume": 500}, {"date": "2026-07-02T15:00:00+00:00", "volume": 750},
                              {"date": "2026-07-03T09:00:00+00:00", "volume": "oops"}],
                "vitals": [{"date": "2026-07-02T08:00:00+00:00", "heart_rate": 60}, {"date": "2026-07-02T20:00:00+00:00", "heart_rate": 70}]}
        return {"entries": rows.get(slug, [])}
    monkeypatch.setattr(al, "list_domain", fake_list_domain)
    monkeypatch.setattr(al.S, "load_entries", lambda *a: (_ for _ in ()).throw(RuntimeError("no sleep table")))
    monkeypatch.setattr(al.S, "load_details", lambda *a: {"2026-07-02": {"cycle_phase": "luteal"}, "2026-07-03": {"cycle_phase": "follicular"}})
    monkeypatch.setattr(al.Mind, "load_mood_entries", lambda *a: [])
    s = al.load_series(None, "u1", 30, 0)
    assert s["hydration_ml"] == {date(2026, 7, 2): 1250.0}            # sum per day; the non-numeric entry is ignored, not zeroed
    assert s["resting_hr"] == {date(2026, 7, 2): 65.0}
    assert s["luteal"] == {date(2026, 7, 2): 1.0, date(2026, 7, 3): 0.0}
    assert "symptom_severity" not in s and "sleep_hours" not in s and "mood" not in s


def test_chat_block_never_blocks_and_warms_the_cache(monkeypatch):
    al._cache.clear(); al._running.clear()
    started = threading.Event()
    monkeypatch.setattr(al, "compute", lambda db, uid, days, tz: (started.set(), {"insights": [], "gaps": []})[1])
    assert al.chat_block(None, "u-cold") == ""          # cold: returns at once, computes in the background
    assert started.wait(2)
    for _ in range(100):
        if "u-cold" not in al._running:
            break
        threading.Event().wait(0.02)
    result = {"insights": [{"text": "On days after you slept longer, your logged mood tended to be higher (40 days logged). x", "n_days": 40}], "gaps": []}
    al._cache["u-warm"] = (al.time.monotonic(), result)
    block = al.chat_block(None, "u-warm")
    assert "PATTERNS IN THEIR OWN LOGS" in block and "slept longer" in block and "not a cause" in block and "40 days" in block
    al._cache["u-old"] = (al.time.monotonic() - al.TTL_SECONDS - 1, result)
    assert al.cached("u-old") is None
