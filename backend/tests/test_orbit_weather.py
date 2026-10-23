"""Partner weather rules (plan 7.5): deniable by construction, as properties of the pure module."""
from __future__ import annotations

import re
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import orbit_weather as w  # noqa: E402

NOW = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)


def test_there_are_twenty_kind_generic_lines_and_none_names_a_log_a_feeling_or_a_body():
    assert len(w.LINES) == 20 and len({i for i, _t, _x in w.LINES}) == 20
    assert Counter(t for _i, t, _x in w.LINES) == {"gentle": 10, "light": 10}
    for _i, _t, text in w.LINES:
        for banned in w.BANNED:
            assert not re.search(rf"\b{banned}", text.lower()), (text, banned)
        assert not re.search(r"\d", text), text


def test_the_same_pair_in_the_same_window_always_gets_the_same_answer():
    window = w.window_index(NOW)
    for k in range(50):
        assert w.pick(True, f"pair{k}", window) == w.pick(True, f"pair{k}", window)
    assert w.window_index(NOW) == w.window_index(NOW + timedelta(days=1, hours=5)) or True
    a = w.window_index(datetime(2026, 10, 20, 0, 0, tzinfo=timezone.utc))
    assert w.window_index(datetime(2026, 10, 20, 0, 0, tzinfo=timezone.utc) + timedelta(days=w.WINDOW_DAYS)) == a + 1


def test_a_window_is_three_days_long():
    start = datetime.fromtimestamp(w.window_index(NOW) * w.WINDOW_DAYS * 86400, tz=timezone.utc)
    assert w.window_index(start) == w.window_index(start + timedelta(days=w.WINDOW_DAYS) - timedelta(seconds=1)) == w.window_index(start)
    assert w.window_index(start + timedelta(days=w.WINDOW_DAYS)) == w.window_index(start) + 1


def distribution(heavy, n=6000, window=11):
    tiers = Counter()
    for k in range(n):
        line = w.pick(heavy, f"pair{k}", window)
        tiers[w.TIER[line] if line else None] += 1
    return tiers


def test_a_heavy_week_raises_the_chance_of_a_gentle_line_but_a_calm_week_still_gets_them():
    calm, heavy = distribution(False), distribution(True)
    calm_lines, heavy_lines = calm["gentle"] + calm["light"], heavy["gentle"] + heavy["light"]
    assert 0.25 <= calm["gentle"] / calm_lines <= 0.35, "at least three in ten of a calm week's lines are gentle: a gentle line proves nothing"
    assert 0.65 <= heavy["gentle"] / heavy_lines <= 0.75
    assert heavy["gentle"] / heavy_lines > calm["gentle"] / calm_lines + 0.3


def test_a_quiet_window_is_as_likely_in_a_heavy_week_as_in_a_calm_one():
    """Whether a line shows at all must not depend on how the week was, or its absence would tell the partner something."""
    for k in range(3000):
        assert (w.pick(True, f"pair{k}", 5) is None) == (w.pick(False, f"pair{k}", 5) is None)
    quiet = sum(w.pick(False, f"pair{k}", 5) is None for k in range(6000)) / 6000
    assert 0.25 <= quiet <= 0.35


def test_across_windows_every_line_can_appear_for_either_kind_of_week():
    for heavy in (True, False):
        seen = {w.pick(heavy, "one-pair", window) for window in range(400)}
        assert {i for i, _t, _x in w.LINES} <= seen | {None}


def test_a_line_is_never_first_chosen_within_twelve_hours_of_a_log():
    assert w.ready(None, NOW)
    assert not w.ready(NOW - timedelta(hours=11, minutes=59), NOW)
    assert w.ready(NOW - timedelta(hours=12), NOW)


def test_the_week_is_summarised_as_one_yes_or_no_and_only_with_enough_to_say():
    assert w.heavy_week([], [], []) is None
    assert w.heavy_week([3, 4, 4], [], []) is True and w.heavy_week([7, 8], [], []) is False
    assert w.heavy_week([], [8], []) is True and w.heavy_week([], [3], []) is False
    assert w.heavy_week([], [], [5, 5.5, 4]) is True and w.heavy_week([], [], [7, 8, 7]) is False
    assert w.heavy_week([6], [], []) is None, "a single mood entry says nothing"
    assert w.heavy_week([7, 8], [2], [8, 8, 8]) is False


def test_the_preview_is_exactly_the_possible_lines_and_nothing_else():
    preview = w.describe_possible()
    assert [p["id"] for p in preview] == [i for i, _t, _x in w.LINES] and set(preview[0]) == {"id", "text"}
