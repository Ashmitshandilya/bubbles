"""The response rubric for Bubbles' replies: deterministic, no model. Each check is something a user (or a clinician) would object to."""
import pytest

from response_formatter import response_style_instruction
from response_quality import DOSE_NOTE, lint, scrub_doses

GOOD = (
    "That sounds draining. Poor sleep and headaches often feed each other, so it helps to look at both together.\n\n"
    "- Note when the headache starts and how long you slept the night before.\n"
    "- Drink some water and take a short break from screens.\n\n"
    "If it is sudden and severe, or comes with weakness or confusion, get urgent care now. Would you like me to check your sleep logs?"
)


def test_a_good_reply_passes_every_check():
    assert lint(GOOD) == []


@pytest.mark.parametrize("text,code", [
    ("You definitely have migraine, so rest.", "diagnosis_wording"),
    ("I can diagnose this: it is a sinus infection.", "diagnosis_wording"),
    ("This is certainly an iron problem.", "diagnosis_wording"),
    ("There is nothing to worry about, it will pass.", "false_reassurance"),
    ("You're fine, honestly.", "false_reassurance"),
    ("Take paracetamol 500 mg twice a day.", "dose_given"),
    ("word " * 230, "too_long"),
    ("Why? How? When? Where?", "too_many_questions"),
    ("", "empty"),
])
def test_each_rule_catches_its_own_failure(text, code):
    assert code in lint(text)


def test_doses_are_removed_and_replaced_by_a_plain_note():
    out, removed = scrub_doses("A cup of warm water can help. Take ibuprofen 400 mg every 6 hours with food. Rest well.")
    assert removed and "400" not in out and "ibuprofen" not in out and "warm water" in out and "Rest well" in out and out.endswith(DOSE_NOTE)


def test_ordinary_amounts_that_are_not_medicine_doses_are_kept():
    text = "Aim for about 2 litres of water, and adults need 7 to 9 hours of sleep. Up to 400 mg a day of caffeine is not harmful for most adults."
    out, removed = scrub_doses(text)
    assert not removed and out == text
    assert lint(text) == []


def test_bullets_that_only_held_a_dose_do_not_leave_empty_bullets():
    out, removed = scrub_doses("Things that may help:\n- Rest\n- Paracetamol 500 mg twice daily\n- Fluids")
    assert removed and "- \n" not in out and "- Rest" in out and "- Fluids" in out


def test_style_guide_keeps_the_safety_invariants_and_asks_for_craft():
    s = response_style_instruction().lower()
    for must in ("never diagnose", "never give a dose", "one question", "same language"):
        assert must in s


def test_fixed_log_replies_keep_their_meaning_in_every_wording():
    import chat_pipeline as cp
    assert len(cp._ONE_DAY) >= 4 and all(("day" in s.lower()) and ("pattern" in s.lower() or "compar" in s.lower()) for s in cp._ONE_DAY)
    assert all(("note" in s.lower()) and ("confirm" in s.lower() or "review" in s.lower() or "look over" in s.lower()) for s in cp._SAVED_NOTES)
    assert not any("diagnos" in s.lower() for s in cp._ONE_DAY + cp._SAVED_NOTES)


# --- friend voice: no authority names, soft conclusions, urgent call to action ---------------------------------------------

from response_quality import lint as _lint, strip_attribution


def test_style_prompt_has_no_authority_examples_and_bans_them():
    s = response_style_instruction()
    assert "NHS guidance says" not in s
    assert "never write the name of an organisation" in s
    assert "112" in s and "SOFT, NOT SCARY" in s


def test_lint_flags_authority_names_but_not_the_pronoun():
    assert "authority_citation" in _lint("NHS guidance says rest helps.")
    assert "authority_citation" in _lint("According to the WHO, sleep matters.")
    assert "authority_citation" in _lint("Studies show it helps.")
    assert "authority_citation" not in _lint("Rest and fluids usually help someone who is tired.")


def test_lint_flags_heavy_verdicts():
    assert "heavy_verdict" in _lint("This means you have diabetes.")
    assert "heavy_verdict" not in _lint("It could be low iron, worth a blood test if it keeps up.")


def test_strip_attribution_rewrites_only_a_leading_attribution():
    assert strip_attribution("NHS guidance says that sleep helps.") == "Sleep helps."
    assert strip_attribution("According to the WHO, water helps.") == "Water helps."
    assert strip_attribution("Studies show rest helps.") == "Rest helps."
    assert strip_attribution("Rest usually helps.") == "Rest usually helps."


def test_safety_copy_is_untouched_by_the_guard():
    from safety_engine import CRISIS_LINES
    assert strip_attribution(CRISIS_LINES) == CRISIS_LINES
