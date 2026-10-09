from pathlib import Path


def _read_migration(name: str) -> str:
    return Path(__file__).parent.parent.parent.joinpath(f'supabase/migrations/{name}').read_text(encoding='utf-8')


def test_r6_migration_scopes_bubbles_policies_to_authenticated():
    source = _read_migration('20260919_coco_r6_rls_indexes.sql')
    assert 'to authenticated' in source
    assert "replace(r.qual,'auth.uid()','(select auth.uid())')" in source
    assert 'idx_chat_messages_user_created' in source


def test_vector_extension_move_is_followed_by_pinned_rag_search_path():
    source = _read_migration('20260919_coco_r6_rag_extension_search_path.sql')
    assert 'extensions.vector' in source
    assert 'search_path = public, extensions, pg_temp' in source
