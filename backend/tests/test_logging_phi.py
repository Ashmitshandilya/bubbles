"""Logs must not carry health text: error messages and context are scrubbed."""
import json

from logging_util import BubblesLogger as L


def test_error_message_drops_quoted_user_text_numbers_and_emails():
    msg = L._scrub_text(ValueError("invalid input syntax: 'I have chest pain since monday' for a@b.com id 123456789"))
    assert "chest pain" not in msg and "a@b.com" not in msg and "123456789" not in msg


def test_context_redacts_content_keys_secrets_and_nested_strings():
    out = L._sanitize_data({"message": "my period is late", "route": "reply", "api_key": "x", "Authorization": "Bearer y",
                            "nested": {"query": "headache", "n": 3, "label": "ok"}, "tags": ["a", "b"]})
    assert out["message"] == "[redacted len=17]" and out["route"] == "reply" and "api_key" not in out and "Authorization" not in out
    assert out["nested"]["query"].startswith("[redacted") and out["nested"]["n"] == 3 and out["tags"] == ["a", "b"]


def test_logged_error_line_has_no_user_text(capsys):
    L.error("T", "op", RuntimeError('boom "I have a severe headache today"'), context={"user_message": "severe headache"})
    line = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    assert "headache" not in json.dumps(line)
