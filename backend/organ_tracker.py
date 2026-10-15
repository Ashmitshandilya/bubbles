"""BUBBLES Organ Tracker foundation.

This module intentionally estimates *risk/health indicators*, not organ diagnoses.
It converts available user data into transparent, bounded scores and evidence trails.
Clinical findings (labs, imaging, clinician diagnoses) outrank lifestyle proxies.

No score may claim that an organ is structurally healthy/damaged when direct evidence
is absent. Missing data lowers confidence rather than being treated as normal.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


ORGANS = (
    "brain",
    "eyes",
    "heart",
    "lungs",
    "liver",
    "kidneys",
    "pancreas",
    "digestive_system",
    "reproductive_system",
    "musculoskeletal_system",
)

# Risk multipliers are deliberately conservative product weights, not clinical odds ratios.
# They rank attention areas only. Evidence-backed clinical rules belong in the evidence layer.
RISK_FACTORS = {
    "smoking": {"lungs": 0.30, "heart": 0.22, "brain": 0.16, "kidneys": 0.08, "eyes": 0.06},
    "nicotine": {"lungs": 0.18, "heart": 0.16, "brain": 0.12},
    "poor_sleep": {"brain": 0.16, "heart": 0.12, "pancreas": 0.08},
    "low_activity": {"heart": 0.12, "pancreas": 0.10, "musculoskeletal_system": 0.10},
    "high_salt_pattern": {"heart": 0.12, "kidneys": 0.08},
    "high_sugar_pattern": {"pancreas": 0.14, "liver": 0.10, "heart": 0.06},
    "highly_processed_diet": {"heart": 0.08, "liver": 0.08, "pancreas": 0.08},
    "overweight_or_obesity": {"heart": 0.12, "liver": 0.16, "pancreas": 0.14},
    "persistent_high_bp": {"heart": 0.22, "brain": 0.20, "kidneys": 0.16, "eyes": 0.12},
    "persistent_high_glucose": {"pancreas": 0.20, "kidneys": 0.18, "heart": 0.14, "brain": 0.08, "eyes": 0.14},
    "alcohol_excess": {"liver": 0.25, "heart": 0.08, "brain": 0.08, "pancreas": 0.14},
    # Eyes: product weights awaiting clinician review (docs/clinical). 6 h of daily screen time and 3 days of eye symptoms
    # in 14 days are product thresholds, not clinical cut-offs.
    "high_screen_time": {"eyes": 0.14},
    "frequent_eye_symptoms": {"eyes": 0.16},
}

# These are product-level evidence weights, not diagnostic thresholds.
DIRECT_EVIDENCE_FIELDS = {
    "brain": ("neurologic_diagnosis", "brain_imaging", "clinician_neurologic_finding"),
    # a date of the last eye exam is NOT evidence of eye health, so it is not listed here (it feeds the Care checklist instead)
    "eyes": ("vision_prescription", "eye_diagnosis", "eye_pressure"),
    "heart": ("blood_pressure", "lipids", "ecg", "cardiac_diagnosis"),
    "lungs": ("spirometry", "oxygen_saturation", "lung_imaging", "respiratory_diagnosis"),
    "liver": ("alt", "ast", "bilirubin", "alp", "liver_imaging", "liver_diagnosis"),
    "kidneys": ("creatinine", "egfr", "urine_albumin", "kidney_imaging", "kidney_diagnosis"),
    "pancreas": ("glucose", "hba1c", "pancreatic_diagnosis"),
    "digestive_system": ("gi_diagnosis", "gi_imaging", "endoscopy"),
    "reproductive_system": ("reproductive_diagnosis", "pelvic_imaging", "reproductive_labs"),
    "musculoskeletal_system": ("bone_density", "musculoskeletal_imaging", "musculoskeletal_diagnosis"),
}


@dataclass
class OrganSignal:
    factor: str
    direction: str  # "risk", "protective", "direct"
    weight: float
    source_ids: list[str] = field(default_factory=list)
    explanation: str = ""


@dataclass
class OrganAssessment:
    organ: str
    score: float | None
    status: str
    confidence: float
    data_completeness: float
    signals: list[OrganSignal]
    limitations: list[str]
    recommended_actions: list[str]


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _truthy(snapshot: dict[str, Any], key: str) -> bool:
    """Return True only for an explicit positive signal.

    Unknown/missing/negative values must never become risk signals merely because
    they are non-empty strings.
    """
    value = snapshot.get(key)
    if isinstance(value, str):
        return value.strip().lower() in {"yes", "true", "current", "daily", "frequent"}
    return value is True


def _source_ids_for(source_ids: Any, factor: str) -> list[str]:
    """Normalize provenance IDs without turning malformed strings into characters."""
    if not isinstance(source_ids, dict):
        return []
    value = source_ids.get(factor, [])
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if item not in (None, "")]
    return []


def _factor_present(snapshot: dict[str, Any], factor: str) -> bool:
    if factor == "smoking":
        return snapshot.get("smoking_status") in {"current", "daily", "frequent"}
    if factor == "nicotine":
        return snapshot.get("nicotine_use") in {"current", "daily", "frequent"}
    if factor == "poor_sleep":
        hours = snapshot.get("sleep_hours_avg")
        return isinstance(hours, (int, float)) and hours < 7
    if factor == "low_activity":
        mins = snapshot.get("activity_minutes_week")
        return isinstance(mins, (int, float)) and mins < 150
    if factor == "high_salt_pattern":
        return _truthy(snapshot, "high_salt_pattern")
    if factor == "high_sugar_pattern":
        return _truthy(snapshot, "high_sugar_pattern")
    if factor == "highly_processed_diet":
        return _truthy(snapshot, "highly_processed_diet")
    if factor == "overweight_or_obesity":
        bmi = snapshot.get("bmi")
        return isinstance(bmi, (int, float)) and bmi >= 25
    if factor == "persistent_high_bp":
        return _truthy(snapshot, "persistent_high_bp")
    if factor == "persistent_high_glucose":
        return _truthy(snapshot, "persistent_high_glucose")
    if factor == "alcohol_excess":
        return _truthy(snapshot, "alcohol_excess")
    if factor == "high_screen_time":
        hours = snapshot.get("screen_hours_avg")
        return isinstance(hours, (int, float)) and not isinstance(hours, bool) and hours >= 6
    if factor == "frequent_eye_symptoms":
        days = snapshot.get("eye_symptom_days")
        return isinstance(days, (int, float)) and not isinstance(days, bool) and days >= 3
    return False


def assess_organ(organ: str, snapshot: dict[str, Any]) -> OrganAssessment:
    if organ not in ORGANS:
        raise ValueError(f"Unsupported organ/system: {organ}")

    signals: list[OrganSignal] = []
    total_risk = 0.0
    source_ids = snapshot.get("source_ids", {}) or {}

    for factor, organ_weights in RISK_FACTORS.items():
        weight = organ_weights.get(organ)
        if weight is None or not _factor_present(snapshot, factor):
            continue
        ids = _source_ids_for(source_ids, factor)
        signals.append(
            OrganSignal(
                factor=factor,
                direction="risk",
                weight=weight,
                source_ids=ids,
                explanation=f"Available data contains the modifiable factor '{factor}'.",
            )
        )
        total_risk += weight

    direct_fields = DIRECT_EVIDENCE_FIELDS.get(organ, ())
    direct_count = sum(1 for field in direct_fields if snapshot.get(field) not in (None, ""))
    completeness = _clamp(direct_count / max(len(direct_fields), 1))

    # Direct evidence does not automatically mean good/bad. It increases confidence
    # that the assessment is grounded in clinical data; interpretation is delegated to
    # a future validated evidence/rules layer.
    if direct_count:
        signals.append(
            OrganSignal(
                factor="direct_clinical_data",
                direction="direct",
                weight=min(0.25, 0.05 * direct_count),
                source_ids=_source_ids_for(source_ids, "direct_clinical_data"),
                explanation="Clinical measurements or records are available for this organ/system.",
            )
        )

    # A score is only meaningful when there is enough evidence to establish
    # an assessment. Never turn "unknown" into an apparently healthy 100.
    if not signals:
        score = None
        status = "unknown"
        confidence = 0.0
    else:
        # This is a bounded *risk-context indicator*, not an organ-health score.
        # Higher values mean more accumulated product-level risk signals.
        score = round(100 * _clamp(total_risk), 1)
        if total_risk >= 0.45:
            status = "needs_attention"
        elif total_risk >= 0.25:
            status = "watch"
        else:
            status = "no_major_risk_signal"

        confidence = _clamp(0.15 + 0.60 * completeness + 0.25 * min(len(signals), 3) / 3)
    limitations = [
        "This is a bounded risk-context indicator, not a diagnosis or measurement of structural organ health. It is not a percentage of organ health.",
    ]
    if completeness < 0.5:
        limitations.append("Direct clinical data are limited; absence of a signal does not mean the organ is healthy.")

    actions = _actions_for(organ, signals)
    return OrganAssessment(
        organ=organ,
        score=score,
        status=status,
        confidence=round(confidence, 3),
        data_completeness=round(completeness, 3),
        signals=signals,
        limitations=limitations,
        recommended_actions=actions,
    )


def _actions_for(organ: str, signals: list[OrganSignal]) -> list[str]:
    factors = {s.factor for s in signals if s.direction == "risk"}
    actions: list[str] = []
    if "smoking" in factors or "nicotine" in factors:
        actions.append("Prioritize reducing and ultimately stopping tobacco/nicotine exposure.")
    if "poor_sleep" in factors:
        actions.append("Work toward a consistent sleep schedule and adequate sleep duration.")
    if "low_activity" in factors:
        actions.append("Build activity gradually toward an appropriate weekly activity target.")
    if "high_salt_pattern" in factors or "high_sugar_pattern" in factors or "highly_processed_diet" in factors:
        actions.append("Improve diet quality with more minimally processed foods and appropriate fruit, vegetables, fibre and protein.")
    if "persistent_high_bp" in factors or "persistent_high_glucose" in factors:
        actions.append("Discuss persistent abnormal measurements with a clinician rather than relying on the app score.")
    if organ == "eyes":
        if "high_screen_time" in factors or "frequent_eye_symptoms" in factors:
            actions.append("Short screen breaks, such as looking at something about 6 metres away for 20 seconds every 20 minutes, are a common habit for tired eyes. If symptoms keep coming back, an eye check is worth considering.")
        if "persistent_high_bp" in factors or "persistent_high_glucose" in factors:
            actions.append("High blood pressure and high blood sugar can affect the eyes, so it is worth asking your doctor how often you should have an eye exam.")
    if not actions:
        actions.append("Continue collecting reliable health data; improve the assessment when measurements or clinical records become available.")
    return actions


def assess_all(snapshot: dict[str, Any]) -> list[OrganAssessment]:
    return [assess_organ(organ, snapshot) for organ in ORGANS]


def explain_interaction(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    """Return transparent cross-factor relationships for the UI.

    These are associations/risk pathways, never claims that one lifestyle event caused
    a structural organ change. The UI should label them as evidence-backed risk links.
    """
    interactions: list[dict[str, Any]] = []
    if _factor_present(snapshot, "smoking") and _factor_present(snapshot, "poor_sleep"):
        interactions.append({
            "factors": ["smoking", "poor_sleep"],
            "systems": ["brain", "heart", "lungs"],
            "type": "combined_risk_context",
            "message": "Smoking and poor sleep can both contribute to cardiovascular and brain-health risk; the combined state should increase monitoring priority, not be interpreted as proof of organ damage.",
        })
    if _factor_present(snapshot, "smoking") and _factor_present(snapshot, "persistent_high_bp"):
        interactions.append({
            "factors": ["smoking", "persistent_high_bp"],
            "systems": ["heart", "brain", "kidneys"],
            "type": "combined_risk_context",
            "message": "Smoking and persistent high blood pressure are important vascular risk factors and should raise the priority of cardiovascular and stroke-risk review.",
        })
    if _factor_present(snapshot, "persistent_high_glucose") and _factor_present(snapshot, "overweight_or_obesity"):
        interactions.append({
            "factors": ["persistent_high_glucose", "overweight_or_obesity"],
            "systems": ["pancreas", "heart", "kidneys", "liver"],
            "type": "metabolic_risk_context",
            "message": "Abnormal glucose and excess weight can cluster with metabolic and cardiovascular risk and should be interpreted alongside actual measurements and clinician assessment.",
        })
    return interactions
