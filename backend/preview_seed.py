"""DEV ONLY. Seeds the preview database through the real endpoints: about 60 days of believable SYNTHETIC history for a demo person.

Real patterns are planted on purpose (longer sleep goes with a better mood; activity goes with better sleep the next night) so the
association engine has something true to find. Nothing here is real data.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

DAYS = 60
H = {"Authorization": "Bearer preview"}


def seed(app, db, user_id: str) -> dict:
    rng = random.Random(7)
    client = TestClient(app, raise_server_exceptions=False)
    today = datetime.now(timezone.utc).date()
    counts: dict[str, int] = {}

    def post(path: str, body: dict, key: str) -> None:
        r = client.post(path, json=body, headers=H)
        if r.status_code < 300:
            counts[key] = counts.get(key, 0) + 1

    db.table("profiles").insert({"id": user_id, "display_name": "Riya", "date_of_birth": "1999-03-14", "height_cm": 162, "gender": "female",
                                 "timezone": "Asia/Kolkata", "created_at": (today - timedelta(days=75)).isoformat()}).execute()

    meals = [("Poha with peanuts and a cup of chai", 320, "breakfast"), ("Dal, 2 rotis, sabzi and curd", 520, "lunch"), ("Idli with sambar", 300, "breakfast"),
             ("Paneer bhurji and a roti", 410, "dinner"), ("Rajma chawal", 560, "lunch"), ("Khichdi with ghee", 430, "dinner"), ("Fruit and nuts", 180, "snack")]
    for i in range(DAYS, 0, -1):
        d = today - timedelta(days=i)
        iso = d.isoformat()
        active = rng.random() < 0.55
        minutes = rng.choice([20, 30, 40, 45, 60]) if active else 0
        # planted pattern 1: activity yesterday goes with better sleep tonight
        prev_active = (today - timedelta(days=i + 1)).toordinal() % 2 == 0
        hours = round(max(4.5, min(9.2, 6.4 + (0.9 if prev_active else -0.2) + rng.uniform(-0.8, 0.8))), 1)
        quality = max(1, min(10, round(4 + (hours - 6) * 1.1 + rng.uniform(-1, 1))))
        # planted pattern 2: longer sleep goes with a better mood
        mood = max(1, min(10, round(2.5 + hours * 0.75 + rng.uniform(-1.2, 1.2))))
        post("/health/sleep", {"date": iso, "duration": hours, "quality": quality}, "sleep")
        post("/health/mood", {"date": iso, "mood": mood}, "mood")
        if minutes:
            post("/health/activity", {"date": iso, "type": rng.choice(["Walk", "Yoga", "Cycling", "Dance workout"]), "duration": minutes, "intensity": "moderate"}, "activity")
        for _ in range(rng.randint(2, 5)):
            post("/health/hydration", {"date": iso, "volume": rng.choice([250, 300, 500]), "type": "water"}, "hydration")
        for desc, kcal, meal in rng.sample(meals, 3):
            post("/health/nutrition", {"date": iso, "description": desc, "calories": kcal, "meal_type": meal}, "nutrition")
        if i % 5 == 0:
            post("/health/weight", {"date": iso, "weight": round(129 + rng.uniform(-1.2, 1.2), 1)}, "weight")
        if i % 4 == 0:
            post("/health/vitals", {"date": iso, "heart_rate": rng.randint(66, 78), "blood_pressure": "112/72"}, "vitals")
        if rng.random() < 0.12:
            post("/health/symptoms", {"date": iso, "symptom": "Headache", "severity": rng.randint(2, 5)}, "symptoms")

    # long screen days with tired eyes, so the eyes show a status on the body map
    for i in (1, 2, 4, 6):
        post("/health/eyes", {"date": (today - timedelta(days=i)).isoformat(), "screen_hours": 8, "comfort": 2, "symptoms": ["dry", "strained"]}, "eyes")

    # a regular 28 day cycle, today is mid-cycle (day 14)
    for k in range(7):
        start = today - timedelta(days=13 + 28 * k)
        post("/health/cycle", {"date": start.isoformat(), "phase": "period"}, "cycle")

    post("/health/medications", {"name": "Folic acid", "dosage": "as prescribed", "reason": "Supplement"}, "medications")
    post("/health/conditions", {"condition_name": "Mild iron deficiency", "status": "Managed", "diagnosed_date": "2025-11-02"}, "conditions")
    post("/health/allergies", {"allergen": "Penicillin", "reaction_type": "Rash", "severity": "Moderate"}, "allergies")
    post("/health/labs", {"test_name": "Ferritin", "value": "21", "unit": "ng/mL", "reference_range": "15-150", "test_date": (today - timedelta(days=30)).isoformat()}, "labs")
    post("/health/labs", {"test_name": "TSH", "value": "2.4", "unit": "mIU/L", "reference_range": "0.4-4.0", "test_date": (today - timedelta(days=30)).isoformat()}, "labs")
    post("/health/visits", {"visit_date": (today - timedelta(days=21)).isoformat(), "doctor_name": "Dr. Mehta", "specialty": "Gynaecology", "reason": "Routine check"}, "visits")

    # a short conversation, written straight into the chat tables
    now = datetime.now(timezone.utc)
    conv = "11111111-1111-1111-1111-111111111111"
    db.table("chat_conversations").insert({"id": conv, "user_id": user_id, "title": "Headaches and sleep", "created_at": (now - timedelta(hours=3)).isoformat(),
                                           "updated_at": (now - timedelta(hours=3)).isoformat()}).execute()
    thread = [("user", "I have had headaches this week and I'm sleeping badly."),
              ("bubbles", "That sounds draining. Poor sleep and headaches often feed each other, so it helps to look at both together.\n\nIn your logs, the nights you slept longer were followed by better moods. Want me to line up your headache days with your sleep?")]
    for n, (role, text) in enumerate(thread):
        db.table("chat_messages").insert({"id": f"22222222-2222-2222-2222-22222222220{n}", "conversation_id": conv, "user_id": user_id, "role": role, "content": text,
                                          "metadata": {}, "created_at": (now - timedelta(hours=3, minutes=-n)).isoformat()}).execute()
    counts["chat_messages"] = len(thread)
    # the demo person has finished first-run setup (a female body), so every screen is reachable in the preview
    client.put("/onboarding/answers", json={"answers": {"preferred_name": "Riya", "birth_date": "1999-03-14", "body": "female", "language": "english",
                                                         "goals": ["sleep", "stress_mood"], "conditions": ["none"], "tone": "gentle_warm", "periods": "regular"}}, headers=H)
    if client.post("/onboarding/complete", headers=H).status_code < 300:
        counts["onboarding"] = 1
    return counts
