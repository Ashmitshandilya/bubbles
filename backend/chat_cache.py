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


def forget_user(user_id: str) -> None:
    """Call after the person's setup or profile is saved: the next reply reads the new values."""
    _style.invalidate(str(user_id))
    try:
        import context_engine
        context_engine.forget_profile(str(user_id))
    except Exception:  # noqa: BLE001 - invalidation is best effort; the entries expire on their own within minutes
        pass
