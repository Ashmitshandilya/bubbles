"""A symptom that continues ("still", "keeps") is the same current symptom: it must be caught like the plain wording."""
import pytest

from health_semantics import analyze
from safety_engine import assess_safety


@pytest.mark.parametrize("text", [
    "my chest still hurts", "chest is still hurting", "my chest keeps hurting", "my chest is still tight", "chest still hurting",
    "My chest STILL hurts!",
])
def test_continuing_chest_pain_is_an_emergency_like_the_plain_wording(text):
    facts = analyze(text)
    assert [(f.concept, f.assertion) for f in facts] == [("chest_pain", "present")], text
    assert assess_safety(text, facts).state == assess_safety("my chest hurts", analyze("my chest hurts")).state == "EMERGENCY"


@pytest.mark.parametrize("text,concept", [
    ("my head still hurts", "headache"), ("my head keeps pounding", "headache"), ("my stomach is still hurting", "abdominal_pain"),
    ("my back still aches", "back_pain"), ("my throat is still sore", "sore_throat"),
])
def test_other_body_parts_too(text, concept):
    facts = analyze(text)
    assert any(f.concept == concept and f.assertion == "present" for f in facts), (text, [(f.concept, f.assertion) for f in facts])


@pytest.mark.parametrize("text", ["my chest doesn't hurt anymore", "my chest doesnt hurt any more", "no chest pain, it is still early"])
def test_denials_and_unrelated_still_are_unchanged(text):
    assert assess_safety(text, analyze(text)).state != "EMERGENCY"
