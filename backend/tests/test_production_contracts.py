from pathlib import Path
import ast


def _read_main():
    return Path(__file__).parent.parent.joinpath('main.py').read_text(encoding='utf-8')


def _read_ai_provider():
    return Path(__file__).parent.parent.joinpath('ai_provider.py').read_text(encoding='utf-8')


def _read_bubbles_ai():
    return Path(__file__).parent.parent.joinpath('bubbles_ai.py').read_text(encoding='utf-8')


def _read_migration():
    return Path(__file__).parent.parent.parent.joinpath('supabase/migrations/20260919_coco_storage_reconciliation.sql').read_text(encoding='utf-8')


def test_api_routes_are_unique():
    tree = ast.parse(_read_main())
    routes = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
                if decorator.func.attr in {'get', 'post', 'put', 'patch', 'delete'} and decorator.args:
                    path = decorator.args[0]
                    if isinstance(path, ast.Constant) and isinstance(path.value, str):
                        routes.append((decorator.func.attr.upper(), path.value))
    assert len(routes) == len(set(routes)), [r for r in routes if routes.count(r) > 1]


def test_public_supabase_debug_endpoint_is_removed():
    source = _read_main()
    assert '@app.get("/supabase-test")' not in source


def test_extracted_event_schema_matches_pipeline_contract():
    migration = _read_migration()
    assert 'extraction_status text not null default' in migration
    assert 'idx_extracted_events_user_status' in migration


def test_health_event_window_is_time_bounded():
    source = _read_main()
    function = source[source.index('def _get_user_health_events'):source.index('@app.get("/insights/weekly"')]
    assert 'timedelta(days=days)' in function
    assert '.gte("created_at", cutoff)' in function


def test_red_safety_path_has_hard_llm_gate():
    """EMERGENCY (legacy RED) must be answered deterministically, never through a model.

    chat() now routes every turn with route_turn(); emergency is the first route and the model call
    lives only in the final else-branch.
    """
    source = _read_main()
    routes = '_DETERMINISTIC_ROUTES = {"emergency", "correction", "clarification", "daily_log", "fitness_support", "fitness_answer", "small_talk", "safety_followup", "recall", "remembered"}'
    assert routes in source          # emergency is on the list of routes that never reach a model
    gate = 'if turn.route in _DETERMINISTIC_ROUTES or state.consent_required:'
    assert gate in source
    assert 'state.consent_required = turn.route not in _DETERMINISTIC_ROUTES and not has_ai_consent(' in source  # consent can only ADD a reason not to call a model
    start = source.index(gate)
    ai_branch = source.index("ctx_job = submit(_context_stage,", start)   # the first line of the branch that talks to a model
    deterministic_block = source[start:ai_branch]
    assert "deterministic_reply(" in deterministic_block
    assert "ask_bubbles(" not in deterministic_block
    assert source.index("ask_bubbles(", start) > ai_branch
    # the router itself must put emergency before every other route
    import chat_pipeline
    import inspect
    router = inspect.getsource(chat_pipeline.route_turn)
    assert router.index('"emergency"') < router.index('"correction"') < router.index('"clarification"')


def test_red_response_is_explicitly_urgent():
    source = _read_main()
    assert 'Please get urgent medical help' in source
    assert 'local emergency service' in source
    assert 'red-flag symptom' in source


def test_keyless_providers_are_not_in_health_fallback_by_default():
    source = _read_ai_provider()
    assert 'AUTHENTICATED_PROVIDERS' in source
    assert 'if ALLOW_KEYLESS_AI and (not health_data or ALLOW_KEYLESS_HEALTH_DATA):' in source
    assert 'health_data=True' in _read_bubbles_ai()


def test_keyless_provider_is_not_in_authenticated_default_pool():
    source = _read_ai_provider()
    start = source.index('AUTHENTICATED_PROVIDERS = [')
    end = source.index(']\n\nKEYLESS_PROVIDERS', start)
    default_pool = source[start:end]
    assert 'KeylessAI' not in default_pool
    assert 'Kilo' not in default_pool
    assert 'Murakumo' not in default_pool
    assert 'BlockRun' not in default_pool
    assert 'Animica' not in default_pool


def test_free_model_policy_fails_closed_for_unknown_provider():
    source = _read_ai_provider()
    assert 'if not allowed or model not in allowed' in source


def test_public_debug_endpoint_is_removed():
    source = _read_main()
    assert '@app.get("/bubbles-test")' not in source


def test_cors_is_not_wildcarded():
    source = _read_main()
    assert 'allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]' in source
    # explicit list, never "*"; X-Tz-Offset-Minutes carries the user's clock so "today" is their day, not UTC
    assert 'allow_headers=["Authorization", "Content-Type", "X-Tz-Offset-Minutes"]' in source
    assert 'allow_headers=["*"]' not in source
    assert "allow_credentials=False" in source           # Bearer tokens, no cookies
    assert 'None if os.getenv("RENDER")' in source        # the localhost regex is development-only


def test_living_map_is_get_not_post():
    """Verify /intelligence/living-map endpoint is GET, not POST."""
    source = _read_main()
    # Should have GET decorator for living-map
    assert '/intelligence/living-map' in source and '@app.get' in source
    # Should NOT have POST decorator for living-map
    assert '@app.post("/intelligence/living-map")' not in source


def test_living_map_requires_auth():
    """Verify living-map endpoint requires Authorization header."""
    source = _read_main()
    # Find the living_map function and verify it uses get_authenticated_user
    living_map_start = source.index('def living_signal_map')
    living_map_end = source.index('\n\n', living_map_start)
    living_map_func = source[living_map_start:living_map_end]
    assert 'authorization: str | None = Header(default=None)' in living_map_func
    assert 'get_authenticated_user(authorization)' in living_map_func


def test_living_map_bounded_days():
    """Verify living-map endpoint validates days parameter bounds (1-90)."""
    source = _read_main()
    living_map_start = source.index('def living_signal_map')
    living_map_end = source.index('\n\n', living_map_start)
    living_map_func = source[living_map_start:living_map_end]
    assert 'days: int = Query(default=14, ge=1, le=90)' in living_map_func


def test_living_map_uses_bounded_events():
    """Verify living-map fetches events via _bounded_events helper."""
    source = _read_main()
    living_map_start = source.index('def living_signal_map')
    living_map_end = source.index('\n\n', living_map_start)
    living_map_func = source[living_map_start:living_map_end]
    assert '_bounded_events(str(user.id), days * 2)' in living_map_func
    # Should pass events (not user.id string) to both processing functions
    assert '_health_state(events, days)' in living_map_func   # build_health_state through the helper that shares it inside one Today request
    assert 'build_health_state(events, days=days)' in source[source.index('def _health_state'):source.index('def _get_user_health_events')]
    assert 'analyze_longitudinal(events, days=days)' in living_map_func