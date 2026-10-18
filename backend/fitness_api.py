"""Fitness API: body profile, food search / whole-meal parsing / food log, targets, diet plan, workouts, strict Transformation mode.

All routes are authenticated and owner-scoped. Data is stored as JSON documents (doc_store) or in the existing tracker
domains (health_logs), so no Supabase schema change is needed. Targets always come from plan_engine; nothing here computes
calories itself. Every number that is an estimate is labelled as one.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

from fastapi import APIRouter, Header, HTTPException, Query, Request
from starlette.concurrency import run_in_threadpool

import clinical_constants as K
import condition_rules
import diet_planner
import doc_store
import exercise_planner
import food_db
import health_logs
import hydration_engine
import meal_composer
import open_food_facts
import nutrition_calc as N
import plan_engine
import transformation as T
from calc_core import local_today
from wellness_common import request_tz
from event_filters import is_live_positive
from exercise_library import LIB

LBS_PER_KG = health_logs.LBS_PER_KG
DIET_STYLES = {"", "none", "vegetarian", "vegan", "eggetarian", "jain", "non-vegetarian", "halal"}
LIST_FIELDS = ("cuisines", "likes", "dislikes", "equipment", "injuries", "extra_conditions", "extra_allergies", "extra_medications")
BOOL_FIELDS = ("pregnant", "breastfeeding", "trying_to_conceive", "menstruating", "resistance_training", "eating_disorder_history", "postpartum")
SCOFF_REQUIRED = len(K.SCOFF_QUESTIONS)


def _bad(msg: str, status: int = 422) -> HTTPException:
    return HTTPException(status_code=status, detail=msg)


async def _json(request: Request) -> dict:
    try:
        body = await request.json()
    except (ValueError, RecursionError):
        raise _bad("Request body must be valid JSON")
    if not isinstance(body, dict):
        raise _bad("Request body must be a JSON object")
    return body


def _day(value: Any = None) -> str:
    if not value:
        return local_today().isoformat()
    try:
        d = date.fromisoformat(str(value)[:10])
    except ValueError:
        raise _bad("date must look like 2026-03-01")
    if not 1900 <= d.year <= 2100:
        raise _bad("date is out of range")
    return d.isoformat()


def _log_day(value: Any = None) -> str:
    """A calendar day for a log entry: from a year ago to tomorrow (keeps one user from creating documents for any date)."""
    day = _day(value)
    today = local_today()
    if not today - timedelta(days=366) <= date.fromisoformat(day) <= today + timedelta(days=1):
        raise _bad("That date is too far from today to log")
    return day


def _strings(value: Any, label: str, limit: int = 40) -> list[str]:
    if value in (None, ""):
        return []
    if not isinstance(value, list) or len(value) > limit:
        raise _bad(f"{label} must be a short list")
    out = []
    for v in value:
        if not isinstance(v, str):
            raise _bad(f"{label} must contain text")
        v = v.replace(chr(0), "").strip()[:60]
        if v:
            out.append(v)
    return list(dict.fromkeys(out))


def _num(body: dict, key: str, lo: float, hi: float) -> float | None:
    v = body.get(key)
    if v in (None, ""):
        return None
    if isinstance(v, bool):
        raise _bad(f"{key} must be a number")
    try:
        n = float(v)
    except (TypeError, ValueError, OverflowError):
        raise _bad(f"{key} must be a number")
    if n != n or not lo <= n <= hi:
        raise _bad(f"{key} must be between {lo:g} and {hi:g}")
    return n


def clean_profile(body: dict, current: dict | None = None) -> dict:
    """Validate a profile update (partial). Returns the merged profile."""
    out = dict(current or {})
    if "birth_date" in body:
        v = body["birth_date"]
        if v in (None, ""):
            out.pop("birth_date", None)
        else:
            age = N.age_from_birth(v)
            if age is None or not K.MIN_PLAUSIBLE["age"][0] <= age <= K.MIN_PLAUSIBLE["age"][1]:
                raise _bad("birth_date is not a plausible date")
            out["birth_date"] = str(v)[:10]
    for key, (lo, hi) in (("height_cm", K.MIN_PLAUSIBLE["height_cm"]), ("weight_kg", K.MIN_PLAUSIBLE["weight_kg"]), ("target_weight_kg", K.MIN_PLAUSIBLE["weight_kg"])):
        if key in body:
            n = _num(body, key, lo, hi)
            out.pop(key, None) if n is None else out.__setitem__(key, round(n, 1))
    if "formula_basis" in body:
        if not isinstance(body["formula_basis"], str) or body["formula_basis"] not in K.FORMULA_BASES:
            raise _bad("formula_basis must be male, female or average")
        out["formula_basis"] = body["formula_basis"]
    if "activity_level" in body:
        if not isinstance(body["activity_level"], str) or body["activity_level"] not in K.ACTIVITY_FACTORS:
            raise _bad("activity_level is not recognised")
        out["activity_level"] = body["activity_level"]
    if "units" in body:
        if not isinstance(body["units"], str) or body["units"] not in ("metric", "imperial"):
            raise _bad("units must be metric or imperial")
        out["units"] = body["units"]
    if "diet_style" in body:
        v = str(body["diet_style"] or "").lower() if isinstance(body["diet_style"], (str, type(None))) else "?"
        if v not in DIET_STYLES:
            raise _bad("diet_style is not recognised")
        out["diet_style"] = v
    for key in LIST_FIELDS:
        if key in body:
            out[key] = _strings(body[key], key)
    for key in BOOL_FIELDS:
        if key in body:
            if not isinstance(body[key], bool):
                raise _bad(f"{key} must be true or false")
            out[key] = body[key]
    for key, lo, hi in (("meals_per_day", 3, 5), ("level", 1, 3), ("days_per_week", 1, 6), ("session_minutes", 10, 120), ("people", 1, 12)):
        if key in body:
            n = _num(body, key, lo, hi)
            out.pop(key, None) if n is None else out.__setitem__(key, int(n))
    if "clinician_clearance" in body:
        c = body["clinician_clearance"]
        if c in (None, False):
            out.pop("clinician_clearance", None)
        elif isinstance(c, dict) and isinstance(c.get("cleared"), bool):
            areas = _strings(c.get("areas"), "areas", 12)
            if c["cleared"] and (not areas or any(a not in T.CLEARABLE_AREAS for a in areas)):
                raise _bad("Say what your clinician cleared, for example the condition or 'age'")
            out["clinician_clearance"] = {"cleared": c["cleared"], "date": _day(c.get("date")), "areas": areas}
        else:
            raise _bad("clinician_clearance must say cleared true/false and a date")
    return out


def _lbs_to_kg(lbs: Any) -> float | None:
    try:
        return round(float(lbs) / LBS_PER_KG, 2)
    except (TypeError, ValueError):
        return None


def _domain(db: Any, uid: str, slug: str, days: int) -> list[dict]:
    try:
        return health_logs.list_domain(db, slug, health_logs.DOMAINS[slug], uid, days).get("entries", [])
    except HTTPException:
        raise
    except Exception:  # noqa: BLE001  - a refused table must not take the whole feature down
        return []


def records(db: Any, uid: str) -> dict[str, Any]:
    """What Bubbles already knows from the user's tracker records."""
    conds = [e.get("condition_name") for e in _domain(db, uid, "conditions", 730) if e.get("condition_name")]
    meds = [e.get("name") for e in _domain(db, uid, "medications", 730) if e.get("name")]
    allergies = [e.get("allergen") for e in _domain(db, uid, "allergies", 730) if e.get("allergen")]
    weights = [(str(e["date"])[:10], _lbs_to_kg(e.get("weight"))) for e in _domain(db, uid, "weight", 400) if e.get("weight") is not None]
    weights = sorted([(d, w) for d, w in weights if w], key=lambda t: t[0])
    periods = sorted({str(e["date"])[:10] for e in _domain(db, uid, "cycle", 730) if e.get("phase") == "period" and e.get("date")})
    return {"conditions": conds, "medications": meds, "allergies": allergies, "weights": weights,
            "latest_weight_kg": weights[-1][1] if weights else None, "period_starts": periods}


def engine_profile(profile: dict, rec: dict, eating_positive: bool = False, cycle_mode: str | None = None) -> dict:
    """Merge the saved profile with tracker records into what plan_engine / transformation expect.

    The Cycle section's mode counts too: pregnancy, trying to conceive and the months after birth all mean no calorie deficit.
    """
    p = dict(profile)
    if cycle_mode == "pregnancy":
        p["pregnant"] = True
    elif cycle_mode == "conceive":
        p["trying_to_conceive"] = True
    elif cycle_mode == "postpartum":
        p["breastfeeding"] = True        # conservative: Bubbles cannot tell whether someone is breastfeeding after a birth
    p["eating_concern"] = bool(profile.get("eating_disorder_history") or eating_positive)
    p["conditions"] = list(dict.fromkeys(rec["conditions"] + p.get("extra_conditions", [])))
    p["medications"] = list(dict.fromkeys(rec["medications"] + p.get("extra_medications", [])))
    p["allergies"] = list(dict.fromkeys(rec["allergies"] + p.get("extra_allergies", [])))
    if rec["latest_weight_kg"] and not p.get("weight_kg"):
        p["weight_kg"] = rec["latest_weight_kg"]
    elif rec["latest_weight_kg"]:
        p["weight_kg"] = rec["latest_weight_kg"]   # the newest weigh-in always wins over the profile figure
    p["sex"] = p.get("formula_basis")
    return p


def missing_fields(p: dict) -> list[str]:
    need = []
    if not (p.get("birth_date") or p.get("age")):
        need.append("birth_date")
    for k in ("height_cm", "weight_kg"):
        if not p.get(k):
            need.append(k)
    return need


def months_since_period(rec: dict, profile: dict, today: date) -> float | None:
    if not profile.get("menstruating") or not rec["period_starts"]:
        return None
    last = date.fromisoformat(rec["period_starts"][-1])
    return round((today - last).days / 30.4, 1)


def red_flag_days_ago(db: Any, uid: str, today: date) -> int | None:
    """Days since Bubbles last gave an urgent/emergency safety response (None if none in the look-back window)."""
    try:
        rows = (db.table("chat_messages").select("metadata,created_at").eq("user_id", uid).order("created_at", desc=True).limit(300).execute().data or [])
    except Exception:  # noqa: BLE001
        return None
    for r in rows:
        meta = r.get("metadata") if isinstance(r.get("metadata"), dict) else {}
        s = meta.get("safety") if isinstance(meta.get("safety"), dict) else {}
        if s.get("level") == "RED" or s.get("state") in ("URGENT", "EMERGENCY"):
            when = health_logs.parse_moment(r.get("created_at"))
            if when:
                days = (today - when.date()).days
                return days if days <= K.RED_FLAG_LOOKBACK_DAYS else None
    return None


def _food_entries(db: Any, uid: str, day: str) -> list[dict]:
    doc = doc_store.get(db, uid, "food_log", day)
    return list((doc or {}).get("entries", []))


def _chat_food_rows(db: Any, uid: str) -> list[dict]:
    try:
        return (db.table("extracted_health_events").select("id,extracted_data,extraction_status,created_at").eq("user_id", uid)
                .eq("event_type", "food").order("created_at", desc=True).limit(300).execute().data or [])
    except Exception:  # noqa: BLE001
        return []


def _chat_entries_from(rows: list[dict], day: str) -> list[dict]:
    """Meals the user mentioned in chat that day (read-only; fix them by telling Bubbles). Only values Bubbles' own parser produced, within range."""
    out = []
    for r in rows:
        data = r.get("extracted_data") if isinstance(r.get("extracted_data"), dict) else {}
        prov = data.get("_prov") if isinstance(data.get("_prov"), dict) else {}
        if prov.get("source") != "user_message" or prov.get("extractor") != "rules" or str(data.get("date", ""))[:10] != day or not is_live_positive(r):
            continue
        kcal = data.get("calories")
        if isinstance(kcal, bool) or not isinstance(kcal, (int, float)) or kcal != kcal or not 0 <= kcal <= 5000:
            continue
        protein = data.get("protein_g")
        protein = protein if isinstance(protein, (int, float)) and not isinstance(protein, bool) and 0 <= protein <= 500 else 0
        out.append({"id": f"chat-{r['id']}", "ts": r.get("created_at"), "meal": data.get("meal"), "text": str(data.get("name") or "meal")[:300], "source": "chat",
                    "items": [], "label": "estimate",
                    "totals": {"kcal": kcal, "kcal_low": data.get("calories_low", round(kcal * 0.75)), "kcal_high": data.get("calories_high", round(kcal * 1.25)),
                               "protein_g": protein, "carbs_g": 0, "fat_g": 0, "fibre_g": 0}})
    return out


def _all_entries(db: Any, uid: str, day: str, chat_rows: list[dict] | None = None) -> list[dict]:
    """Food-log entries plus meals mentioned in chat (for totals and budgets). Pass ``chat_rows`` to avoid re-querying across many days."""
    return _food_entries(db, uid, day) + _chat_entries_from(chat_rows if chat_rows is not None else _chat_food_rows(db, uid), day)


def _sum(entries: list[dict]) -> dict[str, float]:
    keys = ("kcal", "kcal_low", "kcal_high", "protein_g", "carbs_g", "fat_g", "fibre_g")
    t = {k: sum(float(e.get("totals", {}).get(k, 0)) for e in entries) for k in keys}
    return {k: round(v, 1) if k.endswith("_g") else round(v) for k, v in t.items()}


def _mirror_food(db: Any, uid: str, entry: dict, day: str) -> None:
    """Make a food-log entry visible to insights (one analytics event, tagged mirror). Best effort."""
    try:
        t = entry["totals"]
        db.table("extracted_health_events").insert({
            "user_id": uid, "event_type": "food", "confidence": 1.0, "extraction_status": "confirmed", "user_confirmed": True, "message_id": None,
            "extracted_data": {"name": entry.get("text", "meal")[:120], "category": entry.get("meal") or "meal", "meal_type": entry.get("meal"),
                               "calories": t["kcal"], "protein_g": t["protein_g"], "date": day,
                               "_prov": {"source": "tracker", "domain": "food_log", "store": "mirror", "entry_id": entry["id"]}}}).execute()
    except Exception:  # noqa: BLE001
        pass


def _unmirror_food(db: Any, uid: str, entry_id: str) -> None:
    try:
        rows = db.table("extracted_health_events").select("id").eq("user_id", uid).eq("extracted_data->_prov->>entry_id", entry_id).execute().data or []
        for r in rows:
            db.table("extracted_health_events").update({"extraction_status": "retracted"}).eq("id", r["id"]).eq("user_id", uid).execute()
    except Exception:  # noqa: BLE001
        pass


def _custom_foods(db: Any, uid: str) -> dict[str, dict]:
    return {d["payload"]["name"]: d["payload"] for d in doc_store.list_docs(db, uid, "custom_food", 200) if d["payload"].get("name")}


def build_router(get_user: Callable[[str | None], Any], db: Any) -> APIRouter:
    router = APIRouter()

    def uid_of(authorization: str | None) -> str:
        return str(get_user(authorization).id)

    def eating_positive(uid: str) -> bool:
        """True while a positive eating screen is recent (it stays on even if the answers are entered again)."""
        saved = doc_store.get(db, uid, "eating_screen", "current") or {}
        until = saved.get("positive_until")
        return bool(until) and str(until) >= local_today().isoformat()

    def safety_pause_days_ago(uid: str, today: date) -> int | None:
        saved = doc_store.get(db, uid, "safety_pause", "last")
        if not saved or not saved.get("since"):
            return None
        try:
            return (today - date.fromisoformat(str(saved["since"])[:10])).days
        except ValueError:
            return None

    def record_safety_pause(uid: str, reasons: str) -> None:
        doc_store.put(db, uid, "safety_pause", "last", {"since": local_today().isoformat(), "reason": reasons[:200]})

    def load_profile(uid: str) -> dict:
        return doc_store.get(db, uid, "profile", "me") or {}

    def cycle_mode(uid: str) -> str | None:
        settings = doc_store.get(db, uid, "cycle_settings", "main") or {}
        mode = settings.get("mode")
        return mode if isinstance(mode, str) else None

    def engine(uid: str) -> tuple[dict, dict, dict]:
        profile = load_profile(uid)
        rec = records(db, uid)
        return profile, rec, engine_profile(profile, rec, eating_positive(uid), cycle_mode(uid))

    def targets_for(uid: str, extra_minutes: float | None = None) -> tuple[dict | None, dict, dict, dict, str | None]:
        profile, rec, ep = engine(uid)
        gap = missing_fields(ep)
        if gap:
            names = [{"birth_date": "birth date", "height_cm": "height", "weight_kg": "weight", "sex": "sex"}.get(g, g.replace("_", " ")) for g in gap]
            listed = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
            return None, profile, rec, ep, f"Add your {listed} to see your targets."
        try:
            return plan_engine.build_targets(ep, extra_exercise_min_per_week=extra_minutes), profile, rec, ep, None
        except N.CalcError as err:
            return None, profile, rec, ep, str(err)

    # ---- profile ---------------------------------------------------------------------------
    @router.get("/profile/body")
    def get_body_profile(authorization: str | None = Header(default=None)):
        uid = uid_of(authorization)
        profile, rec, ep = engine(uid)
        age = N.age_from_birth(profile.get("birth_date"))
        return {"status": "success", "profile": profile, "known": {"conditions": rec["conditions"], "medications": rec["medications"], "allergies": rec["allergies"],
                                                                    "latest_weight_kg": rec["latest_weight_kg"]},
                "age": age, "missing": missing_fields(ep), "review": plan_engine.review_banner(), "scoff_questions": list(K.SCOFF_QUESTIONS),
                "parq_questions": [{"key": k, "text": q, "blocking": k in K.PARQ_BLOCKING_KEYS} for k, q in K.PARQ_QUESTIONS]}

    @router.put("/profile/body")
    async def put_body_profile(request: Request, authorization: str | None = Header(default=None)):
        uid = await run_in_threadpool(uid_of, authorization)
        body = await _json(request)

        def save():
            merged = clean_profile(body, load_profile(uid))
            doc_store.put(db, uid, "profile", "me", merged)
            return merged
        return {"status": "success", "profile": await run_in_threadpool(save)}

    # ---- targets / summary -------------------------------------------------------------------------------
    @router.get("/fitness/targets")
    def get_targets(authorization: str | None = Header(default=None)):
        uid = uid_of(authorization)
        t, _p, _r, _e, why = targets_for(uid)
        return {"status": "success", "targets": t, "message": why, "review": plan_engine.review_banner()}

    @router.get("/fitness/summary")
    def summary(date_: str | None = Query(default=None, alias="date"), authorization: str | None = Header(default=None)):
        uid = uid_of(authorization)
        day = _day(date_)
        t, profile, rec, ep, why = targets_for(uid)
        entries = _all_entries(db, uid, day)
        eaten = _sum(entries)
        workout = doc_store.get(db, uid, "workout_log", day) or {}
        burn = sum(float(w.get("kcal_estimate", 0)) for w in workout.get("sessions", []))
        plan = doc_store.get(db, uid, "transform_plan", "current")
        water_today = hydration_engine.day_totals(_domain(db, uid, "hydration", 2), day, request_tz() or 0)["raw_ml"]  # tz-aware, ignores invalid volumes
        out: dict[str, Any] = {"status": "success", "date": day, "water_ml_today": round(water_today), "targets": t, "message": why, "eaten": eaten, "entries": len(entries), "intake_logged": bool(entries),
                               "workout_kcal": round(burn), "transform": {"status": plan["status"], "target_weight_kg": plan["target_weight_kg"]} if plan else None,
                               "has_diet_plan": bool(doc_store.get(db, uid, "meal_plan", "current")), "has_workout_plan": bool(doc_store.get(db, uid, "workout_plan", "current")),
                               "review": plan_engine.review_banner(), "latest_weight_kg": rec["latest_weight_kg"]}
        if t:
            out["budget"] = plan_engine.day_budget(t, eaten["kcal"], burn)
        return out

    # ---- foods -------------------------------------------------------------------------------------
    @router.get("/fitness/foods/search")
    def foods_search(q: str = Query(default="", max_length=80), limit: int = Query(default=10, ge=1, le=30), authorization: str | None = Header(default=None)):
        uid = uid_of(authorization)
        extra = _custom_foods(db, uid)
        return {"status": "success", "results": [food_db.card(f) for f in food_db.search(q, limit, extra)], "label": "estimate"}

    @router.get("/fitness/foods/barcode/{code}")
    def food_by_barcode(code: str, authorization: str | None = Header(default=None)):
        get_user(authorization)
        if not open_food_facts.valid_barcode(code):
            raise _bad("A barcode has 8 to 14 digits")
        row = open_food_facts.lookup(code)
        if row is None:
            raise _bad("Bubbles could not find that product. You can add it as your own food.", 404)
        return {"status": "success", "food": food_db.card(row), "label": "estimate", "note": "Community data from Open Food Facts. Check it against the pack."}

    @router.post("/fitness/foods/custom", status_code=201)
    async def add_custom_food(request: Request, authorization: str | None = Header(default=None)):
        uid = await run_in_threadpool(uid_of, authorization)
        b = await _json(request)
        if b.get("kcal") in (None, ""):  # an unknown amount must never be saved as 0 kcal (it would understate intake)
            raise _bad("Please enter the calories for one serving (enter 0 only if it really has none)")
        try:
            def f(key: str, default: float) -> float:
                v = b.get(key)
                return default if v in (None, "") else float(v)
            row = food_db.custom_food(str(b.get("name") or ""), str(b.get("serving") or "1 serving"), f("serving_g", 100), f("kcal", 0), f("protein_g", 0),
                                      f("carbs_g", 0), f("fat_g", 0), f("fibre_g", 0), str(b.get("diet") or "v"), _strings(b.get("allergens"), "allergens", 10))
        except (ValueError, TypeError, OverflowError) as err:
            msg = str(err)
            raise _bad(msg if "float()" not in msg and "could not convert" not in msg else "Please enter numbers for the serving and nutrients")
        existing = await run_in_threadpool(doc_store.list_docs, db, uid, "custom_food", food_db.MAX_CUSTOM_FOODS + 1)
        if len(existing) >= food_db.MAX_CUSTOM_FOODS and row["name"] not in {d["key"] for d in existing}:
            raise _bad("You have saved the maximum number of your own foods. Delete one first.")
        await run_in_threadpool(doc_store.put, db, uid, "custom_food", row["name"][:100], row)
        return {"status": "success", "food": food_db.card(row)}

    @router.post("/fitness/meal/parse")
    async def parse_meal(request: Request, authorization: str | None = Header(default=None)):
        uid = await run_in_threadpool(uid_of, authorization)
        b = await _json(request)
        text = str(b.get("text") or "")[:2000]
        if not text.strip():
            raise _bad("Tell Bubbles what you ate")
        oil = _num(b, "oil_extra_tsp", -3, 10) or 0.0

        def run():
            profile, rec, ep = engine(uid)
            parsed = meal_composer.compose(text, _custom_foods(db, uid), oil_extra_tsp=max(0.0, oil))
            parsed["warnings"] = meal_composer.conflicts(parsed, ep.get("diet_style"), ep.get("allergies"))
            codes = T.restriction_language(text)
            if codes:
                parsed["support"] = "It sounds like food may feel hard right now. If that is true, you do not have to carry it alone. Talking to a doctor or someone you trust can help."
            return parsed
        return {"status": "success", **(await run_in_threadpool(run))}

    @router.post("/fitness/food-log", status_code=201)
    async def add_food_log(request: Request, authorization: str | None = Header(default=None)):
        uid = await run_in_threadpool(uid_of, authorization)
        b = await _json(request)
        day = _log_day(b.get("date"))
        meal = str(b.get("meal") or "").lower()
        if meal and meal not in ("breakfast", "lunch", "dinner", "snack"):
            raise _bad("meal must be breakfast, lunch, dinner or snack")
        text = str(b.get("text") or "")[:2000]
        if not text.strip():
            raise _bad("Tell Bubbles what you ate")
        oil = max(0.0, _num(b, "oil_extra_tsp", -3, 10) or 0.0)

        def run():
            parsed = meal_composer.compose(text, _custom_foods(db, uid), oil_extra_tsp=oil)
            if not parsed["items"]:
                raise _bad("Bubbles did not recognise any food in that. Try naming the foods, for example '2 rotis, dal and curd'.")
            entry = {"id": uuid.uuid4().hex[:10], "ts": datetime.now(timezone.utc).isoformat(), "meal": meal or None, "text": text[:300], "items": parsed["items"],
                     "totals": parsed["totals"], "unrecognised": parsed["unrecognised"], "label": "estimate"}
            entries = _food_entries(db, uid, day)
            if len(entries) >= 60:
                raise _bad("That is a lot of entries for one day. Edit or delete some first.")
            doc_store.put(db, uid, "food_log", day, {"entries": entries + [entry]})
            _mirror_food(db, uid, entry, day)
            return entry
        entry = await run_in_threadpool(run)
        return {"status": "success", "entry": entry}

    @router.get("/fitness/food-log")
    def get_food_log(date_: str | None = Query(default=None, alias="date"), authorization: str | None = Header(default=None)):
        uid = uid_of(authorization)
        day = _day(date_)
        entries = _all_entries(db, uid, day)
        t, *_ = targets_for(uid)
        workout = doc_store.get(db, uid, "workout_log", day) or {}
        burn = sum(float(w.get("kcal_estimate", 0)) for w in workout.get("sessions", []))
        totals = _sum(entries)
        return {"status": "success", "date": day, "entries": entries, "totals": totals, "budget": plan_engine.day_budget(t, totals["kcal"], burn) if t else None,
                "targets": t, "label": "estimate"}

    @router.delete("/fitness/food-log/{entry_id}")
    def delete_food_entry(entry_id: str, date_: str | None = Query(default=None, alias="date"), authorization: str | None = Header(default=None)):
        uid = uid_of(authorization)
        day = _day(date_)
        entries = _food_entries(db, uid, day)
        keep = [e for e in entries if e.get("id") != entry_id]
        if len(keep) == len(entries):
            raise _bad("That entry was not found", 404)
        doc_store.put(db, uid, "food_log", day, {"entries": keep})
        _unmirror_food(db, uid, entry_id)
        return {"status": "success", "entries": keep, "totals": _sum(keep)}

    @router.get("/fitness/food-log/week")
    def food_week(days: int = Query(default=7, ge=1, le=60), authorization: str | None = Header(default=None)):
        uid = uid_of(authorization)
        today = local_today()
        out = []
        chat_rows = _chat_food_rows(db, uid)
        for i in range(days):
            d = (today - timedelta(days=i)).isoformat()
            entries = _all_entries(db, uid, d, chat_rows)
            out.append({"date": d, "kcal": _sum(entries)["kcal"], "protein_g": _sum(entries)["protein_g"], "entries": len(entries)})
        return {"status": "success", "days": list(reversed(out))}

    # ---- diet plan ---------------------------------------------------------------------------------
    def diet_prefs(profile: dict, ep: dict, targets: dict, extra: dict) -> dict:
        return {"diet_style": extra.get("diet_style", profile.get("diet_style")), "allergies": ep.get("allergies") or [],
                "dislikes": extra.get("dislikes", profile.get("dislikes") or []), "likes": extra.get("likes", profile.get("likes") or []),
                "must_include": extra.get("must_include") or [], "goal": targets["goal"],
                "conditions": condition_rules.classify(ep.get("conditions"), ep.get("medications")), "menstruating": bool(profile.get("menstruating")),
                "seed": int(extra.get("seed") or 0)}

    @router.post("/fitness/diet/plan")
    async def make_diet_plan(request: Request, authorization: str | None = Header(default=None)):
        uid = await run_in_threadpool(uid_of, authorization)
        b = await _json(request)

        def run():
            t, profile, _rec, ep, why = targets_for(uid)
            if t is None:
                raise _bad(why or "Add your details first")
            extra = {"diet_style": str(b.get("diet_style") or profile.get("diet_style") or "").lower(), "must_include": _strings(b.get("must_include"), "must_include", 20),
                     "likes": _strings(b.get("likes"), "likes") or profile.get("likes", []), "dislikes": _strings(b.get("dislikes"), "dislikes") or profile.get("dislikes", []),
                     "seed": int(_num(b, "seed", 0, 1000) or 0)}
            meals = int(_num(b, "meals_per_day", 3, 5) or profile.get("meals_per_day") or 4)
            prefs = diet_prefs(profile, ep, t, extra)
            plan = diet_planner.plan_week(t, prefs, meals_per_day=meals)
            if not plan["ok"]:
                raise _bad(plan["reason"])
            doc = {"plan": plan, "prefs": {k: v for k, v in prefs.items() if k != "conditions"}, "targets_kcal": t["kcal"], "meals_per_day": meals,
                   "created": datetime.now(timezone.utc).isoformat(), "locked": []}
            doc_store.put(db, uid, "meal_plan", "current", doc)
            return doc
        doc = await run_in_threadpool(run)
        return {"status": "success", **doc, "review": plan_engine.review_banner()}

    @router.get("/fitness/diet/plan")
    def get_diet_plan(authorization: str | None = Header(default=None)):
        uid = uid_of(authorization)
        doc = doc_store.get(db, uid, "meal_plan", "current")
        return {"status": "success", "exists": bool(doc), **(doc or {}), "review": plan_engine.review_banner()}

    @router.post("/fitness/diet/swap-options")
    async def swap_options(request: Request, authorization: str | None = Header(default=None)):
        uid = await run_in_threadpool(uid_of, authorization)
        b = await _json(request)

        def run():
            doc = doc_store.get(db, uid, "meal_plan", "current")
            t, profile, _rec, ep, why = targets_for(uid)
            if not doc or t is None:
                raise _bad("Make a meal plan first")
            day_i, slot = int(_num(b, "day", 1, 14) or 1), str(b.get("slot") or "")
            days = doc["plan"]["days"]
            if day_i > len(days):
                raise _bad("That day is not in your plan")
            cur = next((m for m in days[day_i - 1]["meals"] if m["slot"] == slot), None)
            if cur is None:
                raise _bad("That meal slot is not in your plan")
            used = [m["template_id"] for d in days for m in d["meals"]]
            return diet_planner.swap_options(t, diet_prefs(profile, ep, t, doc["prefs"]), cur["template_id"], slot, doc["meals_per_day"], 6, used[-8:])
        return {"status": "success", "options": await run_in_threadpool(run)}

    @router.post("/fitness/diet/swap")
    async def swap_meal(request: Request, authorization: str | None = Header(default=None)):
        uid = await run_in_threadpool(uid_of, authorization)
        b = await _json(request)

        def run():
            doc = doc_store.get(db, uid, "meal_plan", "current")
            t, profile, _rec, ep, _why = targets_for(uid)
            if not doc or t is None:
                raise _bad("Make a meal plan first")
            day_i, slot, tid = int(_num(b, "day", 1, 14) or 1), str(b.get("slot") or ""), str(b.get("template_id") or "")
            days = doc["plan"]["days"]
            if day_i > len(days):
                raise _bad("That day is not in your plan")
            options = diet_planner.swap_options(t, diet_prefs(profile, ep, t, doc["prefs"]), "", slot, doc["meals_per_day"], 30)
            new = next((o for o in options if o["template_id"] == tid), None)
            if new is None:
                raise _bad("That meal is not a safe swap for this slot")
            meals = days[day_i - 1]["meals"]
            idx = next(i for i, m in enumerate(meals) if m["slot"] == slot)
            meals[idx] = new
            days[day_i - 1] = diet_planner._finish_day(meals, t) | {"day": day_i}
            doc_store.put(db, uid, "meal_plan", "current", doc)
            return days[day_i - 1]
        return {"status": "success", "day": await run_in_threadpool(run)}

    @router.get("/fitness/diet/grocery")
    def grocery(people: int = Query(default=1, ge=1, le=12), authorization: str | None = Header(default=None)):
        uid = uid_of(authorization)
        doc = doc_store.get(db, uid, "meal_plan", "current")
        if not doc:
            raise _bad("Make a meal plan first", 404)
        return {"status": "success", "aisles": diet_planner.grocery_list(doc["plan"], people), "note": "Quantities are approximate."}

    # ---- workouts ---------------------------------------------------------------------------------
    @router.get("/fitness/exercises")
    def exercises(q: str = Query(default="", max_length=40), category: str = Query(default="", max_length=20), authorization: str | None = Header(default=None)):
        get_user(authorization)
        ql = q.lower().strip()
        rows = [m for m in LIB.values() if (not category or m["category"] == category) and (not ql or ql in m["name"].lower() or ql in m["pattern"])]
        return {"status": "success", "exercises": rows[:100]}

    @router.post("/fitness/workouts/screen")
    async def workouts_screen(request: Request, authorization: str | None = Header(default=None)):
        uid = await run_in_threadpool(uid_of, authorization)
        b = await _json(request)
        answers = b.get("answers")
        if not isinstance(answers, dict) or any(not isinstance(v, bool) for v in answers.values()):
            raise _bad("answers must be yes/no for each question")
        result = exercise_planner.screen(answers, bool(b.get("clinician_cleared")))
        if result["mode"] != "incomplete":
            await run_in_threadpool(doc_store.put, db, uid, "exercise_screen", "current", {**result, "answers": answers, "date": _day(None), "clinician_cleared": bool(b.get("clinician_cleared"))})
        return {"status": "success", **result}

    @router.post("/fitness/workouts/plan")
    async def make_workout_plan(request: Request, authorization: str | None = Header(default=None)):
        uid = await run_in_threadpool(uid_of, authorization)
        b = await _json(request)

        def run():
            profile, rec, ep = engine(uid)
            gap = missing_fields(ep)
            if gap:
                raise _bad("Add your " + ", ".join(g.replace("_", " ") for g in gap) + " first")
            scr = doc_store.get(db, uid, "exercise_screen", "current")
            if not scr:
                raise _bad("Please answer the short safety questions first", 409)
            prior = doc_store.get(db, uid, "workout_plan", "current") or {}
            week_index = int(_num(b, "week_index", 1, 104) or (prior.get("week_index", 0) + (1 if b.get("next_week") else 0) or 1))
            params = {"days_per_week": int(_num(b, "days_per_week", 1, 6) or profile.get("days_per_week") or 3), "minutes": int(_num(b, "minutes", 10, 120) or profile.get("session_minutes") or 40),
                      "equipment": b.get("equipment") or profile.get("equipment") or "none", "level": int(_num(b, "level", 1, 3) or profile.get("level") or 1)}
            if isinstance(params["equipment"], list):
                params["equipment"] = _strings(params["equipment"], "equipment", 10)
            elif params["equipment"] not in ("none", "home", "gym", "pool"):
                raise _bad("equipment must be none, home, gym or pool")
            try:
                body = N.check_body(ep.get("weight_kg"), ep.get("height_cm"), N.age_from_birth(ep.get("birth_date")) or ep.get("age"), required=("weight_kg", "height_cm", "age"))
                plan = exercise_planner.plan_week({**ep, "weight_kg": body["weight_kg"], "height_cm": body["height_cm"], "age": body["age"]}, week_index=week_index,
                                                  screen_result={k: scr[k] for k in ("mode", "message", "blocking", "adapt", "unanswered", "cleared") if k in scr},
                                                  injuries=profile.get("injuries", []), **params)
            except N.CalcError as err:
                raise _bad(str(err))
            if not plan.get("ok"):
                raise _bad(plan.get("reason") or "Could not build a plan")
            doc_store.put(db, uid, "workout_plan", "current", {"plan": plan, "week_index": week_index, "params": {k: v for k, v in params.items()}, "created": datetime.now(timezone.utc).isoformat()})
            return plan
        return {"status": "success", "plan": await run_in_threadpool(run), "review": plan_engine.review_banner()}

    @router.get("/fitness/workouts/plan")
    def get_workout_plan(authorization: str | None = Header(default=None)):
        uid = uid_of(authorization)
        doc = doc_store.get(db, uid, "workout_plan", "current")
        return {"status": "success", "exists": bool(doc), **(doc or {}), "screen": doc_store.get(db, uid, "exercise_screen", "current")}

    @router.post("/fitness/workouts/adapt")
    async def adapt_workout(request: Request, authorization: str | None = Header(default=None)):
        uid = await run_in_threadpool(uid_of, authorization)
        b = await _json(request)

        def run():
            doc = doc_store.get(db, uid, "workout_plan", "current")
            if not doc:
                raise _bad("Make a workout plan first")
            i = int(_num(b, "session", 0, 6) or 0)
            sessions = doc["plan"]["sessions"]
            if i >= len(sessions):
                raise _bad("That session is not in your plan")
            fb = b.get("feedback") if isinstance(b.get("feedback"), dict) else {}
            fb = {k: v for k, v in fb.items() if k in ("pain", "pain_area", "pain_severity", "chest_pain", "dizzy", "fainting", "poor_sleep", "low_energy", "heavy_period", "rpe_avg", "completed_pct")}
            result = exercise_planner.adapt_session(sessions[i], fb)
            minutes = _num(b, "minutes", 5, 120)
            if minutes and not result["stop"]:
                result["session"] = exercise_planner.time_box(result["session"], int(minutes))
                result["messages"].append(f"Shortened to {int(minutes)} minutes.")
            return result
        return {"status": "success", **(await run_in_threadpool(run))}

    @router.post("/fitness/workouts/log", status_code=201)
    async def log_workout(request: Request, authorization: str | None = Header(default=None)):
        uid = await run_in_threadpool(uid_of, authorization)
        b = await _json(request)
        day = _log_day(b.get("date"))
        title = str(b.get("title") or b.get("activity") or "").strip()[:100]
        minutes = _num(b, "minutes", 1, 600)
        if not title or not minutes:
            raise _bad("Tell Bubbles what you did and for how long")
        rpe = _num(b, "rpe", 0, 10)

        def run():
            t, _p, _r, ep, _w = targets_for(uid)
            weight = (t or {}).get("current_weight_kg") or ep.get("weight_kg") or 70.0
            met_key = str(b.get("activity") or title).lower().replace(" ", "_")
            try:
                burn = N.met_burn(met_key if met_key in K.MET_VALUES else "walking_brisk" if "walk" in met_key else "strength_light", minutes, float(weight))
            except N.CalcError as err:
                raise _bad(str(err))
            session = {"id": uuid.uuid4().hex[:10], "title": title, "minutes": minutes, "rpe": rpe, "kcal_estimate": burn["kcal"], "sets": [x for x in (b.get("sets") if isinstance(b.get("sets"), list) else [])[:40] if isinstance(x, (dict, int, float, str)) and len(str(x)) < 200],
                       "ts": datetime.now(timezone.utc).isoformat()}
            doc = doc_store.get(db, uid, "workout_log", day) or {}
            doc_store.put(db, uid, "workout_log", day, {"sessions": (doc.get("sessions", []) + [session])[-20:]})
            try:  # also the tracker domain, so insights and the activity page see it
                health_logs.save_domain(db, "activity", health_logs.DOMAINS["activity"], uid, {"type": title, "duration": minutes, "intensity": "rpe %g" % rpe if rpe is not None else None, "date": day})
            except Exception:  # noqa: BLE001
                pass
            return {**session, "burn": burn}
        return {"status": "success", "session": await run_in_threadpool(run)}

    @router.get("/fitness/workouts/log")
    def workout_log(days: int = Query(default=14, ge=1, le=90), authorization: str | None = Header(default=None)):
        uid = uid_of(authorization)
        today = local_today()
        out = []
        for i in range(days):
            d = (today - timedelta(days=i)).isoformat()
            doc = doc_store.get(db, uid, "workout_log", d)
            if doc and doc.get("sessions"):
                out.append({"date": d, "sessions": doc["sessions"]})
        return {"status": "success", "days": out}

    # ---- progress --------------------------------------------------------------------------------------
    @router.get("/fitness/progress")
    def progress(days: int = Query(default=120, ge=7, le=730), authorization: str | None = Header(default=None)):
        uid = uid_of(authorization)
        rec = records(db, uid)
        cutoff = (local_today() - timedelta(days=days)).isoformat()
        pts = [(d, w) for d, w in rec["weights"] if d >= cutoff]
        trend = N.weight_trend(pts)
        measurements = [{"date": d["key"], **d["payload"]} for d in doc_store.list_docs(db, uid, "measurement", 60)]
        logged = [(local_today() - timedelta(days=i)).isoformat() for i in range(28)]
        chat_rows = _chat_food_rows(db, uid)
        days_logged = sum(1 for d in logged if _all_entries(db, uid, d, chat_rows))
        plan = doc_store.get(db, uid, "transform_plan", "current")
        return {"status": "success", "weights": [{"date": d, "weight_kg": w} for d, w in pts], "trend": trend, "rate_kg_per_week": N.trend_rate_kg_per_week(trend, 14),
                "measurements": measurements, "adherence": {"days_logged_28": days_logged, "label": "consistency, not perfection"},
                "plan": {"status": plan["status"], "start_weight_kg": plan["start_weight_kg"], "target_weight_kg": plan["target_weight_kg"]} if plan else None,
                "luteal_note": "Weight can rise a little around your period because of water. Trends matter more than single days."}

    @router.post("/fitness/measurements", status_code=201)
    async def add_measurement(request: Request, authorization: str | None = Header(default=None)):
        uid = await run_in_threadpool(uid_of, authorization)
        b = await _json(request)
        day = _log_day(b.get("date"))
        vals = {k: _num(b, k, 10, 300) for k in ("waist_cm", "hip_cm", "chest_cm", "arm_cm", "thigh_cm")}
        vals = {k: v for k, v in vals.items() if v is not None}
        if not vals:
            raise _bad("Enter at least one measurement")
        await run_in_threadpool(doc_store.put, db, uid, "measurement", day, vals)
        return {"status": "success", "date": day, "measurements": vals}

    # ---- Strict Transformation mode -----------------------------------------------------------------------------
    def scoff_from(b: dict, uid: str) -> list[bool] | None:
        s = b.get("scoff")
        if s is None:
            saved = doc_store.get(db, uid, "eating_screen", "current")
            return saved.get("answers") if saved and saved.get("answers") else None
        if not isinstance(s, list) or len(s) != SCOFF_REQUIRED or any(not isinstance(v, bool) for v in s):
            raise _bad(f"scoff must be {SCOFF_REQUIRED} yes/no answers")
        return s

    def do_screen(uid: str, b: dict) -> tuple[dict, dict, dict, date]:
        profile, rec, ep = engine(uid)
        today = local_today()
        scoff = scoff_from(b, uid)
        if b.get("scoff") is not None:
            prior = doc_store.get(db, uid, "eating_screen", "current") or {}
            positive = sum(scoff) >= K.SCOFF_POSITIVE_AT
            until = (today + timedelta(days=K.EATING_SCREEN_STICKY_DAYS)).isoformat() if positive else prior.get("positive_until")
            doc_store.put(db, uid, "eating_screen", "current", {"answers": scoff, "positive": positive, "date": today.isoformat(), "positive_until": until})
            if not positive and until and str(until) >= today.isoformat():
                scoff = list(prior.get("answers") or scoff)         # re-entering "no" answers does not erase a recent positive screen
        if "target_weight_kg" in b:
            t = _num(b, "target_weight_kg", *K.MIN_PLAUSIBLE["weight_kg"])
            ep = {**ep, "target_weight_kg": t}
        gap = missing_fields(ep)
        if gap:
            raise _bad("Add your " + ", ".join(g.replace("_", " ") for g in gap) + " first")
        result = T.screen(ep, scoff, months_since_period=months_since_period(rec, profile, today), red_flag_days_ago=red_flag_days_ago(db, uid, today),
                          recent_surgery_or_injury=bool(b.get("recent_surgery_or_injury")), safety_pause_days_ago=safety_pause_days_ago(uid, today), today=today)
        return result, profile, ep, today

    @router.post("/fitness/transform/screen")
    async def transform_screen(request: Request, authorization: str | None = Header(default=None)):
        uid = await run_in_threadpool(uid_of, authorization)
        b = await _json(request)
        result, *_ = await run_in_threadpool(do_screen, uid, b)
        return {"status": "success", **result, "review": plan_engine.review_banner(), "scoff_questions": list(K.SCOFF_QUESTIONS)}

    @router.post("/fitness/transform/preview")
    async def transform_preview(request: Request, authorization: str | None = Header(default=None)):
        uid = await run_in_threadpool(uid_of, authorization)
        b = await _json(request)

        def run():
            result, profile, ep, _today = do_screen(uid, b)
            if result["decision"] not in ("allowed", "allowed_with_cautions"):
                return {"screening": result, "preview": None}
            sel = selections_from(b, uid)
            return {"screening": result, "preview": T.preview(ep, sel)}
        return {"status": "success", **(await run_in_threadpool(run)), "review": plan_engine.review_banner()}

    def selections_from(b: dict, uid: str) -> dict:
        s = b.get("selections") if isinstance(b.get("selections"), dict) else {}
        out: dict[str, Any] = {"foods": _strings(s.get("foods"), "foods", 30), "likes": _strings(s.get("likes"), "likes"), "dislikes": _strings(s.get("dislikes"), "dislikes"),
                               "diet_style": str(s.get("diet_style") or "").lower() or None, "meals_per_day": int(_num(s, "meals_per_day", 3, 5) or 4),
                               "days_per_week": int(_num(s, "days_per_week", 1, 6) or 4), "session_minutes": int(_num(s, "session_minutes", 10, 120) or 40),
                               "level": int(_num(s, "level", 1, 3) or 1), "injuries": _strings(s.get("injuries"), "injuries", 10)}
        eq = s.get("equipment") or "none"
        out["equipment"] = _strings(eq, "equipment", 10) if isinstance(eq, list) else (eq if eq in ("none", "home", "gym", "pool") else "none")
        pace = _num(s, "pace_pct_per_week", 0.1, 1.0)
        if pace:
            out["pace_pct_per_week"] = pace
        scr = doc_store.get(db, uid, "exercise_screen", "current")
        if scr:
            out["exercise_screen"] = {k: scr[k] for k in ("mode", "message", "blocking", "adapt", "unanswered", "cleared") if k in scr}
        return out

    @router.post("/fitness/transform/start", status_code=201)
    async def transform_start(request: Request, authorization: str | None = Header(default=None)):
        uid = await run_in_threadpool(uid_of, authorization)
        b = await _json(request)

        def run():
            existing = doc_store.get(db, uid, "transform_plan", "current")
            if existing and existing.get("status") in ("active", "paused"):
                raise _bad("You already have a plan. Pause or finish it first.", 409)
            result, profile, ep, today = do_screen(uid, b)       # re-checked on the server: the screen is never trusted from the client
            try:
                plan = T.make_plan(ep, selections_from(b, uid), result, b.get("acknowledged") is True, today)
            except ValueError as err:
                raise _bad(str(err), 403 if "not available" in str(err) else 422)
            diet = plan.pop("diet_preview", None)
            doc_store.put(db, uid, "transform_plan", "current", plan)
            if diet:
                doc_store.put(db, uid, "meal_plan", "current", {"plan": diet, "prefs": {}, "targets_kcal": plan["targets"]["kcal"], "meals_per_day": plan["selections"].get("meals_per_day", 4),
                                                               "created": datetime.now(timezone.utc).isoformat(), "locked": [], "from_plan": plan["id"]})
            return plan
        return {"status": "success", "plan": await run_in_threadpool(run)}

    def current_plan(uid: str) -> dict:
        plan = doc_store.get(db, uid, "transform_plan", "current")
        if not plan:
            raise _bad("You do not have a transformation plan yet", 404)
        return plan

    @router.get("/fitness/transform/plan")
    def transform_plan(authorization: str | None = Header(default=None)):
        uid = uid_of(authorization)
        plan = doc_store.get(db, uid, "transform_plan", "current")
        return {"status": "success", "exists": bool(plan), "plan": plan, "review": plan_engine.review_banner()}

    @router.get("/fitness/transform/today")
    def transform_today(date_: str | None = Query(default=None, alias="date"), authorization: str | None = Header(default=None)):
        uid = uid_of(authorization)
        plan = current_plan(uid)
        day = _day(date_)
        eaten = _sum(_all_entries(db, uid, day))
        workout = doc_store.get(db, uid, "workout_log", day) or {}
        burn = sum(float(w.get("kcal_estimate", 0)) for w in workout.get("sessions", []))
        water = hydration_engine.day_totals(_domain(db, uid, "hydration", 2), day, request_tz() or 0)["raw_ml"]
        view = T.today_view(plan, eaten, water, burn, 0)
        meal_doc = doc_store.get(db, uid, "meal_plan", "current")
        today_meals = None
        if meal_doc:
            idx = (local_today() - date.fromisoformat(plan["start_date"])).days % max(1, len(meal_doc["plan"]["days"]))
            today_meals = meal_doc["plan"]["days"][idx]
        return {"status": "success", "plan_status": plan["status"], "view": view, "meals": today_meals, "good_day": T.good_day(plan["targets"], None), "review": plan_engine.review_banner()}

    def checkin_inputs(uid: str, plan: dict, today: date) -> dict:
        rec = records(db, uid)
        intake = []
        chat_rows = _chat_food_rows(db, uid)
        for i in range(20):
            d = (today - timedelta(days=i)).isoformat()
            k = _sum(_all_entries(db, uid, d, chat_rows))["kcal"]
            if k > 0:
                intake.append({"date": d, "kcal": k})
        intake.sort(key=lambda x: x["date"])
        exercise_min = 0.0
        for i in range(7):
            doc = doc_store.get(db, uid, "workout_log", (today - timedelta(days=i)).isoformat()) or {}
            exercise_min += sum(float(s.get("minutes", 0)) for s in doc.get("sessions", []))
        return {"weights": [(d, w) for d, w in rec["weights"] if d >= plan["start_date"] or True][-120:], "intake": intake, "exercise_min": exercise_min, "rec": rec}

    @router.post("/fitness/transform/checkin")
    async def transform_checkin(request: Request, authorization: str | None = Header(default=None)):
        uid = await run_in_threadpool(uid_of, authorization)
        b = await _json(request)

        def run():
            plan = current_plan(uid)
            if plan["status"] != "active":
                raise _bad("The plan is paused", 409)
            today = local_today()
            last = plan.get("last_checkin_applied")
            if last and (today - date.fromisoformat(str(last)[:10])).days < K.CHECKIN_MIN_DAYS_BETWEEN:
                raise _bad("You already did this week's check-in. The next one opens in a few days.", 409)
            inp = checkin_inputs(uid, plan, today)
            profile = load_profile(uid)
            symptoms = {k: bool(v) for k, v in (b.get("symptoms") or {}).items() if k in ("dizzy", "fainting", "palpitations", "chest_pain")} if isinstance(b.get("symptoms"), dict) else {}
            text = str(b.get("note") or "")[:1000]
            codes = T.restriction_language(text) if text else []
            starts = inp["rec"]["period_starts"]
            recent_period = bool(starts) and (today - date.fromisoformat(starts[-1])).days <= 5
            result = T.weekly_checkin(plan, inp["weights"], inp["intake"], exercise_min_week=inp["exercise_min"], today=today,
                                      in_luteal_or_period=bool(b.get("in_luteal_or_period")) or recent_period, symptoms=symptoms,
                                      months_without_period=months_since_period(inp["rec"], profile, today), restriction_codes=codes,
                                      past_weekly_rates=[float(x) for x in (plan.get("past_rates") or [])][-4:])
            if result["decision"] == "pause":
                paused = T.pause(plan, "safety check-in", safety=True)
                doc_store.put(db, uid, "transform_plan", "current", paused)
                record_safety_pause(uid, "weekly check-in safety monitor")
                result["applied"] = True
            else:
                doc_store.put(db, uid, "checkin_proposal", "current", {"result": {k: v for k, v in result.items() if k not in ("trend",)}, "date": today.isoformat()})
                result["applied"] = False
            return result
        return {"status": "success", **(await run_in_threadpool(run))}

    @router.post("/fitness/transform/checkin/apply")
    async def transform_checkin_apply(request: Request, authorization: str | None = Header(default=None)):
        uid = await run_in_threadpool(uid_of, authorization)
        b = await _json(request)

        def run():
            plan = current_plan(uid)
            prop = doc_store.get(db, uid, "checkin_proposal", "current")
            if not prop:
                raise _bad("There is no check-in waiting", 404)
            if plan["status"] != "active":
                raise _bad("The plan is paused", 409)
            if prop.get("date") != local_today().isoformat():
                doc_store.delete(db, uid, "checkin_proposal", "current")
                raise _bad("That check-in is out of date. Please do a new one.", 409)
            r = prop["result"]
            if b.get("accept") is True and r.get("new_kcal") and r["decision"] in ("adjust", "continue"):
                t = dict(plan["targets"])
                new = max(float(t["floor_kcal"]), float(r["new_kcal"]))
                if abs(new - t["kcal"]) > K.MAX_WEEKLY_CALORIE_CHANGE + 1:
                    raise _bad("That change is bigger than Bubbles allows in a week")
                _p, _r, ep = engine(uid)
                height = ep.get("height_cm") or plan["targets"].get("height_cm")
                if not height:
                    raise _bad("Add your height in Fitness setup first", 409)
                kidney = condition_rules.classify(ep.get("conditions"), ep.get("medications"))["kidney"]
                m = N.macros(new, plan["targets"]["current_weight_kg"], float(height), True, kidney_caution=kidney)
                t.update(kcal=round(new), deficit_kcal=max(0, round(t["tdee_kcal"] - new)), **m)
                plan = {**plan, "targets": t}
            plan = {**plan, "weeks_on_plan": plan.get("weeks_on_plan", 0) + 1, "last_checkin_applied": local_today().isoformat(),
                    "past_rates": (plan.get("past_rates") or [])[-9:] + ([r["trend_rate_kg_per_week"]] if r.get("trend_rate_kg_per_week") is not None else [])}
            T._log(plan, "checkin_applied" if b.get("accept") is True else "checkin_skipped", decision=r["decision"])
            doc_store.put(db, uid, "transform_plan", "current", plan)
            doc_store.delete(db, uid, "checkin_proposal", "current")
            return plan
        return {"status": "success", "plan": await run_in_threadpool(run)}

    @router.post("/fitness/transform/pause")
    async def transform_pause(request: Request, authorization: str | None = Header(default=None)):
        uid = await run_in_threadpool(uid_of, authorization)
        b = await _json(request)

        def run():
            plan = T.pause(current_plan(uid), str(b.get("reason") or "user")[:200])
            doc_store.put(db, uid, "transform_plan", "current", plan)
            return plan
        return {"status": "success", "plan": await run_in_threadpool(run)}

    @router.post("/fitness/transform/resume")
    async def transform_resume(request: Request, authorization: str | None = Header(default=None)):
        uid = await run_in_threadpool(uid_of, authorization)
        b = await _json(request)

        def run():
            plan = current_plan(uid)
            result, *_ = do_screen(uid, b)
            try:
                plan = T.resume(plan, result)
            except ValueError as err:
                raise _bad(str(err), 409)
            doc_store.put(db, uid, "transform_plan", "current", plan)
            return plan
        return {"status": "success", "plan": await run_in_threadpool(run)}

    @router.post("/fitness/transform/finish")
    async def transform_finish(request: Request, authorization: str | None = Header(default=None)):
        uid = await run_in_threadpool(uid_of, authorization)

        def run():
            plan = current_plan(uid)
            rec = records(db, uid)
            weight = rec["latest_weight_kg"] or plan["targets"]["current_weight_kg"]
            try:
                done = T.finish(plan, weight, plan["targets"]["tdee_kcal"])
            except ValueError as err:
                raise _bad(str(err), 409)
            doc_store.put(db, uid, "transform_plan", "current", done)
            return done
        return {"status": "success", "plan": await run_in_threadpool(run)}

    @router.put("/fitness/transform/goal")
    async def transform_goal(request: Request, authorization: str | None = Header(default=None)):
        uid = await run_in_threadpool(uid_of, authorization)
        b = await _json(request)
        target = _num(b, "target_weight_kg", *K.MIN_PLAUSIBLE["weight_kg"])
        if target is None:
            raise _bad("target_weight_kg is required")

        def run():
            plan = current_plan(uid)
            result, profile, ep, _t = do_screen(uid, {**b, "target_weight_kg": target})
            try:
                new = T.edit_goal(ep, plan, target, result)
            except ValueError as err:
                raise _bad(str(err), 403)
            doc_store.put(db, uid, "transform_plan", "current", new)
            return new
        return {"status": "success", "plan": await run_in_threadpool(run)}

    @router.get("/fitness/transform/report")
    def transform_report(authorization: str | None = Header(default=None)):
        uid = uid_of(authorization)
        plan = current_plan(uid)
        today = local_today()
        inp = checkin_inputs(uid, plan, today)
        return {"status": "success", "report": T.progress_report(plan, inp["weights"], inp["intake"])}

    return router
