from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read_backend_main():
    return (ROOT / "backend" / "main.py").read_text(encoding='utf-8')


def _read_frontend_page():
    return (ROOT / "frontend" / "app" / "page.tsx").read_text(encoding='utf-8')


def test_v3_chat_request_has_bounded_payload_fields():
    source = _read_backend_main()
    assert 'message: str = Field(default="", max_length=8000)' in source
    assert 'message_id: str | None = Field(default=None, min_length=16, max_length=128)' in source
    assert 'conversation_id: str | None = Field(default=None, max_length=64)' in source


def test_v3_chat_idempotency_handles_concurrent_unique_winner():
    source = _read_backend_main()
    assert 'A concurrent retry can win the unique idempotency race' in source
    assert 'eq("client_message_id", client_message_id)' in source


def test_v3_browser_is_read_only_for_chat_persistence():
    # Verify chat writes go through authenticated API, not direct Supabase
    frontend_root = ROOT / "frontend"
    companion_client = (frontend_root / "app/companion/CompanionClient.tsx").read_text(encoding='utf-8')
    # Chat UI sends message_id to /chat endpoint - not direct Supabase writes
    assert '/chat' in companion_client
    assert 'message_id:' in companion_client
    # No direct Supabase table access for chat
    assert '.from("chat_messages")' not in companion_client
    assert '.from("chat_conversations")' not in companion_client
    assert '.insert(' not in companion_client


def test_v3_no_health_payload_console_logging_in_main_ui():
    source = _read_frontend_page()
    assert 'Health events received from backend:' not in source
    assert 'Persisted health event IDs:' not in source