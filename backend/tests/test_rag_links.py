import pytest

import rag
import rag_links as rl


@pytest.mark.parametrize("query,expected", [
    ("does lack of sleep affect my mood", ["mood-sleep"]),
    ("does exercise help with low mood", ["activity-mood"]),
    ("why do I get headaches when I do not drink enough water", ["hydration-symptom"]),
    ("can stress delay my period", ["cycle-stress"]),
    ("is low energy linked to thyroid or anaemia", ["fatigue-labs"]),
    ("sleep", []), ("what is a normal heart rate", []), ("", []),
])
def test_detect_needs_both_areas_in_the_question(query, expected):
    assert rl.detect(query)[:len(expected)] == expected and (expected or rl.detect(query) == [])


def test_detect_returns_at_most_two_and_only_registered_links():
    out = rl.detect("tired after poor sleep, stress, heavy period and low mood and weight gain", limit=2)
    assert len(out) <= 2 and all(p in rl.LINK_DOCS for p in out)


def test_pair_id_maps_logged_series_to_a_link_id():
    assert rl.pair_id("sleep_hours", "mood") == "mood-sleep" and rl.pair_id("mood", "sleep_quality") == "mood-sleep"
    assert rl.pair_id("luteal", "mood") == "cycle-mood" and rl.pair_id("hydration_ml", "symptom_severity") == "hydration-symptom"
    assert rl.pair_id("hydration_ml", "mood") is None and rl.pair_id("sleep_hours", "sleep_quality") is None and rl.pair_id("x", "mood") is None


def test_every_link_has_sources_and_a_query():
    assert set(rl.LINK_QUERY) == set(rl.LINK_DOCS) and all(rl.LINK_DOCS.values())
    assert all(pid == "-".join(sorted(pid.split("-"))) for pid in rl.LINK_DOCS)   # ids are sorted so pair_id() and detect() agree


# --- hybrid_search with links -----------------------------------------------------------------------------------------------

class _Q:
    def __init__(self, data): self.data = data
    def select(self, *_): return self
    def in_(self, *_): return self
    def execute(self): return self


class _DB:
    def __init__(self, by_topic): self.by_topic, self.calls = by_topic, []
    def rpc(self, name, params):
        self.calls.append(params)
        return _Q([dict(r) for r in self.by_topic.get(params["topic_filter"], [])])
    def table(self, _): return _Q([])


def _run(monkeypatch, by_topic, **kw):
    db = _DB(by_topic)
    monkeypatch.setattr(rag, "embed_text", lambda _q, **_kw: None)
    monkeypatch.setattr(rag, "_db", lambda: db)
    return rag.hybrid_search(**kw), db


GENERAL = [dict(chunk_id="g1", fused_score=0.0164), dict(chunk_id="g2", fused_score=0.0160)]
LINKED = [dict(chunk_id="l1", fused_score=0.0100), dict(chunk_id="g2", fused_score=0.0090), dict(chunk_id="l3", fused_score=0.0050)]


def test_a_relationship_question_puts_the_tagged_sources_first_without_duplicates(monkeypatch):
    out, db = _run(monkeypatch, {None: GENERAL, "link:mood-sleep": LINKED}, query="does lack of sleep affect my mood", limit=5)
    assert [r["chunk_id"] for r in out] == ["l1", "g2", "g1"]            # at most two tagged rows, then the general ones, g2 once
    assert out[0].get("linked") and not out[2].get("linked")
    assert sorted(str(c["topic_filter"]) for c in db.calls) == ["None", "link:mood-sleep"]   # both searches run side by side: no fixed order


def test_plain_questions_and_explicit_topics_and_the_switch_skip_the_link_search(monkeypatch):
    _, db = _run(monkeypatch, {None: GENERAL}, query="what is ferritin", limit=3)
    assert len(db.calls) == 1
    _, db = _run(monkeypatch, {None: GENERAL}, query="does lack of sleep affect my mood", topic="link:mood-sleep", limit=3)
    assert [c["topic_filter"] for c in db.calls] == ["link:mood-sleep"]
    monkeypatch.setenv("RAG_LINKS", "0")
    _, db = _run(monkeypatch, {None: GENERAL}, query="does lack of sleep affect my mood", limit=3)
    assert len(db.calls) == 1


def test_a_failing_link_search_still_returns_the_general_results(monkeypatch):
    class Boom(_DB):
        def rpc(self, name, params):
            if params["topic_filter"]:
                raise RuntimeError("down")
            return super().rpc(name, params)
    db = Boom({None: GENERAL})
    monkeypatch.setattr(rag, "embed_text", lambda _q, **_kw: None)
    monkeypatch.setattr(rag, "_db", lambda: db)
    out = rag.hybrid_search(query="does lack of sleep affect my mood", limit=3)
    assert [r["chunk_id"] for r in out] == ["g1", "g2"]


# --- evidence for a link + tagging -------------------------------------------------------------------------------------------

def test_evidence_for_pair_is_compact_cached_and_never_raises():
    rl._cache.clear()
    calls = []

    def search(**kw):
        calls.append(kw)
        return [dict(title="T", source_name="MedlinePlus", source_url="https://medlineplus.gov/x.html", content="a  b\n" + "c" * 500)]
    out = rl.evidence_for_pair("mood-sleep", search=search)
    assert out[0]["source_url"].startswith("https://") and len(out[0]["snippet"]) <= 240 and calls[0]["topic"] == "link:mood-sleep"
    assert rl.evidence_for_pair("mood-sleep", search=search) == out and len(calls) == 1                    # cached
    rl._cache.clear()
    assert rl.evidence_for_pair("mood-sleep", search=lambda **kw: (_ for _ in ()).throw(RuntimeError("x"))) == []


class _TagTable:
    def __init__(self, db): self.db, self.prefix, self.pending = db, None, None
    def select(self, *_): return self
    def like(self, _col, pattern): self.prefix = pattern.rstrip("%"); return self
    def update(self, payload): self.pending = payload; return self
    def eq(self, _col, val): self.db.updates.append((val, self.pending)); return self
    def execute(self):
        self.data = [d for d in self.db.docs if d["title"].startswith(self.prefix)] if self.prefix is not None else []
        return self


class _TagDB:
    def __init__(self, docs): self.docs, self.updates = docs, []
    def table(self, _): return _TagTable(self)


def test_tagging_is_additive_idempotent_and_dry_by_default():
    docs = [dict(id="a", title="Poor sleep and depression/anxiety are bidirectionally linked; x", topic_tags=["batch:v1"]),
            dict(id="b", title="Low mood, sadness and depression: causes, treatment and self-care", topic_tags=["link:mood-sleep"])]
    db = _TagDB(docs)
    dry = rl.tag_documents(db, apply=False)
    assert dry["tagged"] >= 1 and db.updates == [] and not dry["applied"]
    res = rl.tag_documents(db, apply=True)
    mine = [u for u in db.updates if u[0] == "a" and "link:mood-sleep" in u[1]["topic_tags"]]
    assert mine and "batch:v1" in mine[0][1]["topic_tags"]                       # existing tags are kept
    assert not any(u[0] == "b" and u[1]["topic_tags"].count("link:mood-sleep") > 1 for u in db.updates)   # never duplicated
    assert any(pid == "mood-sleep" for pid, _t in res["changed"]) and res["missing"]                       # other prefixes aren't in this fake store
