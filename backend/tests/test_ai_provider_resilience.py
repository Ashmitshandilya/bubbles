from pathlib import Path


def test_provider_has_bounded_transient_retry():
    import os
    source = open(os.path.join(os.path.dirname(__file__), '..', 'ai_provider.py'), encoding='utf-8').read()
    assert 'AI_MAX_RETRIES' in source
    assert 'response.status_code == 429 or response.status_code >= 500' in source
    assert 'time.sleep((AI_RETRY_BACKOFF_MS / 1000.0)' in source


def test_ai_telemetry_endpoint_is_authenticated():
    source = Path(__file__).parent.parent.joinpath('main.py').read_text(encoding='utf-8')
    start = source.index('@app.get("/ai/telemetry"')
    end = source.index('@app.post("/ai/route")', start)
    block = source[start:end]
    assert 'get_authenticated_user(authorization)' in block
    assert 'ai_telemetry_snapshot()' in block
