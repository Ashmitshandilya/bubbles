from context_engine import format_user_context


def test_context_formatter_is_compact_and_structured():
    context = {
        "profile": {"full_name": "Test", "date_of_birth": None, "sex": None, "timezone": "Asia/Kolkata"},
        "preferences": {"id": "x", "user_id": "u", "language": "English"},
        "memory_context": "L2: Headaches have recurred.",
        "recent_events": [
            {"type": "sleep", "data": {"duration": "5h"}, "confidence": 0.9, "created_at": "2026-09-18T20:00:00Z"}
        ],
    }
    output = format_user_context(context)
    assert "PROFILE:" in output
    assert "PREFERENCES:" in output
    assert "L2: Headaches have recurred." in output
    assert "RECENT HEALTH EVENTS:" in output
    assert "5h" in output
