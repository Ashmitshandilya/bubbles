"""Today's readiness to train, in words and never a score. Pure: pass what was found in, get a level and the reasons out.

Levels: "go" (Go for it), "moderate" (Keep it moderate), "recovery" (Recovery day suggested), or None when nothing recent was logged
(a gap, never "ready"). Every level lists the reasons it came from, so the person can disagree. It is guidance for effort, not a
medical statement; the safety screening in exercise_planner is unchanged and always wins.
"""
from __future__ import annotations

from typing import Any

LABELS = {"go": "Go for it", "moderate": "Keep it moderate", "recovery": "Recovery day suggested"}


def _h(x: float) -> str:
    return f"{x:.1f}".rstrip("0").rstrip(".") + " h"


def assess(*, last_night_hours: float | None = None, usual_hours: float | None = None, yesterday_minutes: float | None = None,
           recent_hard_days: int = 0, soreness: int | None = None, heavy_period: bool = False, stress_high: bool = False) -> dict[str, Any]:
    """``soreness`` is 1 to 5 as the person logged it; ``recent_hard_days`` counts days in the last 3 with 45 minutes or more of training."""
    reasons: list[str] = []
    points = 0
    known = 0

    if last_night_hours is not None:
        known += 1
        gap = (usual_hours - last_night_hours) if usual_hours else None
        if last_night_hours < 5.5 or (gap is not None and gap >= 1.5):
            points -= 2
            reasons.append(f"You slept {_h(last_night_hours)}" + (f", well under your usual {_h(usual_hours)}." if gap and gap >= 1.0 else "."))
        elif last_night_hours < 6.5 or (gap is not None and gap >= 0.75):
            points -= 1
            reasons.append(f"You slept {_h(last_night_hours)}, a little under what suits you." if not usual_hours else f"You slept {_h(last_night_hours)}, a little under your usual {_h(usual_hours)}.")
        else:
            reasons.append(f"Last night's sleep ({_h(last_night_hours)}) was close to your usual or better.")

    if yesterday_minutes is not None:
        known += 1
        if yesterday_minutes >= 90:
            points -= 1
            reasons.append("Yesterday was a big training day.")
    if recent_hard_days >= 3:
        known += 1
        points -= 1
        reasons.append("You have trained hard three days running.")

    if soreness is not None:
        known += 1
        if soreness >= 4:
            points -= 2
            reasons.append("You logged strong soreness.")
        elif soreness == 3:
            points -= 1
            reasons.append("You logged some soreness.")

    if heavy_period:
        known += 1
        points -= 1
        reasons.append("It is a heavy period day, so gentler may feel better.")
    if stress_high:
        known += 1
        points -= 1
        reasons.append("Stress has been high lately.")

    if not known:
        return {"level": None, "label": "Not enough logged to say", "reasons": ["Log your sleep and workouts for a few days and Bubbles can say how ready you look."]}
    level = "recovery" if points <= -3 else "moderate" if points <= -1 else "go"
    return {"level": level, "label": LABELS[level], "reasons": reasons}
