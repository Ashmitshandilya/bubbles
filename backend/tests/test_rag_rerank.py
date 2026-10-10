import rag


class _Q:
    def __init__(self, data): self.data = data
    def select(self, *_): return self
    def in_(self, *_): return self
    def execute(self): return self


class _DB:
    def __init__(self, rows): self.rows, self.calls = rows, []
    def rpc(self, name, params): self.calls.append(params); return _Q(self.rows)
    def table(self, _): return _Q([])


def _run(monkeypatch, rows, **kw):
    db = _DB(rows)
    monkeypatch.setattr(rag, "embed_text", lambda _q: None)
    monkeypatch.setattr(rag, "_db", lambda: db)
    return rag.hybrid_search(**kw), db


def test_evidence_level_only_reorders_near_ties_and_result_is_trimmed(monkeypatch):
    rows = [dict(chunk_id="forum", fused_score=0.0164, evidence_level="unknown"),
            dict(chunk_id="guide", fused_score=0.0163, evidence_level="guideline"),
            dict(chunk_id="weak", fused_score=0.0100, evidence_level="guideline")]
    out, db = _run(monkeypatch, rows, query="q", limit=2)
    assert [r["chunk_id"] for r in out] == ["guide", "forum"]  # near-tie flipped, clearly weaker never promoted
    assert db.calls[0]["match_count"] == 4


def test_overfetch_is_capped_at_30(monkeypatch):
    _, db = _run(monkeypatch, [], query="q", limit=30)
    assert db.calls[0]["match_count"] == 30


def test_expansion_reaches_the_search_and_can_be_switched_off(monkeypatch):
    _, db = _run(monkeypatch, [], query="mujhe bukhar hai", limit=3)
    assert "fever" in db.calls[0]["query_text"]
    monkeypatch.setenv("RAG_EXPAND", "0")
    _, db = _run(monkeypatch, [], query="mujhe bukhar hai", limit=3)
    assert db.calls[0]["query_text"] == "mujhe bukhar hai"
