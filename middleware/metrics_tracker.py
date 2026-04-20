"""
Metrics Tracking Middleware

This module tracks basic operational metrics for the API.
Metrics are stored in-memory and reset on service restart.
"""

import time
from typing import Dict, List
from datetime import datetime, timezone
from collections import defaultdict
from threading import Lock


class MetricsTracker:
    """
    In-memory metrics tracker for API requests.
    
    Tracks:
    - Request counts (total, success, errors)
    - Rate limiting stats (active users, blocked requests)
    - Performance metrics (response times)
    """
    
    def __init__(self):
        """Initialize metrics tracker with thread-safe storage."""
        self._lock = Lock()
        self._request_count = 0
        self._success_count = 0
        self._error_count = 0
        self._rate_limited_count = 0
        self._active_users = set()
        self._response_times: List[float] = []
        self._start_time = datetime.now(timezone.utc)
    
    def record_request(self, user_id: str = None, status_code: int = 200, response_time_ms: float = 0):
        """
        Record a request with its outcome.
        
        Args:
            user_id: User ID from JWT (if authenticated)
            status_code: HTTP status code
            response_time_ms: Response time in milliseconds
        """
        with self._lock:
            self._request_count += 1
            
            if 200 <= status_code < 300:
                self._success_count += 1
            elif status_code >= 400:
                self._error_count += 1
            
            if status_code == 429:
                self._rate_limited_count += 1
            
            if user_id:
                self._active_users.add(user_id)
            
            if response_time_ms > 0:
                self._response_times.append(response_time_ms)
                # Keep only last 1000 response times to prevent memory growth
                if len(self._response_times) > 1000:
                    self._response_times = self._response_times[-1000:]
    
    def get_metrics(self) -> Dict:
        """
        Get current metrics snapshot.
        
        Returns:
            Dictionary with all tracked metrics
        """
        with self._lock:
            # Calculate performance percentiles
            response_times_sorted = sorted(self._response_times) if self._response_times else []
            
            avg_response_time = (
                sum(response_times_sorted) / len(response_times_sorted)
                if response_times_sorted else 0
            )
            
            p95_response_time = (
                response_times_sorted[int(len(response_times_sorted) * 0.95)]
                if response_times_sorted else 0
            )
            
            p99_response_time = (
                response_times_sorted[int(len(response_times_sorted) * 0.99)]
                if response_times_sorted else 0
            )
            
            uptime_seconds = (datetime.now(timezone.utc) - self._start_time).total_seconds()
            
            return {
                "requests": {
                    "total": self._request_count,
                    "success": self._success_count,
                    "errors": self._error_count
                },
                "rate_limiting": {
                    "active_users": len(self._active_users),
                    "blocked_requests": self._rate_limited_count
                },
                "performance": {
                    "avg_response_time_ms": round(avg_response_time, 2),
                    "p95_response_time_ms": round(p95_response_time, 2),
                    "p99_response_time_ms": round(p99_response_time, 2)
                },
                "uptime_seconds": round(uptime_seconds, 2)
            }
    
    def reset(self):
        """Reset all metrics (useful for testing)."""
        with self._lock:
            self._request_count = 0
            self._success_count = 0
            self._error_count = 0
            self._rate_limited_count = 0
            self._active_users.clear()
            self._response_times.clear()
            self._start_time = datetime.now(timezone.utc)


# Global metrics tracker instance
_metrics_tracker = MetricsTracker()


def get_metrics_tracker() -> MetricsTracker:
    """Get the global metrics tracker instance."""
    return _metrics_tracker
