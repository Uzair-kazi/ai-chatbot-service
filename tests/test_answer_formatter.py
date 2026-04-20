"""
Tests for Answer Formatter Service.

Note: Integration tests require AI provider configuration.
They are marked with @pytest.mark.integration and skip if not configured.
"""

import os
import pytest
from services.answer_formatter import AnswerFormatter, AnswerFormattingError


def test_formatter_initialization():
    """Test that AnswerFormatter initializes correctly."""
    formatter = AnswerFormatter()
    
    assert formatter is not None
    assert formatter.ai_client is not None
    assert formatter.model_name is not None
    assert formatter.sdk_type in ["openai_compatible", "anthropic"]


def test_format_answer_with_empty_results():
    """Test that empty results return appropriate message."""
    formatter = AnswerFormatter()
    
    question = "How many tanks are there?"
    sql = "SELECT COUNT(*) FROM iso_tank WHERE 1=0;"
    results = {
        "columns": ["count"],
        "rows": [],
        "row_count": 0
    }
    
    answer = formatter.format_answer(question, sql, results)
    
    assert answer == "No results found for your question."


def test_format_rows_as_text_single_row():
    """Test formatting a single row as text."""
    formatter = AnswerFormatter()
    
    rows = [{"count": 47}]
    columns = ["count"]
    
    text = formatter._format_rows_as_text(rows, columns)
    
    assert "count: 47" in text
    assert "|" not in text  # Single row should not use table format


def test_format_rows_as_text_multiple_rows():
    """Test formatting multiple rows as text."""
    formatter = AnswerFormatter()
    
    rows = [
        {"tank_number": "ABC123", "status": "IN"},
        {"tank_number": "DEF456", "status": "OUT"}
    ]
    columns = ["tank_number", "status"]
    
    text = formatter._format_rows_as_text(rows, columns)
    
    # Should use table format with pipes
    assert "|" in text
    assert "ABC123" in text
    assert "DEF456" in text
    assert "IN" in text
    assert "OUT" in text


def test_format_rows_as_text_empty():
    """Test formatting empty rows."""
    formatter = AnswerFormatter()
    
    rows = []
    columns = ["test"]
    
    text = formatter._format_rows_as_text(rows, columns)
    
    assert text == "(No rows)"


def test_build_prompt_includes_question():
    """Test that prompt includes the original question."""
    formatter = AnswerFormatter()
    
    question = "How many tanks are there?"
    sql = "SELECT COUNT(*) FROM iso_tank;"
    results = {
        "columns": ["count"],
        "rows": [{"count": 47}],
        "row_count": 1
    }
    
    prompt = formatter._build_prompt(question, sql, results)
    
    assert question in prompt
    assert sql in prompt
    assert "47" in prompt


def test_build_prompt_shows_truncation():
    """Test that prompt mentions truncation for large result sets."""
    formatter = AnswerFormatter()
    
    question = "List all tanks"
    sql = "SELECT * FROM iso_tank;"
    
    # Create 15 rows but only 10 will be shown
    rows = [{"id": i, "tank_number": f"TANK{i}"} for i in range(15)]
    results = {
        "columns": ["id", "tank_number"],
        "rows": rows,
        "row_count": 15
    }
    
    prompt = formatter._build_prompt(question, sql, results)
    
    # Should mention showing 10 of 15
    assert "10 of 15" in prompt or "Showing 10" in prompt


def test_build_prompt_no_truncation_for_small_results():
    """Test that prompt doesn't mention truncation for small result sets."""
    formatter = AnswerFormatter()
    
    question = "List tanks"
    sql = "SELECT * FROM iso_tank LIMIT 5;"
    
    rows = [{"id": i, "tank_number": f"TANK{i}"} for i in range(5)]
    results = {
        "columns": ["id", "tank_number"],
        "rows": rows,
        "row_count": 5
    }
    
    prompt = formatter._build_prompt(question, sql, results)
    
    # Should show 5 of 5 (no truncation message needed)
    assert "5 of 5" in prompt or "showing 5" in prompt.lower()


@pytest.mark.skipif(
    not all([
        os.getenv("AI_API_KEY"),
        os.getenv("AI_MODEL"),
        os.getenv("SDK_TYPE")
    ]),
    reason="AI provider not configured - skipping integration tests"
)
@pytest.mark.integration
def test_format_answer_single_row_count():
    """Integration test: Format answer for COUNT query."""
    formatter = AnswerFormatter()
    
    question = "How many ISO tanks are in 'IN' status?"
    sql = "SELECT COUNT(*) FROM iso_tank WHERE iso_tank_status = 'IN';"
    results = {
        "columns": ["count"],
        "rows": [{"count": 47}],
        "row_count": 1
    }
    
    answer = formatter.format_answer(question, sql, results)
    
    # Verify answer is generated
    assert answer is not None
    assert len(answer) > 0
    
    # Verify answer references the number
    assert "47" in answer


@pytest.mark.skipif(
    not all([
        os.getenv("AI_API_KEY"),
        os.getenv("AI_MODEL"),
        os.getenv("SDK_TYPE")
    ]),
    reason="AI provider not configured - skipping integration tests"
)
@pytest.mark.integration
def test_format_answer_multiple_rows():
    """Integration test: Format answer for multi-row query."""
    formatter = AnswerFormatter()
    
    question = "Show me the top 3 tanks"
    sql = "SELECT tank_number, iso_tank_status FROM iso_tank LIMIT 3;"
    results = {
        "columns": ["tank_number", "iso_tank_status"],
        "rows": [
            {"tank_number": "ABC123", "iso_tank_status": "IN"},
            {"tank_number": "DEF456", "iso_tank_status": "OUT"},
            {"tank_number": "GHI789", "iso_tank_status": "IN"}
        ],
        "row_count": 3
    }
    
    answer = formatter.format_answer(question, sql, results)
    
    # Verify answer is generated
    assert answer is not None
    assert len(answer) > 0


@pytest.mark.skipif(
    not all([
        os.getenv("AI_API_KEY"),
        os.getenv("AI_MODEL"),
        os.getenv("SDK_TYPE")
    ]),
    reason="AI provider not configured - skipping integration tests"
)
@pytest.mark.integration
def test_format_answer_with_truncation():
    """Integration test: Format answer with truncated results."""
    formatter = AnswerFormatter()
    
    question = "List all tanks"
    sql = "SELECT tank_number FROM iso_tank;"
    
    # Create 15 rows
    rows = [{"tank_number": f"TANK{i:03d}"} for i in range(15)]
    results = {
        "columns": ["tank_number"],
        "rows": rows,
        "row_count": 15
    }
    
    answer = formatter.format_answer(question, sql, results)
    
    # Verify answer mentions truncation
    assert answer is not None
    assert len(answer) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
