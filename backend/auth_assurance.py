"""Two-step sign-in enforcement on the server.

A person who turned on two-step sign-in (an authenticator app) must not be let in with a password-only session. Supabase marks every access
token with an "aal" claim: "aal1" after the password, "aal2" after the authenticator code. The token has already been verified by Supabase
(``auth.get_user``) before these helpers run, so only the claim is read here, never trusted on its own to prove who someone is.
"""
from __future__ import annotations

import base64
import json
from typing import Any


def token_aal(token: str) -> str | None:
    """The "aal" claim of an access token, or None when it cannot be read."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload.encode("ascii")))
        value = claims.get("aal") if isinstance(claims, dict) else None
        return value if isinstance(value, str) else None
    except Exception:  # noqa: BLE001 - any malformed token simply has no readable claim
        return None


def has_verified_factor(user: Any) -> bool:
    """True when the account has a verified second factor (an authenticator app)."""
    factors = getattr(user, "factors", None)
    if factors is None and isinstance(user, dict):
        factors = user.get("factors")
    for factor in factors or []:
        status = factor.get("status") if isinstance(factor, dict) else getattr(factor, "status", None)
        if status == "verified":
            return True
    return False


def requires_second_step(user: Any, token: str) -> bool:
    """True when the account has two-step sign-in on but this token only passed the password step."""
    return has_verified_factor(user) and token_aal(token) != "aal2"
