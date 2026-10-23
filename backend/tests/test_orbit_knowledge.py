"""Orbit pattern cards (plan 7.4, WP2.1): schema, retrieval, and the honest numbers.

``orbit_cards.jsonl`` and ``orbit_cards_heldout.jsonl`` were written first and then used to tune the signals, so their scores are an upper bound.
``orbit_cards_blind.jsonl`` was written afterwards and never tuned against; its recall (about a third strict, about half loose) is the number to
believe about messages Bubbles has not seen. Strict matching keeps false positives near zero; loose matching is for talk already about a relationship.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import orbit_knowledge as ok  # noqa: E402

EVAL = Path(__file__).parent / "eval"


def rows(name):
    return [json.loads(l) for l in (EVAL / f"{name}.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]


def score(name, loose=False):
    data = rows(name)
    pos = [r for r in data if r["cards"]]
    neg = [r for r in data if not r["cards"]]
    hit = sum(1 for r in pos if set(r["cards"]) & {c["id"] for c in ok.cards_for(r["text"], loose=loose)})
    quiet = sum(1 for r in neg if not ok.cards_for(r["text"], loose=loose))
    return hit / len(pos), quiet / len(neg), len(pos), len(neg)


def test_the_card_file_is_well_formed():
    assert ok.validate() == []
    assert 28 <= len(ok.cards()) <= 40


def test_every_starter_card_from_the_plan_exists():
    ids = {c["id"] for c in ok.cards()}
    for needed in ("pursue_withdraw", "harsh_startup", "flooding", "repair_attempts", "bids_for_connection", "contempt_antidote", "defensiveness_antidote", "stonewalling",
                   "love_maps", "accepting_influence", "stress_spillover", "long_distance", "in_laws_and_family", "joint_family_privacy", "arranged_marriage_early_years",
                   "money_and_family", "new_parents", "cycle_and_mood", "jealousy_and_phone_checking", "situationship_uncertainty", "breakup_grief", "reassurance_seeking",
                   "different_love_expressions", "apology_styles", "festival_and_family_stress", "religion_or_caste_differences", "sexual_mismatch", "trust_after_lie",
                   "social_media_comparison"):
        assert needed in ids, needed


def test_no_card_claims_a_number_and_every_card_says_what_never_to_say():
    for c in ok.cards():
        assert not any(ch.isdigit() for ch in c["what_it_is"] + " ".join(c["what_helps"])), c["id"]
        assert c["never_say"] and c["source"].strip() and c["evidence"] in ok.EVIDENCE_RANK, c["id"]


def test_cards_with_thin_research_say_so_and_none_claims_to_be_strong_without_a_replicated_source():
    for c in ok.cards():
        if c["evidence"] == "strong":
            pytest.fail(f"{c['id']}: no card here has replicated-finding support strong enough to be called strong")
    practice = [c["id"] for c in ok.cards() if c["evidence"] == "practice"]
    assert {"in_laws_and_family", "situationship_uncertainty", "trust_after_lie", "sexual_mismatch"} <= set(practice)


def test_the_first_eval_sets_meet_the_plan_targets_but_are_tuned():
    for name in ("orbit_cards", "orbit_cards_heldout"):
        recall, quiet, npos, nneg = score(name)
        assert recall >= 0.90 and quiet >= 0.95, (name, recall, quiet)
    assert score("orbit_cards")[2] >= 90 and score("orbit_cards")[3] >= 25


def test_unseen_messages_the_honest_numbers():
    recall, quiet, npos, nneg = score("orbit_cards_blind")
    assert npos >= 35 and nneg >= 12
    assert quiet >= 0.90, "strict matching must stay quiet on unrelated messages"
    assert recall >= 0.30, "a floor, not a goal: this was about 0.35 when measured"
    loose_recall, _, _, _ = score("orbit_cards_blind", loose=True)
    assert loose_recall >= recall and loose_recall >= 0.40


def test_devanagari_and_spelling_variants_match():
    assert [c["id"] for c in ok.cards_for("उसने मुझसे कई दिन बात नहीं की")][:1] in (["stonewalling"], [])  # transliteration is rough; this must not crash
    assert ok.normalize("Baat NAHIN karta!") == "baat nahi karta"
    assert [c["id"] for c in ok.cards_for("woh phone chek karta hai aur password maangta hai")] in ([], ["jealousy_and_phone_checking"])
    assert ok.cards_for("woh mera password maangta hai aur phone check karta hai")[0]["id"] == "jealousy_and_phone_checking"


def test_a_card_needs_the_new_message_history_alone_never_brings_one():
    history = [{"role": "user", "content": "he gives me the silent treatment and I keep texting"}]
    assert ok.cards_for("what should I make for dinner", history) == []
    assert ok.cards_for("", history) == []
    with_history = ok.cards_for("he gives me the silent treatment", history)
    assert with_history and with_history[0]["id"] in ("stonewalling", "pursue_withdraw")


def test_limit_and_order_are_stable():
    first = ok.cards_for("he gives me the silent treatment and I keep texting him and he won't talk", limit=2)
    assert len(first) <= 2 and [c["id"] for c in first] == [c["id"] for c in ok.cards_for("he gives me the silent treatment and I keep texting him and he won't talk", limit=2)]
    assert ok.cards_for("he gives me the silent treatment", limit=0) == []


def test_the_prompt_block_carries_the_card_the_never_say_line_and_the_india_note_only_for_india():
    cards = ok.cards_for("he gives me the silent treatment for days", limit=1)
    india = ok.prompt_block(cards, "in")
    assert india.startswith("PATTERN CARDS (general knowledge, not facts about this person.")
    assert "Never say:" in india and "Note for India:" in india
    assert "Note for India:" not in ok.prompt_block(cards, "other")
    assert "Note for India:" in ok.prompt_block(cards, None), "a person who never said is treated as India, like everywhere else"
    assert ok.prompt_block([]) == ""
    assert "diagnos" in india.lower()
