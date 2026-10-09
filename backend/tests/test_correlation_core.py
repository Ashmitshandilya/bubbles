"""Known-answer and honesty tests for correlation_core."""
import random
from datetime import date, timedelta

import correlation_core as cc

D0 = date(2026, 9, 1)


def test_spearman_known_values():
    assert cc.spearman([1, 2, 3, 4, 5], [10, 20, 30, 40, 50]) == 1.0
    assert cc.spearman([1, 2, 3, 4, 5], [5, 4, 3, 2, 1]) == -1.0
    assert cc.spearman([1, 1, 1, 1], [1, 2, 3, 4]) is None                  # no variation
    assert abs(cc.spearman([1, 2, 2, 4], [1, 3, 2, 4]) - 0.9487) < 1e-3     # ties use average ranks


def test_benjamini_hochberg_known_example():
    q = cc.benjamini_hochberg([0.01, 0.04, 0.03, 0.005])
    assert [round(v, 4) for v in q] == [0.02, 0.04, 0.04, 0.02]


def test_missing_is_not_zero_and_lag_alignment():
    sx = {D0 + timedelta(days=i): (None if i == 2 else float(i)) for i in range(5)}
    sy = {D0 + timedelta(days=i): float(i) for i in range(6)}
    assert len(cc.paired(sx, sy)) == 4                                        # the unlogged day is dropped, not zero
    assert cc.paired(sx, sy, lag_days=1)[0] == (0.0, 1.0)                     # x today vs y tomorrow


def test_dedupe_collapses_one_episode_logged_on_consecutive_days():
    days = [D0, D0 + timedelta(days=1), D0 + timedelta(days=2), D0 + timedelta(days=20)]
    assert cc.dedupe_events(days) == [D0, D0 + timedelta(days=20)]


def test_abstains_with_too_few_pairs_and_flat_series():
    f = cc.assess_pairs("short", [(i, i) for i in range(5)])
    assert f.status == "insufficient_data" and "needs at least" in f.reason
    assert cc.assess_pairs("flat", [(1.0, float(i)) for i in range(20)]).status == "insufficient_data"


def test_real_monotonic_relationship_is_a_repeated_pattern_without_causal_claims():
    rng = random.Random(1)
    pairs = [(float(i % 12), float(i % 12) + rng.random()) for i in range(40)]
    f = cc.analyze_batch([("sleep->energy", pairs)])[0]
    assert f.status == "repeated_pattern" and f.rho > 0.9 and f.q <= cc.Q_MAX and f.repeated
    assert any("does not show that one thing causes" in s for s in f.limitations)


def test_noise_is_not_promoted_even_when_many_pairs_are_examined():
    rng = random.Random(7)
    specs = [(f"noise{i}", [(rng.random(), rng.random()) for _ in range(30)]) for i in range(40)]
    out = cc.analyze_batch(specs)
    assert sum(f.status in ("candidate_association", "repeated_pattern") for f in out) <= 1   # ~0 expected; BH controls false discoveries


def test_deterministic():
    pairs = [(float(i), float((i * 7) % 11)) for i in range(25)]
    assert cc.assess_pairs("a", pairs).to_dict() == cc.assess_pairs("a", pairs).to_dict()


def test_pattern_in_only_one_half_is_candidate_not_repeated():
    rng = random.Random(3)
    first = [(float(i), float(i) + rng.random()) for i in range(15)]
    second = [(float(i), rng.random() * 15) for i in range(15)]
    f = cc.analyze_batch([("x", first + second)])[0]
    assert f.status in ("candidate_association", "no_pattern") and f.status != "repeated_pattern"
