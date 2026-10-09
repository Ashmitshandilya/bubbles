"""If safety analysis AND the keyword scan both fail, triage must not answer GREEN."""
import safety_engine as se


def test_double_failure_is_amber_not_green(monkeypatch):
    def boom(*_a, **_k): raise RuntimeError("down")
    monkeypatch.setattr(se, "analyze", boom)
    monkeypatch.setattr(se, "keyword_hits", boom)
    a = se.assess_safety("I feel strange today")
    assert a.level == "AMBER" and a.state == se.POTENTIAL


def test_analysis_failure_with_working_keyword_scan_still_catches_red_flags(monkeypatch):
    monkeypatch.setattr(se, "analyze", lambda _t: (_ for _ in ()).throw(RuntimeError("down")))
    assert se.assess_safety("crushing chest pain and cannot breathe").level in ("AMBER", "RED")
