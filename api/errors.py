"""
Error Handling Utilities

This module provides global exception handlers and error response utilities
for consistent error handling across the FastAPI application.
"""

from datetime import datetime, timezone
from typing import Dict, Any
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from config.logging_config import get_logger

logger = get_logger(__name__)


# Error code constants
class ErrorCode:
    """Standard error codes for API responses."""
    INVALID_REQUEST = "INVALID_REQUEST"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    AI_SERVICE_ERROR = "AI_SERVICE_ERROR"
    QUERY_TIMEOUT = "QUERY_TIMEOUT"
    DATABASE_ERROR = "DATABASE_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


def create_error_response(
    code: str,
    message: str,
    status_code: int,
    details: Dict[str, Any] = None
) -> JSONResponse:
    """
    Create a standardized error response.
    
    Args:
        code: Machine-readable error code
        message: Human-readable error message
        status_code: HTTP status code
        details: Optional additional error details
        
    Returns:
        JSONResponse with standardized error format
    """
    error_body = {
        "error": {
            "code": code,
            "message": message,
            "status": status_code,
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        }
    }
    
    if details:
        error_body["error"]["details"] = details
    
    return JSONResponse(
        status_code=status_code,
        content=error_body
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    Handle Pydantic validation errors.
    
    Args:
        request: FastAPI request object
        exc: Validation error exception
        
    Returns:
        JSONResponse with validation error details
    """
    logger.warning(f"Validation error on {request.method} {request.url.path}: {exc.errors()}")
    
    # Extract validation error details
    errors = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"])
        errors.append({
            "field": field,
            "message": error["msg"],
            "type": error["type"]
        })
    
    return create_error_response(
        code=ErrorCode.INVALID_REQUEST,
        message="Request validation failed",
        status_code=status.HTTP_400_BAD_REQUEST,
        details={"validation_errors": errors}
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle all unhandled exceptions.
    
    Args:
        request: FastAPI request object
        exc: Exception instance
        
    Returns:
        JSONResponse with generic error message
    """
    # Log full exception details server-side
    logger.exception(
        f"Unhandled exception on {request.method} {request.url.path}: {type(exc).__name__}: {str(exc)}"
    )
    
    # Map known exception types to appropriate responses
    exception_type = type(exc).__name__
    
    # Import exception classes dynamically to avoid circular imports
    if exception_type == "SQLGenerationError":
        return create_error_response(
            code=ErrorCode.AI_SERVICE_ERROR,
            message="Failed to generate SQL query from your question",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    elif exception_type == "QueryTimeoutError":
        return create_error_response(
            code=ErrorCode.QUERY_TIMEOUT,
            message="Query execution timed out",
            status_code=status.HTTP_504_GATEWAY_TIMEOUT
        )
    
    elif exception_type == "DatabaseConnectionError":
        return create_error_response(
            code=ErrorCode.DATABASE_ERROR,
            message="Database connection failed",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    
    elif exception_type == "SQLSyntaxError":
        return create_error_response(
            code=ErrorCode.INVALID_REQUEST,
            message="Generated SQL query has syntax errors",
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    elif exception_type == "PermissionDeniedError":
        return create_error_response(
            code=ErrorCode.FORBIDDEN,
            message="Permission denied for this operation",
            status_code=status.HTTP_403_FORBIDDEN
        )
    
    elif exception_type == "AnswerFormattingError":
        return create_error_response(
            code=ErrorCode.AI_SERVICE_ERROR,
            message="Failed to format answer from query results",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    # Default catch-all for unknown exceptions
    return create_error_response(
        code=ErrorCode.INTERNAL_ERROR,
        message="An internal error occurred",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
    )
