"""No unauthenticated request may reach the database or succeed on the router-based feature APIs.

Each router is built with a get_user that refuses everyone and a database that fails the test if touched, then EVERY route is called
without credentials. Public routes are listed explicitly (the partner share link authenticates by its own token)."""
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

import cycle_api
import data_rights
import fitness_api
import health_logs
import import_api
import insights_api
import partner_sharing
import wellness_api

PUBLIC = {("GET", "/cycle/partner/{token}"), ("POST", "/cycle/partner-view"), ("GET", "/partner/{token}")}  # token-based, rate-limited public partner link


class TouchedDB:
    touched = False

    def __getattr__(self, name):
        TouchedDB.touched = True
        raise AssertionError(f"database touched without authentication: {name}")


def refuse(_authorization=None):
    raise HTTPException(status_code=401, detail="Authentication required")


BUILDERS = [health_logs.build_router, fitness_api.build_router, data_rights.build_router, wellness_api.build_router,
            import_api.build_router, cycle_api.build_router, partner_sharing.build_router, insights_api.build_router]


def find_leaks(router):
    TouchedDB.touched = False
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app, raise_server_exceptions=False)
    routes = [r for r in router.routes if isinstance(r, APIRoute)]
    assert routes, "router has no routes (test would be vacuous)"
    leaks = []
    for r in routes:
        path = r.path
        for p in r.dependant.path_params:
            path = path.replace("{" + p.name + "}", "00000000-0000-0000-0000-000000000000")
        path = path.replace("{day}", "2026-01-01")
        for method in sorted(r.methods - {"HEAD", "OPTIONS"}):
            if (method, r.path) in PUBLIC:
                continue
            resp = client.request(method, path, json={})
            if resp.status_code < 300 or TouchedDB.touched:
                leaks.append((method, r.path, resp.status_code))
    return leaks


@pytest.mark.parametrize("builder", BUILDERS, ids=lambda b: b.__module__)
def test_every_route_refuses_without_credentials(builder):
    leaks = find_leaks(builder(refuse, TouchedDB()))
    assert not leaks, f"unauthenticated access: {leaks}"


def test_negative_control_an_unprotected_route_is_detected():
    from fastapi import APIRouter
    r = APIRouter()

    @r.get("/open")
    def open_route():  # forgot to authenticate
        return {"ok": True}

    assert find_leaks(r) == [("GET", "/open", 200)]


def test_main_app_routes_call_get_authenticated_user_except_health():
    """Static guard for main.py's own routes (running them needs the real database): a new route without the call fails here."""
    import inspect

    import main
    missing = [r.path for r in main.app.routes if isinstance(r, APIRoute) and "get_authenticated_user" not in inspect.getsource(r.endpoint)]
    assert missing == ["/health"], missing
