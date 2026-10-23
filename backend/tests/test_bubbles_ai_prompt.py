"""What the model is actually told: one voice section, no attribution priming, the evidence wrapper that keeps source names out of replies."""
from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
os.environ.setdefault("SUPABASE_URL", "http://localhost")
os.environ.setdefault("SUPABASE_SECRET_KEY", "x")

import bubbles_ai  # noqa: E402
import rag  # noqa: E402
from bubbles_ai import BubblesAIResponse  # noqa: E402
from response_formatter import response_style_instruction  # noqa: E402
from safety_engine import assess_safety, safety_instruction  # noqa: E402

EVIDENCE_ROW = {"chunk_id": "c1", "title": "Sleep and mood", "source_name": "Sleep guide", "publisher": "NHS", "source_url": "https://example.org/sleep",
                "content": "Sleep affects mood.", "evidence_level": "A", "fused_score": 0.9}


def _capture(monkeypatch, **kw):
    seen = {}

    def fake(message, system_instruction):
        seen["system"] = system_instruction
        return BubblesAIResponse(response="ok", sentiment="neutral", health_events=[])
    monkeypatch.setattr(bubbles_ai, "_call_gemini", fake)
    monkeypatch.setattr(bubbles_ai.admin_settings, "is_paused", lambda _name: False)
    bubbles_ai.ask_bubbles("I slept badly", **kw)
    return seen["system"]


def _prompt(monkeypatch):
    style = response_style_instruction()
    return _capture(monkeypatch, memory_context="Name: Riya", evidence_context=rag.build_evidence_context([EVIDENCE_ROW]),
                    safety_context=safety_instruction(assess_safety("I slept badly")) + "\n\n" + style + "\n\n- Length: keep replies short"), style


def test_the_prompt_has_exactly_one_voice_and_format_section(monkeypatch):
    prompt, style = _prompt(monkeypatch)
    assert prompt.count("BUBBLES RESPONSE STYLE (") == 1 and prompt.count(style) == 1
    assert prompt.count("VOICE:") == 1 and prompt.count("FORMAT:") == 1
    assert "Voice, format and length rules are in BUBBLES RESPONSE STYLE below; follow them." in prompt


def test_the_old_conflicting_voice_lines_are_gone(monkeypatch):
    prompt, _ = _prompt(monkeypatch)
    for gone in ("feminine", "evidence-aware", "NHS guidance says", "What I’m noticing", "Be warm, feminine", "Do not invent citations, sources"):
        assert gone not in prompt, gone
    assert "never name the publisher or source in the reply" in prompt


def test_the_style_block_forbids_authority_names_and_scary_leads_and_keeps_the_warning(monkeypatch):
    style = response_style_instruction()
    assert len(style.split()) < 540   # 450 before the renovation plan 5.3 voice rules (person model, threads, no stereotypes, no verdicts, never invent)
    for must in ("NO AUTHORITY NAMES", "SOFT, NOT SCARY", "WARN WITHOUT ALARM", "never diagnose", "never give a dose", "112", "At most one question"):
        assert must in style, must


def test_the_evidence_wrapper_tells_the_model_not_to_quote_sources(monkeypatch):
    sentence = "Source, Publisher and URL lines are for the app's reading links. Never quote or name them in the reply."
    context = rag.build_evidence_context([EVIDENCE_ROW])
    assert sentence in context
    assert "Publisher: NHS" in context and "https://example.org/sleep" in context      # the provenance lines themselves stay
    assert "Source, Publisher and URL lines are for the app's reading links" in _prompt(monkeypatch)[0]


def test_an_empty_evidence_block_adds_no_wrapper(monkeypatch):
    assert rag.build_evidence_context([]) == "" or "BEGIN UNTRUSTED" not in rag.build_evidence_context([])
