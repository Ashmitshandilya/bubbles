"""Phone (FCM) tokens for Android push: register, revoke, list, and the scheduler's "who has push on" index.

One row per device token in ``device_tokens`` (supabase/migrations/20261016_bubbles_device_tokens.sql). The token is opaque and
carries no health data. A token belongs to exactly one account at a time: registering it again from another signed-in account
moves it, so a second person using the same phone never receives the first person's reminders.

Every function is fail-soft for the callers that must not break a request: database problems (including the migration not being
applied yet) raise ``PushUnavailable``, which the routes turn into a calm "not ready" answer.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

TABLE = "device_tokens"
MAX_ACTIVE_PER_USER = 5          # a person rarely has more than a phone and a tablet; the oldest are revoked beyond this
PLATFORMS = ("android",)
_TOKEN = re.compile(r"^[A-Za-z0-9_:.\-]{20,512}$")   # FCM tokens are about 160 characters of this alphabet
_VERSION = re.compile(r"^[0-9A-Za-z.+\-]{1,40}$")


class PushUnavailable(Exception):
    """The device table cannot be read or written (migration not applied, or the database is down)."""


class PushInputError(ValueError):
    """The request is malformed; the message is safe to show."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate(token: Any, platform: Any = "android", app_version: Any = None) -> tuple[str, str, str | None]:
    if not isinstance(token, str) or not _TOKEN.match(token):
        raise PushInputError("That device token does not look right.")
    if platform not in PLATFORMS:
        raise PushInputError("Only Android is supported for now.")
    if app_version is not None and not (isinstance(app_version, str) and _VERSION.match(app_version)):
        app_version = None   # a bad version string is not worth refusing the registration for
    return token, str(platform), app_version


def _run(fn):
    try:
        return fn()
    except (PushInputError, PushUnavailable):
        raise
    except Exception as exc:  # noqa: BLE001 - table missing, permission denied, network: all "not ready"
        raise PushUnavailable(type(exc).__name__) from exc


def register(db: Any, uid: str, token: Any, platform: Any = "android", app_version: Any = None) -> dict[str, Any]:
    """Store the token for this user (or move it here from another account), then keep at most MAX_ACTIVE_PER_USER active."""
    token, platform, app_version = validate(token, platform, app_version)

    def work() -> dict[str, Any]:
        now = _now()
        fields = {"user_id": uid, "platform": platform, "app_version": app_version, "last_seen": now, "revoked": False}
        existing = db.table(TABLE).select("id").eq("token", token).limit(1).execute().data or []
        if existing:
            db.table(TABLE).update(fields).eq("token", token).execute()
        else:
            try:
                db.table(TABLE).insert({**fields, "token": token, "created_at": now}).execute()
            except Exception:  # noqa: BLE001 - a parallel register won the unique token: take it over instead
                db.table(TABLE).update(fields).eq("token", token).execute()
        rows = (db.table(TABLE).select("token,last_seen").eq("user_id", uid).eq("revoked", False)
                .order("last_seen", desc=True).limit(50).execute().data or [])
        for old in rows[MAX_ACTIVE_PER_USER:]:
            db.table(TABLE).update({"revoked": True}).eq("token", old["token"]).eq("user_id", uid).execute()
        return {"registered": True, "active": min(len(rows), MAX_ACTIVE_PER_USER)}

    return _run(work)


def unregister(db: Any, uid: str, token: Any) -> int:
    """Revoke only the caller's own token. A token that is not theirs (or unknown) changes nothing."""
    if not isinstance(token, str) or not _TOKEN.match(token):
        raise PushInputError("That device token does not look right.")
    return _run(lambda: len(db.table(TABLE).update({"revoked": True}).eq("token", token).eq("user_id", uid).eq("revoked", False)
                            .execute().data or []))


def revoke_all(db: Any, uid: str) -> int:
    """Withdrawal of consent: every device of this user stops receiving pushes."""
    return _run(lambda: len(db.table(TABLE).update({"revoked": True}).eq("user_id", uid).eq("revoked", False).execute().data or []))


def delete_all(db: Any, uid: str) -> int:
    """"Delete my data": remove the rows themselves."""
    return _run(lambda: len(db.table(TABLE).delete().eq("user_id", uid).execute().data or []))


def active_tokens(db: Any, uid: str) -> list[str]:
    rows = _run(lambda: db.table(TABLE).select("token").eq("user_id", uid).eq("revoked", False).limit(MAX_ACTIVE_PER_USER).execute().data or [])
    return [r["token"] for r in rows if isinstance(r.get("token"), str)]


def revoke_tokens(db: Any, tokens: list[str]) -> int:
    """Tokens the push service reported as no longer valid."""
    done = 0
    for token in tokens:
        try:
            done += len(db.table(TABLE).update({"revoked": True}).eq("token", token).execute().data or [])
        except Exception:  # noqa: BLE001 - cleanup is best effort
            pass
    return done


def users_with_active_tokens(db: Any, limit: int = 2000) -> list[str]:
    """Distinct user ids that have at least one active token: the fan-out index for the scheduler."""
    rows = _run(lambda: db.table(TABLE).select("user_id").eq("revoked", False).limit(limit).execute().data or [])
    seen: dict[str, None] = {}
    for r in rows:
        if r.get("user_id"):
            seen[str(r["user_id"])] = None
    return list(seen)
