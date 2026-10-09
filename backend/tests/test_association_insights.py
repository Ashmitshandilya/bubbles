import random
from datetime import date, timedelta

import association_insights as ai

D0 = date(2026, 8, 1)


def rows(n, f):
    return [{"date": (D0 + timedelta(days=i)).isoformat(), "hours": f(i)[0], "quality": f(i)[1]} for i in range(n)]


def moods(n, f):
    return {(D0 + timedelta(days=i)).isoformat(): {"m": f(i), "n": 1} for i in range(n)}


def test_real_relationship_produces_a_qualified_sentence():
    rng = random.Random(2)
    hrs = [5 + (i * 7) % 5 for i in range(45)]
    out = ai.insights(rows(45, lambda i: (hrs[i], None)), moods(45, lambda i: 3 + hrs[i] * 0.8 + rng.random()))
    assert out["insights"], out["findings"]
    t = out["insights"][0]["text"]
    assert "slept longer" in t and "higher" in t and "does not show that one thing causes" in t and "(45 days logged)" in t


def test_negative_relationship_is_worded_correctly():
    hrs = [5 + (i * 7) % 5 for i in range(45)]
    out = ai.insights(rows(45, lambda i: (hrs[i], None)), moods(45, lambda i: 10 - hrs[i] * 0.8 + (i % 2) * 0.1))
    t = out["insights"][0]["text"]
    assert out["insights"][0]["rho"] < 0 and "slept less" in t and "tended to be higher" in t   # more sleep -> lower mood, so less sleep -> higher


def test_too_little_or_unrelated_data_says_so_and_shows_no_insight():
    few = ai.insights(rows(6, lambda i: (6 + i, None)), moods(6, lambda i: 5 + i))
    assert few["insights"] == [] and "Not enough reliable data" in few["message"]
    rng = random.Random(9)
    noise = ai.insights(rows(40, lambda i: (rng.uniform(4, 9), rng.uniform(1, 5))), moods(40, lambda i: rng.uniform(1, 10)))
    assert noise["insights"] == [] and noise["message"]


def test_missing_values_are_dropped_not_zeroed():
    r = rows(30, lambda i: (None if i % 2 else 6 + i % 4, None))
    m = moods(30, lambda i: 5 + i % 4)
    f = {x.label: x for x in ai.sleep_mood_findings(r, m)}
    assert f["sleep_hours->mood"].n == 15 and f["sleep_quality->mood"].status == "insufficient_data"
