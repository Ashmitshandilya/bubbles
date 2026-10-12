"""In-app notifications (zero cost), with an optional SMTP email channel and a documented web-push stub.

Rules this module enforces:
  * GENERIC TEXT ONLY. A notification body/title is chosen from fixed templates; custom text is accepted only if it passes
    ``is_generic`` (no digits, no symptoms, no medicine or condition names, no units). Anything else is replaced by the
    template, so a lock screen or an email never reveals health data.
  * quiet hours (no notification is created inside them), a per-user daily cap (default 5), de-duplication, read state.
  * EMERGENCIES NEVER DEPEND ON NOTIFICATIONS. Safety responses are returned synchronously by the safety engine; nothing
    here is a safety path, and any failure here is swallowed rather than allowed to affect a request.

Channels: ``in_app`` (default on). ``email`` is off by default and only works when SMTP_HOST (and optionally SMTP_PORT,
SMTP_USER, SMTP_PASSWORD, SMTP_FROM) are set; it fails soft. ``push`` is a stub: browser web push needs VAPID keys that the
project owner generates (``npx web-push generate-vapid-keys``) plus a service worker and a ``push_subscriptions`` store;
none of that exists yet, so ``send_web_push`` always reports ``not_configured``.

Docs: ``notification`` / key = id, ``notification_settings`` / key = ``me``.
"""
from __future__ import annotations

import os
import re
import smtplib
import ssl
import uuid
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Any, Callable

import clinical_constants as K
import doc_store
import hydration_engine as H
import med_schedule as M
import sleep_engine as S
import wellness_common as W
from condition_rules import _pattern
from wellness_common import InputError, fmt_hhmm, parse_hhmm

TEMPLATES = {
    "water": ("A little water break?", "Time for a sip of water."),
    "med": ("Medicine check-in", "Open Bubbles to see what is due."),
    "winddown": ("Wind-down time", "Your wind-down time is near. Ease into your evening."),
    "system": ("Bubbles", "You have an update in Bubbles."),
}
SETTING_TYPES = ("water", "med", "winddown")
SYMPTOM_WORDS = ("pain", "ache", "headache", "migraine", "nausea", "nauseous", "vomit", "fever", "dizzy", "dizziness", "bleeding", "blood",
                 "period", "cramp", "cramps", "pregnant", "pregnancy", "anxiety", "anxious", "depressed", "depression", "panic", "chest",
                 "breath", "breathing", "faint", "fainting", "seizure", "overdose", "suicidal", "pressure", "sugar", "glucose", "cholesterol",
                 "dose", "doses", "tablet", "tablets", "pill", "pills", "injection", "symptom", "symptoms", "diagnosis", "cycle", "ovulation",
                 "weight", "calories", "kcal", "mg", "ml", "kg", "bpm", "mmol", "mmhg", "litres", "liters", "hours")
_DIGIT = re.compile(r"\d")
_blocked: re.Pattern[str] | None = None


def _blocked_pattern() -> re.Pattern[str]:
    global _blocked
    if _blocked is None:
        words: set[str] = set(SYMPTOM_WORDS) | set(K.GLP1_MEDICATIONS) | set(K.CONTRACEPTIVE_PILL_KEYWORDS)
        for group in (K.DRUG_CLASSES, K.STRICT_BLOCKING_CONDITIONS, K.STRICT_BLOCKING_MEDICATIONS, K.SOFT_CAUTION_CONDITIONS):
            for terms in group.values():
                words.update(terms)
        _blocked = _pattern(tuple(sorted(words)))   # type: ignore[assignment]
    return _blocked  # type: ignore[return-value]


def is_generic(value: Any) -> bool:
    """True when the text has no digits and no health words (symptoms, medicines, conditions, units)."""
    if not isinstance(value, str) or not value.strip() or len(value) > 200:
        return False
    low = value.lower()
    return not _DIGIT.search(low) and not _blocked_pattern().search(low)


def sanitise(kind: str, title: Any = None, body: Any = None) -> tuple[str, str]:
    """(title, body) that are safe to show anywhere: custom text only when generic, otherwise the template."""
    t0, b0 = TEMPLATES[kind]
    return (title.strip() if is_generic(title) else t0), (body.strip() if is_generic(body) else b0)


# --- settings ------------------------------------------------------------------------------------------------------------

def default_settings() -> dict[str, Any]:
    return {"channels": {"in_app": True, "email": False, "push": False},
            "quiet_hours": {"enabled": True, "start": K.NOTIFY_QUIET_HOURS_DEFAULT[0], "end": K.NOTIFY_QUIET_HOURS_DEFAULT[1]},
            "daily_cap": K.NOTIFY_DAILY_CAP_DEFAULT, "types": {t: True for t in SETTING_TYPES}, "tz_offset_minutes": 0}


def smtp_configured() -> bool:
    return bool(os.getenv("SMTP_HOST", "").strip())


def channel_status() -> dict[str, Any]:
    return {"in_app": {"available": True}, "email": {"available": smtp_configured(), "note": "Needs SMTP_HOST on the server."},
            "push": {"available": False, "note": "Browser push isn't set up yet; in-app notifications are used."}}


def normalize_settings(body: dict, current: dict | None = None) -> dict[str, Any]:
    out = default_settings()
    cur = current or {}
    for k in ("channels", "quiet_hours", "types"):
        out[k] = {**out[k], **(cur.get(k) if isinstance(cur.get(k), dict) else {})}
    cap, tz = cur.get("daily_cap"), cur.get("tz_offset_minutes")
    if isinstance(cap, int) and not isinstance(cap, bool) and 0 <= cap <= K.NOTIFY_DAILY_CAP_MAX:
        out["daily_cap"] = cap
    if isinstance(tz, int) and not isinstance(tz, bool) and abs(tz) <= W.TZ_LIMIT_MIN:
        out["tz_offset_minutes"] = tz
    if not isinstance(body, dict):
        raise InputError("settings must be an object")
    for group, keys in (("channels", ("in_app", "email", "push")), ("types", SETTING_TYPES)):
        if body.get(group) is not None:
            if not isinstance(body[group], dict):
                raise InputError(f"{group} must be an object")
            for k, v in body[group].items():
                if k not in keys:
                    raise InputError(f"unknown {group[:-1]}: {str(k)[:30]}")
                if not isinstance(v, bool):
                    raise InputError(f"{k} must be true or false")
                out[group][k] = v
    if body.get("quiet_hours") is not None:
        q = body["quiet_hours"]
        if not isinstance(q, dict):
            raise InputError("quiet hours must be an object")
        if "enabled" in q:
            if not isinstance(q["enabled"], bool):
                raise InputError("enabled must be true or false")
            out["quiet_hours"]["enabled"] = q["enabled"]
        for k in ("start", "end"):
            if k in q:
                out["quiet_hours"][k] = fmt_hhmm(parse_hhmm(q[k], f"quiet hours {k}"))
    if body.get("daily_cap") is not None:
        cap = body["daily_cap"]
        if isinstance(cap, bool) or not isinstance(cap, int) or not 0 <= cap <= K.NOTIFY_DAILY_CAP_MAX:
            raise InputError(f"daily cap must be a whole number from 0 to {K.NOTIFY_DAILY_CAP_MAX}")
        out["daily_cap"] = cap
    if body.get("tz_offset_minutes") is not None:
        tz = body["tz_offset_minutes"]
        if isinstance(tz, bool) or not isinstance(tz, int) or abs(tz) > W.TZ_LIMIT_MIN:
            raise InputError("time zone offset must be whole minutes between -840 and 840")
        out["tz_offset_minutes"] = tz
    return out


def load_settings(db: Any, uid: str) -> dict[str, Any]:
    try:
        return normalize_settings({}, doc_store.get(db, uid, "notification_settings", "me"))
    except InputError:   # a hand-edited document must never break the app
        return default_settings()


def save_settings(db: Any, uid: str, settings: dict) -> dict:
    doc_store.put(db, uid, "notification_settings", "me", settings)
    return settings


def in_quiet_hours(settings: dict, minute_of_day: int) -> bool:
    q = settings["quiet_hours"]
    if not q.get("enabled"):
        return False
    start, end = parse_hhmm(q["start"]), parse_hhmm(q["end"])
    if start == end:
        return False
    return start <= minute_of_day < end if start < end else (minute_of_day >= start or minute_of_day < end)


# --- channels ------------------------------------------------------------------------------------------------------------

def send_email(to: str | None, subject: str, body: str, *, smtp_factory: Callable[..., Any] | None = None) -> bool:
    """Send one generic email through the owner's SMTP server. Fail-soft: returns False on any problem, never raises."""
    if not to or not smtp_configured():
        return False
    try:
        host, port = os.environ["SMTP_HOST"].strip(), int(os.getenv("SMTP_PORT", "587") or 587)
        sender = os.getenv("SMTP_FROM") or os.getenv("SMTP_USER") or "bubbles@localhost"
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = sender, to, subject
        msg.set_content(body)
        with (smtp_factory or smtplib.SMTP)(host, port, timeout=5) as smtp:
            if os.getenv("SMTP_USER"):
                smtp.starttls(context=ssl.create_default_context())   # verify the server certificate before sending the password
                smtp.login(os.environ["SMTP_USER"], os.getenv("SMTP_PASSWORD", ""))
            smtp.send_message(msg)
        return True
    except Exception:  # noqa: BLE001
        return False


def send_web_push(subscription: Any, title: str, body: str) -> dict[str, Any]:
    """Stub: needs owner-generated VAPID keys, a service worker and stored subscriptions. Always a no-op for now."""
    return {"sent": False, "reason": "not_configured"}


# --- create / list / read --------------------------------------------------------------------------------------------------

def _recent(db: Any, uid: str, limit: int = 200) -> list[dict]:
    return doc_store.list_docs(db, uid, "notification", limit=limit)


def create_notification(db: Any, uid: str, kind: str, *, title: str | None = None, body: str | None = None, dedupe_key: str | None = None,
                        now: datetime | None = None, settings: dict | None = None, email: str | None = None,
                        mailer: Callable[..., Any] | None = None) -> dict | None:
    """Create one notification, or None when it is suppressed (type off, quiet hours, daily cap reached, duplicate)."""
    if kind not in K.NOTIFY_KINDS:
        raise InputError("unknown notification kind")
    settings = settings or load_settings(db, uid)
    if kind in SETTING_TYPES and not settings["types"].get(kind, True):
        return None
    if not settings["channels"].get("in_app", True) and not settings["channels"].get("email"):
        return None
    now = now or datetime.now(timezone.utc)
    local = W.local_now(now, settings["tz_offset_minutes"])
    if in_quiet_hours(settings, local.hour * 60 + local.minute):
        return None
    today = local.date().isoformat()
    existing = [d["payload"] for d in _recent(db, uid)]
    if dedupe_key and any(p.get("dedupe_key") == dedupe_key for p in existing):
        return None
    if sum(1 for p in existing if p.get("local_date") == today) >= settings["daily_cap"]:
        return None
    t, b = sanitise(kind, title, body)
    nid = uuid.uuid4().hex[:16]
    payload = {"id": nid, "kind": kind, "title": t, "body": b, "created_at": now.astimezone(timezone.utc).isoformat(),
               "local_date": today, "read": False, "dedupe_key": dedupe_key}
    doc_store.put(db, uid, "notification", nid, payload, when=payload["created_at"])
    if settings["channels"].get("email"):
        send_email(email, t, b, smtp_factory=mailer)   # fail-soft; the in-app copy above already exists
    return payload


def list_notifications(db: Any, uid: str, *, limit: int = 50, unread_only: bool = False) -> dict[str, Any]:
    items = [d["payload"] for d in _recent(db, uid)]
    unread = sum(1 for p in items if not p.get("read"))
    shown = [p for p in items if not unread_only or not p.get("read")][:limit]
    return {"notifications": shown, "unread_count": unread}


def mark_read(db: Any, uid: str, ids: list[str] | None = None, all_: bool = False) -> int:
    """Mark the user's own notifications read. Unknown ids (including other users') are ignored."""
    count = 0
    targets = [d["payload"] for d in _recent(db, uid)] if all_ else [doc_store.get(db, uid, "notification", str(i)) for i in (ids or [])]
    for p in targets:
        if p and not p.get("read"):
            doc_store.put(db, uid, "notification", p["id"], {**p, "read": True})
            count += 1
    return count


# --- due reminders ---------------------------------------------------------------------------------------------------------

def generate_due(db: Any, uid: str, now: datetime | None = None, *, email: str | None = None,
                 mailer: Callable[..., Any] | None = None) -> list[dict]:
    """Create the reminders that are due right now (medicine, wind-down, water) and return them. Safe to call as often as you like:
    it respects the user's settings, quiet hours and daily cap, and de-duplicates per slot. Other modules call this."""
    now = now or datetime.now(timezone.utc)
    settings = load_settings(db, uid)
    local = W.local_now(now, settings["tz_offset_minutes"])
    now_min, day = local.hour * 60 + local.minute, local.date().isoformat()
    if in_quiet_hours(settings, now_min) or settings["daily_cap"] <= 0:
        return []
    made: list[dict] = []

    def emit(kind: str, key: str) -> None:
        n = create_notification(db, uid, kind, dedupe_key=key, now=now, settings=settings, email=email, mailer=mailer)
        if n:
            made.append(n)

    if settings["types"].get("med", True):
        schedules = M.load_schedules(db, uid)
        if schedules:
            docs = M.dose_docs_for_day(M.load_dose_docs(db, uid, 1, local.date()), day)   # the window follows `now`, not the wall clock
            for time in sorted({i["time"] for i in M.due_list(schedules, docs, local)["items"] if i["status"] == "due" and not i["placebo"]}):
                emit("med", f"med:{day}:{time}")
    if settings["types"].get("winddown", True):
        profile = W.load_profile(db, uid)
        goal = S.resolve_goal(profile["age"], S.load_goal(db, uid))
        details = S.load_details(db, uid, 30)
        beds = [details[k]["bedtime"] for k in sorted(details, reverse=True)[:14] if details[k].get("bedtime")]
        wd = parse_hhmm(S.winddown(goal["hours"], bedtime=goal.get("bedtime"), wake=goal.get("wake_time"), recent_bedtimes=beds)["winddown"])
        if 0 <= (now_min - wd) % 1440 < 30:
            emit("winddown", f"winddown:{day}")
    if settings["types"].get("water", True):
        profile = W.load_profile(db, uid)
        flags = W.load_condition_flags(db, uid, profile)
        goal = H.daily_goal(profile["weight_kg"], H.exercise_minutes_on(db, uid, day, settings["tz_offset_minutes"]),
                            profile["pregnant"], profile["breastfeeding"], flags["fluid_restricted"])
        if goal["goal_ml"] is not None:
            totals = H.day_totals(H.load_entries(db, uid, 2), day, settings["tz_offset_minutes"])
            q = settings["quiet_hours"]
            wake, sleep = (parse_hhmm(q["end"]), parse_hhmm(q["start"])) if q.get("enabled") else (7 * 60, 22 * 60)
            slot = H.reminder_plan(goal["goal_ml"], totals["effective_ml"], now_min, wake, sleep)["due_now"]
            if slot:
                emit("water", f"water:{day}:{slot}")
    return made
