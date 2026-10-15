"""Firebase Cloud Messaging (HTTP v1) sender for Android push. Replaces the old web-push stub in notifications.py.

Rules:
  * GENERIC TEXT ONLY. ``send`` refuses any title/body that fails ``notifications.is_generic`` (no digits, no health words), and the
    data payload carries only a fixed app route and the notification kind. A lock screen never reveals health data.
  * NEVER RAISES. Every problem (not configured, no network, a bad answer) becomes a result dict; nothing here can break a request.
  * Tokens FCM says are gone (UNREGISTERED and friends) are returned in ``invalid`` so the caller can revoke them.

Configuration: the service-account key of the Firebase project, read once from ``FCM_SERVICE_ACCOUNT_B64`` (base64 of the JSON
file) or ``FCM_SERVICE_ACCOUNT_JSON`` (the JSON itself). Without it every send reports ``not_configured`` and nothing happens.
"""
from __future__ import annotations

import base64
import json
import os
import threading
from functools import lru_cache
from typing import Any, Callable

import requests

SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
SEND_URL = "https://fcm.googleapis.com/v1/projects/{project}/messages:send"
CONNECT_TIMEOUT_S, READ_TIMEOUT_S = 3, 5
MAX_TOKENS_PER_CALL = 5

# Where a tap lands, by kind. Fixed list: the app only follows routes it knows (frontend/lib/push.ts checks again).
ROUTES = {"water": "/hydration", "med": "/medications", "winddown": "/sleep", "system": "/notifications"}
# Android notification channels created by the app (MainActivity): reminders, and gentle check-ins.
CHANNELS = {"water": "reminders", "med": "reminders", "winddown": "reminders", "system": "checkins"}
_INVALID_CODES = ("UNREGISTERED", "SENDER_ID_MISMATCH")


@lru_cache(maxsize=1)
def _account() -> dict[str, Any] | None:
    raw = os.getenv("FCM_SERVICE_ACCOUNT_B64", "").strip()
    try:
        text = base64.b64decode(raw, validate=True).decode("utf-8") if raw else os.getenv("FCM_SERVICE_ACCOUNT_JSON", "").strip()
        info = json.loads(text) if text else None
    except (ValueError, UnicodeDecodeError):
        return None
    ok = isinstance(info, dict) and all(isinstance(info.get(k), str) and info[k] for k in ("project_id", "client_email", "private_key"))
    return info if ok else None


def configured() -> bool:
    return _account() is not None


_lock = threading.Lock()
_credentials: Any = None


def _fast_request(url: str, method: str = "GET", body: Any = None, headers: Any = None, **_kw: Any) -> Any:
    """google-auth transport with a short timeout (its default is two minutes)."""
    from google.auth.transport.requests import Request
    return Request()(url, method=method, body=body, headers=headers, timeout=CONNECT_TIMEOUT_S + READ_TIMEOUT_S)


def _access_token() -> str | None:
    global _credentials
    info = _account()
    if info is None:
        return None
    try:
        with _lock:
            if _credentials is None:
                from google.oauth2 import service_account
                _credentials = service_account.Credentials.from_service_account_info(info, scopes=[SCOPE])
            if not _credentials.valid:
                _credentials.refresh(_fast_request)
            return _credentials.token
    except Exception:  # noqa: BLE001
        _credentials = None
        return None


def _is_invalid_token(status: int, body: Any) -> bool:
    err = body.get("error") if isinstance(body, dict) and isinstance(body.get("error"), dict) else {}
    codes = {d.get("errorCode") for d in err.get("details", []) if isinstance(d, dict)}
    if codes & set(_INVALID_CODES):   # not a bare 404: a wrong project id is a 404 too, and must not revoke every token
        return True
    # a malformed token is INVALID_ARGUMENT naming the registration token; other 400s are about our own message
    return status == 400 and "registration token" in str(err.get("message", "")).lower()


def build_message(token: str, title: str, body: str, kind: str) -> dict[str, Any]:
    kind = kind if kind in ROUTES else "system"
    return {"message": {
        "token": token,
        "notification": {"title": title, "body": body},
        "data": {"route": ROUTES[kind], "kind": kind},
        "android": {"priority": "HIGH", "notification": {"channel_id": CHANNELS[kind], "icon": "ic_stat_bubbles", "color": "#D6246F"}},
    }}


def send(tokens: list[str], title: str, body: str, kind: str = "system", *,
         post: Callable[..., Any] | None = None, token_provider: Callable[[], str | None] | None = None) -> dict[str, Any]:
    """Send one generic notification to each token. ``post`` and ``token_provider`` are injectable for tests.

    Returns ``{"sent": n, "failed": n, "invalid": [tokens FCM no longer knows], "reason": str | None}``."""
    result: dict[str, Any] = {"sent": 0, "failed": 0, "invalid": [], "reason": None}
    try:
        from notifications import is_generic   # imported here: notifications imports this module
        if not (is_generic(title) and is_generic(body)):
            return {**result, "reason": "not_generic"}
        tokens = [t for t in tokens if isinstance(t, str) and t][:MAX_TOKENS_PER_CALL]
        if not tokens:
            return {**result, "reason": "no_devices"}
        info = _account()
        if info is None and token_provider is None:
            return {**result, "reason": "not_configured"}
        bearer = (token_provider or _access_token)()
        if not bearer:
            return {**result, "failed": len(tokens), "reason": "auth_failed"}
        url = SEND_URL.format(project=(info or {}).get("project_id", "test"))
        poster = post or requests.post
        for token in tokens:
            try:
                resp = poster(url, json=build_message(token, title, body, kind), headers={"Authorization": f"Bearer {bearer}"},
                              timeout=(CONNECT_TIMEOUT_S, READ_TIMEOUT_S))
                if 200 <= resp.status_code < 300:
                    result["sent"] += 1
                    continue
                result["failed"] += 1
                try:
                    payload = resp.json()
                except ValueError:
                    payload = None
                if _is_invalid_token(resp.status_code, payload):
                    result["invalid"].append(token)
            except Exception:  # noqa: BLE001
                result["failed"] += 1
        return result
    except Exception:  # noqa: BLE001
        return {**result, "reason": "error"}
