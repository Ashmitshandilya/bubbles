import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _main_source():
    return (ROOT / "main.py").read_text(encoding="utf-8")


def test_next_actions_endpoint_exists_and_is_authenticated():
    source = _main_source()
    assert '/intelligence/next-actions' in source and '@app.post' in source
    start = source.index('def intelligence_next_actions')
    end = source.index('def intelligence_learning', start)
    block = source[start:end]
    assert "get_authenticated_user(authorization)" in block
    assert "data_gaps" in block
    assert '"actions"' in block


def test_next_actions_are_bounded_and_deterministic():
    source = _main_source()
    tree = ast.parse(source)
    endpoint = next(
        n for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "intelligence_next_actions"
    )
    body = ast.unparse(endpoint)
    assert "min(request.days, 90)" in body
    assert "actions[:6]" in body
    assert "build_health_state" in body


def test_frontend_consumes_adaptive_action_endpoint():
    # Today reads the brief (state, learning and the adaptive actions) from the one /today call, whose brief part is /intelligence/brief's data.
    page = (ROOT.parent / "frontend/app/dashboard/dashboard/DashboardClient.tsx").read_text(encoding="utf-8")
    assert "TODAY_PATH" in page and "briefData?.actions" in page
    assert '"/today' in (ROOT.parent / "frontend/app/dashboard/dashboard/bundle.ts").read_text(encoding="utf-8")
    assert "WorthALook" in (ROOT.parent / "frontend/app/dashboard/dashboard/TodaySections.tsx").read_text(encoding="utf-8")
    main = (ROOT / "main.py").read_text(encoding="utf-8")
    assert 'intelligence_brief(InteractionRequest(days=days), authorization)' in main   # the bundle's brief IS the brief route's answer
