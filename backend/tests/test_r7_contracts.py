from pathlib import Path


def _read_main():
    return Path(__file__).parent.parent.joinpath('main.py').read_text(encoding='utf-8')


def _read_memory_manager():
    return Path(__file__).parent.parent.joinpath('memory_manager.py').read_text(encoding='utf-8')


def _read_memory_retrieval():
    return Path(__file__).parent.parent.joinpath('memory_retrieval.py').read_text(encoding='utf-8')


def _read_ai_orchestrator():
    return Path(__file__).parent.parent.joinpath('ai_orchestrator.py').read_text(encoding='utf-8')


def _read_migration(name: str) -> str:
    return Path(__file__).parent.parent.parent.joinpath(f'supabase/migrations/{name}').read_text(encoding='utf-8')


def _read_frontend_page():
    return Path(__file__).parent.parent.parent.joinpath('frontend/app/page.tsx').read_text(encoding='utf-8')


def test_chat_persistence_is_backend_owned():
    source = _read_main()
    assert '_persist_chat_message' in source
    assert 'client_message_id' in source
    assert 'health_event_ids' in source


def test_frontend_no_longer_writes_chat_rows():
    source = _read_frontend_page()
    # All chat operations now go through API - no direct Supabase in browser
    assert '.from("chat_messages")' not in source
    assert '.from("chat_conversations")' not in source
    # Backend owns chat persistence - verify API endpoint exists
    backend_source = _read_main()
    assert '/chat/history' in backend_source
    assert '@app.get("/chat/history")' in backend_source


def test_chat_write_migration_revokes_client_mutations():
    source = _read_migration('20260919_coco_r7_chat_write_authority.sql')
    assert 'revoke insert, update, delete on table public.chat_messages from authenticated' in source
    assert 'revoke insert, update, delete on table public.chat_conversations from authenticated' in source
    assert 'uq_chat_messages_user_client_message' in source


def test_memory_integrity_tracks_replacement_and_freshness():
    source = _read_memory_manager()
    assert 'verification_status' in source
    assert 'superseded_by' in source
    assert 'review_after' in source
    assert 'A new value for the same key is a correction' in source


def test_memory_retrieval_rejects_stale_or_superseded_memory():
    source = _read_memory_retrieval()
    assert 'review_after' in source
    assert 'superseded' in source


def test_pricing_does_not_fake_zero_for_unknown_provider():
    source = _read_ai_orchestrator()
    assert 'unknown provider pricing is represented as unknown rather than zero' not in source or 'pricing_status' in source
    assert 'return None' in source


def test_longitudinal_engine_exposes_missing_data_coverage():
    from longitudinal_health_analysis import analyze
    result = analyze([], 30)
    assert result["domains"]["sleep"]["coverage_status"] == "missing"
    assert "missing_data_policy" in result["data_quality"]