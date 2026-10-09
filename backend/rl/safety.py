from __future__ import annotations

"""Deterministic safety boundary for Bubbles' personalization policy."""

FORBIDDEN_RL_ACTIONS = {
    "diagnose",
    "treatment",
    "medication_change",
    "medication_dose",
    "emergency_triage",
    "pregnancy_diagnosis",
    "lab_interpretation_action",
    "doctor_replacement",
}

# Actions that are safe enough for a personalization experiment. The RL layer
# may rank these; it may never invent a new action outside this allowlist.
LOW_RISK_ACTIONS = {
    "hydration_checkin",
    "sleep_support",
    "light_activity",
    "rest_recovery",
    "food_balance",
    "mood_checkin",
    "cycle_checkin",
    "goal_checkin",
}

# In elevated-risk states, personalization should become conservative. The
# safety engine remains authoritative; these are only supportive actions.
ELEVATED_RISK_ACTIONS = {
    "rest_recovery",
    "mood_checkin",
}


def normalize_safety_level(level: str | None) -> str:
    value = (level or "GREEN").strip().upper()
    return value if value in {"GREEN", "YELLOW", "ORANGE", "RED"} else "ORANGE"


def allowed_rl_actions(safety_level: str) -> set[str]:
    level = normalize_safety_level(safety_level)
    if level in {"ORANGE", "RED"}:
        return set(ELEVATED_RISK_ACTIONS)
    return set(LOW_RISK_ACTIONS)


def filter_rl_actions(actions: list[dict], safety_level: str) -> list[dict]:
    allowed = allowed_rl_actions(safety_level)
    return [
        action
        for action in actions
        if action.get("arm_key") in allowed
        and action.get("action_type") not in FORBIDDEN_RL_ACTIONS
    ]
