"""
Tests for API Endpoints

Integration tests for all FastAPI endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import jwt
import os
from datetime import datetime, timedelta, timezone

from main import app

# Create test client
client = TestClient(app)

# Test JWT secret (must match the one in .env or use a test value)
TEST_JWT_SECRET = os.getenv("JWT_SECRET_KEY", "test_secret_key_for_testing")


def create_test_token(user_id="test_user_123", role_name="admin", expired=False):
    """Helper to create test JWT tokens."""
    payload = {
        "id": user_id,
        "email": "test@example.com",
        "role_name": role_name,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1 if not expired else -1)
    }
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


class TestAskEndpoint:
    """Tests for POST /v1/ask endpoint."""
    
    @patch('api.routes.pipeline_ask')
    def test_valid_question_with_jwt_returns_answer(self, mock_pipeline):
        """Happy path: Valid question with JWT returns answer."""
        # Mock pipeline response
        mock_pipeline.return_value = {
            "answer": "There are 47 ISO tanks with status 'IN'.",
            "sql": "SELECT COUNT(*) FROM iso_tank WHERE iso_tank_status = 'IN' LIMIT 100;",
            "rows_count": 1,
            "status_code": 200
        }
        
        token = create_test_token()
        response = client.post(
            "/v1/ask",
            json={"question": "How many ISO tanks are in 'IN' status?"},
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "sql" in data
        assert "rows_count" in data
        assert "timestamp" in data
        assert data["answer"] == "There are 47 ISO tanks with status 'IN'."
        assert data["rows_count"] == 1
    
    @patch('api.routes.pipeline_ask')
    def test_response_includes_all_fields(self, mock_pipeline):
        """Happy path: Response includes answer, SQL, row count, timestamp."""
        mock_pipeline.return_value = {
            "answer": "Test answer",
            "sql": "SELECT * FROM test;",
            "rows_count": 5,
            "execution_time_ms": 1234,
            "status_code": 200
        }
        
        token = create_test_token()
        response = client.post(
            "/v1/ask",
            json={"question": "Test question?"},
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "Test answer"
        assert data["sql"] == "SELECT * FROM test;"
        assert data["rows_count"] == 5
        assert data["execution_time_ms"] == 1234
        assert data["timestamp"].endswith("Z")
    
    def test_missing_authorization_header_returns_401(self):
        """Error path: Missing Authorization header returns 401."""
        response = client.post(
            "/v1/ask",
            json={"question": "How many tanks?"}
        )
        
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        assert "authorization" in data["detail"].lower()
    
    def test_invalid_jwt_token_returns_401(self):
        """Error path: Invalid JWT token returns 401."""
        response = client.post(
            "/v1/ask",
            json={"question": "How many tanks?"},
            headers={"Authorization": "Bearer invalid_token_here"}
        )
        
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
    
    def test_expired_jwt_token_returns_401(self):
        """Error path: Expired JWT token returns 401."""
        token = create_test_token(expired=True)
        response = client.post(
            "/v1/ask",
            json={"question": "How many tanks?"},
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        assert "expired" in data["detail"].lower()
    
    def test_non_admin_user_returns_403(self):
        """Error path: Non-admin user returns 403."""
        token = create_test_token(role_name="user")  # Not admin
        response = client.post(
            "/v1/ask",
            json={"question": "How many tanks?"},
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 403
        data = response.json()
        assert "detail" in data
        assert "admin" in data["detail"].lower()
    
    def test_invalid_question_format_returns_400(self):
        """Error path: Invalid question format returns 400."""
        token = create_test_token()
        
        # Empty question
        response = client.post(
            "/v1/ask",
            json={"question": ""},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 422  # Pydantic validation error
        
        # Whitespace-only question
        response = client.post(
            "/v1/ask",
            json={"question": "   "},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 422
        
        # Question too long (>500 chars)
        response = client.post(
            "/v1/ask",
            json={"question": "a" * 501},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 422
    
    @patch('api.routes.pipeline_ask')
    def test_pipeline_safety_check_failure_returns_400(self, mock_pipeline):
        """Error path: Pipeline safety check failure returns 400."""
        mock_pipeline.return_value = {
            "answer": "That question can't be answered safely.",
            "sql": "DROP TABLE users;",
            "rows_count": 0,
            "status_code": 400,
            "error": "SQL safety check failed"
        }
        
        token = create_test_token()
        response = client.post(
            "/v1/ask",
            json={"question": "Drop all tables"},
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
    
    @patch('api.routes.pipeline_ask')
    def test_pipeline_timeout_returns_504(self, mock_pipeline):
        """Error path: Pipeline timeout returns 504."""
        mock_pipeline.return_value = {
            "answer": "Query took too long.",
            "sql": "SELECT * FROM huge_table;",
            "rows_count": 0,
            "status_code": 504,
            "error": "Query timeout"
        }
        
        token = create_test_token()
        response = client.post(
            "/v1/ask",
            json={"question": "Complex query"},
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 504
        data = response.json()
        assert "detail" in data
    
    @patch('api.routes.pipeline_ask')
    def test_database_connection_failure_returns_503(self, mock_pipeline):
        """Error path: Database connection failure returns 503."""
        mock_pipeline.return_value = {
            "answer": "Database unavailable.",
            "sql": "",
            "rows_count": 0,
            "status_code": 503,
            "error": "Database connection failed"
        }
        
        token = create_test_token()
        response = client.post(
            "/v1/ask",
            json={"question": "Any question"},
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 503
        data = response.json()
        assert "detail" in data
    
    @patch('api.routes.pipeline_ask')
    def test_end_to_end_with_real_jwt_and_pipeline(self, mock_pipeline):
        """Integration: End-to-end request with real JWT and pipeline."""
        mock_pipeline.return_value = {
            "answer": "Integration test answer",
            "sql": "SELECT 1;",
            "rows_count": 1,
            "status_code": 200
        }
        
        token = create_test_token()
        response = client.post(
            "/v1/ask",
            json={"question": "Integration test question"},
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "Integration test answer"
        assert data["sql"] == "SELECT 1;"
        
        # Verify pipeline was called with the question
        mock_pipeline.assert_called_once_with("Integration test question")
    
    @patch('api.routes.pipeline_ask')
    def test_question_whitespace_is_trimmed(self, mock_pipeline):
        """Validation: Question with leading/trailing whitespace is trimmed."""
        mock_pipeline.return_value = {
            "answer": "Test answer",
            "sql": "SELECT 1;",
            "rows_count": 1,
            "status_code": 200
        }
        
        token = create_test_token()
        response = client.post(
            "/v1/ask",
            json={"question": "  How many tanks?  "},
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        
        # Verify pipeline received the trimmed question
        mock_pipeline.assert_called_once_with("How many tanks?")


class TestRootEndpoint:
    """Tests for root endpoint."""
    
    def test_root_endpoint_returns_api_info(self):
        """Happy path: Root endpoint returns API information."""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data
        assert "docs" in data
        assert "health" in data

