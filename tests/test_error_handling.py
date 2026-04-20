"""
Tests for Global Error Handling

This module tests the global exception handlers and error response format
to ensure consistent error handling across the API.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from datetime import datetime

from main import app
from api.errors import ErrorCode


client = TestClient(app)


class TestValidationErrors:
    """Test Pydantic validation error handling."""
    
    def test_missing_question_field(self):
        """Test that missing question field returns 400 with validation error."""
        with patch("middleware.auth.verify_jwt_token") as mock_verify:
            mock_verify.return_value = {"user_id": "user123", "role_name": "admin"}
            
            response = client.post(
                "/v1/ask",
                json={},  # Missing question field
                headers={"Authorization": "Bearer fake_token"}
            )
            
            assert response.status_code == 400
            data = response.json()
            assert data["error"]["code"] == ErrorCode.INVALID_REQUEST
            assert data["error"]["message"] == "Request validation failed"
            assert "validation_errors" in data["error"]["details"]
            assert data["error"]["status"] == 400
            assert "timestamp" in data["error"]
    
    def test_empty_question_string(self):
        """Test that empty question string returns 400."""
        with patch("middleware.auth.verify_jwt_token") as mock_verify:
            mock_verify.return_value = {"user_id": "user123", "role_name": "admin"}
            
            response = client.post(
                "/v1/ask",
                json={"question": ""},
                headers={"Authorization": "Bearer fake_token"}
            )
            
            assert response.status_code == 400
            data = response.json()
            assert data["error"]["code"] == ErrorCode.INVALID_REQUEST
    
    def test_question_too_long(self):
        """Test that question over 500 characters returns 400."""
        with patch("middleware.auth.verify_jwt_token") as mock_verify:
            mock_verify.return_value = {"user_id": "user123", "role_name": "admin"}
            
            long_question = "a" * 501
            response = client.post(
                "/v1/ask",
                json={"question": long_question},
                headers={"Authorization": "Bearer fake_token"}
            )
            
            assert response.status_code == 400
            data = response.json()
            assert data["error"]["code"] == ErrorCode.INVALID_REQUEST
    
    def test_invalid_json_body(self):
        """Test that invalid JSON returns 422."""
        with patch("middleware.auth.verify_jwt_token") as mock_verify:
            mock_verify.return_value = {"user_id": "user123", "role_name": "admin"}
            
            response = client.post(
                "/v1/ask",
                data="not valid json",
                headers={
                    "Authorization": "Bearer fake_token",
                    "Content-Type": "application/json"
                }
            )
            
            assert response.status_code == 422  # FastAPI returns 422 for malformed JSON


class TestPipelineExceptionMapping:
    """Test that pipeline exceptions map to correct HTTP status codes."""
    
    def test_sql_generation_error_returns_500(self):
        """Test that SQLGenerationError returns 500 with AI_SERVICE_ERROR."""
        with patch("middleware.auth.verify_jwt_token") as mock_verify:
            mock_verify.return_value = {"user_id": "user123", "role_name": "admin"}
            
            with patch("services.chatbot_pipeline.ask") as mock_ask:
                # Simulate SQLGenerationError
                from services.sql_generator import SQLGenerationError
                mock_ask.side_effect = SQLGenerationError("AI failed to generate SQL")
                
                response = client.post(
                    "/v1/ask",
                    json={"question": "test question"},
                    headers={"Authorization": "Bearer fake_token"}
                )
                
                assert response.status_code == 500
                data = response.json()
                assert data["error"]["code"] == ErrorCode.AI_SERVICE_ERROR
                assert "generate SQL" in data["error"]["message"]
    
    def test_query_timeout_error_returns_504(self):
        """Test that QueryTimeoutError returns 504 with QUERY_TIMEOUT."""
        with patch("middleware.auth.verify_jwt_token") as mock_verify:
            mock_verify.return_value = {"user_id": "user123", "role_name": "admin"}
            
            with patch("services.chatbot_pipeline.ask") as mock_ask:
                from services.sql_executor import QueryTimeoutError
                mock_ask.side_effect = QueryTimeoutError("Query took too long")
                
                response = client.post(
                    "/v1/ask",
                    json={"question": "test question"},
                    headers={"Authorization": "Bearer fake_token"}
                )
                
                assert response.status_code == 504
                data = response.json()
                assert data["error"]["code"] == ErrorCode.QUERY_TIMEOUT
    
    def test_database_connection_error_returns_503(self):
        """Test that DatabaseConnectionError returns 503 with DATABASE_ERROR."""
        with patch("middleware.auth.verify_jwt_token") as mock_verify:
            mock_verify.return_value = {"user_id": "user123", "role_name": "admin"}
            
            with patch("services.chatbot_pipeline.ask") as mock_ask:
                from services.sql_executor import DatabaseConnectionError
                mock_ask.side_effect = DatabaseConnectionError("Cannot connect to database")
                
                response = client.post(
                    "/v1/ask",
                    json={"question": "test question"},
                    headers={"Authorization": "Bearer fake_token"}
                )
                
                assert response.status_code == 503
                data = response.json()
                assert data["error"]["code"] == ErrorCode.DATABASE_ERROR
    
    def test_sql_syntax_error_returns_400(self):
        """Test that SQLSyntaxError returns 400 with INVALID_REQUEST."""
        with patch("middleware.auth.verify_jwt_token") as mock_verify:
            mock_verify.return_value = {"user_id": "user123", "role_name": "admin"}
            
            with patch("services.chatbot_pipeline.ask") as mock_ask:
                from services.sql_validator import SQLSyntaxError
                mock_ask.side_effect = SQLSyntaxError("Invalid SQL syntax")
                
                response = client.post(
                    "/v1/ask",
                    json={"question": "test question"},
                    headers={"Authorization": "Bearer fake_token"}
                )
                
                assert response.status_code == 400
                data = response.json()
                assert data["error"]["code"] == ErrorCode.INVALID_REQUEST
    
    def test_permission_denied_error_returns_403(self):
        """Test that PermissionDeniedError returns 403 with FORBIDDEN."""
        with patch("middleware.auth.verify_jwt_token") as mock_verify:
            mock_verify.return_value = {"user_id": "user123", "role_name": "admin"}
            
            with patch("services.chatbot_pipeline.ask") as mock_ask:
                from services.sql_validator import PermissionDeniedError
                mock_ask.side_effect = PermissionDeniedError("Access denied")
                
                response = client.post(
                    "/v1/ask",
                    json={"question": "test question"},
                    headers={"Authorization": "Bearer fake_token"}
                )
                
                assert response.status_code == 403
                data = response.json()
                assert data["error"]["code"] == ErrorCode.FORBIDDEN
    
    def test_answer_formatting_error_returns_500(self):
        """Test that AnswerFormattingError returns 500 with AI_SERVICE_ERROR."""
        with patch("middleware.auth.verify_jwt_token") as mock_verify:
            mock_verify.return_value = {"user_id": "user123", "role_name": "admin"}
            
            with patch("services.chatbot_pipeline.ask") as mock_ask:
                from services.answer_formatter import AnswerFormattingError
                mock_ask.side_effect = AnswerFormattingError("Failed to format answer")
                
                response = client.post(
                    "/v1/ask",
                    json={"question": "test question"},
                    headers={"Authorization": "Bearer fake_token"}
                )
                
                assert response.status_code == 500
                data = response.json()
                assert data["error"]["code"] == ErrorCode.AI_SERVICE_ERROR


class TestGenericExceptionHandling:
    """Test handling of unexpected exceptions."""
    
    def test_unhandled_exception_returns_500(self):
        """Test that unhandled exceptions return 500 with INTERNAL_ERROR."""
        with patch("middleware.auth.verify_jwt_token") as mock_verify:
            mock_verify.return_value = {"user_id": "user123", "role_name": "admin"}
            
            with patch("services.chatbot_pipeline.ask") as mock_ask:
                # Simulate unexpected exception
                mock_ask.side_effect = RuntimeError("Unexpected error")
                
                response = client.post(
                    "/v1/ask",
                    json={"question": "test question"},
                    headers={"Authorization": "Bearer fake_token"}
                )
                
                assert response.status_code == 500
                data = response.json()
                assert data["error"]["code"] == ErrorCode.INTERNAL_ERROR
                assert data["error"]["message"] == "An internal error occurred"
    
    def test_error_response_never_exposes_stack_trace(self):
        """Test that stack traces are never exposed in error responses."""
        with patch("middleware.auth.verify_jwt_token") as mock_verify:
            mock_verify.return_value = {"user_id": "user123", "role_name": "admin"}
            
            with patch("services.chatbot_pipeline.ask") as mock_ask:
                mock_ask.side_effect = Exception("Internal details that should not be exposed")
                
                response = client.post(
                    "/v1/ask",
                    json={"question": "test question"},
                    headers={"Authorization": "Bearer fake_token"}
                )
                
                data = response.json()
                # Ensure internal exception message is not exposed
                assert "Internal details" not in data["error"]["message"]
                assert data["error"]["message"] == "An internal error occurred"


class TestErrorResponseFormat:
    """Test that all error responses follow consistent format."""
    
    def test_error_response_has_required_fields(self):
        """Test that error responses have all required fields."""
        with patch("middleware.auth.verify_jwt_token") as mock_verify:
            mock_verify.return_value = {"user_id": "user123", "role_name": "admin"}
            
            response = client.post(
                "/v1/ask",
                json={},  # Missing question field
                headers={"Authorization": "Bearer fake_token"}
            )
            
            data = response.json()
            assert "error" in data
            assert "code" in data["error"]
            assert "message" in data["error"]
            assert "status" in data["error"]
            assert "timestamp" in data["error"]
    
    def test_error_timestamp_is_iso8601(self):
        """Test that error timestamp is in ISO 8601 format."""
        with patch("middleware.auth.verify_jwt_token") as mock_verify:
            mock_verify.return_value = {"user_id": "user123", "role_name": "admin"}
            
            response = client.post(
                "/v1/ask",
                json={},
                headers={"Authorization": "Bearer fake_token"}
            )
            
            data = response.json()
            timestamp = data["error"]["timestamp"]
            
            # Verify ISO 8601 format
            assert timestamp.endswith("Z")
            # Should be parseable as datetime
            datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    
    def test_error_status_matches_http_status(self):
        """Test that error.status field matches HTTP status code."""
        with patch("middleware.auth.verify_jwt_token") as mock_verify:
            mock_verify.return_value = {"user_id": "user123", "role_name": "admin"}
            
            response = client.post(
                "/v1/ask",
                json={},
                headers={"Authorization": "Bearer fake_token"}
            )
            
            assert response.status_code == 400
            data = response.json()
            assert data["error"]["status"] == 400


class TestErrorLogging:
    """Test that errors are logged appropriately."""
    
    def test_validation_errors_logged_as_warning(self):
        """Test that validation errors are logged at WARNING level."""
        with patch("middleware.auth.verify_jwt_token") as mock_verify:
            mock_verify.return_value = {"user_id": "user123", "role_name": "admin"}
            
            with patch("api.errors.logger") as mock_logger:
                response = client.post(
                    "/v1/ask",
                    json={},
                    headers={"Authorization": "Bearer fake_token"}
                )
                
                assert response.status_code == 400
                mock_logger.warning.assert_called_once()
    
    def test_unhandled_exceptions_logged_with_full_details(self):
        """Test that unhandled exceptions are logged with full stack trace."""
        with patch("middleware.auth.verify_jwt_token") as mock_verify:
            mock_verify.return_value = {"user_id": "user123", "role_name": "admin"}
            
            with patch("services.chatbot_pipeline.ask") as mock_ask:
                mock_ask.side_effect = RuntimeError("Test error")
                
                with patch("api.errors.logger") as mock_logger:
                    response = client.post(
                        "/v1/ask",
                        json={"question": "test"},
                        headers={"Authorization": "Bearer fake_token"}
                    )
                    
                    assert response.status_code == 500
                    # Verify exception() was called (logs with stack trace)
                    mock_logger.exception.assert_called_once()
