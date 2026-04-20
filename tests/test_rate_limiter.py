"""
Tests for Rate Limiting Middleware

Tests the in-memory rate limiter with sliding window algorithm.
"""

import pytest
import time
from middleware.rate_limiter import RateLimiter


class TestRateLimiter:
    """Tests for RateLimiter class."""
    
    def test_first_request_from_user_passes(self):
        """Happy path: First request from user passes."""
        limiter = RateLimiter(max_requests=20, window_seconds=60)
        is_allowed, retry_after = limiter.check_rate_limit("user_123")
        
        assert is_allowed is True
        assert retry_after is None
    
    def test_20th_request_within_60_seconds_passes(self):
        """Happy path: 20th request within 60 seconds passes."""
        limiter = RateLimiter(max_requests=20, window_seconds=60)
        
        # Make 20 requests
        for i in range(20):
            is_allowed, retry_after = limiter.check_rate_limit("user_123")
            assert is_allowed is True, f"Request {i+1} should be allowed"
            assert retry_after is None
    
    def test_21st_request_within_60_seconds_returns_429(self):
        """Edge case: 21st request within 60 seconds returns 429."""
        limiter = RateLimiter(max_requests=20, window_seconds=60)
        
        # Make 20 requests (all should pass)
        for _ in range(20):
            is_allowed, _ = limiter.check_rate_limit("user_123")
            assert is_allowed is True
        
        # 21st request should be rate limited
        is_allowed, retry_after = limiter.check_rate_limit("user_123")
        assert is_allowed is False
        assert retry_after is not None
        assert retry_after > 0
    
    def test_request_after_window_resets(self):
        """Edge case: Request after window expires resets the limit."""
        limiter = RateLimiter(max_requests=2, window_seconds=1)  # Small window for testing
        
        # Make 2 requests
        limiter.check_rate_limit("user_123")
        limiter.check_rate_limit("user_123")
        
        # 3rd request should be rate limited
        is_allowed, _ = limiter.check_rate_limit("user_123")
        assert is_allowed is False
        
        # Wait for window to expire
        time.sleep(1.1)
        
        # Request should now be allowed
        is_allowed, retry_after = limiter.check_rate_limit("user_123")
        assert is_allowed is True
        assert retry_after is None
    
    def test_multiple_users_tracked_independently(self):
        """Edge case: Multiple users tracked independently."""
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        
        # User 1 makes 2 requests
        limiter.check_rate_limit("user_1")
        limiter.check_rate_limit("user_1")
        
        # User 1's 3rd request should be rate limited
        is_allowed, _ = limiter.check_rate_limit("user_1")
        assert is_allowed is False
        
        # User 2's first request should still be allowed
        is_allowed, retry_after = limiter.check_rate_limit("user_2")
        assert is_allowed is True
        assert retry_after is None
    
    def test_rate_limit_headers(self):
        """Happy path: Rate limit headers are correct."""
        limiter = RateLimiter(max_requests=20, window_seconds=60)
        
        # Make 5 requests
        for _ in range(5):
            limiter.check_rate_limit("user_123")
        
        # Get headers
        headers = limiter.get_rate_limit_headers("user_123")
        
        assert headers["X-RateLimit-Limit"] == "20"
        assert headers["X-RateLimit-Remaining"] == "15"  # 20 - 5 = 15
        assert "X-RateLimit-Reset" in headers
    
    def test_retry_after_header_when_rate_limited(self):
        """Error path: Retry-After header is set when rate limited."""
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        
        # Make 2 requests
        limiter.check_rate_limit("user_123")
        limiter.check_rate_limit("user_123")
        
        # 3rd request should be rate limited with retry_after
        is_allowed, retry_after = limiter.check_rate_limit("user_123")
        assert is_allowed is False
        assert retry_after is not None
        assert 0 < retry_after <= 60
    
    def test_stats_tracking(self):
        """Happy path: Stats track active users correctly."""
        limiter = RateLimiter(max_requests=20, window_seconds=60)
        
        # Make requests from 3 users
        limiter.check_rate_limit("user_1")
        limiter.check_rate_limit("user_2")
        limiter.check_rate_limit("user_3")
        
        stats = limiter.get_stats()
        assert stats["active_users"] == 3
        assert stats["total_recent_requests"] == 3
    
    def test_cleanup_removes_old_entries(self):
        """Edge case: Cleanup removes old entries to prevent memory leaks."""
        limiter = RateLimiter(max_requests=20, window_seconds=1)
        
        # Make requests
        limiter.check_rate_limit("user_123")
        
        # Wait for window to expire
        time.sleep(1.1)
        
        # Force cleanup by making another request
        limiter.last_cleanup = 0  # Force cleanup on next check
        limiter.check_rate_limit("user_456")
        
        # Old user should be cleaned up
        stats = limiter.get_stats()
        assert stats["active_users"] == 1  # Only user_456 should be active


class TestRateLimitIntegration:
    """Integration tests for rate limiting with FastAPI."""
    
    def test_rate_limit_applies_to_ask_endpoint(self):
        """Integration: Rate limit applies to /v1/ask endpoint."""
        from fastapi.testclient import TestClient
        from main import app
        from tests.test_api_endpoints import create_test_token
        from unittest.mock import patch
        
        client = TestClient(app)
        token = create_test_token()
        
        # Mock the pipeline to avoid actual execution
        with patch('api.routes.pipeline_ask') as mock_pipeline:
            mock_pipeline.return_value = {
                "answer": "Test",
                "sql": "SELECT 1;",
                "rows_count": 1,
                "status_code": 200
            }
            
            # Make requests up to the limit
            for i in range(20):
                response = client.post(
                    "/v1/ask",
                    json={"question": "Test question"},
                    headers={"Authorization": f"Bearer {token}"}
                )
                assert response.status_code == 200, f"Request {i+1} should succeed"
                
                # Check rate limit headers
                assert "X-RateLimit-Limit" in response.headers
                assert "X-RateLimit-Remaining" in response.headers
                assert "X-RateLimit-Reset" in response.headers
            
            # 21st request should be rate limited
            response = client.post(
                "/v1/ask",
                json={"question": "Test question"},
                headers={"Authorization": f"Bearer {token}"}
            )
            assert response.status_code == 429
            assert "Retry-After" in response.headers
            
            data = response.json()
            assert data["error"]["code"] == "RATE_LIMIT_EXCEEDED"
            assert "retry_after" in data["error"]
    
    def test_rate_limit_does_not_apply_to_health_endpoint(self):
        """Integration: Rate limit does not apply to /v1/health endpoint."""
        from fastapi.testclient import TestClient
        from main import app
        
        client = TestClient(app)
        
        # Make many requests to health endpoint (should not be rate limited)
        for _ in range(30):
            response = client.get("/v1/health")
            # Health endpoint may return 503 if dependencies are down,
            # but should never return 429 (rate limited)
            assert response.status_code != 429
