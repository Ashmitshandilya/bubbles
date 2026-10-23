"""The prompt budget (plan 5.4) and the suggestion chips (C7)."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from chat_pipeline import PROMPT_BUDGET, RECENT, assemble_context, fit_blocks, suggestions_for  # noqa: E402


def block(name, n, prio, ch="x"):
    return (name, ch * n, prio)


def test_everything_that_fits_is_kept_in_prompt_order():
    out = assemble_context([block("a", 10, 0, "a"), block("b", 10, 5, "b"), block("c", 10, 3, "c")], 1000)
    assert out == "a" * 10 + "\n\n" + "b" * 10 + "\n\n" + "c" * 10


def test_the_highest_priority_number_goes_first_and_priority_zero_never_goes():
    blocks = [block("safety", 100, 0), block("state", 100, 2), block("person", 100, 4), block("threads", 100, 5), block("values", 100, 7),
              block("metrics", 100, 8), block("assoc", 100, 9), block("evidence", 100, 11)]
    drop_order = []
    kept = set(n for n, _t, _p in blocks)
    for budget in range(900, 90, -102):
        now = set(fit_blocks(blocks, budget))
        drop_order += [n for n in kept - now]
        kept = now
    assert drop_order == ["evidence", "assoc", "metrics", "values", "threads", "person", "state"]
    assert "safety" in fit_blocks(blocks, 10), "priority 0 stays even when nothing fits"


def test_the_recent_conversation_is_trimmed_oldest_first_but_never_below_four_lines():
    lines = [f"User: message number {i} " + "x" * 80 for i in range(8)]
    recent = "RECENT CONVERSATION (oldest first):\n" + "\n".join(lines)
    blocks = [("safety", "s" * 100, 0), (RECENT, recent, 3), ("evidence", "e" * 500, 11)]
    kept = fit_blocks(blocks, 600)
    assert "evidence" not in kept and kept[RECENT].startswith("RECENT CONVERSATION (oldest first):\n")
    body = kept[RECENT].split("\n")[1:]
    assert len(body) < 8 and body[-1] == lines[-1] and "message number 0 " not in kept[RECENT]
    tiny = fit_blocks(blocks, 50)
    assert len(tiny[RECENT].split("\n")[1:]) == 4, "four lines stay however small the budget"


def test_a_block_is_never_cut_in_the_middle():
    kept = fit_blocks([block("a", 50, 0), block("b", 50, 6)], 70)
    assert kept == {"a": "a" * 0 + "x" * 50}


def test_empty_blocks_are_ignored_and_the_default_budget_is_the_plan_number():
    assert fit_blocks([("a", "", 0), ("b", "  ", 1)]) == {}
    assert PROMPT_BUDGET == 9000


def test_a_big_realistic_set_ends_under_the_budget():
    blocks = [block("safety", 600, 0), block("mind", 300, 0), block("setup_style", 500, 1), block("state", 400, 2), (RECENT, "RECENT CONVERSATION (oldest first):\n" + "\n".join("U: " + "x" * 340 for _ in range(8)), 3),
              block("personal", 3000, 2), block("person_model", 600, 4), block("open_threads", 300, 5), block("values", 1200, 7), block("metrics", 1500, 8),
              block("associations", 500, 9), block("nutrient_hint", 200, 10), block("evidence", 1200, 11)]
    total = sum(len(t) for _n, t, _p in blocks)
    assert total > PROMPT_BUDGET
    kept = fit_blocks(blocks)
    assert sum(len(t) + 2 for t in kept.values()) <= PROMPT_BUDGET
    assert {"safety", "mind", "setup_style", "state", "personal"} <= set(kept)


# ---- suggestion chips ----------------------------------------------------------------------------------------------------------------

def turn(text="hello", route="ai", topics=(), state="NO_REDFLAG", tier=0):
    return SimpleNamespace(text=text, route=route, topics=topics, safety=SimpleNamespace(state=state), harbor=SimpleNamespace(tier=tier))


def test_chips_follow_the_topic_and_are_at_most_three():
    chips = suggestions_for(turn("my gf is upset", topics=("relationship",)))
    assert 1 <= len(chips) <= 3 and "Help me work out what to say" in chips
    assert suggestions_for(turn("I feel low", topics=("mind",)))[0].startswith("What could help me feel calmer")
    assert suggestions_for(turn("slept 6 hours", route="daily_log"))[0] == "How did my week look?"
    assert len(suggestions_for(turn("tell me something"))) == 3


def test_a_hinglish_writer_gets_hinglish_chips():
    chips = suggestions_for(turn("mera boyfriend naraz hai aur mujhe kya karna chahiye", topics=("relationship",)))
    assert chips and chips[-1] == "Open in Heart-to-heart" and all(any(w in c.lower() for w in ("mujhe", "kya", "isse", "main", "chalo", "kaise", "heart")) for c in chips)
    assert suggestions_for(turn("मुझे बहुत थकान है", topics=("body",)))[0].startswith("Mujhe kis cheez")


def test_no_chips_on_safety_replies_a_consent_question_or_a_harbor_conversation():
    for route in ("emergency", "safe_harbor", "safety_followup", "clarification", "correction"):
        assert suggestions_for(turn(route=route)) == []
    assert suggestions_for(turn(), consent_required=True) == []
    assert suggestions_for(turn(state="URGENT")) == []
    assert suggestions_for(turn(tier=1)) == []
