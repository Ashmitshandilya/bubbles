"""Phone notifications for the Android app through Firebase Cloud Messaging (FCM HTTP v1). FCM is free on every Firebase plan.

Off until the owner sets ``FIREBASE_SERVICE_ACCOUNT_JSON`` on the server (the service-account key file from Firebase console ->
Project settings -> Service accounts, pasted as JSON or base64). Nothing here runs, sends or starts a thread without it.

Rules this module enforces:
  * GENERIC TEXT ONLY. Title and body always come from ``notifications.sanitise`` (fixed templates); the message data carries
    only the reminder kind. The Android notification is marked private, so a locked phone can hide even that plain text.
  * TWO YESES. A phone notification is sent only when the person's "On this phone" reminder switch is on AND the consent log
    has a current yes for ``push_notifications``. Withdrawing either one stops sending at once.
  * ONE OWNER PER PHONE. A device token is a signed document (``push_device`` / sha256 of the token). Registering a token
    removes it from every other account, so a shared phone never shows the previous person's reminders. At most
    ``MAX_DEVICES`` per person; a token FCM reports as gone is deleted. "Delete all my data" removes them with the rest.
  * EMERGENCIES NEVER DEPEND ON THIS. Fail-soft everywhere: nothing here raises into a request.

The background sweep (``start_background``) creates due reminders every few minutes for people with a phone registered, so a
reminder reaches the phone while the app is closed. On Render's free plan the API stays awake through
``.github/workflows/keep-awake.yml``; if it sleeps anyway, reminders resume when it wakes (FCM drops anything over an hour old).
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import random
import re
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable

import doc_store

DEVICE_KIND = "push_device"
MAX_DEVICES = 5
PLATFORMS = ("android",)
TOKEN_RE = re.compile(r"^[A-Za-z0-9_:\-]{20,4096}$")
SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
CHANNEL_ID = "reminders"          # created by android/.../BubblesFirebasePlugin.java
ICON = "ic_stat_bubbles"           # android/app/src/main/res/drawable/ic_stat_bubbles.xml
COLOR = "#D6246F"
TTL = "3600s"                      # a reminder more than an hour late is noise, not help
TEST_COOLDOWN_S = 60
SWEEP_DEFAULT_S, SWEEP_MIN_S = 300, 60
SWEEP_MAX_USERS = 5000
SWEEP_BATCH = int(os.getenv("BUBBLES_PUSH_BATCH", "200"))         # people handled per run; the rest are picked up by the next runs
SWEEP_BUDGET_S = float(os.getenv("BUBBLES_PUSH_BUDGET_S", "90"))  # the host answers within this, even for a big batch

_lock = threading.Lock()
_cached: tuple[str, dict | None] = ("", None)
_creds: Any = None
_last_test: dict[str, float] = {}
_sweeper: threading.Thread | None = None


# --- configuration --------------------------------------------------------------------------------------------------------

def _service_account() -> dict | None:
    """The parsed service account, or None when it is missing or not a service-account key. Parsed once per value."""
    global _cached, _creds
    raw = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
    if raw == _cached[0]:
        return _cached[1]
    info: dict | None = None
    try:
        text = raw if raw.startswith("{") else base64.b64decode(raw, validate=True).decode("utf-8")
        parsed = json.loads(text) if raw else None
        if isinstance(parsed, dict) and parsed.get("type") == "service_account" and all(parsed.get(k) for k in ("project_id", "private_key", "client_email")):
            info = parsed
    except (ValueError, UnicodeDecodeError):
        info = None
    with _lock:
        _cached, _creds = (raw, info), None
    return info


def configured() -> bool:
    return _service_account() is not None


def _access_token() -> str:
    """A short-lived OAuth token for FCM, refreshed when it expires. Raises on failure (callers catch)."""
    global _creds
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account

    info = _service_account()
    if info is None:
        raise RuntimeError("FCM is not configured")
    with _lock:
        if _creds is None:
            _creds = service_account.Credentials.from_service_account_info(info, scopes=[SCOPE])
        if not _creds.valid:
            _creds.refresh(Request())
        return str(_creds.token)


def _http_post(url: str, payload: dict, headers: dict) -> tuple[int, dict]:
    import httpx

    response = httpx.post(url, json=payload, headers=headers, timeout=5.0)
    try:
        body = response.json()
    except ValueError:
        body = {}
    return response.status_code, body if isinstance(body, dict) else {}


# --- devices --------------------------------------------------------------------------------------------------------------

def device_key(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:32]


def valid_token(token: Any) -> bool:
    return isinstance(token, str) and bool(TOKEN_RE.match(token))


def list_devices(db: Any, uid: str) -> list[dict]:
    return [d["payload"] for d in doc_store.list_docs(db, uid, DEVICE_KIND, limit=50) if valid_token(d["payload"].get("token"))]


def _release_elsewhere(db: Any, uid: str, key: str) -> None:
    """Remove this phone's token from every other account (the trusted backend's one cross-account write here)."""
    title = f"{DEVICE_KIND}:{key}"
    (db.table(doc_store.TABLE).delete().eq("event_type", doc_store.EVENT_TYPE).eq("title", title).neq("user_id", uid).execute())


def register_device(db: Any, uid: str, token: Any, platform: Any = "android", now: datetime | None = None) -> dict[str, Any]:
    """Save (or refresh) this phone for the signed-in person. Raises ValueError for a malformed token or platform."""
    if not valid_token(token):
        raise ValueError("token")
    if platform not in PLATFORMS:
        raise ValueError("platform")
    stamp = (now or datetime.now(timezone.utc)).isoformat()
    key = device_key(token)
    _release_elsewhere(db, uid, key)
    current = doc_store.get(db, uid, DEVICE_KIND, key) or {}
    doc_store.put(db, uid, DEVICE_KIND, key, {"token": token, "platform": platform, "added_at": current.get("added_at") or stamp, "seen_at": stamp})
    devices = sorted(list_devices(db, uid), key=lambda d: str(d.get("seen_at")), reverse=True)
    for old in devices[MAX_DEVICES:]:
        doc_store.delete(db, uid, DEVICE_KIND, device_key(old["token"]))
    return {"registered": True, "devices": min(len(devices), MAX_DEVICES)}


def remove_all_devices(db: Any, uid: str) -> int:
    """Forget every phone of this person (the push choice was withdrawn). Never raises."""
    try:
        return sum(int(doc_store.delete(db, uid, DEVICE_KIND, device_key(d["token"]))) for d in list_devices(db, uid))
    except Exception as exc:  # noqa: BLE001
        _log("remove_all", exc)
        return 0


def remove_device(db: Any, uid: str, token: Any) -> bool:
    return valid_token(token) and doc_store.delete(db, uid, DEVICE_KIND, device_key(token))


# --- sending --------------------------------------------------------------------------------------------------------------

def wanted(db: Any, uid: str, settings: dict) -> bool:
    """Both yeses: the reminder switch and a current yes in the consent log."""
    if not (settings.get("channels") or {}).get("push"):
        return False
    import consent_ledger

    return consent_ledger.is_granted(db, uid, "push_notifications")


def allowed(db: Any, uid: str, settings: dict) -> bool:
    """Both yeses and a configured server."""
    return configured() and wanted(db, uid, settings)


def _message(token: str, kind: str, title: str, body: str) -> dict:
    return {"message": {
        "token": token,
        "notification": {"title": title, "body": body},
        "data": {"kind": kind},
        "android": {"priority": "normal", "ttl": TTL, "collapse_key": kind,
                    "notification": {"channel_id": CHANNEL_ID, "tag": kind, "icon": ICON, "color": COLOR, "visibility": "PRIVATE"}},
    }}


def _token_is_gone(status: int, body: dict) -> bool:
    err = body.get("error") if isinstance(body.get("error"), dict) else {}
    codes = {str(d.get("errorCode")) for d in err.get("details") or [] if isinstance(d, dict)}
    if status == 404 or "UNREGISTERED" in codes:
        return True
    return status == 400 and "registration token" in str(err.get("message", "")).lower()


def _log(operation: str, error: Exception | None = None, **context: Any) -> None:
    try:
        from logging_util import logger

        logger.warning(component="PUSH", operation=operation, error=error, context=context or None, fallback_action="in_app_only")
    except Exception:  # noqa: BLE001
        pass


def send_to_user(db: Any, uid: str, kind: str, title: str | None = None, body: str | None = None, *,
                 post: Callable[[str, dict, dict], tuple[int, dict]] | None = None) -> dict[str, Any]:
    """Send one generic notification to every phone this person registered. Callers check ``allowed`` first. Never raises."""
    import notifications as N

    try:
        devices = list_devices(db, uid)
        if not devices:
            return {"sent": 0, "removed": 0, "reason": "no_devices"}
        t, b = N.sanitise(kind, title, body)
        if kind == "med":   # a lock screen is not private: even "Medicine check-in" says something about the person's health
            t, b = N.TEMPLATES["system"][0], "You have a reminder in Bubbles."
        project = _service_account()["project_id"]   # type: ignore[index]
        url = f"https://fcm.googleapis.com/v1/projects/{project}/messages:send"
        headers = {"Authorization": f"Bearer {_access_token()}", "Content-Type": "application/json; charset=utf-8"}
    except Exception as exc:  # noqa: BLE001
        _log("prepare", exc)
        return {"sent": 0, "removed": 0, "reason": "not_ready"}
    sent = removed = 0
    for device in devices:
        try:
            status, reply = (post or _http_post)(url, _message(device["token"], kind, t, b), headers)
        except Exception as exc:  # noqa: BLE001 - one phone failing must not stop the others
            _log("send", exc)
            continue
        if 200 <= status < 300:
            sent += 1
        elif _token_is_gone(status, reply):
            removed += int(remove_device(db, uid, device["token"]))
        else:
            _log("send", status=status)   # status only: never the token or the reply text
    return {"sent": sent, "removed": removed}


def deliver(db: Any, uid: str, notification: dict, settings: dict, **kw: Any) -> None:
    """Called by notifications.create_notification after it stores an in-app notification. Never raises."""
    try:
        if allowed(db, uid, settings):
            send_to_user(db, uid, str(notification.get("kind")), notification.get("title"), notification.get("body"), **kw)
    except Exception as exc:  # noqa: BLE001
        _log("deliver", exc)


def send_test(db: Any, uid: str, *, post: Callable[..., tuple[int, dict]] | None = None, clock: Callable[[], float] = time.monotonic) -> dict[str, Any]:
    """One plain test notification to the person's own phones, at most once a minute. Raises PermissionError when not allowed."""
    import notifications as N

    if not allowed(db, uid, N.load_settings(db, uid)):
        raise PermissionError("push_off")
    now = clock()
    with _lock:
        if now - _last_test.get(uid, -TEST_COOLDOWN_S) < TEST_COOLDOWN_S:
            return {"sent": 0, "removed": 0, "reason": "wait"}
        _last_test[uid] = now
    return send_to_user(db, uid, "system", "Bubbles", "Phone reminders are working.", post=post)


# --- background sweep -------------------------------------------------------------------------------------------------------

def users_with_devices(db: Any, limit: int = SWEEP_MAX_USERS) -> list[str]:
    """Every account with at least one registered phone. Forged rows only lead to a no-op: everything after reads signed documents."""
    rows = (db.table(doc_store.TABLE).select("user_id").eq("event_type", doc_store.EVENT_TYPE).eq("data->>kind", DEVICE_KIND)
            .limit(limit).execute().data or [])
    return sorted({str(r["user_id"]) for r in rows if isinstance(r, dict) and r.get("user_id")})


def sweep(db: Any, now: datetime | None = None, *, batch: int = SWEEP_BATCH, budget_s: float = SWEEP_BUDGET_S) -> dict[str, Any]:
    """Create the reminders due now for everyone with phone notifications on; create_notification sends each one.
    Bounded (``batch`` people, ``budget_s`` seconds) and idempotent (per-slot de-duplication). A person whose choice was withdrawn
    has their phones forgotten here too."""
    import notifications as N

    started = time.monotonic()
    out: dict[str, Any] = {"checked": 0, "created": 0, "revoked": 0, "errors": 0, "partial": False}
    uids = users_with_devices(db)
    if len(uids) > batch:   # a random slice, a different one each run: fair over time without a stored cursor
        uids, out["partial"] = random.sample(uids, batch), True
    for uid in uids:
        if time.monotonic() - started > budget_s:
            out["partial"] = True
            break
        try:
            if not wanted(db, uid, N.load_settings(db, uid)):
                out["revoked"] += int(remove_all_devices(db, uid) > 0)
                continue
            if not configured():
                continue
            out["checked"] += 1
            out["created"] += len(N.generate_due(db, uid, now))
        except Exception as exc:  # noqa: BLE001 - one person's data must not stop everyone else's reminders
            out["errors"] += 1
            _log("sweep_user", exc)
    return out


def sweep_interval() -> int:
    try:
        return max(SWEEP_MIN_S, int(os.getenv("PUSH_SWEEP_SECONDS", str(SWEEP_DEFAULT_S))))
    except ValueError:
        return SWEEP_DEFAULT_S


def start_background(db: Any) -> bool:
    """Start the sweep thread once, only when FCM is configured and BUBBLES_PUSH_SWEEP is not 0. Returns whether it runs."""
    global _sweeper
    if not configured() or os.getenv("BUBBLES_PUSH_SWEEP", "1").strip() == "0":
        return False
    with _lock:
        if _sweeper is not None and _sweeper.is_alive():
            return True

        def loop() -> None:
            while True:
                time.sleep(sweep_interval())
                try:
                    sweep(db)
                except Exception as exc:  # noqa: BLE001
                    _log("sweep", exc)

        _sweeper = threading.Thread(target=loop, name="bubbles-push-sweep", daemon=True)
        _sweeper.start()
    return True
