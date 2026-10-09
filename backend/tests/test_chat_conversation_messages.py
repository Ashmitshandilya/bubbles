"""GET /chat/conversations/{id}/messages: owner-scoped history read with a fake Supabase."""
import os
from types import SimpleNamespace

# Never let this test pick up real credentials from backend/.env.
os.environ.setdefault("SUPABASE_URL", "http://localhost:54321")
os.environ.setdefault("SUPABASE_SECRET_KEY", "test-key")

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

OWNER, OTHER = "user-owner", "user-other"
CONV = "11111111-1111-4111-8111-111111111111"
OTHER_CONV = "22222222-2222-4222-8222-222222222222"


class FakeQuery:
    def __init__(self, rows):
        self.rows, self.filters, self.desc, self.n = rows, [], False, None

    def select(self, *_cols):
        return self

    def eq(self, key, value):
        self.filters.append((key, value))
        return self

    def order(self, _key, desc=False):
        self.desc = desc
        return self

    def limit(self, n):
        self.n = n
        return self

    def execute(self):
        rows = [r for r in self.rows if all(r.get(k) == v for k, v in self.filters)]
        rows.sort(key=lambda r: r.get("created_at", ""), reverse=self.desc)
        return SimpleNamespace(data=rows[: self.n] if self.n else rows)


class FakeSupabase:
    def __init__(self):
        self.tables = {
            "chat_conversations": [
                {"id": CONV, "user_id": OWNER},
                {"id": OTHER_CONV, "user_id": OTHER},
            ],
            "chat_messages": [
                {"id": "m2", "conversation_id": CONV, "user_id": OWNER, "role": "bubbles",
                 "content": "Take care.", "created_at": "2026-10-06T10:00:02Z",
                 "metadata": {"safety": {"level": "AMBER", "reasons": ["x"]}}},
                {"id": "m1", "conversation_id": CONV, "user_id": OWNER, "role": "user",
                 "content": "Headache", "created_at": "2026-10-06T10:00:01Z", "metadata": {}},
                {"id": "m3", "conversation_id": CONV, "user_id": OWNER, "role": "user",
                 "content": "Thanks", "created_at": "2026-10-06T10:00:03Z", "metadata": None},
                {"id": "x1", "conversation_id": OTHER_CONV, "user_id": OTHER, "role": "user",
                 "content": "private", "created_at": "2026-10-06T09:00:00Z", "metadata": {}},
            ],
        }
        tokens = {"owner-token": OWNER, "other-token": OTHER}
        self.auth = SimpleNamespace(
            get_user=lambda token: SimpleNamespace(user=SimpleNamespace(id=tokens[token]) if token in tokens else None)
        )

    def table(self, name):
        return FakeQuery(self.tables[name])


def _client(monkeypatch):
    monkeypatch.setattr(main, "supabase", FakeSupabase())
    return TestClient(main.app)


def test_owner_reads_messages_oldest_first(monkeypatch):
    client = _client(monkeypatch)
    res = client.get(f"/chat/conversations/{CONV}/messages", headers={"Authorization": "Bearer owner-token"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "success" and body["conversation_id"] == CONV
    assert [m["id"] for m in body["messages"]] == ["m1", "m2", "m3"]
    legacy = {k: body["messages"][1][k] for k in ("id", "role", "content", "created_at", "safety_level")}
    assert legacy == {"id": "m2", "role": "bubbles", "content": "Take care.",
                      "created_at": "2026-10-06T10:00:02Z", "safety_level": "AMBER"}
    # additive contract: the persisted safety object (original level kept, retraction flagged) is exposed too
    assert body["messages"][1]["safety"]["level"] == "AMBER" and body["messages"][1]["safety"]["retracted"] is False
    assert body["messages"][0]["safety_level"] is None and body["messages"][2]["safety_level"] is None


def test_limit_keeps_the_latest_messages(monkeypatch):
    client = _client(monkeypatch)
    res = client.get(f"/chat/conversations/{CONV}/messages?limit=2", headers={"Authorization": "Bearer owner-token"})
    assert [m["id"] for m in res.json()["messages"]] == ["m2", "m3"]


def test_other_users_conversation_is_not_found(monkeypatch):
    client = _client(monkeypatch)
    res = client.get(f"/chat/conversations/{CONV}/messages", headers={"Authorization": "Bearer other-token"})
    assert res.status_code == 404
    assert "Take care" not in res.text


def test_rejects_bad_input_and_missing_auth(monkeypatch):
    client = _client(monkeypatch)
    auth = {"Authorization": "Bearer owner-token"}
    assert client.get("/chat/conversations/not-a-uuid/messages", headers=auth).status_code == 400
    assert client.get(f"/chat/conversations/{CONV}/messages?limit=0", headers=auth).status_code == 422
    assert client.get(f"/chat/conversations/{CONV}/messages?limit=201", headers=auth).status_code == 422
    assert client.get(f"/chat/conversations/{CONV}/messages").status_code == 401
