from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from supabase_client import supabase
from .contextual_bandit import ARMS, ContextualBandit, build_context, reward_from_feedback
from .safety import allowed_rl_actions, normalize_safety_level


bandit = ContextualBandit()


def _load_stats(user_id: str) -> dict[str, dict[str, Any]]:
    try:
        result = (
            supabase.table("rl_arm_stats")
            .select("arm_key, impressions, reward_sum")
            .eq("user_id", user_id)
            .execute()
        )
        return {row["arm_key"]: row for row in (result.data or [])}
    except Exception as error:
        from logging_util import logger
        logger.error(
            component="RL_SERVICE",
            operation="load_stats",
            error=error,
            user_id=user_id,
            fallback_action="returning_empty_stats",
        )
        return {}


def _propensity(
    context: dict[str, float],
    allowed: set[str],
    stats: dict[str, dict[str, Any]],
    chosen_key: str,
) -> float:
    if context.get("notification_fatigue", 0.0) >= 0.8:
        return 1.0

    epsilon = bandit.epsilon
    candidates = [arm for arm in ARMS if arm.key in allowed]
    if not candidates:
        return 0.0

    best = max(
        candidates,
        key=lambda arm: bandit.score(context, arm, stats.get(arm.key)),
    )
    base = epsilon / len(candidates)
    return base + (1.0 - epsilon if chosen_key == best.key else 0.0)


def choose_recommendation(
    user_id: str,
    *,
    safety_level: str = "GREEN",
    context: dict[str, float] | None = None,
) -> dict[str, Any]:
    safety_level = normalize_safety_level(safety_level)
    context = context or build_context()
    stats = _load_stats(user_id)
    allowed = allowed_rl_actions(safety_level)

    arm, score = bandit.choose(
        context=context,
        stats_by_arm=stats,
        allowed_arm_keys=allowed,
    )

    propensity = _propensity(context, allowed, stats, arm.key)
    interaction_id = None

    try:
        stat = (
            supabase.table("rl_arm_stats")
            .select("id, impressions, reward_sum")
            .eq("user_id", user_id)
            .eq("arm_key", arm.key)
            .limit(1)
            .execute()
        )

        if stat.data:
            row = stat.data[0]
            supabase.table("rl_arm_stats").update({
                "impressions": int(row.get("impressions", 0)) + 1,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", row["id"]).eq("user_id", user_id).execute()
        else:
            supabase.table("rl_arm_stats").insert({
                "user_id": user_id,
                "arm_key": arm.key,
                "impressions": 1,
                "reward_sum": 0,
            }).execute()

        result = (
            supabase.table("rl_interactions")
            .insert({
                "user_id": user_id,
                "arm_key": arm.key,
                "context": context,
                "policy_score": score,
                "propensity": propensity,
                "safety_level": safety_level,
                "policy_version": ContextualBandit.POLICY_VERSION,
                "decision_mode": "contextual_bandit",
            })
            .select("id")
            .execute()
        )
        if result.data:
            interaction_id = result.data[0]["id"]
    except Exception as error:
        from logging_util import logger
        logger.error(
            component="RL_SERVICE",
            operation="log_interaction",
            error=error,
            user_id=user_id,
            context={"arm_key": arm.key},
            fallback_action="interaction_not_logged",
        )

    return {
        "interaction_id": interaction_id,
        "arm_key": arm.key,
        "category": arm.category,
        "text": arm.text,
        "score": round(score, 4),
        "propensity": round(propensity, 6),
        "context": context,
        "safety_level": safety_level,
        "policy_version": ContextualBandit.POLICY_VERSION,
        "decision_mode": "contextual_bandit",
    }


def record_feedback(
    user_id: str,
    interaction_id: str,
    feedback: str,
    reward: float | None = None,
) -> dict[str, Any]:
    feedback = feedback.strip().lower()
    computed_reward = reward_from_feedback(feedback) if reward is None else float(reward)
    computed_reward = max(-1.0, min(1.0, computed_reward))

    interaction = (
        supabase.table("rl_interactions")
        .select("id, arm_key, reward")
        .eq("id", interaction_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )

    if not interaction.data:
        raise ValueError("RL interaction not found")

    row = interaction.data[0]
    if row.get("reward") is not None:
        raise ValueError("Feedback has already been recorded for this interaction")

    arm_key = row["arm_key"]

    supabase.table("rl_interactions").update({
        "feedback": feedback,
        "reward": computed_reward,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", interaction_id).eq("user_id", user_id).is_("reward", "null").execute()

    existing = (
        supabase.table("rl_arm_stats")
        .select("id, reward_sum")
        .eq("user_id", user_id)
        .eq("arm_key", arm_key)
        .limit(1)
        .execute()
    )

    if existing.data:
        stats = existing.data[0]
        supabase.table("rl_arm_stats").update({
            "reward_sum": float(stats.get("reward_sum", 0.0)) + computed_reward,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", stats["id"]).eq("user_id", user_id).execute()

    return {
        "interaction_id": interaction_id,
        "arm_key": arm_key,
        "feedback": feedback,
        "reward": computed_reward,
    }
