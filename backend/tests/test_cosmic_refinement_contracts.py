import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_intelligence_brief_is_authenticated_and_bounded():
    source = (ROOT / "main.py").read_text(encoding="utf-8")
    assert '/intelligence/brief' in source
    tree = ast.parse(source)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "intelligence_brief")
    body = ast.unparse(fn)
    assert "get_authenticated_user(authorization)" in body
    assert "min(request.days, 90)" in body
    assert "actions" in body
    assert "companion" in body
    assert "learning" in body


def test_public_landing_explains_memory_and_safety():
    """The public home page is the landing page (redesign 2026-10); it must keep the
    memory model and the no-diagnosis/safety framing visible to visitors."""
    page = (ROOT.parent / "frontend/app/page.tsx").read_text(encoding="utf-8")
    landing = (ROOT.parent / "frontend/app/landing/Landing.tsx").read_text(encoding="utf-8")
    assert "<Landing" in page
    # Wording changed in the scroll-story redesign; the memory model and safety framing must still be visible.
    assert "Nothing becomes memory until you confirm it" in landing
    assert "does not diagnose" in landing
    assert "Red flags first" in landing

