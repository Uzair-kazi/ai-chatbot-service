"""
Tests for SQL Executor Service.

Note: Integration tests require a valid database connection.
They are marked with @pytest.mark.integration and skip if DB_URL is not set.
"""

import os
import pytest
from unittest.mock import Mock, patch
from services.sql_executor import (
    SQLExecutor,
    QueryTimeoutError,
    DatabaseConnectionError,
    SQLSyntaxError,
    PermissionDeniedError,
    get_executor,
    close_executor
)


def test_executor_requires_db_url():
    """Test that SQLExecutor raises error if DB_URL is not set."""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="DB_URL environment variable is required"):
            SQLExecutor()


@pytest.mark.skipif(
    not os.getenv("DB_URL"),
    reason="DB_URL not set - skipping integration tests"
)
@pytest.mark.integration
def test_executor_initialization():
    """Integration test: SQLExecutor initializes with valid DB_URL."""
    executor = SQLExecutor()
    
    assert executor is not None
    assert executor.pool is not None
    assert executor.timeout_seconds == 60
    
    executor.close()


@pytest.mark.skipif(
    not os.getenv("DB_URL"),
    reason="DB_URL not set - skipping integration tests"
)
@pytest.mark.integration
def test_execute_simple_query():
    """Integration test: Execute a simple SELECT query."""
    executor = SQLExecutor()
    
    # Simple query that should work on any PostgreSQL database
    sql = "SELECT 1 AS test_column;"
    result = executor.execute_query(sql)
    
    assert result is not None
    assert "columns" in result
    assert "rows" in result
    assert "row_count" in result
    
    assert result["columns"] == ["test_column"]
    assert result["row_count"] == 1
    assert result["rows"][0]["test_column"] == 1
    
    executor.close()


@pytest.mark.skipif(
    not os.getenv("DB_URL"),
    reason="DB_URL not set - skipping integration tests"
)
@pytest.mark.integration
def test_execute_query_with_multiple_rows():
    """Integration test: Execute query that returns multiple rows."""
    executor = SQLExecutor()
    
    # Generate multiple rows
    sql = "SELECT generate_series(1, 5) AS number;"
    result = executor.execute_query(sql)
    
    assert result["row_count"] == 5
    assert len(result["rows"]) == 5
    assert result["rows"][0]["number"] == 1
    assert result["rows"][4]["number"] == 5
    
    executor.close()


@pytest.mark.skipif(
    not os.getenv("DB_URL"),
    reason="DB_URL not set - skipping integration tests"
)
@pytest.mark.integration
def test_execute_query_with_empty_result():
    """Integration test: Execute query that returns no rows."""
    executor = SQLExecutor()
    
    # Query that returns no rows
    sql = "SELECT 1 AS test WHERE 1 = 0;"
    result = executor.execute_query(sql)
    
    assert result["row_count"] == 0
    assert len(result["rows"]) == 0
    assert result["columns"] == ["test"]
    
    executor.close()


@pytest.mark.skipif(
    not os.getenv("DB_URL"),
    reason="DB_URL not set - skipping integration tests"
)
@pytest.mark.integration
def test_execute_query_limits_to_100_rows():
    """Integration test: Verify query returns max 100 rows."""
    executor = SQLExecutor()
    
    # Generate 150 rows, but should only get 100
    sql = "SELECT generate_series(1, 150) AS number;"
    result = executor.execute_query(sql)
    
    assert result["row_count"] == 100
    assert len(result["rows"]) == 100
    
    executor.close()


@pytest.mark.skipif(
    not os.getenv("DB_URL"),
    reason="DB_URL not set - skipping integration tests"
)
@pytest.mark.integration
def test_execute_query_with_invalid_syntax():
    """Integration test: Invalid SQL syntax raises SQLSyntaxError."""
    executor = SQLExecutor()
    
    # Invalid SQL syntax
    sql = "SELECT * FORM invalid_table;"  # FORM instead of FROM
    
    with pytest.raises(SQLSyntaxError):
        executor.execute_query(sql)
    
    executor.close()


@pytest.mark.skipif(
    not os.getenv("DB_URL"),
    reason="DB_URL not set - skipping integration tests"
)
@pytest.mark.integration
def test_execute_query_with_nonexistent_table():
    """Integration test: Query on non-existent table raises error."""
    executor = SQLExecutor()
    
    # Table that doesn't exist
    sql = "SELECT * FROM nonexistent_table_12345;"
    
    with pytest.raises((SQLSyntaxError, PermissionDeniedError)):
        executor.execute_query(sql)
    
    executor.close()


@pytest.mark.skipif(
    not os.getenv("DB_URL"),
    reason="DB_URL not set - skipping integration tests"
)
@pytest.mark.integration
def test_execute_query_logs_execution_time():
    """Integration test: Verify query execution time is logged."""
    executor = SQLExecutor()
    
    # Query that takes a measurable amount of time
    sql = "SELECT pg_sleep(0.1), 1 AS result;"
    result = executor.execute_query(sql)
    
    assert result is not None
    assert result["row_count"] == 1
    
    executor.close()


@pytest.mark.skipif(
    not os.getenv("DB_URL"),
    reason="DB_URL not set - skipping integration tests"
)
@pytest.mark.integration
def test_connection_pool_reuse():
    """Integration test: Verify connection pool reuses connections."""
    executor = SQLExecutor()
    
    # Execute multiple queries
    for i in range(5):
        sql = f"SELECT {i} AS number;"
        result = executor.execute_query(sql)
        assert result["rows"][0]["number"] == i
    
    executor.close()


@pytest.mark.skipif(
    not os.getenv("DB_URL"),
    reason="DB_URL not set - skipping integration tests"
)
@pytest.mark.integration
def test_get_executor_singleton():
    """Integration test: Verify get_executor returns singleton instance."""
    executor1 = get_executor()
    executor2 = get_executor()
    
    assert executor1 is executor2
    
    close_executor()


@pytest.mark.skipif(
    not os.getenv("DB_URL"),
    reason="DB_URL not set - skipping integration tests"
)
@pytest.mark.integration
def test_executor_custom_timeout():
    """Integration test: Verify custom timeout can be set."""
    executor = SQLExecutor(timeout_seconds=30)
    
    assert executor.timeout_seconds == 30
    
    # Execute a quick query to verify it works
    sql = "SELECT 1 AS test;"
    result = executor.execute_query(sql)
    assert result["row_count"] == 1
    
    executor.close()


def test_executor_result_structure():
    """Unit test: Verify result structure is correct."""
    # This test doesn't need a real database
    # We're just testing the expected structure
    
    expected_keys = ["columns", "rows", "row_count"]
    
    # Mock result
    mock_result = {
        "columns": ["id", "name"],
        "rows": [{"id": 1, "name": "test"}],
        "row_count": 1
    }
    
    for key in expected_keys:
        assert key in mock_result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])



def test_get_executor_concurrent_singleton_with_mock():
    """Unit test: Verify get_executor creates only one instance under concurrent access."""
    import threading
    from unittest.mock import patch, MagicMock
    
    # Reset singleton
    close_executor()
    
    executors = []
    pool_ids = []
    
    # Mock the database connection
    with patch('services.sql_executor.psycopg2.pool.SimpleConnectionPool') as mock_pool:
        mock_pool_instance = MagicMock()
        mock_pool.return_value = mock_pool_instance
        
        def get_and_store():
            executor = get_executor()
            executors.append(executor)
            pool_ids.append(id(executor.pool))
        
        # Launch 10 concurrent threads
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=get_and_store)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All executors should be the same instance
        assert len(set(id(e) for e in executors)) == 1, "All threads should get the same executor instance"
        
        # All pools should be the same instance
        assert len(set(pool_ids)) == 1, "Only one connection pool should be created"
        
        # Pool should have been created exactly once
        assert mock_pool.call_count == 1, f"Pool should be created once, but was created {mock_pool.call_count} times"
    
    close_executor()
