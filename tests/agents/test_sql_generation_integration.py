"""
Integration Tests for SQL Generation Agent

These tests verify the SQL Generation agent works end-to-end with real
AI providers (when configured). They are marked as integration tests and
can be skipped if AI provider is not configured.
"""

import pytest
import os
from agents.sql_generation import SQLGenerationAgent
from agents.models.query_models import SQLGenerationRequest


# Sample schema for testing
SAMPLE_SCHEMA = """Table: iso_tank
  - id: uuid
  - tank_number: varchar
  - iso_tank_status: varchar
  - created_at: timestamp
  - vehicle_in_id: uuid
  - vehicle_out_id: uuid
  - survey_form_id: uuid

Table: vehicle_in
  - id: uuid
  - created_at: timestamp

Table: vehicle_out
  - id: uuid
  - created_at: timestamp
"""


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("AI_API_KEY"),
    reason="AI_API_KEY not configured - skipping integration test"
)
def test_sql_generation_agent_real_ai_simple_query():
    """Integration test: Generate SQL for simple query with real AI provider."""
    agent = SQLGenerationAgent()
    request = SQLGenerationRequest(
        question="How many ISO tanks are there?",
        db_schema=SAMPLE_SCHEMA,
        max_retries=2,
        temperature=0.1
    )
    
    response = agent.execute(request)
    
    # Should succeed
    assert response.success is True
    assert response.sql is not None
    
    # Should contain expected SQL elements
    assert "SELECT" in response.sql.upper()
    assert "iso_tank" in response.sql.lower()
    assert "LIMIT" in response.sql.upper()
    
    # Should have high confidence (first attempt)
    assert response.confidence >= 0.75
    
    # Should have low retry count
    assert response.retry_count <= 1


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("AI_API_KEY"),
    reason="AI_API_KEY not configured - skipping integration test"
)
def test_sql_generation_agent_real_ai_complex_query():
    """Integration test: Generate SQL for complex query with JOIN."""
    agent = SQLGenerationAgent()
    request = SQLGenerationRequest(
        question="Show me ISO tanks with their vehicle in data",
        db_schema=SAMPLE_SCHEMA,
        max_retries=2,
        temperature=0.1
    )
    
    response = agent.execute(request)
    
    # Complex queries may fail validation even after retries
    # This is expected behavior - the agent should return low confidence
    if response.success:
        # If successful, should contain JOIN
        assert "JOIN" in response.sql.upper()
        assert "ON" in response.sql.upper()
        
        # Should reference both tables
        assert "iso_tank" in response.sql.lower()
        assert "vehicle_in" in response.sql.lower()
    else:
        # If failed, should have low confidence and validation issues
        assert response.confidence < 0.7
        assert len(response.validation_issues) > 0
        assert response.error is not None


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("AI_API_KEY"),
    reason="AI_API_KEY not configured - skipping integration test"
)
def test_sql_generation_agent_real_ai_filtering_query():
    """Integration test: Generate SQL with WHERE clause."""
    agent = SQLGenerationAgent()
    request = SQLGenerationRequest(
        question="Show me ISO tanks with status 'IN'",
        db_schema=SAMPLE_SCHEMA,
        max_retries=2,
        temperature=0.1
    )
    
    response = agent.execute(request)
    
    # Should succeed
    assert response.success is True
    assert response.sql is not None
    
    # Should contain WHERE clause
    assert "WHERE" in response.sql.upper()
    assert "iso_tank_status" in response.sql.lower()
    assert "'IN'" in response.sql or '"IN"' in response.sql
