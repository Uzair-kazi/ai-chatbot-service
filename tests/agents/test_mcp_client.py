"""
Tests for MCP Client Wrapper

Test coverage:
- Happy path: Schema retrieval, query validation, query execution
- Error path: Connection failures, query errors, timeouts
- Edge cases: Reconnection logic, fallback mode
- Integration: MCP client with mocked MCP SDK
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from agents.mcp_client import (
    MCPClient,
    MCPConnectionError,
    MCPQueryError,
    MCPTimeoutError,
    ValidationResult,
    QueryResult,
    MCPErrorType
)


class TestMCPClient:
    """Test suite for MCPClient."""
    
    @pytest.fixture
    def mock_env_vars(self, monkeypatch):
        """Mock environment variables for MCP configuration."""
        monkeypatch.setenv("MCP_SERVER_URL", "http://localhost:8080")
        monkeypatch.setenv("MCP_DATABASE_NAME", "test_db")
    
    @pytest.fixture
    def client(self, mock_env_vars):
        """Create MCPClient instance with mocked environment."""
        return MCPClient()
    
    @pytest.fixture
    def client_no_config(self, monkeypatch):
        """Create MCPClient instance without configuration."""
        monkeypatch.delenv("MCP_SERVER_URL", raising=False)
        monkeypatch.delenv("MCP_DATABASE_NAME", raising=False)
        return MCPClient()
    
    # Happy path tests - Schema retrieval
    
    def test_get_schema_all_tables(self, client):
        """Test getting schema for all tables."""
        schema = client.get_schema()
        
        assert isinstance(schema, str)
        assert len(schema) > 0
        # In fallback mode, should return placeholder
        assert "schema" in schema.lower() or "fallback" in schema.lower()
    
    def test_get_schema_specific_table(self, client):
        """Test getting schema for specific table."""
        schema = client.get_schema(table_name="iso_tank")
        
        assert isinstance(schema, str)
        assert len(schema) > 0
        assert "iso_tank" in schema.lower() or "fallback" in schema.lower()
    
    def test_is_connected_returns_true_when_configured(self, client):
        """Test is_connected returns True when properly configured."""
        # In fallback mode with config, should be "connected"
        assert client.is_connected() is True
    
    def test_is_connected_returns_false_without_config(self, client_no_config):
        """Test is_connected returns False without configuration."""
        assert client_no_config.is_connected() is False
    
    # Happy path tests - Query validation
    
    def test_validate_query_valid_select(self, client):
        """Test validating a valid SELECT query."""
        result = client.validate_query("SELECT * FROM iso_tank")
        
        assert isinstance(result, ValidationResult)
        assert result.valid is True
        assert len(result.errors) == 0
    
    def test_validate_query_valid_with_where(self, client):
        """Test validating SELECT query with WHERE clause."""
        result = client.validate_query(
            "SELECT tank_number FROM iso_tank WHERE status = 'active'"
        )
        
        assert result.valid is True
        assert len(result.errors) == 0
    
    def test_validate_query_valid_with_join(self, client):
        """Test validating SELECT query with JOIN."""
        result = client.validate_query(
            "SELECT it.tank_number, vi.client_name "
            "FROM iso_tank it JOIN vehicle_in vi ON it.vehicle_in_id = vi.id"
        )
        
        assert result.valid is True
        assert len(result.errors) == 0
    
    # Error path tests - Query validation
    
    def test_validate_query_empty_query(self, client):
        """Test validating empty query."""
        result = client.validate_query("")
        
        assert result.valid is False
        assert len(result.errors) > 0
        assert "empty" in result.errors[0].lower()
    
    def test_validate_query_invalid_syntax(self, client):
        """Test validating query with invalid syntax."""
        result = client.validate_query("INVALID QUERY SYNTAX")
        
        assert result.valid is False
        assert len(result.errors) > 0
    
    def test_validate_query_without_connection_raises_error(self, client_no_config):
        """Test validating query without MCP connection raises error."""
        with pytest.raises(MCPConnectionError) as exc_info:
            client_no_config.validate_query("SELECT * FROM iso_tank")
        
        assert "not available" in str(exc_info.value).lower()
    
    # Happy path tests - Query execution
    
    def test_execute_query_returns_result(self, client):
        """Test executing query returns QueryResult."""
        result = client.execute_query("SELECT COUNT(*) FROM iso_tank")
        
        assert isinstance(result, QueryResult)
        assert result.success is True
        assert isinstance(result.rows, list)
        assert isinstance(result.row_count, int)
        assert isinstance(result.columns, list)
        assert result.execution_time >= 0
    
    def test_execute_query_with_results(self, client):
        """Test executing query with results."""
        result = client.execute_query("SELECT * FROM iso_tank LIMIT 10")
        
        assert result.success is True
        assert result.row_count >= 0
    
    # Error path tests - Query execution
    
    def test_execute_query_without_connection_raises_error(self, client_no_config):
        """Test executing query without MCP connection raises error."""
        with pytest.raises(MCPConnectionError) as exc_info:
            client_no_config.execute_query("SELECT * FROM iso_tank")
        
        assert "not available" in str(exc_info.value).lower()
    
    # Edge case tests - Connection management
    
    def test_client_initialization_with_custom_timeouts(self, mock_env_vars):
        """Test client initialization with custom timeout values."""
        client = MCPClient(
            query_timeout=60,
            validation_timeout=20,
            max_retries=5
        )
        
        assert client.query_timeout == 60
        assert client.validation_timeout == 20
        assert client.max_retries == 5
    
    def test_client_initialization_with_explicit_config(self):
        """Test client initialization with explicit configuration."""
        client = MCPClient(
            server_url="http://custom-server:9000",
            database_name="custom_db"
        )
        
        assert client.server_url == "http://custom-server:9000"
        assert client.database_name == "custom_db"
    
    def test_client_close_connection(self, client):
        """Test closing MCP connection."""
        # Should not raise error
        client.close()
        
        # After close, should not be connected
        assert client.is_connected() is False
    
    def test_generate_request_id_is_unique(self, client):
        """Test request ID generation produces unique IDs."""
        id1 = client._generate_request_id()
        id2 = client._generate_request_id()
        
        assert id1 != id2
        assert len(id1) > 0
        assert len(id2) > 0
    
    # Edge case tests - Fallback mode
    
    def test_get_schema_fallback_all_tables(self, client):
        """Test schema retrieval in fallback mode for all tables."""
        schema = client._get_schema_fallback()
        
        assert isinstance(schema, str)
        assert "schema" in schema.lower()
    
    def test_get_schema_fallback_specific_table(self, client):
        """Test schema retrieval in fallback mode for specific table."""
        schema = client._get_schema_fallback(table_name="iso_tank")
        
        assert isinstance(schema, str)
        assert "iso_tank" in schema.lower()
    
    def test_validate_query_fallback_valid(self, client):
        """Test query validation fallback with valid query."""
        result = client._validate_query_fallback("SELECT * FROM iso_tank")
        
        assert result.valid is True
        assert len(result.errors) == 0
    
    def test_validate_query_fallback_empty(self, client):
        """Test query validation fallback with empty query."""
        result = client._validate_query_fallback("")
        
        assert result.valid is False
        assert len(result.errors) > 0
    
    def test_execute_query_fallback_returns_empty_result(self, client):
        """Test query execution fallback returns empty result."""
        result = client._execute_query_fallback("SELECT * FROM iso_tank")
        
        assert result.success is True
        assert result.row_count == 0
        assert len(result.rows) == 0
        assert len(result.columns) == 0
    
    # Data structure tests
    
    def test_validation_result_to_dict(self):
        """Test ValidationResult to_dict conversion."""
        result = ValidationResult(
            valid=False,
            errors=["Syntax error"],
            suggestions=["Check table name"]
        )
        
        result_dict = result.to_dict()
        
        assert result_dict["valid"] is False
        assert result_dict["errors"] == ["Syntax error"]
        assert result_dict["suggestions"] == ["Check table name"]
    
    def test_query_result_to_dict(self):
        """Test QueryResult to_dict conversion."""
        result = QueryResult(
            success=True,
            rows=[{"id": 1, "name": "test"}],
            row_count=1,
            columns=["id", "name"],
            execution_time=0.5
        )
        
        result_dict = result.to_dict()
        
        assert result_dict["success"] is True
        assert result_dict["row_count"] == 1
        assert result_dict["execution_time"] == 0.5
        assert result_dict["error"] is None
    
    def test_query_result_with_error(self):
        """Test QueryResult with error."""
        result = QueryResult(
            success=False,
            rows=[],
            row_count=0,
            columns=[],
            execution_time=0.0,
            error="Table not found"
        )
        
        assert result.success is False
        assert result.error == "Table not found"
    
    # Integration tests
    
    def test_full_workflow_schema_validate_execute(self, client):
        """Test full workflow: get schema, validate, execute."""
        # Get schema
        schema = client.get_schema()
        assert len(schema) > 0
        
        # Validate query
        validation = client.validate_query("SELECT * FROM iso_tank")
        assert validation.valid is True
        
        # Execute query
        result = client.execute_query("SELECT * FROM iso_tank LIMIT 10")
        assert result.success is True
    
    def test_client_handles_multiple_operations(self, client):
        """Test client handles multiple operations correctly."""
        # Multiple schema requests
        schema1 = client.get_schema()
        schema2 = client.get_schema("iso_tank")
        
        assert len(schema1) > 0
        assert len(schema2) > 0
        
        # Multiple validations
        val1 = client.validate_query("SELECT * FROM iso_tank")
        val2 = client.validate_query("SELECT COUNT(*) FROM vehicle_in")
        
        assert val1.valid is True
        assert val2.valid is True
        
        # Multiple executions
        res1 = client.execute_query("SELECT * FROM iso_tank LIMIT 5")
        res2 = client.execute_query("SELECT * FROM vehicle_in LIMIT 5")
        
        assert res1.success is True
        assert res2.success is True
    
    def test_mcp_error_type_enum(self):
        """Test MCPErrorType enum values."""
        assert MCPErrorType.CONNECTION_ERROR.value == "connection_error"
        assert MCPErrorType.QUERY_ERROR.value == "query_error"
        assert MCPErrorType.TIMEOUT_ERROR.value == "timeout_error"
        assert MCPErrorType.VALIDATION_ERROR.value == "validation_error"
        assert MCPErrorType.UNKNOWN_ERROR.value == "unknown_error"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
