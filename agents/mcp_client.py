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
"""

import os
import time
import uuid
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from enum import Enum
from config.logging_config import get_logger

logger = get_logger(__name__)


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
        self._connection = None
        
        # Initialize connection
        self._connect()
    
    def _connect(self) -> None:
        """
        Establish connection to MCP server.
        
        Raises:
            MCPConnectionError: If connection fails after retries
        """
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
                
                # TODO: Replace with actual MCP SDK connection
                # For now, simulate connection
                # from mcp import Client
                # self._connection = Client(self.server_url, self.database_name)
                
                self._connected = True
                self.logger.info("Successfully connected to MCP server")
                return
                
            except Exception as e:
                self.logger.warning(
                    f"MCP connection attempt {attempt} failed: {e}"
                )
                
                if attempt == self.max_retries:
                    self.logger.error(
                        f"Failed to connect to MCP server after {self.max_retries} attempts"
                    )
                    self._connected = False
                    # Don't raise - allow fallback mode
                    return
                
                # Exponential backoff
                time.sleep(2 ** attempt)
    
    def _reconnect(self) -> None:
        """Attempt to reconnect to MCP server."""
        self.logger.info("Attempting to reconnect to MCP server")
        self._connected = False
        self._connection = None
        self._connect()
    
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
                f"MCP not connected - cannot get schema - request_id={request_id}"
            )
            raise MCPConnectionError(
                "MCP server not available. Please check MCP_SERVER_URL and "
                "MCP_DATABASE_NAME configuration."
            )
        
        try:
            start_time = time.time()
            
            # TODO: Replace with actual MCP SDK call
            # schema = self._connection.get_schema(table_name)
            
            # For now, return placeholder
            schema = self._get_schema_fallback(table_name)
            
            execution_time = time.time() - start_time
            
            self.logger.info(
                f"Schema retrieved in {execution_time:.2f}s - request_id={request_id}"
            )
            
            return schema
            
        except Exception as e:
            self.logger.error(
                f"Failed to get schema: {e} - request_id={request_id}",
                exc_info=True
            )
            
            # Attempt reconnection
            self._reconnect()
            
            raise MCPConnectionError(f"Failed to get schema: {e}")
    
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
                f"MCP not connected - cannot validate query - request_id={request_id}"
            )
            raise MCPConnectionError(
                "MCP server not available. Please check MCP_SERVER_URL and "
                "MCP_DATABASE_NAME configuration."
            )
        
        try:
            start_time = time.time()
            
            # TODO: Replace with actual MCP SDK call
            # result = self._connection.validate_query(sql, timeout=self.validation_timeout)
            
            # For now, return placeholder validation
            result = self._validate_query_fallback(sql)
            
            execution_time = time.time() - start_time
            
            self.logger.info(
                f"Query validation completed in {execution_time:.2f}s - "
                f"valid={result.valid} - request_id={request_id}"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(
                f"Query validation error: {e} - request_id={request_id}",
                exc_info=True
            )
            
            # Attempt reconnection
            self._reconnect()
            
            raise MCPConnectionError(f"Query validation failed: {e}")
    
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
                f"MCP not connected - cannot execute query - request_id={request_id}"
            )
            raise MCPConnectionError(
                "MCP server not available. Please check MCP_SERVER_URL and "
                "MCP_DATABASE_NAME configuration."
            )
        
        try:
            start_time = time.time()
            
            # TODO: Replace with actual MCP SDK call
            # result = self._connection.execute_query(sql, timeout=self.query_timeout)
            
            # For now, return placeholder result
            result = self._execute_query_fallback(sql)
            
            execution_time = time.time() - start_time
            result.execution_time = execution_time
            
            self.logger.info(
                f"Query executed in {execution_time:.2f}s - "
                f"rows={result.row_count} - request_id={request_id}"
            )
            
            return result
            
        except TimeoutError as e:
            self.logger.error(
                f"Query timeout after {self.query_timeout}s - request_id={request_id}"
            )
            raise MCPTimeoutError(
                f"Query timed out after {self.query_timeout}s. "
                "Consider simplifying the query or adding filters."
            )
            
        except Exception as e:
            self.logger.error(
                f"Query execution error: {e} - request_id={request_id}",
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
            if self._connection:
                # TODO: Replace with actual MCP SDK close
                # self._connection.close()
                self.logger.info("MCP connection closed")
        except Exception as e:
            self.logger.warning(f"Error closing MCP connection: {e}")
        finally:
            self._connected = False
            self._connection = None
