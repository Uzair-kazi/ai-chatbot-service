"""
Tests for User Service

Tests user credential lookup and password verification functionality.
"""

import pytest
import os
from unittest.mock import patch, MagicMock
import psycopg2

from services.user_service import get_user_by_email


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
