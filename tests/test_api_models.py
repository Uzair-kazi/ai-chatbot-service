"""
Tests for API Pydantic Models

Tests validation rules and serialization for all request/response models.
"""

import pytest
from pydantic import ValidationError
from api.models import (
    QuestionRequest,
    AnswerResponse,
    ErrorResponse,
    ErrorDetail,
    HealthResponse,
    MetricsResponse,
    RequestStats,
    RateLimitStats,
    PerformanceStats
)


class TestQuestionRequest:
    """Tests for QuestionRequest model."""
    
    def test_valid_question(self):
        """Happy path: Valid question passes validation."""
        request = QuestionRequest(question="How many tanks are there?")
        assert request.question == "How many tanks are there?"
    
    def test_question_with_exactly_1_character(self):
        """Edge case: Question with exactly 1 character passes."""
        request = QuestionRequest(question="?")
        assert request.question == "?"
    
    def test_question_with_exactly_500_characters(self):
        """Edge case: Question with exactly 500 characters passes."""
        question = "a" * 500
        request = QuestionRequest(question=question)
        assert len(request.question) == 500
    
    def test_whitespace_only_question_rejected(self):
        """Edge case: Whitespace-only question is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            QuestionRequest(question="   ")
        assert "whitespace-only" in str(exc_info.value).lower()
    
    def test_question_with_501_characters_rejected(self):
        """Edge case: Question with 501 characters is rejected."""
        question = "a" * 501
        with pytest.raises(ValidationError) as exc_info:
            QuestionRequest(question=question)
        assert "500 characters" in str(exc_info.value).lower()
    
    def test_empty_question_rejected(self):
        """Error path: Empty question field returns validation error."""
        with pytest.raises(ValidationError) as exc_info:
            QuestionRequest(question="")
        # Empty string is caught by min_length validation
        assert "at least 1 character" in str(exc_info.value).lower()
    
    def test_non_string_question_rejected(self):
        """Error path: Non-string question field returns validation error."""
        with pytest.raises(ValidationError):
            QuestionRequest(question=123)
    
    def test_question_trimmed(self):
        """Edge case: Question is trimmed of leading/trailing whitespace."""
        request = QuestionRequest(question="  How many tanks?  ")
        assert request.question == "How many tanks?"


class TestAnswerResponse:
    """Tests for AnswerResponse model."""
    
    def test_valid_answer_response(self):
        """Happy path: Valid answer response serializes correctly."""
        response = AnswerResponse(
            answer="There are 47 tanks.",
            sql="SELECT COUNT(*) FROM tanks;",
            rows_count=1,
            execution_time_ms=1234
        )
        assert response.answer == "There are 47 tanks."
        assert response.sql == "SELECT COUNT(*) FROM tanks;"
        assert response.rows_count == 1
        assert response.execution_time_ms == 1234
        assert response.timestamp.endswith("Z")
    
    def test_answer_response_without_execution_time(self):
        """Edge case: execution_time_ms is optional."""
        response = AnswerResponse(
            answer="There are 47 tanks.",
            sql="SELECT COUNT(*) FROM tanks;",
            rows_count=1
        )
        assert response.execution_time_ms is None


class TestErrorResponse:
    """Tests for ErrorResponse model."""
    
    def test_valid_error_response(self):
        """Happy path: Valid error response serializes correctly."""
        error_detail = ErrorDetail(
            code="QUERY_UNSAFE",
            message="That question can't be answered safely.",
            status=400
        )
        response = ErrorResponse(error=error_detail)
        assert response.error.code == "QUERY_UNSAFE"
        assert response.error.message == "That question can't be answered safely."
        assert response.error.status == 400
        assert response.error.timestamp.endswith("Z")
    
    def test_error_response_with_retry_after(self):
        """Edge case: retry_after is optional."""
        error_detail = ErrorDetail(
            code="RATE_LIMIT_EXCEEDED",
            message="Too many requests.",
            status=429,
            retry_after=45
        )
        response = ErrorResponse(error=error_detail)
        assert response.error.retry_after == 45


class TestHealthResponse:
    """Tests for HealthResponse model."""
    
    def test_healthy_response(self):
        """Happy path: Healthy status serializes correctly."""
        response = HealthResponse(
            status="healthy",
            version="1.0.0",
            checks={"database": "ok", "ai_provider": "ok"}
        )
        assert response.status == "healthy"
        assert response.version == "1.0.0"
        assert response.checks["database"] == "ok"
        assert response.checks["ai_provider"] == "ok"
    
    def test_unhealthy_response(self):
        """Edge case: Unhealthy status with error messages."""
        response = HealthResponse(
            status="unhealthy",
            version="1.0.0",
            checks={"database": "error: connection refused", "ai_provider": "ok"}
        )
        assert response.status == "unhealthy"
        assert "error" in response.checks["database"]


class TestMetricsResponse:
    """Tests for MetricsResponse model."""
    
    def test_valid_metrics_response(self):
        """Happy path: Valid metrics response serializes correctly."""
        response = MetricsResponse(
            requests=RequestStats(total=1234, success=1100, errors=134),
            rate_limiting=RateLimitStats(active_users=5, blocked_requests=23),
            performance=PerformanceStats(
                avg_response_time_ms=2345.5,
                p95_response_time_ms=4500.0,
                p99_response_time_ms=8900.0
            )
        )
        assert response.requests.total == 1234
        assert response.requests.success == 1100
        assert response.requests.errors == 134
        assert response.rate_limiting.active_users == 5
        assert response.rate_limiting.blocked_requests == 23
        assert response.performance.avg_response_time_ms == 2345.5
        assert response.timestamp.endswith("Z")
