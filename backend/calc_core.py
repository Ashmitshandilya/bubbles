"""Calculation provenance layer: one result shape, a formula registry, and honest missing-data handling.

It does NOT re-implement formulas. It wraps the existing engines (nutrition_calc, cycle_engine, hydration_engine)
so every derived number carries: inputs, method, unit, window, data-quality flags, limitations and a formula version.
Rules: missing is never zero; "insufficient_data" and "not_applicable" are normal results, not errors.

Add a calculation: register it in FORMULAS (bump `version` when the maths changes), return a CalcResult, add a known-value
test in tests/test_calc_core.py.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from typing import Any

import clinical_constants as K
import cycle_engine
import hydration_engine
import nutrition_calc
from wellness_common import local_now, request_tz

FORMULAS: dict[str, dict[str, str]] = {
    "bmi": {"version": "1.0", "unit": "kg/m2", "source": "nutrition_calc.bmi_info; WHO + Asian cut-offs from clinical_constants"},
    "mean_logged": {"version": "1.0", "unit": "as input", "source": "arithmetic mean over logged values only"},
    "cycle_length_summary": {"version": "1.0", "unit": "days", "source": "cycle_engine.length_stats, gated by K.CYCLE_MIN_CYCLES_FOR_PREDICTION"},
    "hydration_day_total": {"version": "1.0", "unit": "ml", "source": "hydration_engine.day_totals (tz-aware, drink-type weighted)"},
}
OK, INSUFFICIENT, NOT_APPLICABLE, INVALID = "ok", "insufficient_data", "not_applicable", "invalid_input"


@dataclass
class CalcResult:
    calc_id: str
    status: str                      # ok | insufficient_data | not_applicable | invalid_input
    value: Any = None
    unit: str = ""
    inputs: dict = field(default_factory=dict)
    window: str = ""
    quality: list[str] = field(default_factory=list)       # data-quality flags
    limitations: list[str] = field(default_factory=list)
    reason: str = ""
    version: str = ""

    def __post_init__(self):
        spec = FORMULAS[self.calc_id]  # unregistered calculations cannot be created
        self.version = spec["version"]
        self.unit = self.unit or spec["unit"]
        self.method = spec["source"]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["method"] = self.method
        return d


def local_today(offset_min: int | None = None, now_utc: datetime | None = None) -> date:
    """The user's calendar day (offset None = the client timezone sent with this request, else UTC). `datetime.now(timezone.utc).date()` is wrong for ~5.5 h/day in India (+05:30)."""
    if offset_min is None:
        offset_min = request_tz() or 0
    return local_now(now_utc or datetime.now(timezone.utc), max(-840, min(840, int(offset_min)))).date()


def mean_logged(values: list[Any], unit: str = "", window: str = "") -> CalcResult:
    """Mean over logged numbers only. None / blank / non-numeric are *missing*, never zero."""
    nums, missing = [], 0
    for v in values:
        try:
            if v is None or isinstance(v, bool) or v == "":
                raise ValueError
            nums.append(float(v))
        except (TypeError, ValueError):
            missing += 1
    q = [f"{len(nums)} logged", f"{missing} missing (not counted as zero)"]
    if not nums:
        return CalcResult("mean_logged", INSUFFICIENT, None, unit, {"n_logged": 0, "n_missing": missing}, window, q, reason="no logged values")
    lim = ["Few logged values; treat as a rough average."] if len(nums) < 3 else []
    return CalcResult("mean_logged", OK, round(sum(nums) / len(nums), 2), unit, {"n_logged": len(nums), "n_missing": missing}, window, q, lim)


def calc_bmi(weight_kg: Any, height_cm: Any, age_years: Any = None, pregnant: bool = False) -> CalcResult:
    inp = {"weight_kg": weight_kg, "height_cm": height_cm, "age_years": age_years, "pregnant": pregnant}
    if pregnant:
        return CalcResult("bmi", NOT_APPLICABLE, None, "", inp, reason="adult BMI bands are not suitable in pregnancy")
    try:
        if age_years is not None and float(age_years) < 18:
            return CalcResult("bmi", NOT_APPLICABLE, None, "", inp, reason="adult BMI bands are not suitable under 18 (age/sex-specific growth charts are needed)")
        info = nutrition_calc.bmi_info(float(weight_kg), float(height_cm))
    except (nutrition_calc.CalcError, TypeError, ValueError) as e:
        return CalcResult("bmi", INVALID, None, "", inp, reason=str(e)[:160])
    return CalcResult("bmi", OK, info["bmi"], "", inp, "single measurement", ["inputs within plausible ranges"],
                      [info["note"], "Bands: " + info["who_band"] + " (WHO), " + info["asian_cutoff_band"] + " (Asian cut-offs)"])


def cycle_length_summary(lengths: list[int]) -> CalcResult:
    """Observed cycle lengths (start-to-start, oldest first). Below the minimum number of cycles: abstain."""
    n = len(lengths)
    stats = cycle_engine.length_stats(lengths)
    if n < K.CYCLE_MIN_CYCLES_FOR_PREDICTION:
        return CalcResult("cycle_length_summary", INSUFFICIENT, None, "", {"n_cycles": n, "lengths": lengths}, "",
                          [f"{n} cycle(s) logged"], reason=f"needs at least {K.CYCLE_MIN_CYCLES_FOR_PREDICTION} cycles before any typical range is stated")
    return CalcResult("cycle_length_summary", OK, stats, "", {"n_cycles": n, "lengths": lengths}, f"last {n} cycles",
                      [f"{n} cycles"], ["Observed history, not a forecast; cycle length varies naturally."])


def hydration_day_total(entries: list[dict], day: str, tz_offset_min: int = 0) -> CalcResult:
    """Fluid intake for one local day. No entries => insufficient_data, not 0 ml."""
    inp = {"day": day, "tz_offset_min": tz_offset_min, "n_entries": len(entries)}
    if not entries:
        return CalcResult("hydration_day_total", INSUFFICIENT, None, "", inp, day, ["no entries logged"], reason="nothing logged for this day (not the same as 0 ml)")
    return CalcResult("hydration_day_total", OK, hydration_engine.day_totals(entries, day, tz_offset_min), "", inp, day,
                      ["tz-aware day boundary"], ["Logged intake only; a generic goal is not a personal prescription."])
