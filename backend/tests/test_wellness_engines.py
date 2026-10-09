"""Pure-function tests for sleep, hydration, medication and mind engines (no database)."""
from __future__ import annotations

import pathlib
import random
import re
from datetime import date, datetime, timedelta, timezone

import pytest

import clinical_constants as K
import hydration_engine as H
import med_schedule as M
import mind_checkins as Mind
import nutrition_calc as N
import sleep_engine as S
from wellness_common import InputError

ROOT = pathlib.Path(__file__).resolve().parents[2]
PACKET = (ROOT / "docs" / "clinical" / "BUBBLES_CLINICAL_REVIEW_PACKET.md").read_text(encoding="utf-8")
TODAY = date(2026, 10, 8)   # a Thursday
SHAME = re.compile(r"\b(fail|failed|lazy|bad|guilt|guilty|ashamed|shame|punish|broke|broken|miss(ed)?|worst)\b", re.I)


def entries(hours, start=TODAY, quality=None):
    """One sleep entry per day ending at `start`; hours is oldest-first."""
    out = []
    for i, h in enumerate(hours):
        d = start - timedelta(days=len(hours) - 1 - i)
        out.append({"id": str(i), "date": d.isoformat(), "duration": h, "quality": quality})
    return out


# ============================================================ sleep ============================================================

@pytest.mark.parametrize("age,group,target", [(None, "adult", 8.0), (30, "adult", 8.0), (15, "teen", 9.0), (8, "child", 10.5), (70, "older", 7.5)])
def test_goal_by_age(age, group, target):
    g = S.goal_for_age(age)
    assert g["group"] == group and g["target"] == target


def test_user_goal_overrides_and_bad_stored_goal_is_ignored():
    assert S.resolve_goal(30, {"hours": 7.5})["hours"] == 7.5
    assert S.resolve_goal(30, {"hours": 99})["source"] == "age"
    with pytest.raises(InputError):
        S.normalize_goal({"hours": 2})
    assert S.normalize_goal({"hours": 7.6, "bedtime": "22:30"}) == {"hours": 7.5, "bedtime": "22:30"}


def test_duration_from_times_crosses_midnight():
    assert S.duration_hours("23:30", "06:30") == 7.0
    assert S.duration_hours("01:00", "08:30") == 7.5
    with pytest.raises(InputError):
        S.duration_hours("07:00", "07:00")


def test_score_golden_values():
    assert S.score(8, 8, 0, 10)["value"] == 100
    assert S.score(4, 8, None, None)["value"] == 50          # duration only, half the goal
    assert S.score(8, 8, 120, 10)["value"] == 70             # regularity part is zero: 50 + 0 + 20
    assert S.score(8, 8, 30, None)["value"] == 100           # at the "consistent" limit, no quality: re-weighted
    assert S.score(None, 8, 0, 5) is None


def test_score_always_between_0_and_100():
    rng = random.Random(7)
    for _ in range(2000):
        s = S.score(rng.uniform(0, 30), rng.uniform(4, 12), rng.choice([None, rng.uniform(0, 600)]),
                    rng.choice([None, rng.uniform(-5, 20)]), rng.choice([None, 9.0]))
        assert 0 <= s["value"] <= 100 and all(0 <= v <= 100 for v in s["parts"].values())


def test_regularity_handles_midnight_and_falls_back_to_duration():
    nights = [{"hours": 7, "bedtime": b, "wake": w} for b, w in (("23:50", "07:00"), ("00:10", "07:05"), ("23:55", "06:55"))]
    reg = S.regularity(nights)
    assert reg["basis"] == "times" and reg["minutes"] <= 30 and reg["consistent"]
    wide = [{"hours": 7, "bedtime": b, "wake": "07:00"} for b in ("21:00", "01:00", "23:00")]
    assert not S.regularity(wide)["consistent"]
    only_hours = S.regularity([{"hours": h} for h in (7, 7, 7)])
    assert only_hours == {"minutes": 0, "basis": "duration", "consistent": True}
    assert S.regularity([{"hours": 7}]) is None


def test_sleep_debt_is_shortfall_only_over_seven_days():
    nights = S.nightly(entries([6] * 7), {}, TODAY)
    assert S.sleep_debt(nights, 8, TODAY)["hours"] == 14.0
    mixed = S.nightly(entries([10, 6]), {}, TODAY)           # surplus does not pay back debt
    d = S.sleep_debt(mixed, 8, TODAY)
    assert d["hours"] == 2.0 and d["partial"] is True
    old = S.nightly(entries([4], start=TODAY - timedelta(days=10)), {}, TODAY)
    assert S.sleep_debt(old, 8, TODAY) is None
    assert not SHAME.search(S.sleep_debt(nights, 8, TODAY)["message"])


def test_streak_counts_consecutive_nights_and_resets_without_blame():
    nights = S.nightly(entries([8, 5, 8, 8, 8], start=TODAY - timedelta(days=1)), {}, TODAY)   # last logged night is yesterday
    s = S.streak(nights, 8, TODAY)
    assert s["current"] == 3 and s["best"] == 3
    broken = S.streak(S.nightly(entries([8, 8, 8, 4]), {}, TODAY), 8, TODAY)
    assert broken["current"] == 0 and broken["best"] == 3 and not SHAME.search(broken["message"])
    assert S.streak([], 8, TODAY)["current"] == 0


def test_nap_entries_are_not_nights():
    es = entries([7]) + [{"id": "n", "date": TODAY.isoformat(), "duration": 0.5, "quality": None}]
    n = S.nightly(es, {TODAY.isoformat(): {"nap_minutes": 20}}, TODAY)
    assert len(n) == 1 and n[0]["hours"] == 7 and n[0]["nap_minutes"] == 50
    assert S.nap_summary(n, 30)["total_minutes"] == 50


def test_weekday_pattern_needs_data_and_spread():
    hours = [9 if date(2026, 9, 1) + timedelta(days=i) and (date(2026, 9, 1) + timedelta(days=i)).weekday() == 5 else 6 for i in range(35)]
    nights = S.nightly(entries(hours, start=date(2026, 9, 1) + timedelta(days=34)), {}, TODAY)
    wp = S.weekday_pattern(nights)
    assert wp["best"]["weekday"] == "Saturday" and "tend to" in wp["message"]
    assert S.weekday_pattern(S.nightly(entries([7] * 35), {}, TODAY)) is None
    assert S.weekday_pattern(S.nightly(entries([7, 6, 5]), {}, TODAY)) is None


def _tagged(n_with, n_without, short=6.0, long=8.0):
    es, det = [], {}
    for i in range(n_with + n_without):
        d = (TODAY - timedelta(days=i)).isoformat()
        has = i < n_with
        es.append({"id": str(i), "date": d, "duration": short if has else long, "quality": None})
        det[d] = {"tags": ["caffeine"] if has else []}
    return S.nightly(es, det, TODAY)


def test_tag_insight_uses_tendency_wording_and_minimum_data():
    ins = S.tag_insights(_tagged(5, 8))
    assert len(ins) == 1 and ins[0]["diff_minutes"] == -120 and "tended to" in ins[0]["text"]
    assert not re.search(r"\b(caused|because|due to|leads to)\b", ins[0]["text"])
    assert S.tag_insights(_tagged(2, 12)) == []            # too few nights with the tag
    assert S.tag_insights(_tagged(3, 4)) == []             # too few nights overall
    assert S.tag_insights(_tagged(5, 8, short=7.9, long=8.0)) == []   # difference too small to mention


def test_nights_without_details_are_unknown_not_untagged():
    es = entries([8] * 12)
    assert S.tag_insights(S.nightly(es, {}, TODAY)) == []


def test_winddown_time_from_goal():
    w = S.winddown(8, wake="06:30")
    assert w["bedtime"] == "22:30" and w["winddown"] == "21:45"
    assert S.winddown(7.5, bedtime="23:00")["winddown"] == "22:15"
    usual = S.winddown(8, recent_bedtimes=["23:50", "00:10", "00:00"])
    assert usual["bedtime"] == "00:00" and usual["basis"] == "your usual bedtime"


def test_sleep_overview_shapes():
    goal = S.resolve_goal(None, None)
    empty = S.overview([], {}, goal=goal, today=TODAY)
    assert empty["score"] is None and empty["data_gaps"] and empty["streak"]["current"] == 0
    full = S.overview(entries([7.5] * 14, quality=8), {}, goal=goal, today=TODAY)
    assert 0 <= full["score"]["value"] <= 100 and full["nights_logged"] == 14 and full["last_night"]["hours"] == 7.5
    assert "disclaimer" in full and not SHAME.search(str(full["streak"]) + str(full["debt"]))


# ========================================================== hydration ==========================================================

def test_goal_matches_calculator_and_adapts_on_workout_days():
    g = H.daily_goal(70, 0)
    assert g["goal_ml"] == N.hydration_target(70) and g["workout_bonus_ml"] == 0 and g["basis"] == "personal"
    w = H.daily_goal(70, 45)
    assert w["goal_ml"] == N.hydration_target(70, 45) and w["workout_bonus_ml"] == w["goal_ml"] - g["goal_ml"] > 0
    assert H.daily_goal(60, 0, pregnant=True)["goal_ml"] > H.daily_goal(60, 0)["goal_ml"]
    assert H.daily_goal(None)["basis"] == "general" and H.daily_goal(None)["goal_ml"] == 2000


def test_no_target_when_fluid_restricted():
    g = H.daily_goal(80, 60, fluid_restricted=True)
    assert g["goal_ml"] is None and g["fluid_restricted"] and "clinician" in g["message"]
    view = H.overview([], day="2026-10-08", now_min=600, goal=g, state=H.new_state(), today="2026-10-08")
    assert view["percent"] is None and view["reminders"]["slots"] == [] and view["streak"] is None and view["garden"] is None


def test_goal_always_inside_min_and_max_property():
    rng = random.Random(3)
    for _ in range(1000):
        g = H.daily_goal(rng.uniform(30, 300), rng.uniform(-50, 900), rng.random() < .2, rng.random() < .2)
        assert K.HYDRATION_MIN_ML <= g["goal_ml"] <= K.HYDRATION_MAX_ML
        assert H.daily_goal(rng.uniform(30, 300), 10, fluid_restricted=True)["goal_ml"] is None


def test_volume_validation_and_presets():
    assert H.check_volume(2000) == 2000
    for bad in (2001, 5, 0, -3, "x", True, None):
        with pytest.raises(InputError):
            H.check_volume(bad)
    assert [p["ml"] for p in H.PRESETS] == [150, 250, 500, 750, 1000]
    assert H.volume_from_body({"preset": "bottle_750"}) == 750 and H.volume_from_body({"ml": 330}) == 330
    with pytest.raises(InputError):
        H.volume_from_body({"preset": "barrel"})


def test_beverage_factors_and_day_totals():
    es = [{"id": "1", "date": "2026-10-08T08:00:00+00:00", "volume": 500, "type": "water"},
          {"id": "2", "date": "2026-10-08T09:00:00+00:00", "volume": 250, "type": "coffee"},
          {"id": "3", "date": "2026-10-08T10:00:00+00:00", "volume": 330, "type": "alcohol"},
          {"id": "4", "date": "2026-10-07T10:00:00+00:00", "volume": 999, "type": "water"}]
    t = H.day_totals(es, "2026-10-08")
    assert t["raw_ml"] == 1080 and t["effective_ml"] == 700 and t["by_type"]["alcohol"] == 330
    assert H.normalize_type("Green Tea") == "tea" and H.normalize_type("kombucha") == "other"
    # a local day boundary: 23:30 UTC is already tomorrow in India (+330)
    late = [{"id": "5", "date": "2026-10-08T23:30:00+00:00", "volume": 200, "type": "water"}]
    assert H.day_totals(late, "2026-10-09", 330)["raw_ml"] == 200 and H.day_totals(late, "2026-10-08", 330)["raw_ml"] == 0


def test_reminders_follow_progress_and_stop_at_goal():
    behind = H.reminder_plan(2400, 0, now_min=11 * 60 + 10)
    assert behind["enabled"] and behind["due_now"] == "11:00" and behind["slots"][-1]["minutes"] <= 22 * 60 - K.HYDRATION_REMINDER_BEFORE_SLEEP_MIN
    on_pace = H.reminder_plan(2400, 1500, now_min=11 * 60 + 10)
    assert on_pace["due_now"] is None
    for reason, plan in (("goal_reached", H.reminder_plan(2400, 2400, 600)), ("no_target", H.reminder_plan(None, 0, 600))):
        assert plan["slots"] == [] and plan["due_now"] is None and plan["reason"] == reason


def test_never_nag_after_goal_property():
    rng = random.Random(5)
    for _ in range(500):
        goal = rng.uniform(1500, 4000)
        plan = H.reminder_plan(goal, goal + rng.uniform(0, 3000), rng.randint(0, 1439), rng.randint(300, 600), rng.randint(1200, 1400))
        assert plan["slots"] == [] and plan["due_now"] is None


def test_streak_does_not_break_while_today_is_unfinished():
    met = ["2026-10-05", "2026-10-06", "2026-10-07"]
    s = H.streak(met, TODAY)
    assert s["current"] == 3 and s["best"] == 3
    assert H.streak(["2026-10-01"], TODAY)["current"] == 0 and not SHAME.search(H.streak([], TODAY)["message"])


def test_garden_is_a_monotonic_pure_function():
    names = [H.garden(0, d)["name"] for d in (0, 2, 3, 7, 14, 30, 60, 500)]
    assert names == ["seed", "seed", "sprout", "leaves", "blossom", "pond", "oasis", "oasis"]
    levels = [H.garden(d * 1000, d)["level"] for d in range(0, 100)]
    assert levels == sorted(levels)
    assert H.garden(5000, 3)["next_level"] == "leaves" and H.garden(5000, 3)["days_to_next"] == 4
    assert H.garden(5000, 3) == H.garden(5000, 3)


def test_state_updates_are_idempotent_for_days():
    s = H.mark_met(H.mark_met(H.new_state(), "2026-10-08"), "2026-10-08")
    assert s["met_dates"] == ["2026-10-08"] and H.add_ml(s, 250)["total_ml"] == 250.0


# ======================================================== medications ==========================================================

def sched(**kw):
    base = {"name": "Metformin", "dose_label": "500 mg", "times": ["08:00", "20:00"]}
    base.update(kw)
    s = M.normalize_schedule(base, TODAY)
    s["id"] = kw.get("id", "aaaaaaaaaaaa")
    return s


def test_schedule_validation():
    assert sched()["times"] == ["08:00", "20:00"] and sched()["refill_alert_days"] == K.MED_REFILL_ALERT_DAYS
    bad = [{"name": ""}, {"name": "x", "times": []}, {"name": "x", "times": ["25:00"]}, {"name": "x", "times": ["8:00am"]},
           {"name": "x", "times": ["08:00"], "weekdays": [7]}, {"name": "x", "times": ["08:00"], "end_date": "2020-01-01"},
           {"name": "x", "times": ["08:00"], "kind": "magic"}, {"name": "x", "kind": "taper", "times": ["08:00"]},
           {"name": "x", "kind": "cycle_pill", "times": ["08:00"]}, {"name": "x", "kind": "glp1", "times": ["08:00"], "weekdays": [1, 2]},
           {"name": "x", "times": ["08:00"], "pill_count": -1}]
    for b in bad:
        with pytest.raises(InputError):
            M.normalize_schedule(b, TODAY)
    assert M.normalize_schedule({"name": "Paracetamol", "kind": "as_needed"}, TODAY)["times"] == []


def test_doses_for_day_weekdays_dates_and_pause():
    s = sched(weekdays=[0, 3], start_date="2026-10-01", end_date="2026-10-20")      # Mon and Thu
    assert [d["time"] for d in M.doses_for_day(s, TODAY)] == ["08:00", "20:00"]       # Thursday
    assert M.doses_for_day(s, TODAY + timedelta(days=1)) == []                       # Friday
    assert M.doses_for_day(s, date(2026, 9, 28)) == [] and M.doses_for_day(s, date(2026, 10, 22)) == []
    assert M.doses_for_day({**s, "active": False}, TODAY) == []


def test_cycle_pill_21_7_and_28():
    start = "2026-10-01"
    pill = sched(kind="cycle_pill", name="Pill", times=["21:00"], cycle={"pattern": "21_7", "pack_start": start})
    assert len(M.doses_for_day(pill, date(2026, 10, 21))) == 1 and M.doses_for_day(pill, date(2026, 10, 22)) == []   # day 21 is pill-free
    assert M.pill_free_today(pill, date(2026, 10, 25)) and not M.pill_free_today(pill, date(2026, 10, 29))        # next pack begins on day 28
    assert len(M.doses_for_day(pill, date(2026, 10, 29))) == 1
    pill28 = sched(kind="cycle_pill", name="Pill", times=["21:00"], cycle={"pattern": "28", "pack_start": start})
    d = M.doses_for_day(pill28, date(2026, 10, 24))
    assert len(d) == 1 and d[0]["placebo"] is True and M.doses_for_day(pill28, date(2026, 10, 10))[0]["placebo"] is False


def test_taper_steps_are_shown_not_invented():
    t = sched(kind="taper", name="Prednisolone", times=["08:00"], dose_label=None, start_date="2026-09-01",
              taper_steps=[{"from_date": "2026-10-01", "dose_label": "20 mg"}, {"from_date": "2026-10-08", "dose_label": "10 mg"}])
    assert M.doses_for_day(t, date(2026, 10, 7))[0]["dose_label"] == "20 mg"
    assert M.doses_for_day(t, TODAY)[0]["dose_label"] == "10 mg"
    assert M.doses_for_day(t, date(2026, 9, 30)) == []


NOW = datetime(2026, 10, 8, 8, 30)   # local wall clock


def test_due_list_statuses_and_windows():
    s = sched()
    items = {i["time"]: i for i in M.due_list([s], {}, NOW)["items"]}
    assert items["08:00"]["status"] == "due" and items["20:00"]["status"] == "upcoming"
    assert items["08:00"]["window"] == {"start": "07:00", "end": "09:00"}
    late = M.due_list([s], {}, datetime(2026, 10, 8, 10, 30))["items"][0]
    assert late["status"] == "late" and "pharmacist or prescriber" in late["message"]
    done = M.due_list([s], {s["id"]: {"doses": {"08:00": {"status": "taken"}}}}, NOW)["items"][0]
    assert done["status"] == "taken"
    snz = M.due_list([s], {s["id"]: {"doses": {"08:00": {"status": "snoozed", "snoozed_until": "08:45"}}}}, NOW)["items"][0]
    assert snz["status"] == "snoozed"
    prn = M.due_list([M.normalize_schedule({"name": "Paracetamol", "kind": "as_needed"}, TODAY) | {"id": "bbbbbbbbbbbb"}], {}, NOW)
    assert prn["items"] == [] and prn["as_needed"][0]["name"] == "Paracetamol"


def test_record_dose_rules_and_pill_counter():
    s = sched(pill_count=10, units_per_dose=1)
    utc = NOW.replace(tzinfo=timezone.utc)
    payload, rec, delta = M.record_dose(s, None, day=TODAY, time_key="08:00", status="taken", now_utc=utc, now_local=NOW)
    assert delta == -1 and payload["doses"]["08:00"]["status"] == "taken"
    s2 = M.apply_pill_delta(s, delta)
    assert s2["pill_count"] == 9
    _p, _r, back = M.record_dose(s2, payload, day=TODAY, time_key="08:00", status="skipped", reason="side_effects", now_utc=utc, now_local=NOW)
    assert back == 1 and "pharmacist or prescriber" in _r["message"]
    _p2, _r2, again = M.record_dose(s2, payload, day=TODAY, time_key="08:00", status="taken", now_utc=utc, now_local=NOW)
    assert again == 0
    assert M.apply_pill_delta({"pill_count": 0}, -1)["pill_count"] == 0
    with pytest.raises(InputError):
        M.record_dose(s, None, day=TODAY, time_key="13:00", status="taken", now_utc=utc, now_local=NOW)
    with pytest.raises(InputError):
        M.record_dose(s, None, day=TODAY, time_key="08:00", status="skipped", reason="bored", now_utc=utc, now_local=NOW)
    with pytest.raises(InputError):
        M.record_dose(s, None, day=TODAY, time_key="08:00", status="snoozed", snooze_minutes=7, now_utc=utc, now_local=NOW)
    z = M.record_dose(s, None, day=TODAY, time_key="08:00", status="snoozed", snooze_minutes=15, now_utc=utc, now_local=NOW)[1]
    assert z["snoozed_until"] == "08:45"
    prn = M.normalize_schedule({"name": "Paracetamol", "kind": "as_needed"}, TODAY) | {"id": "cccccccccccc"}
    assert M.record_dose(prn, None, day=TODAY, time_key=None, status="taken", now_utc=utc, now_local=NOW)[1]["time"] == "prn-1"
    with pytest.raises(InputError):
        M.record_dose(prn, None, day=TODAY, time_key=None, status="skipped", now_utc=utc, now_local=NOW)


def test_refill_alert():
    s = sched(pill_count=14)                      # 2 per day -> 7 days left
    r = M.refill_status(s, TODAY)
    assert r["days_left"] == 7.0 and r["alert"] and "refill" in r["message"]
    assert not M.refill_status(sched(pill_count=200), TODAY)["alert"]
    assert M.refill_status(sched(), TODAY) is None


def test_adherence_is_non_shaming_and_needs_enough_doses():
    s = sched(times=["08:00"], start_date="2026-09-01")
    docs = {(s["id"], (TODAY - timedelta(days=i)).isoformat()): {"doses": {"08:00": {"status": "taken"}}} for i in range(1, 5)}
    a = M.adherence([s], docs, datetime(2026, 10, 8, 12, 0), 7)
    assert a["total"] == {"taken": 4, "skipped": 0, "not_recorded": 3} and a["percent"] == 57
    assert not SHAME.search(a["message"]) and "pharmacist or prescriber" in a["message"]
    few = M.adherence([s], {}, datetime(2026, 10, 8, 7, 0), 2)
    assert few["percent"] is None and "Not enough" in few["message"]
    steady = M.adherence([s], {(s["id"], (TODAY - timedelta(days=i)).isoformat()): {"doses": {"08:00": {"status": "taken"}}} for i in range(1, 8)},
                         datetime(2026, 10, 8, 7, 0), 7)
    assert steady["percent"] == 100


# --- interactions ---------------------------------------------------------------------------------------------------------

def packet_rows():
    section = PACKET.split("## 10. Medications")[1].split("## 11.")[0]
    rows = []
    for line in section.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.startswith("|") and len(cells) == 3 and cells[0] not in ("Pair",) and not set(cells[0]) <= {"-"}:
            rows.append(tuple(cells))
    return rows


def test_interaction_table_matches_the_clinical_packet_exactly():
    packet = packet_rows()
    code = [(r["pair"], r["concern"], r["level"]) for r in K.INTERACTION_RULES]
    assert len(packet) == 15 and sorted(packet) == sorted(code)
    assert len({r["id"] for r in K.INTERACTION_RULES}) == 15
    for r in K.INTERACTION_RULES:
        assert r["a"] in K.DRUG_CLASSES and all(b in K.DRUG_CLASSES for b in r["b"]) and r["level"] in ("high", "moderate", "timing")


# one (name, name) example per rule, mixing generics and brands
EXAMPLES = {
    "warfarin_nsaid": ("Warfarin", "Brufen"), "nsaid_ssri": ("diclofenac", "Sertraline"), "acearb_potassium": ("Ramipril", "potassium chloride"),
    "acearb_nsaid": ("Losartan", "naproxen"), "ssri_serotonergic": ("Escitalopram", "tramadol"), "nitrate_pde5": ("isosorbide", "Viagra"),
    "simvastatin_cyp3a4": ("Simvastatin", "grapefruit"), "levothyroxine_minerals": ("Thyronorm", "Shelcal"),
    "tetracycline_minerals": ("doxycycline", "milk"), "metformin_alcohol": ("Glycomet", "wine"), "methotrexate_nsaid": ("methotrexate", "ibuprofen"),
    "digoxin_diuretic": ("Lanoxin", "furosemide"), "hypoglycaemia": ("insulin", "calorie deficit"), "lithium_renal": ("lithium", "ibuprofen"),
    "chc_inducers": ("combined pill", "St John's wort"),
}
FORBIDDEN_TONE = re.compile(r"\b(do not|don't|dont|never|avoid|stop|must|should not|shouldn't|contraindicated|forbidden|dangerous|deadly)\b", re.I)


@pytest.mark.parametrize("rule_id,pair", list(EXAMPLES.items()))
def test_each_rule_fires_in_both_orders_and_is_worded_as_a_check(rule_id, pair):
    for names in (list(pair), list(reversed(pair))):
        found = [f for f in M.check_interactions(names) if f["rule"] == rule_id]
        assert found, (rule_id, names)
        assert "pharmacist" in found[0]["message"].lower() and not FORBIDDEN_TONE.search(found[0]["message"])


def test_interaction_edge_cases():
    assert M.check_interactions(["Paracetamol", "Metformin", "Vitamin D"]) == []
    assert M.check_interactions([]) == []
    out = M.check_interactions(["warfarin", "ibuprofen", "aspirin"])
    assert [f["level"] for f in out] == ["high", "high"] and {f["names"][1] for f in out} == {"ibuprofen", "aspirin"}
    assert M.check_interactions(["Warfarin", "warfarin"]) == []                      # same medicine twice is not a pair
    levels = [f["level"] for f in M.check_interactions(["warfarin", "ibuprofen", "sertraline", "levothyroxine", "calcium"])]
    assert levels == sorted(levels, key=lambda l: {"high": 0, "moderate": 1, "timing": 2}[l])
    with pytest.raises(InputError):
        M.check_interactions("warfarin")
    with pytest.raises(InputError):
        M.check_interactions(["x"] * 31)
    assert M.check_interactions(["ARB", "nsaid"]) and M.check_interactions(["warfarin", "NSAID"])   # class names work as names
    assert M.check_interactions(["warfarin", "carbonated"]) == []


def test_allergy_warnings():
    w = M.allergy_warnings(["Augmentin", "Paracetamol"], ["Penicillin"])
    assert len(w) == 1 and w[0]["medicine"] == "Augmentin" and "pharmacist" in w[0]["message"]
    assert M.allergy_warnings(["ibuprofen"], ["NSAIDs"]) and M.allergy_warnings(["aspirin"], ["aspirin"])
    assert M.allergy_warnings(["Paracetamol"], ["peanuts"]) == []


# --- RxNav adapter -----------------------------------------------------------------------------------------------------------

def fake_rxnav(url):
    if "rxcui.json" in url:
        return {"idGroup": {"rxnormId": ["5640"]}}
    return {"relatedGroup": {"conceptGroup": [{"conceptProperties": [{"name": "Ibuprofen"}]}]}}


def test_rxnav_is_off_by_default_and_fail_soft(monkeypatch):
    monkeypatch.delenv("BUBBLES_ENABLE_RXNAV", raising=False)
    assert M.rxnav_enabled() is False and M.rxnav_ingredients("advil", fake_rxnav) == []
    monkeypatch.setenv("BUBBLES_ENABLE_RXNAV", "1")
    assert M.rxnav_enabled() and M.rxnav_ingredients("advil", fake_rxnav) == ["ibuprofen"]
    assert M.expand_names(["Advil"], fake_rxnav) == ["Advil", "ibuprofen"]
    def boom(url):
        raise TimeoutError("network down")
    assert M.rxnav_ingredients("advil", boom) == [] and M.expand_names(["Advil"], boom) == ["Advil"]
    assert M.rxnav_ingredients("advil", lambda u: {"idGroup": {}}) == []
    assert any(f["rule"] == "warfarin_nsaid" for f in M.check_interactions(M.expand_names(["warfarin", "Advil"], fake_rxnav)))


# --- GLP-1 ----------------------------------------------------------------------------------------------------------------------

DOSE_CHANGE = re.compile(r"\b(increase|decrease|reduce|raise|lower|double|halve|skip your dose|stop taking|titrate|up-?titrat|higher dose|lower dose)\b", re.I)


def test_glp1_site_rotation_reminders_and_nudges():
    s = sched(kind="glp1", name="Semaglutide", times=["09:00"], weekdays=[3], dose_label="0.5 mg")
    assert M.next_site(None) == "abdomen_left" and M.next_site("upper_arm_right") == "abdomen_left" and M.next_site("thigh_left") == "thigh_right"
    ov = M.glp1_overview(s, {}, [], NOW)
    assert ov["schedule"]["dose_day_today"] and ov["schedule"]["reminder"] == "Today is your dose day." and "prescriber decides" in ov["note"]
    docs = {(s["id"], "2026-10-08"): {"doses": {"09:00": {"status": "taken", "site": "thigh_left"}}}}
    after = M.glp1_overview(s, docs, [], NOW)
    assert after["schedule"]["days_until"] == 7 and after["schedule"]["suggested_site"] == "thigh_right"
    ill = M.glp1_overview(s, {}, [{"nausea": 8, "appetite": 1}], NOW)
    text = " ".join(ill["nudges"] + [ill["note"]])
    assert "prescriber" in text and "protein" in text and "fluid" in text.lower() and not DOSE_CHANGE.search(text)
    assert M.glp1_overview(None, {}, [], NOW)["schedule"] is None
    with pytest.raises(InputError):
        M.normalize_glp1_log({})
    with pytest.raises(InputError):
        M.normalize_glp1_log({"nausea": 11})


def test_logbook_export_data():
    s = sched(times=["08:00"], start_date="2026-09-01")
    docs = {(s["id"], "2026-10-07"): {"doses": {"08:00": {"status": "skipped", "reason": "side_effects"}}},
            (s["id"], "2026-10-06"): {"doses": {"08:00": {"status": "taken"}}}}
    lb = M.logbook([s, sched(name="Ibuprofen", id="bbbbbbbbbbbb", times=["09:00"], start_date="2026-09-01")], docs, datetime(2026, 10, 8, 12), 14, ["Penicillin"])
    assert lb["medications"][0]["skip_reasons"] == {"side_effects": 1} and lb["medications"][0]["last_taken"] == "2026-10-06"
    assert lb["allergies"] == ["Penicillin"] and "Medication logbook" in lb["text"] and "not a prescription" in lb["text"].lower()


# ============================================== no message ever advises doubling up or a dose change =====================================

def test_med_copy_never_advises_double_dosing_or_dose_changes():
    s = sched()
    late_msgs = [i["message"] for i in M.due_list([s], {}, datetime(2026, 10, 8, 14, 0))["items"] if "message" in i]
    msgs = late_msgs + [M.MISSED_MESSAGE, M.PRESCRIBER_NOTE, M.adherence([s], {}, datetime(2026, 10, 8, 12), 30)["message"]]
    msgs += [f["message"] for f in M.check_interactions([n for pair in EXAMPLES.values() for n in pair])]
    msgs += M.glp1_overview(sched(kind="glp1", times=["09:00"], weekdays=[3]), {}, [{"nausea": 9, "appetite": 1}], NOW)["nudges"]
    banned = re.compile(r"\b(double|twice the|extra dose|catch up|make up|two doses|take two|take extra|increase|decrease|lower your dose|raise your dose)\b", re.I)
    for m in msgs:
        assert not banned.search(m), m
    assert "pharmacist or prescriber" in M.MISSED_MESSAGE
    for forbidden in K.FORBIDDEN_ADVICE:
        if forbidden != "diagnosis":
            assert all(forbidden not in m.lower() for m in msgs)


# ============================================================ mind ============================================================

def test_safety_gate_blocks_urgent_text_and_passes_ordinary_text():
    for t in ("I want to end my life", "I have severe chest pain right now and I cannot breathe"):
        r = Mind.safety_gate("fine", t)
        assert r and r["status"] == "safety" and r["saved"] is False and r["message"]
    assert Mind.safety_gate(None, "", "Had a lovely walk and a calm day") is None
    assert Mind.safety_gate("no chest pain today") is None
    assert Mind.safety_gate("I want to end my life")["crisis"] is True


def test_checkin_normalisation_and_notes_roundtrip():
    from health_logs import _mood_row
    c = Mind.normalize_checkin({"face": 4, "activities": ["exercise", "social", "exercise"], "notes": "good day"})
    assert c["mood"] == 8 and c["activities"] == ["exercise", "social"]
    body = Mind.tracker_body(c, None)
    row = _mood_row(body)
    assert Mind.parse_activities(row["notes"]) == ["exercise", "social"] and "good day" in row["notes"]
    assert Mind.parse_activities("Activities: exercise | Stress 3/10") == ["exercise"]
    for bad in ({}, {"mood": 11}, {"mood": 5, "activities": ["skydiving"]}, {"mood": 5, "activities": "run"}, {"face": 9}):
        with pytest.raises(InputError):
            Mind.normalize_checkin(bad)
    assert [Mind.level_of(m) for m in (1, 2, 3, 6, 9, 10)] == [1, 1, 2, 3, 5, 5]


def test_pixels_merge_never_loses_old_days():
    stored = {"2026-01-05": {"m": 7, "n": 1}, "2026-10-07": {"m": 3, "n": 1}}
    recent = Mind.per_day_moods([{"date": "2026-10-07T10:00:00+00:00", "mood": 8}, {"date": "2026-10-07T20:00:00+00:00", "mood": 6}])
    merged = Mind.merge_pixels(stored, recent)
    assert merged["2026-01-05"]["m"] == 7 and merged["2026-10-07"] == {"m": 7.0, "n": 2}
    assert Mind.merge_pixels(stored, recent, "2026-10-07")["2026-10-07"]["m"] == 3      # a possibly-partial oldest day never overwrites
    year = Mind.year_pixels(merged, 2026)
    assert len(year["days"]) == 365 and year["logged_days"] == 2 and len(Mind.year_pixels({}, 2028)["days"]) == 366


def test_phq2_gad2_gentle_wording():
    assert Mind.screen_questions("phq2")["questions"] == list(K.PHQ2_QUESTIONS)
    low = Mind.score_screen("phq2", [1, 1])
    high = Mind.score_screen("gad2", [2, 1])
    assert low["score"] == 2 and not low["suggest_talking_to_someone"]
    assert high["score"] == 3 and high["suggest_talking_to_someone"] and "talking to someone" in high["message"]
    for r in (low, high):
        assert "diagnos" not in r["message"].lower() and "depress" not in r["message"].lower() and "disorder" not in r["message"].lower()
    assert Mind.score_screen("phq2", [3, 3])["score"] == 6
    for bad in ([1], [1, 4], [1, True], "11", [1, 2, 3]):
        with pytest.raises(InputError):
            Mind.score_screen("phq2", bad)
    with pytest.raises(InputError):
        Mind.score_screen("phq9", [1, 1])
    assert Mind.screen_due([], TODAY)["due"] and not Mind.screen_due([{"payload": {"date": "2026-10-05"}}], TODAY)["due"]


def test_journal_local_only_is_filtered_from_ai_context():
    entries = [{"payload": {"id": "1", "text": "private", "local_only": True}}, {"payload": {"id": "2", "text": "shareable", "local_only": False}},
               {"id": "3", "text": "flat", "local_only": True}]
    assert [e.get("payload", e)["id"] for e in Mind.journal_for_ai(entries)] == ["2"]
    assert Mind.normalize_journal({"text": " hello ", "local_only": True}) == {"text": "hello", "local_only": True}
    for bad in ({"text": ""}, {"text": "x", "local_only": "yes"}, {}, {"text": ["a"]}):
        with pytest.raises(InputError):
            Mind.normalize_journal(bad)
    assert len(Mind.normalize_journal({"text": "a" * 9000})["text"]) == K.MIND_JOURNAL_MAX_CHARS


def test_exercise_catalogue():
    ids = {e["id"] for e in Mind.EXERCISES}
    assert {"box_breathing", "grounding_54321"} <= ids
    box = next(e for e in Mind.EXERCISES if e["id"] == "box_breathing")
    assert box["pattern"] == {"inhale": 4, "hold": 4, "exhale": 4, "hold_empty": 4} and len(next(e for e in Mind.EXERCISES if e["id"] == "grounding_54321")["steps"]) == 5


def test_correlations_have_minimum_data_and_tendency_wording():
    days = [(TODAY - timedelta(days=i)).isoformat() for i in range(14)]
    mood = {d: (8 if i % 2 == 0 else 5) for i, d in enumerate(days)}
    active = {d for i, d in enumerate(days) if i % 2 == 0}
    out = Mind.correlations(mood, exercise_days=active)
    assert out["insights"][0]["factor"] == "exercise" and out["insights"][0]["diff"] == 3.0 and "tended to" in out["insights"][0]["text"]
    assert not re.search(r"\b(caused|because)\b", out["insights"][0]["text"])
    few = Mind.correlations({d: 6 for d in days[:5]}, exercise_days={days[0]})
    assert few["insights"] == [] and few["data_gaps"]
    sleep = {d: (8.0 if i % 2 == 0 else 5.0) for i, d in enumerate(days)}
    assert any(i["factor"] == "sleep" for i in Mind.correlations(mood, sleep_hours=sleep, sleep_goal=8)["insights"])
    flat = Mind.correlations({d: 6 for d in days}, exercise_days=active)
    assert flat["insights"] == []
