import today_brief as tb


def test_priority_order():
    base = dict(uid="u", day="2026-10-24")
    full = dict(safety="AMBER", open_thread="How is the headache?", association="Sleep and mood moved together.",
                cycle_line="Period may start soon.", orbit_waiting=True, **base)
    order = ["safety", "thread", "pattern", "cycle", "orbit", "warm"]
    for kind in order:
        assert tb.pick(**full)["kind"] == kind
        key = {"safety": "safety", "thread": "open_thread", "pattern": "association", "cycle": "cycle_line", "orbit": "orbit_waiting"}.get(kind)
        if key:
            full[key] = False if key == "orbit_waiting" else None


def test_green_is_not_safety_and_line_is_stable_and_short():
    out = tb.pick(uid="u", day="d", safety="GREEN")
    assert out["kind"] == "warm" and out == tb.pick(uid="u", day="d")
    assert len(tb.WARM_LINES) == 30 and all(len(line.split()) <= tb.MAX_WORDS for line in tb.WARM_LINES)
    assert not any("welcome back" in line.lower() or "—" in line for line in tb.WARM_LINES)


def test_long_insight_is_cut():
    long = " ".join(["word"] * 60)
    assert len(tb.pick(uid="u", day="d", association=long)["text"].split()) <= tb.MAX_WORDS


def test_a_pattern_becomes_one_friendly_sentence():
    raw = "On days after you slept longer, your logged mood tended to be higher (60 days logged). Only days you logged are compared. An association in their logs."
    out = tb.pick(uid="u", day="d", association=raw)
    assert out["kind"] == "pattern"
    assert out["text"] == "On days after you slept longer, your logged mood tended to be higher. That's from your own logs, not a cause."
    assert "(" not in out["text"] and "their" not in out["text"]
