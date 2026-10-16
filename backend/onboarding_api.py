"""First-run setup API: /onboarding/questions, /onboarding/state, PUT /onboarding/answers, POST /onboarding/complete and GET /experience.

Storage is signed documents (doc_store), so there is no schema change: kind `onboarding` / key `v1` holds the answers, kind `experience` /
key `main` holds the personalisation built from them. Completing also fills the stores the rest of the app already reads (profile, body
profile, cycle settings, conditions, allergies, AI consent) through their own validators, best effort and one by one.

Safety: free text goes through the safety engine first. Crisis wording returns the deterministic response and the text is not stored.
Under 18: nothing but the age gate is stored. Nothing here calls an AI model and nothing is diagnosed.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Callable

from fastapi import APIRouter, Body, Header, HTTPException

import consent
import chat_cache
import ops_telemetry
import doc_store
import onboarding as ob
from calc_core import local_today
from health_logs import DOMAINS, list_domain, save_domain
from safety_engine import assess_safety, emergency_response, urgent_fallback_response

KIND, KEY = "onboarding", "v1"
EXP_KIND, EXP_KEY = "experience", "main"


def _log(operation: str, error: Exception) -> None:
    try:
        from logging_util import logger
        logger.warning(component="ONBOARDING", operation=operation, error=error, fallback_action="continue")   # never the answers
    except Exception:  # noqa: BLE001
        pass


def style_block_for(db: Any, uid: str) -> str:
    """The style lines for this person's chat replies, or "" (no setup yet, or any read problem: chat must never wait on or fail for this)."""
    try:
        return ob.style_block(doc_store.get(db, uid, EXP_KIND, EXP_KEY))
    except Exception:  # noqa: BLE001
        return ""


def build_router(get_user: Callable[[str | None], Any], db: Any) -> APIRouter:
    router = APIRouter()

    def uid_of(authorization: str | None) -> str:
        return str(get_user(authorization).id)

    # ---- reading what already exists, so people who were here before are not asked again --------------------------
    def prefill(uid: str, today: date) -> dict[str, Any]:
        out: dict[str, Any] = {}
        try:
            rows = db.table("profiles").select("display_name,date_of_birth").eq("id", uid).limit(1).execute().data or []
            if rows:
                if rows[0].get("display_name"):
                    out["preferred_name"] = str(rows[0]["display_name"]).strip()[:40]
                if rows[0].get("date_of_birth"):
                    out["birth_date"] = str(rows[0]["date_of_birth"])[:10]
        except Exception as exc:  # noqa: BLE001
            _log("prefill_profile", exc)
        try:
            body = doc_store.get(db, uid, "profile", "me") or {}
            if body.get("birth_date") and "birth_date" not in out:
                out["birth_date"] = str(body["birth_date"])[:10]
            if body.get("height_cm") or body.get("weight_kg"):
                out["height_weight"] = {k: body[k] for k in ("height_cm", "weight_kg") if isinstance(body.get(k), (int, float))}
            if body.get("diet_style") in {o["id"] for o in ob.BY_ID["diet_style"]["options"]}:
                out["diet_style"] = body["diet_style"]
            if body.get("activity_level") in {o["id"] for o in ob.BY_ID["activity"]["options"]}:
                out["activity"] = body["activity_level"]
        except Exception as exc:  # noqa: BLE001
            _log("prefill_body", exc)
        # a prefilled value must still be valid today; anything that is not is simply not offered
        clean: dict[str, Any] = {}
        for qid, value in out.items():
            try:
                clean[qid] = ob.clean_answer(ob.BY_ID[qid], value, {**clean, qid: value}, today)
            except ob.AnswerError:
                continue
        return clean

    def load(uid: str, today: date) -> dict[str, Any]:
        doc = doc_store.get(db, uid, KIND, KEY) or {}
        under_18 = doc.get("age_gate") == "under_18"
        stored = doc.get("answers") if isinstance(doc.get("answers"), dict) else {}
        pre = {} if (under_18 or doc.get("completed_at")) else {k: v for k, v in prefill(uid, today).items() if k not in stored}
        answers = {**pre, **stored}
        missing = ob.required_missing(answers, today) if not under_18 else list(ob.REQUIRED)
        return {"doc": doc, "under_18": under_18, "answers": answers, "prefilled": sorted(pre), "stored": stored, "missing": missing}

    def state_payload(uid: str, today: date) -> dict[str, Any]:
        s = load(uid, today)
        complete = bool(s["doc"].get("completed_at")) and not s["under_18"] and not s["missing"]
        return {"status": "success", "complete": complete, "under_18": s["under_18"], "step": int(s["doc"].get("step") or 0),
                "answers": {} if s["under_18"] else s["answers"], "prefilled": s["prefilled"], "required_missing": s["missing"],
                "visible": [] if s["under_18"] else ob.visible_ids(s["answers"], today), "bank_version": ob.BANK_VERSION,
                "bank_changed": bool(s["doc"].get("completed_at")) and s["doc"].get("bank_version") != ob.BANK_VERSION}

    # ---- routes ----------------------------------------------------------------------------------------------------------
    @router.get("/onboarding/questions")
    def questions(authorization: str | None = Header(default=None)):
        uid_of(authorization)
        return {"status": "success", "version": ob.BANK_VERSION, "steps": ob.STEPS, "questions": ob.QUESTIONS, "titles_hi": ob.TITLES_HI,
                "required": list(ob.REQUIRED), "min_age": ob.MIN_AGE}

    @router.get("/onboarding/state")
    def state(authorization: str | None = Header(default=None)):
        uid = uid_of(authorization)
        return state_payload(uid, local_today())

    @router.put("/onboarding/answers")
    def save_answers(payload: dict = Body(...), authorization: str | None = Header(default=None)):
        uid = uid_of(authorization)
        today = local_today()
        patch = payload.get("answers")
        if not isinstance(patch, dict) or len(patch) > 40:
            raise HTTPException(status_code=422, detail="answers must be an object")
        step = payload.get("step")
        s = load(uid, today)
        # 18 and over only. A younger person's answers are never stored, and the gate is all that is kept.
        if "birth_date" in patch and patch["birth_date"] not in (None, ""):
            try:
                born = ob.clean_answer(ob.BY_ID["birth_date"], patch["birth_date"], {}, today)
            except ob.AnswerError as err:
                raise HTTPException(status_code=422, detail={"field": err.qid, "message": err.message})
            if (ob.age_on(born, today) or 0) < ob.MIN_AGE:
                ops_telemetry.funnel("under_18")
                doc_store.put(db, uid, KIND, KEY, {"age_gate": "under_18", "at": datetime.now(timezone.utc).isoformat(), "bank_version": ob.BANK_VERSION})
                return {"status": "success", "under_18": True}
        if s["under_18"]:
            raise HTTPException(status_code=403, detail={"code": "under_18", "message": "Bubbles is for people 18 and over for now."})
        # free text first: crisis wording is answered, never stored
        safety = None
        clean_patch = dict(patch)
        for field in ob.FREE_TEXT:
            text = clean_patch.get(field)
            if isinstance(text, str) and text.strip():
                a = assess_safety(text)
                if a.state in ("URGENT", "EMERGENCY") or a.crisis:
                    clean_patch.pop(field, None)
                    safety = {"field": field, "level": a.level, "state": a.state,
                              "message": emergency_response(a) if (a.state == "EMERGENCY" or a.crisis) else urgent_fallback_response(a)}
        try:
            answers, dropped, skipped = ob.apply_answers(s["answers"], clean_patch, today)
        except ob.AnswerError as err:
            raise HTTPException(status_code=422, detail={"field": err.qid, "message": err.message})
        doc = {**s["doc"], "answers": answers, "bank_version": ob.BANK_VERSION, "updated_at": datetime.now(timezone.utc).isoformat()}
        doc.pop("age_gate", None)
        if "started_at" not in doc:
            ops_telemetry.funnel(ob.STEPS[0]["id"])   # the first save: the setup was started
        doc.setdefault("started_at", doc["updated_at"])
        if isinstance(step, int) and 0 <= step <= len(ob.STEPS):
            if step > int(s["doc"].get("step") or 0) and step < len(ob.STEPS):
                ops_telemetry.funnel(ob.STEPS[step]["id"])   # a step reached for the first time: a count, never an answer
            doc["step"] = step
        doc_store.put(db, uid, KIND, KEY, doc)
        out = state_payload(uid, today)
        out.update({"dropped": dropped, "skipped": skipped, "safety": safety})
        return out

    @router.post("/onboarding/complete")
    def complete(authorization: str | None = Header(default=None)):
        uid = uid_of(authorization)
        today = local_today()
        s = load(uid, today)
        if s["under_18"]:
            raise HTTPException(status_code=403, detail={"code": "under_18", "message": "Bubbles is for people 18 and over for now."})
        answers = s["answers"]
        missing = ob.required_missing(answers, today)
        if missing:
            raise HTTPException(status_code=422, detail={"message": "A few required questions are still open.", "missing": missing})
        exp = ob.build_experience(answers, today)
        wrote: list[str] = []

        def attempt(name: str, fn: Callable[[], None]) -> None:
            try:
                fn()
                wrote.append(name)
            except Exception as exc:  # noqa: BLE001 - one store failing must not undo the others or lose the answers
                _log(name, exc)

        body = answers.get("body")
        attempt("profile", lambda: db.table("profiles").upsert(
            {"id": uid, "display_name": answers["preferred_name"], "date_of_birth": answers["birth_date"],
             "gender": {"female": "female", "male": "male", "trans": "transgender", "other": "other"}.get(body, None)}, on_conflict="id").execute())

        def body_profile() -> None:
            from fitness_api import clean_profile
            patch: dict[str, Any] = {"birth_date": answers["birth_date"], "formula_basis": exp["fitness"]["formula_basis"]}
            hw = answers.get("height_weight") or {}
            patch.update({k: hw[k] for k in ("height_cm", "weight_kg") if k in hw})
            if answers.get("activity"):
                patch["activity_level"] = answers["activity"]
            if answers.get("diet_style"):
                patch["diet_style"] = answers["diet_style"]
            reason = answers.get("periods_reason")
            if reason == "pregnant":
                patch["pregnant"] = True
            if reason in ("recently_gave_birth", "breastfeeding"):
                patch["postpartum"] = True
            if reason == "breastfeeding":
                patch["breastfeeding"] = True
            if answers.get("pregnancy_plans") == "trying":
                patch["trying_to_conceive"] = True
            if answers.get("periods") in ("regular", "irregular"):
                patch["menstruating"] = True
            doc_store.put(db, uid, "profile", "me", clean_profile(patch, doc_store.get(db, uid, "profile", "me") or {}))

        attempt("body_profile", body_profile)

        def cycle_settings() -> None:
            if exp["sections"]["hidden"] and "cycle" in exp["sections"]["hidden"]:
                return                                  # a male body: Cycle is not set up
            from cycle_api import SETTINGS_KIND, _merge_settings, _settings
            patch: dict[str, Any] = {"mode": exp["cycle"]["mode"]}
            if answers.get("due_date"):
                patch["pregnancy"] = {"due_date": answers["due_date"]}
            if answers.get("baby_birth_date"):
                patch["postpartum"] = {"delivery_date": answers["baby_birth_date"], "breastfeeding": answers.get("periods_reason") == "breastfeeding" or None}
            current = _settings(db, uid)
            doc_store.put(db, uid, SETTINGS_KIND, "main", _merge_settings(current, patch, today))

        attempt("cycle_settings", cycle_settings)

        def last_period() -> None:
            if answers.get("last_period") and answers.get("periods") in ("regular", "irregular"):
                save_domain(db, "cycle", DOMAINS["cycle"], uid, {"phase": "period", "date": answers["last_period"]})

        attempt("last_period", last_period)

        def known(slug: str, field: str) -> set[str]:
            try:
                return {str(e.get(field) or "").strip().lower() for e in list_domain(db, slug, DOMAINS[slug], uid, 730)["entries"]}
            except Exception:  # noqa: BLE001
                return set()

        def conditions() -> None:
            names = {"diabetes": "Diabetes", "prediabetes": "Prediabetes", "high_bp": "High blood pressure", "thyroid": "Thyroid condition",
                     "pcos": "PCOS or PCOD", "asthma_copd": "Asthma or COPD", "heart": "Heart condition", "migraine": "Migraine",
                     "anaemia": "Anaemia", "depression_anxiety": "Depression or anxiety", "kidney": "Kidney condition", "liver": "Liver condition",
                     "arthritis": "Arthritis"}
            have = known("conditions", "condition_name")
            for cond in ob._picked(answers.get("conditions")):
                if cond in names and names[cond].lower() not in have:        # running setup again never adds a second copy
                    save_domain(db, "conditions", DOMAINS["conditions"], uid, {"condition_name": names[cond], "status": "told by you at setup"})
            other = answers.get("conditions_other")
            if other and other.lower() not in have:
                save_domain(db, "conditions", DOMAINS["conditions"], uid, {"condition_name": other, "status": "told by you at setup"})

        attempt("conditions", conditions)

        def allergies() -> None:
            have = known("allergies", "allergen")
            labels = {"food": "Food allergy", "medicine": "Medicine allergy", "dust_pollen": "Dust or pollen allergy", "other": "Other allergy"}
            for kind in ob._picked(answers.get("allergy_types")):
                if kind in labels and labels[kind].lower() not in have:
                    save_domain(db, "allergies", DOMAINS["allergies"], uid, {"allergen": labels[kind], "notes": "Told by you at setup"})

        attempt("allergies", allergies)
        if answers.get("ai_consent") == "yes":
            attempt("consent", lambda: consent.set_ai_chat(db, uid, True))

        now = datetime.now(timezone.utc).isoformat()
        try:
            doc_store.put(db, uid, EXP_KIND, EXP_KEY, {**exp, "built_at": now})
            chat_cache.forget_user(uid)   # the next reply reads the new tone settings and profile
            doc_store.put(db, uid, KIND, KEY, {**s["doc"], "answers": answers, "completed_at": now, "bank_version": ob.BANK_VERSION, "step": len(ob.STEPS)})
            ops_telemetry.funnel("completed")
        except Exception as exc:  # noqa: BLE001
            _log("save_experience", exc)
            raise HTTPException(status_code=503, detail="Your answers are saved, but Bubbles couldn't finish setting up just now. Please try again.")
        return {"status": "success", "experience": exp, "applied": [{"id": f"line-{i}", "label": line} for i, line in enumerate(ob.setup_lines(exp))]}

    @router.get("/experience")
    def experience(authorization: str | None = Header(default=None)):
        uid = uid_of(authorization)
        doc = doc_store.get(db, uid, EXP_KIND, EXP_KEY)
        return {"status": "success", "experience": doc if isinstance(doc, dict) else None}

    return router
