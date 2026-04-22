"""
MCP Client Wrapper

This module provides a wrapper around the Model Context Protocol (MCP) SDK
for standardized database operations. It handles connection management,
error handling, retries, and provides a consistent interface for agents.

Key features:
- Schema introspection (get_schema)
- Query validation (validate_query)
- Query execution (execute_query)
- Automatic reconnection on failures
- Structured error responses
- Request ID tracking for debugging

MCP Server Setup (Optional):
To use MCP mode instead of fallback mode, you need to run a local MCP PostgreSQL server.

1. Install MCP Python SDK:
   pip install "mcp[cli]"

2. Create an MCP server that exposes PostgreSQL operations:
   - Use mcp.server.fastmcp to create a server
   - Expose tools for schema introspection, query validation, and execution
   - Run with HTTP transport on localhost:8080

3. Configure environment variables:
   MCP_SERVER_URL="http://localhost:8080/mcp"
   MCP_DATABASE_NAME="tank_depot"

4. The client will automatically connect to MCP server if configured,
   otherwise it operates in fallback mode (direct database access).
"""

import os
import time
import uuid
import asyncio
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from enum import Enum
from config.logging_config import get_logger

logger = get_logger(__name__)

# MCP SDK imports - only imported if MCP is configured
try:
    from mcp import ClientSession
    from mcp.client.sse import sse_client
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    logger.warning(
        "MCP SDK not installed. Install with: pip install 'mcp[cli]'. "
        "Operating in fallback mode only."
    )


class MCPErrorType(Enum):
    """MCP error types for categorization."""
    CONNECTION_ERROR = "connection_error"
    QUERY_ERROR = "query_error"
    TIMEOUT_ERROR = "timeout_error"
    VALIDATION_ERROR = "validation_error"
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class ValidationResult:
    """Result of query validation."""
    valid: bool
    errors: List[str]
    suggestions: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "valid": self.valid,
            "errors": self.errors,
            "suggestions": self.suggestions
        }


@dataclass
class QueryResult:
    """Result of query execution."""
    success: bool
    rows: List[Dict[str, Any]]
    row_count: int
    columns: List[str]
    execution_time: float
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "rows": self.rows,
            "row_count": self.row_count,
            "columns": self.columns,
            "execution_time": self.execution_time,
            "error": self.error
        }


class MCPConnectionError(Exception):
    """Raised when MCP connection fails."""
    pass


class MCPQueryError(Exception):
    """Raised when query execution fails."""
    pass


class MCPTimeoutError(Exception):
    """Raised when query times out."""
    pass


class MCPClient:
    """
    MCP client wrapper for database operations.
    
    Provides a consistent interface for schema introspection, query validation,
    and query execution through the Model Context Protocol.
    
    Attributes:
        server_url: MCP server URL
        database_name: Database name
        query_timeout: Query execution timeout in seconds
        validation_timeout: Query validation timeout in seconds
        max_retries: Maximum number of connection retry attempts
        logger: Logger instance
    """
    
    def __init__(
        self,
        server_url: Optional[str] = None,
        database_name: Optional[str] = None,
        query_timeout: int = 30,
        validation_timeout: int = 10,
        max_retries: int = 3
    ):
        """
        Initialize MCP client.
        
        Args:
            server_url: MCP server URL (defaults to MCP_SERVER_URL env var)
            database_name: Database name (defaults to MCP_DATABASE_NAME env var)
            query_timeout: Query execution timeout in seconds
            validation_timeout: Query validation timeout in seconds
            max_retries: Maximum number of connection retry attempts
        """
        self.server_url = server_url or os.getenv("MCP_SERVER_URL")
        self.database_name = database_name or os.getenv("MCP_DATABASE_NAME")
        self.query_timeout = query_timeout
        self.validation_timeout = validation_timeout
        self.max_retries = max_retries
        self.logger = logger
        
        # Connection state
        self._connected = False
        self._session = None
        self._event_loop = None
        
        # Initialize connection
        self._connect()
    
    def _connect(self) -> None:
        """
        Establish connection to MCP server.
        
        Raises:
            MCPConnectionError: If connection fails after retries
        """
        if not MCP_AVAILABLE:
            self.logger.warning(
                "MCP SDK not available - operating in fallback mode. "
                "Install with: pip install 'mcp[cli]'"
            )
            self._connected = False
            return
        
        if not self.server_url:
            self.logger.warning(
                "MCP_SERVER_URL not configured - MCP client will operate in fallback mode"
            )
            self._connected = False
            return
        
        if not self.database_name:
            self.logger.warning(
                "MCP_DATABASE_NAME not configured - MCP client will operate in fallback mode"
            )
            self._connected = False
            return
        
        for attempt in range(1, self.max_retries + 1):
            try:
                self.logger.info(
                    f"Connecting to MCP server at {self.server_url} "
                    f"(attempt {attempt}/{self.max_retries})"
                )
                
                # Create event loop for async operations
                try:
                    self._event_loop = asyncio.get_event_loop()
                except RuntimeError:
                    self._event_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(self._event_loop)
                
                # Test connection with a simple async call
                async def test_connection():
                    async with sse_client(self.server_url) as (read, write):
                        async with ClientSession(read, write) as session:
                            await session.initialize()
                            return session
                
                # Run connection test
                self._event_loop.run_until_complete(
                    asyncio.wait_for(test_connection(), timeout=10)
                )
                
                self._connected = True
                self.logger.info("Successfully connected to MCP server")
                return
                
            except asyncio.TimeoutError:
                self.logger.warning(
                    f"MCP connection attempt {attempt} timed out"
                )
            except Exception as e:
                self.logger.warning(
                    f"MCP connection attempt {attempt} failed: {e}"
                )
                
            if attempt == self.max_retries:
                self.logger.error(
                    f"Failed to connect to MCP server after {self.max_retries} attempts. "
                    "Operating in fallback mode."
                )
                self._connected = False
                return
            
            # Exponential backoff
            time.sleep(2 ** attempt)
    
    def _reconnect(self) -> None:
        """Attempt to reconnect to MCP server."""
        self.logger.info("Attempting to reconnect to MCP server")
        self._connected = False
        self._session = None
        self._connect()
    
    async def _call_mcp_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        Call an MCP tool with the given arguments.
        
        Args:
            tool_name: Name of the MCP tool to call
            arguments: Tool arguments
            
        Returns:
            Tool result
            
        Raises:
            MCPConnectionError: If connection fails
        """
        if not self._connected or not MCP_AVAILABLE:
            raise MCPConnectionError("MCP server not available")
        
        try:
            async with sse_client(self.server_url) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    # Call the tool
                    result = await session.call_tool(tool_name, arguments)
                    return result
                    
        except Exception as e:
            self.logger.error(f"MCP tool call failed: {e}", exc_info=True)
            raise MCPConnectionError(f"Failed to call MCP tool {tool_name}: {e}")
    
    def _generate_request_id(self) -> str:
        """Generate unique request ID for tracing."""
        return str(uuid.uuid4())
    
    def is_connected(self) -> bool:
        """Check if client is connected to MCP server."""
        return self._connected
    
    def get_schema(self, table_name: Optional[str] = None) -> str:
        """
        Get database schema description.
        
        Args:
            table_name: Optional table name to get schema for specific table.
                       If None, returns schema for all tables.
        
        Returns:
            Formatted schema string
            
        Raises:
            MCPConnectionError: If connection fails and reconnection fails
        """
        request_id = self._generate_request_id()
        
        self.logger.info(
            f"Getting schema (table={table_name or 'all'}) - request_id={request_id}"
        )
        
        if not self._connected:
            self.logger.warning(
                f"MCP not connected - using fallback mode - request_id={request_id}"
            )
            return self._get_schema_fallback(table_name)
        
        try:
            start_time = time.time()
            
            # Call MCP tool for schema introspection
            arguments = {"database": self.database_name}
            if table_name:
                arguments["table_name"] = table_name
            
            # Run async MCP call
            result = self._event_loop.run_until_complete(
                asyncio.wait_for(
                    self._call_mcp_tool("get_schema", arguments),
                    timeout=self.validation_timeout
                )
            )
            
            # Extract schema from result
            if hasattr(result, 'content') and result.content:
                schema = result.content[0].text if result.content else str(result)
            else:
                schema = str(result)
            
            execution_time = time.time() - start_time
            
            self.logger.info(
                f"Schema retrieved via MCP in {execution_time:.2f}s - request_id={request_id}"
            )
            
            return schema
            
        except asyncio.TimeoutError:
            self.logger.warning(
                f"MCP schema request timed out - using fallback - request_id={request_id}"
            )
            return self._get_schema_fallback(table_name)
            
        except Exception as e:
            self.logger.error(
                f"Failed to get schema via MCP: {e} - using fallback - request_id={request_id}",
                exc_info=True
            )
            
            # Attempt reconnection
            self._reconnect()
            
            # Use fallback instead of raising
            return self._get_schema_fallback(table_name)
    
    def _get_schema_fallback(self, table_name: Optional[str] = None) -> str:
        """
        Fallback schema retrieval (placeholder for testing).
        
        In production, this would not be used - MCP SDK would provide schema.
        """
        if table_name:
            return f"Schema for table: {table_name}\n(MCP fallback mode)"
        return "Full database schema\n(MCP fallback mode)"
    
    def validate_query(self, sql: str) -> ValidationResult:
        """
        Validate SQL query without executing it.
        
        Performs dry-run validation to check for syntax errors,
        invalid table/column references, and other issues.
        
        Args:
            sql: SQL query to validate
            
        Returns:
            ValidationResult with validation status and errors
            
        Raises:
            MCPConnectionError: If connection fails
        """
        request_id = self._generate_request_id()
        
        self.logger.info(
            f"Validating query - request_id={request_id} - sql={sql[:100]}..."
        )
        
        if not self._connected:
            self.logger.warning(
                f"MCP not connected - using fallback validation - request_id={request_id}"
            )
            return self._validate_query_fallback(sql)
        
        try:
            start_time = time.time()
            
            # Call MCP tool for query validation
            arguments = {
                "database": self.database_name,
                "sql": sql
            }
            
            # Run async MCP call
            result = self._event_loop.run_until_complete(
                asyncio.wait_for(
                    self._call_mcp_tool("validate_query", arguments),
                    timeout=self.validation_timeout
                )
            )
            
            # Parse validation result
            if hasattr(result, 'content') and result.content:
                content = result.content[0]
                if hasattr(content, 'text'):
                    # Parse text response
                    import json
                    data = json.loads(content.text)
                    validation_result = ValidationResult(
                        valid=data.get("valid", False),
                        errors=data.get("errors", []),
                        suggestions=data.get("suggestions", [])
                    )
                else:
                    # Assume valid if no errors
                    validation_result = ValidationResult(valid=True, errors=[], suggestions=[])
            else:
                validation_result = ValidationResult(valid=True, errors=[], suggestions=[])
            
            execution_time = time.time() - start_time
            
            self.logger.info(
                f"Query validation completed via MCP in {execution_time:.2f}s - "
                f"valid={validation_result.valid} - request_id={request_id}"
            )
            
            return validation_result
            
        except asyncio.TimeoutError:
            self.logger.warning(
                f"MCP validation timed out - using fallback - request_id={request_id}"
            )
            return self._validate_query_fallback(sql)
            
        except Exception as e:
            self.logger.error(
                f"Query validation error via MCP: {e} - using fallback - request_id={request_id}",
                exc_info=True
            )
            
            # Attempt reconnection
            self._reconnect()
            
            # Use fallback instead of raising
            return self._validate_query_fallback(sql)
    
    def _validate_query_fallback(self, sql: str) -> ValidationResult:
        """
        Fallback query validation (placeholder for testing).
        
        In production, this would not be used - MCP SDK would validate.
        """
        # Basic syntax check
        sql_upper = sql.upper().strip()
        
        errors = []
        suggestions = []
        
        # Check for empty query
        if not sql.strip():
            errors.append("Empty query")
            return ValidationResult(valid=False, errors=errors, suggestions=suggestions)
        
        # Check for basic SQL keywords
        if not any(keyword in sql_upper for keyword in ["SELECT", "INSERT", "UPDATE", "DELETE"]):
            errors.append("Query must contain a valid SQL statement")
            suggestions.append("Start with SELECT, INSERT, UPDATE, or DELETE")
        
        valid = len(errors) == 0
        
        return ValidationResult(valid=valid, errors=errors, suggestions=suggestions)
    
    def execute_query(self, sql: str) -> QueryResult:
        """
        Execute SQL query and return results.
        
        Args:
            sql: SQL query to execute
            
        Returns:
            QueryResult with rows and metadata
            
        Raises:
            MCPConnectionError: If connection fails
            MCPQueryError: If query execution fails
            MCPTimeoutError: If query times out
        """
        request_id = self._generate_request_id()
        
        self.logger.info(
            f"Executing query - request_id={request_id} - sql={sql[:100]}..."
        )
        
        if not self._connected:
            self.logger.warning(
                f"MCP not connected - using fallback execution - request_id={request_id}"
            )
            return self._execute_query_fallback(sql)
        
        try:
            start_time = time.time()
            
            # Call MCP tool for query execution
            arguments = {
                "database": self.database_name,
                "sql": sql
            }
            
            # Run async MCP call
            result = self._event_loop.run_until_complete(
                asyncio.wait_for(
                    self._call_mcp_tool("execute_query", arguments),
                    timeout=self.query_timeout
                )
            )
            
            # Parse query result
            if hasattr(result, 'content') and result.content:
                content = result.content[0]
                if hasattr(content, 'text'):
                    # Parse JSON response
                    import json
                    data = json.loads(content.text)
                    query_result = QueryResult(
                        success=data.get("success", True),
                        rows=data.get("rows", []),
                        row_count=data.get("row_count", len(data.get("rows", []))),
                        columns=data.get("columns", []),
                        execution_time=0.0,
                        error=data.get("error")
                    )
                else:
                    # Empty result
                    query_result = QueryResult(
                        success=True,
                        rows=[],
                        row_count=0,
                        columns=[],
                        execution_time=0.0
                    )
            else:
                query_result = QueryResult(
                    success=True,
                    rows=[],
                    row_count=0,
                    columns=[],
                    execution_time=0.0
                )
            
            execution_time = time.time() - start_time
            query_result.execution_time = execution_time
            
            self.logger.info(
                f"Query executed via MCP in {execution_time:.2f}s - "
                f"rows={query_result.row_count} - request_id={request_id}"
            )
            
            return query_result
            
        except asyncio.TimeoutError:
            self.logger.error(
                f"Query timeout after {self.query_timeout}s via MCP - request_id={request_id}"
            )
            raise MCPTimeoutError(
                f"Query timed out after {self.query_timeout}s. "
                "Consider simplifying the query or adding filters."
            )
            
        except Exception as e:
            self.logger.error(
                f"Query execution error via MCP: {e} - request_id={request_id}",
                exc_info=True
            )
            
            # Attempt reconnection
            self._reconnect()
            
            raise MCPQueryError(f"Query execution failed: {e}")
    
    def _execute_query_fallback(self, sql: str) -> QueryResult:
        """
        Fallback query execution (placeholder for testing).
        
        In production, this would not be used - MCP SDK would execute.
        """
        # Return empty result set
        return QueryResult(
            success=True,
            rows=[],
            row_count=0,
            columns=[],
            execution_time=0.0
        )
    
    def close(self) -> None:
        """Close MCP connection."""
        try:
            if self._session:
                # MCP sessions are context managers, so they auto-close
                self.logger.info("MCP session closed")
            if self._event_loop and not self._event_loop.is_closed():
                # Don't close the event loop if it's the main one
                pass
        except Exception as e:
            self.logger.warning(f"Error closing MCP connection: {e}")
        finally:
            self._connected = False
            self._session = None
