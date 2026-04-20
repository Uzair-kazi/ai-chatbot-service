"""
Tests for JWT authentication middleware.

Note: These tests validate the authentication logic.
They use mock JWT tokens for testing purposes.
"""

import os
import pytest
import jwt
from datetime import datetime, timedelta
from fastapi import HTTPException
from middleware.auth import (
    verify_jwt_token,
    is_admin_user,
    authenticate_admin
)


# Test JWT secret (for testing only)
TEST_JWT_SECRET = "test_secret_key_for_testing"


@pytest.fixture(autouse=True)
def set_test_jwt_secret(monkeypatch):
    """Set test JWT secret for all tests."""
    monkeypatch.setenv("JWT_SECRET_KEY", TEST_JWT_SECRET)
    
    # Reload the auth module to pick up the new environment variable
    import sys
    if 'middleware.auth' in sys.modules:
        del sys.modules['middleware.auth']


def create_test_token(payload: dict, expired: bool = False) -> str:
    """Helper function to create test JWT tokens."""
    if expired:
        # Create an expired token (expired 1 hour ago)
        payload["exp"] = datetime.utcnow() - timedelta(hours=1)
    else:
        # Create a valid token (expires in 1 hour)
        payload["exp"] = datetime.utcnow() + timedelta(hours=1)
    
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


def test_verify_jwt_token_with_valid_token():
    """Test that verify_jwt_token successfully decodes a valid token."""
    from middleware.auth import verify_jwt_token
    
    payload = {
        "id": "user123",
        "email": "admin@example.com",
        "name": "Admin User"
    }
    token = create_test_token(payload)
    
    decoded = verify_jwt_token(token)
    
    assert decoded["id"] == "user123"
    assert decoded["email"] == "admin@example.com"
    assert decoded["name"] == "Admin User"


def test_verify_jwt_token_with_expired_token():
    """Test that verify_jwt_token raises ExpiredSignatureError for expired tokens."""
    from middleware.auth import verify_jwt_token
    from jwt.exceptions import ExpiredSignatureError
    
    payload = {
        "id": "user123",
        "email": "admin@example.com"
    }
    token = create_test_token(payload, expired=True)
    
    with pytest.raises(ExpiredSignatureError):
        verify_jwt_token(token)


def test_verify_jwt_token_with_invalid_signature():
    """Test that verify_jwt_token raises InvalidTokenError for invalid signatures."""
    from middleware.auth import verify_jwt_token
    from jwt.exceptions import InvalidTokenError
    
    # Create a token with a different secret
    payload = {"id": "user123"}
    token = jwt.encode(payload, "wrong_secret", algorithm="HS256")
    
    with pytest.raises(InvalidTokenError):
        verify_jwt_token(token)


def test_is_admin_user_with_admin_role():
    """Test that is_admin_user returns True for admin role."""
    from middleware.auth import is_admin_user
    
    # Test with role_name directly in payload
    payload = {"role_name": "admin"}
    assert is_admin_user(payload) is True
    
    # Test with uppercase Admin
    payload = {"role_name": "Admin"}
    assert is_admin_user(payload) is True


def test_is_admin_user_with_non_admin_role():
    """Test that is_admin_user returns False for non-admin roles."""
    from middleware.auth import is_admin_user
    
    payload = {"role_name": "client"}
    assert is_admin_user(payload) is False
    
    payload = {"role_name": "surveyor"}
    assert is_admin_user(payload) is False


def test_is_admin_user_with_nested_role():
    """Test that is_admin_user handles nested role structure."""
    from middleware.auth import is_admin_user
    
    # Test with role nested in payload
    payload = {
        "role": {
            "role_name": "admin"
        }
    }
    assert is_admin_user(payload) is True


def test_is_admin_user_with_missing_role():
    """Test that is_admin_user returns False when role is missing."""
    from middleware.auth import is_admin_user
    
    payload = {"id": "user123", "email": "user@example.com"}
    assert is_admin_user(payload) is False


def test_authenticate_admin_with_valid_admin_token():
    """Test that authenticate_admin succeeds with valid admin token."""
    from middleware.auth import authenticate_admin
    
    payload = {
        "id": "admin123",
        "email": "admin@example.com",
        "name": "Admin User",
        "role_name": "admin"
    }
    token = create_test_token(payload)
    authorization_header = f"Bearer {token}"
    
    result = authenticate_admin(authorization_header)
    
    assert result["id"] == "admin123"
    assert result["email"] == "admin@example.com"


def test_authenticate_admin_with_missing_header():
    """Test that authenticate_admin raises HTTPException when header is missing."""
    from middleware.auth import authenticate_admin
    
    with pytest.raises(HTTPException) as exc_info:
        authenticate_admin(None)
    
    assert exc_info.value.status_code == 401
    assert "Authorization header is required" in exc_info.value.detail


def test_authenticate_admin_with_malformed_header():
    """Test that authenticate_admin raises HTTPException for malformed headers."""
    from middleware.auth import authenticate_admin
    
    # Missing "Bearer" prefix
    with pytest.raises(HTTPException) as exc_info:
        authenticate_admin("just_a_token")
    
    assert exc_info.value.status_code == 401
    assert "Invalid Authorization header format" in exc_info.value.detail


def test_authenticate_admin_with_expired_token():
    """Test that authenticate_admin raises HTTPException for expired tokens."""
    from middleware.auth import authenticate_admin
    
    payload = {
        "id": "admin123",
        "role_name": "admin"
    }
    token = create_test_token(payload, expired=True)
    authorization_header = f"Bearer {token}"
    
    with pytest.raises(HTTPException) as exc_info:
        authenticate_admin(authorization_header)
    
    assert exc_info.value.status_code == 401
    assert "expired" in exc_info.value.detail.lower()


def test_authenticate_admin_with_invalid_token():
    """Test that authenticate_admin raises HTTPException for invalid tokens."""
    from middleware.auth import authenticate_admin
    
    # Create a token with wrong secret
    payload = {"id": "admin123", "role_name": "admin"}
    token = jwt.encode(payload, "wrong_secret", algorithm="HS256")
    authorization_header = f"Bearer {token}"
    
    with pytest.raises(HTTPException) as exc_info:
        authenticate_admin(authorization_header)
    
    assert exc_info.value.status_code == 401
    assert "Invalid token" in exc_info.value.detail


def test_authenticate_admin_with_non_admin_user():
    """Test that authenticate_admin raises HTTPException for non-admin users."""
    from middleware.auth import authenticate_admin
    
    payload = {
        "id": "user123",
        "email": "user@example.com",
        "role_name": "client"
    }
    token = create_test_token(payload)
    authorization_header = f"Bearer {token}"
    
    with pytest.raises(HTTPException) as exc_info:
        authenticate_admin(authorization_header)
    
    assert exc_info.value.status_code == 401
    assert "You must be an admin" in exc_info.value.detail


def test_authenticate_admin_case_insensitive_role():
    """Test that authenticate_admin handles case-insensitive admin role."""
    from middleware.auth import authenticate_admin
    
    # Test with "Admin" (uppercase A)
    payload = {
        "id": "admin123",
        "role_name": "Admin"
    }
    token = create_test_token(payload)
    authorization_header = f"Bearer {token}"
    
    result = authenticate_admin(authorization_header)
    assert result["id"] == "admin123"
    
    # Test with "ADMIN" (all uppercase)
    payload["role_name"] = "ADMIN"
    token = create_test_token(payload)
    authorization_header = f"Bearer {token}"
    
    result = authenticate_admin(authorization_header)
    assert result["id"] == "admin123"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
