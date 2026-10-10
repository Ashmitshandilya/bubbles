"""Plain-language names for internal metric ids, for anything a person reads ("sleep", not "sleep hours"; "water intake", not "water ml")."""
import re

_PLAIN = {
    "sleep_hours": "sleep", "sleep_duration": "sleep", "sleep_quality": "sleep quality", "water_ml": "water intake", "hydration_ml": "water intake",
    "water": "water intake", "hydration": "water intake", "mood_score": "mood", "weight_kg": "weight", "heart_rate": "heart rate",
    "resting_hr": "resting heart rate", "activity_minutes": "activity", "calories": "food intake", "calories_kcal": "food intake",
}
_UNIT_SUFFIX = re.compile(r"_(ml|hours?|minutes?|mins?|kg|lbs?|bpm|score|count|level)$")


def plain_metric(name: str) -> str:
    key = str(name or "").strip().lower()
    return _PLAIN.get(key) or _UNIT_SUFFIX.sub("", key).replace("_", " ") or "this"
