"""
Request Logging Middleware

This module logs all API requests and responses for audit and debugging.
Logs are written to logs/chat_audit.log.
"""

import time
import uuid
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from config.logging_config import get_logger

logger = get_logger("api")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log all API requests and responses.
    
    Logs include:
    - Request ID (UUID for tracing)
    - HTTP method and path
    - User ID (from JWT if authenticated)
    - Status code
    - Response time in milliseconds
    - Question text for /v1/ask endpoint (for audit)
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and log details.
        
        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain
            
        Returns:
            HTTP response
        """
        # Generate request ID for tracing
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # Extract user ID from request state (set by auth middleware)
        user_id = "anonymous"
        if hasattr(request.state, "user"):
            user = request.state.user
            user_id = user.get("id") or user.get("user_id") or "unknown"
        
        # Start timer
        start_time = time.time()
        
        # Log request body for /ask endpoint (question only, not full payload)
        question_preview = ""
        if request.url.path == "/v1/ask" and request.method == "POST":
            try:
                # Read body without consuming it
                body = await request.body()
                # Re-create request with body for downstream handlers
                async def receive():
                    return {"type": "http.request", "body": body}
                request._receive = receive
                
                # Try to extract question from body
                import json
                try:
                    body_json = json.loads(body.decode())
                    question = body_json.get("question", "")
                    if question:
                        # Truncate long questions for logging
                        question_preview = f" - question=\"{question[:100]}{'...' if len(question) > 100 else ''}\""
                except (json.JSONDecodeError, UnicodeDecodeError):
                    pass
            except Exception:
                # If we can't read the body, just skip the preview
                pass
        
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration_ms = round((time.time() - start_time) * 1000, 2)
        
        # Log request details
        log_message = (
            f"{request.method} {request.url.path} - "
            f"user_id={user_id} - "
            f"status={response.status_code} - "
            f"duration={duration_ms}ms - "
            f"request_id={request_id}"
            f"{question_preview}"
        )
        
        # Log at appropriate level based on status code
        if response.status_code >= 500:
            logger.error(log_message)
        elif response.status_code >= 400:
            logger.warning(log_message)
        else:
            logger.info(log_message)
        
        # Add request ID to response headers for client-side tracing
        response.headers["X-Request-ID"] = request_id
        
        return response
