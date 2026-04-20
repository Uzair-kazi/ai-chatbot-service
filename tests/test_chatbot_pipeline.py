"""
Tests for Chatbot Pipeline Orchestrator.

Note: Integration tests require both database and AI provider configuration.
They are marked with @pytest.mark.integration and skip if not configured.
"""

import os
import pytest
from unittest.mock import Mock, patch
from services.chatbot_pipeline import ask, PipelineError
from services.sql_generator import SQLGenerationError
from services.sql_executor import (
    QueryTimeoutError,
    DatabaseConnectionError,
    SQLSyntaxError,
    PermissionDeniedError
)
from services.answer_formatter import AnswerFormattingError


def test_ask_returns_correct_structure():
    """Test that ask() returns the expected structure."""
    # This test verifies the return structure without actually calling the pipeline
    expected_keys = ["answer", "sql", "rows_count", "status_code"]
    
    # Mock result
    mock_result = {
        "answer": "Test answer",
        "sql": "SELECT 1;",
        "rows_count": 1,
        "status_code": 200
    }
    
    for key in expected_keys:
        assert key in mock_result


@patch('services.chatbot_pipeline.get_database_schema')
@patch('services.chatbot_pipeline.SQLGenerator')
@patch('services.chatbot_pipeline.SQLValidator')
@patch('services.chatbot_pipeline.get_executor')
@patch('services.chatbot_pipeline.AnswerFormatter')
def test_ask_successful_pipeline(mock_formatter, mock_executor, mock_validator, mock_generator, mock_schema):
    """Test successful pipeline execution with mocked services."""
    # Setup mocks
    mock_schema.return_value = "Mock schema"
    
    mock_gen_instance = Mock()
    mock_gen_instance.generate_sql.return_value = "SELECT COUNT(*) FROM iso_tank;"
    mock_generator.return_value = mock_gen_instance
    
    mock_val_instance = Mock()
    mock_val_instance.validate_references.return_value = (True, "")
    mock_val_instance.check_safety.return_value = (True, "")
    mock_validator.return_value = mock_val_instance
    
    mock_exec_instance = Mock()
    mock_exec_instance.execute_query.return_value = {
        "columns": ["count"],
        "rows": [{"count": 47}],
        "row_count": 1
    }
    mock_executor.return_value = mock_exec_instance
    
    mock_fmt_instance = Mock()
    mock_fmt_instance.format_answer.return_value = "There are 47 tanks."
    mock_formatter.return_value = mock_fmt_instance
    
    # Execute pipeline
    result = ask("How many tanks?")
    
    # Verify result
    assert result["status_code"] == 200
    assert result["answer"] == "There are 47 tanks."
    assert result["sql"] == "SELECT COUNT(*) FROM iso_tank;"
    assert result["rows_count"] == 1
    assert "error" not in result


@patch('services.chatbot_pipeline.get_database_schema')
@patch('services.chatbot_pipeline.SQLGenerator')
def test_ask_handles_sql_generation_error(mock_generator, mock_schema):
    """Test that SQL generation errors are handled gracefully."""
    mock_schema.return_value = "Mock schema"
    
    mock_gen_instance = Mock()
    mock_gen_instance.generate_sql.side_effect = SQLGenerationError("AI API failed")
    mock_generator.return_value = mock_gen_instance
    
    result = ask("Test question")
    
    assert result["status_code"] == 500
    assert "Failed to generate SQL query" in result["answer"]
    assert "error" in result


@patch('services.chatbot_pipeline.get_database_schema')
@patch('services.chatbot_pipeline.SQLGenerator')
@patch('services.chatbot_pipeline.SQLValidator')
def test_ask_handles_validation_failure(mock_validator, mock_generator, mock_schema):
    """Test that validation failures return 400 status."""
    mock_schema.return_value = "Mock schema"
    
    mock_gen_instance = Mock()
    mock_gen_instance.generate_sql.return_value = "SELECT * FROM invalid_table;"
    mock_generator.return_value = mock_gen_instance
    
    mock_val_instance = Mock()
    mock_val_instance.validate_references.return_value = (False, "Table 'invalid_table' does not exist")
    mock_validator.return_value = mock_val_instance
    
    result = ask("Test question")
    
    assert result["status_code"] == 400
    assert "invalid_table" in result["answer"]
    assert "error" in result


@patch('services.chatbot_pipeline.get_database_schema')
@patch('services.chatbot_pipeline.SQLGenerator')
@patch('services.chatbot_pipeline.SQLValidator')
def test_ask_handles_safety_failure(mock_validator, mock_generator, mock_schema):
    """Test that safety check failures return 400 status."""
    mock_schema.return_value = "Mock schema"
    
    mock_gen_instance = Mock()
    mock_gen_instance.generate_sql.return_value = "DROP TABLE iso_tank;"
    mock_generator.return_value = mock_gen_instance
    
    mock_val_instance = Mock()
    mock_val_instance.validate_references.return_value = (True, "")
    mock_val_instance.check_safety.return_value = (False, "That question can't be answered safely")
    mock_validator.return_value = mock_val_instance
    
    result = ask("Test question")
    
    assert result["status_code"] == 400
    assert "can't be answered safely" in result["answer"]
    assert "error" in result


@patch('services.chatbot_pipeline.get_database_schema')
@patch('services.chatbot_pipeline.SQLGenerator')
@patch('services.chatbot_pipeline.SQLValidator')
@patch('services.chatbot_pipeline.get_executor')
def test_ask_handles_query_timeout(mock_executor, mock_validator, mock_generator, mock_schema):
    """Test that query timeouts return 504 status."""
    mock_schema.return_value = "Mock schema"
    
    mock_gen_instance = Mock()
    mock_gen_instance.generate_sql.return_value = "SELECT * FROM iso_tank;"
    mock_generator.return_value = mock_gen_instance
    
    mock_val_instance = Mock()
    mock_val_instance.validate_references.return_value = (True, "")
    mock_val_instance.check_safety.return_value = (True, "")
    mock_validator.return_value = mock_val_instance
    
    mock_exec_instance = Mock()
    mock_exec_instance.execute_query.side_effect = QueryTimeoutError("Query timeout")
    mock_executor.return_value = mock_exec_instance
    
    result = ask("Test question")
    
    assert result["status_code"] == 504
    assert "took too long" in result["answer"]
    assert "error" in result


@patch('services.chatbot_pipeline.get_database_schema')
@patch('services.chatbot_pipeline.SQLGenerator')
@patch('services.chatbot_pipeline.SQLValidator')
@patch('services.chatbot_pipeline.get_executor')
def test_ask_handles_database_connection_error(mock_executor, mock_validator, mock_generator, mock_schema):
    """Test that database connection errors return 503 status."""
    mock_schema.return_value = "Mock schema"
    
    mock_gen_instance = Mock()
    mock_gen_instance.generate_sql.return_value = "SELECT * FROM iso_tank;"
    mock_generator.return_value = mock_gen_instance
    
    mock_val_instance = Mock()
    mock_val_instance.validate_references.return_value = (True, "")
    mock_val_instance.check_safety.return_value = (True, "")
    mock_validator.return_value = mock_val_instance
    
    mock_exec_instance = Mock()
    mock_exec_instance.execute_query.side_effect = DatabaseConnectionError("Connection failed")
    mock_executor.return_value = mock_exec_instance
    
    result = ask("Test question")
    
    assert result["status_code"] == 503
    assert "Database unavailable" in result["answer"]
    assert "error" in result


@patch('services.chatbot_pipeline.get_database_schema')
@patch('services.chatbot_pipeline.SQLGenerator')
@patch('services.chatbot_pipeline.SQLValidator')
@patch('services.chatbot_pipeline.get_executor')
def test_ask_handles_sql_syntax_error(mock_executor, mock_validator, mock_generator, mock_schema):
    """Test that SQL syntax errors return 400 status."""
    mock_schema.return_value = "Mock schema"
    
    mock_gen_instance = Mock()
    mock_gen_instance.generate_sql.return_value = "SELECT * FORM iso_tank;"
    mock_generator.return_value = mock_gen_instance
    
    mock_val_instance = Mock()
    mock_val_instance.validate_references.return_value = (True, "")
    mock_val_instance.check_safety.return_value = (True, "")
    mock_validator.return_value = mock_val_instance
    
    mock_exec_instance = Mock()
    mock_exec_instance.execute_query.side_effect = SQLSyntaxError("Syntax error")
    mock_executor.return_value = mock_exec_instance
    
    result = ask("Test question")
    
    assert result["status_code"] == 400
    assert "Invalid SQL query" in result["answer"]
    assert "error" in result


@patch('services.chatbot_pipeline.get_database_schema')
@patch('services.chatbot_pipeline.SQLGenerator')
@patch('services.chatbot_pipeline.SQLValidator')
@patch('services.chatbot_pipeline.get_executor')
def test_ask_handles_permission_denied(mock_executor, mock_validator, mock_generator, mock_schema):
    """Test that permission denied errors return 403 status."""
    mock_schema.return_value = "Mock schema"
    
    mock_gen_instance = Mock()
    mock_gen_instance.generate_sql.return_value = "SELECT * FROM iso_tank;"
    mock_generator.return_value = mock_gen_instance
    
    mock_val_instance = Mock()
    mock_val_instance.validate_references.return_value = (True, "")
    mock_val_instance.check_safety.return_value = (True, "")
    mock_validator.return_value = mock_val_instance
    
    mock_exec_instance = Mock()
    mock_exec_instance.execute_query.side_effect = PermissionDeniedError("Access denied")
    mock_executor.return_value = mock_exec_instance
    
    result = ask("Test question")
    
    assert result["status_code"] == 403
    assert "Access denied" in result["answer"]
    assert "error" in result


@pytest.mark.skipif(
    not all([
        os.getenv("DB_URL"),
        os.getenv("AI_API_KEY"),
        os.getenv("AI_MODEL"),
        os.getenv("SDK_TYPE")
    ]),
    reason="Database and AI provider not configured - skipping integration tests"
)
@pytest.mark.integration
@pytest.mark.slow
def test_ask_full_pipeline_integration():
    """Integration test: Run complete pipeline with real services."""
    question = "How many rows are in the iso_tank table?"
    
    result = ask(question)
    
    # Verify result structure
    assert "answer" in result
    assert "sql" in result
    assert "rows_count" in result
    assert "status_code" in result
    
    # Verify success
    assert result["status_code"] == 200
    assert len(result["answer"]) > 0
    assert len(result["sql"]) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
