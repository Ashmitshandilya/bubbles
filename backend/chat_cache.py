"""Small per-person caches for the chat path. Each holds only the person's own data, per person, in process memory, with an explicit
invalidation (ttl_cache.py rules). Memory items and health events are deliberately NOT cached: a symptom saved a second ago must be
in the next reply."""
from __future__ import annotations

from typing import Any

from ttl_cache import TTLCache

# The tone lines (language, reply length, topics to avoid) built from the saved setup. Read on every AI reply; changes only when
# the setup is saved, and that save calls forget_user().
_style = TTLCache("style_block", ttl_s=120, max_entries=5000)


def style_block(db: Any, user_id: str) -> str:
    """onboarding_api.style_block_for, remembered for two minutes. An empty answer (no setup yet, or a read problem) is never
    remembered, so a failed read cannot hide a person's tone settings."""
    from onboarding_api import style_block_for
    return _style.get_or_compute(str(user_id), lambda: style_block_for(db, user_id), ttl_for=lambda value: 120 if value else 0)


# Where the person lives and how they describe themselves (setup v2): decides which emergency numbers and support lines a reply shows.
# Read on every message, changes only when the setup is saved, and that save calls forget_user().
_identity = TTLCache("identity", ttl_s=120, max_entries=5000)


def identity(db: Any, user_id: str) -> dict[str, Any]:
    """onboarding_api.identity_for, remembered for two minutes. {} (no setup yet, or a read problem) is never remembered."""
    from onboarding_api import identity_for
    return _identity.get_or_compute(str(user_id), lambda: identity_for(db, user_id), ttl_for=lambda value: 120 if value else 0)


def forget_user(user_id: str) -> None:
    """Call after the person's setup or profile is saved: the next reply reads the new values."""
    _style.invalidate(str(user_id))
    _identity.invalidate(str(user_id))
    try:
        import context_engine
        context_engine.forget_profile(str(user_id))
    except Exception:  # noqa: BLE001 - invalidation is best effort; the entries expire on their own within minutes
        pass
