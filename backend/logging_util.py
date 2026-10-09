"""Bubbles structured logging utility.

Provides centralized, consistent error logging with request context,
enabling production debugging and observability without leaking sensitive data.
"""

import json
import re
import sys
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


_QUOTED = re.compile(r"""(['"])(?:(?!\1).){3,}\1""")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_TOKEN = re.compile(r"\b(?:eyJ[\w-]{10,}|[A-Za-z0-9_\-]{32,})\b")
_LONG_NUM = re.compile(r"\d{6,}")
_SECRET_WORDS = ("password", "token", "api_key", "apikey", "secret", "authorization", "credential", "sensitive_data")
_CONTENT_KEYS = {"message", "content", "text", "query", "user_message", "body", "prompt", "response", "note", "notes", "summary"}


class BubblesLogger:
    """Centralized logging for Bubbles backend operations."""

    @staticmethod
    def generate_request_id() -> str:
        """Generate a unique request ID for tracing."""
        return str(uuid4())[:8]

    @staticmethod
    def _scrub_text(text: Any, limit: int = 200) -> str:
        """Error text can echo user input (parse errors, DB messages): drop quoted spans, emails, tokens, long numbers."""
        s = str(text)
        s = _QUOTED.sub("[quoted]", s)
        s = _EMAIL.sub("[email]", s)
        s = _TOKEN.sub("[token]", s)
        s = _LONG_NUM.sub("[num]", s)
        return s[:limit]

    @staticmethod
    def _sanitize_data(data: Any, _depth: int = 0) -> Any:
        """Recursively remove secrets, replace free-text content fields by their length, scrub other strings."""
        if _depth > 4:
            return "[depth]"
        if isinstance(data, dict):
            out = {}
            for k, v in data.items():
                key = str(k).lower()
                if any(w in key for w in _SECRET_WORDS):
                    continue
                if key in _CONTENT_KEYS and isinstance(v, str):
                    out[k] = f"[redacted len={len(v)}]"
                else:
                    out[k] = BubblesLogger._sanitize_data(v, _depth + 1)
            return out
        if isinstance(data, (list, tuple, set)):
            return [BubblesLogger._sanitize_data(v, _depth + 1) for v in list(data)[:20]]
        if isinstance(data, str):
            return BubblesLogger._scrub_text(data, 120)
        return data

    @staticmethod
    def error(
        component: str,
        operation: str,
        error: Exception,
        request_id: str = None,
        user_id: str = None,
        context: dict = None,
        fallback_action: str = None,
    ) -> dict[str, Any]:
        """Log an error with full context.

        Args:
            component: Which module/system (e.g., 'RAG', 'AI_PROVIDER', 'MEMORY')
            operation: What was being attempted (e.g., 'embedding_request', 'memory_retrieval')
            error: The exception that occurred
            request_id: Optional unique request ID for tracing
            user_id: Optional user context (must not be PII)
            context: Optional operation context (sanitized before logging)
            fallback_action: What happened as fallback (e.g., 'using_empty_results')

        Returns:
            dict with logged information for caller's use
        """
        request_id = request_id or BubblesLogger.generate_request_id()
        timestamp = datetime.now(timezone.utc).isoformat()

        log_entry = {
            "level": "ERROR",
            "timestamp": timestamp,
            "request_id": request_id,
            "component": component,
            "operation": operation,
            "error_type": type(error).__name__,
            "error_message": BubblesLogger._scrub_text(error),  # truncated + PHI-scrubbed
            "user_id": user_id,
            "fallback_action": fallback_action,
        }

        if context:
            log_entry["context"] = BubblesLogger._sanitize_data(context)

        # Write to stderr so it's separate from stdout/API responses
        print(json.dumps(log_entry), file=sys.stderr)
        sys.stderr.flush()

        return {
            "request_id": request_id,
            "error_type": type(error).__name__,
            "fallback_action": fallback_action,
        }

    @staticmethod
    def warning(
        component: str,
        message: str = "",
        request_id: str = None,
        user_id: str = None,
        context: dict = None,
        operation: str = None,
        error: Exception = None,
        fallback_action: str = None,
        **_ignored: Any,
    ) -> dict[str, Any]:
        """Log a warning with context.

        Accepts the same keyword arguments as :meth:`error` so a logging call made inside an
        ``except`` block can never itself raise and turn a handled failure into a 500.
        """
        request_id = request_id or BubblesLogger.generate_request_id()
        timestamp = datetime.now(timezone.utc).isoformat()

        log_entry = {
            "level": "WARNING",
            "timestamp": timestamp,
            "request_id": request_id,
            "component": component,
            "operation": operation,
            "message": (message or operation or "")[:200],
            "user_id": user_id,
        }
        if error is not None:
            log_entry["error_type"] = type(error).__name__
        if fallback_action:
            log_entry["fallback_action"] = fallback_action

        if context:
            log_entry["context"] = BubblesLogger._sanitize_data(context)

        print(json.dumps(log_entry), file=sys.stderr)
        sys.stderr.flush()

        return {"request_id": request_id}

    @staticmethod
    def info(
        component: str,
        message: str = "",
        request_id: str = None,
        user_id: str = None,
        context: dict = None,
        operation: str = None,
        error: Exception = None,
        fallback_action: str = None,
        **_ignored: Any,
    ) -> None:
        """Log informational message."""
        message = message or operation or ""
        request_id = request_id or BubblesLogger.generate_request_id()
        timestamp = datetime.now(timezone.utc).isoformat()

        log_entry = {
            "level": "INFO",
            "timestamp": timestamp,
            "request_id": request_id,
            "component": component,
            "message": message[:200],
            "user_id": user_id,
        }
        if error is not None:
            log_entry["error_type"] = type(error).__name__

        if context:
            log_entry["context"] = BubblesLogger._sanitize_data(context)

        print(json.dumps(log_entry), file=sys.stderr)
        sys.stderr.flush()


# Convenience singleton
logger = BubblesLogger()
