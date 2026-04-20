"""
Tests for SQL Validator Service.
"""

import pytest
from services.sql_validator import SQLValidator


# Mock schema for testing
MOCK_SCHEMA = """
Database Schema:
================================================================================

Table: iso_tank
--------------------------------------------------------------------------------
  - id: uuid (primary key)
  - tank_number: character varying
  - iso_tank_status: character varying
  - vehicle_in_id: uuid (foreign key -> vehicle_in.id)
  - created_at: timestamp with time zone (not null)
  - updated_at: timestamp with time zone (not null)

Table: service_tank
--------------------------------------------------------------------------------
  - id: uuid (primary key)
  - tank_number: character varying
  - service_tank_status: character varying (not null)
  - created_at: timestamp with time zone (not null)

Table: vehicle_in
--------------------------------------------------------------------------------
  - id: uuid (primary key)
  - vehicle_number: character varying
  - created_at: timestamp with time zone (not null)
"""


def test_validator_initialization():
    """Test that SQLValidator initializes correctly."""
    validator = SQLValidator()
    assert validator is not None


# ============================================================================
# Pre-Validation Tests (Unit 3)
# ============================================================================

def test_validate_references_with_valid_sql():
    """Test that valid SQL with existing tables/columns passes validation."""
    validator = SQLValidator()
    
    sql = "SELECT tank_number, iso_tank_status FROM iso_tank WHERE id = '123';"
    is_valid, error = validator.validate_references(sql, MOCK_SCHEMA)
    
    assert is_valid is True
    assert error == ""


def test_validate_references_with_table_alias():
    """Test that SQL with table aliases validates correctly."""
    validator = SQLValidator()
    
    sql = "SELECT t.tank_number FROM iso_tank AS t WHERE t.id = '123';"
    is_valid, error = validator.validate_references(sql, MOCK_SCHEMA)
    
    assert is_valid is True
    assert error == ""


def test_validate_references_with_qualified_columns():
    """Test that SQL with qualified column names validates correctly."""
    validator = SQLValidator()
    
    sql = "SELECT iso_tank.tank_number, iso_tank.iso_tank_status FROM iso_tank;"
    is_valid, error = validator.validate_references(sql, MOCK_SCHEMA)
    
    assert is_valid is True
    assert error == ""


def test_validate_references_with_aggregate_functions():
    """Test that SQL with aggregate functions validates correctly."""
    validator = SQLValidator()
    
    # COUNT(*)
    sql = "SELECT COUNT(*) FROM iso_tank;"
    is_valid, error = validator.validate_references(sql, MOCK_SCHEMA)
    assert is_valid is True
    
    # SUM(column)
    sql = "SELECT SUM(id) FROM iso_tank;"
    is_valid, error = validator.validate_references(sql, MOCK_SCHEMA)
    assert is_valid is True


def test_validate_references_with_sql_functions():
    """Test that SQL functions are skipped during validation."""
    validator = SQLValidator()
    
    sql = "SELECT tank_number, CURRENT_DATE FROM iso_tank WHERE created_at >= DATE_TRUNC('month', CURRENT_DATE);"
    is_valid, error = validator.validate_references(sql, MOCK_SCHEMA)
    
    assert is_valid is True
    assert error == ""


def test_validate_references_with_nonexistent_table():
    """Test that SQL with non-existent table fails validation."""
    validator = SQLValidator()
    
    sql = "SELECT * FROM orders WHERE id = '123';"
    is_valid, error = validator.validate_references(sql, MOCK_SCHEMA)
    
    assert is_valid is False
    assert "Table 'orders' does not exist" in error


def test_validate_references_with_nonexistent_column():
    """Test that SQL with non-existent column fails validation."""
    validator = SQLValidator()
    
    sql = "SELECT invalid_column FROM iso_tank;"
    is_valid, error = validator.validate_references(sql, MOCK_SCHEMA)
    
    assert is_valid is False
    assert "Column 'invalid_column' does not exist" in error


def test_validate_references_with_empty_sql():
    """Test that empty SQL fails validation."""
    validator = SQLValidator()
    
    is_valid, error = validator.validate_references("", MOCK_SCHEMA)
    assert is_valid is False
    assert "SQL cannot be empty" in error
    
    is_valid, error = validator.validate_references("   ", MOCK_SCHEMA)
    assert is_valid is False
    assert "SQL cannot be empty" in error


def test_validate_references_with_join():
    """Test that SQL with JOIN validates correctly."""
    validator = SQLValidator()
    
    sql = """
        SELECT it.tank_number, vi.vehicle_number 
        FROM iso_tank it 
        JOIN vehicle_in vi ON it.vehicle_in_id = vi.id;
    """
    is_valid, error = validator.validate_references(sql, MOCK_SCHEMA)
    
    assert is_valid is True
    assert error == ""


# ============================================================================
# Safety Guard Tests (Unit 4)
# ============================================================================

def test_check_safety_with_valid_select():
    """Test that valid SELECT query passes safety check."""
    validator = SQLValidator()
    
    sql = "SELECT * FROM iso_tank WHERE iso_tank_status = 'IN';"
    is_safe, error = validator.check_safety(sql)
    
    assert is_safe is True
    assert error == ""


def test_check_safety_with_lowercase_select():
    """Test that lowercase SELECT passes safety check."""
    validator = SQLValidator()
    
    sql = "select * from iso_tank;"
    is_safe, error = validator.check_safety(sql)
    
    assert is_safe is True
    assert error == ""


def test_check_safety_with_leading_whitespace():
    """Test that SELECT with leading whitespace passes safety check."""
    validator = SQLValidator()
    
    sql = "   SELECT * FROM iso_tank;"
    is_safe, error = validator.check_safety(sql)
    
    assert is_safe is True
    assert error == ""


def test_check_safety_blocks_drop():
    """Test that DROP statement is blocked."""
    validator = SQLValidator()
    
    sql = "DROP TABLE iso_tank;"
    is_safe, error = validator.check_safety(sql)
    
    assert is_safe is False
    assert "can't be answered safely" in error


def test_check_safety_blocks_delete():
    """Test that DELETE statement is blocked."""
    validator = SQLValidator()
    
    sql = "DELETE FROM iso_tank WHERE id = '123';"
    is_safe, error = validator.check_safety(sql)
    
    assert is_safe is False
    assert "can't be answered safely" in error


def test_check_safety_blocks_update():
    """Test that UPDATE statement is blocked."""
    validator = SQLValidator()
    
    sql = "UPDATE iso_tank SET tank_number = 'HACKED' WHERE id = '123';"
    is_safe, error = validator.check_safety(sql)
    
    assert is_safe is False
    assert "can't be answered safely" in error


def test_check_safety_blocks_insert():
    """Test that INSERT statement is blocked."""
    validator = SQLValidator()
    
    sql = "INSERT INTO iso_tank (tank_number) VALUES ('FAKE');"
    is_safe, error = validator.check_safety(sql)
    
    assert is_safe is False
    assert "can't be answered safely" in error


def test_check_safety_blocks_sql_injection():
    """Test that SQL injection attempts are blocked."""
    validator = SQLValidator()
    
    # Classic SQL injection
    sql = "SELECT * FROM iso_tank WHERE id = '1'; DELETE FROM iso_tank WHERE 1=1; --"
    is_safe, error = validator.check_safety(sql)
    
    assert is_safe is False
    assert "can't be answered safely" in error


def test_check_safety_blocks_non_select_queries():
    """Test that non-SELECT queries are blocked."""
    validator = SQLValidator()
    
    # EXPLAIN query
    sql = "EXPLAIN SELECT * FROM iso_tank;"
    is_safe, error = validator.check_safety(sql)
    
    assert is_safe is False
    assert "Only SELECT queries are allowed" in error


def test_check_safety_with_empty_sql():
    """Test that empty SQL fails safety check."""
    validator = SQLValidator()
    
    is_safe, error = validator.check_safety("")
    assert is_safe is False
    assert "SQL cannot be empty" in error


def test_check_safety_case_insensitive():
    """Test that safety check is case-insensitive."""
    validator = SQLValidator()
    
    # Lowercase dangerous keywords
    sql = "select * from iso_tank; delete from iso_tank;"
    is_safe, error = validator.check_safety(sql)
    
    assert is_safe is False
    assert "can't be answered safely" in error


# ============================================================================
# Schema Parsing Tests
# ============================================================================

def test_parse_schema():
    """Test that schema parsing extracts tables and columns correctly."""
    validator = SQLValidator()
    
    tables, columns = validator._parse_schema(MOCK_SCHEMA)
    
    # Check tables
    assert 'iso_tank' in tables
    assert 'service_tank' in tables
    assert 'vehicle_in' in tables
    
    # Check columns for iso_tank
    assert 'id' in columns['iso_tank']
    assert 'tank_number' in columns['iso_tank']
    assert 'iso_tank_status' in columns['iso_tank']
    assert 'created_at' in columns['iso_tank']
    
    # Check columns for service_tank
    assert 'service_tank_status' in columns['service_tank']


def test_extract_tables():
    """Test that table extraction works correctly."""
    validator = SQLValidator()
    
    # Simple FROM
    sql = "SELECT * FROM iso_tank;"
    tables = validator._extract_tables(sql)
    assert 'iso_tank' in tables
    
    # JOIN
    sql = "SELECT * FROM iso_tank JOIN vehicle_in ON iso_tank.vehicle_in_id = vehicle_in.id;"
    tables = validator._extract_tables(sql)
    assert 'iso_tank' in tables
    assert 'vehicle_in' in tables
    
    # LEFT JOIN
    sql = "SELECT * FROM iso_tank LEFT JOIN service_tank ON iso_tank.id = service_tank.id;"
    tables = validator._extract_tables(sql)
    assert 'iso_tank' in tables
    assert 'service_tank' in tables


def test_extract_columns():
    """Test that column extraction works correctly."""
    validator = SQLValidator()
    
    # Simple SELECT
    sql = "SELECT tank_number, iso_tank_status FROM iso_tank;"
    columns = validator._extract_columns(sql)
    assert 'tank_number' in columns
    assert 'iso_tank_status' in columns
    
    # SELECT with WHERE
    sql = "SELECT tank_number FROM iso_tank WHERE id = '123';"
    columns = validator._extract_columns(sql)
    assert 'tank_number' in columns
    assert 'id' in columns
    
    # SELECT with ORDER BY
    sql = "SELECT tank_number FROM iso_tank ORDER BY created_at DESC;"
    columns = validator._extract_columns(sql)
    assert 'tank_number' in columns
    assert 'created_at' in columns


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
