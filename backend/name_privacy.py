"""Names of the people in someone's life never reach an outside AI (plan C11).

The person tells Bubbles who their people are ("my boyfriend is Ashmit"); those facts are saved as people memory. Before a prompt leaves the server,
each saved name is swapped for a role label (``[PARTNER]``, ``[MOTHER]``, ``[FRIEND_1]``), and in the model's reply the labels are swapped back, so the
person reads "How is Ashmit?" while the provider only ever saw "How is [PARTNER]?". If the model invents or mangles a label, it is replaced by a plain
word ("your partner") rather than shown.

Pure and reversible. A name is matched exactly as saved (capital letter included), so an ordinary word that is also a name ("will", "hope") is left alone
unless the person typed it as a name.
"""
from __future__ import annotations

import re
from typing import Any, Iterable

#: group (people_memory) -> label and the plain words used if the model hands back a label we cannot place
_ROLES: dict[str, tuple[str, str]] = {
    "partner": ("PARTNER", "your partner"), "mother": ("MOTHER", "your mother"), "father": ("FATHER", "your father"), "brother": ("BROTHER", "your brother"),
    "sister": ("SISTER", "your sister"), "son": ("SON", "your son"), "daughter": ("DAUGHTER", "your daughter"), "grandmother": ("GRANDMOTHER", "your grandmother"),
    "grandfather": ("GRANDFATHER", "your grandfather"), "aunt": ("AUNT", "your aunt"), "uncle": ("UNCLE", "your uncle"), "cousin": ("COUSIN", "your cousin"),
    "best friend": ("BEST_FRIEND", "your best friend"), "friend": ("FRIEND", "your friend"), "roommate": ("ROOMMATE", "your roommate"),
    "mother-in-law": ("MOTHER_IN_LAW", "your mother-in-law"), "father-in-law": ("FATHER_IN_LAW", "your father-in-law"),
    "brother-in-law": ("BROTHER_IN_LAW", "your brother-in-law"), "sister-in-law": ("SISTER_IN_LAW", "your sister-in-law"),
    "dog": ("PET", "your pet"), "cat": ("PET", "your pet"), "pet": ("PET", "your pet"),
}
_OTHER = ("PERSON", "someone you know")
_LABEL_RX = re.compile(r"\[([A-Za-z_]+(?:_\d+)?)\]")


def _group_of(key: str) -> str:
    parts = str(key or "").split(":")
    return parts[1] if len(parts) >= 3 and parts[0] in ("person", "pet") else parts[0]


def build_map(facts: Iterable[dict[str, Any]]) -> dict[str, str]:
    """``{name: "[LABEL]"}`` for the people the person has told Bubbles about. Two people in one role get ``_2``, ``_3``."""
    out: dict[str, str] = {}
    used: dict[str, int] = {}
    for fact in facts or []:
        name = str(fact.get("value") or "").strip()
        key = str(fact.get("key") or "")
        if not name or len(name) < 2 or name in out or not (key.startswith(("person:", "pet:")) or key in _ROLES):
            continue
        label = _ROLES.get(_group_of(key), _OTHER)[0]
        used[label] = used.get(label, 0) + 1
        out[name] = f"[{label}]" if used[label] == 1 else f"[{label}_{used[label]}]"
    return out


def _rx(name: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![\w]){re.escape(name)}(?![\w])")


def mask(text: str, mapping: dict[str, str]) -> str:
    """The text with every saved name replaced by its label. Longer names first, so "Anil Kumar" goes before "Anil"."""
    if not text or not mapping:
        return text
    for name in sorted(mapping, key=len, reverse=True):
        text = _rx(name).sub(mapping[name], text)
    return text


def unmask(text: str, mapping: dict[str, str]) -> str:
    """The reply with each label turned back into the name. A label that is not in the map becomes plain words, never a bracketed code."""
    if not text or "[" not in text:
        return text
    back = {label.upper(): name for name, label in mapping.items()}

    def fix(m: re.Match[str]) -> str:
        label = f"[{m.group(1).upper()}]"
        if label in back:
            return back[label]
        base = re.sub(r"_\d+$", "", m.group(1).upper())
        for key, (role, words) in _ROLES.items():
            if role == base:
                return words
        return _OTHER[1] if base == _OTHER[0] else m.group(0)

    return _LABEL_RX.sub(fix, text)


def people_map(db: Any, uid: str) -> dict[str, str]:
    """{name: "[LABEL]"} for the people this person has told Bubbles about (their saved, not rejected, people memory). Never raises."""
    try:
        rows = (db.table("memory_items").select("structured_data,verification_status").eq("user_id", uid).eq("memory_type", "L2").eq("is_active", True).limit(200).execute().data or [])
        facts = []
        for row in rows:
            data = row.get("structured_data") if isinstance(row.get("structured_data"), dict) else {}
            if data.get("source") == "explicit_user_statement" and row.get("verification_status") not in {"rejected", "superseded"}:
                facts.append({"key": data.get("key"), "value": data.get("value")})
        return build_map(facts)
    except Exception:  # noqa: BLE001 - without a map nothing is masked; callers that need masking check for that
        return {}


def mask_all(mapping: dict[str, str], *texts: str) -> tuple[str, ...]:
    return tuple(mask(t, mapping) for t in texts)


def leaked(text: str, mapping: dict[str, str]) -> list[str]:
    """Names still present in ``text`` (for tests and a last check before a prompt is sent)."""
    return [name for name in mapping if _rx(name).search(text or "")]
