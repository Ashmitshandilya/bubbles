"""Community API: gates, aliases, limits, moderation wiring, reports, blocks, admin, delete-my-data. FakeDB, no network, no AI."""
from __future__ import annotations

import json
import types
import uuid
from datetime import timedelta

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

import community_api as ca
import doc_store
from fake_db import FakeDB, grant_consent

SECRET = "x" * 32
ADMIN = "aaaaaaaa-0000-0000-0000-00000000000a"
IDS = {n: str(uuid.UUID(int=i + 1)) for i, n in enumerate(["ann", "ben", "cat", "dan", "eve", "fay", "gus"])}
TOKENS = {f"t-{n}": u for n, u in IDS.items()}
TOKENS["t-admin"] = ADMIN
GOOD = "I have been sleeping badly for a week and feel tired in the afternoons. What helped you wind down?"


class Env:
    def __init__(self):
        self.db = FakeDB(TOKENS)
        app = FastAPI()

        def get_user(authorization):
            tok = (authorization or "").replace("Bearer ", "")
            if tok not in TOKENS:
                raise HTTPException(status_code=401, detail="Invalid token")
            return types.SimpleNamespace(id=TOKENS[tok])

        @app.middleware("http")
        async def admin_stub(request: Request, call_next):   # stands in for main._admin_gate: only t-admin is an admin, else the plain 404
            if request.url.path.startswith("/admin"):
                tok = request.headers.get("authorization", "").replace("Bearer ", "")
                if tok != "t-admin":
                    from fastapi.responses import JSONResponse
                    return JSONResponse({"detail": "Not Found"}, status_code=404)
                request.state.admin_user_id = ADMIN
            return await call_next(request)

        app.include_router(ca.build_router(get_user, self.db))
        self.client = TestClient(app, raise_server_exceptions=False)
        self.clock = ca._now()

    def h(self, who):
        return {"Authorization": f"Bearer t-{who}"}

    def adult(self, who, born="1990-05-05", name="Asha"):
        doc_store.put(self.db, IDS[who], "onboarding", "v1", {"answers": {"birth_date": born, "preferred_name": name}})

    def member(self, who):
        self.adult(who)
        grant_consent(self.db, IDS[who], "community_visibility")

    def get(self, who, path, **kw):
        return self.client.get(path, headers=self.h(who), **kw)

    def post(self, who, path, body, **kw):
        return self.client.post(path, headers=self.h(who), json=body, **kw)

    def new_post(self, who="ann", body=GOOD, topic="sleep", anonymous=True):
        return self.post(who, "/community/posts", {"topic": topic, "body": body, "anonymous": anonymous})


@pytest.fixture()
def env(monkeypatch):
    monkeypatch.setenv("COMMUNITY_ALIAS_SECRET", SECRET)
    e = Env()
    for n in ("ann", "ben", "cat", "dan"):
        e.member(n)
    return e


def codes(res):
    d = res.json().get("detail")
    return d.get("code") if isinstance(d, dict) else None


def uuids_in(obj):
    return [u for u in IDS.values() if u in json.dumps(obj)]


# ---- the gates -----------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("method,path", [("get", "/community/status"), ("get", "/community/posts"), ("post", "/community/posts"), ("delete", "/community/me"),
                                         ("post", "/community/reports"), ("post", "/community/reactions"), ("post", "/community/blocks")])
def test_unauthenticated_is_refused_everywhere(env, method, path):
    body = {"topic": "sleep", "body": GOOD, "target": f"post:{uuid.uuid4()}", "kind": "helpful", "reason": "spam"}
    kw = {"json": body} if method == "post" else {}
    assert getattr(env.client, method)(path, **kw).status_code == 401
    assert getattr(env.client, method)(path, headers={"Authorization": "Bearer nope"}, **kw).status_code == 401


def test_a_post_without_the_consent_is_refused_and_nothing_is_stored(env):
    env.adult("eve")
    res = env.new_post("eve")
    assert (res.status_code, codes(res)) == (403, "consent_needed")
    assert env.db.rows("community_posts") == []
    assert env.get("eve", "/community/posts").status_code == 200   # reading needs no consent
    assert env.get("eve", "/community/status").json()["reason"] == "consent_needed"


def test_withdrawing_the_consent_closes_posting_again(env):
    import consent
    assert env.new_post("ann").status_code == 200
    consent.set_purpose(env.db, IDS["ann"], "community_visibility", False, source="settings")
    consent.forget(IDS["ann"])
    assert codes(env.new_post("ann", body=GOOD + " Again?")) == "consent_needed"


def test_withdrawing_the_consent_hides_what_they_already_posted(env):
    import consent
    pid = env.new_post("ann").json()["post"]["id"]
    consent.set_purpose(env.db, IDS["ann"], "community_visibility", False, source="settings")
    consent.forget(IDS["ann"])
    assert [r["status"] for r in env.db.rows("community_posts") if r["id"] == pid] == ["held"]


@pytest.mark.parametrize("doc", [None, {"answers": {}}, {"age_gate": "under_18"}, {"answers": {"birth_date": "2012-01-01"}}, {"answers": {"birth_date": "junk"}}])
def test_under_18_or_unknown_age_cannot_read_or_post(env, doc):
    grant_consent(env.db, IDS["eve"], "community_visibility")
    if doc is not None:
        doc_store.put(env.db, IDS["eve"], "onboarding", "v1", doc)
    for res in (env.new_post("eve"), env.get("eve", "/community/posts"), env.get("eve", f"/community/posts/{uuid.uuid4()}/comments")):
        assert (res.status_code, codes(res)) == (403, "adults_only")
    assert env.get("eve", "/community/status").json()["can_read"] is False
    assert env.db.rows("community_posts") == []


def test_exactly_18_today_is_allowed_and_one_day_short_is_not(env):
    from calc_core import local_today
    t = local_today()
    ok = t.replace(year=t.year - 18).isoformat()
    short = (t.replace(year=t.year - 18) + timedelta(days=1)).isoformat()
    env.adult("eve", born=ok)
    grant_consent(env.db, IDS["eve"], "community_visibility")
    assert env.new_post("eve").status_code == 200
    env.adult("fay", born=short)
    grant_consent(env.db, IDS["fay"], "community_visibility")
    assert codes(env.new_post("fay")) == "adults_only"


def test_a_banned_person_can_read_but_not_post_react_or_report(env):
    env.db.table("community_bans").insert({"user_id": IDS["ben"], "reason_code": "admin"}).execute()
    pid = env.new_post("ann").json()["post"]["id"]
    assert env.get("ben", "/community/posts").status_code == 200
    assert codes(env.new_post("ben")) == "not_allowed"
    assert codes(env.post("ben", f"/community/posts/{pid}/comments", {"body": GOOD})) == "not_allowed"
    assert codes(env.post("ben", "/community/reactions", {"target": f"post:{pid}", "kind": "helpful"})) == "not_allowed"
    assert codes(env.post("ben", "/community/reports", {"target": f"post:{pid}", "reason": "spam"})) == "not_allowed"


def test_without_the_alias_secret_the_feature_refuses_with_no_weak_default(env, monkeypatch):
    for value in (None, "", "short", " " * 40):
        if value is None:
            monkeypatch.delenv("COMMUNITY_ALIAS_SECRET", raising=False)
        else:
            monkeypatch.setenv("COMMUNITY_ALIAS_SECRET", value)
        assert ca.enabled() is False
        assert (env.new_post("ann").status_code, codes(env.new_post("ann"))) == (503, "community_off")
        assert env.get("ann", "/community/posts").status_code == 503
        s = env.get("ann", "/community/status").json()
        assert s["enabled"] is False and s["can_post"] is False
        with pytest.raises(HTTPException):
            ca.alias_for(IDS["ann"], "thread")
        a = env.client.get("/admin/community/status", headers=env.h("admin")).json()
        assert a["enabled"] is False and "COMMUNITY_ALIAS_SECRET" in a["message"]
    assert env.db.rows("community_posts") == []


def test_the_migration_not_applied_degrades_to_off(env):
    env.db.failures["community_posts"] = RuntimeError("relation does not exist")
    assert env.get("ann", "/community/status").json()["enabled"] is False
    res = env.get("ann", "/community/posts")
    assert res.status_code == 503 and "does not exist" not in res.text


# ---- aliases and anonymity -----------------------------------------------------------------------------------------------

def test_alias_is_stable_per_thread_differs_across_threads_and_people(env):
    a1 = env.new_post("ann").json()["post"]
    a2 = env.new_post("ann", body=GOOD + " (second thread)").json()["post"]
    b1 = env.new_post("ben", body=GOOD + " ben").json()["post"]
    assert a1["alias"] != a2["alias"] and a1["alias"] != b1["alias"]
    assert ca.alias_for(IDS["ann"], a1["id"]) == a1["alias"] == ca.alias_for(IDS["ann"], a1["id"])
    c1 = env.post("ann", f"/community/posts/{a1['id']}/comments", {"body": "Glad you asked, a warm shower helps me."}).json()["comment"]
    c2 = env.post("ann", f"/community/posts/{a1['id']}/comments", {"body": "Also no screens late helps me a lot."}).json()["comment"]
    assert c1["alias"] == c2["alias"] == a1["alias"]                      # the same person in one thread keeps the one name
    other = env.post("ann", f"/community/posts/{b1['id']}/comments", {"body": "Replying on another thread here."}).json()["comment"]
    assert other["alias"] != c1["alias"]
    import re
    assert re.fullmatch(r"[A-Z][a-z]+ [A-Z][a-z]+ \d{4}", a1["alias"])


def test_no_response_ever_holds_an_author_id(env):
    pid = env.new_post("ann").json()["post"]["id"]
    env.post("ben", f"/community/posts/{pid}/comments", {"body": "Thanks for sharing this with us today."})
    env.post("cat", "/community/reactions", {"target": f"post:{pid}", "kind": "helpful"})
    env.post("cat", "/community/reports", {"target": f"post:{pid}", "reason": "spam"})
    out = [env.get("ben", "/community/posts"), env.get("ann", "/community/posts?mine=true"), env.get("cat", f"/community/posts/{pid}/comments"),
           env.new_post("dan", body=GOOD + " dan"), env.get("ben", "/community/status")]
    for r in out:
        assert r.status_code == 200
        assert uuids_in(r.json()) == [], r.text
        assert "author_id" not in r.text and "user_id" not in r.text


def test_named_mode_shows_a_first_name_only_and_falls_back_to_the_alias(env):
    env.adult("ann", name="Asha Verma")
    p = env.new_post("ann", anonymous=False).json()["post"]
    assert p["alias"] == "Asha" and p["anonymous"] is False
    env.adult("ben", name="Ben0 the 3rd")
    q = env.new_post("ben", body=GOOD + "b", anonymous=False).json()["post"]
    assert q["alias"] == ca.alias_for(IDS["ben"], q["id"])


def test_a_rotated_secret_changes_new_names_but_old_posts_and_admin_lookup_still_work(env, monkeypatch):
    p = env.new_post("ann").json()["post"]
    monkeypatch.setenv("COMMUNITY_ALIAS_SECRET", "y" * 32)
    shown = env.get("ben", "/community/posts").json()["posts"]
    assert shown[0]["alias"] == p["alias"]                                    # stored names do not change
    assert ca.alias_for(IDS["ann"], p["id"]) != p["alias"]                    # a new one would
    r = env.client.post("/admin/community/resolve", headers=env.h("admin"), json={"target": f"post:{p['id']}"})
    assert r.json()["user_id"] == IDS["ann"]


# ---- length, rate limits, duplicates --------------------------------------------------------------------------------------

def text_of(n, seed="a"):
    words = []
    i = 0
    while sum(len(w) + 1 for w in words) < n + 1:
        words.append(f"w{seed}{i}")
        i += 1
    return " ".join(words)[:n].rstrip().ljust(n, "z")


@pytest.mark.parametrize("n,ok", [(1200, True), (1201, False)])
def test_post_length_boundary(env, n, ok):
    res = env.new_post("ann", body=text_of(n))
    assert (res.status_code == 200) is ok
    if not ok:
        assert codes(res) == "too_long"


@pytest.mark.parametrize("n,ok", [(600, True), (601, False)])
def test_comment_length_boundary(env, n, ok):
    pid = env.new_post("ben").json()["post"]["id"]
    res = env.post("ann", f"/community/posts/{pid}/comments", {"body": text_of(n)})
    assert (res.status_code == 200) is ok


def test_empty_whitespace_and_huge_bodies_are_refused(env):
    for body in ("", "   \n\t ", "​​"):
        assert env.new_post("ann", body=body).status_code == 422
    assert env.new_post("ann", body="x " * 100000).status_code == 422             # pydantic cap
    assert env.client.post("/community/posts", headers=env.h("ann"), content=b"{" + b"1" * 3000000).status_code == 422
    assert env.db.rows("community_posts") == []


def test_five_posts_an_hour_and_the_sixth_is_slowed(env):
    for i in range(5):
        assert env.new_post("ann", body=f"{GOOD} number {i} of my questions").status_code == 200
    res = env.new_post("ann", body=GOOD + " number 6 of my questions")
    assert (res.status_code, codes(res)) == (429, "slow_down")
    assert env.new_post("ben", body=GOOD + " ben first").status_code == 200   # another person is not affected


def test_deleting_does_not_dodge_the_limit_and_old_posts_age_out(env):
    ids = [env.new_post("ann", body=f"{GOOD} variant {i} today").json()["post"]["id"] for i in range(5)]
    for i in ids:
        assert env.client.delete(f"/community/posts/{i}", headers=env.h("ann")).status_code == 200
    assert codes(env.new_post("ann", body=GOOD + " fresh start")) == "slow_down"
    old = (ca._now() - timedelta(hours=1, minutes=1)).isoformat()
    for r in env.db.tables["community_posts"]:
        r["created_at"] = old
    assert env.new_post("ann", body=GOOD + " fresh start").status_code == 200


def test_twenty_comments_an_hour_and_the_21st_is_slowed(env):
    pid = env.new_post("ben").json()["post"]["id"]
    for i in range(20):
        assert env.post("ann", f"/community/posts/{pid}/comments", {"body": f"Reply number {i} with a kind thought."}).status_code == 200, i
    res = env.post("ann", f"/community/posts/{pid}/comments", {"body": "Reply number 21 with a kind thought."})
    assert (res.status_code, codes(res)) == (429, "slow_down")


def test_duplicates_are_refused_even_with_case_and_punctuation_changes(env):
    assert env.new_post("ann").status_code == 200
    for variant in (GOOD, GOOD.upper(), GOOD.replace(" ", "  ") + "!!!", "  " + GOOD + "\n"):
        res = env.new_post("ann", body=variant)
        assert (res.status_code, codes(res)) == (409, "duplicate")
    assert env.new_post("ben").status_code == 200                                 # someone else may say the same thing


def test_duplicate_comments_across_threads_are_refused(env):
    p1 = env.new_post("ben", body=GOOD + " one").json()["post"]["id"]
    p2 = env.new_post("ben", body=GOOD + " two").json()["post"]["id"]
    assert env.post("ann", f"/community/posts/{p1}/comments", {"body": "Great thread, thank you all."}).status_code == 200
    assert codes(env.post("ann", f"/community/posts/{p2}/comments", {"body": "great thread thank you all"})) == "duplicate"


# ---- moderation wiring ----------------------------------------------------------------------------------------------------

def test_removed_text_is_never_stored_and_the_author_gets_a_plain_reason(env):
    res = env.new_post("ann", body="Take 500 mg of paracetamol every four hours, it works for everyone.")
    p = res.json()["post"]
    assert p["status"] == "removed" and "taken down" in p["note"]
    assert env.db.rows("community_posts")[0]["body"] == "[removed by moderation]"
    assert "paracetamol" not in json.dumps(env.db.tables)
    assert env.get("ben", "/community/posts").json()["posts"] == []
    assert env.db.rows("community_moderation_log")[0]["actor"] == "bot"


def test_held_text_is_visible_only_to_its_author(env):
    p = env.new_post("ann", body="You definitely have PCOS, that is exactly what this is.").json()["post"]
    assert p["status"] == "held"
    assert env.get("ben", "/community/posts").json()["posts"] == []
    mine = env.get("ann", "/community/posts?mine=true").json()["posts"]
    assert mine[0]["status"] == "held" and "waiting" in mine[0]["note"]
    assert env.post("ben", f"/community/posts/{p['id']}/comments", {"body": "I hope this helps you a bit."}).status_code == 404
    assert env.get("ben", f"/community/posts/{p['id']}/comments").status_code == 404


@pytest.mark.parametrize("body", ["Call me on 9876543210 please", "mail me at someone@example.com", "follow @myhandle_99 for tips",
                                  "see https://example.com/page for more", "nine eight seven six five four three two one zero call"])
def test_contact_details_never_reach_the_feed(env, body):
    env.new_post("ann", body="I feel low on energy lately. " + body)
    for p in env.get("ben", "/community/posts").json()["posts"]:
        assert not any(x in p["body"] for x in ("9876543210", "example.com", "@myhandle", "nine eight seven"))


@pytest.mark.parametrize("body", ["<script>alert(1)</script> hello there friends", "<img src=x onerror=alert(1)> my sleep is bad", "<b>bold</b> sleep trouble all week"])
def test_html_and_script_markup_is_stripped_before_storage(env, body):
    env.new_post("ann", body=body)
    stored = env.db.rows("community_posts")[0]["body"]
    assert "<" not in stored and ">" not in stored


@pytest.mark.parametrize("body", ["I want to end my life", "i dont want to live anymore", "mujhe marna hai, sab khatam kar dunga"])
def test_crisis_text_is_held_with_a_calm_message_and_lines_never_shown_on_the_feed(env, body):
    res = env.new_post("ann", body=body)
    assert res.status_code == 200
    data = res.json()
    assert data["support"]["kind"] == "crisis" and "14416" in data["support"]["lines"] and "112" in data["support"]["lines"]
    assert data["post"]["status"] == "held"
    low = (data["support"]["message"] + data["post"]["note"]).lower()
    assert not any(w in low for w in ("violat", "banned", "removed", "inappropriate", "report", "not allowed"))
    assert env.get("ben", "/community/posts").json()["posts"] == []
    q = env.client.get("/admin/community/queue", headers=env.h("admin")).json()["items"]
    assert q and q[0]["crisis"] is True


def test_crisis_comment_is_held_too_and_the_queue_puts_crisis_first(env):
    pid = env.new_post("ben").json()["post"]["id"]
    env.new_post("cat", body="You definitely have thyroid disease, trust me on this one.")
    res = env.post("ann", f"/community/posts/{pid}/comments", {"body": "I want to kill myself"})
    assert res.json()["support"]["kind"] == "crisis"
    assert env.get("cat", f"/community/posts/{pid}/comments").json()["comments"] == []
    items = env.client.get("/admin/community/queue", headers=env.h("admin")).json()["items"]
    assert [i["crisis"] for i in items] == [True, False]


def test_a_threat_inside_a_crisis_post_is_still_removed(env):
    res = env.new_post("ann", body="I want to die and I will kill you all")
    assert res.json()["post"]["status"] == "removed"


@pytest.mark.parametrize("body", ["I am so lonely, any advice?", "Anyone else feel anxious before exams? What helps you?", "Mere bal jhad rahe hain, kya karun, koi tip?"])
def test_near_misses_pass(env, body):
    assert env.new_post("ann", body=body).json()["post"]["status"] == "visible"


@pytest.mark.parametrize("body", ["Stop taking your thyroid tablets, they are poison", "T@ke 5OO mg of dolo 650 twice daily and you will be cured",
                                  "dm me for medicine, cheap price rs 500", "k.i.l.l yourself you idiot", "fr​ee c​ash dm me"])
def test_evasions_do_not_get_through_to_the_feed(env, body):
    env.new_post("ann", body=body)
    assert env.get("ben", "/community/posts").json()["posts"] == []


# ---- reading: pagination, topics, ownership ----------------------------------------------------------------------------------

def test_cursor_pagination_walks_every_post_once_and_ends(env):
    for i in range(7):
        env.new_post("ann" if i < 5 else "ben", body=f"{GOOD} post {i} here")
    for r in env.db.tables["community_posts"]:   # distinct clock ticks so the cursor is exact
        pass
    seen, cursor = [], None
    for _ in range(10):
        res = env.get("cat", "/community/posts?limit=3" + (f"&cursor={cursor}" if cursor else "")).json()
        seen += [p["id"] for p in res["posts"]]
        cursor = res["next_cursor"]
        if not cursor:
            break
    assert len(seen) == len(set(seen)) == 7 and cursor is None


@pytest.mark.parametrize("q", ["limit=0", "limit=31", "limit=-1", "limit=abc", "limit=99999999", "cursor=!!!", "cursor=" + "A" * 500, "topic=nonsense", "topic=" + "x" * 50])
def test_pagination_and_filter_abuse_is_refused(env, q):
    assert env.get("ann", "/community/posts?" + q).status_code == 422


def test_limit_30_is_accepted_and_topic_filter_works(env):
    env.new_post("ann", topic="sleep")
    env.new_post("ann", body=GOOD + " food", topic="food")
    assert env.get("ben", "/community/posts?limit=30").status_code == 200
    assert [p["topic"] for p in env.get("ben", "/community/posts?topic=food").json()["posts"]] == ["food"]
    assert codes(env.new_post("ann", body=GOOD + " zzz", topic="weather")) == "bad_topic"


def test_the_disclaimer_is_in_the_feed(env):
    assert env.get("ben", "/community/posts").json()["disclaimer"] == "Shared by people, not medical advice."


# ---- delete, edit ----------------------------------------------------------------------------------------------------------

def test_only_the_author_can_delete_and_everyone_else_gets_a_plain_404(env):
    pid = env.new_post("ann").json()["post"]["id"]
    cid = env.post("ben", f"/community/posts/{pid}/comments", {"body": "I hope you sleep better soon."}).json()["comment"]["id"]
    assert env.client.delete(f"/community/posts/{pid}", headers=env.h("ben")).status_code == 404
    assert env.client.delete(f"/community/comments/{cid}", headers=env.h("ann")).status_code == 404
    assert env.client.delete(f"/community/posts/{uuid.uuid4()}", headers=env.h("ann")).status_code == 404
    assert env.client.delete(f"/community/posts/{pid}", headers={}).status_code == 401
    assert env.client.delete("/community/posts/not-a-uuid", headers=env.h("ann")).status_code == 422
    assert env.client.delete(f"/community/things/{pid}", headers=env.h("ann")).status_code == 404
    assert env.get("cat", "/community/posts").json()["posts"][0]["id"] == pid
    assert env.client.delete(f"/community/comments/{cid}", headers=env.h("ben")).status_code == 200
    assert env.get("cat", f"/community/posts/{pid}/comments").json()["comments"] == []
    assert env.client.delete(f"/community/posts/{pid}", headers=env.h("ann")).status_code == 200
    assert env.get("cat", "/community/posts").json()["posts"] == []
    assert env.db.rows("community_posts")[0]["body"] == "[deleted]"
    assert env.client.delete(f"/community/posts/{pid}", headers=env.h("ann")).status_code == 200     # again is harmless


def test_there_is_no_edit_route_so_nobody_can_change_a_post(env):
    pid = env.new_post("ann").json()["post"]["id"]
    for method in ("patch", "put"):
        assert getattr(env.client, method)(f"/community/posts/{pid}", headers=env.h("ben"), json={"body": "hacked"}).status_code in (404, 405)
    assert env.db.rows("community_posts")[0]["body"] == GOOD


def test_deleted_post_cannot_be_commented_reacted_reported_or_read(env):
    pid = env.new_post("ann").json()["post"]["id"]
    env.client.delete(f"/community/posts/{pid}", headers=env.h("ann"))
    assert env.post("ben", f"/community/posts/{pid}/comments", {"body": "Are you still here friend?"}).status_code == 404
    assert env.post("ben", "/community/reactions", {"target": f"post:{pid}", "kind": "helpful"}).status_code == 404
    assert env.post("ben", "/community/reports", {"target": f"post:{pid}", "reason": "spam"}).status_code == 404
    assert env.get("ben", f"/community/posts/{pid}/comments").status_code == 404
    assert env.get("ann", "/community/posts?mine=true").json()["posts"] == []


# ---- reactions, reports, blocks ----------------------------------------------------------------------------------------------

def test_reactions_toggle_and_count_once_per_person(env):
    pid = env.new_post("ann").json()["post"]["id"]
    assert env.post("ben", "/community/reactions", {"target": f"post:{pid}", "kind": "me_too"}).json() == {"on": True}
    p = env.get("ben", "/community/posts").json()["posts"][0]
    assert p["reactions"] == {"me_too": 1, "helpful": 0} and p["my_reactions"] == ["me_too"]
    assert env.post("ben", "/community/reactions", {"target": f"post:{pid}", "kind": "me_too"}).json() == {"on": False}
    assert env.get("cat", "/community/posts").json()["posts"][0]["reactions"]["me_too"] == 0
    for bad in ({"target": f"post:{pid}", "kind": "angry"}, {"target": "post:nope", "kind": "helpful"}, {"target": f"user:{pid}", "kind": "helpful"}):
        assert env.post("ben", "/community/reactions", bad).status_code == 422


def test_three_distinct_reporters_hide_a_post_two_do_not(env):
    env.member("eve")
    pid = env.new_post("ann").json()["post"]["id"]
    for who in ("ben", "cat"):
        assert env.post(who, "/community/reports", {"target": f"post:{pid}", "reason": "spam"}).status_code == 200
    assert env.post("cat", "/community/reports", {"target": f"post:{pid}", "reason": "spam"}).status_code == 200   # the same person again counts once
    assert len(env.get("dan", "/community/posts").json()["posts"]) == 1
    assert env.post("dan", "/community/reports", {"target": f"post:{pid}", "reason": "unkind"}).status_code == 200
    assert env.get("eve", "/community/posts").json()["posts"] == []
    mine = env.get("ann", "/community/posts?mine=true").json()["posts"][0]
    assert mine["status"] == "held" and "Several people" in mine["note"]
    q = env.client.get("/admin/community/queue", headers=env.h("admin")).json()["items"][0]
    assert q["reports"] == 3 and q["reason_codes" if False else "reason_code"] == "reports"


def test_report_rules_own_post_bad_reason_bad_target_and_mass_reporting(env):
    pid = env.new_post("ann").json()["post"]["id"]
    assert codes(env.post("ann", "/community/reports", {"target": f"post:{pid}", "reason": "spam"})) == "own_post"
    assert env.post("ben", "/community/reports", {"target": f"post:{pid}", "reason": "because"}).status_code == 422
    assert env.post("ben", "/community/reports", {"target": "post:1; drop table", "reason": "spam"}).status_code == 422
    assert env.post("ben", "/community/reports", {"target": f"post:{uuid.uuid4()}", "reason": "spam"}).status_code == 404
    for i in range(10):
        p = env.new_post("cat", body=f"{GOOD} other {i}") if i < 5 else env.new_post("dan", body=f"{GOOD} other {i}")
        assert env.post("ben", "/community/reports", {"target": f"post:{p.json()['post']['id']}", "reason": "spam"}).status_code == 200
    extra = env.post("ben", "/community/reports", {"target": f"post:{pid}", "reason": "spam"})
    assert (extra.status_code, codes(extra)) == (429, "slow_down")


def test_blocking_hides_that_person_without_revealing_them_and_unblock_restores(env):
    pid = env.new_post("ann").json()["post"]["id"]
    env.new_post("cat", body=GOOD + " cat")
    assert env.post("ben", "/community/blocks", {"target": f"post:{pid}"}).status_code == 200
    seen = env.get("ben", "/community/posts").json()["posts"]
    assert len(seen) == 1 and seen[0]["id"] != pid
    assert uuids_in(env.db.rows("community_blocks")) == [IDS["ben"]]                 # the block row holds ben and a keyed hash, never ann
    assert IDS["ann"] not in json.dumps(env.db.rows("community_blocks"))
    assert env.post("ben", f"/community/posts/{pid}/comments", {"body": "Trying to reply anyway here."}).status_code == 404
    assert len(env.get("cat", "/community/posts").json()["posts"]) == 2                      # others still see it
    assert codes(env.post("ann", "/community/blocks", {"target": f"post:{pid}"})) == "own_post"
    env.client.delete("/community/blocks", headers=env.h("ben"))
    assert len(env.get("ben", "/community/posts").json()["posts"]) == 2


# ---- admin -----------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("method,path", [("get", "/admin/community/status"), ("get", "/admin/community/queue"), ("get", "/admin/community/log"),
                                         ("post", "/admin/community/decide"), ("post", "/admin/community/resolve")])
def test_admin_routes_answer_everyone_else_with_the_plain_404(env, method, path):
    pid = env.new_post("ann").json()["post"]["id"]
    body = {"target": f"post:{pid}", "action": "remove"}
    unknown = env.client.get("/admin/does-not-exist")
    for headers in ({}, env.h("ben"), {"Authorization": "Bearer junk"}):
        res = getattr(env.client, method)(path, headers=headers, **({"json": body} if method == "post" else {}))
        assert res.status_code == 404 and res.content == unknown.content
    assert env.db.rows("community_posts")[0]["status"] == "visible"
    assert env.db.rows("community_moderation_log") == []


def test_the_router_has_its_own_lock_without_the_middleware(env):
    from admin_api import _admin
    with pytest.raises(HTTPException) as e:
        _admin(types.SimpleNamespace(state=types.SimpleNamespace()))
    assert e.value.status_code == 404


def test_admin_resolution_returns_the_person_and_is_logged_first(env):
    pid = env.new_post("ann").json()["post"]["id"]
    r = env.client.post("/admin/community/resolve", headers=env.h("admin"), json={"target": f"post:{pid}"})
    assert r.status_code == 200 and r.json()["user_id"] == IDS["ann"]
    log = env.db.rows("community_moderation_log", action="alias_resolved")
    assert len(log) == 1 and log[0]["actor"] == "admin" and log[0]["target"] == f"post:{pid}"
    assert env.client.post("/admin/community/resolve", headers=env.h("admin"), json={"target": f"post:{uuid.uuid4()}"}).status_code == 404
    assert env.client.post("/admin/community/resolve", headers=env.h("admin"), json={"target": "x"}).status_code == 422
    assert len(env.db.rows("community_moderation_log", action="alias_resolved")) == 1


def test_admin_approve_remove_and_ban(env):
    held = env.new_post("ann", body="You definitely have PCOS, that is exactly what this is.").json()["post"]["id"]
    other = env.new_post("ann", body=GOOD + " other").json()["post"]["id"]
    d = lambda target, action: env.client.post("/admin/community/decide", headers=env.h("admin"), json={"target": target, "action": action})
    assert d(f"post:{held}", "approve").status_code == 200
    assert len(env.get("ben", "/community/posts").json()["posts"]) == 2
    assert d(f"post:{other}", "remove").status_code == 200
    assert env.db.rows("community_posts", id=other)[0]["body"] == "[removed by moderation]"
    assert [p["id"] for p in env.get("ben", "/community/posts").json()["posts"]] == [held]
    assert d(f"post:{held}", "ban").status_code == 200
    assert env.get("ben", "/community/posts").json()["posts"] == []
    assert codes(env.new_post("ann", body=GOOD + " third")) == "not_allowed"
    assert d(f"post:{held}", "explode").status_code == 422
    assert [x["action"] for x in env.db.rows("community_moderation_log", actor="admin")] == ["approve", "remove", "ban"]


def test_admin_status_counts_and_log_hold_no_text(env):
    env.new_post("ann", body="Take 500 mg of paracetamol every four hours, it works for everyone.")
    s = env.client.get("/admin/community/status", headers=env.h("admin")).json()
    assert s["enabled"] is True and s["message"] is None and s["counts"]["posts_removed"] == 1
    assert "paracetamol" not in env.client.get("/admin/community/log", headers=env.h("admin")).text


# ---- delete my data -----------------------------------------------------------------------------------------------------------

def test_delete_my_data_wipes_posts_comments_reactions_reports_and_blocks_but_keeps_others(env):
    mine = env.new_post("ann").json()["post"]["id"]
    theirs = env.new_post("ben", body=GOOD + " ben").json()["post"]["id"]
    env.post("ben", f"/community/posts/{mine}/comments", {"body": "Replying under ann's post here."})
    env.post("ann", f"/community/posts/{theirs}/comments", {"body": "Replying under ben's post here."})
    env.post("ann", "/community/reactions", {"target": f"post:{theirs}", "kind": "helpful"})
    env.post("ann", "/community/reports", {"target": f"post:{theirs}", "reason": "spam"})
    env.post("ann", "/community/blocks", {"target": f"post:{theirs}"})
    out = env.client.delete("/community/me", headers=env.h("ann")).json()["deleted"]
    assert out["community_posts"] == 1 and out["community_comments"] == 1
    for table in ("community_posts", "community_comments", "community_reactions", "community_reports", "community_blocks"):
        assert IDS["ann"] not in json.dumps(env.db.tables.get(table, [])), table
    assert env.db.rows("community_comments", post_id=mine) == []                    # others' comments under her deleted post go too
    assert [p["id"] for p in env.get("cat", "/community/posts").json()["posts"]] == [theirs]
    assert env.db.rows("community_moderation_log") == [] or all(IDS["ann"] not in json.dumps(r) for r in env.db.rows("community_moderation_log"))


def test_the_main_delete_my_data_path_also_wipes_community(env):
    env.new_post("ann")
    doc_store.delete_everything(env.db, IDS["ann"])
    assert env.db.rows("community_posts") == []


def test_delete_my_data_never_breaks_when_the_tables_do_not_exist(env):
    for t in ("community_posts", "community_comments", "community_reactions", "community_reports", "community_blocks"):
        env.db.failures[t] = RuntimeError("missing")
    assert ca.forget(env.db, IDS["ann"]) == {t: 0 for t in ("community_reactions", "community_reports", "community_blocks", "community_comments", "community_posts")}
