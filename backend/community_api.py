"""Community API (text-only posts and comments, optionally anonymous) and its admin Moderation routes.

Every read and write goes through here (the tables have no client access). No response ever holds an author id: people are shown by a
name for that one thread (``Quiet Otter 4821``), made with an HMAC of (author, thread) under COMMUNITY_ALIAS_SECRET. Without a long
secret the feature stays OFF; there is no default. Only an admin can resolve a name back to a person, and each resolution is logged.

Gate for writing: signed in, 18+ (date of birth from the setup), consent ``community_visibility``, not banned. Reading: signed in and 18+.
Text is checked by community_moderation (deterministic, no AI) before anyone else can see it. Removed text is never stored.
Crisis wording is never shamed: the author gets a calm support message and the post waits (hidden from the feed) for a person to look.
"""
from __future__ import annotations

import base64
import functools
import hashlib
import hmac
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field

import community_moderation as cm
import consent
import doc_store
import onboarding as ob
from calc_core import local_today

TOPICS = ("cycle", "sleep", "mind", "food", "fitness", "skin_hair", "talk")
POST_MAX, COMMENT_MAX = 1200, 600
POSTS_PER_HOUR, COMMENTS_PER_HOUR, REPORTS_PER_HOUR = 5, 20, 10
REPORT_HIDE_AT = 3                 # distinct reporters
PAGE_DEFAULT, PAGE_MAX = 15, 30
REASONS = ("unkind", "unsafe_advice", "spam", "private_info", "sexual", "other")
SECRET_MIN = 16
DUPLICATE_WINDOW = timedelta(hours=24)
_TARGET = re.compile(r"^(post|comment):([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$")
_TAGS = re.compile(r"<[^>\n]{0,300}>")
_WORDS = json.loads((Path(__file__).resolve().parent / "data" / "community_alias_words.json").read_text(encoding="utf-8"))

DISCLAIMER = "Shared by people, not medical advice."
CRISIS_NOTE = ("Thank you for sharing this. You do not have to carry it alone. Your post is saved and a person will look at it soon, "
               "so it is not on the feed yet. If you feel unsafe right now, please reach out to someone today.")
URGENT_NOTE = ("This sounds like it could be urgent. If it is happening now, please call your local emergency number instead of waiting for replies. "
               "Your post is saved and will be looked at soon.")


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---- aliases ------------------------------------------------------------------------------------------------------------

def _secret() -> bytes | None:
    s = (os.getenv("COMMUNITY_ALIAS_SECRET") or "").strip()
    return s.encode("utf-8") if len(s) >= SECRET_MIN else None


def enabled() -> bool:
    return _secret() is not None


def admin_message() -> str | None:
    if enabled():
        return None
    return ("Community is switched off: COMMUNITY_ALIAS_SECRET is not set (or shorter than 16 characters). Set it to a long random string on the "
            "API host to turn it on. There is no default on purpose.")


def _mac(label: str, *parts: str) -> bytes:
    key = _secret()
    if key is None:
        raise HTTPException(status_code=503, detail={"code": "community_off", "message": "Community is not switched on yet."})
    return hmac.new(key, "|".join((label, *parts)).encode("utf-8"), hashlib.sha256).digest()


def alias_for(author_id: str, thread_id: str) -> str:
    d = _mac("alias", author_id, thread_id)
    n = int.from_bytes(d[:8], "big")
    adj, animal = _WORDS["adjectives"], _WORDS["animals"]
    # ponytail: two people in one thread can share a name (1 in ~14 million per pair); add a collision check if threads get huge
    return f"{adj[n % len(adj)]} {animal[(n // len(adj)) % len(animal)]} {1000 + (n // (len(adj) * len(animal))) % 9000}"


def block_key(author_id: str) -> str:
    return _mac("block", author_id).hex()[:32]


# ---- small helpers -------------------------------------------------------------------------------------------------------

def _err(status: int, code: str, message: str, signal: Any = None) -> HTTPException:
    detail: dict[str, Any] = {"code": code, "message": message}
    if signal is not None:
        import safety_engine
        detail["support"] = {"kind": "crisis" if getattr(signal, "crisis", False) else "urgent", "message": "You do not have to carry this alone.", "lines": safety_engine.CRISIS_LINES}
    return HTTPException(status_code=status, detail=detail)


def _safe(fn: Callable) -> Callable:
    @functools.wraps(fn)
    def run(*a, **k):
        try:
            return fn(*a, **k)
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001 - a missing table or a database hiccup must not leak details
            try:
                from logging_util import logger
                logger.warning(component="COMMUNITY", operation=fn.__name__, error=exc, fallback_action="503")
            except Exception:  # noqa: BLE001
                pass
            raise _err(503, "community_unavailable", "Community is not available right now. Please try again later.") from exc
    return run


def _norm(text: str) -> str:
    return re.sub(r"[\W_]+", " ", (text or "").casefold()).strip()


def _clean(raw: str) -> str:
    t = _TAGS.sub(" ", cm._normalise(raw or ""))
    t = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def _target(raw: str) -> tuple[str, str]:
    m = _TARGET.match(raw or "")
    if not m:
        raise _err(422, "bad_target", "That does not look right.")
    return m.group(1), m.group(2)


def _table(kind: str) -> str:
    return "community_posts" if kind == "post" else "community_comments"


def _log(db: Any, target: str, action: str, reason: str | None, actor: str) -> None:
    try:
        db.table("community_moderation_log").insert({"target": target, "action": action, "reason_code": reason, "actor": actor, "created_at": _now().isoformat()}).execute()
    except Exception:  # noqa: BLE001 - the trail is best effort; it never blocks a person
        pass


def _cursor_in(raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        v = base64.urlsafe_b64decode(raw.encode("ascii") + b"=" * (-len(raw) % 4)).decode("utf-8")
        datetime.fromisoformat(v)
        return v
    except Exception:  # noqa: BLE001
        raise _err(422, "bad_cursor", "That page link is not valid.")


def _cursor_out(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")


def _adult(db: Any, uid: str) -> bool:
    doc = doc_store.get(db, uid, "onboarding", "v1") or {}
    if doc.get("age_gate") == "under_18":
        return False
    born = (doc.get("answers") or {}).get("birth_date") if isinstance(doc.get("answers"), dict) else None
    age = ob.age_on(born, local_today()) if born else None
    return age is not None and age >= ob.MIN_AGE


def _banned(db: Any, uid: str) -> bool:
    return bool(db.table("community_bans").select("user_id").eq("user_id", uid).limit(1).execute().data)


def _blocked_keys(db: Any, uid: str) -> set[str]:
    return {r["blocked_alias_key"] for r in db.table("community_blocks").select("blocked_alias_key").eq("user_id", uid).limit(500).execute().data or []}


def _name_for(db: Any, uid: str, thread: str, anonymous: bool) -> str:
    """Anonymous: the thread name. Named: the first word of the preferred name (checked like any text), else the thread name."""
    if not anonymous:
        doc = doc_store.get(db, uid, "onboarding", "v1") or {}
        name = str(((doc.get("answers") or {}) if isinstance(doc.get("answers"), dict) else {}).get("preferred_name") or "").strip().split(" ")[0][:20]
        if name and cm.moderate(name).action == cm.ALLOW and re.fullmatch(r"[^\W\d_]+", name):
            return name
    return alias_for(uid, thread)


def _public(row: dict, uid: str, reactions: dict, comments: int | None = None) -> dict:
    mine = row["author_id"] == uid
    out: dict[str, Any] = {
        "id": row["id"], "alias": row["alias"], "anonymous": row.get("display_mode") == "anonymous", "body": row["body"],
        "created_at": row["created_at"], "mine": mine,
        "reactions": {"me_too": reactions.get("me_too", 0), "helpful": reactions.get("helpful", 0)}, "my_reactions": sorted(reactions.get("mine", [])),
    }
    if "topic" in row:
        out["topic"] = row["topic"]
    if comments is not None:
        out["comment_count"] = comments
    if mine:
        out["status"] = row["status"]
        if row["status"] != "visible":
            out["note"] = CRISIS_NOTE if (row.get("crisis") and row["status"] == "held") else cm.REASON_TEXT.get(row.get("reason_code") or "", "This is waiting for a quick review.")
    return out


def _reaction_map(db: Any, field: str, ids: list[str], uid: str) -> dict[str, dict]:
    out: dict[str, dict] = {i: {"mine": []} for i in ids}
    if not ids:
        return out
    for r in db.table("community_reactions").select("*").in_(field, ids).limit(20000).execute().data or []:
        slot = out.get(str(r.get(field)))
        if slot is not None:
            slot[r["kind"]] = slot.get(r["kind"], 0) + 1
            if r["user_id"] == uid:
                slot["mine"].append(r["kind"])
    return out


def forget(db: Any, uid: str) -> dict[str, int]:
    """Delete-my-data: remove the person's posts (their comments and reactions go with them), comments, reactions, reports and blocks.
    The moderation trail keeps codes only (no text, no person). Returns counts."""
    counts: dict[str, int] = {}
    for table, col in (("community_reactions", "user_id"), ("community_reports", "reporter_id"), ("community_blocks", "user_id"),
                       ("community_comments", "author_id"), ("community_posts", "author_id")):
        try:
            if table == "community_posts":   # a fake or older database may not cascade, so remove the comments under these posts first
                ids = [r["id"] for r in db.table(table).select("id").eq(col, uid).limit(20000).execute().data or []]
                for pid in ids:
                    db.table("community_comments").delete().eq("post_id", pid).execute()
                    db.table("community_reactions").delete().eq("post_id", pid).execute()
            counts[table] = len(db.table(table).delete().eq(col, uid).execute().data or [])
        except Exception:  # noqa: BLE001 - table not created yet, nothing to remove
            counts[table] = 0
    return counts


def hold_all(db: Any, uid: str) -> None:
    """Consent to be visible was withdrawn: every visible post and comment of theirs goes back to held (reason 'consent')."""
    for table in ("community_posts", "community_comments"):
        try:
            db.table(table).update({"status": "held", "reason_code": "consent"}).eq("author_id", uid).eq("status", "visible").execute()
        except Exception:  # noqa: BLE001 - table not created yet
            pass


# ---- request bodies ------------------------------------------------------------------------------------------------------

class PostIn(BaseModel):
    topic: str = Field(max_length=20)
    body: str = Field(max_length=5000)
    anonymous: bool = True


class CommentIn(BaseModel):
    body: str = Field(max_length=3000)
    anonymous: bool = True


class ReactIn(BaseModel):
    target: str = Field(max_length=60)
    kind: str = Field(max_length=10)


class ReportIn(BaseModel):
    target: str = Field(max_length=60)
    reason: str = Field(max_length=20)


class TargetIn(BaseModel):
    target: str = Field(max_length=60)


class DecideIn(BaseModel):
    target: str = Field(max_length=60)
    action: str = Field(max_length=10)


def build_router(get_user: Callable[[str | None], Any], db: Any) -> APIRouter:
    router = APIRouter()

    def uid_of(authorization: str | None) -> str:
        return str(get_user(authorization).id)

    def require_reader(uid: str) -> None:
        if not enabled():
            raise _err(503, "community_off", "Community is not switched on yet.")
        if not _adult(db, uid):
            raise _err(403, "adults_only", "Community is for people 18 and over.")

    def require_writer(uid: str) -> None:
        require_reader(uid)
        if not consent.is_granted(db, uid, "community_visibility"):
            raise _err(403, "consent_needed", "Turn on \"Show my posts in the community\" to post here.")
        if _banned(db, uid):
            raise _err(403, "not_allowed", "You can read here, but posting is switched off for your account.")

    def over_limit(table: str, uid: str, limit: int) -> bool:
        since = (_now() - timedelta(hours=1)).isoformat()
        rows = db.table(table).select("id").eq("author_id", uid).gte("created_at", since).limit(limit + 1).execute().data or []
        return len(rows) >= limit

    def is_duplicate(table: str, uid: str, text: str) -> bool:
        since = (_now() - DUPLICATE_WINDOW).isoformat()
        rows = db.table(table).select("body").eq("author_id", uid).gte("created_at", since).order("created_at", desc=True).limit(50).execute().data or []
        n = _norm(text)
        return bool(n) and any(_norm(r["body"]) == n for r in rows)

    def moderate_new(table: str, uid: str, raw: str, limit_chars: int, per_hour: int) -> tuple[str, str | None, str, Any]:
        """-> (status, reason, text to store, safety assessment or None). Raises the friendly refusals."""
        text = _clean(raw)
        if not text:
            raise _err(422, "empty", "Write something first.")
        if len(text) > limit_chars:
            raise _err(422, "too_long", f"Please keep it to {limit_chars} characters.")
        signal = cm.safety_signal(text)   # first, so someone in crisis who is rate-limited or repeats themselves still gets the support lines
        if over_limit(table, uid, per_hour):
            raise _err(429, "slow_down", "You have posted a lot in the last hour. Please try again a little later.", signal)
        if is_duplicate(table, uid, text):
            raise _err(409, "duplicate", cm.REASON_TEXT["duplicate"], signal)
        d = cm.moderate(text, crisis=signal is not None)
        if d.action == cm.REMOVE:
            return "removed", d.reason, "[removed by moderation]", signal
        if signal is not None:
            return "held", "crisis", d.text, signal
        if d.action == cm.HOLD:
            return "held", d.reason, d.text, signal
        return "visible", None, d.text, signal

    def support_for(signal: Any, status: str) -> dict | None:
        if signal is None or status == "removed":
            return None
        import safety_engine
        crisis = bool(getattr(signal, "crisis", False))
        return {"kind": "crisis" if crisis else "urgent", "message": CRISIS_NOTE if crisis else URGENT_NOTE, "lines": safety_engine.CRISIS_LINES}

    # ---- reads -----------------------------------------------------------------------------------------------------------

    @router.get("/community/status")
    @_safe
    def status(authorization: str | None = Header(default=None)):
        uid = uid_of(authorization)
        base = {"topics": list(TOPICS), "disclaimer": DISCLAIMER, "limits": {"post": POST_MAX, "comment": COMMENT_MAX}}
        if not enabled():
            return {**base, "enabled": False, "can_read": False, "can_post": False, "reason": "off"}
        if not _adult(db, uid):
            return {**base, "enabled": True, "can_read": False, "can_post": False, "reason": "adults_only"}
        try:
            db.table("community_posts").select("id").limit(1).execute()
        except Exception:  # noqa: BLE001 - migration not applied yet
            return {**base, "enabled": False, "can_read": False, "can_post": False, "reason": "off"}
        if not consent.is_granted(db, uid, "community_visibility"):
            return {**base, "enabled": True, "can_read": True, "can_post": False, "reason": "consent_needed"}
        if _banned(db, uid):
            return {**base, "enabled": True, "can_read": True, "can_post": False, "reason": "not_allowed"}
        return {**base, "enabled": True, "can_read": True, "can_post": True, "reason": None}

    @router.get("/community/posts")
    @_safe
    def feed(topic: str | None = Query(default=None, max_length=20), mine: bool = False, cursor: str | None = Query(default=None, max_length=100),
             limit: int = Query(default=PAGE_DEFAULT, ge=1, le=PAGE_MAX), authorization: str | None = Header(default=None)):
        uid = uid_of(authorization)
        require_reader(uid)
        if topic is not None and topic not in TOPICS:
            raise _err(422, "bad_topic", "Pick one of the topics.")
        q = db.table("community_posts").select("*")
        q = q.eq("author_id", uid) if mine else q.eq("status", "visible")
        if topic:
            q = q.eq("topic", topic)
        before = _cursor_in(cursor)
        if before:
            q = q.lt("created_at", before)
        rows = q.order("created_at", desc=True).limit(limit + 1).execute().data or []
        more = len(rows) > limit
        rows = rows[:limit]
        next_cursor = _cursor_out(rows[-1]["created_at"]) if (more and rows) else None
        blocked = set() if mine else _blocked_keys(db, uid)
        rows = [r for r in rows if not (r["status"] == "removed" and r.get("reason_code") == "deleted")
                and (mine or r["author_id"] == uid or block_key(r["author_id"]) not in blocked)]
        ids = [r["id"] for r in rows]
        react = _reaction_map(db, "post_id", ids, uid)
        counts = {i: 0 for i in ids}
        if ids:
            for c in db.table("community_comments").select("post_id").in_("post_id", ids).eq("status", "visible").limit(20000).execute().data or []:
                counts[c["post_id"]] += 1
        return {"posts": [_public(r, uid, react[r["id"]], counts[r["id"]]) for r in rows], "next_cursor": next_cursor, "disclaimer": DISCLAIMER}

    @router.get("/community/posts/{post_id}/comments")
    @_safe
    def comments(post_id: str, cursor: str | None = Query(default=None, max_length=100), limit: int = Query(default=PAGE_DEFAULT, ge=1, le=PAGE_MAX),
                 authorization: str | None = Header(default=None)):
        uid = uid_of(authorization)
        require_reader(uid)
        _target("post:" + post_id)
        post = (db.table("community_posts").select("*").eq("id", post_id).limit(1).execute().data or [None])[0]
        if not post or not (post["status"] == "visible" or post["author_id"] == uid):
            raise _err(404, "not_found", "That post is not here any more.")
        q = db.table("community_comments").select("*").eq("post_id", post_id)
        before = _cursor_in(cursor)
        if before:
            q = q.lt("created_at", before)
        rows = q.order("created_at", desc=True).limit(limit + 1).execute().data or []
        more = len(rows) > limit
        rows = rows[:limit]
        blocked = _blocked_keys(db, uid)
        rows = [r for r in rows if (r["status"] == "visible" or r["author_id"] == uid) and not (r["status"] == "removed" and r.get("reason_code") == "deleted")
                and (r["author_id"] == uid or block_key(r["author_id"]) not in blocked)]
        react = _reaction_map(db, "comment_id", [r["id"] for r in rows], uid)
        return {"comments": [_public(r, uid, react[r["id"]]) for r in rows], "next_cursor": _cursor_out(rows[-1]["created_at"]) if (more and rows) else None}

    # ---- writes ----------------------------------------------------------------------------------------------------------

    @router.post("/community/posts")
    @_safe
    def create_post(body: PostIn, authorization: str | None = Header(default=None)):
        uid = uid_of(authorization)
        require_writer(uid)
        if body.topic not in TOPICS:
            raise _err(422, "bad_topic", "Pick one of the topics.")
        state, reason, text, signal = moderate_new("community_posts", uid, body.body, POST_MAX, POSTS_PER_HOUR)
        pid = _new_id()
        row = {"id": pid, "author_id": uid, "display_mode": "anonymous" if body.anonymous else "named", "alias": _name_for(db, uid, pid, body.anonymous),
               "topic": body.topic, "body": text, "status": state, "reason_code": reason, "crisis": signal is not None and state != "removed",
               "created_at": _now().isoformat()}
        saved = (db.table("community_posts").insert(row).execute().data or [row])[0]
        if state != "visible":
            _log(db, f"post:{pid}", "hold" if state == "held" else "remove", reason, "bot")
        return {"post": _public(saved, uid, {}, 0), "support": support_for(signal, state)}

    @router.post("/community/posts/{post_id}/comments")
    @_safe
    def create_comment(post_id: str, body: CommentIn, authorization: str | None = Header(default=None)):
        uid = uid_of(authorization)
        require_writer(uid)
        _target("post:" + post_id)
        post = (db.table("community_posts").select("*").eq("id", post_id).limit(1).execute().data or [None])[0]
        if not post or post["status"] != "visible":
            raise _err(404, "not_found", "That post is not here any more.")
        if post["author_id"] != uid and block_key(post["author_id"]) in _blocked_keys(db, uid):
            raise _err(404, "not_found", "That post is not here any more.")
        state, reason, text, signal = moderate_new("community_comments", uid, body.body, COMMENT_MAX, COMMENTS_PER_HOUR)
        cid = _new_id()
        existing = (db.table("community_comments").select("alias,display_mode").eq("post_id", post_id).eq("author_id", uid).limit(1).execute().data or [None])[0]
        alias = existing["alias"] if (existing and existing.get("display_mode") == "anonymous" and body.anonymous) else _name_for(db, uid, post_id, body.anonymous)
        row = {"id": cid, "post_id": post_id, "author_id": uid, "display_mode": "anonymous" if body.anonymous else "named", "alias": alias, "body": text,
               "status": state, "reason_code": reason, "crisis": signal is not None and state != "removed", "created_at": _now().isoformat()}
        saved = (db.table("community_comments").insert(row).execute().data or [row])[0]
        if state != "visible":
            _log(db, f"comment:{cid}", "hold" if state == "held" else "remove", reason, "bot")
        return {"comment": _public(saved, uid, {}), "support": support_for(signal, state)}

    @router.delete("/community/{kind}/{item_id}")
    @_safe
    def delete_own(kind: str, item_id: str, authorization: str | None = Header(default=None)):
        uid = uid_of(authorization)    # works without consent: withdrawing must never trap a post
        if kind not in ("posts", "comments"):
            raise _err(404, "not_found", "Not found.")
        _target(("post:" if kind == "posts" else "comment:") + item_id)
        table = "community_posts" if kind == "posts" else "community_comments"
        row = (db.table(table).select("*").eq("id", item_id).limit(1).execute().data or [None])[0]
        if not row or row["author_id"] != uid:   # someone else's, or not there: the same answer
            raise _err(404, "not_found", "That is not here any more.")
        # The text goes; a stub stays so the hourly limit cannot be dodged by posting and deleting.
        db.table(table).update({"body": "[deleted]", "status": "removed", "reason_code": "deleted", "crisis": False}).eq("id", item_id).execute()
        return {"status": "success"}

    @router.post("/community/reactions")
    @_safe
    def react(body: ReactIn, authorization: str | None = Header(default=None)):
        uid = uid_of(authorization)
        require_writer(uid)
        if body.kind not in ("me_too", "helpful"):
            raise _err(422, "bad_kind", "Pick me too or helpful.")
        kind, tid = _target(body.target)
        row = (db.table(_table(kind)).select("status").eq("id", tid).limit(1).execute().data or [None])[0]
        if not row or row["status"] != "visible":
            raise _err(404, "not_found", "That is not here any more.")
        col = "post_id" if kind == "post" else "comment_id"
        found = db.table("community_reactions").select("id").eq(col, tid).eq("user_id", uid).eq("kind", body.kind).limit(1).execute().data
        if found:
            db.table("community_reactions").delete().eq("id", found[0]["id"]).execute()
            return {"on": False}
        db.table("community_reactions").insert({col: tid, "user_id": uid, "kind": body.kind, "created_at": _now().isoformat()}).execute()
        return {"on": True}

    @router.post("/community/reports")
    @_safe
    def report(body: ReportIn, authorization: str | None = Header(default=None)):
        uid = uid_of(authorization)
        require_writer(uid)
        if body.reason not in REASONS:
            raise _err(422, "bad_reason", "Pick a reason.")
        kind, tid = _target(body.target)
        row = (db.table(_table(kind)).select("*").eq("id", tid).limit(1).execute().data or [None])[0]
        if not row or row["status"] == "removed":
            raise _err(404, "not_found", "That is not here any more.")
        if row["author_id"] == uid:
            raise _err(422, "own_post", "That one is yours. You can delete it instead.")
        since = (_now() - timedelta(hours=1)).isoformat()
        if len(db.table("community_reports").select("id").eq("reporter_id", uid).gte("created_at", since).limit(REPORTS_PER_HOUR + 1).execute().data or []) >= REPORTS_PER_HOUR:
            raise _err(429, "slow_down", "You have sent a lot of reports. Please try again a little later.")
        target = f"{kind}:{tid}"
        if not db.table("community_reports").select("id").eq("target", target).eq("reporter_id", uid).limit(1).execute().data:
            db.table("community_reports").insert({"target": target, "reporter_id": uid, "reason": body.reason, "created_at": _now().isoformat()}).execute()
        distinct = {r["reporter_id"] for r in db.table("community_reports").select("reporter_id").eq("target", target).limit(1000).execute().data or []}
        if len(distinct) >= REPORT_HIDE_AT and row["status"] == "visible":
            db.table(_table(kind)).update({"status": "held", "reason_code": "reports"}).eq("id", tid).execute()
            _log(db, target, "auto_hide", "reports", "bot")
        return {"status": "success", "message": "Thank you. A person will take a look."}

    @router.post("/community/blocks")
    @_safe
    def block(body: TargetIn, authorization: str | None = Header(default=None)):
        uid = uid_of(authorization)
        require_reader(uid)
        kind, tid = _target(body.target)
        row = (db.table(_table(kind)).select("author_id").eq("id", tid).limit(1).execute().data or [None])[0]
        if not row:
            raise _err(404, "not_found", "That is not here any more.")
        if row["author_id"] == uid:
            raise _err(422, "own_post", "That one is yours.")
        key = block_key(row["author_id"])
        if key not in _blocked_keys(db, uid):
            db.table("community_blocks").insert({"user_id": uid, "blocked_alias_key": key, "created_at": _now().isoformat()}).execute()
        return {"status": "success"}

    @router.delete("/community/blocks")
    @_safe
    def unblock_all(authorization: str | None = Header(default=None)):
        db.table("community_blocks").delete().eq("user_id", uid_of(authorization)).execute()
        return {"status": "success"}

    @router.delete("/community/me")
    @_safe
    def delete_my_community_data(authorization: str | None = Header(default=None)):
        return {"status": "success", "deleted": forget(db, uid_of(authorization))}

    # ---- admin (the middleware answers every non-admin with the same 404 before routing; _admin is the second lock) ----------

    from admin_api import _admin

    def hidden_items() -> list[dict]:
        items: list[dict] = []
        for kind in ("post", "comment"):
            for r in db.table(_table(kind)).select("*").eq("status", "held").limit(300).execute().data or []:
                target = f"{kind}:{r['id']}"
                reports = db.table("community_reports").select("reason").eq("target", target).limit(200).execute().data or []
                items.append({"target": target, "kind": kind, "alias": r["alias"], "topic": r.get("topic"), "body": r["body"], "created_at": r["created_at"],
                              "reason_code": r.get("reason_code"), "crisis": bool(r.get("crisis")), "reports": len(reports),
                              "report_reasons": sorted({x["reason"] for x in reports})})
        items.sort(key=lambda i: (not i["crisis"], i["created_at"]))
        return items

    @router.get("/admin/community/status", include_in_schema=False)
    @_safe
    def admin_status(request: Request):
        _admin(request)
        counts = {}
        for t in ("community_posts", "community_comments"):
            for s in ("visible", "held", "removed"):
                counts[f"{t[10:]}_{s}"] = len(db.table(t).select("id").eq("status", s).limit(20000).execute().data or [])
        return {"enabled": enabled(), "message": admin_message(), "counts": counts, "banned": len(db.table("community_bans").select("user_id").limit(20000).execute().data or [])}

    @router.get("/admin/community/queue", include_in_schema=False)
    @_safe
    def admin_queue(request: Request):
        _admin(request)
        return {"items": hidden_items(), "enabled": enabled(), "message": admin_message()}

    @router.get("/admin/community/log", include_in_schema=False)
    @_safe
    def admin_log(request: Request, limit: int = Query(default=100, ge=1, le=300)):
        _admin(request)
        return {"log": db.table("community_moderation_log").select("*").order("created_at", desc=True).limit(limit).execute().data or []}

    @router.post("/admin/community/decide", include_in_schema=False)
    @_safe
    def admin_decide(body: DecideIn, request: Request):
        _admin(request)
        if body.action not in ("approve", "remove", "ban"):
            raise _err(422, "bad_action", "approve, remove or ban.")
        kind, tid = _target(body.target)
        table = _table(kind)
        row = (db.table(table).select("*").eq("id", tid).limit(1).execute().data or [None])[0]
        if not row:
            raise _err(404, "not_found", "Not found.")
        target = f"{kind}:{tid}"
        if body.action == "approve":
            db.table(table).update({"status": "visible", "reason_code": None, "crisis": False}).eq("id", tid).execute()
            db.table("community_reports").delete().eq("target", target).execute()
        else:
            db.table(table).update({"status": "removed", "reason_code": "admin", "body": "[removed by moderation]", "crisis": False}).eq("id", tid).execute()
            if body.action == "ban":
                if not _banned(db, row["author_id"]):
                    db.table("community_bans").insert({"user_id": row["author_id"], "reason_code": "admin", "created_at": _now().isoformat()}).execute()
                for t in ("community_posts", "community_comments"):   # everything else they wrote waits for a look
                    db.table(t).update({"status": "held", "reason_code": "admin"}).eq("author_id", row["author_id"]).eq("status", "visible").execute()
        _log(db, target, body.action, "admin" if body.action != "approve" else None, "admin")
        return {"status": "success"}

    @router.post("/admin/community/resolve", include_in_schema=False)
    @_safe
    def admin_resolve(body: TargetIn, request: Request):
        _admin(request)
        kind, tid = _target(body.target)
        row = (db.table(_table(kind)).select("author_id,alias").eq("id", tid).limit(1).execute().data or [None])[0]
        if not row:
            raise _err(404, "not_found", "Not found.")
        _log(db, f"{kind}:{tid}", "alias_resolved", None, "admin")   # logged BEFORE the answer leaves
        return {"target": f"{kind}:{tid}", "alias": row["alias"], "user_id": row["author_id"]}

    return router


def _new_id() -> str:
    import uuid
    return str(uuid.uuid4())
