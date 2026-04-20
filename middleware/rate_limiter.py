"""
Rate Limiting Middleware

In-memory rate limiting using sliding window algorithm.
Limits requests per user to prevent abuse.

Configuration:
- RATE_LIMIT_REQUESTS: Maximum requests per window (default: 20)
- RATE_LIMIT_WINDOW_SECONDS: Time window in seconds (default: 60)
"""

import os
import time
from typing import Dict, List, Optional
from collections import defaultdict
from fastapi import HTTPException, status, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from dotenv import load_dotenv

from config.logging_config import get_logger

# Load environment variables
load_dotenv()

# Configuration
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "20"))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
CLEANUP_INTERVAL_SECONDS = 300  # Clean up old entries every 5 minutes

# Initialize logger
logger = get_logger(__name__)


class RateLimiter:
    """
    In-memory rate limiter using sliding window algorithm.
    
    Tracks request timestamps per user ID and enforces rate limits.
    """
    
    def __init__(
        self,
        max_requests: int = RATE_LIMIT_REQUESTS,
        window_seconds: int = RATE_LIMIT_WINDOW_SECONDS
    ):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum requests allowed per window
            window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, List[float]] = defaultdict(list)
        self.last_cleanup = time.time()
        
        logger.info(
            f"Rate limiter initialized: {max_requests} requests per {window_seconds}s"
        )
    
    def _cleanup_old_entries(self):
        """Remove old timestamp entries to prevent memory leaks."""
        current_time = time.time()
        
        # Only cleanup every CLEANUP_INTERVAL_SECONDS
        if current_time - self.last_cleanup < CLEANUP_INTERVAL_SECONDS:
            return
        
        cutoff_time = current_time - self.window_seconds
        users_to_remove = []
        
        for user_id, timestamps in self.requests.items():
            # Filter out old timestamps
            self.requests[user_id] = [ts for ts in timestamps if ts > cutoff_time]
            
            # Mark empty entries for removal
            if not self.requests[user_id]:
                users_to_remove.append(user_id)
        
        # Remove empty entries
        for user_id in users_to_remove:
            del self.requests[user_id]
        
        self.last_cleanup = current_time
        
        if users_to_remove:
            logger.debug(f"Cleaned up {len(users_to_remove)} inactive users from rate limiter")
    
    def check_rate_limit(self, user_id: str) -> tuple[bool, Optional[int]]:
        """
        Check if user has exceeded rate limit.
        
        Args:
            user_id: User identifier
        
        Returns:
            Tuple of (is_allowed, retry_after_seconds)
            - is_allowed: True if request is allowed, False if rate limited
            - retry_after_seconds: Seconds to wait before retry (None if allowed)
        """
        current_time = time.time()
        cutoff_time = current_time - self.window_seconds
        
        # Get user's request timestamps
        timestamps = self.requests[user_id]
        
        # Filter to only timestamps within the window (sliding window)
        recent_timestamps = [ts for ts in timestamps if ts > cutoff_time]
        self.requests[user_id] = recent_timestamps
        
        # Check if limit exceeded
        if len(recent_timestamps) >= self.max_requests:
            # Calculate retry_after: time until oldest request expires
            oldest_timestamp = min(recent_timestamps)
            retry_after = int(oldest_timestamp + self.window_seconds - current_time) + 1
            
            logger.warning(
                f"Rate limit exceeded for user {user_id}: "
                f"{len(recent_timestamps)}/{self.max_requests} requests"
            )
            
            return False, retry_after
        
        # Allow request and record timestamp
        self.requests[user_id].append(current_time)
        
        # Periodic cleanup
        self._cleanup_old_entries()
        
        return True, None
    
    def get_rate_limit_headers(self, user_id: str) -> Dict[str, str]:
        """
        Get rate limit headers for response.
        
        Args:
            user_id: User identifier
        
        Returns:
            Dictionary of rate limit headers
        """
        current_time = time.time()
        cutoff_time = current_time - self.window_seconds
        
        # Get recent timestamps
        timestamps = self.requests.get(user_id, [])
        recent_timestamps = [ts for ts in timestamps if ts > cutoff_time]
        
        remaining = max(0, self.max_requests - len(recent_timestamps))
        
        # Calculate reset time (when oldest request expires)
        if recent_timestamps:
            oldest_timestamp = min(recent_timestamps)
            reset_time = int(oldest_timestamp + self.window_seconds)
        else:
            reset_time = int(current_time + self.window_seconds)
        
        return {
            "X-RateLimit-Limit": str(self.max_requests),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(reset_time)
        }
    
    def get_stats(self) -> Dict:
        """
        Get rate limiter statistics.
        
        Returns:
            Dictionary with active users and total tracked requests
        """
        current_time = time.time()
        cutoff_time = current_time - self.window_seconds
        
        active_users = 0
        total_recent_requests = 0
        
        for timestamps in self.requests.values():
            recent = [ts for ts in timestamps if ts > cutoff_time]
            if recent:
                active_users += 1
                total_recent_requests += len(recent)
        
        return {
            "active_users": active_users,
            "total_recent_requests": total_recent_requests
        }


# Global rate limiter instance
rate_limiter = RateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for rate limiting.
    
    Applies rate limiting to protected endpoints only.
    Public endpoints (health, metrics) are not rate limited.
    """
    
    async def dispatch(self, request: Request, call_next):
        """
        Process request and apply rate limiting.
        
        Args:
            request: FastAPI request
            call_next: Next middleware/endpoint
        
        Returns:
            Response with rate limit headers
        """
        # Skip rate limiting for public endpoints
        if request.url.path in ["/", "/v1/health", "/v1/metrics", "/docs", "/redoc", "/openapi.json"]:
            return await call_next(request)
        
        # Extract user ID from request
        # For authenticated endpoints, this will be set by auth middleware
        user_id = None
        
        # Try to extract user ID from Authorization header
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            # We'll use a hash of the token as user ID for rate limiting
            # The actual user ID will be extracted by auth middleware
            token = auth_header.split(" ")[1]
            user_id = f"token_{hash(token) % 1000000}"  # Simple hash for rate limiting
        
        if not user_id:
            # No auth header - use IP address as fallback
            user_id = f"ip_{request.client.host if request.client else 'unknown'}"
        
        # Check rate limit
        is_allowed, retry_after = rate_limiter.check_rate_limit(user_id)
        
        if not is_allowed:
            # Rate limit exceeded - return 429
            headers = rate_limiter.get_rate_limit_headers(user_id)
            headers["Retry-After"] = str(retry_after)
            
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": f"Too many requests. Please wait {retry_after} seconds before trying again.",
                        "status": 429,
                        "retry_after": retry_after,
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                    }
                },
                headers=headers
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers to response
        headers = rate_limiter.get_rate_limit_headers(user_id)
        for key, value in headers.items():
            response.headers[key] = value
        
        return response
