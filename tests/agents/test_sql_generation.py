"""
Tests for SQL Generation Agent with Self-Critique Loop

This module tests the SQL Generation agent's ability to:
1. Generate valid SQL on first attempt
2. Self-critique and retry with validation feedback
3. Handle confidence decay across retry attempts
4. Catch column hallucinations, table errors, and JOIN issues
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from agents.sql_generation import SQLGenerationAgent
from agents.models.query_models import SQLGenerationRequest, SQLGenerationResponse
from agents.base import AgentValidationError, AgentExecutionError


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


class TestSQLGenerationAgentValidation:
    """Test validation logic for SQL generation agent."""
    
    def test_validate_sql_valid_query(self):
        """Happy path: Valid SQL passes validation."""
        agent = SQLGenerationAgent()
        sql = "SELECT COUNT(*) FROM iso_tank WHERE iso_tank_status = 'IN' LIMIT 100;"
        
        is_valid, issues = agent._validate_sql(sql, SAMPLE_SCHEMA)
        
        assert is_valid is True
        assert issues == []
    
    def test_validate_sql_invalid_table(self):
        """Integration: Validation catches table name errors."""
        agent = SQLGenerationAgent()
        sql = "SELECT COUNT(*) FROM invalid_table LIMIT 100;"
        
        is_valid, issues = agent._validate_sql(sql, SAMPLE_SCHEMA)
        
        assert is_valid is False
        assert len(issues) > 0
        assert "invalid_table" in issues[0].lower()
    
    def test_validate_sql_invalid_column(self):
        """Integration: Validation catches column hallucinations."""
        agent = SQLGenerationAgent()
        # "idastank_count" is a hallucinated column (should be "id")
        sql = "SELECT idastank_count FROM iso_tank LIMIT 100;"
        
        is_valid, issues = agent._validate_sql(sql, SAMPLE_SCHEMA)
        
        assert is_valid is False
        assert len(issues) > 0
        assert "idastank_count" in issues[0].lower()
    
    def test_validate_sql_missing_join_condition(self):
        """Integration: Validation catches missing JOIN conditions."""
        agent = SQLGenerationAgent()
        # Missing ON clause in JOIN
        sql = "SELECT * FROM iso_tank JOIN vehicle_in LIMIT 100;"
        
        is_valid, issues = agent._validate_sql(sql, SAMPLE_SCHEMA)
        
        assert is_valid is False
        assert len(issues) > 0
        assert "join" in issues[0].lower()
    
    def test_validate_sql_valid_join(self):
        """Happy path: Valid JOIN passes validation."""
        agent = SQLGenerationAgent()
        sql = "SELECT * FROM iso_tank JOIN vehicle_in ON iso_tank.vehicle_in_id = vehicle_in.id LIMIT 100;"
        
        is_valid, issues = agent._validate_sql(sql, SAMPLE_SCHEMA)
        
        assert is_valid is True
        assert issues == []
    
    def test_validate_sql_empty_query(self):
        """Edge case: Empty SQL fails validation."""
        agent = SQLGenerationAgent()
        
        is_valid, issues = agent._validate_sql("", SAMPLE_SCHEMA)
        
        assert is_valid is False
        assert len(issues) > 0
    
    def test_validate_sql_dangerous_keywords(self):
        """Integration: Validation catches dangerous SQL operations."""
        agent = SQLGenerationAgent()
        sql = "DROP TABLE iso_tank;"
        
        is_valid, issues = agent._validate_sql(sql, SAMPLE_SCHEMA)
        
        assert is_valid is False
        assert len(issues) > 0


class TestSQLGenerationAgentExecution:
    """Test SQL generation agent execution with self-critique loop."""
    
    @patch('agents.sql_generation.ai_client')
    def test_execute_valid_sql_first_attempt(self, mock_ai_client):
        """Happy path: Generate valid SQL on first attempt (confidence=0.9)."""
        # Mock AI response with valid SQL
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="SELECT COUNT(*) FROM iso_tank LIMIT 100;"))]
        mock_response.usage = Mock(prompt_tokens=100, completion_tokens=20, total_tokens=120)
        mock_ai_client.chat.completions.create.return_value = mock_response
        
        agent = SQLGenerationAgent()
        request = SQLGenerationRequest(
            question="How many ISO tanks?",
            db_schema=SAMPLE_SCHEMA,
            max_retries=2,
            temperature=0.1
        )
        
        response = agent.execute(request)
        
        assert response.success is True
        assert response.sql is not None
        assert "SELECT COUNT(*) FROM iso_tank" in response.sql
        assert response.confidence == 0.9
        assert response.retry_count == 0
        assert response.validation_issues == []
    
    @patch('agents.sql_generation.ai_client')
    def test_execute_valid_sql_second_attempt(self, mock_ai_client):
        """Happy path: Generate valid SQL on second attempt after validation failure (confidence=0.75)."""
        # First attempt: invalid column
        mock_response_1 = Mock()
        mock_response_1.choices = [Mock(message=Mock(content="SELECT idastank_count FROM iso_tank LIMIT 100;"))]
        mock_response_1.usage = Mock(prompt_tokens=100, completion_tokens=20, total_tokens=120)
        
        # Second attempt: valid SQL
        mock_response_2 = Mock()
        mock_response_2.choices = [Mock(message=Mock(content="SELECT COUNT(*) FROM iso_tank LIMIT 100;"))]
        mock_response_2.usage = Mock(prompt_tokens=100, completion_tokens=20, total_tokens=120)
        
        mock_ai_client.chat.completions.create.side_effect = [mock_response_1, mock_response_2]
        
        agent = SQLGenerationAgent()
        request = SQLGenerationRequest(
            question="How many ISO tanks?",
            db_schema=SAMPLE_SCHEMA,
            max_retries=2,
            temperature=0.1
        )
        
        response = agent.execute(request)
        
        assert response.success is True
        assert response.sql is not None
        assert "SELECT COUNT(*) FROM iso_tank" in response.sql
        assert response.confidence == 0.75  # Decayed from 0.9
        assert response.retry_count == 1
        assert len(response.validation_issues) == 0  # Final attempt has no issues
    
    @patch('agents.sql_generation.ai_client')
    def test_execute_valid_sql_third_attempt(self, mock_ai_client):
        """Happy path: Generate valid SQL on third attempt (confidence=0.6)."""
        # First attempt: invalid table
        mock_response_1 = Mock()
        mock_response_1.choices = [Mock(message=Mock(content="SELECT * FROM invalid_table LIMIT 100;"))]
        mock_response_1.usage = Mock(prompt_tokens=100, completion_tokens=20, total_tokens=120)
        
        # Second attempt: invalid column
        mock_response_2 = Mock()
        mock_response_2.choices = [Mock(message=Mock(content="SELECT idastank_count FROM iso_tank LIMIT 100;"))]
        mock_response_2.usage = Mock(prompt_tokens=100, completion_tokens=20, total_tokens=120)
        
        # Third attempt: valid SQL
        mock_response_3 = Mock()
        mock_response_3.choices = [Mock(message=Mock(content="SELECT COUNT(*) FROM iso_tank LIMIT 100;"))]
        mock_response_3.usage = Mock(prompt_tokens=100, completion_tokens=20, total_tokens=120)
        
        mock_ai_client.chat.completions.create.side_effect = [mock_response_1, mock_response_2, mock_response_3]
        
        agent = SQLGenerationAgent()
        request = SQLGenerationRequest(
            question="How many ISO tanks?",
            db_schema=SAMPLE_SCHEMA,
            max_retries=2,
            temperature=0.1
        )
        
        response = agent.execute(request)
        
        assert response.success is True
        assert response.sql is not None
        assert "SELECT COUNT(*) FROM iso_tank" in response.sql
        assert abs(response.confidence - 0.6) < 0.01  # Decayed twice: 0.9 -> 0.75 -> 0.6 (allow floating point tolerance)
        assert response.retry_count == 2
    
    @patch('agents.sql_generation.ai_client')
    def test_execute_all_attempts_fail(self, mock_ai_client):
        """Error path: All 3 attempts fail validation → return error with low_confidence=True."""
        # All attempts return invalid SQL
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="SELECT * FROM invalid_table LIMIT 100;"))]
        mock_response.usage = Mock(prompt_tokens=100, completion_tokens=20, total_tokens=120)
        mock_ai_client.chat.completions.create.return_value = mock_response
        
        agent = SQLGenerationAgent()
        request = SQLGenerationRequest(
            question="How many ISO tanks?",
            db_schema=SAMPLE_SCHEMA,
            max_retries=2,
            temperature=0.1
        )
        
        response = agent.execute(request)
        
        assert response.success is False
        assert response.sql is None
        assert response.error is not None
        assert "validation" in response.error.lower() or "failed" in response.error.lower()
        assert response.confidence < 0.7  # Low confidence
        assert response.retry_count >= 2  # At least 2 retries
        assert len(response.validation_issues) > 0
    
    def test_execute_empty_question(self):
        """Edge case: Empty question → Pydantic validation error."""
        agent = SQLGenerationAgent()
        
        # Pydantic validates before agent execution
        with pytest.raises(Exception):  # Pydantic ValidationError
            request = SQLGenerationRequest(
                question="",
                db_schema=SAMPLE_SCHEMA
            )
    
    def test_execute_empty_schema(self):
        """Edge case: Empty schema → Pydantic validation error."""
        agent = SQLGenerationAgent()
        
        # Pydantic validates before agent execution
        with pytest.raises(Exception):  # Pydantic ValidationError
            request = SQLGenerationRequest(
                question="How many ISO tanks?",
                db_schema=""
            )
    
    @patch('agents.sql_generation.ai_client')
    def test_execute_ai_provider_failure(self, mock_ai_client):
        """Error path: AI provider failure → return error response."""
        mock_ai_client.chat.completions.create.side_effect = Exception("API connection failed")
        
        agent = SQLGenerationAgent()
        request = SQLGenerationRequest(
            question="How many ISO tanks?",
            db_schema=SAMPLE_SCHEMA
        )
        
        response = agent.execute(request)
        
        assert response.success is False
        assert response.error is not None
        assert "failed" in response.error.lower() or "error" in response.error.lower()


class TestSQLGenerationAgentConfidenceDecay:
    """Test confidence decay across retry attempts."""
    
    def test_confidence_decay_formula(self):
        """Verify confidence decays correctly: 0.9 → 0.75 → 0.6."""
        agent = SQLGenerationAgent()
        
        # Initial confidence
        confidence_0 = agent._calculate_confidence(0)
        assert confidence_0 == 0.9
        
        # After 1 retry
        confidence_1 = agent._calculate_confidence(1)
        assert confidence_1 == 0.75
        
        # After 2 retries (allow floating point tolerance)
        confidence_2 = agent._calculate_confidence(2)
        assert abs(confidence_2 - 0.6) < 0.01
        
        # After 3 retries (should not happen, but test boundary)
        confidence_3 = agent._calculate_confidence(3)
        assert abs(confidence_3 - 0.45) < 0.01


class TestSQLGenerationAgentTokenLogging:
    """Test token usage logging for cost tracking."""
    
    @patch('agents.sql_generation.ai_client')
    def test_token_usage_logged(self, mock_ai_client):
        """Verification: Token usage is logged for cost tracking."""
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="SELECT COUNT(*) FROM iso_tank LIMIT 100;"))]
        mock_response.usage = Mock(prompt_tokens=100, completion_tokens=20, total_tokens=120)
        mock_ai_client.chat.completions.create.return_value = mock_response
        
        agent = SQLGenerationAgent()
        request = SQLGenerationRequest(
            question="How many ISO tanks?",
            db_schema=SAMPLE_SCHEMA
        )
        
        with patch.object(agent.logger, 'info') as mock_logger:
            response = agent.execute(request)
            
            # Verify token usage was logged
            log_calls = [str(call) for call in mock_logger.call_args_list]
            token_logged = any('token' in str(call).lower() for call in log_calls)
            assert token_logged is True


class TestSQLGenerationAgentSQLCleaning:
    """Test SQL cleaning methods."""
    
    def test_clean_sql_removes_markdown(self):
        """Verify SQL cleaning removes markdown code blocks."""
        agent = SQLGenerationAgent()
        
        sql_with_markdown = "```sql\nSELECT * FROM iso_tank;\n```"
        cleaned = agent._clean_sql(sql_with_markdown)
        
        assert "```" not in cleaned
        assert "SELECT * FROM iso_tank" in cleaned
    
    def test_clean_sql_adds_semicolon(self):
        """Verify SQL cleaning adds semicolon if missing."""
        agent = SQLGenerationAgent()
        
        sql_without_semicolon = "SELECT * FROM iso_tank"
        cleaned = agent._clean_sql(sql_without_semicolon)
        
        assert cleaned.endswith(';')
    
    def test_ensure_limit_adds_limit(self):
        """Verify LIMIT clause is added if missing."""
        agent = SQLGenerationAgent()
        
        sql_without_limit = "SELECT * FROM iso_tank;"
        with_limit = agent._ensure_limit(sql_without_limit)
        
        assert "LIMIT" in with_limit.upper()
    
    def test_ensure_limit_preserves_existing(self):
        """Verify existing LIMIT clause is preserved."""
        agent = SQLGenerationAgent()
        
        sql_with_limit = "SELECT * FROM iso_tank LIMIT 50;"
        result = agent._ensure_limit(sql_with_limit)
        
        assert "LIMIT 50" in result
        assert result.count("LIMIT") == 1


class TestSQLGenerationAgentIntegration:
    """Integration tests for self-critique catching specific error types."""
    
    @patch('agents.sql_generation.ai_client')
    def test_self_critique_catches_column_hallucination(self, mock_ai_client):
        """Integration: Self-critique catches column hallucination (e.g., 'idastank_count' → 'id')."""
        # First attempt: hallucinated column
        mock_response_1 = Mock()
        mock_response_1.choices = [Mock(message=Mock(content="SELECT idastank_count FROM iso_tank LIMIT 100;"))]
        mock_response_1.usage = Mock(prompt_tokens=100, completion_tokens=20, total_tokens=120)
        
        # Second attempt: corrected
        mock_response_2 = Mock()
        mock_response_2.choices = [Mock(message=Mock(content="SELECT id FROM iso_tank LIMIT 100;"))]
        mock_response_2.usage = Mock(prompt_tokens=100, completion_tokens=20, total_tokens=120)
        
        mock_ai_client.chat.completions.create.side_effect = [mock_response_1, mock_response_2]
        
        agent = SQLGenerationAgent()
        request = SQLGenerationRequest(
            question="Show me tank IDs",
            db_schema=SAMPLE_SCHEMA
        )
        
        response = agent.execute(request)
        
        assert response.success is True
        assert "idastank_count" not in response.sql
        assert response.retry_count == 1
    
    @patch('agents.sql_generation.ai_client')
    def test_self_critique_catches_table_error(self, mock_ai_client):
        """Integration: Self-critique catches table name errors."""
        # First attempt: wrong table name
        mock_response_1 = Mock()
        mock_response_1.choices = [Mock(message=Mock(content="SELECT * FROM tanks LIMIT 100;"))]
        mock_response_1.usage = Mock(prompt_tokens=100, completion_tokens=20, total_tokens=120)
        
        # Second attempt: corrected
        mock_response_2 = Mock()
        mock_response_2.choices = [Mock(message=Mock(content="SELECT * FROM iso_tank LIMIT 100;"))]
        mock_response_2.usage = Mock(prompt_tokens=100, completion_tokens=20, total_tokens=120)
        
        mock_ai_client.chat.completions.create.side_effect = [mock_response_1, mock_response_2]
        
        agent = SQLGenerationAgent()
        request = SQLGenerationRequest(
            question="Show me all tanks",
            db_schema=SAMPLE_SCHEMA
        )
        
        response = agent.execute(request)
        
        assert response.success is True
        assert "iso_tank" in response.sql
        assert response.retry_count == 1
    
    @patch('agents.sql_generation.ai_client')
    def test_self_critique_catches_missing_join(self, mock_ai_client):
        """Integration: Self-critique catches missing JOIN conditions."""
        # First attempt: missing ON clause
        mock_response_1 = Mock()
        mock_response_1.choices = [Mock(message=Mock(content="SELECT * FROM iso_tank JOIN vehicle_in LIMIT 100;"))]
        mock_response_1.usage = Mock(prompt_tokens=100, completion_tokens=20, total_tokens=120)
        
        # Second attempt: corrected with ON clause
        mock_response_2 = Mock()
        mock_response_2.choices = [Mock(message=Mock(content="SELECT * FROM iso_tank JOIN vehicle_in ON iso_tank.vehicle_in_id = vehicle_in.id LIMIT 100;"))]
        mock_response_2.usage = Mock(prompt_tokens=100, completion_tokens=20, total_tokens=120)
        
        mock_ai_client.chat.completions.create.side_effect = [mock_response_1, mock_response_2]
        
        agent = SQLGenerationAgent()
        request = SQLGenerationRequest(
            question="Show me tanks with vehicle in data",
            db_schema=SAMPLE_SCHEMA
        )
        
        response = agent.execute(request)
        
        assert response.success is True
        assert "ON" in response.sql
        assert response.retry_count == 1
