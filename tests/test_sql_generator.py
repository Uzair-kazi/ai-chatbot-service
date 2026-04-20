"""
Tests for SQL Generator Service.

Note: These tests validate the SQL generation logic.
Tests that require actual AI API calls are marked with @pytest.mark.integration
and skip if AI provider is not configured.
"""

import os
import pytest
from services.sql_generator import SQLGenerator, SQLGenerationError


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
  - vehicle_out_id: uuid (foreign key -> vehicle_out.id)
  - survey_form_id: uuid (foreign key -> survey_form.id)
  - created_at: timestamp with time zone (not null)
  - updated_at: timestamp with time zone (not null)

Table: service_tank
--------------------------------------------------------------------------------
  - id: uuid (primary key)
  - tank_number: character varying
  - service_tank_status: character varying (not null)
  - vehicle_in_id: uuid (foreign key -> vehicle_in.id)
  - vehicle_out_id: uuid (foreign key -> vehicle_out.id)
  - created_at: timestamp with time zone (not null)
  - updated_at: timestamp with time zone (not null)
"""


def test_sql_generator_initialization():
    """Test that SQLGenerator initializes correctly."""
    generator = SQLGenerator()
    
    assert generator is not None
    assert generator.ai_client is not None
    assert generator.model_name is not None
    assert generator.sdk_type in ["openai_compatible", "anthropic"]


def test_empty_question_raises_error():
    """Test that empty question raises ValueError."""
    generator = SQLGenerator()
    
    with pytest.raises(ValueError, match="Question cannot be empty"):
        generator.generate_sql("", MOCK_SCHEMA)
    
    with pytest.raises(ValueError, match="Question cannot be empty"):
        generator.generate_sql("   ", MOCK_SCHEMA)


def test_clean_sql_removes_markdown():
    """Test that _clean_sql removes markdown code blocks."""
    generator = SQLGenerator()
    
    # Test with ```sql code block
    sql_with_markdown = "```sql\nSELECT * FROM iso_tank\n```"
    cleaned = generator._clean_sql(sql_with_markdown)
    assert "```" not in cleaned
    assert "SELECT * FROM iso_tank" in cleaned
    
    # Test with ``` code block (no language)
    sql_with_markdown = "```\nSELECT * FROM iso_tank\n```"
    cleaned = generator._clean_sql(sql_with_markdown)
    assert "```" not in cleaned
    assert "SELECT * FROM iso_tank" in cleaned


def test_clean_sql_adds_semicolon():
    """Test that _clean_sql adds semicolon if missing."""
    generator = SQLGenerator()
    
    sql_without_semicolon = "SELECT * FROM iso_tank"
    cleaned = generator._clean_sql(sql_without_semicolon)
    assert cleaned.endswith(';')
    
    sql_with_semicolon = "SELECT * FROM iso_tank;"
    cleaned = generator._clean_sql(sql_with_semicolon)
    assert cleaned.endswith(';')
    assert cleaned.count(';') == 1


def test_clean_sql_normalizes_whitespace():
    """Test that _clean_sql normalizes whitespace."""
    generator = SQLGenerator()
    
    sql_with_extra_whitespace = "SELECT  *  \n  FROM   iso_tank  \n  WHERE   id = 1"
    cleaned = generator._clean_sql(sql_with_extra_whitespace)
    
    # Should have single spaces
    assert "  " not in cleaned
    assert "\n" not in cleaned
    assert "SELECT * FROM iso_tank WHERE id = 1" in cleaned


def test_ensure_limit_adds_limit():
    """Test that _ensure_limit adds LIMIT 100 if not present."""
    generator = SQLGenerator()
    
    # SQL without LIMIT
    sql_without_limit = "SELECT * FROM iso_tank;"
    result = generator._ensure_limit(sql_without_limit)
    assert "LIMIT 100" in result
    assert result == "SELECT * FROM iso_tank LIMIT 100;"
    
    # SQL without LIMIT or semicolon
    sql_without_limit = "SELECT * FROM iso_tank"
    result = generator._ensure_limit(sql_without_limit)
    assert "LIMIT 100" in result


def test_ensure_limit_preserves_existing_limit():
    """Test that _ensure_limit preserves existing LIMIT clause."""
    generator = SQLGenerator()
    
    # SQL with LIMIT
    sql_with_limit = "SELECT * FROM iso_tank LIMIT 50;"
    result = generator._ensure_limit(sql_with_limit)
    assert "LIMIT 50" in result
    assert "LIMIT 100" not in result
    
    # SQL with lowercase limit
    sql_with_limit = "SELECT * FROM iso_tank limit 25;"
    result = generator._ensure_limit(sql_with_limit)
    assert "limit 25" in result
    assert "LIMIT 100" not in result


def test_build_system_prompt_includes_schema():
    """Test that system prompt includes the schema."""
    generator = SQLGenerator()
    
    prompt = generator._build_system_prompt(MOCK_SCHEMA)
    
    assert "iso_tank" in prompt
    assert "service_tank" in prompt
    assert "FEW-SHOT EXAMPLES" in prompt
    assert "RULES" in prompt


def test_build_system_prompt_includes_few_shot_examples():
    """Test that system prompt includes few-shot examples."""
    generator = SQLGenerator()
    
    prompt = generator._build_system_prompt(MOCK_SCHEMA)
    
    # Check for example patterns
    assert "Example 1:" in prompt or "Question:" in prompt
    assert "SELECT" in prompt
    assert "FROM" in prompt


@pytest.mark.skipif(
    not all([
        os.getenv("AI_API_KEY"),
        os.getenv("AI_MODEL"),
        os.getenv("SDK_TYPE")
    ]),
    reason="AI provider not configured - skipping integration tests"
)
@pytest.mark.integration
def test_generate_sql_with_real_ai():
    """Integration test: Generate SQL with real AI provider."""
    generator = SQLGenerator()
    
    question = "How many ISO tanks are in 'IN' status?"
    sql = generator.generate_sql(question, MOCK_SCHEMA)
    
    # Verify SQL is generated
    assert sql is not None
    assert len(sql) > 0
    
    # Verify SQL contains expected elements
    assert "SELECT" in sql.upper()
    assert "iso_tank" in sql.lower()
    assert "LIMIT" in sql.upper()
    
    # Verify no markdown artifacts
    assert "```" not in sql


@pytest.mark.skipif(
    not all([
        os.getenv("AI_API_KEY"),
        os.getenv("AI_MODEL"),
        os.getenv("SDK_TYPE")
    ]),
    reason="AI provider not configured - skipping integration tests"
)
@pytest.mark.integration
def test_generate_sql_with_join_query():
    """Integration test: Generate SQL with JOIN."""
    generator = SQLGenerator()
    
    question = "Show me ISO tanks with their vehicle in information"
    sql = generator.generate_sql(question, MOCK_SCHEMA)
    
    # Verify SQL contains JOIN
    assert "JOIN" in sql.upper() or "join" in sql.lower()
    assert "iso_tank" in sql.lower()
    assert "LIMIT" in sql.upper()


@pytest.mark.skipif(
    not all([
        os.getenv("AI_API_KEY"),
        os.getenv("AI_MODEL"),
        os.getenv("SDK_TYPE")
    ]),
    reason="AI provider not configured - skipping integration tests"
)
@pytest.mark.integration
def test_generate_sql_adds_limit_automatically():
    """Integration test: Verify LIMIT is added automatically."""
    generator = SQLGenerator()
    
    question = "List all service tanks"
    sql = generator.generate_sql(question, MOCK_SCHEMA)
    
    # Verify LIMIT clause exists
    assert "LIMIT" in sql.upper()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
