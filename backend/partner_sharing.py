"""Partner sharing: the owner decides, category by category, what ONE trusted person can see. Default: nothing.

Two ways to give access (both show exactly the categories the owner picked):
  * CONNECT (recommended, like Flo for Partners): the owner makes a one-time invite code; the partner signs in to their own Bubbles
    account and enters it. The partner then sees a "Shared with you" view inside the app. Either person can end it instantly.
  * QUICK LINK: a random link that works without an account, expires in 7/30/90 days, can be replaced or revoked.

Privacy rules:
* Opt-in per category; at least one. Only CATEGORIES can ever be shared. Chat, symptoms, medications, labs, reports, journal and
  notes, contraception, pregnancy and sexual-health records are deliberately NOT shareable. Partners get summaries, never logs.
* Tokens / codes are random; only their hashes are stored; codes are single use and expire in 48 hours; wrong guesses are limited.
* One connected partner at a time. The owner can see who is connected and disconnect; the partner can leave. Stopping is immediate:
  the partner's access is re-checked against the owner's settings on every read.
* Only rows this server signed for their owner are trusted (doc_store). Cycle information follows the cycle privacy rules
  (nothing in local-only mode or during pregnancy/postpartum).

Add a category: add it to CATEGORIES, write a section builder, register it in `_sections`, add a test that it contains no raw log fields.
"""
from __future__ import annotations

import hashlib
import re
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

import consent
import doc_store
import health_logs

SHARE_KIND, LINK_KIND, INVITE_KIND, WITH_KIND = "partner_share", "partner_link", "partner_invite", "partner_with"
CATEGORIES = {
    "cycle": {"label": "Cycle estimate", "description": "When your next period may start (a range), the phase you may be in, and gentle tips for them. A prediction, never a fact."},
    "sleep": {"label": "Sleep this week", "description": "Your average sleep over the last 7 nights. Never notes or times."},
    "support_note": {"label": "A note from you", "description": "A short message in your own words, for example how they can support you."},
    "orbit_rituals": {"label": "Orbit: shared question and weekly check-in", "description": "Lets the person you are connected with see your answer to the daily question and your weekly check-in, "
                      "but only once you have both answered. Nothing else from Orbit is ever shown."},
    "orbit_weather": {"label": "Orbit: a gentle nudge for them", "description": "Lets Bubbles show the person you are connected with one kind, general line now and then, such as "
                      "\"Ask how their day really was\". It never names a feeling or anything you logged, and some lines appear whatever your week was like."},
}
#: categories that live in Orbit (orbit.py), have no section in the "Shared with you" view and are never shown through a quick link
ORBIT_CATEGORIES = ("orbit_rituals", "orbit_weather")
EXPIRY_CHOICES = (7, 30, 90)
NOTE_MAX, NAME_MAX = 500, 40
INVITE_HOURS = 48
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"          # no I, L, O, 0, 1: easy to read out loud
TOKEN_RX = re.compile(r"[A-Za-z0-9_-]{20,80}")
NOTICE = "Shared by someone who chose to share this with you. It is a summary, not their medical record, and they can stop sharing at any time."
TIPS = {
    "menstrual": ["Offer a warm drink or a hot water bottle without being asked.", "Take a few chores off their plate for a day or two."],
    "follicular": ["Energy is often higher around now: a walk or a small plan together can feel good."],
    "ovulatory": ["Many people feel more social around now. Ask if they would like to make plans."],
    "luteal": ["Mood and energy can dip before a period. Be patient and keep plans light.", "Ask whether they want company or some quiet."],
}
TIP_CAVEAT = "Everyone is different. The best tip is to ask them what would help."
_attempts: dict[str, list[float]] = {}                   # wrong invite codes per person (in memory; one process)
MAX_ATTEMPTS, ATTEMPT_WINDOW = 10, 3600.0


def _bad(msg: str, code: int = 422) -> HTTPException:
    return HTTPException(status_code=code, detail=msg)


def _need_consent(db: Any, uid: str) -> None:
    """Nothing is shared, made or accepted unless the owner said yes in Privacy choices (withdrawing ends all sharing at once)."""
    if not consent.is_granted(db, uid, "partner_sharing"):
        raise _bad("Turn on partner sharing in Privacy choices first.", 403)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:40]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(d: datetime) -> str:
    return d.isoformat()


def _parse(raw: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(raw))
    except (TypeError, ValueError):
        return None


def _future(raw: Any) -> bool:
    d = _parse(raw)
    return bool(d and d > _now())


def _load(db: Any, uid: str) -> dict:
    return doc_store.get(db, uid, SHARE_KIND, "main") or {}


def _save(db: Any, uid: str, cfg: dict) -> None:
    doc_store.put(db, uid, SHARE_KIND, "main", {**cfg, "updated_at": _iso(_now())})


def _norm_code(code: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(code or "").upper())


def available() -> list[dict]:
    return [{"key": k, **v} for k, v in CATEGORIES.items()]


def _drop_ghost_connection(db: Any, uid: str, cfg: dict) -> dict:
    """The partner may have deleted their data or left: if their side of the connection is gone, clear ours too."""
    conn = cfg.get("connection")
    if conn and not doc_store.get(db, conn["uid"], WITH_KIND, _owner_id(uid)):
        cfg["connection"] = None
        _save(db, uid, cfg)
    return cfg


def status(db: Any, uid: str) -> dict:
    cfg = _drop_ghost_connection(db, uid, _load(db, uid))
    link, invite, conn = cfg.get("link"), cfg.get("invite"), cfg.get("connection")
    link_on, invite_on = bool(link and _future(link.get("expires_at"))), bool(invite and _future(invite.get("expires_at")))
    cats = list(cfg.get("categories", []))
    views = (doc_store.get(db, uid, LINK_KIND, link["key"]) or {}).get("views") if link_on else None
    return {
        "status": "success", "available": available(), "categories": cats, "note": cfg.get("note", ""), "owner_name": cfg.get("owner_name", ""),
        "configured": bool(cats),
        "link": {"active": link_on, "expired": bool(link and not link_on), "expires_at": link.get("expires_at") if link_on else None,
                 "views": views or {"count": 0, "last_at": None}},
        "invite": {"active": invite_on, "expires_at": invite.get("expires_at") if invite_on else None},
        "connection": {"name": conn.get("name"), "since": conn.get("since")} if conn else None,
        "sharing": bool(cats and (link_on or conn)),
        "consent": consent.is_granted(db, uid, "partner_sharing"),
        "never_shared": ["Chat", "Symptoms", "Medications", "Lab results and reports", "Journal and notes", "Contraception, pregnancy and sexual health"],
    }


# ---- owner: what to share ------------------------------------------------------------------------------------------------

def _clean_name(raw: Any, label: str) -> str:
    if raw is None:
        return ""
    if not isinstance(raw, str) or len(raw) > NAME_MAX:
        raise _bad(f"{label} can be up to {NAME_MAX} characters.")
    return " ".join(raw.split())


def save_settings(db: Any, uid: str, body: dict) -> dict:
    _need_consent(db, uid)
    cats = body.get("categories")
    if not isinstance(cats, list) or not cats or len(cats) > len(CATEGORIES) or any(c not in CATEGORIES for c in cats):
        raise _bad("Choose at least one thing to share, from the list shown.")
    cats = [c for c in CATEGORIES if c in cats]
    if any(c in ORBIT_CATEGORIES for c in cats) and not consent.is_granted(db, uid, "orbit_partner_signals"):
        raise _bad("Turn on Orbit partner signals in Privacy choices first.", 403)
    note = body.get("note", "")
    if not isinstance(note, str) or len(note) > NOTE_MAX:
        raise _bad(f"Your note can be up to {NOTE_MAX} characters.")
    note = " ".join(note.split())
    if "support_note" in cats and not note:
        raise _bad("Add the note you want them to see, or untick \"A note from you\".")
    if "cycle" in cats:
        import cycle_api
        if cycle_api._settings(db, uid)["privacy"].get("local_only"):
            raise _bad("Turn off local-only mode in Cycle before sharing your cycle estimate.")
    cfg = _load(db, uid)
    cfg.update(categories=cats, note=note if "support_note" in cats else "", owner_name=_clean_name(body.get("owner_name"), "Your name"))
    _save(db, uid, cfg)
    import consent_ledger
    consent_ledger.record_if_changed(db, uid, "partner_sharing", True, "settings")   # choosing what to share is the yes, and it is logged
    return status(db, uid)


def _need_settings(cfg: dict) -> None:
    if not cfg.get("categories"):
        raise _bad("Choose what to share first.")


# ---- owner: quick link ---------------------------------------------------------------------------------------------------

def create_link(db: Any, uid: str, body: dict) -> dict:
    _need_consent(db, uid)
    cfg = _load(db, uid)
    _need_settings(cfg)
    days = body.get("expires_in_days", 30)
    if isinstance(days, bool) or days not in EXPIRY_CHOICES:
        raise _bad("Choose how long the link lasts: 7, 30 or 90 days.")
    if cfg.get("link"):
        doc_store.delete(db, uid, LINK_KIND, cfg["link"]["key"])
    token = secrets.token_urlsafe(24)
    key = _hash(token)
    now = _now()
    doc_store.put(db, uid, LINK_KIND, key, {"uid": uid, "enabled": True, "views": {"count": 0, "last_at": None}})
    cfg["link"] = {"key": key, "created_at": _iso(now), "expires_at": _iso(now + timedelta(days=days))}
    _save(db, uid, cfg)
    return {**status(db, uid), "token": token, "share_path": f"/partner/{token}"}


def revoke_link(db: Any, uid: str) -> dict:
    cfg = _load(db, uid)
    if cfg.get("link"):
        doc_store.delete(db, uid, LINK_KIND, cfg["link"]["key"])
        cfg["link"] = None
        _save(db, uid, cfg)
    return status(db, uid)


# ---- owner: connect a Bubbles account ------------------------------------------------------------------------------------

def _new_code() -> str:
    raw = "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))
    return f"{raw[:4]}-{raw[4:]}"


def create_invite(db: Any, uid: str) -> dict:
    _need_consent(db, uid)
    cfg = _drop_ghost_connection(db, uid, _load(db, uid))
    _need_settings(cfg)
    if cfg.get("connection"):
        raise _bad("Someone is already connected. Disconnect them first to invite another person.")
    if cfg.get("invite"):
        doc_store.delete(db, uid, INVITE_KIND, cfg["invite"]["hash"])
    code = _new_code()
    h = _hash(_norm_code(code))
    exp = _now() + timedelta(hours=INVITE_HOURS)
    doc_store.put(db, uid, INVITE_KIND, h, {"uid": uid})
    cfg["invite"] = {"hash": h, "expires_at": _iso(exp)}
    _save(db, uid, cfg)
    return {**status(db, uid), "code": code}


def revoke_invite(db: Any, uid: str) -> dict:
    cfg = _load(db, uid)
    if cfg.get("invite"):
        doc_store.delete(db, uid, INVITE_KIND, cfg["invite"]["hash"])
        cfg["invite"] = None
        _save(db, uid, cfg)
    return status(db, uid)


def _owner_id(owner_uid: str) -> str:
    return _hash("owner:" + owner_uid)[:16]


def disconnect(db: Any, uid: str) -> dict:
    cfg = _load(db, uid)
    conn = cfg.get("connection")
    if conn:
        doc_store.delete(db, conn["uid"], WITH_KIND, _owner_id(uid))
        cfg["connection"] = None
        _save(db, uid, cfg)
    return status(db, uid)


def stop_all(db: Any, uid: str) -> dict:
    cfg = _load(db, uid)
    if cfg.get("link"):
        doc_store.delete(db, uid, LINK_KIND, cfg["link"]["key"])
    if cfg.get("invite"):
        doc_store.delete(db, uid, INVITE_KIND, cfg["invite"]["hash"])
    if cfg.get("connection"):
        doc_store.delete(db, cfg["connection"]["uid"], WITH_KIND, _owner_id(uid))
    doc_store.delete(db, uid, SHARE_KIND, "main")
    import consent_ledger
    consent_ledger.record_if_changed(db, uid, "partner_sharing", False, "settings")   # stopping everything is a withdrawal, and it is logged
    return status(db, uid)


# ---- partner: accept, view, leave ----------------------------------------------------------------------------------------

def _signed_payload(db: Any, kind: str, key: str) -> dict | None:
    rows = (db.table(doc_store.TABLE).select("*").eq("event_type", doc_store.EVENT_TYPE).eq("title", f"{kind}:{key}").limit(1).execute().data or [])
    row = rows[0] if rows else None
    payload = ((row.get("data") or {}).get("payload") or {}) if row else {}
    uid = payload.get("uid")
    if not row or not doc_store.row_is_valid(row) or not uid or str(row.get("user_id")) != str(uid):
        return None
    return payload


def _throttle(uid: str) -> None:
    now = time.time()
    for k in [k for k, v in _attempts.items() if not v or now - v[-1] >= ATTEMPT_WINDOW]:   # drop stale people so the dict cannot grow forever
        del _attempts[k]
    recent = _attempts[uid] = [t for t in _attempts.get(uid, []) if now - t < ATTEMPT_WINDOW]
    if len(recent) >= MAX_ATTEMPTS:
        raise _bad("Too many wrong codes. Please wait an hour and ask for a new code.", 429)


def connect(db: Any, partner_uid: str, body: dict) -> dict:
    _throttle(partner_uid)
    code = _norm_code(body.get("code"))
    name = _clean_name(body.get("name"), "Your name") or "Your partner"
    def fail() -> HTTPException:
        """Count the wrong guess, and answer every kind of failure with the same words so a guesser learns nothing."""
        _attempts.setdefault(partner_uid, []).append(time.time())
        return _bad("That code is not valid or has expired. Ask them for a new one.", 404)

    if len(code) != 8:
        raise fail()
    h = _hash(code)
    payload = _signed_payload(db, INVITE_KIND, h)
    if not payload:
        raise fail()
    owner = str(payload["uid"])
    cfg = _load(db, owner)
    inv = cfg.get("invite")
    if not inv or inv.get("hash") != h or not _future(inv.get("expires_at")) or not cfg.get("categories") or not consent.is_granted(db, owner, "partner_sharing"):
        raise fail()
    if owner == str(partner_uid):
        raise _bad("This is your own code. Give it to the person you want to share with.")
    if cfg.get("connection"):
        raise fail()
    doc_store.delete(db, owner, INVITE_KIND, h)                      # single use
    cfg["invite"] = None
    cfg["connection"] = {"uid": str(partner_uid), "name": name, "since": _iso(_now())}
    # The partner's side first: if saving the owner's side then fails, nothing claims a connection the owner does not have.
    doc_store.put(db, str(partner_uid), WITH_KIND, _owner_id(owner), {"owner_uid": owner, "since": _iso(_now())})
    try:
        _save(db, owner, cfg)
    except Exception:
        doc_store.delete(db, str(partner_uid), WITH_KIND, _owner_id(owner))
        raise
    return {"status": "success", "connected": True, "from_name": cfg.get("owner_name") or "Your partner"}


def shared_with_me(db: Any, partner_uid: str) -> dict:
    out = []
    for d in doc_store.list_docs(db, partner_uid, WITH_KIND, 5):
        owner = str((d.get("payload") or {}).get("owner_uid") or "")
        cfg = _load(db, owner) if owner else {}
        conn = cfg.get("connection") or {}
        if not owner or str(conn.get("uid")) != str(partner_uid) or not cfg.get("categories"):   # re-checked on every read
            doc_store.delete(db, partner_uid, WITH_KIND, d["key"])
            continue
        if not consent.is_granted(db, owner, "partner_sharing"):   # paused, not removed: a failed read must not end the connection
            continue
        out.append({"id": d["key"], "from_name": cfg.get("owner_name") or "Your partner", "since": conn.get("since"),
                    "sections": _sections(db, owner, cfg), "notice": NOTICE})
    return {"status": "success", "shares": out}


def leave(db: Any, partner_uid: str, share_id: str) -> dict:
    doc = doc_store.get(db, partner_uid, WITH_KIND, share_id)
    if doc:
        owner = str(doc.get("owner_uid") or "")
        cfg = _load(db, owner) if owner else {}
        if (cfg.get("connection") or {}).get("uid") == str(partner_uid):
            cfg["connection"] = None
            _save(db, owner, cfg)
        doc_store.delete(db, partner_uid, WITH_KIND, share_id)
    return shared_with_me(db, partner_uid)


# ---- what the partner sees -----------------------------------------------------------------------------------------------

def _section_cycle(db: Any, uid: str) -> dict | None:
    import cycle_api
    ctx = cycle_api._context(db, uid, cycle_api._utc_today())
    state = ctx["state"]
    show = state["mode"] in ("track", "conceive", "birth_control", "perimenopause") and state["next_period"]
    if ctx["settings"]["privacy"].get("local_only") or not show:   # same words either way: a partner cannot infer a mode change
        return {"key": "cycle", "title": "Next period, estimated", "range": None, "text": "No estimate is available right now.", "detail": None}
    nxt = state["next_period"]
    tips = TIPS.get(state["phase"] or "", []) if state["mode"] == "track" else []
    return cycle_api._jsonable({"key": "cycle", "title": "Next period, estimated", "range": {"earliest": nxt["earliest"], "latest": nxt["latest"]}, "text": None,
                                "detail": f"Bubbles estimates they may be in their {state['phase']} phase." if state["phase"] else None,
                                "caveat": "A prediction, not a fact, and not a way to plan around pregnancy.",
                                "tips": tips, "tips_caveat": TIP_CAVEAT if tips else None})


def _section_sleep(db: Any, uid: str) -> dict:
    try:
        entries = health_logs.list_domain(db, "sleep", health_logs.DOMAINS["sleep"], uid, 7).get("entries", [])
    except HTTPException:
        entries = []
    hours = [float(e["duration"]) for e in entries if isinstance(e.get("duration"), (int, float)) and not isinstance(e.get("duration"), bool) and 0 < e["duration"] <= 16]
    if len(hours) < 3:
        return {"key": "sleep", "title": "Sleep this week", "text": "Not enough nights logged to say.", "detail": None}
    avg = round(sum(hours) / len(hours) * 2) / 2
    return {"key": "sleep", "title": "Sleep this week", "text": f"About {avg:g} hours a night, over {len(hours)} nights.", "detail": None}


def _sections(db: Any, uid: str, cfg: dict) -> list[dict]:
    out = []
    for cat in cfg.get("categories", []):
        if cat in ORBIT_CATEGORIES:
            continue
        sec = _section_cycle(db, uid) if cat == "cycle" else _section_sleep(db, uid) if cat == "sleep" else (
            {"key": "support_note", "title": "A note from them", "text": cfg["note"], "detail": None} if cfg.get("note") else None)
        if sec:
            out.append(sec)
    return out


def public(db: Any, token: str) -> dict:
    gone = HTTPException(status_code=404, detail="This link is no longer active.")
    if not TOKEN_RX.fullmatch(token or ""):
        raise gone
    payload = _signed_payload(db, LINK_KIND, _hash(token))
    if not payload or not payload.get("enabled"):
        raise gone
    uid = str(payload["uid"])
    cfg = _load(db, uid)
    link = cfg.get("link") or {}
    if link.get("key") != _hash(token) or not _future(link.get("expires_at")) or not cfg.get("categories") or not consent.is_granted(db, uid, "partner_sharing"):
        raise gone
    sections = _sections(db, uid, cfg)
    try:  # best effort: a count and a time in the LINK's own document (never who or where from); the owner's settings are never re-saved here
        views = dict(payload.get("views") or {"count": 0, "last_at": None})
        views["count"] = int(views.get("count", 0)) + 1
        views["last_at"] = _iso(_now())
        doc_store.put(db, uid, LINK_KIND, _hash(token), {**payload, "views": views})
    except Exception:  # noqa: BLE001
        pass
    return {"status": "success", "label": "Shared with you", "expires_at": link["expires_at"], "sections": sections, "notice": NOTICE}


# ---- Orbit: who is paired with whom, and what each side allows ---------------------------------------------------------------

def paired_with(db: Any, uid: str) -> dict | None:
    """The person ``uid`` is connected with, or None: ``{uid, name}``. Either side may have made the invite; the connection must still be there on both sides,
    and it is checked on every call, so leaving or disconnecting ends everything at the next read."""
    cfg = _load(db, uid)
    conn = cfg.get("connection")
    if conn and doc_store.get(db, conn["uid"], WITH_KIND, _owner_id(uid)):
        return {"uid": str(conn["uid"]), "name": conn.get("name") or "Your partner"}
    for d in doc_store.list_docs(db, uid, WITH_KIND, 5):
        owner = str((d.get("payload") or {}).get("owner_uid") or "")
        owner_cfg = _load(db, owner) if owner else {}
        if owner and str((owner_cfg.get("connection") or {}).get("uid")) == str(uid):
            return {"uid": owner, "name": owner_cfg.get("owner_name") or "Your partner"}
    return None


def shares(db: Any, uid: str, category: str) -> bool:
    """True only when ``uid`` has said yes to partner sharing and to Orbit partner signals and has switched this category on."""
    try:
        return (category in (_load(db, uid).get("categories") or []) and consent.is_granted(db, uid, "partner_sharing")
                and consent.is_granted(db, uid, "orbit_partner_signals"))
    except Exception:  # noqa: BLE001 - if it cannot be read, nothing is shared
        return False


# ---- HTTP ----------------------------------------------------------------------------------------------------------------

def build_router(get_user: Callable[[str | None], Any], db: Any) -> APIRouter:
    router = APIRouter()

    def uid_of(authorization: str | None) -> str:
        return str(get_user(authorization).id)

    async def body_of(request: Request) -> dict:
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            raise _bad("Send a JSON body.")
        if not isinstance(body, dict):
            raise _bad("Send a JSON object.")
        return body

    async def owner(authorization: str | None) -> str:
        return await run_in_threadpool(uid_of, authorization)           # authenticate FIRST, before reading anything

    @router.get("/partner-sharing")
    async def status_route(authorization: str | None = Header(default=None)):
        return await run_in_threadpool(status, db, await owner(authorization))

    @router.put("/partner-sharing/settings")
    async def settings_route(request: Request, authorization: str | None = Header(default=None)):
        uid = await owner(authorization)
        return await run_in_threadpool(save_settings, db, uid, await body_of(request))

    @router.post("/partner-sharing/link")
    async def link_create(request: Request, authorization: str | None = Header(default=None)):
        uid = await owner(authorization)
        return JSONResponse(await run_in_threadpool(create_link, db, uid, await body_of(request)), headers={"Cache-Control": "no-store"})

    @router.delete("/partner-sharing/link")
    async def link_revoke(authorization: str | None = Header(default=None)):
        return await run_in_threadpool(revoke_link, db, await owner(authorization))

    @router.post("/partner-sharing/invite")
    async def invite_create(authorization: str | None = Header(default=None)):
        uid = await owner(authorization)
        return JSONResponse(await run_in_threadpool(create_invite, db, uid), headers={"Cache-Control": "no-store"})

    @router.delete("/partner-sharing/invite")
    async def invite_revoke(authorization: str | None = Header(default=None)):
        return await run_in_threadpool(revoke_invite, db, await owner(authorization))

    @router.delete("/partner-sharing/connection")
    async def connection_remove(authorization: str | None = Header(default=None)):
        return await run_in_threadpool(disconnect, db, await owner(authorization))

    @router.delete("/partner-sharing")
    async def stop_route(authorization: str | None = Header(default=None)):
        return await run_in_threadpool(stop_all, db, await owner(authorization))

    @router.post("/partner-sharing/connect")
    async def connect_route(request: Request, authorization: str | None = Header(default=None)):
        uid = await owner(authorization)
        return JSONResponse(await run_in_threadpool(connect, db, uid, await body_of(request)), headers={"Cache-Control": "no-store"})

    @router.get("/partner-sharing/shared-with-me")
    async def mine_route(authorization: str | None = Header(default=None)):
        uid = await owner(authorization)
        return JSONResponse(await run_in_threadpool(shared_with_me, db, uid), headers={"Cache-Control": "no-store"})

    @router.delete("/partner-sharing/shared-with-me/{share_id}")
    async def leave_route(share_id: str, authorization: str | None = Header(default=None)):
        uid = await owner(authorization)
        if not re.fullmatch(r"[a-f0-9]{16}", share_id):
            raise _bad("That share does not exist.", 404)
        return await run_in_threadpool(leave, db, uid, share_id)

    @router.get("/partner/{token}")
    async def public_route(token: str):
        return JSONResponse(await run_in_threadpool(public, db, token), headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})

    return router
