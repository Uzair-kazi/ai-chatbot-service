"""
Tests for API Models

Tests Pydantic model validation for login endpoints.
"""

import pytest
from pydantic import ValidationError

from api.models import LoginRequest, LoginResponse, UserInfo


class TestLoginRequest:
    """Tests for LoginRequest model"""
    
    def test_valid_email_and_password(self):
        """Happy path: Valid email and password pass validation"""
        request = LoginRequest(
            email="admin@example.com",
            password="secure_password"
        )
        
        assert request.email == "admin@example.com"
        assert request.password == "secure_password"
    
    def test_email_format_validation_rejects_invalid(self):
        """Edge case: Email field validates email format (reject invalid formats)"""
        with pytest.raises(ValidationError) as exc_info:
            LoginRequest(
                email="not-an-email",
                password="password123"
            )
        
        errors = exc_info.value.errors()
        assert any("Invalid email format" in str(error) for error in errors)
    
    def test_email_format_validation_rejects_missing_at(self):
        """Edge case: Email without @ is rejected"""
        with pytest.raises(ValidationError) as exc_info:
            LoginRequest(
                email="notemail.com",
                password="password123"
            )
        
        errors = exc_info.value.errors()
        assert any("Invalid email format" in str(error) for error in errors)
    
    def test_password_rejects_empty_string(self):
        """Edge case: Password field rejects empty string"""
        with pytest.raises(ValidationError) as exc_info:
            LoginRequest(
                email="admin@example.com",
                password=""
            )
        
        errors = exc_info.value.errors()
        assert any("Password cannot be empty" in str(error) or "at least 1 character" in str(error) for error in errors)
    
    def test_password_accepts_any_non_empty_string(self):
        """Edge case: Password field accepts any non-empty string (no max length)"""
        long_password = "a" * 1000
        request = LoginRequest(
            email="admin@example.com",
            password=long_password
        )
        
        assert request.password == long_password
    
    def test_missing_email_field_raises_validation_error(self):
        """Error path: Missing email field raises validation error"""
        with pytest.raises(ValidationError) as exc_info:
            LoginRequest(password="password123")
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("email",) for error in errors)
    
    def test_missing_password_field_raises_validation_error(self):
        """Error path: Missing password field raises validation error"""
        with pytest.raises(ValidationError) as exc_info:
            LoginRequest(email="admin@example.com")
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("password",) for error in errors)
    
    def test_email_whitespace_is_trimmed(self):
        """Edge case: Email whitespace is trimmed"""
        request = LoginRequest(
            email="  admin@example.com  ",
            password="password123"
        )
        
        assert request.email == "admin@example.com"


class TestLoginResponse:
    """Tests for LoginResponse model"""
    
    def test_valid_login_response(self):
        """Happy path: Valid login response with all fields"""
        response = LoginResponse(
            token="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            user=UserInfo(
                id="123",
                email="admin@example.com",
                name="Admin User",
                role="Admin"
            )
        )
        
        assert response.token == "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
        assert response.user.id == "123"
        assert response.user.email == "admin@example.com"
        assert response.user.name == "Admin User"
        assert response.user.role == "Admin"
        assert response.timestamp is not None
    
    def test_timestamp_auto_generated(self):
        """Edge case: Timestamp is automatically generated if not provided"""
        response = LoginResponse(
            token="test_token",
            user=UserInfo(
                id="123",
                email="test@example.com",
                name="Test User",
                role="User"
            )
        )
        
        assert response.timestamp is not None
        assert "Z" in response.timestamp  # ISO 8601 format with Z suffix
