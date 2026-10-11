"""Two-step sign-in is enforced on the server, not only in the browser."""
from __future__ import annotations

import base64
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import auth_assurance as A


def jwt_with(claims: dict) -> str:
    def enc(obj):
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip("=")
    return f"{enc({'alg': 'HS256'})}.{enc(claims)}.signature"


FACTOR_OK = SimpleNamespace(id="f1", factor_type="totp", status="verified")
FACTOR_PENDING = SimpleNamespace(id="f2", factor_type="totp", status="unverified")


def test_reads_the_aal_claim_and_ignores_garbage():
    assert A.token_aal(jwt_with({"aal": "aal2"})) == "aal2"
    assert A.token_aal(jwt_with({"aal": "aal1"})) == "aal1"
    assert A.token_aal(jwt_with({"sub": "x"})) is None
    assert A.token_aal(jwt_with({"aal": 2})) is None
    for junk in ["", "abc", "a.b", "a.%%%.c", "not a token at all"]:
        assert A.token_aal(junk) is None


def test_only_a_verified_factor_counts():
    assert A.has_verified_factor(SimpleNamespace(factors=[FACTOR_OK])) is True
    assert A.has_verified_factor(SimpleNamespace(factors=[FACTOR_PENDING])) is False
    assert A.has_verified_factor(SimpleNamespace(factors=None)) is False
    assert A.has_verified_factor(SimpleNamespace()) is False
    assert A.has_verified_factor({"factors": [{"status": "verified"}]}) is True


def test_password_only_session_is_refused_for_two_step_accounts():
    user = SimpleNamespace(factors=[FACTOR_OK])
    assert A.requires_second_step(user, jwt_with({"aal": "aal1"})) is True
    assert A.requires_second_step(user, jwt_with({})) is True          # no claim: fail closed for these accounts
    assert A.requires_second_step(user, jwt_with({"aal": "aal2"})) is False


def test_accounts_without_two_step_are_never_affected():
    for user in (SimpleNamespace(factors=None), SimpleNamespace(factors=[FACTOR_PENDING]), SimpleNamespace(factors=[])):
        assert A.requires_second_step(user, jwt_with({"aal": "aal1"})) is False


def test_get_authenticated_user_enforces_it(monkeypatch):
    # main reads its Supabase settings at import; dummy values are enough because get_user is replaced below and nothing touches the network
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:9")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_dummy_for_tests")
    main = pytest.importorskip("main")

    def fake_get_user(token):
        return SimpleNamespace(user=SimpleNamespace(id="u1", factors=[FACTOR_OK]))

    monkeypatch.setattr(main.supabase.auth, "get_user", fake_get_user, raising=False)
    with pytest.raises(HTTPException) as refused:
        main.get_authenticated_user("Bearer " + jwt_with({"aal": "aal1"}))
    assert refused.value.status_code == 401
    assert "second step" in str(refused.value.detail).lower() or "two-step" in str(refused.value.detail).lower()
    user = main.get_authenticated_user("Bearer " + jwt_with({"aal": "aal2"}))
    assert user.id == "u1"
