"""Smoke: every route answers valid minimal requests without a 5xx.

Uses a permissive in-memory fake Supabase, stubbed AI providers and dummy env;
never reads real credentials and never touches the network.
"""
from __future__ import annotations

import os
import re
import sys
import types
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


class _Result:
    def __init__(self, data, count=None):
        self.data, self.count = data, count


class _Query:
    def __init__(self, rows=None):
        self._payload, self._single = None, False

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)

        def call(*args, **kwargs):
            if name in ("insert", "upsert", "update") and args:
                self._payload = args[0]
            if name in ("single", "maybe_single"):
                self._single = True
            return self
        return call

    def execute(self):
        p = self._payload
        if p is None:
            return _Result(None if self._single else [], 0)
        rows = [dict(r, id=r.get("id", "id-1")) for r in (p if isinstance(p, list) else [p])]
        return _Result(rows[0] if self._single else rows, len(rows))


class _FakeAuth:
    def get_user(self, token):
        return types.SimpleNamespace(user=types.SimpleNamespace(
            id="00000000-0000-0000-0000-000000000001", email="t@example.com"))


class _FakeSupabase:
    auth = _FakeAuth()

    def table(self, name):
        return _Query()

    def rpc(self, name, params=None):
        return _Query()


def _fill(schema, spec, depth=0):
    if "$ref" in schema:
        return _fill(spec["components"]["schemas"][schema["$ref"].split("/")[-1]], spec, depth)
    for key in ("anyOf", "oneOf", "allOf"):
        if key in schema:
            opts = [o for o in schema[key] if o.get("type") != "null"] or schema[key]
            return _fill(opts[0], spec, depth)
    if "default" in schema:
        return schema["default"]
    if "enum" in schema:
        return schema["enum"][0]
    t = schema.get("type")
    if t == "object" or "properties" in schema:
        if depth > 4:
            return {}
        req = schema.get("required", [])
        return {k: _fill(v, spec, depth + 1) for k, v in schema.get("properties", {}).items() if k in req}
    if t == "array":
        return []
    if t == "string":
        f = schema.get("format")
        return {"date-time": "2026-01-01T00:00:00Z", "date": "2026-01-01"}.get(f, "test")
    if t == "integer":
        return max(schema.get("minimum", 1), 1)
    if t == "number":
        return max(schema.get("minimum", 1), 1)
    if t == "boolean":
        return False
    return "test"


@pytest.fixture(scope="module")
def client():
    for k in ("GROQ_API_KEY", "NVIDIA_API_KEY", "ZAI_API_KEY", "AIML_API_KEY", "SAMBANOVA_API_KEY",
              "HYPERBOLIC_API_KEY", "MISTRAL_API_KEY", "CEREBRAS_API_KEY", "CLOUDFLARE_API_TOKEN",
              "GEMINI_API_KEY", "GOOGLE_API_KEY"):
        os.environ.pop(k, None)
    os.environ.update(SUPABASE_URL="http://localhost", SUPABASE_SECRET_KEY="dummy",
                      ALLOW_PAID_AI="false", ALLOW_KEYLESS_AI="false", COMMUNITY_ALIAS_SECRET="smoke-test-secret-0123456789")
    fake_mod = types.ModuleType("supabase_client")
    fake_mod.supabase = _FakeSupabase()
    saved = sys.modules.get("supabase_client")
    sys.modules["supabase_client"] = fake_mod
    for m in ("main", "memory_manager", "memory_retrieval", "memory_promotion",
              "context_engine", "rag", "rl.service", "health_logs"):
        sys.modules.pop(m, None)
    import ai_provider
    import main
    import rag
    rag.embed_text = lambda *a, **k: None
    from fastapi.testclient import TestClient

    def no_network(*a, **k):
        raise RuntimeError("network disabled in smoke test")
    for name in dir(ai_provider):
        if name.startswith("call_") or name == "_post_json":
            setattr(ai_provider, name, no_network)
    yield TestClient(main.app, raise_server_exceptions=False), main.app
    if saved is not None:
        sys.modules["supabase_client"] = saved
    else:
        sys.modules.pop("supabase_client", None)
    for m in ("main", "memory_manager", "memory_retrieval", "memory_promotion",
              "context_engine", "rag", "rl.service", "health_logs"):
        sys.modules.pop(m, None)


def test_no_route_returns_5xx(client):
    c, app = client
    spec = app.openapi()
    headers = {"Authorization": "Bearer test-token"}
    failures = []
    tested = 0
    for path, ops in spec["paths"].items():
        for method, op in ops.items():
            if method not in ("get", "post", "put", "patch", "delete"):
                continue
            url = re.sub(r"\{[^}]+\}", "00000000-0000-0000-0000-000000000002", path)
            params = {p["name"]: _fill(p["schema"], spec) for p in op.get("parameters", [])
                      if p["in"] == "query" and p.get("required")}
            body = None
            rb = op.get("requestBody", {}).get("content", {}).get("application/json")
            if rb:
                body = _fill(rb["schema"], spec)
            r = c.request(method.upper(), url, params=params, json=body, headers=headers)
            tested += 1
            if r.status_code >= 500:
                failures.append(f"{method.upper()} {path} -> {r.status_code} {r.text[:200]}")
    assert tested > 50
    assert not failures, "\n".join(failures)
