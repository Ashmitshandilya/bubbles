"""Personal association insights from logged numeric series. Pure: pass rows in, get findings and wording out.

First consumer of correlation_core: sleep hours / sleep quality vs the same day's mood. Everything is a batch, so the
false-discovery correction sees every comparison. Wording is generated here from the statistics (direction, n), never by
a model, and always states that it is an association in the user's own logs.

Add a relationship: build two {date: value} series, add a spec to `_specs`, add a sentence template in `_SENTENCES`.
"""
from __future__ import annotations

from datetime import date, timedelta
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


# --- general engine: every curated link between the things a person logs --------------------------------------------------
# (x, y, lag_days, sentence when higher x goes with higher y, sentence when higher x goes with lower y, extra caveat)
# lag 1 means "x on day d against y on day d+1" (sleep is logged the morning after, so it belongs to the next day).
# Keep this list CURATED and short: every pair added is one more comparison the false-discovery correction must pay for.
PAIRS: list[tuple[str, str, int, str, str, str]] = [
    ("sleep_hours", "mood", 0, "On days after you slept longer, your logged mood tended to be higher", "On days after you slept longer, your logged mood tended to be lower", ""),
    ("sleep_quality", "mood", 0, "On days after better-rated sleep, your logged mood tended to be higher", "On days after better-rated sleep, your logged mood tended to be lower", ""),
    ("activity_minutes", "mood", 0, "On days you were active for longer, your logged mood tended to be higher", "On days you were active for longer, your logged mood tended to be lower", "Only days you logged activity are compared."),
    ("activity_minutes", "sleep_quality", 1, "After days you were active for longer, your next sleep rating tended to be better", "After days you were active for longer, your next sleep rating tended to be worse", "Only days you logged activity are compared."),
    ("activity_minutes", "sleep_hours", 1, "After days you were active for longer, you tended to sleep longer", "After days you were active for longer, you tended to sleep less", "Only days you logged activity are compared."),
    ("hydration_ml", "mood", 0, "On days you logged more drinks, your logged mood tended to be higher", "On days you logged more drinks, your logged mood tended to be lower", "Only drinks you logged are counted."),
    ("hydration_ml", "symptom_severity", 0, "On days you logged more drinks, your logged symptoms tended to be more severe", "On days you logged more drinks, your logged symptoms tended to be milder", "Only days you logged a symptom are compared."),
    ("sleep_hours", "symptom_severity", 0, "After longer sleep, your logged symptoms tended to be more severe", "After longer sleep, your logged symptoms tended to be milder", "Only days you logged a symptom are compared."),
    ("mood", "sleep_quality", 1, "On days your mood was higher, your next sleep rating tended to be better", "On days your mood was higher, your next sleep rating tended to be worse", ""),
    ("calories", "sleep_quality", 1, "After days you logged more food, your next sleep rating tended to be better", "After days you logged more food, your next sleep rating tended to be worse", "Only meals you logged are counted, so a day with a missed log looks lighter than it was."),
    ("sleep_hours", "resting_hr", 0, "After longer sleep, your logged heart rate tended to be higher", "After longer sleep, your logged heart rate tended to be lower", "Heart rate depends heavily on when and how it was measured."),
    ("screen_hours", "eye_comfort", 0, "On days you logged more screen time, your logged eye comfort tended to be higher", "On days you logged more screen time, your logged eye comfort tended to be lower", "Screen time is only what you logged in the Eyes tracker."),
    ("screen_hours", "sleep_quality", 1, "After days you logged more screen time, your next sleep rating tended to be better", "After days you logged more screen time, your next sleep rating tended to be worse", "Screen time is only what you logged in the Eyes tracker."),
    ("luteal", "mood", 0, "In the luteal phase of your cycle, your logged mood tended to be higher", "In the luteal phase of your cycle, your logged mood tended to be lower", "Cycle phase is an estimate, not a measurement."),
    ("luteal", "sleep_quality", 0, "In the luteal phase of your cycle, your sleep rating tended to be better", "In the luteal phase of your cycle, your sleep rating tended to be worse", "Cycle phase is an estimate, not a measurement."),
    ("orbit_tension", "sleep_hours", 1, "On days with tension at home, your sleep that night tended to be longer in your logs", "On days with tension at home, your sleep that night was shorter in your logs", "Tension days are the days you used After a fight in Orbit; days without it are counted as calm, which may not always be true."),
    ("orbit_connection", "mood", 1, "After days with a connection moment, your logged mood tended to be higher", "After days with a connection moment, your logged mood tended to be lower", "Connection moments are the days you answered Orbit's daily question or wrote a gratitude note."),
    ("luteal", "orbit_tension", 0, "In the luteal phase of your cycle, tension days were more common in your logs", "In the luteal phase of your cycle, tension days were less common in your logs", "Cycle phase is an estimate, not a measurement. This is shown only to you."),
    ("luteal", "symptom_severity", 0, "In the luteal phase of your cycle, your logged symptoms tended to be more severe", "In the luteal phase of your cycle, your logged symptoms tended to be milder", "Cycle phase is an estimate, not a measurement. Only days you logged a symptom are compared."),
]
TOPIC = {"sleep_hours": "sleep", "sleep_quality": "sleep ratings", "mood": "mood", "activity_minutes": "activity", "hydration_ml": "drinks",
         "symptom_severity": "symptoms", "calories": "meals", "resting_hr": "heart rate", "luteal": "cycle phase",
         "screen_hours": "screen time", "eye_comfort": "eye comfort", "orbit_tension": "tension at home", "orbit_connection": "connection moments"}
_LOG_MORE = "Log {x} and {y} on the same days to check this link (you have {n} of the {need} days needed)."


def _strength(rho: float) -> str:
    a = abs(rho)
    return "weak" if a < 0.4 else "moderate" if a < 0.6 else "strong"


MAX_PAIRS = 12   # newest days returned with a link, so the detail view can show the numbers behind it


def _dated_pairs(sx: dict[date, float | None], sy: dict[date, float | None], lag: int) -> list[dict[str, Any]]:
    """Newest first: the day x was logged (y is on that day plus lag_days) and both values. Same pairing as cc.paired."""
    out = []
    for d in sorted(sx, reverse=True):
        a, b = sx.get(d), sy.get(d + timedelta(days=lag))
        if a is None or b is None:
            continue
        out.append({"date": d.isoformat(), "x": a, "y": b})
        if len(out) == MAX_PAIRS:
            break
    return out


def analyze(series: dict[str, dict[date, float | None]], pairs: list[tuple[str, str, int, str, str, str]] | None = None) -> dict[str, Any]:
    """series: {'sleep_hours': {date: value}, ...}. Returns {'insights': [...reliable only], 'gaps': [...what to log next],
    'data_days': {series: n}, 'message'?: ...}. One false-discovery correction covers every pair, so adding pairs gets stricter."""
    pairs = pairs if pairs is not None else PAIRS
    specs = [(f"{x}->{y}", cc.paired(series.get(x, {}), series.get(y, {}), lag)) for x, y, lag, *_ in pairs]
    findings = cc.analyze_batch(specs)
    shown: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    for (x, y, lag, up, down, caveat), f in zip(pairs, findings):
        if f.status in ("candidate_association", "repeated_pattern"):
            shown.append({"id": f.label, "domains": [x, y], "lag_days": lag, "status": f.status, "strength": _strength(f.rho),
                          "direction": "up" if f.rho > 0 else "down", "n_days": f.n, "rho": f.rho, "p": f.p, "q": f.q,
                          "repeated": f.repeated, "limitations": ([caveat] if caveat else []) + list(f.limitations),
                          "pairs": _dated_pairs(series.get(x, {}), series.get(y, {}), lag),
                          "text": (up if f.rho > 0 else down) + f" ({f.n} days logged). " + " ".join(([caveat] if caveat else []) + f.limitations)})
        elif f.status == "insufficient_data" and f.n >= 1 and series.get(x) and series.get(y):
            gaps.append({"id": f.label, "domains": [x, y], "n_days": f.n, "need": cc.MIN_PAIRS,
                         "text": _LOG_MORE.format(x=TOPIC.get(x, x), y=TOPIC.get(y, y), n=f.n, need=cc.MIN_PAIRS)})
    shown.sort(key=lambda s: (s["status"] != "repeated_pattern", -abs(s["rho"])))
    gaps.sort(key=lambda g: -g["n_days"])
    out: dict[str, Any] = {"insights": shown, "gaps": gaps[:4], "pairs_checked": len(pairs), "version": cc.VERSION,
                           "data_days": {k: sum(1 for v in s.values() if v is not None) for k, s in series.items() if s}}
    if not shown:
        out["message"] = ("Not enough reliable data to find a pattern yet. Logging sleep, mood, activity and drinks on the same days "
                          "unlocks them." if not out["data_days"] else "No reliable pattern between the things you log yet. That is a normal result, not a problem.")
    return out


def chat_lines(result: dict[str, Any], k: int = 3) -> list[str]:
    """Short sentences for the assistant's context. Derived text only, never raw values."""
    return [f"{i['text'].split(' (')[0]} ({i['n_days']} days; an association in their logs, not a cause)" for i in result.get("insights", [])[:k]]
