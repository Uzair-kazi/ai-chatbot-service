"""
Tests for database schema introspection service.

Note: These tests require a running PostgreSQL database with the tank-depot schema.
Set DB_URL environment variable before running tests.
"""

import os
import pytest
from services.schema import SchemaIntrospector, get_database_schema


def test_schema_introspector_requires_db_url():
    """Test that SchemaIntrospector raises error if DB_URL is not set."""
    # Save original DB_URL
    original_db_url = os.getenv("DB_URL")
    
    try:
        # Temporarily unset DB_URL
        if "DB_URL" in os.environ:
            del os.environ["DB_URL"]
        
        with pytest.raises(ValueError, match="DB_URL environment variable is required"):
            SchemaIntrospector()
    finally:
        # Restore original DB_URL
        if original_db_url:
            os.environ["DB_URL"] = original_db_url


@pytest.mark.skipif(
    not os.getenv("DB_URL"),
    reason="DB_URL not set - skipping integration tests"
)
def test_get_database_schema_returns_non_empty_string():
    """Test that get_database_schema() returns a non-empty string."""
    schema = get_database_schema()
    
    assert isinstance(schema, str)
    assert len(schema) > 0
    assert "Database Schema:" in schema


@pytest.mark.skipif(
    not os.getenv("DB_URL"),
    reason="DB_URL not set - skipping integration tests"
)
def test_schema_includes_expected_tables():
    """Test that schema description includes expected tables from Prisma schema."""
    schema = get_database_schema()
    
    # These tables should exist based on the Prisma schema
    expected_tables = ["iso_tank", "service_tank", "suraksha_tanker"]
    
    for table in expected_tables:
        assert f"Table: {table}" in schema, f"Expected table '{table}' not found in schema"


@pytest.mark.skipif(
    not os.getenv("DB_URL"),
    reason="DB_URL not set - skipping integration tests"
)
def test_schema_includes_column_information():
    """Test that schema description includes column names and data types."""
    schema = get_database_schema()
    
    # Check for column information (iso_tank table columns)
    assert "id:" in schema
    assert "tank_number:" in schema or "tankNumber:" in schema
    
    # Check for data type information
    assert "uuid" in schema or "character varying" in schema or "text" in schema


@pytest.mark.skipif(
    not os.getenv("DB_URL"),
    reason="DB_URL not set - skipping integration tests"
)
def test_schema_includes_foreign_key_relationships():
    """Test that schema description includes foreign key relationships."""
    schema = get_database_schema()
    
    # Check for foreign key notation
    assert "foreign key ->" in schema


@pytest.mark.skipif(
    not os.getenv("DB_URL"),
    reason="DB_URL not set - skipping integration tests"
)
def test_schema_includes_primary_keys():
    """Test that schema description includes primary key annotations."""
    schema = get_database_schema()
    
    # Check for primary key notation
    assert "primary key" in schema


@pytest.mark.skipif(
    not os.getenv("DB_URL"),
    reason="DB_URL not set - skipping integration tests"
)
def test_schema_introspector_handles_connection_errors():
    """Test that SchemaIntrospector raises ConnectionError for invalid DB URL."""
    invalid_db_url = "postgresql://invalid:invalid@localhost:9999/nonexistent"
    
    with pytest.raises(ConnectionError, match="Failed to connect to database"):
        SchemaIntrospector(db_url=invalid_db_url)


@pytest.mark.skipif(
    not os.getenv("DB_URL"),
    reason="DB_URL not set - skipping integration tests"
)
def test_schema_introspector_can_be_closed():
    """Test that SchemaIntrospector connection pool can be closed."""
    introspector = SchemaIntrospector()
    
    # Get schema once
    schema = introspector.get_database_schema()
    assert len(schema) > 0
    
    # Close the pool
    introspector.close()
    
    # This should work without errors
    assert True


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
