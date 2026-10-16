"""A small stateful in-memory stand-in for the Supabase client (PostgREST builder subset).

Unlike the permissive stub in test_all_routes_smoke.py this one really stores rows, so tests can
run multi-turn scenarios (history, retraction, retries) through the real FastAPI routes.
Supported: select / insert (row or list) / update / delete, eq / neq / in_ / gte / lte / is_ filters,
JSON-path equality ("metadata->>user_message_id"), order, limit, count="exact", and per-table
injected failures (e.g. Postgres 42501 permission denied).
"""
from __future__ import annotations

import copy
import itertools
import types
import uuid
from datetime import datetime, timezone
from typing import Any

_clock = itertools.count(1)
_TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")   # rows default to today, so "recent" logic (e.g. the 48 h rule for resumed chats) sees them as recent


class FakeAPIError(Exception):
    """Mimics postgrest.exceptions.APIError closely enough for message/code based checks."""

    def __init__(self, message: str, code: str | None = None):
        super().__init__({"message": message, "code": code})
        self.code, self.message = code, message


def permission_denied(table: str) -> FakeAPIError:
    return FakeAPIError(f"permission denied for table {table}", "42501")


class Result:
    def __init__(self, data: Any, count: int | None = None):
        self.data, self.count = data, count


def _get(row: dict, column: str) -> Any:
    if "->>" in column or "->" in column:
        head, *path = column.replace("->>", "->").split("->")
        value: Any = row.get(head)
        for key in path:
            value = value.get(key) if isinstance(value, dict) else None
        return value if value is None else str(value)
    return row.get(column)


class Query:
    def __init__(self, db: "FakeDB", table: str):
        self.db, self.table, self.op = db, table, "select"
        self.payload: Any = None
        self.filters: list = []
        self._order: tuple[str, bool] | None = None
        self._limit: int | None = None
        self._count = False

    # ---- builder
    def select(self, *_a, count: str | None = None, **_k):
        if self.op == "select":
            self.op = "select"
        self._count = count == "exact"
        return self

    def insert(self, payload):
        self.op, self.payload = "insert", payload
        return self

    def upsert(self, payload, **_k):
        self.op, self.payload = "insert", payload
        return self

    def update(self, payload):
        self.op, self.payload = "update", payload
        return self

    def delete(self):
        self.op = "delete"
        return self

    def eq(self, col, val):
        self.filters.append(lambda r, c=col, v=val: (_get(r, c) is None and v is None) or (_get(r, c) is not None and str(_get(r, c)) == str(v)))
        return self

    def neq(self, col, val):
        self.filters.append(lambda r, c=col, v=val: str(_get(r, c)) != str(v))
        return self

    def in_(self, col, vals):
        vals = {str(v) for v in vals}
        self.filters.append(lambda r, c=col, s=vals: str(_get(r, c)) in s)
        return self

    def gte(self, col, val):
        self.filters.append(lambda r, c=col, v=val: _get(r, c) is not None and str(_get(r, c)) >= str(v))
        return self

    def lt(self, col, val):
        self.filters.append(lambda r, c=col, v=val: _get(r, c) is not None and str(_get(r, c)) < str(v))
        return self

    def lte(self, col, val):
        self.filters.append(lambda r, c=col, v=val: _get(r, c) is not None and str(_get(r, c)) <= str(v))
        return self

    def is_(self, col, val):
        self.filters.append(lambda r, c=col: _get(r, c) is None)
        return self

    def order(self, col, desc: bool = False, **_k):
        self._order = (col, desc)
        return self

    def limit(self, n):
        self._limit = n
        return self

    def single(self):
        self._limit = 1
        return self

    # ---- run
    def execute(self):
        fail = self.db.failures.get(self.table)
        if fail is not None:
            raise fail
        rows = self.db.tables.setdefault(self.table, [])
        if self.op == "insert":
            items = self.payload if isinstance(self.payload, list) else [self.payload]
            saved = []
            for item in items:
                row = copy.deepcopy(item)
                row.setdefault("id", str(uuid.uuid4()))
                row.setdefault("created_at", f"{_TODAY}T10:{next(_clock) // 60 % 60:02d}:{next(_clock) % 60:02d}+00:00")
                for unique in self.db.unique.get(self.table, ()):
                    if any(r.get(unique) is not None and r.get(unique) == row.get(unique) and r.get("user_id") == row.get("user_id") for r in rows):
                        raise FakeAPIError(f"duplicate key value violates unique constraint ({unique})", "23505")
                rows.append(row)
                saved.append(copy.deepcopy(row))
            return Result(saved, len(saved))
        matched = [r for r in rows if all(f(r) for f in self.filters)]
        if self.op == "update":
            for r in matched:
                r.update(copy.deepcopy(self.payload))
            return Result(copy.deepcopy(matched), len(matched))
        if self.op == "delete":
            for r in matched:
                rows.remove(r)
            return Result(copy.deepcopy(matched), len(matched))
        if self._order:
            col, desc = self._order
            matched.sort(key=lambda r: str(_get(r, col) or ""), reverse=desc)
        total = len(matched)
        if self._limit is not None:
            matched = matched[: self._limit]
        return Result(copy.deepcopy(matched), total if self._count else None)


class FakeAuth:
    def __init__(self, tokens: dict[str, str]):
        self.tokens = tokens

    def get_user(self, token):
        uid = self.tokens.get(token)
        if not uid:
            raise Exception("invalid token")
        return types.SimpleNamespace(user=types.SimpleNamespace(id=uid, email="t@example.com", user_metadata={"full_name": "Ashy Test"}))


class FakeDB:
    def __init__(self, tokens: dict[str, str] | None = None):
        self.tables: dict[str, list[dict]] = {}
        self.failures: dict[str, Exception] = {}
        self.unique: dict[str, tuple[str, ...]] = {"chat_messages": ("client_message_id",)}
        self.auth = FakeAuth(tokens or {"tok": "00000000-0000-0000-0000-000000000001"})

    def table(self, name: str) -> Query:
        return Query(self, name)

    def rpc(self, *_a, **_k):
        return Query(self, "_rpc")

    # test helpers
    def rows(self, table: str, **match) -> list[dict]:
        return [r for r in self.tables.get(table, []) if all(r.get(k) == v for k, v in match.items())]
