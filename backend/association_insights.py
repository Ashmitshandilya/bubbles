"""Personal association insights from logged numeric series. Pure: pass rows in, get findings and wording out.

First consumer of correlation_core: sleep hours / sleep quality vs the same day's mood. Everything is a batch, so the
false-discovery correction sees every comparison. Wording is generated here from the statistics (direction, n), never by
a model, and always states that it is an association in the user's own logs.

Add a relationship: build two {date: value} series, add a spec to `_specs`, add a sentence template in `_SENTENCES`.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import correlation_core as cc

_SENTENCES = {
    ("sleep_hours", "mood"): ("On days after you slept longer, your logged mood tended to be higher", "On days after you slept less, your logged mood tended to be higher"),
    ("sleep_quality", "mood"): ("On days after better-rated sleep, your logged mood tended to be higher", "On days after worse-rated sleep, your logged mood tended to be higher"),
}


def _series(rows: list[dict], key: str) -> dict[date, float | None]:
    out: dict[date, float | None] = {}
    for r in rows:
        try:
            d = date.fromisoformat(str(r.get("date"))[:10])
        except ValueError:
            continue
        v = r.get(key)
        out[d] = float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None
    return out


def _mood(mood_by_day: dict[str, dict]) -> dict[date, float | None]:
    out: dict[date, float | None] = {}
    for d, v in mood_by_day.items():
        try:
            out[date.fromisoformat(d[:10])] = float(v["m"])
        except (ValueError, KeyError, TypeError):
            continue
    return out


def sleep_mood_findings(sleep_rows: list[dict], mood_by_day: dict[str, dict]) -> list[cc.Finding]:
    mood = _mood(mood_by_day)
    specs = [("sleep_hours->mood", cc.paired(_series(sleep_rows, "hours"), mood)),
             ("sleep_quality->mood", cc.paired(_series(sleep_rows, "quality"), mood))]
    return cc.analyze_batch(specs)


def insights(sleep_rows: list[dict], mood_by_day: dict[str, dict]) -> dict[str, Any]:
    """{'insights': [...only reliable ones...], 'findings': [...all, for debugging...], 'message': text when nothing is reliable}"""
    findings = sleep_mood_findings(sleep_rows, mood_by_day)
    shown = []
    for f in findings:
        if f.status not in ("candidate_association", "repeated_pattern"):
            continue
        a, b = f.label.split("->")
        pos, neg = _SENTENCES[(a, b)]
        shown.append({"label": f.label, "status": f.status, "n_days": f.n, "rho": f.rho, "q": f.q,
                      "text": (pos if f.rho > 0 else neg) + f" ({f.n} days logged). " + " ".join(f.limitations)})
    out: dict[str, Any] = {"insights": shown, "findings": [f.to_dict() for f in findings]}
    if not shown:
        out["message"] = "Not enough reliable data to identify a pattern between your sleep and mood yet."
    return out
