"""Backward-compatible food lookup (used by chat daily-log estimates and /nutrition/food endpoints).

The reference table now lives in food_data.py / food_db.py; this module keeps the original small API and result shape.
"""
import food_db
from food_data import FOODS


def _legacy(food, confidence="reference"):
    return {"name": food["name"], "aliases": food.get("aliases", []), "serving": food["serving"], "calories": food["kcal"],
            "protein_g": food["protein_g"], "carbs_g": food["carbs_g"], "fat_g": food["fat_g"], "fibre_g": food["fibre_g"],
            "source": "Bubbles reference estimate", "confidence": confidence}


def lookup_food(query):
    food = food_db.find_food(query or "")
    return _legacy(food) if food else None


def search_foods(query, limit=10):
    if not (query or "").strip():
        return []
    return [{k: v for k, v in _legacy(f).items() if k != "confidence"} for f in food_db.search(query, max(1, min(limit, 20)))]
