"""
Tests for Metrics Endpoint

This module tests the /v1/metrics endpoint and metrics tracking functionality.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from main import app
from middleware.metrics_tracker import get_metrics_tracker


client = TestClient(app)


class TestMetricsEndpoint:
    """Test metrics endpoint functionality."""
    
    def setup_method(self):
        """Reset metrics before each test."""
        get_metrics_tracker().reset()
    
    def test_metrics_endpoint_returns_200(self):
        """Test that metrics endpoint returns 200."""
        response = client.get("/v1/metrics")
        
        assert response.status_code == 200
        data = response.json()
        assert "requests" in data
        assert "rate_limiting" in data
        assert "performance" in data
        assert "uptime_seconds" in data
        assert "timestamp" in data
    
    def test_metrics_no_authentication_required(self):
        """Test that metrics endpoint does not require authentication."""
        # Call without Authorization header
        response = client.get("/v1/metrics")
        
        assert response.status_code == 200
    
    def test_metrics_initial_state(self):
        """Test that metrics start at zero."""
        response = client.get("/v1/metrics")
        
        assert response.status_code == 200
        data = response.json()
        
        # Initial state should have zero counts
        assert data["requests"]["total"] >= 0  # May include the metrics request itself
        assert data["rate_limiting"]["active_users"] == 0
        assert data["rate_limiting"]["blocked_requests"] == 0
    
    def test_metrics_tracks_requests(self):
        """Test that metrics tracker records requests."""
        tracker = get_metrics_tracker()
        tracker.reset()
        
        # Record some requests
        tracker.record_request(user_id="user1", status_code=200, response_time_ms=100)
        tracker.record_request(user_id="user2", status_code=200, response_time_ms=150)
        tracker.record_request(user_id="user1", status_code=400, response_time_ms=50)
        
        response = client.get("/v1/metrics")
        data = response.json()
        
        # Should have recorded the requests (plus the metrics request itself)
        assert data["requests"]["total"] >= 3
        assert data["requests"]["success"] >= 2
        assert data["requests"]["errors"] >= 1
        assert data["rate_limiting"]["active_users"] == 2  # user1 and user2
    
    def test_metrics_tracks_rate_limiting(self):
        """Test that metrics tracker records rate-limited requests."""
        tracker = get_metrics_tracker()
        tracker.reset()
        
        # Record some rate-limited requests
        tracker.record_request(user_id="user1", status_code=429, response_time_ms=10)
        tracker.record_request(user_id="user1", status_code=429, response_time_ms=10)
        
        response = client.get("/v1/metrics")
        data = response.json()
        
        assert data["rate_limiting"]["blocked_requests"] >= 2
    
    def test_metrics_tracks_performance(self):
        """Test that metrics tracker calculates performance stats."""
        tracker = get_metrics_tracker()
        tracker.reset()
        
        # Record requests with known response times
        tracker.record_request(user_id="user1", status_code=200, response_time_ms=100)
        tracker.record_request(user_id="user1", status_code=200, response_time_ms=200)
        tracker.record_request(user_id="user1", status_code=200, response_time_ms=300)
        
        response = client.get("/v1/metrics")
        data = response.json()
        
        # Should have calculated performance metrics
        assert data["performance"]["avg_response_time_ms"] > 0
        assert data["performance"]["p95_response_time_ms"] > 0
        assert data["performance"]["p99_response_time_ms"] > 0
    
    def test_metrics_includes_uptime(self):
        """Test that metrics include service uptime."""
        import time
        time.sleep(0.01)  # Wait a tiny bit to ensure uptime > 0
        
        response = client.get("/v1/metrics")
        data = response.json()
        
        # Uptime should be positive or zero (if very fast)
        assert data["uptime_seconds"] >= 0
    
    def test_metrics_response_time_under_100ms(self):
        """Test that metrics endpoint responds quickly (under 100ms)."""
        import time
        
        start_time = time.time()
        response = client.get("/v1/metrics")
        end_time = time.time()
        
        assert response.status_code == 200
        assert (end_time - start_time) < 0.1  # Under 100ms
    
    def test_metrics_tracker_thread_safety(self):
        """Test that metrics tracker handles concurrent requests safely."""
        import threading
        
        tracker = get_metrics_tracker()
        tracker.reset()
        
        def record_requests():
            for i in range(100):
                tracker.record_request(user_id=f"user{i % 10}", status_code=200, response_time_ms=100)
        
        # Create multiple threads
        threads = [threading.Thread(target=record_requests) for _ in range(5)]
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify metrics were recorded correctly
        metrics = tracker.get_metrics()
        assert metrics["requests"]["total"] == 500  # 5 threads * 100 requests
        assert metrics["rate_limiting"]["active_users"] == 10  # user0-user9
