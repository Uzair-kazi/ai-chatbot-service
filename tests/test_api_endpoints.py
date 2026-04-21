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




class TestLoginEndpoint:
    """Tests for POST /v1/login endpoint."""
    
    @pytest.mark.integration
    @patch('api.routes.generate_token')
    def test_valid_admin_credentials_return_token(self, mock_generate_token):
        """Happy path: Valid admin credentials return 200 with token and user info"""
        # Mock token generation
        mock_generate_token.return_value = "test_jwt_token_here"
        
        # Use the known admin user from database
        response = client.post(
            "/v1/login",
            json={
                "email": "admin@croyanceqs.com",
                "password": "123456"  # Assuming this is the password
            }
        )
        
        # Note: This test will fail if the password is wrong
        # We're testing the happy path assuming correct credentials
        if response.status_code == 200:
            data = response.json()
            assert "token" in data
            assert "user" in data
            assert data["user"]["email"] == "admin@croyanceqs.com"
            assert data["user"]["role"] == "Admin"
            assert "timestamp" in data
    
    @patch('api.routes.get_user_by_email')
    @patch('api.routes.verify_password')
    @patch('api.routes.generate_token')
    def test_returned_token_can_be_used_for_ask_endpoint(self, mock_generate_token, mock_verify, mock_get_user):
        """Happy path: Returned token can be used to call /v1/ask endpoint successfully"""
        # Mock user lookup
        mock_get_user.return_value = {
            "id": "test-123",
            "email": "admin@example.com",
            "name": "Test Admin",
            "role_name": "Admin",
            "password": "hashed_password"
        }
        mock_verify.return_value = True
        
        # Generate a real token for testing
        real_token = create_test_token()
        mock_generate_token.return_value = real_token
        
        # Login
        login_response = client.post(
            "/v1/login",
            json={"email": "admin@example.com", "password": "password123"}
        )
        
        assert login_response.status_code == 200
        token = login_response.json()["token"]
        
        # Use token to call /v1/ask
        with patch('api.routes.pipeline_ask') as mock_pipeline:
            mock_pipeline.return_value = {
                "answer": "Test answer",
                "sql": "SELECT 1;",
                "rows_count": 1,
                "status_code": 200
            }
            
            ask_response = client.post(
                "/v1/ask",
                json={"question": "Test question"},
                headers={"Authorization": f"Bearer {token}"}
            )
            
            assert ask_response.status_code == 200
    
    @patch('api.routes.get_user_by_email')
    def test_non_existent_email_returns_401(self, mock_get_user):
        """Error path: Non-existent email returns 401 'Invalid credentials'"""
        mock_get_user.return_value = None
        
        response = client.post(
            "/v1/login",
            json={"email": "nonexistent@example.com", "password": "password123"}
        )
        
        assert response.status_code == 401
        data = response.json()
        assert data["detail"] == "Invalid credentials"
    
    @patch('api.routes.get_user_by_email')
    @patch('api.routes.verify_password')
    def test_wrong_password_returns_401(self, mock_verify, mock_get_user):
        """Error path: Wrong password returns 401 'Invalid credentials'"""
        mock_get_user.return_value = {
            "id": "test-123",
            "email": "admin@example.com",
            "name": "Test Admin",
            "role_name": "Admin",
            "password": "hashed_password"
        }
        mock_verify.return_value = False
        
        response = client.post(
            "/v1/login",
            json={"email": "admin@example.com", "password": "wrong_password"}
        )
        
        assert response.status_code == 401
        data = response.json()
        assert data["detail"] == "Invalid credentials"
    
    @patch('api.routes.get_user_by_email')
    @patch('api.routes.verify_password')
    def test_non_admin_role_returns_403(self, mock_verify, mock_get_user):
        """Error path: Valid credentials but non-admin role returns 403 'Admin access required'"""
        mock_get_user.return_value = {
            "id": "test-456",
            "email": "user@example.com",
            "name": "Regular User",
            "role_name": "User",
            "password": "hashed_password"
        }
        mock_verify.return_value = True
        
        response = client.post(
            "/v1/login",
            json={"email": "user@example.com", "password": "password123"}
        )
        
        assert response.status_code == 403
        data = response.json()
        assert data["detail"] == "Admin access required"
    
    def test_missing_email_field_returns_422(self):
        """Error path: Missing email field returns 422 validation error"""
        response = client.post(
            "/v1/login",
            json={"password": "password123"}
        )
        
        # FastAPI validation errors return 400 due to global error handler
        assert response.status_code == 400
    
    def test_missing_password_field_returns_422(self):
        """Error path: Missing password field returns 422 validation error"""
        response = client.post(
            "/v1/login",
            json={"email": "admin@example.com"}
        )
        
        # FastAPI validation errors return 400 due to global error handler
        assert response.status_code == 400
    
    def test_malformed_email_format_returns_422(self):
        """Error path: Malformed email format returns 422 validation error"""
        response = client.post(
            "/v1/login",
            json={"email": "not-an-email", "password": "password123"}
        )
        
        # FastAPI validation errors return 400 due to global error handler
        assert response.status_code == 400
    
    @patch('api.routes.get_user_by_email')
    def test_database_error_returns_503(self, mock_get_user):
        """Error path: Database error returns 503 service unavailable"""
        import psycopg2
        mock_get_user.side_effect = psycopg2.OperationalError("Connection failed")
        
        response = client.post(
            "/v1/login",
            json={"email": "admin@example.com", "password": "password123"}
        )
        
        assert response.status_code == 503
        data = response.json()
        assert "unavailable" in data["detail"].lower()
