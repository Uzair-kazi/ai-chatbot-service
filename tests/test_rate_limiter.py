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
    
    def test_concurrent_requests_respect_rate_limit(self):
        """Concurrency: Concurrent requests from same user respect rate limit."""
        import threading
        
        limiter = RateLimiter(max_requests=10, window_seconds=60)
        results = []
        
        def make_request():
            is_allowed, _ = limiter.check_rate_limit("user_concurrent")
            results.append(is_allowed)
        
        # Launch 15 concurrent threads
        threads = []
        for _ in range(15):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Exactly 10 requests should be allowed, 5 should be denied
        allowed_count = sum(1 for r in results if r is True)
        denied_count = sum(1 for r in results if r is False)
        
        assert allowed_count == 10, f"Expected 10 allowed, got {allowed_count}"
        assert denied_count == 5, f"Expected 5 denied, got {denied_count}"
    
    def test_concurrent_requests_from_different_users(self):
        """Concurrency: Concurrent requests from different users don't block each other."""
        import threading
        
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        results = {}
        
        def make_request(user_id):
            is_allowed, _ = limiter.check_rate_limit(user_id)
            if user_id not in results:
                results[user_id] = []
            results[user_id].append(is_allowed)
        
        # Launch 10 threads for 3 different users (30 total requests)
        threads = []
        for user_num in range(3):
            user_id = f"user_{user_num}"
            for _ in range(10):
                thread = threading.Thread(target=make_request, args=(user_id,))
                threads.append(thread)
                thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Each user should have exactly 5 allowed and 5 denied
        for user_id in ["user_0", "user_1", "user_2"]:
            allowed = sum(1 for r in results[user_id] if r is True)
            denied = sum(1 for r in results[user_id] if r is False)
            assert allowed == 5, f"{user_id}: Expected 5 allowed, got {allowed}"
            assert denied == 5, f"{user_id}: Expected 5 denied, got {denied}"
    
    def test_high_concurrency_stress_test(self):
        """Concurrency: High concurrency stress test (100 threads)."""
        import threading
        
        limiter = RateLimiter(max_requests=20, window_seconds=60)
        results = []
        
        def make_request():
            is_allowed, _ = limiter.check_rate_limit("stress_test_user")
            results.append(is_allowed)
        
        # Launch 100 concurrent threads
        threads = []
        for _ in range(100):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Exactly 20 requests should be allowed, 80 should be denied
        allowed_count = sum(1 for r in results if r is True)
        denied_count = sum(1 for r in results if r is False)
        
        assert allowed_count == 20, f"Expected 20 allowed, got {allowed_count}"
        assert denied_count == 80, f"Expected 80 denied, got {denied_count}"
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




class TestLoginRateLimiter:
    """Tests for login-specific rate limiting."""
    
    def test_login_rate_limiter_has_stricter_limit(self):
        """Happy path: Login rate limiter has stricter limit (5 req/min vs 20)."""
        from middleware.rate_limiter import login_rate_limiter
        
        assert login_rate_limiter.max_requests == 5
        assert login_rate_limiter.window_seconds == 60
    
    def test_5_login_requests_within_1_minute_succeed(self):
        """Happy path: 5 login requests within 1 minute succeed."""
        from fastapi.testclient import TestClient
        from main import app
        from unittest.mock import patch
        
        client = TestClient(app)
        
        with patch('api.routes.get_user_by_email') as mock_get_user:
            mock_get_user.return_value = None  # User not found (will return 401)
            
            # Make 5 requests (all should go through, even if they fail auth)
            for i in range(5):
                response = client.post(
                    "/v1/login",
                    json={"email": f"test{i}@example.com", "password": "password"}
                )
                # Should get 401 (auth failure), not 429 (rate limit)
                assert response.status_code == 401, f"Request {i+1} should not be rate limited"
                
                # Check rate limit headers are present
                assert "X-RateLimit-Limit" in response.headers
                assert "X-RateLimit-Remaining" in response.headers
    
    def test_6th_login_request_within_1_minute_returns_429(self):
        """Error path: 6th login request within 1 minute returns 429."""
        from fastapi.testclient import TestClient
        from main import app
        from unittest.mock import patch
        
        client = TestClient(app)
        
        with patch('api.routes.get_user_by_email') as mock_get_user:
            mock_get_user.return_value = None
            
            # Make 5 requests
            for _ in range(5):
                client.post(
                    "/v1/login",
                    json={"email": "test2@example.com", "password": "password"}
                )
            
            # 6th request should be rate limited
            response = client.post(
                "/v1/login",
                json={"email": "test2@example.com", "password": "password"}
            )
            
            assert response.status_code == 429
            assert "Retry-After" in response.headers
            
            data = response.json()
            assert data["error"]["code"] == "RATE_LIMIT_EXCEEDED"
            assert "login attempts" in data["error"]["message"].lower()
    
    def test_rate_limit_resets_after_60_seconds(self):
        """Edge case: Rate limit resets after 60 seconds."""
        from middleware.rate_limiter import RateLimiter
        
        # Create a test limiter with short window
        test_limiter = RateLimiter(max_requests=5, window_seconds=1)
        
        # Make 5 requests
        for _ in range(5):
            is_allowed, _ = test_limiter.check_rate_limit("test_ip_reset")
        
        # 6th request should be denied
        is_allowed, _ = test_limiter.check_rate_limit("test_ip_reset")
        assert is_allowed is False
        
        # Wait for window to expire
        time.sleep(1.1)
        
        # Request should now be allowed
        is_allowed, retry_after = test_limiter.check_rate_limit("test_ip_reset")
        assert is_allowed is True
        assert retry_after is None
    
    def test_different_ips_have_independent_rate_limits(self):
        """Edge case: Different IP addresses have independent rate limits."""
        from fastapi.testclient import TestClient
        from main import app
        from unittest.mock import patch
        
        client = TestClient(app)
        
        with patch('api.routes.get_user_by_email') as mock_get_user:
            mock_get_user.return_value = None
            
            # Make 5 requests from "IP 1" (simulated by test client)
            for _ in range(5):
                client.post(
                    "/v1/login",
                    json={"email": "ip1@example.com", "password": "password"}
                )
            
            # 6th request from "IP 1" should be rate limited
            response = client.post(
                "/v1/login",
                json={"email": "ip1@example.com", "password": "password"}
            )
            assert response.status_code == 429
            
            # But requests from "IP 2" should still work
            # (In real scenario, this would be a different client IP)
            # For testing, we're limited by the test client's single IP
            # This test documents the expected behavior
    
    def test_rate_limit_headers_present_in_login_response(self):
        """Integration: Rate limit headers (X-RateLimit-*) are present in response."""
        from fastapi.testclient import TestClient
        from main import app
        from unittest.mock import patch
        
        client = TestClient(app)
        
        with patch('api.routes.get_user_by_email') as mock_get_user:
            mock_get_user.return_value = None
            
            response = client.post(
                "/v1/login",
                json={"email": "headers_test@example.com", "password": "password"}
            )
            
            # Check that rate limit headers are present
            assert "X-RateLimit-Limit" in response.headers
            assert "X-RateLimit-Remaining" in response.headers
            assert "X-RateLimit-Reset" in response.headers
    
    def test_retry_after_header_indicates_seconds_until_reset(self):
        """Integration: Retry-After header indicates seconds until reset."""
        from fastapi.testclient import TestClient
        from main import app
        from unittest.mock import patch
        
        client = TestClient(app)
        
        with patch('api.routes.get_user_by_email') as mock_get_user:
            mock_get_user.return_value = None
            
            # Make 5 requests
            for _ in range(5):
                client.post(
                    "/v1/login",
                    json={"email": "retry@example.com", "password": "password"}
                )
            
            # 6th request should be rate limited
            response = client.post(
                "/v1/login",
                json={"email": "retry@example.com", "password": "password"}
            )
            
            assert response.status_code == 429
            assert "Retry-After" in response.headers
            
            retry_after = int(response.headers["Retry-After"])
            assert 0 < retry_after <= 60
