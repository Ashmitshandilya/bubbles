"""Small shared helpers for the sleep / hydration / medication / mind / notification modules (pure, except the loaders).

``InputError`` is the one exception the engines raise for bad user input; the router turns it into a 422 with a
fixed, human string (never raw exception text).
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone
from typing import Any

import clinical_constants as K
import condition_rules
import doc_store
from health_logs import DOMAINS, LBS_PER_KG, list_domain

TZ_LIMIT_MIN = 14 * 60
MAX_TEXT = 2000


class InputError(ValueError):
    """Bad user input. The message is written for the user and safe to return."""


# --- parsing -----------------------------------------------------------------------------------------------------------

def parse_date(value: Any, label: str = "date") -> date:
    try:
        parsed = date.fromisoformat(str(value).strip()[:10])
    except (TypeError, ValueError):
        raise InputError(f"{label} must be a date like 2026-10-08")
    if not 2000 <= parsed.year <= 2100:
        raise InputError(f"{label} is out of range")
    return parsed


def parse_hhmm(value: Any, label: str = "time") -> int:
    """'07:30' -> minutes after midnight."""
    text = str(value).strip() if value is not None else ""
    try:
        hh, mm = text.split(":")
        h, m = int(hh), int(mm)
    except ValueError:
        raise InputError(f"{label} must look like 07:30")
    if not (0 <= h <= 23 and 0 <= m <= 59) or len(mm) != 2:
        raise InputError(f"{label} must look like 07:30")
    return h * 60 + m


def fmt_hhmm(minutes: float) -> str:
    m = int(round(minutes)) % 1440
    return f"{m // 60:02d}:{m % 60:02d}"


def number(value: Any, lo: float, hi: float, label: str, *, required: bool = False) -> float | None:
    if value in (None, ""):
        if required:
            raise InputError(f"{label} is required")
        return None
    if isinstance(value, bool):
        raise InputError(f"{label} must be a number")
    try:
        n = float(value)
    except (TypeError, ValueError, OverflowError):
        raise InputError(f"{label} must be a number")
    if not math.isfinite(n) or not lo <= n <= hi:
        raise InputError(f"{label} must be between {lo:g} and {hi:g}")
    return n


def text(value: Any, limit: int = MAX_TEXT, label: str = "text") -> str | None:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        raise InputError(f"{label} must be text")
    out = str(value).replace(chr(0), "").encode("utf-8", "ignore").decode("utf-8").strip()
    return out[:limit] or None


def choice(value: Any, allowed: tuple, label: str) -> str:
    v = str(value).strip().lower().replace(" ", "_").replace("-", "_") if value is not None else ""
    if v not in allowed:
        raise InputError(f"{label} must be one of " + ", ".join(allowed))
    return v


def tz_offset(value: Any) -> int:
    """Minutes east of UTC, clamped to a real offset."""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return 0
    return max(-TZ_LIMIT_MIN, min(TZ_LIMIT_MIN, n))


def local_now(now_utc: datetime, offset_min: int = 0) -> datetime:
    """A naive datetime holding the user's wall-clock time."""
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    return (now_utc.astimezone(timezone.utc) + timedelta(minutes=offset_min)).replace(tzinfo=None)


def local_date_of(iso: Any, offset_min: int = 0) -> str | None:
    """The user's calendar day (YYYY-MM-DD) of an ISO timestamp. A bare date is returned as is."""
    raw = str(iso or "")
    if not raw:
        return None
    if len(raw) <= 10:
        return raw[:10]
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return raw[:10]
    if parsed.tzinfo is None:
        return parsed.date().isoformat()
    return local_now(parsed, offset_min).date().isoformat()


def days_back(day: date, n: int) -> list[str]:
    """The n calendar days ending at ``day`` (inclusive), oldest first."""
    return [(day - timedelta(days=i)).isoformat() for i in range(n - 1, -1, -1)]


# --- loaders (the only database access in this file) ----------------------------------------------------------------------

def load_profile(db: Any, uid: str) -> dict[str, Any]:
    """Body profile written by the fitness features (doc kind 'profile', key 'body'); weight falls back to the weight tracker."""
    raw = doc_store.get(db, uid, "profile", "body") or doc_store.get(db, uid, "profile", "me") or {}
    lo, hi = K.MIN_PLAUSIBLE["weight_kg"]
    weight = None
    try:
        w = float(raw.get("weight_kg"))
        weight = w if math.isfinite(w) and lo <= w <= hi else None
    except (TypeError, ValueError):
        weight = None
    if weight is None:
        try:  # convenience only: a refused weight table must not break hydration
            entries = list_domain(db, "weight", DOMAINS["weight"], uid, 365)["entries"]
            if entries and entries[0].get("weight") is not None:
                w = float(entries[0]["weight"]) / LBS_PER_KG
                weight = w if lo <= w <= hi else None
        except Exception:  # noqa: BLE001
            weight = None
    age = None
    try:
        a = float(raw.get("age"))
        age = a if K.MIN_PLAUSIBLE["age"][0] <= a <= K.MIN_PLAUSIBLE["age"][1] else None
    except (TypeError, ValueError):
        age = None
    conditions = [str(c) for c in (raw.get("conditions") or []) if c][:50] if isinstance(raw.get("conditions"), list) else []
    return {"weight_kg": weight, "age": age, "pregnant": bool(raw.get("pregnant")), "breastfeeding": bool(raw.get("breastfeeding")),
            "conditions": conditions}


def _names(db: Any, uid: str, slug: str, key: str) -> list[str]:
    try:
        entries = list_domain(db, slug, DOMAINS[slug], uid, 730)["entries"]
    except Exception:  # noqa: BLE001 - see load_profile
        return []
    return [str(e[key]) for e in entries if e.get(key)][:100]


def load_condition_flags(db: Any, uid: str, profile: dict | None = None, extra_meds: list[str] | None = None) -> dict[str, Any]:
    """condition_rules.classify() over the conditions and medicines the user has recorded anywhere."""
    profile = profile if profile is not None else load_profile(db, uid)
    conditions = list(profile.get("conditions") or []) + _names(db, uid, "conditions", "condition_name")
    meds = _names(db, uid, "medications", "name") + list(extra_meds or [])
    return condition_rules.classify(conditions, meds)


def load_allergies(db: Any, uid: str) -> list[str]:
    return _names(db, uid, "allergies", "allergen")


# --- client timezone for THIS request (sent by the app as X-Tz-Offset-Minutes) -----------------------------------
from contextvars import ContextVar  # noqa: E402

REQUEST_TZ: ContextVar = ContextVar("request_tz", default=None)


def parse_tz_header(raw: Any) -> int | None:
    """Minutes east of UTC from the header, clamped; None when absent or not a number."""
    try:
        return max(-TZ_LIMIT_MIN, min(TZ_LIMIT_MIN, int(str(raw).strip())))
    except (TypeError, ValueError):
        return None


def request_tz() -> int | None:
    return REQUEST_TZ.get()
