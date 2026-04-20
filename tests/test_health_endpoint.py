"""
Tests for Health Check Endpoint

This module tests the /v1/health endpoint to ensure proper health monitoring.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import psycopg2

from main import app


client = TestClient(app)


class TestHealthEndpoint:
    """Test health check endpoint functionality."""
    
    def test_health_check_all_healthy(self):
        """Test that health check returns 200 when all checks pass."""
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
                
                response = client.get("/v1/health")
                
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "healthy"
                assert data["version"] == "1.0.0"
                assert "checks" in data
                assert data["checks"]["database"]["status"] == "healthy"
                assert data["checks"]["ai_provider"]["status"] == "healthy"
    
    def test_health_check_database_failure(self):
        """Test that health check returns 503 when database check fails."""
        with patch("api.routes.psycopg2.connect") as mock_connect:
            # Mock database connection failure
            mock_connect.side_effect = psycopg2.OperationalError("Connection failed")
            
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
                
                response = client.get("/v1/health")
                
                assert response.status_code == 503
                data = response.json()
                assert data["detail"]["status"] == "unhealthy"
                assert data["detail"]["checks"]["database"]["status"] == "unhealthy"
                assert "Connection failed" in data["detail"]["checks"]["database"]["message"]
    
    def test_health_check_missing_db_url(self):
        """Test that health check returns 503 when DB_URL is missing."""
        with patch("api.routes.os.getenv") as mock_getenv:
            def getenv_side_effect(key, default=None):
                env_vars = {
                    "AI_PROVIDER": "openai",
                    "AI_API_KEY": "sk-test",
                    "AI_MODEL": "gpt-4",
                    "SERVICE_VERSION": "1.0.0"
                }
                return env_vars.get(key, default)
            
            mock_getenv.side_effect = getenv_side_effect
            
            response = client.get("/v1/health")
            
            assert response.status_code == 503
            data = response.json()
            assert data["detail"]["status"] == "unhealthy"
            assert data["detail"]["checks"]["database"]["status"] == "unhealthy"
            assert "not configured" in data["detail"]["checks"]["database"]["message"]
    
    def test_health_check_missing_ai_config(self):
        """Test that health check returns 503 when AI config is missing."""
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
                        "SERVICE_VERSION": "1.0.0"
                        # Missing AI_PROVIDER, AI_API_KEY, AI_MODEL
                    }
                    return env_vars.get(key, default)
                
                mock_getenv.side_effect = getenv_side_effect
                
                response = client.get("/v1/health")
                
                assert response.status_code == 503
                data = response.json()
                assert data["detail"]["status"] == "unhealthy"
                assert data["detail"]["checks"]["ai_provider"]["status"] == "unhealthy"
                assert "Missing configuration" in data["detail"]["checks"]["ai_provider"]["message"]
    
    def test_health_check_no_authentication_required(self):
        """Test that health check endpoint does not require authentication."""
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
                
                # Call without Authorization header
                response = client.get("/v1/health")
                
                assert response.status_code == 200
    
    def test_health_check_response_time(self):
        """Test that health check responds quickly (under 1 second)."""
        import time
        
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
                
                start_time = time.time()
                response = client.get("/v1/health")
                end_time = time.time()
                
                assert response.status_code == 200
                assert (end_time - start_time) < 1.0  # Under 1 second
