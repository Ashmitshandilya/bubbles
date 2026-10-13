"""The few operational settings an administrator may change from the portal. Nothing else is editable there.

Values live in process memory (read on the chat path without any I/O) and are written through to ``bubbles_admin_settings`` so
they survive a restart. Every change is audited with its old and new value. Not editable here by design: secrets, safety rules,
clinical constants, sign-in, RLS, DNS, billing, model allow-lists, the paid / keyless switches.

Single-instance assumption (DEPLOY.md: one Render instance): a change is visible to the whole API at once. With several
instances each would need to reload the table.
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

import ops_telemetry

TABLE = "bubbles_admin_settings"
CACHE_NAMES = ("sign_in", "consent", "profile_sync")
CACHE_LABELS = {"sign_in": "Remember sign-in checks (30 s)", "consent": "Remember the AI consent answer (5 min)",
                "profile_sync": "Remember that a name is saved (1 h)"}

_lock = threading.Lock()
_values: dict[str, Any] = {}
_meta: dict[str, dict[str, Any]] = {}
state = {"loaded": False, "persisted": None}


def chain_names() -> list[str]:
    """The chat chain in order, read from the code (Gemini first, then the keyed fallback pool). Never the keyless pool."""
    from ai_provider import AUTHENTICATED_PROVIDERS
    return ["Gemini"] + [name for name, _fn in AUTHENTICATED_PROVIDERS]


def _spec() -> dict[str, dict[str, Any]]:
    spec: dict[str, dict[str, Any]] = {
        "telemetry_retention_days": {"type": "int", "min": 1, "max": 90, "default": 14,
                                     "label": "Keep technical logs for (days)"},
    }
    for name in chain_names():
        spec[f"provider_paused.{name}"] = {"type": "bool", "default": False, "label": name}
    for name in CACHE_NAMES:
        spec[f"cache_enabled.{name}"] = {"type": "bool", "default": True, "label": CACHE_LABELS[name]}
    return spec


def get(key: str) -> Any:
    spec = _spec().get(key)
    with _lock:
        return _values.get(key, spec["default"] if spec else None)


def is_paused(provider: str) -> bool:
    """Read on the chat path: memory only, and any problem means "not paused"."""
    try:
        return _values.get(f"provider_paused.{provider}") is True
    except Exception:  # noqa: BLE001
        return False


def _validate(key: str, value: Any) -> Any:
    spec = _spec().get(key)
    if spec is None:
        raise ValueError("unknown_setting")
    if spec["type"] == "bool":
        if not isinstance(value, bool):
            raise ValueError("expected_true_or_false")
        return value
    if isinstance(value, bool) or not isinstance(value, int) or not spec["min"] <= value <= spec["max"]:
        raise ValueError(f"expected_whole_number_{spec['min']}_to_{spec['max']}")
    return value


def _apply(key: str, value: Any) -> None:
    if key == "telemetry_retention_days":
        ops_telemetry.retention_days = int(value)
    elif key.startswith("cache_enabled."):
        import ttl_cache
        cache = ttl_cache.get(key.split(".", 1)[1])
        if cache is not None:
            cache.enabled = bool(value)
            if not value:
                cache.clear()


def describe() -> list[dict[str, Any]]:
    out = []
    for key, spec in _spec().items():
        with _lock:
            value = _values.get(key, spec["default"])
            meta = dict(_meta.get(key, {}))
        out.append({"key": key, **spec, "value": value, "updated_at": meta.get("updated_at"), "updated_by": meta.get("updated_by")})
    return out


def update(key: str, value: Any, actor: str) -> dict[str, Any]:
    """Validates, applies, writes through and audits. Raises ValueError for anything outside the allow-list."""
    try:
        value = _validate(key, value)
    except ValueError as error:
        # only a known key is written back; anything typed that is not on the list is recorded as "unknown key", never verbatim
        ops_telemetry.record("audit", action="setting_rejected", target=key if key in _spec() else "unknown key",
                             outcome=str(error), actor=actor)
        raise
    old = get(key)
    now = datetime.now(timezone.utc).isoformat()
    with _lock:
        _values[key] = value
        _meta[key] = {"updated_at": now, "updated_by": actor}
    _apply(key, value)
    try:
        from supabase_client import supabase
        supabase.table(TABLE).upsert({"key": key, "value": value, "updated_at": now, "updated_by": actor}, on_conflict="key").execute()
        state["persisted"] = True
    except Exception:  # noqa: BLE001 - the change still holds until the next restart
        state["persisted"] = False
    ops_telemetry.record("audit", action="setting_changed", target=key, old=old, new=value, actor=actor,
                         outcome="saved" if state["persisted"] else "applied_not_saved")
    return {"key": key, "value": value, "old": old, "persisted": state["persisted"]}


def load() -> None:
    """Startup: read stored values (known keys only, each re-validated). Never raises; defaults stay on any problem."""
    try:
        from supabase_client import supabase
        rows = supabase.table(TABLE).select("key,value,updated_at,updated_by").execute().data or []
        state["persisted"] = True
    except Exception:  # noqa: BLE001
        state["persisted"] = False
        rows = []
    for row in rows:
        try:
            key, value = row["key"], _validate(row["key"], row["value"])
        except Exception:  # noqa: BLE001 - an unknown or invalid stored row is ignored
            continue
        with _lock:
            _values[key] = value
            _meta[key] = {"updated_at": row.get("updated_at"), "updated_by": row.get("updated_by")}
        _apply(key, value)
    state["loaded"] = True


def reset_for_tests() -> None:
    with _lock:
        _values.clear()
        _meta.clear()
    state.update({"loaded": False, "persisted": None})
