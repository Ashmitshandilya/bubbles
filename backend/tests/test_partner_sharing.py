"""Partner sharing: opt-in categories; connect with an invite code (both accounts) or a quick link; instant stop from either side;
no raw data; wrong guesses limited; forged rows ignored; strict isolation."""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

BACKEND = Path(__file__).resolve().parents[1]
for p in (str(BACKEND), str(BACKEND / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

import cycle_api  # noqa: E402
import doc_store  # noqa: E402
import partner_sharing as ps  # noqa: E402
from db_access import register_db_error_handlers  # noqa: E402
from fake_db import FakeDB  # noqa: E402

A, B, C = "00000000-0000-0000-0000-00000000000a", "00000000-0000-0000-0000-00000000000b", "00000000-0000-0000-0000-00000000000c"
HA, HB, HC = {"Authorization": "Bearer ta"}, {"Authorization": "Bearer tb"}, {"Authorization": "Bearer tc"}
NOTE = "I get tired and quiet before my period. A cup of tea helps."


@pytest.fixture()
def env():
    ps._attempts.clear()
    db = FakeDB({"ta": A, "tb": B, "tc": C})
    app = FastAPI()
    register_db_error_handlers(app)

    def get_user(authorization):
        uid = db.auth.tokens.get((authorization or "").removeprefix("Bearer ").strip())
        if not uid:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return type("U", (), {"id": uid})()

    app.include_router(ps.build_router(get_user, db))
    app.include_router(cycle_api.build_router(get_user, db))
    return TestClient(app, raise_server_exceptions=False), db


def settings(client, h=HA, **kw):
    body = {"categories": ["sleep", "support_note"], "note": NOTE, "owner_name": "Riya"}
    body.update(kw)
    return client.put("/partner-sharing/settings", json=body, headers=h)


def add_sleep(db, uid, nights, hours=7.5):
    today = datetime.now(timezone.utc).date()
    for i in range(nights):
        db.table("sleep_logs").insert({"user_id": uid, "sleep_date": (today - timedelta(days=i)).isoformat(), "duration_minutes": int(hours * 60),
                                       "sleep_quality": 4, "notes": "SECRET-NIGHT-NOTE"}).execute()


def link(client, days=30):
    return client.post("/partner-sharing/link", json={"expires_in_days": days}, headers=HA)


def invite(client, h=HA):
    return client.post("/partner-sharing/invite", headers=h)


# ---- access control ------------------------------------------------------------------------------------------------------

OWNER_ROUTES = [("GET", "/partner-sharing"), ("PUT", "/partner-sharing/settings"), ("POST", "/partner-sharing/link"), ("DELETE", "/partner-sharing/link"),
                ("POST", "/partner-sharing/invite"), ("DELETE", "/partner-sharing/invite"), ("DELETE", "/partner-sharing/connection"),
                ("DELETE", "/partner-sharing"), ("POST", "/partner-sharing/connect"), ("GET", "/partner-sharing/shared-with-me"),
                ("DELETE", "/partner-sharing/shared-with-me/" + "a" * 16)]


@pytest.mark.parametrize("method,path", OWNER_ROUTES)
def test_every_owner_route_needs_login(env, method, path):
    client, _ = env
    assert client.request(method, path, json={}).status_code == 401


def test_default_is_sharing_nothing(env):
    client, _ = env
    s = client.get("/partner-sharing", headers=HA).json()
    assert s["sharing"] is False and s["configured"] is False and s["connection"] is None and s["link"]["active"] is False
    assert {c["key"] for c in s["available"]} == {"cycle", "sleep", "support_note"}
    assert any("Symptoms" in x for x in s["never_shared"])
    assert client.post("/partner-sharing/link", json={"expires_in_days": 30}, headers=HA).status_code == 422     # choose what to share first
    assert invite(client).status_code == 422


def test_settings_validation(env):
    client, _ = env
    for bad in ({"categories": []}, {"categories": ["symptoms"]}, {"categories": ["sleep", "medications"]}, {"categories": "sleep"},
                {"categories": ["sleep"], "note": "x" * 501}, {"categories": ["support_note"], "note": ""}, {"categories": ["sleep"], "owner_name": "n" * 41}):
        assert client.put("/partner-sharing/settings", json=bad, headers=HA).status_code == 422, bad
    assert client.put("/partner-sharing/settings", content="not json", headers=HA).status_code == 422
    assert client.put("/partner-sharing/settings", json=["sleep"], headers=HA).status_code == 422


def test_local_only_blocks_sharing_the_cycle(env):
    client, _ = env
    client.put("/cycle/settings", json={"privacy": {"local_only": True}}, headers=HA)
    assert settings(client, categories=["cycle"], note="").status_code == 422


# ---- connect with a code -------------------------------------------------------------------------------------------------

def test_connect_flow_end_to_end(env):
    client, db = env
    add_sleep(db, A, 5)
    assert settings(client).status_code == 200
    r = invite(client)
    code = r.json()["code"]
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store" and len(code) == 9 and code[4] == "-" and "code" not in client.get("/partner-sharing", headers=HA).json()
    assert client.get("/partner-sharing", headers=HA).json()["invite"]["active"] is True
    # the partner types it in lower case with a space: still fine
    c = client.post("/partner-sharing/connect", json={"code": code.lower().replace("-", " "), "name": "Arjun"}, headers=HB)
    assert c.status_code == 200 and c.json() == {"status": "success", "connected": True, "from_name": "Riya"}
    s = client.get("/partner-sharing", headers=HA).json()
    assert s["connection"]["name"] == "Arjun" and s["invite"]["active"] is False and s["sharing"] is True
    mine = client.get("/partner-sharing/shared-with-me", headers=HB).json()["shares"]
    assert len(mine) == 1 and mine[0]["from_name"] == "Riya"
    assert [x["key"] for x in mine[0]["sections"]] == ["sleep", "support_note"]
    assert mine[0]["sections"][0]["text"] == "About 7.5 hours a night, over 5 nights." and NOTE in str(mine[0]["sections"])
    assert "SECRET-NIGHT-NOTE" not in str(mine) and "duration_minutes" not in str(mine)


def test_code_is_single_use_and_wrong_codes_fail_the_same_way(env):
    client, _ = env
    settings(client)
    code = invite(client).json()["code"]
    assert client.post("/partner-sharing/connect", json={"code": code}, headers=HB).status_code == 200
    assert client.post("/partner-sharing/connect", json={"code": code}, headers=HC).status_code == 404            # used
    for bad in ("ZZZZ-ZZZZ", "short", "", "12345678"):
        assert client.post("/partner-sharing/connect", json={"code": bad}, headers=HC).status_code == 404, bad
    assert client.get("/partner-sharing/shared-with-me", headers=HC).json()["shares"] == []


def test_expired_code_and_own_code(env):
    client, db = env
    settings(client)
    code = invite(client).json()["code"]
    assert client.post("/partner-sharing/connect", json={"code": code}, headers=HA).status_code == 422             # your own code
    cfg = doc_store.get(db, A, ps.SHARE_KIND, "main")
    doc_store.put(db, A, ps.SHARE_KIND, "main", {**cfg, "invite": {**cfg["invite"], "expires_at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()}})
    assert client.post("/partner-sharing/connect", json={"code": code}, headers=HB).status_code == 404
    assert client.get("/partner-sharing", headers=HA).json()["invite"]["active"] is False


def test_wrong_guesses_are_limited(env):
    client, _ = env
    codes = [f"AAAA-{i:04d}".replace("0", "B").replace("1", "C") for i in range(12)]
    results = [client.post("/partner-sharing/connect", json={"code": c}, headers=HC).status_code for c in codes]
    assert results[:10] == [404] * 10 and results[10:] == [429] * 2


def test_a_failed_save_leaves_no_half_connection_on_the_partner_side(env, monkeypatch):
    client, db = env
    settings(client)
    code = invite(client).json()["code"]
    real_save = ps._save
    monkeypatch.setattr(ps, "_save", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("database hiccup")))
    assert client.post("/partner-sharing/connect", json={"code": code}, headers=HB).status_code == 500
    monkeypatch.setattr(ps, "_save", real_save)
    assert client.get("/partner-sharing/shared-with-me", headers=HB).json()["shares"] == []         # the partner sees nothing half-made
    assert client.get("/partner-sharing", headers=HA).json()["connection"] is None


def test_one_partner_at_a_time(env):
    client, _ = env
    settings(client)
    client.post("/partner-sharing/connect", json={"code": invite(client).json()["code"]}, headers=HB)
    assert invite(client).status_code == 422                                          # already connected: disconnect first


def test_owner_disconnect_is_immediate_and_clean(env):
    client, db = env
    settings(client)
    client.post("/partner-sharing/connect", json={"code": invite(client).json()["code"]}, headers=HB)
    assert len(client.get("/partner-sharing/shared-with-me", headers=HB).json()["shares"]) == 1
    s = client.delete("/partner-sharing/connection", headers=HA).json()
    assert s["connection"] is None
    assert client.get("/partner-sharing/shared-with-me", headers=HB).json()["shares"] == []
    assert doc_store.list_docs(db, B, ps.WITH_KIND, 5) == []


def test_partner_can_leave_and_owner_sees_it(env):
    client, _ = env
    settings(client)
    client.post("/partner-sharing/connect", json={"code": invite(client).json()["code"]}, headers=HB)
    share_id = client.get("/partner-sharing/shared-with-me", headers=HB).json()["shares"][0]["id"]
    assert client.delete(f"/partner-sharing/shared-with-me/{share_id}", headers=HB).json()["shares"] == []
    assert client.get("/partner-sharing", headers=HA).json()["connection"] is None
    assert client.delete("/partner-sharing/shared-with-me/not-an-id", headers=HB).status_code == 404


def test_changing_what_is_shared_applies_to_the_partner_at_once(env):
    client, db = env
    add_sleep(db, A, 4)
    settings(client)
    client.post("/partner-sharing/connect", json={"code": invite(client).json()["code"]}, headers=HB)
    settings(client, categories=["sleep"], note="")
    secs = client.get("/partner-sharing/shared-with-me", headers=HB).json()["shares"][0]["sections"]
    assert [s["key"] for s in secs] == ["sleep"]


def test_stop_everything_kills_link_invite_and_connection(env):
    client, _ = env
    settings(client)
    token = link(client).json()["token"]
    invite(client)
    client.post("/partner-sharing/connect", json={"code": client.post("/partner-sharing/invite", headers=HA).json().get("code", "")}, headers=HB)
    client.delete("/partner-sharing", headers=HA)
    s = client.get("/partner-sharing", headers=HA).json()
    assert s["sharing"] is False and s["configured"] is False and s["connection"] is None and s["invite"]["active"] is False
    assert client.get(f"/partner/{token}").status_code == 404
    assert client.get("/partner-sharing/shared-with-me", headers=HB).json()["shares"] == []


def test_a_third_person_and_a_forged_share_see_nothing(env):
    client, db = env
    settings(client)
    client.post("/partner-sharing/connect", json={"code": invite(client).json()["code"]}, headers=HB)
    assert client.get("/partner-sharing/shared-with-me", headers=HC).json()["shares"] == []
    # C writes a "partner_with" pointing at A without ever being connected: the owner's settings do not list C, so it shows nothing
    doc_store.put(db, C, ps.WITH_KIND, ps._owner_id(A), {"owner_uid": A, "since": "2026-01-01T00:00:00+00:00"})
    assert client.get("/partner-sharing/shared-with-me", headers=HC).json()["shares"] == []
    assert doc_store.list_docs(db, C, ps.WITH_KIND, 5) == []                           # and the stale pointer was removed


# ---- quick link ----------------------------------------------------------------------------------------------------------

def test_quick_link_shows_only_chosen_categories_and_never_raw_logs(env):
    client, db = env
    add_sleep(db, A, 5)
    settings(client)
    r = link(client)
    token = r.json()["token"]
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store" and r.json()["share_path"] == f"/partner/{token}" and len(token) >= 30
    assert "token" not in client.get("/partner-sharing", headers=HA).json()
    pub = client.get(f"/partner/{token}")                                                 # no Authorization header
    assert pub.status_code == 200 and pub.headers["cache-control"] == "no-store"
    assert [s["key"] for s in pub.json()["sections"]] == ["sleep", "support_note"]
    assert "SECRET-NIGHT-NOTE" not in pub.text and "duration_minutes" not in pub.text


def test_link_rotate_revoke_expiry_and_bad_input(env):
    client, db = env
    settings(client)
    old = link(client).json()["token"]
    new = link(client, 7).json()["token"]
    assert client.get(f"/partner/{old}").status_code == 404 and client.get(f"/partner/{new}").status_code == 200
    assert client.post("/partner-sharing/link", json={"expires_in_days": 5}, headers=HA).status_code == 422
    cfg = doc_store.get(db, A, ps.SHARE_KIND, "main")
    doc_store.put(db, A, ps.SHARE_KIND, "main", {**cfg, "link": {**cfg["link"], "expires_at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()}})
    assert client.get(f"/partner/{new}").status_code == 404
    assert client.get("/partner-sharing", headers=HA).json()["link"]["expired"] is True
    new2 = link(client).json()["token"]
    client.delete("/partner-sharing/link", headers=HA)
    assert client.get(f"/partner/{new2}").status_code == 404


def test_forged_link_row_and_bad_tokens(env):
    client, db = env
    forged = "F" * 32
    db.table(doc_store.TABLE).insert({"user_id": A, "event_type": doc_store.EVENT_TYPE, "title": f"{ps.LINK_KIND}:{ps._hash(forged)}",
                                      "data": {"kind": ps.LINK_KIND, "key": ps._hash(forged), "payload": {"uid": A, "enabled": True}, "version": 1}}).execute()
    assert client.get(f"/partner/{forged}").status_code == 404
    for t in ("short", "x" * 200, "a-b" * 5, "dots.in.token." + "a" * 20):
        assert client.get(f"/partner/{t}").status_code == 404


def test_view_count_is_recorded_without_identifying_the_viewer(env):
    client, _ = env
    settings(client)
    token = link(client).json()["token"]
    client.get(f"/partner/{token}")
    client.get(f"/partner/{token}")
    v = client.get("/partner-sharing", headers=HA).json()["link"]["views"]
    assert v["count"] == 2 and v["last_at"] and set(v) == {"count", "last_at"}


# ---- cycle section with tips ---------------------------------------------------------------------------------------------

def test_cycle_section_has_phase_tips_for_the_partner_and_respects_local_only(env):
    client, _ = env
    today = datetime.now(timezone.utc).date()
    days = [today - timedelta(days=5 + 28 * i) for i in range(4, -1, -1)]
    for d in days:
        assert client.post("/cycle/period/start", json={"date": d.isoformat()}, headers=HA).status_code == 200
    settings(client, categories=["cycle"], note="")
    token = link(client).json()["token"]
    sec = client.get(f"/partner/{token}").json()["sections"][0]
    assert sec["key"] == "cycle" and sec["range"] and sec["tips"] and "ask them" in sec["tips_caveat"].lower()
    assert "fertile" not in str(sec).lower() and "ovulation" not in str(sec).lower().replace("ovulatory", "")
    client.put("/cycle/settings", json={"privacy": {"local_only": True}}, headers=HA)
    assert client.get(f"/partner/{token}").json()["sections"][0]["text"] == "No estimate is available right now."   # silenced, and same words as pregnancy


# ---- ghost connection, view counter isolation, attempt pruning -------------------------------------------------------------

def test_ghost_connection_is_cleared_when_the_partner_side_is_gone(env):
    client, db = env
    settings(client)
    code = invite(client).json()["code"]
    assert client.post("/partner-sharing/connect", json={"code": code, "name": "Arjun"}, headers=HB).status_code == 200
    doc_store.delete_everything(db, B)                        # the partner deleted all their data
    assert client.get("/partner-sharing", headers=HA).json()["connection"] is None
    assert invite(client).status_code == 200                  # can invite someone new


def test_public_view_does_not_resave_owner_settings(env):
    client, db = env
    settings(client)
    token = link(client).json()["token"]
    before = doc_store.get_doc(db, A, ps.SHARE_KIND, "main")["version"]
    client.get(f"/partner/{token}")
    assert doc_store.get_doc(db, A, ps.SHARE_KIND, "main")["version"] == before


def test_local_only_cycle_section_matches_no_estimate_text(env):
    client, db = env
    settings(client, categories=["cycle"], note="")
    client.put("/cycle/settings", json={"privacy": {"local_only": True}}, headers=HA)
    sec = ps._section_cycle(db, A)
    assert sec and sec["text"] == "No estimate is available right now."


def test_stale_attempt_entries_are_pruned():
    ps._attempts.clear()
    ps._attempts["old"] = [0.0]
    ps._attempts["empty"] = []
    ps._throttle("someone")
    assert "old" not in ps._attempts and "empty" not in ps._attempts
