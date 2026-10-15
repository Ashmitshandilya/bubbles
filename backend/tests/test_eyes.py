"""Eyes end to end on the backend: the tracker rows, the derived body-system facts, the eye system itself and how chat understands eye words."""
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from health_logs import DOMAINS, EYE_SYMPTOMS, _eyes_row
from health_semantics import analyze
from organ_intelligence import eye_snapshot, build_body_system_intelligence
from organ_tracker import ORGANS, assess_organ
from safety_engine import assess_safety

NOW = datetime(2026, 10, 15, 8, 0, tzinfo=timezone.utc)


def day(offset: int) -> str:
    return (NOW.date() - timedelta(days=offset)).isoformat()


# --- tracker rows -----------------------------------------------------------------------------------------------------------

def test_eyes_is_a_tracker_domain_in_the_event_ledger():
    domain = DOMAINS["eyes"]
    assert domain["table"] == "health_events" and domain["filters"] == {"event_type": "eye_check"}


def test_a_full_eye_check_is_stored_as_the_persons_own_record():
    row = _eyes_row({"screen_hours": "7.5", "comfort": 2, "symptoms": "dry, red", "glasses": "yes", "breaks": 3,
                     "last_exam": "2025-11-01", "notes": "after a long day", "date": "2026-10-05T10:00:00Z"})
    assert row["event_type"] == "eye_check" and row["description"] == "after a long day"
    assert row["data"] == {"screen_hours": 7.5, "comfort": 2, "symptoms": "dry, red", "glasses": "yes", "breaks": 3, "last_exam": "2025-11-01"}
    assert domain_entry({"data": row["data"], "description": row["description"]})["symptoms"] == "dry, red"


def domain_entry(row):
    return DOMAINS["eyes"]["to_entry"](row)


def test_symptoms_may_be_a_list_or_a_comma_string_and_never_repeat():
    assert _eyes_row({"symptoms": ["dry", "red", "dry"]})["data"]["symptoms"] == "dry, red"
    assert _eyes_row({"symptoms": " Dry , RED "})["data"]["symptoms"] == "dry, red"


@pytest.mark.parametrize("body,fragment", [
    ({}, "at least one"),
    ({"symptoms": "stabbing"}, "eye symptom must be one of"),
    ({"screen_hours": 19}, "screen hours"),
    ({"screen_hours": -1}, "screen hours"),
    ({"comfort": 6}, "comfort"),
    ({"breaks": 99}, "breaks"),
    ({"glasses": "maybe"}, "yes or no"),
    ({"last_exam": (date.today() + timedelta(days=30)).isoformat()}, "future"),
    ({"last_exam": "not a date"}, "ISO date"),
])
def test_bad_eye_entries_are_refused_with_a_reason(body, fragment):
    with pytest.raises(HTTPException) as caught:
        _eyes_row(body)
    assert caught.value.status_code == 422 and fragment in caught.value.detail


def test_one_detail_is_enough_and_zero_is_a_real_answer():
    assert _eyes_row({"breaks": 0})["data"] == {"breaks": 0}
    assert _eyes_row({"screen_hours": 0})["data"] == {"screen_hours": 0}
    assert _eyes_row({"glasses": False})["data"] == {"glasses": "no"}


def test_the_symptom_vocabulary_is_fixed():
    assert EYE_SYMPTOMS == ("dry", "itchy", "red", "strained", "blurry", "watery", "headache")


# --- facts derived from the logs --------------------------------------------------------------------------------------------

def check(offset, **data):
    return {"id": f"e{offset}-{len(data)}", "event_type": "eye_check", "extraction_status": "confirmed",
            "extracted_data": {"date": day(offset), **data, "_prov": {"source": "tracker"}}}


def chat_symptom(offset, name, **prov):
    return {"id": f"s{offset}", "event_type": "symptom", "extraction_status": "confirmed",
            "extracted_data": {"date": day(offset), "name": name, "symptom": name, "_prov": {"assertion": "present", **prov}}}


def test_nothing_logged_means_nothing_derived_never_zeros():
    assert eye_snapshot([], NOW) == {}
    assert eye_snapshot([chat_symptom(1, "headache")], NOW) == {}


def test_screen_time_average_needs_three_days():
    assert "screen_hours_avg" not in eye_snapshot([check(1, screen_hours=9), check(2, screen_hours=9)], NOW)
    out = eye_snapshot([check(1, screen_hours=9), check(2, screen_hours=6), check(3, screen_hours=3)], NOW)
    assert out["screen_hours_avg"] == 6.0


def test_one_value_per_day_the_longest_logged():
    events = [check(1, screen_hours=2), check(1, screen_hours=8), check(2, screen_hours=4), check(3, screen_hours=6)]
    assert eye_snapshot(events, NOW)["screen_hours_avg"] == 6.0


def test_only_the_last_two_weeks_count():
    events = [check(20, screen_hours=12, eye_symptoms="dry"), check(1, screen_hours=1), check(2, screen_hours=1), check(3, screen_hours=1)]
    out = eye_snapshot(events, NOW)
    assert out["screen_hours_avg"] == 1.0 and "eye_symptom_days" not in out


def test_symptom_days_count_distinct_days_from_the_tracker_and_from_chat():
    events = [check(1, eye_symptoms="dry, red"), check(1, eye_comfort=1), check(2, eye_comfort=2),
              chat_symptom(3, "eye strain"), chat_symptom(3, "dry eyes"), chat_symptom(4, "headache"), check(5, eye_comfort=4)]
    assert eye_snapshot(events, NOW)["eye_symptom_days"] == 3          # days 1, 2 and 3


def test_denied_other_peoples_and_rejected_entries_never_count():
    events = [chat_symptom(1, "eye strain", assertion="negated"), chat_symptom(2, "eye strain", subject="other"),
              {**chat_symptom(3, "eye strain"), "extraction_status": "rejected"}]
    assert eye_snapshot(events, NOW) == {}


def test_the_latest_recorded_exam_date_is_kept_even_when_old():
    out = eye_snapshot([check(100, last_exam="2024-05-01"), check(40, last_exam="2025-09-10")], NOW)
    assert out["last_eye_exam"] == "2025-09-10"


# --- the eye system ----------------------------------------------------------------------------------------------------------

def test_eyes_are_a_body_system_with_no_claim_when_nothing_is_known():
    assert "eyes" in ORGANS
    a = assess_organ("eyes", {})
    assert a.status == "unknown" and a.score is None and a.confidence == 0.0 and a.signals == []
    assert any("not mean the organ is healthy" in text for text in a.limitations)


def test_an_exam_date_alone_is_not_evidence_of_healthy_eyes():
    a = assess_organ("eyes", {"last_eye_exam": "2026-09-01"})
    assert a.status == "unknown" and a.signals == []


def test_long_screen_days_and_frequent_symptoms_make_it_worth_watching():
    a = assess_organ("eyes", {"screen_hours_avg": 7.5, "eye_symptom_days": 4})
    assert {s.factor for s in a.signals} == {"high_screen_time", "frequent_eye_symptoms"}
    assert a.status == "watch" and any("screen breaks" in text for text in a.recommended_actions)


def test_either_signal_alone_is_below_watch_and_thresholds_are_exact():
    assert assess_organ("eyes", {"screen_hours_avg": 5.9}).signals == []
    assert [s.factor for s in assess_organ("eyes", {"screen_hours_avg": 6}).signals] == ["high_screen_time"]
    assert assess_organ("eyes", {"eye_symptom_days": 2}).signals == []
    assert assess_organ("eyes", {"eye_symptom_days": 3}).status == "no_major_risk_signal"


def test_diabetes_and_blood_pressure_signals_bring_the_exam_advice_not_a_diagnosis():
    a = assess_organ("eyes", {"persistent_high_glucose": True, "persistent_high_bp": True})
    assert a.status == "watch"
    assert any("how often you should have an eye exam" in text for text in a.recommended_actions)
    assert not any("diagnos" in text.lower() for text in a.recommended_actions)


def test_bad_values_never_become_signals():
    for bad in (True, "9", None, [9]):
        assert assess_organ("eyes", {"screen_hours_avg": bad, "eye_symptom_days": bad}).signals == []


def test_body_systems_report_includes_eyes_from_the_logs():
    events = [check(i, screen_hours=8, eye_symptoms="strained") for i in range(1, 5)]
    report = build_body_system_intelligence(events)
    eyes = next(s for s in report["systems"] if s["organ"] == "eyes")
    assert report["total_systems"] == len(ORGANS) == 16
    assert eyes["status"] == "watch" and {s["factor"] for s in eyes["signals"]} == {"high_screen_time", "frequent_eye_symptoms"}


# --- chat understanding ------------------------------------------------------------------------------------------------------

def concepts(text, **want):
    return [(f.concept, f.assertion, f.experiencer) for f in analyze(text)]


@pytest.mark.parametrize("text,concept", [
    ("My eyes are burning after the laptop", "eye_strain"),
    ("my eyes feel tired", "eye_strain"),
    ("I have dry eyes", "dry_eyes"),
    ("my eyes are red", "red_eye"),
    ("I think I have conjunctivitis", "red_eye"),
    ("my eyes hurt", "eye_pain"),
    ("there is pressure behind my eyes", "eye_pain"),
    ("itchy eyes since morning", "eye_itch"),
    ("aankhon mein jalan ho rahi hai", "eye_strain"),
    ("meri aankh mein dard hai", "eye_pain"),
    ("aankhon mein khujli hai", "eye_itch"),
    ("aankhen lal hain", "red_eye"),
    ("aankhein sookhi hain", "dry_eyes"),
])
def test_eye_words_become_eye_symptoms(text, concept):
    assert concept in [c for c, _a, e in concepts(text) if e == "self"]


@pytest.mark.parametrize("text", ["I took a red-eye flight", "eye drops twice a day", "keep an eye on the baby", "she has eyes like her mother"])
def test_words_that_only_look_like_eye_symptoms_are_ignored(text):
    assert concepts(text) == []


def test_denied_and_other_peoples_eye_symptoms_are_not_the_persons_own():
    assert concepts("no eye pain") == [("eye_pain", "negated", "self")]
    assert concepts("my mom has red eyes")[0][1:] == ("other_person", "other")


def test_severe_eye_pain_is_urgent_but_ordinary_eye_discomfort_is_not():
    severe = assess_safety("severe eye pain since morning")
    assert (severe.level, severe.state) == ("AMBER", "URGENT")
    for text in ("my eyes are burning after the laptop", "my eyes hurt a bit", "dry eyes again", "no severe eye pain", "my dad has severe eye pain"):
        assert assess_safety(text).state == "NO_REDFLAG", text


def test_sudden_vision_loss_stays_a_red_emergency():
    for text in ("sudden loss of vision in one eye", "I suddenly can't see out of my left eye", "all of a sudden I cannot see anything",
                 "I suddenly lost my vision", "a curtain fell over my vision", "suddenly I can't see properly"):
        assert assess_safety(text).level == "RED", text


def test_everyday_sight_talk_is_not_an_emergency():
    for text in ("I can't see the board from the back row", "I can't see properly without my glasses", "my vision is a bit blurry after the laptop",
                 "no sudden loss of vision", "my dad suddenly lost his vision", "I cannot see anything in this dark room",
                 "can't see out of my left eye because of the hair", "I lost my sunglasses suddenly"):
        assert assess_safety(text).level != "RED", text


# --- patterns ----------------------------------------------------------------------------------------------------------------

def test_screen_time_links_are_checked_against_eye_comfort_and_next_nights_sleep():
    import association_insights as ai
    pairs = {(x, y, lag) for x, y, lag, *_ in ai.PAIRS}
    assert ("screen_hours", "eye_comfort", 0) in pairs and ("screen_hours", "sleep_quality", 1) in pairs
    assert ai.TOPIC["screen_hours"] == "screen time" and ai.TOPIC["eye_comfort"] == "eye comfort"


def test_a_clear_screen_time_and_eye_comfort_link_is_found_and_worded_as_an_association():
    import association_insights as ai
    start = date(2026, 8, 1)
    days = [start + timedelta(days=i) for i in range(30)]
    screen = {d: float(2 + (i * 7) % 10) for i, d in enumerate(days)}
    comfort = {d: round(5 - screen[d] / 3, 2) for d in days}
    out = ai.analyze({"screen_hours": screen, "eye_comfort": comfort})
    found = [i for i in out["insights"] if i["domains"] == ["screen_hours", "eye_comfort"]]
    assert found and found[0]["direction"] == "down"
    text = found[0]["text"].lower()
    assert "tended to be lower" in text and "because" not in text and "causes" in text and "not" in text.split("causes")[0][-40:]   # only the caveat mentions cause, and it denies it


def test_the_loader_reads_screen_time_and_comfort_from_the_eyes_logs():
    import association_loader as loader
    rows = [{"event_type": "eye_check", "event_date": f"2026-10-{d:02d}T09:00:00+00:00", "description": None,
             "data": {"screen_hours": 4 + d, "comfort": 3}, "id": f"id{d}", "user_id": "u"} for d in range(1, 4)]

    class Q:
        def __init__(self, data): self.data = data
        def select(self, *a, **k): return self
        def eq(self, *a, **k): return self
        def gte(self, *a, **k): return self
        def order(self, *a, **k): return self
        def limit(self, *a, **k): return self
        def execute(self): return type("R", (), {"data": self.data})()

    class DB:
        def table(self, name): return Q(rows if name == "health_events" else [])

    series = loader.load_series(DB(), "u", 90, 0)
    assert sorted(series["screen_hours"].values()) == [5.0, 6.0, 7.0]
    assert set(series["eye_comfort"].values()) == {3.0}


def test_an_eye_symptom_told_in_chat_reaches_the_eye_system():
    """chat words -> rule event name -> eye_snapshot: renaming a display label must not silently break the chain."""
    from chat_pipeline import analyze_turn, build_rule_events
    now = datetime(2026, 10, 15, 8, 0, tzinfo=timezone.utc)
    events = []
    for i, text in enumerate(("my eyes are burning after the laptop", "dry eyes again today", "meri aankh mein dard hai"), start=1):
        when = now - timedelta(days=i)
        turn = analyze_turn(text, [], now=when)
        for e in build_rule_events(turn, f"m{i}", now=when):
            events.append({"id": f"c{i}", "event_type": e["event_type"], "extraction_status": "confirmed", "extracted_data": e["extracted_data"]})
    names = sorted(e["extracted_data"]["name"] for e in events)
    assert names == ["dry eyes", "eye pain", "eye strain"]
    snapshot = eye_snapshot(events, now)
    assert snapshot["eye_symptom_days"] == 3
    assert assess_organ("eyes", snapshot).status == "no_major_risk_signal"   # three symptom days is one signal, not a verdict
