"""What Companion is told about the person's current figures.

Read straight from the tracker tables (and the profile for height), so whatever was saved or edited in any screen, in chat or in
the tracker, is what Companion says next; there is no copy to fall behind. A tracker with nothing saved is left out, never shown as zero."""
from __future__ import annotations

from typing import Any

from health_logs import LBS_PER_KG, latest_values

_SKIP = {"id", "date", "notes"}


def _line(slug: str, entry: dict[str, Any]) -> str:
    day = str(entry.get("date") or "")[:10]
    if slug == "weight" and isinstance(entry.get("weight"), (int, float)):
        lbs = float(entry["weight"])
        return f"- weight: {lbs / LBS_PER_KG:.1f} kg ({lbs:.1f} lbs), logged {day}"
    bits = ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in entry.items() if k not in _SKIP and v not in (None, ""))
    return f"- {slug}: {bits or 'logged'}, logged {day}"


def latest_values_block(db: Any, uid: str) -> str:
    """A prompt block, or "" when nothing is saved or anything fails. Never raises."""
    try:
        lines = [_line(slug, entry) for slug, entry in latest_values(db, uid)]
        height = None
        try:
            import doc_store
            height = (doc_store.get(db, uid, "profile", "me") or {}).get("height_cm")
        except Exception:  # noqa: BLE001
            pass
        if height is None:
            try:
                rows = db.table("profiles").select("height_cm").eq("id", uid).limit(1).execute().data or []
                height = rows[0].get("height_cm") if rows else None
            except Exception:  # noqa: BLE001 - height is optional; the tracker values still go out
                pass
        if isinstance(height, (int, float)):
            lines.append(f"- height: {height:g} cm")
        if not lines:
            return ""
        return ("\n\nLATEST SAVED VALUES (the person's own latest entries in their trackers and profile; these are current, so use them "
                "over older mentions in chat, and say when a value has no entry):\n" + "\n".join(lines))
    except Exception:  # noqa: BLE001
        return ""
