"""Guard: supabase-py builders returned by insert/update/upsert/delete have no
.single/.limit/.order/.range. Unit-test fakes used to hide such calls (they
raised AttributeError in production and were swallowed by broad except blocks)."""
import ast
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
UNAVAILABLE_AFTER_WRITE = {"single", "maybe_single", "limit", "order", "range"}


def _chain(node):
    out = []
    while isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        out.append((node.func.attr, node.lineno))
        node = node.func.value
    return list(reversed(out))


def test_no_invalid_calls_after_supabase_writes():
    offenders = []
    for path in BACKEND.glob("**/*.py"):
        if {"venv", "tests", "__pycache__"} & set(path.relative_to(BACKEND).parts):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "execute":
                chain = _chain(node)
                write = next((i for i, (name, _) in enumerate(chain) if name in {"insert", "update", "upsert", "delete"}), None)
                if write is None:
                    continue
                bad = [(name, line) for name, line in chain[write + 1:] if name in UNAVAILABLE_AFTER_WRITE]
                if bad:
                    offenders.append(f"{path.name}:{chain[write][1]} {chain[write][0]} -> {bad}")
    assert not offenders, offenders
