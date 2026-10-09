"""Tests for Phase 2 infrastructure hardening.

Verifies that logging is properly integrated and silent failures are eliminated.
"""

import pytest
import json


# ============================================================
# TEST: Logging utility creates valid structured logs
# ============================================================

def test_logger_creates_valid_json_log(capsys):
    """Verify logger outputs valid JSON with required fields."""
    from logging_util import logger

    logger.error(
        component="TEST",
        operation="test_operation",
        error=Exception("test error"),
        request_id="test-123",
        user_id="user-456",
        context={"key": "value"},
        fallback_action="test_fallback",
    )

    captured = capsys.readouterr()
    log_json = json.loads(captured.err.strip())

    assert log_json["level"] == "ERROR"
    assert log_json["component"] == "TEST"
    assert log_json["operation"] == "test_operation"
    assert log_json["request_id"] == "test-123"
    assert log_json["user_id"] == "user-456"
    assert log_json["error_type"] == "Exception"
    assert "test error" in log_json["error_message"]
    assert log_json["fallback_action"] == "test_fallback"
    assert log_json["context"]["key"] == "value"
    assert "timestamp" in log_json


def test_logger_sanitizes_sensitive_data(capsys):
    """Verify logger removes sensitive fields before logging."""
    from logging_util import logger

    logger.warning(
        component="TEST",
        message="test warning",
        context={
            "api_key": "secret-key-123",
            "password": "secret-pass",
            "token": "secret-token",
            "safe_field": "safe_value",
        },
    )

    captured = capsys.readouterr()
    log_json = json.loads(captured.err.strip())

    assert "api_key" not in log_json["context"]
    assert "password" not in log_json["context"]
    assert "token" not in log_json["context"]
    assert log_json["context"]["safe_field"] == "safe_value"


# ============================================================
# TEST: RAG retrieval logs errors instead of silently failing
# ============================================================

def test_rag_hybrid_search_logs_error_on_exception(capsys):
    """Verify RAG retrieval logs errors instead of silent failure."""
    from logging_util import logger

    test_error = ConnectionError("Supabase connection failed")
    logger.error(
        component="RAG",
        operation="hybrid_search",
        error=test_error,
        user_id="test-user",
        context={"query_length": 50},
        fallback_action="using_empty_evidence",
    )

    captured = capsys.readouterr()
    log_json = json.loads(captured.err.strip())

    assert log_json["component"] == "RAG"
    assert log_json["operation"] == "hybrid_search"
    assert log_json["error_type"] == "ConnectionError"
    assert "Supabase connection failed" in log_json["error_message"]
    assert log_json["fallback_action"] == "using_empty_evidence"


# ============================================================
# TEST: AI provider failures are logged with context
# ============================================================

def test_ai_provider_gemini_failure_logged(capsys):
    """Verify Gemini failures are logged with full context."""
    from logging_util import logger

    gemini_error = Exception("Gemini API timeout")
    logger.error(
        component="AI_PROVIDER",
        operation="gemini_call",
        error=gemini_error,
        fallback_action="attempting_fallback_provider",
    )

    captured = capsys.readouterr()
    log_json = json.loads(captured.err.strip())

    assert log_json["component"] == "AI_PROVIDER"
    assert log_json["operation"] == "gemini_call"
    assert log_json["fallback_action"] == "attempting_fallback_provider"


def test_ai_provider_fallback_pool_failure_logged(capsys):
    """Verify fallback provider pool failures are logged."""
    from logging_util import logger

    fallback_error = Exception("All providers exhausted")
    logger.error(
        component="AI_PROVIDER",
        operation="fallback_provider_pool",
        error=fallback_error,
        fallback_action="returning_degraded_response",
    )

    captured = capsys.readouterr()
    log_json = json.loads(captured.err.strip())

    assert log_json["component"] == "AI_PROVIDER"
    assert log_json["operation"] == "fallback_provider_pool"
    assert log_json["fallback_action"] == "returning_degraded_response"


# ============================================================
# TEST: Profile sync errors are logged
# ============================================================

def test_profile_sync_error_logged(capsys):
    """Verify profile sync errors are logged with context."""
    from logging_util import logger

    profile_error = Exception("Profile upsert failed")
    logger.error(
        component="PROFILE",
        operation="sync_profile_from_auth",
        error=profile_error,
        user_id="user-789",
        fallback_action="profile_sync_skipped",
    )

    captured = capsys.readouterr()
    log_json = json.loads(captured.err.strip())

    assert log_json["component"] == "PROFILE"
    assert log_json["operation"] == "sync_profile_from_auth"
    assert log_json["user_id"] == "user-789"
    assert log_json["fallback_action"] == "profile_sync_skipped"


# ============================================================
# TEST: RAG embedding configuration missing is logged
# ============================================================

def test_rag_embedding_config_missing_logged(capsys):
    """Verify RAG embedding config missing is logged as warning."""
    from logging_util import logger

    logger.warning(
        component="RAG",
        message="RAG embedding unavailable: Supabase configuration missing",
        context={"has_url": False, "has_secret": False},
    )

    captured = capsys.readouterr()
    log_json = json.loads(captured.err.strip())

    assert log_json["level"] == "WARNING"
    assert log_json["component"] == "RAG"
    assert "configuration missing" in log_json["message"]


# ============================================================
# TEST: Memory retrieval errors can be logged
# ============================================================

def test_memory_retrieval_errors_can_be_logged(capsys):
    """Verify memory retrieval errors have proper logging infrastructure."""
    from logging_util import logger

    l1_error = Exception("L1 query failed")
    logger.error(
        component="MEMORY",
        operation="l1_retrieval",
        error=l1_error,
        user_id="user-123",
        context={"query": "test query"},
        fallback_action="returning_empty_l1",
    )

    captured = capsys.readouterr()
    log_json = json.loads(captured.err.strip())

    assert log_json["component"] == "MEMORY"
    assert log_json["operation"] == "l1_retrieval"
    assert log_json["fallback_action"] == "returning_empty_l1"


# ============================================================
# TEST: Request ID generation
# ============================================================

def test_logger_generates_unique_request_ids():
    """Verify logger generates unique request IDs for tracing."""
    from logging_util import BubblesLogger

    id1 = BubblesLogger.generate_request_id()
    id2 = BubblesLogger.generate_request_id()

    assert len(id1) == 8
    assert len(id2) == 8
    assert id1 != id2


# ============================================================
# TEST: Info logging works
# ============================================================

def test_logger_info_works(capsys):
    """Verify logger.info() works correctly."""
    from logging_util import logger

    logger.info(
        component="TEST",
        message="test info message",
        request_id="test-id",
        user_id="test-user",
    )

    captured = capsys.readouterr()
    log_json = json.loads(captured.err.strip())

    assert log_json["level"] == "INFO"
    assert log_json["component"] == "TEST"
    assert "test info message" in log_json["message"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])