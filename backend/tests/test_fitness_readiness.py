import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fitness_readiness as fr  # noqa: E402


def test_nothing_logged_is_a_gap_not_ready():
    out = fr.assess()
    assert out["level"] is None and "Not enough" in out["label"] and out["reasons"]


def test_well_slept_is_go_and_says_why():
    out = fr.assess(last_night_hours=7.5, usual_hours=7.2)
    assert out["level"] == "go" and out["label"] == "Go for it" and "close to your usual" in out["reasons"][0]


def test_short_sleep_after_hard_day_is_moderate_or_recovery():
    assert fr.assess(last_night_hours=5, usual_hours=7.5)["level"] == "moderate"
    out = fr.assess(last_night_hours=5, usual_hours=7.5, yesterday_minutes=100, soreness=4)
    assert out["level"] == "recovery" and len(out["reasons"]) == 3


def test_reasons_are_always_listed_and_no_score_leaks():
    out = fr.assess(last_night_hours=6, usual_hours=7, heavy_period=True)
    assert out["reasons"] and set(out) == {"level", "label", "reasons"}


def test_recent_hard_days_and_stress_count():
    assert fr.assess(last_night_hours=7.5, usual_hours=7.5, recent_hard_days=3, stress_high=True)["level"] == "moderate"
