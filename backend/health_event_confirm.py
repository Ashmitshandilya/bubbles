"""Save or dismiss the details Bubbles picked up in chat.

POST  /health-events/confirmation        {decisions: [{id, confirmed}]}  (1-30 at once, one sign-in check)
PATCH /health-events/{id}/confirmation   {confirmed}                     (the old single route, same code)

The decision is durable the moment the status update commits, and that is all the request waits for: one read of the current statuses and
one update per decision value. Copying a saved detail into the health record (and into memory) runs after the response, and a failure there
never turns a saved decision into an error: it is logged and tried again the next time the same detail is saved. Pressing a button twice is
harmless (the second press changes nothing), and dismissing something that is already saved answers 409 instead of silently half-undoing it.

Each answer is ``{id, status: "confirmed"|"rejected", projection: "queued"|"done"|"compat"|null}`` or
``{id, status: "error", code: 404|409|500, detail}``.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException
from pydantic import BaseModel, Field

from db_access import is_permission_denied
from event_filters import DEAD_STATUSES
from health_event_projection import project_confirmed_events
from memory_promotion import promote_health_event

_COLUMNS = "id,message_id,event_type,extracted_data,confidence,user_confirmed,extraction_status"
_COMPAT_FOR_S = 600.0
_compat_until = 0.0   # set when the health record tables refused a write; the answers say "compat" for a while instead of promising a copy


class Decision(BaseModel):
    id: str
    confirmed: bool


class BatchRequest(BaseModel):
    decisions: list[Decision] = Field(min_length=1, max_length=30)


class SingleRequest(BaseModel):
    confirmed: bool


def _state(row: dict[str, Any]) -> str:
    status = str(row.get("extraction_status") or "").strip().lower()
    if status:
        return status
    return "confirmed" if row.get("user_confirmed") is True else "pending"


def _error(event_id: str, code: int, detail: str) -> dict[str, Any]:
    return {"id": event_id, "status": "error", "code": code, "detail": detail}


def decide(db: Any, user_id: str, decisions: list[Decision]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Writes the decisions. Returns (answers in request order, event rows to copy into the record afterwards, updated rows by id)."""
    from logging_util import logger

    wanted: dict[str, bool] = {}
    answers: dict[str, dict[str, Any]] = {}
    for d in decisions:
        try:
            event_id = str(UUID(d.id))
        except ValueError:
            answers[d.id] = _error(d.id, 404, "That item was not found.")   # ids are UUIDs: anything else cannot exist and never reaches the database
            continue
        wanted.setdefault(event_id, d.confirmed)
    rows: dict[str, dict[str, Any]] = {}
    if wanted:
        try:
            found = db.table("extracted_health_events").select(_COLUMNS).eq("user_id", user_id).in_("id", list(wanted)).execute().data or []
        except Exception as error:  # noqa: BLE001
            logger.error(component="HEALTH_EVENT", operation="confirm_read", error=error, user_id=user_id, fallback_action="error_per_item")
            found = None
        if found is None:
            for event_id in wanted:
                answers[event_id] = _error(event_id, 500, "Unable to update health event")
            wanted = {}
        rows = {str(r["id"]): r for r in found or []}

    to_write: dict[bool, dict[str, list[str]]] = {True: {"pending": [], "null": []}, False: {"pending": [], "null": []}}
    to_project: list[dict[str, Any]] = []
    for event_id, confirmed in wanted.items():
        row = rows.get(event_id)
        if row is None:
            answers[event_id] = _error(event_id, 404, "That item was not found.")   # also what someone else's id looks like: never changed, never revealed
            continue
        state = _state(row)
        if confirmed:
            if state == "confirmed":   # pressed twice: nothing to change, but a copy that failed before is tried again
                answers[event_id] = {"id": event_id, "status": "confirmed", "projection": "done"}
                to_project.append(row)
            elif state in DEAD_STATUSES:
                answers[event_id] = _error(event_id, 409, "This item was withdrawn and can no longer be saved.")
            else:
                to_write[True]["pending" if row.get("extraction_status") else "null"].append(event_id)
        else:
            if state == "confirmed":
                answers[event_id] = _error(event_id, 409, "This was already saved, so it can't be dismissed here.")
            elif state in DEAD_STATUSES:
                answers[event_id] = {"id": event_id, "status": "rejected", "projection": None}
            else:
                to_write[False]["pending" if row.get("extraction_status") else "null"].append(event_id)

    updated: dict[str, dict[str, Any]] = {}
    now = datetime.now(timezone.utc).isoformat()
    for confirmed, groups in to_write.items():
        for kind, ids in groups.items():
            if not ids:
                continue
            payload = {"user_confirmed": confirmed, "extraction_status": "confirmed" if confirmed else "rejected", "updated_at": now}
            try:
                query = db.table("extracted_health_events").update(payload).eq("user_id", user_id).in_("id", ids)
                # the status condition: only a detail still waiting is changed, so two presses (or two devices) cannot overwrite each other
                query = query.eq("extraction_status", "pending") if kind == "pending" else query.is_("extraction_status", "null")
                changed = query.select(_COLUMNS).execute().data or []
            except Exception as error:  # noqa: BLE001
                logger.error(component="HEALTH_EVENT", operation="confirm_update", error=error, user_id=user_id,
                             context={"count": len(ids), "confirmed": confirmed}, fallback_action="error_per_item")
                for event_id in ids:
                    answers[event_id] = _error(event_id, 500, "Unable to update health event")
                continue
            by_id = {str(r["id"]): r for r in changed}
            for event_id in ids:
                row = by_id.get(event_id)
                if row is None:   # it changed between our read and our write
                    answers[event_id] = _error(event_id, 409, "This item just changed. Please reload.")
                    continue
                updated[event_id] = row
                answers[event_id] = {"id": event_id, "status": "confirmed" if confirmed else "rejected", "projection": "queued" if confirmed else None}
                if confirmed:
                    to_project.append(row)
    if time.monotonic() < _compat_until:
        for answer in answers.values():
            if answer.get("projection") == "queued":
                answer["projection"] = "compat"
    return [answers.get(d.id) or answers[str(UUID(d.id))] for d in decisions], to_project, updated


def project_and_remember(db: Any, user_id: str, rows: list[dict[str, Any]]) -> None:
    """After the response: copy the saved details into the health record (one batch), then into memory by the usual rules. Never raises."""
    global _compat_until
    from logging_util import logger

    if not rows:
        return
    try:
        results = project_confirmed_events(db=db, user_id=user_id, events=rows)
        failed = sum(1 for r in results.values() if r.get("status") == "error")
        if failed:
            logger.error(component="HEALTH_EVENT", operation="project_confirmed_events", error=None, user_id=user_id,
                         context={"failed": failed, "total": len(rows)}, fallback_action="decision_kept_projection_retried_on_next_save")
    except Exception as error:  # noqa: BLE001
        if is_permission_denied(error):
            _compat_until = time.monotonic() + _COMPAT_FOR_S   # the decision is stored on the event itself and every reader uses it
        logger.error(component="HEALTH_EVENT", operation="project_confirmed_events", error=error, user_id=user_id,
                     context={"total": len(rows)}, fallback_action="decision_kept_projection_retried_on_next_save")
    for row in rows:
        try:
            promote_health_event(user_id=user_id, event_id=str(row["id"]), event_type=str(row["event_type"]), extracted_data=row.get("extracted_data") or {},
                                 confidence=float(row.get("confidence") or 0), user_confirmed=True, extraction_status="confirmed")
        except Exception as error:  # noqa: BLE001 - memory is a bonus; the saved decision stands
            logger.warning(component="MEMORY", operation="promote_on_confirm", error=error, user_id=user_id, fallback_action="not_remembered")


def build_router(get_user: Callable[[str | None], Any], db: Any) -> APIRouter:
    router = APIRouter()

    @router.post("/health-events/confirmation")
    def confirm_batch(request: BatchRequest, background: BackgroundTasks, authorization: str | None = Header(default=None)):
        user_id = str(get_user(authorization).id)
        answers, to_project, _updated = decide(db, user_id, request.decisions)
        background.add_task(project_and_remember, db, user_id, to_project)
        return {"status": "success", "results": answers}

    @router.patch("/health-events/{event_id}/confirmation")
    def confirm_one(event_id: str, request: SingleRequest, background: BackgroundTasks, authorization: str | None = Header(default=None)):
        user_id = str(get_user(authorization).id)
        answers, to_project, updated = decide(db, user_id, [Decision(id=event_id, confirmed=request.confirmed)])
        answer = answers[0]
        if answer["status"] == "error":
            raise HTTPException(status_code=answer["code"], detail=answer["detail"])
        background.add_task(project_and_remember, db, user_id, to_project)
        event = updated.get(str(UUID(event_id))) or next((r for r in to_project if str(r.get("id")) == str(UUID(event_id))), {"id": event_id})
        return {"status": "success", "event": event, "projection": {"status": answer["projection"]}}

    return router
