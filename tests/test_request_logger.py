"""
Tests for Request Logging Middleware

This module tests the request logging middleware functionality.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import re

from main import app


client = TestClient(app)


class TestRequestLoggingMiddleware:
    """Test request logging middleware functionality."""
    
    def test_request_id_in_response_headers(self):
        """Test that X-Request-ID header is added to responses."""
        response = client.get("/v1/health")
        
        assert "X-Request-ID" in response.headers
        # Should be a valid UUID
        request_id = response.headers["X-Request-ID"]
        uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        assert re.match(uuid_pattern, request_id)
    
    def test_request_logged_with_required_fields(self):
        """Test that requests are logged with all required fields."""
        with patch("api.routes.psycopg2.connect") as mock_connect:
            # Mock successful database connection
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = (1,)
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn
            
            with patch("api.routes.os.getenv") as mock_getenv:
                def getenv_side_effect(key, default=None):
                    env_vars = {
                        "DB_URL": "postgresql://user:pass@localhost/db",
                        "AI_PROVIDER": "openai",
                        "AI_API_KEY": "sk-test",
                        "AI_MODEL": "gpt-4",
                        "SERVICE_VERSION": "1.0.0"
                    }
                    return env_vars.get(key, default)
                
                mock_getenv.side_effect = getenv_side_effect
                
                with patch("middleware.request_logger.logger") as mock_logger:
                    response = client.get("/v1/health")
                    
                    assert response.status_code == 200
                    # Should have logged the request
                    mock_logger.info.assert_called_once()
                    
                    log_message = mock_logger.info.call_args[0][0]
                    # Check for required fields
                    assert "GET /v1/health" in log_message
                    assert "user_id=" in log_message
                    assert "status=200" in log_message
                    assert "duration=" in log_message
                    assert "ms" in log_message
                    assert "request_id=" in log_message
    
    def test_authenticated_request_logs_user_id(self):
        """Test that authenticated requests are logged (user_id extraction happens in route, not middleware)."""
        with patch("middleware.auth.verify_jwt_token") as mock_verify:
            mock_verify.return_value = {"user_id": "user123", "role_name": "admin"}
            
            with patch("middleware.request_logger.logger") as mock_logger:
                with patch("api.routes.pipeline_ask") as mock_ask:
                    mock_ask.return_value = {
                        "answer": "Test answer",
                        "sql": "SELECT 1",
                        "rows_count": 1,
                        "status_code": 200
                    }
                    
                    response = client.post(
                        "/v1/ask",
                        json={"question": "test question"},
                        headers={"Authorization": "Bearer fake_token"}
                    )
                    
                    assert response.status_code == 200
                    
                    # Find the log call for the /ask endpoint
                    log_calls = [call[0][0] for call in mock_logger.info.call_args_list]
                    ask_logs = [log for log in log_calls if "/v1/ask" in log]
                    
                    assert len(ask_logs) > 0
                    log_message = ask_logs[0]
                    # Note: Middleware runs before auth dependency, so user_id will be "anonymous"
                    # The actual user_id is only available in the route handler after dependency injection
                    assert "user_id=" in log_message
                    assert "status=200" in log_message
    
    def test_unauthenticated_request_logs_anonymous(self):
        """Test that unauthenticated requests log 'anonymous' as user."""
        with patch("api.routes.psycopg2.connect") as mock_connect:
            # Mock successful database connection
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = (1,)
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn
            
            with patch("api.routes.os.getenv") as mock_getenv:
                def getenv_side_effect(key, default=None):
                    env_vars = {
                        "DB_URL": "postgresql://user:pass@localhost/db",
                        "AI_PROVIDER": "openai",
                        "AI_API_KEY": "sk-test",
                        "AI_MODEL": "gpt-4",
                        "SERVICE_VERSION": "1.0.0"
                    }
                    return env_vars.get(key, default)
                
                mock_getenv.side_effect = getenv_side_effect
                
                with patch("middleware.request_logger.logger") as mock_logger:
                    response = client.get("/v1/health")
                    
                    assert response.status_code == 200
                    log_message = mock_logger.info.call_args[0][0]
                    assert "user_id=anonymous" in log_message
    
    def test_ask_endpoint_logs_question_preview(self):
        """Test that /ask endpoint logs a preview of the question."""
        with patch("middleware.auth.verify_jwt_token") as mock_verify:
            mock_verify.return_value = {"user_id": "user123", "role_name": "admin"}
            
            with patch("middleware.request_logger.logger") as mock_logger:
                with patch("api.routes.pipeline_ask") as mock_ask:
                    mock_ask.return_value = {
                        "answer": "Test answer",
                        "sql": "SELECT 1",
                        "rows_count": 1,
                        "status_code": 200
                    }
                    
                    response = client.post(
                        "/v1/ask",
                        json={"question": "How many tanks are there?"},
                        headers={"Authorization": "Bearer fake_token"}
                    )
                    
                    assert response.status_code == 200
                    
                    # Find the log call for the /ask endpoint
                    log_calls = [call[0][0] for call in mock_logger.info.call_args_list]
                    ask_logs = [log for log in log_calls if "/v1/ask" in log]
                    
                    assert len(ask_logs) > 0
                    log_message = ask_logs[0]
                    assert "question=" in log_message
                    assert "How many tanks" in log_message
    
    def test_long_question_truncated_in_log(self):
        """Test that long questions are truncated in logs."""
        with patch("middleware.auth.verify_jwt_token") as mock_verify:
            mock_verify.return_value = {"user_id": "user123", "role_name": "admin"}
            
            with patch("middleware.request_logger.logger") as mock_logger:
                with patch("api.routes.pipeline_ask") as mock_ask:
                    mock_ask.return_value = {
                        "answer": "Test answer",
                        "sql": "SELECT 1",
                        "rows_count": 1,
                        "status_code": 200
                    }
                    
                    long_question = "a" * 150  # 150 characters
                    response = client.post(
                        "/v1/ask",
                        json={"question": long_question},
                        headers={"Authorization": "Bearer fake_token"}
                    )
                    
                    assert response.status_code == 200
                    
                    # Find the log call for the /ask endpoint
                    log_calls = [call[0][0] for call in mock_logger.info.call_args_list]
                    ask_logs = [log for log in log_calls if "/v1/ask" in log]
                    
                    assert len(ask_logs) > 0
                    log_message = ask_logs[0]
                    # Should be truncated with ellipsis
                    assert "..." in log_message
    
    def test_error_responses_logged_at_warning_level(self):
        """Test that 4xx responses are logged at WARNING level."""
        with patch("middleware.request_logger.logger") as mock_logger:
            # Request without auth (should return 401)
            response = client.post(
                "/v1/ask",
                json={"question": "test"}
            )
            
            assert response.status_code == 401
            # Should have logged at warning level
            mock_logger.warning.assert_called()
    
    def test_server_errors_logged_at_error_level(self):
        """Test that 5xx responses are logged at ERROR level."""
        with patch("middleware.auth.verify_jwt_token") as mock_verify:
            mock_verify.return_value = {"user_id": "user123", "role_name": "admin"}
            
            with patch("middleware.request_logger.logger") as mock_logger:
                with patch("services.chatbot_pipeline.ask") as mock_ask:
                    # Simulate server error
                    mock_ask.side_effect = Exception("Server error")
                    
                    response = client.post(
                        "/v1/ask",
                        json={"question": "test"},
                        headers={"Authorization": "Bearer fake_token"}
                    )
                    
                    assert response.status_code == 500
                    # Should have logged at error level
                    mock_logger.error.assert_called()
    
    def test_no_sensitive_data_in_logs(self):
        """Test that JWT tokens are never logged."""
        with patch("middleware.auth.verify_jwt_token") as mock_verify:
            mock_verify.return_value = {"user_id": "user123", "role_name": "admin"}
            
            with patch("middleware.request_logger.logger") as mock_logger:
                with patch("api.routes.pipeline_ask") as mock_ask:
                    mock_ask.return_value = {
                        "answer": "Test answer",
                        "sql": "SELECT 1",
                        "rows_count": 1,
                        "status_code": 200
                    }
                    
                    response = client.post(
                        "/v1/ask",
                        json={"question": "test"},
                        headers={"Authorization": "Bearer secret_token_12345"}
                    )
                    
                    assert response.status_code == 200
                    
                    # Check all log calls
                    all_log_calls = (
                        [call[0][0] for call in mock_logger.info.call_args_list] +
                        [call[0][0] for call in mock_logger.warning.call_args_list] +
                        [call[0][0] for call in mock_logger.error.call_args_list]
                    )
                    
                    # JWT token should not appear in any log
                    for log_message in all_log_calls:
                        assert "secret_token_12345" not in log_message
                        assert "Bearer" not in log_message
