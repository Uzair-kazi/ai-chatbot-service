"""
Tests for Token Service

Tests JWT token generation and compatibility with existing auth middleware.
"""

import pytest
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import jwt

from services.token_service import generate_token
from middleware.auth import verify_jwt_token, is_admin_user


class TestGenerateToken:
    """Tests for generate_token function"""
    
    def test_generate_token_for_admin_user(self):
        """Happy path: Generate token for admin user, decode it, verify all claims present"""
        user = {
            "id": "test-user-123",
            "email": "admin@example.com",
            "name": "Test Admin",
            "role_name": "Admin"
        }
        
        token = generate_token(user)
        
        # Decode token to verify claims
        jwt_secret = os.getenv("JWT_SECRET_KEY")
        decoded = jwt.decode(token, jwt_secret, algorithms=["HS256"])
        
        assert decoded["id"] == user["id"]
        assert decoded["email"] == user["email"]
        assert decoded["name"] == user["name"]
        assert decoded["role_name"] == user["role_name"]
        assert "exp" in decoded
    
    def test_generate_token_for_non_admin_user(self):
        """Happy path: Generate token for non-admin user, decode it, verify all claims present"""
        user = {
            "id": "test-user-456",
            "email": "user@example.com",
            "name": "Test User",
            "role_name": "User"
        }
        
        token = generate_token(user)
        
        # Decode token to verify claims
        jwt_secret = os.getenv("JWT_SECRET_KEY")
        decoded = jwt.decode(token, jwt_secret, algorithms=["HS256"])
        
        assert decoded["id"] == user["id"]
        assert decoded["email"] == user["email"]
        assert decoded["name"] == user["name"]
        assert decoded["role_name"] == user["role_name"]
        assert "exp" in decoded
    
    def test_generated_token_passes_middleware_validation(self):
        """Integration: Generated token passes middleware/auth.py validation"""
        user = {
            "id": "test-user-789",
            "email": "test@example.com",
            "name": "Test User",
            "role_name": "Admin"
        }
        
        token = generate_token(user)
        
        # Verify token passes middleware validation
        payload = verify_jwt_token(token)
        
        assert payload["id"] == user["id"]
        assert payload["email"] == user["email"]
        assert payload["name"] == user["name"]
        assert payload["role_name"] == user["role_name"]
    
    def test_generated_admin_token_passes_is_admin_check(self):
        """Integration: Generated admin token passes is_admin_user() check"""
        user = {
            "id": "test-admin-123",
            "email": "admin@example.com",
            "name": "Admin User",
            "role_name": "Admin"
        }
        
        token = generate_token(user)
        payload = verify_jwt_token(token)
        
        assert is_admin_user(payload) is True
    
    def test_generated_non_admin_token_fails_is_admin_check(self):
        """Integration: Generated non-admin token fails is_admin_user() check"""
        user = {
            "id": "test-user-456",
            "email": "user@example.com",
            "name": "Regular User",
            "role_name": "User"
        }
        
        token = generate_token(user)
        payload = verify_jwt_token(token)
        
        assert is_admin_user(payload) is False
    
    @patch.dict(os.environ, {"JWT_TOKEN_EXPIRATION_HOURS": "2"})
    def test_token_expiration_from_environment(self):
        """Edge case: Token expiration time is correctly set based on environment variable"""
        user = {
            "id": "test-user-123",
            "email": "test@example.com",
            "name": "Test User",
            "role_name": "Admin"
        }
        
        token = generate_token(user)
        
        # Decode and check expiration
        jwt_secret = os.getenv("JWT_SECRET_KEY")
        decoded = jwt.decode(token, jwt_secret, algorithms=["HS256"])
        
        exp_time = datetime.fromtimestamp(decoded["exp"], tz=timezone.utc)
        now = datetime.now(timezone.utc)
        time_diff = exp_time - now
        
        # Should be approximately 2 hours (allow 1 minute tolerance)
        assert timedelta(hours=1, minutes=59) < time_diff < timedelta(hours=2, minutes=1)
    
    @patch.dict(os.environ, {"JWT_SECRET_KEY": ""}, clear=False)
    def test_missing_jwt_secret_raises_value_error(self):
        """Edge case: Missing JWT_SECRET_KEY raises ValueError with clear message"""
        user = {
            "id": "test-user-123",
            "email": "test@example.com",
            "name": "Test User",
            "role_name": "Admin"
        }
        
        with pytest.raises(ValueError, match="JWT_SECRET_KEY environment variable is required"):
            generate_token(user)
    
    def test_missing_user_field_raises_value_error(self):
        """Error path: Missing required user field raises ValueError"""
        user = {
            "id": "test-user-123",
            "email": "test@example.com",
            "name": "Test User"
            # Missing role_name
        }
        
        with pytest.raises(ValueError, match="User data missing required field: role_name"):
            generate_token(user)
