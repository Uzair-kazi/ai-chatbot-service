"""
Tests for User Service

Tests user credential lookup and password verification functionality.
"""

import pytest
import os
from unittest.mock import patch, MagicMock
import psycopg2
import bcrypt

from services.user_service import get_user_by_email, verify_password


class TestGetUserByEmail:
    """Tests for get_user_by_email function"""
    
    @pytest.mark.integration
    def test_fetch_existing_admin_user(self):
        """Happy path: Fetch existing admin user by email returns complete user record with role"""
        # Use the known admin user from the database
        user = get_user_by_email("admin@croyanceqs.com")
        
        assert user is not None
        assert user["email"] == "admin@croyanceqs.com"
        assert user["name"] == "Admin"
        assert user["role_name"] == "Admin"
        assert "id" in user
        assert "password" in user
        assert "role_id" in user
    
    @pytest.mark.integration
    def test_fetch_existing_non_admin_user(self):
        """Happy path: Fetch existing non-admin user by email returns user record with non-admin role"""
        # Use a known non-admin user from the database
        user = get_user_by_email("service@croyanceqs.com")
        
        assert user is not None
        assert user["email"] == "service@croyanceqs.com"
        assert user["role_name"] != "Admin"
        assert "id" in user
        assert "password" in user
    
    @pytest.mark.integration
    def test_query_non_existent_email(self):
        """Edge case: Query with non-existent email returns None"""
        user = get_user_by_email("nonexistent@example.com")
        
        assert user is None
    
    def test_query_empty_string_email(self):
        """Edge case: Query with empty string email returns None"""
        user = get_user_by_email("")
        
        assert user is None
    
    def test_query_whitespace_email(self):
        """Edge case: Query with whitespace-only email returns None"""
        user = get_user_by_email("   ")
        
        assert user is None
    
    def test_query_malformed_email(self):
        """Edge case: Query with malformed email returns None (no validation, just lookup)"""
        # The function doesn't validate email format, just looks it up
        # If it doesn't exist in DB, returns None
        user = get_user_by_email("not-an-email")
        
        assert user is None
    
    @patch('services.user_service.psycopg2.connect')
    def test_database_connection_failure(self, mock_connect):
        """Error path: Database connection failure raises appropriate exception"""
        mock_connect.side_effect = psycopg2.OperationalError("Connection failed")
        
        with pytest.raises(psycopg2.OperationalError):
            get_user_by_email("test@example.com")
    
    @patch.dict(os.environ, {"DB_URL": ""}, clear=False)
    def test_missing_db_url(self):
        """Error path: Missing DB_URL raises ValueError"""
        with pytest.raises(ValueError, match="DB_URL environment variable is not configured"):
            get_user_by_email("test@example.com")



class TestVerifyPassword:
    """Tests for verify_password function"""
    
    def test_correct_password_returns_true(self):
        """Happy path: Correct password against valid bcrypt hash returns True"""
        # Create a test password and hash
        password = "test_password_123"
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        result = verify_password(password, hashed)
        
        assert result is True
    
    def test_incorrect_password_returns_false(self):
        """Happy path: Incorrect password against valid bcrypt hash returns False"""
        # Create a test password and hash
        password = "test_password_123"
        wrong_password = "wrong_password"
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        result = verify_password(wrong_password, hashed)
        
        assert result is False
    
    def test_empty_password_returns_false(self):
        """Edge case: Empty password against hash returns False"""
        # Create a test hash
        hashed = bcrypt.hashpw(b"test", bcrypt.gensalt()).decode('utf-8')
        
        result = verify_password("", hashed)
        
        assert result is False
    
    def test_empty_hash_raises_value_error(self):
        """Edge case: Empty hash string raises ValueError"""
        with pytest.raises(ValueError, match="Hash cannot be empty"):
            verify_password("test_password", "")
    
    def test_malformed_hash_raises_value_error(self):
        """Edge case: Malformed hash string raises ValueError"""
        with pytest.raises(ValueError, match="Invalid hash format"):
            verify_password("test_password", "not_a_valid_bcrypt_hash")
    
    def test_none_password_raises_type_error(self):
        """Error path: None value for password raises TypeError"""
        hashed = bcrypt.hashpw(b"test", bcrypt.gensalt()).decode('utf-8')
        
        with pytest.raises(TypeError, match="Password and hash cannot be None"):
            verify_password(None, hashed)
    
    def test_none_hash_raises_type_error(self):
        """Error path: None value for hash raises TypeError"""
        with pytest.raises(TypeError, match="Password and hash cannot be None"):
            verify_password("test_password", None)
