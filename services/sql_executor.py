"""
SQL Executor Service

This module executes validated SQL queries against the PostgreSQL database
with timeout protection and comprehensive error handling.
"""

import os
import time
import threading
from typing import Dict, List, Any
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from config.logging_config import get_logger

# Load environment variables
load_dotenv()

logger = get_logger(__name__)


# Module-level lock for singleton initialization
_executor_lock = threading.Lock()


# Custom exceptions
class QueryTimeoutError(Exception):
    """Raised when query execution exceeds timeout."""
    pass


class DatabaseConnectionError(Exception):
    """Raised when database connection fails."""
    pass


class SQLSyntaxError(Exception):
    """Raised when SQL syntax is invalid."""
    pass


class PermissionDeniedError(Exception):
    """Raised when permission is denied for a query."""
    pass


class SQLExecutor:
    """Executes SQL queries with timeout and error handling."""
    
    def __init__(self, db_url: str = None, timeout_seconds: int = 60):
        """
        Initialize the SQL executor.
        
        Args:
            db_url: PostgreSQL connection string. If None, reads from DB_URL env var.
            timeout_seconds: Query timeout in seconds (default: 60)
        """
        self.db_url = db_url or os.getenv("DB_URL")
        if not self.db_url:
            raise ValueError("DB_URL environment variable is required")
        
        self.timeout_seconds = timeout_seconds
        
        # Create connection pool (min=1, max=10)
        try:
            self.pool = psycopg2.pool.SimpleConnectionPool(
                1, 10, self.db_url
            )
            logger.info("SQL executor initialized with connection pool")
        except psycopg2.Error as e:
            raise DatabaseConnectionError(f"Failed to connect to database: {e}")
    
    def execute_query(self, sql: str) -> Dict[str, Any]:
        """
        Execute SQL query and return structured results.
        
        Args:
            sql: SQL query to execute (must be validated before calling this)
            
        Returns:
            Dictionary with:
            - columns: List of column names
            - rows: List of row dictionaries (up to 100 rows)
            - row_count: Total number of rows returned
            
        Raises:
            QueryTimeoutError: If query exceeds timeout
            DatabaseConnectionError: If database connection fails
            SQLSyntaxError: If SQL syntax is invalid
            PermissionDeniedError: If permission is denied
        """
        conn = None
        start_time = time.time()
        
        try:
            # Get connection from pool
            conn = self.pool.getconn()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Set statement timeout
            cursor.execute(f"SET statement_timeout = '{self.timeout_seconds}s';")
            
            logger.info(f"Executing SQL: {sql}")
            
            # Execute the query
            cursor.execute(sql)
            
            # Fetch up to 100 rows
            rows = cursor.fetchmany(100)
            
            # Get column names
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            
            # Convert rows to list of dicts
            rows_list = [dict(row) for row in rows]
            
            # Get total row count
            row_count = len(rows_list)
            
            execution_time = time.time() - start_time
            logger.info(f"Query executed successfully in {execution_time:.2f}s, returned {row_count} rows")
            
            cursor.close()
            
            return {
                "columns": columns,
                "rows": rows_list,
                "row_count": row_count
            }
            
        except psycopg2.extensions.QueryCanceledError as e:
            execution_time = time.time() - start_time
            logger.error(f"Query timeout after {execution_time:.2f}s: {e}")
            raise QueryTimeoutError(f"Query exceeded {self.timeout_seconds} second timeout")
            
        except psycopg2.errors.SyntaxError as e:
            logger.error(f"SQL syntax error: {e}")
            raise SQLSyntaxError(f"Invalid SQL syntax: {e}")
            
        except psycopg2.errors.InsufficientPrivilege as e:
            logger.error(f"Permission denied: {e}")
            raise PermissionDeniedError(f"Access denied: {e}")
            
        except psycopg2.OperationalError as e:
            logger.error(f"Database connection error: {e}")
            raise DatabaseConnectionError(f"Database connection failed: {e}")
            
        except psycopg2.Error as e:
            logger.error(f"Database error: {e}")
            raise DatabaseConnectionError(f"Database error: {e}")
            
        except Exception as e:
            logger.error(f"Unexpected error during query execution: {e}")
            raise
            
        finally:
            # Always return connection to pool
            if conn:
                self.pool.putconn(conn)
                logger.debug("Connection returned to pool")
    
    def close(self):
        """Close the connection pool."""
        if hasattr(self, 'pool') and self.pool:
            self.pool.closeall()
            logger.info("Connection pool closed")


# Global instance for easy import
_executor: SQLExecutor = None


def get_executor() -> SQLExecutor:
    """
    Get the global SQL executor instance.
    
    Thread-safe singleton implementation using double-checked locking pattern.
    This ensures only one connection pool is created even under concurrent access.
    
    Returns:
        SQLExecutor instance
        
    Raises:
        ValueError: If DB_URL environment variable is not set
        DatabaseConnectionError: If database connection fails
    """
    global _executor
    
    # First check without lock (fast path)
    if _executor is not None:
        return _executor
    
    # Acquire lock for initialization
    with _executor_lock:
        # Double-check after acquiring lock
        if _executor is None:
            _executor = SQLExecutor()
    
    return _executor


def close_executor():
    """Close the global SQL executor connection pool."""
    global _executor
    
    if _executor is not None:
        _executor.close()
        _executor = None
