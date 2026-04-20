"""
Pydantic Models

This module defines request and response models for API validation and serialization.
All models include examples for OpenAPI documentation.
"""

from datetime import datetime, timezone
from typing import Dict, Optional
from pydantic import BaseModel, Field, field_validator


class QuestionRequest(BaseModel):
    """Request model for asking a question."""
    
    question: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Natural language question about the database",
        examples=["How many ISO tanks are in 'IN' status?"]
    )
    
    @field_validator('question')
    @classmethod
    def question_must_not_be_whitespace(cls, v: str) -> str:
        """Validate that question is not empty or whitespace-only after trimming."""
        trimmed = v.strip()
        if not trimmed:
            raise ValueError('Question cannot be empty or whitespace-only')
        if len(trimmed) > 500:
            raise ValueError('Question must be 500 characters or less')
        return trimmed
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "question": "How many ISO tanks are in 'IN' status?"
                },
                {
                    "question": "Which clients have the most tanks this month?"
                },
                {
                    "question": "Show me all tanks that haven't been surveyed in 90 days"
                }
            ]
        }
    }


class AnswerResponse(BaseModel):
    """Response model for successful question answers."""
    
    answer: str = Field(
        ...,
        description="Natural language answer to the question"
    )
    sql: str = Field(
        ...,
        description="SQL query that was executed"
    )
    rows_count: int = Field(
        ...,
        description="Number of rows returned by the query"
    )
    execution_time_ms: Optional[int] = Field(
        None,
        description="Query execution time in milliseconds"
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        description="Response timestamp in ISO 8601 format"
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "answer": "There are currently 47 ISO tanks with status 'IN'.",
                    "sql": "SELECT COUNT(*) FROM iso_tank WHERE iso_tank_status = 'IN' LIMIT 100;",
                    "rows_count": 1,
                    "execution_time_ms": 1234,
                    "timestamp": "2026-04-20T10:30:00Z"
                }
            ]
        }
    }


class ErrorDetail(BaseModel):
    """Error detail structure."""
    
    code: str = Field(
        ...,
        description="Machine-readable error code"
    )
    message: str = Field(
        ...,
        description="Human-readable error message"
    )
    status: int = Field(
        ...,
        description="HTTP status code"
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        description="Error timestamp in ISO 8601 format"
    )
    retry_after: Optional[int] = Field(
        None,
        description="Seconds to wait before retrying (for rate limit errors)"
    )


class ErrorResponse(BaseModel):
    """Response model for errors."""
    
    error: ErrorDetail
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "error": {
                        "code": "QUERY_UNSAFE",
                        "message": "That question can't be answered safely.",
                        "status": 400,
                        "timestamp": "2026-04-20T10:30:00Z"
                    }
                },
                {
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": "Too many requests. Please wait 45 seconds before trying again.",
                        "status": 429,
                        "retry_after": 45,
                        "timestamp": "2026-04-20T10:30:00Z"
                    }
                }
            ]
        }
    }


class HealthCheck(BaseModel):
    """Health check detail for a dependency."""
    
    status: str = Field(
        ...,
        description="Status of the check: 'ok' or error message"
    )


class HealthResponse(BaseModel):
    """Response model for health check endpoint."""
    
    status: str = Field(
        ...,
        description="Overall health status: 'healthy' or 'unhealthy'"
    )
    version: str = Field(
        ...,
        description="Service version"
    )
    checks: Dict[str, str] = Field(
        ...,
        description="Individual health checks for dependencies"
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        description="Health check timestamp in ISO 8601 format"
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": "healthy",
                    "version": "1.0.0",
                    "checks": {
                        "database": "ok",
                        "ai_provider": "ok"
                    },
                    "timestamp": "2026-04-20T10:30:00Z"
                },
                {
                    "status": "unhealthy",
                    "version": "1.0.0",
                    "checks": {
                        "database": "error: connection refused",
                        "ai_provider": "ok"
                    },
                    "timestamp": "2026-04-20T10:30:00Z"
                }
            ]
        }
    }


class RequestStats(BaseModel):
    """Request statistics."""
    
    total: int = Field(..., description="Total requests")
    success: int = Field(..., description="Successful requests")
    errors: int = Field(..., description="Failed requests")


class RateLimitStats(BaseModel):
    """Rate limiting statistics."""
    
    active_users: int = Field(..., description="Number of active users")
    blocked_requests: int = Field(..., description="Number of blocked requests")


class PerformanceStats(BaseModel):
    """Performance statistics."""
    
    avg_response_time_ms: float = Field(..., description="Average response time in milliseconds")
    p95_response_time_ms: float = Field(..., description="95th percentile response time")
    p99_response_time_ms: float = Field(..., description="99th percentile response time")


class MetricsResponse(BaseModel):
    """Response model for metrics endpoint."""
    
    requests: RequestStats
    rate_limiting: RateLimitStats
    performance: PerformanceStats
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        description="Metrics timestamp in ISO 8601 format"
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "requests": {
                        "total": 1234,
                        "success": 1100,
                        "errors": 134
                    },
                    "rate_limiting": {
                        "active_users": 5,
                        "blocked_requests": 23
                    },
                    "performance": {
                        "avg_response_time_ms": 2345.5,
                        "p95_response_time_ms": 4500.0,
                        "p99_response_time_ms": 8900.0
                    },
                    "timestamp": "2026-04-20T10:30:00Z"
                }
            ]
        }
    }
