from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any


# Small-data friendly contextual bandit.
# This is a practical RL mechanism for Bubbles' current stage: 5 users, sparse
# feedback, and a strong need for deterministic safety constraints.
# It uses LinUCB-style scoring with a diagonal approximation so it has no
# external ML dependency.

FEATURES = [
    "sleep_low",
    "hydration_low",
    "activity_low",
    "stress_high",
    "mood_low",
    "symptom_active",
    "cycle_related",
    "goal_weight",
    "goal_fitness",
    "goal_hydration",
    "recent_engagement",
    "notification_fatigue",
]


@dataclass(frozen=True)
class Arm:
    key: str
    category: str
    text: str
    min_safety_level: str = "GREEN"


ARMS = [
    Arm("hydration_checkin", "hydration", "A gentle hydration check-in"),
    Arm("sleep_support", "sleep", "A sleep-support suggestion"),
    Arm("light_activity", "activity", "A light activity suggestion"),
    Arm("rest_recovery", "rest", "A rest/recovery suggestion"),
    Arm("food_balance", "food", "A nutrition/balance suggestion"),
    Arm("mood_checkin", "mood", "A short mood check-in"),
    Arm("cycle_checkin", "cycle", "A cycle check-in"),
    Arm("goal_checkin", "goal", "A personal-goal check-in"),
]


class ContextualBandit:
    POLICY_VERSION = "coco-bandit-v1"

    def __init__(self, alpha: float = 0.75, epsilon: float = 0.10) -> None:
        self.alpha = max(0.0, float(alpha))
        self.epsilon = max(0.0, min(0.20, float(epsilon)))

    @staticmethod
    def _arm_prior(arm_key: str, stats: dict[str, Any] | None) -> float:
        stats = stats or {}
        n = float(stats.get("impressions", 0) or 0)
        reward_sum = float(stats.get("reward_sum", 0) or 0)
        # Neutral prior with a small empirical-Bayes pull toward the observed rate.
        if n <= 0:
            return 0.0
        return reward_sum / max(n, 1.0)

    def score(
        self,
        context: dict[str, float],
        arm: Arm,
        stats: dict[str, Any] | None = None,
    ) -> float:
        # Interpretable hand-crafted contextual weights are used until enough
        # interaction data exists to fit a learned model.
        weights = {
            "hydration_checkin": {"hydration_low": 1.8, "recent_engagement": 0.3},
            "sleep_support": {"sleep_low": 1.8, "stress_high": 0.4, "recent_engagement": 0.2},
            "light_activity": {"activity_low": 1.4, "goal_fitness": 0.7, "recent_engagement": 0.2},
            "rest_recovery": {"sleep_low": 0.8, "stress_high": 1.2, "symptom_active": 0.7},
            "food_balance": {"goal_weight": 0.7, "recent_engagement": 0.2},
            "mood_checkin": {"mood_low": 1.6, "stress_high": 0.7},
            "cycle_checkin": {"cycle_related": 1.8, "symptom_active": 0.4},
            "goal_checkin": {"goal_hydration": 0.4, "goal_fitness": 0.4, "goal_weight": 0.4},
        }
        base = self._arm_prior(arm.key, stats)
        contextual = sum(
            float(context.get(feature, 0.0)) * weight
            for feature, weight in weights.get(arm.key, {}).items()
        )
        n = float((stats or {}).get("impressions", 0) or 0)
        uncertainty = self.alpha / math.sqrt(max(n, 1.0))
        return base + contextual + uncertainty

    def choose(
        self,
        context: dict[str, float],
        stats_by_arm: dict[str, dict[str, Any]] | None = None,
        allowed_arm_keys: set[str] | None = None,
    ) -> tuple[Arm, float]:
        stats_by_arm = stats_by_arm or {}
        allowed = allowed_arm_keys or {arm.key for arm in ARMS}
        candidates = [arm for arm in ARMS if arm.key in allowed]
        if not candidates:
            raise ValueError("No safe RL actions are available for this context.")

        # Exploration is explicitly capped and disabled when the user is fatigued.
        effective_epsilon = 0.0 if context.get("notification_fatigue", 0) >= 0.8 else self.epsilon

        scored = [
            (self.score(context, arm, stats_by_arm.get(arm.key)), arm)
            for arm in candidates
        ]
        scored.sort(key=lambda item: item[0], reverse=True)
        greedy_score, greedy_arm = scored[0]

        if random.random() < effective_epsilon:
            arm = random.choice(candidates)
            return arm, self.score(context, arm, stats_by_arm.get(arm.key))

        return greedy_arm, greedy_score


def build_context(
    *,
    sleep_hours: float | None = None,
    hydration_liters: float | None = None,
    activity_minutes: float | None = None,
    stress: float | None = None,
    mood: float | None = None,
    symptom_active: bool = False,
    cycle_related: bool = False,
    goal_weight: bool = False,
    goal_fitness: bool = False,
    goal_hydration: bool = False,
    recent_engagement: float = 0.0,
    notification_fatigue: float = 0.0,
) -> dict[str, float]:
    """Convert health signals into a bounded, auditable RL context vector."""
    return {
        "sleep_low": float(sleep_hours is not None and sleep_hours < 6),
        "hydration_low": float(hydration_liters is not None and hydration_liters < 1.5),
        "activity_low": float(activity_minutes is not None and activity_minutes < 20),
        "stress_high": float(stress is not None and stress >= 7),
        "mood_low": float(mood is not None and mood <= 3),
        "symptom_active": float(symptom_active),
        "cycle_related": float(cycle_related),
        "goal_weight": float(goal_weight),
        "goal_fitness": float(goal_fitness),
        "goal_hydration": float(goal_hydration),
        "recent_engagement": max(0.0, min(1.0, recent_engagement)),
        "notification_fatigue": max(0.0, min(1.0, notification_fatigue)),
    }


def reward_from_feedback(feedback: str) -> float:
    """Bounded reward for product-level feedback, not clinical outcomes."""
    return {
        "accepted": 1.0,
        "completed": 1.0,
        "helpful": 1.0,
        "dismissed": -0.25,
        "snoozed": -0.10,
        "ignored": -0.15,
        "not_helpful": -1.0,
    }.get(feedback.strip().lower(), 0.0)
