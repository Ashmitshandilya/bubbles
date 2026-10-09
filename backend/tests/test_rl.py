from rl.contextual_bandit import build_context, reward_from_feedback, ContextualBandit, ARMS
from rl.safety import allowed_rl_actions


def test_context_is_bounded():
    ctx = build_context(stress=100, mood=-5, recent_engagement=9, notification_fatigue=-1)
    assert ctx["stress_high"] == 1.0
    assert ctx["mood_low"] == 1.0
    assert ctx["recent_engagement"] == 1.0
    assert ctx["notification_fatigue"] == 0.0


def test_elevated_safety_restricts_actions():
    assert allowed_rl_actions("RED") == {"rest_recovery", "mood_checkin"}
    assert allowed_rl_actions("ORANGE") == {"rest_recovery", "mood_checkin"}


def test_rewards_are_bounded_and_known():
    assert reward_from_feedback("helpful") == 1.0
    assert reward_from_feedback("not_helpful") == -1.0
    assert reward_from_feedback("unknown") == 0.0


def test_bandit_only_selects_allowlisted_action():
    bandit = ContextualBandit(epsilon=0.0)
    arm, _ = bandit.choose(build_context(hydration_liters=0.5), allowed_arm_keys={"hydration_checkin"})
    assert arm.key == "hydration_checkin"
