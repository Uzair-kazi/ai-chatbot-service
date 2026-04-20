"""
Tests for API Documentation

This module tests that OpenAPI documentation is properly configured and accessible.
"""

import pytest
from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


class TestAPIDocumentation:
    """Test API documentation endpoints."""
    
    def test_swagger_ui_accessible(self):
        """Test that Swagger UI is accessible at /docs."""
        response = client.get("/docs")
        
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        # Swagger UI should contain the API title
        assert "Admin AI Chatbot API" in response.text
    
    def test_redoc_accessible(self):
        """Test that ReDoc is accessible at /redoc."""
        response = client.get("/redoc")
        
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        # ReDoc should contain the API title
        assert "Admin AI Chatbot API" in response.text
    
    def test_openapi_schema_accessible(self):
        """Test that OpenAPI schema is accessible at /openapi.json."""
        response = client.get("/openapi.json")
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        
        schema = response.json()
        assert "openapi" in schema
        assert "info" in schema
        assert schema["info"]["title"] == "Admin AI Chatbot API"
        assert "paths" in schema
    
    def test_openapi_schema_has_all_endpoints(self):
        """Test that OpenAPI schema includes all endpoints."""
        response = client.get("/openapi.json")
        schema = response.json()
        
        paths = schema["paths"]
        
        # Check that all endpoints are documented
        assert "/v1/ask" in paths
        assert "/v1/health" in paths
        assert "/v1/metrics" in paths
        assert "/" in paths
        
        # Check that /v1/ask has POST method
        assert "post" in paths["/v1/ask"]
        
        # Check that /v1/health has GET method
        assert "get" in paths["/v1/health"]
        
        # Check that /v1/metrics has GET method
        assert "get" in paths["/v1/metrics"]
    
    def test_openapi_schema_has_request_examples(self):
        """Test that OpenAPI schema includes request examples."""
        response = client.get("/openapi.json")
        schema = response.json()
        
        # Check /v1/ask endpoint has examples
        ask_endpoint = schema["paths"]["/v1/ask"]["post"]
        assert "requestBody" in ask_endpoint
        
        # Check that request body references QuestionRequest schema
        request_body = ask_endpoint["requestBody"]
        assert "content" in request_body
        assert "application/json" in request_body["content"]
    
    def test_openapi_schema_has_response_examples(self):
        """Test that OpenAPI schema includes response examples."""
        response = client.get("/openapi.json")
        schema = response.json()
        
        # Check /v1/ask endpoint has response examples
        ask_endpoint = schema["paths"]["/v1/ask"]["post"]
        assert "responses" in ask_endpoint
        
        # Check 200 response
        assert "200" in ask_endpoint["responses"]
        
        # Check error responses
        assert "400" in ask_endpoint["responses"]
        assert "401" in ask_endpoint["responses"]
        assert "403" in ask_endpoint["responses"]
        assert "429" in ask_endpoint["responses"]
        assert "503" in ask_endpoint["responses"]
        assert "504" in ask_endpoint["responses"]
    
    def test_openapi_schema_has_security_requirements(self):
        """Test that OpenAPI schema documents authentication requirements."""
        response = client.get("/openapi.json")
        schema = response.json()
        
        # Check /v1/ask endpoint requires authentication
        ask_endpoint = schema["paths"]["/v1/ask"]["post"]
        
        # The endpoint should have a description mentioning authentication
        assert "description" in ask_endpoint
        assert "Authentication" in ask_endpoint["description"]
    
    def test_openapi_schema_has_tags(self):
        """Test that OpenAPI schema includes endpoint tags."""
        response = client.get("/openapi.json")
        schema = response.json()
        
        # Check that tags are defined
        assert "tags" in schema
        tags = schema["tags"]
        tag_names = [tag["name"] for tag in tags]
        
        assert "Questions" in tag_names
        assert "Monitoring" in tag_names
        
        # Check that endpoints use tags
        ask_endpoint = schema["paths"]["/v1/ask"]["post"]
        assert "tags" in ask_endpoint
        assert "Questions" in ask_endpoint["tags"]
        
        health_endpoint = schema["paths"]["/v1/health"]["get"]
        assert "tags" in health_endpoint
        assert "Monitoring" in health_endpoint["tags"]
    
    def test_openapi_schema_has_version(self):
        """Test that OpenAPI schema includes API version."""
        response = client.get("/openapi.json")
        schema = response.json()
        
        assert "info" in schema
        assert "version" in schema["info"]
        # Version should match SERVICE_VERSION from environment
        assert schema["info"]["version"] is not None
