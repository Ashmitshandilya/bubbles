"""Bubbles checks itself against the person's own days.

From a person's own history Bubbles makes small, testable guesses ("after a short night your mood tends to sit below your usual"), waits for the day
to happen, and scores the guess against what they logged. A link only earns a confident sentence once it has been right often enough for this
person; one that stops holding is doubted and left out. Nothing here is a diagnosis, nothing is sent to a model, and the numbers are the person's own.
Pure: the ledger is a plain dict (stored by prediction_api as a signed document).
"""
from __future__ import annotations

from datetime import date, timedelta
from statistics import mean, median
from typing import Any

Series = dict[date, float | None]
# (x, y, lag_days, what y is called, what a low x is called, what a high x is called). Only series association_loader.load_some can read.
LINKS: list[tuple[str, str, int, str, str, str]] = [
    ("sleep_hours", "mood", 0, "mood", "a short night", "a long night"),
    ("activity_minutes", "sleep_hours", 1, "sleep", "a quiet day", "a busy day"),
    ("hydration_ml", "mood", 0, "mood", "a low-water day", "a high-water day"),
    ("sleep_hours", "activity_minutes", 0, "movement", "a short night", "a long night"),
    ("mood", "sleep_hours", 1, "sleep", "a low day", "a good day"),
    ("mood", "activity_minutes", 1, "movement", "a low day", "a good day"),
    ("screen_hours", "sleep_hours", 1, "sleep", "a light screen day", "a long screen day"),
]
MIN_PAIRS = 14
MIN_GROUP = 5
MIN_SCORED = 6
EARNED = 0.65
DOUBTED = 0.5
KEEP = 120


def key(x: str, y: str) -> str:
    return f"{x}->{y}"


def _mad(values: list[float]) -> float:
    m = median(values)
    return median(abs(v - m) for v in values)


def _pairs(x: Series, y: Series, lag: int, before: date) -> list[tuple[float, float]]:
    out = []
    for d, a in x.items():
        b = y.get(d + timedelta(days=lag))
        if a is not None and b is not None and d + timedelta(days=lag) < before:
            out.append((float(a), float(b)))
    return out


def forecast(x: Series, y: Series, lag: int, today: date) -> dict[str, Any] | None:
    """Today's guess for one link, or None when the history is too thin or the link is not clear for this person."""
    pairs = _pairs(x, y, lag, today + timedelta(days=lag))
    now = x.get(today)
    if now is None or len(pairs) < MIN_PAIRS:
        return None
    xs, ys = [p[0] for p in pairs], [p[1] for p in pairs]
    mx, my = median(xs), median(ys)
    low = [b for a, b in pairs if a < mx]
    high = [b for a, b in pairs if a > mx]
    if len(low) < MIN_GROUP or len(high) < MIN_GROUP:
        return None
    gap = mean(high) - mean(low)
    spread = max(_mad(ys), 1e-9)
    if abs(gap) < 0.5 * spread or now == mx:
        return None
    above = now > mx
    expected = "higher" if (gap > 0) == above else "lower"
    return {"link": [None, None], "made_on": today.isoformat(), "target": (today + timedelta(days=lag)).isoformat(),
            "x_now": float(now), "x_usual": float(mx), "y_usual": float(my), "tie_band": 0.25 * spread, "expected": expected, "scored": None}


def make(series: dict[str, Series], today: date, ledger: dict[str, Any]) -> list[dict[str, Any]]:
    """New guesses for today, one per link, never twice for the same link and day."""
    have = {(e["link"][0], e["link"][1], e["made_on"]) for e in ledger.get("entries", [])}
    out = []
    for x, y, lag, *_ in LINKS:
        if (x, y, today.isoformat()) in have:
            continue
        guess = forecast(series.get(x, {}), series.get(y, {}), lag, today)
        if guess:
            guess["link"] = [x, y]
            out.append(guess)
    return out


def score(ledger: dict[str, Any], series: dict[str, Series], today: date) -> int:
    """Marks every guess whose day has come and whose answer was logged. Returns how many were scored."""
    n = 0
    stats = ledger.setdefault("stats", {})
    for e in ledger.get("entries", []):
        if e.get("scored") is not None:
            continue
        target = date.fromisoformat(e["target"])
        actual = series.get(e["link"][1], {}).get(target)
        if target > today or actual is None:
            continue
        diff = float(actual) - e["y_usual"]
        if abs(diff) <= e["tie_band"]:
            e["scored"] = "tie"
        else:
            e["scored"] = "hit" if (diff > 0) == (e["expected"] == "higher") else "miss"
            s = stats.setdefault(key(*e["link"]), {"hit": 0, "miss": 0})
            s[e["scored"]] += 1
        n += 1
    return n


def trust(ledger: dict[str, Any], x: str, y: str) -> dict[str, Any]:
    s = (ledger.get("stats") or {}).get(key(x, y), {"hit": 0, "miss": 0})
    total = s["hit"] + s["miss"]
    rate = s["hit"] / total if total else 0.0
    status = "learning" if total < MIN_SCORED else "earned" if rate >= EARNED else "doubted" if rate < DOUBTED else "learning"
    return {"status": status, "right": s["hit"], "of": total}


def line(ledger: dict[str, Any], guess: dict[str, Any]) -> str:
    """One plain sentence for a guess, only for a link this person's own days have proven; otherwise an empty string."""
    x, y = guess["link"]
    meta = next((m for m in LINKS if m[0] == x and m[1] == y), None)
    t = trust(ledger, x, y)
    if not meta or t["status"] != "earned":
        return ""
    below = guess["x_now"] < guess["x_usual"]
    lead = meta[4] if below else meta[5]
    return f"In your own history, {lead} is usually followed by {meta[3]} {guess['expected']} than your usual (right {t['right']} of {t['of']} times)."


def checked(ledger: dict[str, Any], today: date, days: int = 3) -> str:
    """The newest guess scored in the last few days, as one honest sentence (a miss is said as plainly as a hit); empty when none."""
    best = None
    for e in ledger.get("entries", []):
        if e.get("scored") in ("hit", "miss") and 0 <= (today - date.fromisoformat(e["target"])).days <= days:
            if best is None or e["target"] > best["target"]:
                best = e
    if not best:
        return ""
    meta = next((m for m in LINKS if m[0] == best["link"][0] and m[1] == best["link"][1]), None)
    if not meta:
        return ""
    lead = meta[4] if best["x_now"] < best["x_usual"] else meta[5]
    verdict = "and it held" if best["scored"] == "hit" else "and it did not hold this time"
    return f"Bubbles guessed your {meta[3]} would run {best['expected']} than usual after {lead}, {verdict}."


def record_lines(ledger: dict[str, Any]) -> list[str]:
    """What this person's own days have proven, as short lines for the model's facts sheet (earned links only, newest record)."""
    out = []
    for x, y, _lag, ylabel, low, _high in LINKS:
        t = trust(ledger, x, y)
        if t["status"] == "earned":
            out.append(f"- Bubbles' own guesses about how {low} affects their {ylabel} have been right {t['right']} of {t['of']} times for this person (a link in their logs, never a cause)")
    return out


def prune(ledger: dict[str, Any]) -> dict[str, Any]:
    ledger["entries"] = ledger.get("entries", [])[-KEEP:]
    return ledger
