"""Routes for sleep, hydration, medications, mind and notifications: ``app.include_router(wellness_api.build_router(get_user, db))``.

Every route is async, calls ``get_user(authorization)`` first (in a thread), runs its database work in a thread pool and only
reads or writes the signed-in user's rows. Bodies are parsed by hand so every malformed request is a 422 whose ``detail`` is a
plain string; engine input errors (``InputError``) carry user-safe messages and nothing here returns raw exception text.
Free text always goes through the safety engine first (see ``mind_checkins.safety_gate``).
"""
from __future__ import annotations

import re
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

from fastapi import APIRouter, Header, HTTPException, Query, Request
from starlette.concurrency import run_in_threadpool

import association_loader as AL
import clinical_constants as K
import consent
import doc_store
import hydration_engine as H
import med_schedule as M
import mind_checkins as Mind
import notifications as N
import push_fcm
import sleep_engine as S
import wellness_common as W
from health_logs import DOMAINS, list_domain, save_domain
from wellness_common import InputError

SID = re.compile(r"^[a-f0-9]{12}$")
JID = re.compile(r"^[a-f0-9]{16}$")
DAY_RANGE = 30


def build_router(get_user: Callable[[str | None], Any], db: Any) -> APIRouter:
    router = APIRouter()

    # --- plumbing ------------------------------------------------------------------------------------------------------
    async def auth(authorization: str | None) -> tuple[str, Any]:
        user = await run_in_threadpool(get_user, authorization)
        return str(user.id), user

    async def body_of(request: Request) -> dict:
        try:
            body = await request.json()
        except (ValueError, RecursionError):
            raise HTTPException(status_code=422, detail="Request body must be valid JSON")
        if not isinstance(body, dict):
            raise HTTPException(status_code=422, detail="Request body must be a JSON object")
        return body

    async def run(fn: Callable[..., Any], *args: Any) -> Any:
        try:
            return await run_in_threadpool(fn, *args)
        except InputError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    def clock(uid: str, tz: int | None = None) -> tuple[dict, int, datetime, datetime]:
        settings = N.load_settings(db, uid)
        offset = W.tz_offset(tz) if tz is not None else (W.request_tz() if W.request_tz() is not None else settings["tz_offset_minutes"])
        now = datetime.now(timezone.utc)
        return settings, offset, now, W.local_now(now, offset)

    def pick_day(raw: Any, today: date, label: str = "date", back: int = DAY_RANGE) -> date:
        if raw in (None, ""):
            return today
        d = W.parse_date(raw, label)
        if d > today:
            raise InputError(f"{label} can't be in the future")
        if (today - d).days > back:
            raise InputError(f"{label} can be at most {back} days ago")
        return d

    def ok(**kw: Any) -> dict:
        return {"status": "success", **kw}

    TZ = Query(default=None, ge=-840, le=840)

    # =========================================================== SLEEP =====================================================
    def sleep_overview(uid: str, days: int, tz: int | None) -> dict:
        _s, _off, _now, local = clock(uid, tz)
        profile = W.load_profile(db, uid)
        goal = S.resolve_goal(profile["age"], S.load_goal(db, uid))
        out = S.overview(S.load_entries(db, uid, days + 2), S.load_details(db, uid), goal=goal, today=local.date(), days=days)
        out["tags"] = list(K.SLEEP_TAGS)
        return ok(**out)

    @router.get("/wellness/sleep/overview")
    async def sleep_overview_route(days: int = Query(default=30, ge=7, le=180), tz_offset_minutes: int | None = TZ,
                                   authorization: str | None = Header(default=None)):
        uid, _ = await auth(authorization)
        return await run(sleep_overview, uid, days, tz_offset_minutes)

    def sleep_goal_set(uid: str, body: dict) -> dict:
        goal = S.normalize_goal(body)
        doc_store.put(db, uid, "sleep_goal", "me", goal)
        return ok(goal=S.resolve_goal(W.load_profile(db, uid)["age"], goal))

    @router.post("/wellness/sleep/goal")
    async def sleep_goal(request: Request, authorization: str | None = Header(default=None)):
        uid, _ = await auth(authorization)
        return await run(sleep_goal_set, uid, await body_of(request))

    def sleep_log(uid: str, body: dict, tz: int | None) -> dict:
        _s, _off, _now, local = clock(uid, tz)
        day = pick_day(body.get("date"), local.date())
        notes = W.text(body.get("notes"), 1000, "notes")
        blocked = Mind.safety_gate(notes)
        if blocked:
            return blocked
        details = S.normalize_details(body)
        hours = W.number(body.get("duration"), 0.25, 24, "duration")
        if hours is None and details.get("bedtime") and details.get("wake"):
            hours = S.duration_hours(details["bedtime"], details["wake"])
        quality = W.number(body.get("quality"), 1, 10, "quality")
        if hours is None and not details.get("nap_minutes"):
            raise InputError("add how long you slept (duration), or a bedtime and wake time, or a nap")
        entry = None
        if hours is not None:
            row = {"duration": hours, "date": day.isoformat()}
            if quality is not None:
                row["quality"] = quality
            if notes:
                row["notes"] = notes
            entry = save_domain(db, "sleep", DOMAINS["sleep"], uid, row)["entry"]
        if details:
            doc_store.put(db, uid, "sleep_tags", day.isoformat(), details, when=f"{day.isoformat()}T12:00:00+00:00")
        return ok(entry=entry, details=details)

    @router.post("/wellness/sleep/log", status_code=201)
    async def sleep_log_route(request: Request, tz_offset_minutes: int | None = TZ, authorization: str | None = Header(default=None)):
        uid, _ = await auth(authorization)
        return await run(sleep_log, uid, await body_of(request), tz_offset_minutes)

    # ========================================================= HYDRATION ===================================================
    def hydration_view(uid: str, day: date, tz: int | None, *, state: dict | None = None) -> dict:
        settings, off, now, local = clock(uid, tz)
        profile = W.load_profile(db, uid)
        flags = W.load_condition_flags(db, uid, profile)
        iso = day.isoformat()
        goal = H.daily_goal(profile["weight_kg"], H.exercise_minutes_on(db, uid, iso, off, (local.date() - day).days + 2),
                            profile["pregnant"], profile["breastfeeding"], flags["fluid_restricted"])
        entries = H.load_entries(db, uid, min(40, (local.date() - day).days + 2))
        state = state if state is not None else H.load_state(db, uid)
        q = settings["quiet_hours"]
        wake, sleep = (W.parse_hhmm(q["end"]), W.parse_hhmm(q["start"])) if q.get("enabled") else (7 * 60, 22 * 60)
        view = H.overview(entries, day=iso, now_min=local.hour * 60 + local.minute, goal=goal, state=state, tz_offset_min=off,
                          wake_min=wake, sleep_min=sleep, today=local.date().isoformat())
        if goal["goal_ml"] is not None and view["effective_ml"] >= goal["goal_ml"] and iso not in (state.get("met_dates") or []):
            H.save_state(db, uid, H.mark_met(state, iso))   # idempotent: keeps the streak and garden even for drinks logged elsewhere
        return ok(**view)

    @router.get("/wellness/hydration/overview")
    async def hydration_overview(date_: str | None = Query(default=None, alias="date"), tz_offset_minutes: int | None = TZ,
                                 authorization: str | None = Header(default=None)):
        uid, _ = await auth(authorization)

        def work() -> dict:
            local = clock(uid, tz_offset_minutes)[3]
            return hydration_view(uid, pick_day(date_, local.date()), tz_offset_minutes)
        return await run(work)

    def hydration_log(uid: str, body: dict, tz: int | None) -> dict:
        settings, off, now, local = clock(uid, tz)
        ml = H.volume_from_body(body)
        kind = H.normalize_type(body.get("type"))
        day = pick_day(body.get("date"), local.date())
        row: dict[str, Any] = {"volume": ml, "type": kind}
        if body.get("date") not in (None, "") and day != local.date():   # a backfilled day is stored at that day's local noon
            row["date"] = (datetime(day.year, day.month, day.day, 12) - timedelta(minutes=off)).replace(tzinfo=timezone.utc).isoformat()
        saved = save_domain(db, "hydration", DOMAINS["hydration"], uid, row)
        state = H.add_ml(H.load_state(db, uid), H.hydrating_ml(ml, kind))
        H.save_state(db, uid, state)
        return {**hydration_view(uid, day, tz, state=state), "logged": {"ml": ml, "type": kind, "hydrating_ml": round(H.hydrating_ml(ml, kind)),
                                                                         "entry": saved["entry"]}}

    @router.post("/wellness/hydration/log", status_code=201)
    async def hydration_log_route(request: Request, tz_offset_minutes: int | None = TZ, authorization: str | None = Header(default=None)):
        uid, _ = await auth(authorization)
        return await run(hydration_log, uid, await body_of(request), tz_offset_minutes)

    # ======================================================== MEDICATIONS ==================================================
    def sid_ok(sid: str) -> str:
        if not SID.match(sid):
            raise HTTPException(status_code=404, detail="Schedule not found")
        return sid

    def warnings_for(uid: str, schedules: list[dict]) -> dict:
        names = [s["name"] for s in schedules if s.get("active", True)]
        return {"interactions": M.check_interactions(names) if names else [], "allergy_warnings": M.allergy_warnings(names, W.load_allergies(db, uid))}

    def schedules_list(uid: str, tz: int | None) -> dict:
        local = clock(uid, tz)[3]
        schedules = M.load_schedules(db, uid)
        items = [{**s, "describe": M.describe(s), "refill": M.refill_status(s, local.date())} for s in schedules]
        return ok(schedules=items, **warnings_for(uid, schedules), note="Bubbles stores what you enter. It never changes a dose or recommends a medicine.")

    @router.get("/wellness/meds/schedules")
    async def meds_schedules(tz_offset_minutes: int | None = TZ, authorization: str | None = Header(default=None)):
        uid, _ = await auth(authorization)
        return await run(schedules_list, uid, tz_offset_minutes)

    def schedule_create(uid: str, body: dict, tz: int | None) -> dict:
        local = clock(uid, tz)[3]
        if len(M.load_schedules(db, uid)) >= M.MAX_SCHEDULES:
            raise InputError("that's the most medicines Bubbles can hold; remove one first")
        sched = {**M.normalize_schedule(body, local.date()), "id": uuid.uuid4().hex[:12]}
        M.save_schedule(db, uid, sched)
        return ok(schedule={**sched, "describe": M.describe(sched)}, **warnings_for(uid, M.load_schedules(db, uid)))

    @router.post("/wellness/meds/schedules", status_code=201)
    async def meds_schedule_create(request: Request, tz_offset_minutes: int | None = TZ, authorization: str | None = Header(default=None)):
        uid, _ = await auth(authorization)
        return await run(schedule_create, uid, await body_of(request), tz_offset_minutes)

    def schedule_update(uid: str, sid: str, body: dict, tz: int | None) -> dict:
        existing = M.load_schedule(db, uid, sid)
        if not existing:
            raise HTTPException(status_code=404, detail="Schedule not found")
        local = clock(uid, tz)[3]
        merged = {k: v for k, v in existing.items() if k != "id"}
        merged.update(body)
        sched = {**M.normalize_schedule(merged, local.date()), "id": sid}
        M.save_schedule(db, uid, sched)
        return ok(schedule={**sched, "describe": M.describe(sched)}, **warnings_for(uid, M.load_schedules(db, uid)))

    @router.put("/wellness/meds/schedules/{sid}")
    async def meds_schedule_update(sid: str, request: Request, tz_offset_minutes: int | None = TZ, authorization: str | None = Header(default=None)):
        uid, _ = await auth(authorization)
        return await run(schedule_update, uid, sid_ok(sid), await body_of(request), tz_offset_minutes)

    @router.delete("/wellness/meds/schedules/{sid}")
    async def meds_schedule_delete(sid: str, authorization: str | None = Header(default=None)):
        uid, _ = await auth(authorization)
        if not await run(doc_store.delete, db, uid, "med_schedule", sid_ok(sid)):
            raise HTTPException(status_code=404, detail="Schedule not found")
        return ok(deleted=True)

    def meds_today(uid: str, tz: int | None) -> dict:
        local = clock(uid, tz)[3]
        schedules = M.load_schedules(db, uid)
        docs = M.dose_docs_for_day(M.load_dose_docs(db, uid, 1), local.date().isoformat())
        today = M.due_list(schedules, docs, local)
        refills = [{"schedule_id": s["id"], "name": s["name"], **r} for s in schedules if (r := M.refill_status(s, local.date())) and r["alert"]]
        return ok(**today, refill_alerts=refills, missed_dose_help=M.MISSED_MESSAGE, snooze_options=list(K.MED_SNOOZE_OPTIONS_MIN),
                  skip_reasons=list(K.MED_SKIP_REASONS), **warnings_for(uid, schedules))

    @router.get("/wellness/meds/today")
    async def meds_today_route(tz_offset_minutes: int | None = TZ, authorization: str | None = Header(default=None)):
        uid, _ = await auth(authorization)
        return await run(meds_today, uid, tz_offset_minutes)

    def dose_record(uid: str, body: dict, tz: int | None) -> dict:
        _s, _off, now, local = clock(uid, tz)
        sid = body.get("schedule_id")
        if not isinstance(sid, str) or not SID.match(sid):
            raise InputError("choose a medicine")
        sched = M.load_schedule(db, uid, sid)
        if not sched:
            raise HTTPException(status_code=404, detail="Schedule not found")
        day = pick_day(body.get("date"), local.date())
        key = f"{sid}:{day.isoformat()}"
        payload, rec, delta = M.record_dose(sched, doc_store.get(db, uid, "med_dose", key), day=day, time_key=body.get("time"),
                                            status=body.get("status"), now_utc=now, now_local=local, reason=body.get("reason"),
                                            snooze_minutes=body.get("snooze_minutes"), site=body.get("site"))
        M.save_dose_doc(db, uid, payload)
        updated = M.apply_pill_delta(sched, delta)
        if updated is not sched:
            M.save_schedule(db, uid, updated)
        return ok(record=rec, refill=M.refill_status(updated, local.date()))

    @router.post("/wellness/meds/dose", status_code=201)
    async def meds_dose(request: Request, tz_offset_minutes: int | None = TZ, authorization: str | None = Header(default=None)):
        uid, _ = await auth(authorization)
        return await run(dose_record, uid, await body_of(request), tz_offset_minutes)

    def interactions(uid: str, body: dict) -> dict:
        names = list(body.get("names") or []) if isinstance(body.get("names") or [], list) else None
        if names is None:
            raise InputError("names must be a list of medicines")
        ctx = body.get("context")
        if isinstance(ctx, dict) and ctx.get("calorie_deficit") is True:
            names.append("calorie deficit")
        if body.get("include_my_medicines") is True:
            names += [s["name"] for s in M.load_schedules(db, uid) if s.get("active", True)]
        clean = M._clean_names(names, 40)
        expanded = M.expand_names(clean)
        return ok(checked=clean, interactions=M.check_interactions(expanded), allergy_warnings=M.allergy_warnings(clean, W.load_allergies(db, uid)),
                  lookup="rxnav+curated" if M.rxnav_enabled() else "curated",
                  note="This is a short, curated list and is not complete. A pharmacist can check everything you take together.")

    @router.post("/wellness/meds/interactions")
    async def meds_interactions(request: Request, authorization: str | None = Header(default=None)):
        uid, _ = await auth(authorization)
        return await run(interactions, uid, await body_of(request))

    @router.get("/wellness/meds/adherence")
    async def meds_adherence(days: int = Query(default=30, ge=7, le=90), tz_offset_minutes: int | None = TZ,
                             authorization: str | None = Header(default=None)):
        uid, _ = await auth(authorization)

        def work() -> dict:
            local = clock(uid, tz_offset_minutes)[3]
            return ok(**M.adherence(M.load_schedules(db, uid), M.load_dose_docs(db, uid, days), local, days))
        return await run(work)

    def glp1_view(uid: str, tz: int | None) -> dict:
        local = clock(uid, tz)[3]
        schedules = M.load_schedules(db, uid)
        sched = next((s for s in schedules if s["kind"] == "glp1" and s.get("active", True)), None)
        names = [s["name"] for s in schedules]
        detected = bool(W.load_condition_flags(db, uid, None, names)["glp1"])
        return ok(detected=detected or sched is not None, **M.glp1_overview(sched, M.load_dose_docs(db, uid, 60), M.load_glp1_logs(db, uid), local))

    @router.get("/wellness/meds/glp1")
    async def meds_glp1(tz_offset_minutes: int | None = TZ, authorization: str | None = Header(default=None)):
        uid, _ = await auth(authorization)
        return await run(glp1_view, uid, tz_offset_minutes)

    def glp1_log(uid: str, body: dict, tz: int | None) -> dict:
        local = clock(uid, tz)[3]
        notes = W.text(body.get("notes"), 500, "notes")
        blocked = Mind.safety_gate(notes)
        if blocked:
            return blocked
        day = pick_day(body.get("date"), local.date())
        entry = M.normalize_glp1_log(body)
        if notes:
            entry["notes"] = notes
        doc_store.put(db, uid, "glp1_log", day.isoformat(), entry)
        nudges = glp1_view(uid, tz)["nudges"]
        return ok(entry={"date": day.isoformat(), **entry}, nudges=nudges)

    @router.post("/wellness/meds/glp1/log", status_code=201)
    async def meds_glp1_log(request: Request, tz_offset_minutes: int | None = TZ, authorization: str | None = Header(default=None)):
        uid, _ = await auth(authorization)
        return await run(glp1_log, uid, await body_of(request), tz_offset_minutes)

    @router.get("/wellness/meds/logbook")
    async def meds_logbook(days: int = Query(default=30, ge=7, le=180), tz_offset_minutes: int | None = TZ,
                           authorization: str | None = Header(default=None)):
        uid, _ = await auth(authorization)

        def work() -> dict:
            local = clock(uid, tz_offset_minutes)[3]
            return ok(**M.logbook(M.load_schedules(db, uid), M.load_dose_docs(db, uid, days), local, days, W.load_allergies(db, uid),
                                  M.load_glp1_logs(db, uid, 30)))
        return await run(work)

    # ============================================================= MIND ====================================================
    def sync_pixels(uid: str, year: int, tz: int) -> dict[str, dict]:
        entries = Mind.load_mood_entries(db, uid, 366)
        recent = {d: v for d, v in Mind.per_day_moods(entries, tz).items() if d.startswith(str(year))}
        stored = Mind.load_pixels(db, uid, year)
        oldest = min(Mind.per_day_moods(entries, tz), default=None) if len(entries) >= 200 else None   # row cap hit: oldest day may be partial
        merged = Mind.merge_pixels(stored, recent, oldest)
        if merged != stored:
            Mind.save_pixels(db, uid, year, merged)
        return merged

    def mind_checkin(uid: str, body: dict, tz: int | None) -> dict:
        _s, off, _now, local = clock(uid, tz)
        c = Mind.normalize_checkin(body)
        blocked = Mind.safety_gate(c.get("notes"))
        if blocked:
            return blocked
        day = pick_day(body.get("date"), local.date())
        row = Mind.tracker_body(c, day.isoformat() if body.get("date") not in (None, "") else None)
        saved = save_domain(db, "mood", DOMAINS["mood"], uid, row)
        sync_pixels(uid, local.year, off)
        out = ok(entry=saved["entry"], level=Mind.level_of(c["mood"]), activities=c["activities"])
        if c["mood"] <= 2:
            out["support"] = ("Sorry it's a rough one. A short breathing exercise may help, and talking to someone you trust can too. "
                              + Mind.SUPPORT_NOTE)
        return out

    @router.post("/wellness/mind/checkin", status_code=201)
    async def mind_checkin_route(request: Request, tz_offset_minutes: int | None = TZ, authorization: str | None = Header(default=None)):
        uid, _ = await auth(authorization)
        return await run(mind_checkin, uid, await body_of(request), tz_offset_minutes)

    def mind_overview(uid: str, days: int, tz: int | None) -> dict:
        _s, off, _now, local = clock(uid, tz)
        entries = Mind.load_mood_entries(db, uid, days)
        by_day = Mind.per_day_moods(entries, off)
        vals = [e["mood"] for e in entries if isinstance(e.get("mood"), (int, float))]
        screens = doc_store.list_docs(db, uid, "mind_screen", limit=20)
        return ok(window_days=days, entries=[{**e, "activities": Mind.parse_activities(e.get("notes"))} for e in entries[:60]],
                  average_mood=round(sum(vals) / len(vals), 1) if vals else None, days_logged=len(by_day),
                  today=by_day.get(local.date().isoformat()), faces=Mind.FACES, support=Mind.SUPPORT_COPY, activities=list(K.MIND_ACTIVITIES),
                  screen=Mind.screen_due(screens, local.date()), exercises=[{"id": e["id"], "name": e["name"], "kind": e["kind"]} for e in Mind.EXERCISES],
                  note="Mood tracking is for your own insight and doesn't replace support from a professional.")

    @router.get("/wellness/mind/overview")
    async def mind_overview_route(days: int = Query(default=30, ge=7, le=180), tz_offset_minutes: int | None = TZ,
                                  authorization: str | None = Header(default=None)):
        uid, _ = await auth(authorization)
        return await run(mind_overview, uid, days, tz_offset_minutes)

    @router.get("/wellness/mind/pixels")
    async def mind_pixels(year: int | None = Query(default=None, ge=2000, le=2100), tz_offset_minutes: int | None = TZ,
                          authorization: str | None = Header(default=None)):
        uid, _ = await auth(authorization)

        def work() -> dict:
            _s, off, _now, local = clock(uid, tz_offset_minutes)
            y = year or local.year
            return ok(**Mind.year_pixels(sync_pixels(uid, y, off), y))
        return await run(work)

    @router.get("/wellness/mind/topics")
    async def mind_topics_copy(authorization: str | None = Header(default=None)):
        await auth(authorization)
        return ok(topics=Mind.TOPIC_COPY)

    @router.get("/wellness/mind/screen")
    async def mind_screen_questions(kind: str = Query(default="phq2", max_length=10), authorization: str | None = Header(default=None)):
        await auth(authorization)
        return await run(lambda: ok(**Mind.screen_questions(kind)))

    def screen_submit(uid: str, body: dict, tz: int | None) -> dict:
        local = clock(uid, tz)[3]
        result = Mind.score_screen(body.get("kind"), body.get("answers"))
        day = local.date().isoformat()
        doc_store.put(db, uid, "mind_screen", f"{result['kind']}:{day}", {"kind": result["kind"], "score": result["score"],
                                                                         "positive": result["suggest_talking_to_someone"], "date": day})
        return ok(**result)

    @router.post("/wellness/mind/screen", status_code=201)
    async def mind_screen_submit(request: Request, tz_offset_minutes: int | None = TZ, authorization: str | None = Header(default=None)):
        uid, _ = await auth(authorization)
        return await run(screen_submit, uid, await body_of(request), tz_offset_minutes)

    def journal_add(uid: str, body: dict, tz: int | None) -> dict:
        local = clock(uid, tz)[3]
        entry = Mind.normalize_journal(body)
        blocked = Mind.safety_gate(entry["text"])
        if blocked:
            return blocked
        jid = uuid.uuid4().hex[:16]
        payload = {"id": jid, "date": local.date().isoformat(), **entry, "created_at": datetime.now(timezone.utc).isoformat()}
        doc_store.put(db, uid, "journal", jid, payload, when=payload["created_at"])
        return ok(entry=payload, note="Saved privately." + (" This entry stays out of any AI features." if entry["local_only"] else ""))

    @router.post("/wellness/mind/journal", status_code=201)
    async def mind_journal_add(request: Request, tz_offset_minutes: int | None = TZ, authorization: str | None = Header(default=None)):
        uid, _ = await auth(authorization)
        return await run(journal_add, uid, await body_of(request), tz_offset_minutes)

    @router.get("/wellness/mind/journal")
    async def mind_journal_list(limit: int = Query(default=30, ge=1, le=100), authorization: str | None = Header(default=None)):
        uid, _ = await auth(authorization)
        return await run(lambda: ok(entries=[d["payload"] for d in doc_store.list_docs(db, uid, "journal", limit=limit)]))

    @router.delete("/wellness/mind/journal/{jid}")
    async def mind_journal_delete(jid: str, authorization: str | None = Header(default=None)):
        uid, _ = await auth(authorization)
        if not JID.match(jid) or not await run(doc_store.delete, db, uid, "journal", jid):
            raise HTTPException(status_code=404, detail="Entry not found")
        return ok(deleted=True)

    @router.get("/wellness/mind/exercises")
    async def mind_exercises(authorization: str | None = Header(default=None)):
        await auth(authorization)
        return ok(exercises=list(Mind.EXERCISES), note=Mind.EXERCISE_NOTE)

    def mind_insights(uid: str, days: int, tz: int | None) -> dict:
        _s, off, _now, local = clock(uid, tz)
        entries = Mind.load_mood_entries(db, uid, days)
        mood = {d: v["m"] for d, v in Mind.per_day_moods(entries, off).items()}
        sleep_rows = S.nightly(S.load_entries(db, uid, days + 2), {}, local.date())
        details = S.load_details(db, uid)
        phases = {d: p["cycle_phase"] for d, p in details.items() if p.get("cycle_phase")}
        try:
            for e in list_domain(db, "cycle", DOMAINS["cycle"], uid, days)["entries"]:
                if e.get("phase") and e.get("date"):
                    phases.setdefault(str(e["date"])[:10], e["phase"])
        except Exception:  # noqa: BLE001 - cycle data is an optional extra input
            pass
        active: set[str] = set()
        try:
            for e in list_domain(db, "activity", DOMAINS["activity"], uid, days)["entries"]:
                if e.get("date"):
                    active.add(W.local_date_of(e["date"], off))
        except Exception:  # noqa: BLE001
            pass
        goal = S.resolve_goal(W.load_profile(db, uid)["age"], S.load_goal(db, uid))["hours"]
        acts = {W.local_date_of(e.get("date"), off): Mind.parse_activities(e.get("notes")) for e in entries if Mind.parse_activities(e.get("notes"))}
        return ok(window_days=days, days_with_mood=len(mood),
                  **Mind.correlations(mood, sleep_hours={n["date"]: n["hours"] for n in sleep_rows}, sleep_goal=goal,
                                      exercise_days=active, phase_by_day=phases, activities_by_day=acts))

    @router.get("/wellness/mind/insights")
    async def mind_insights_route(days: int = Query(default=90, ge=14, le=365), tz_offset_minutes: int | None = TZ,
                                  authorization: str | None = Header(default=None)):
        uid, _ = await auth(authorization)
        return await run(mind_insights, uid, days, tz_offset_minutes)

    @router.get("/wellness/associations")
    async def associations_route(days: int = Query(default=90, ge=14, le=365), refresh: bool = False, tz_offset_minutes: int | None = TZ,
                                 authorization: str | None = Header(default=None)):
        """Patterns between the things the signed-in user logs (sleep, mood, activity, drinks, food, symptoms, heart rate, cycle)."""
        uid, _ = await auth(authorization)
        return await run(lambda: ok(**AL.get(db, uid, days, tz_offset_minutes, refresh)))

    # ======================================================== NOTIFICATIONS ================================================
    def notif_list(uid: str, user: Any, limit: int, unread_only: bool, refresh: bool) -> dict:
        if refresh:
            try:   # reminders appear when the app is opened; a failure here must never break the list or any other request
                N.generate_due(db, uid, email=getattr(user, "email", None))
            except Exception as exc:  # noqa: BLE001
                try:
                    from logging_util import logger
                    logger.warning(component="NOTIFICATIONS", operation="generate_due", error=exc, fallback_action="list_without_new_reminders")
                except Exception:  # noqa: BLE001
                    pass
        return ok(**N.list_notifications(db, uid, limit=limit, unread_only=unread_only))

    @router.get("/notifications")
    async def notifications_list(limit: int = Query(default=50, ge=1, le=200), unread_only: bool = False, refresh: bool = True,
                                 authorization: str | None = Header(default=None)):
        uid, user = await auth(authorization)
        return await run(notif_list, uid, user, limit, unread_only, refresh)

    def notif_read(uid: str, body: dict) -> dict:
        ids, all_ = body.get("ids"), body.get("all")
        if all_ is not None and not isinstance(all_, bool):
            raise InputError("all must be true or false")
        if ids is not None and (not isinstance(ids, list) or len(ids) > 100 or any(not isinstance(i, str) or len(i) > 64 for i in ids)):
            raise InputError("ids must be a list of up to 100 notification ids")
        if not ids and not all_:
            raise InputError("send ids or all: true")
        n = N.mark_read(db, uid, ids, bool(all_))
        return ok(marked=n, unread_count=N.list_notifications(db, uid, limit=1)["unread_count"])

    @router.post("/notifications/read")
    async def notifications_read(request: Request, authorization: str | None = Header(default=None)):
        uid, _ = await auth(authorization)
        return await run(notif_read, uid, await body_of(request))

    @router.get("/notifications/settings")
    async def notifications_settings_get(authorization: str | None = Header(default=None)):
        uid, _ = await auth(authorization)
        return await run(lambda: ok(settings=N.load_settings(db, uid), channels=N.channel_status()))

    def settings_put(uid: str, body: dict) -> dict:
        s = N.normalize_settings(body, N.load_settings(db, uid))
        for channel, purpose in (("email", "email_reminders"),):   # the phone switch is its own in-context yes, logged below
            s["channels"][channel] = s["channels"][channel] and consent.is_granted(db, uid, purpose)   # the switch follows Privacy choices
        N.save_settings(db, uid, s)
        import consent_ledger
        consent_ledger.record_if_changed(db, uid, "email_reminders", bool((s.get("channels") or {}).get("email")), "settings")
        consent_ledger.record_if_changed(db, uid, "push_notifications", bool((s.get("channels") or {}).get("push")), "settings")
        return ok(settings=s, channels=N.channel_status())

    @router.put("/notifications/settings")
    async def notifications_settings_put(request: Request, authorization: str | None = Header(default=None)):
        uid, _ = await auth(authorization)
        return await run(settings_put, uid, await body_of(request))

    # Phone notifications (Android app, Firebase Cloud Messaging): register or forget this phone, and send one test.
    def device_add(uid: str, body: dict) -> dict:
        try:
            result = push_fcm.register_device(db, uid, body.get("token"), body.get("platform", "android"))
        except ValueError as exc:
            raise InputError("token must be this phone's notification token" if str(exc) == "token" else "platform must be android")
        return ok(**result, available=push_fcm.configured())

    @router.post("/notifications/devices")
    async def notifications_device_add(request: Request, authorization: str | None = Header(default=None)):
        uid, _ = await auth(authorization)
        return await run(device_add, uid, await body_of(request))

    @router.post("/notifications/devices/remove")
    async def notifications_device_remove(request: Request, authorization: str | None = Header(default=None)):
        uid, _ = await auth(authorization)
        body = await body_of(request)
        return await run(lambda: ok(removed=push_fcm.remove_device(db, uid, body.get("token"))))

    def push_test(uid: str) -> dict:
        try:
            result = push_fcm.send_test(db, uid)
        except PermissionError:
            raise HTTPException(status_code=409, detail="Turn on phone reminders and save first.")
        return ok(**result)

    @router.post("/notifications/push/test")
    async def notifications_push_test(authorization: str | None = Header(default=None)):
        uid, _ = await auth(authorization)
        return await run(push_test, uid)

    return router
