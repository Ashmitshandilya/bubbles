from fastapi import HTTPException
from typing import Dict, Any
def unauthorized_response(message: str) -> HTTPException:
    """Return a 401 Unauthorized JSONResponse helper.

    Args:
        message: Error message describing the authentication issue

    Returns:
        HTTPException with status_code=401 and error response
    """
    return HTTPException(
        status_code=401,
        detail={"error": "unauthorized", "message": message}
    )
def forbidden_response(message: str) -> HTTPException:
    """Return a 403 Forbidden JSONResponse helper.

    Args:
        message: Error message describing the authorization issue

    Returns:
        HTTPException with status_code=403 and error response
    """
    return HTTPException(
        status_code=403,
        detail={"error": "forbidden", "message": message}
    )
def auth_error_response(error_detail: str) -> HTTPException:
    """Unified auth error response helper.

    Args:
        error_detail: Detailed error information

    Returns:
        HTTPException with status_code=401 and unified error format
    """
    return HTTPException(
        status_code=401,
        detail={"error": "authentication_error", "detail": error_detail}
    )
# For backward compatibility and convenience
def invalid_auth_header_response() -> HTTPException:
    """Return a 401 response for invalid Authorization header format."""
    return unauthorized_response("Invalid Authorization header format. Expected: Bearer <token>")
def missing_auth_header_response() -> HTTPException:
    """Return a 401 response for missing Authorization header."""
    return unauthorized_response("Missing Authorization header")
def invalid_token_response() -> HTTPException:
    """Return a 401 response for invalid or expired access token."""
    return unauthorized_response("Invalid or expired access token")
def invalid_scope_response() -> HTTPException:
    """Return a 403 response for insufficient permissions."""
    return forbidden_response("Insufficient permissions for this operation")