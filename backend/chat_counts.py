"""Message counts for a page of conversations: one round trip through public.bubbles_chat_counts (supabase/migrations/20261016_bubbles_lookup_indexes.sql),
or, while that function is missing, one count per conversation asked at the same time."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any


def _one_by_one(db: Any, ids: list[str]) -> dict[str, int]:
    def count(cid: str) -> int:
        return db.table("chat_messages").select("id", count="exact", head=True).eq("conversation_id", cid).execute().count or 0
    with ThreadPoolExecutor(max_workers=8, thread_name_prefix="history-count") as pool:
        return dict(zip(ids, pool.map(count, ids)))


def message_counts(db: Any, user_id: str, ids: list[str]) -> dict[str, int]:
    """{conversation_id: number of messages}; a conversation with none is 0."""
    ids = [str(i) for i in ids]
    if not ids:
        return {}
    try:
        rows = db.rpc("bubbles_chat_counts", {"p_user": user_id, "p_ids": ids}).execute().data or []
        counts = {str(r["conversation_id"]): int(r["message_count"]) for r in rows}
    except Exception:  # noqa: BLE001 - the function is not installed yet (migration pending): count them one by one
        return _one_by_one(db, ids)
    return {i: counts.get(i, 0) for i in ids}
