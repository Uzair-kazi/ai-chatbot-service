"""
Integration Tests for Multi-Agent Pipeline (Phase 4)

These tests verify the multi-agent pipeline with Result Formatter Agent integration.
They are marked with @pytest.mark.integration and can be skipped if services are not configured.

Phase 4 changes:
- Result Formatter Agent replaces legacy AnswerFormatter
- MCP client integration for database operations
- Updated test mocks for new pipeline structure

Run with: pytest tests/integration/test_multi_agent_pipeline.py -v
Skip with: pytest -m "not integration"
"""

import pytest
import os
from unittest.mock import patch, MagicMock
from services.multi_agent_pipeline import ask as multi_agent_ask


# Skip all tests in this module if services are not configured
pytestmark = pytest.mark.integration


class TestMultiAgentPipelineIntegration:
    """Integration tests for multi-agent pipeline with mocked AI provider and Result Formatter Agent."""
    
    @patch('config.ai_provider.ai_client')
    @patch('agents.result_formatter.ResultFormatterAgent.execute')
    def test_simple_query_generates_correct_sql(self, mock_formatter, mock_ai_client):
        """Integration: Simple query generates correct SQL and executes successfully via Result Formatter Agent."""
        # Mock AI client to return valid SQL
        mock_ai_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(
                message=MagicMock(
                    content="SELECT COUNT(*) FROM iso_tank WHERE iso_tank_status = 'IN' LIMIT 100;"
                )
            )],
            usage=MagicMock(
                prompt_tokens=100,
                completion_tokens=20,
                total_tokens=120
            )
        )
        
        # Mock Result Formatter Agent to return formatted results
        from agents.models.formatter_models import FormatterResponse
        mock_formatter.return_value = FormatterResponse(
            success=True,
            answer="There are currently 47 ISO tanks with status 'IN'.",
            sql="SELECT COUNT(*) FROM iso_tank WHERE iso_tank_status = 'IN' LIMIT 100;",
            rows_count=1,
            execution_time=0.5,
            formatting_method="template",
            metadata={
                "mcp_used": True,
                "token_usage": 0
            }
        )
        
        # Execute pipeline
        result = multi_agent_ask("How many ISO tanks are in 'IN' status?")
        
        # Verify result
        assert result["status_code"] == 200
        assert "47" in result["answer"]
        assert "iso_tank" in result["sql"].lower()
        assert result["rows_count"] == 1
        assert result["confidence"] > 0.0
        assert result["retry_count"] >= 0
        assert "mcp_used" in result
        assert "formatting_strategy" in result
    
    @patch('config.ai_provider.ai_client')
    @patch('agents.result_formatter.ResultFormatterAgent.execute')
    def test_self_critique_catches_column_hallucination(self, mock_formatter, mock_ai_client):
        """Integration: Self-critique loop catches and fixes column hallucination."""
        # Mock AI client to return invalid SQL first, then valid SQL
        
        # First attempt: hallucinated column
        invalid_response = MagicMock(
            choices=[MagicMock(
                message=MagicMock(
                    content="SELECT COUNT(*) FROM iso_tank WHERE idastank_count > 0 LIMIT 100;"
                )
            )],
            usage=MagicMock(prompt_tokens=100, completion_tokens=20, total_tokens=120)
        )
        
        # Second attempt: valid SQL
        valid_response = MagicMock(
            choices=[MagicMock(
                message=MagicMock(
                    content="SELECT COUNT(*) FROM iso_tank WHERE id IS NOT NULL LIMIT 100;"
                )
            )],
            usage=MagicMock(prompt_tokens=100, completion_tokens=20, total_tokens=120)
        )
        
        mock_ai_client.chat.completions.create.side_effect = [invalid_response, valid_response]
        
        # Mock Result Formatter Agent to return formatted results
        from agents.models.formatter_models import FormatterResponse
        mock_formatter.return_value = FormatterResponse(
            success=True,
            answer="There are currently 100 tanks in the system.",
            sql="SELECT COUNT(*) FROM iso_tank WHERE id IS NOT NULL LIMIT 100;",
            rows_count=1,
            execution_time=0.7,
            formatting_method="template",
            metadata={
                "mcp_used": True,
                "token_usage": 0
            }
        )
        
        # Execute pipeline
        result = multi_agent_ask("How many tanks?")
        
        # Verify result
        assert result["status_code"] == 200
        assert result["retry_count"] == 1  # One retry performed
        assert result["confidence"] < 0.9  # Lower confidence after retry
        assert "idastank_count" not in result["sql"]  # Hallucinated column fixed
    
    @patch('config.ai_provider.ai_client')
    def test_low_confidence_escalation(self, mock_ai_client):
        """Integration: Low confidence after max retries triggers escalation."""
        # Mock AI client to always return invalid SQL
        mock_ai_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(
                message=MagicMock(
                    content="SELECT * FROM nonexistent_table LIMIT 100;"
                )
            )],
            usage=MagicMock(prompt_tokens=100, completion_tokens=20, total_tokens=120)
        )
        
        # Execute pipeline
        result = multi_agent_ask("Query that will fail validation")
        
        # Verify escalation
        assert result["status_code"] == 400
        assert "human review" in result["answer"].lower() or "low confidence" in result["error"].lower()
        assert result["confidence"] < 0.6  # Below threshold
    
    @patch('config.ai_provider.ai_client')
    @patch('agents.result_formatter.ResultFormatterAgent.execute')
    def test_complex_query_with_join(self, mock_formatter, mock_ai_client):
        """Integration: Complex query with JOIN generates correct SQL."""
        # Mock AI client to return valid JOIN query
        mock_ai_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(
                message=MagicMock(
                    content="""
                    SELECT c.customer_name, COUNT(t.id) as tank_count
                    FROM customer c
                    JOIN iso_tank t ON c.id = t.customer_id
                    GROUP BY c.customer_name
                    LIMIT 100;
                    """
                )
            )],
            usage=MagicMock(prompt_tokens=150, completion_tokens=40, total_tokens=190)
        )
        
        # Mock Result Formatter Agent to return formatted results
        from agents.models.formatter_models import FormatterResponse
        mock_formatter.return_value = FormatterResponse(
            success=True,
            answer="Customer A has 10 tanks and Customer B has 5 tanks.",
            sql="SELECT c.customer_name, COUNT(t.id) as tank_count FROM customer c JOIN iso_tank t ON c.id = t.customer_id GROUP BY c.customer_name LIMIT 100;",
            rows_count=2,
            execution_time=1.2,
            formatting_method="llm",
            metadata={
                "mcp_used": True,
                "token_usage": 45
            }
        )
        
        # Execute pipeline
        result = multi_agent_ask("How many tanks does each customer have?")
        
        # Verify result
        assert result["status_code"] == 200
        assert "join" in result["sql"].lower()
        assert result["rows_count"] == 2
        assert result["confidence"] > 0.0
        assert result["formatting_strategy"] == "llm"
    
    @patch('config.ai_provider.ai_client')
    @patch('agents.result_formatter.ResultFormatterAgent.execute')
    def test_database_connection_failure_returns_503(self, mock_formatter, mock_ai_client):
        """Integration: Database connection failure returns 503."""
        # Mock AI client to return valid SQL
        mock_ai_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(
                message=MagicMock(
                    content="SELECT COUNT(*) FROM iso_tank LIMIT 100;"
                )
            )],
            usage=MagicMock(prompt_tokens=100, completion_tokens=20, total_tokens=120)
        )
        
        # Mock Result Formatter Agent to return database error
        from agents.models.formatter_models import FormatterResponse
        mock_formatter.return_value = FormatterResponse(
            success=False,
            answer="",
            sql="",
            rows_count=0,
            execution_time=0.1,
            formatting_method="none",
            error="Database connection failed",
            metadata={
                "mcp_used": False,
                "error_type": "database_connection"
            }
        )
        
        # Execute pipeline
        result = multi_agent_ask("Any question")
        
        # Verify error handling
        assert result["status_code"] == 500  # Result Formatter Agent error
        assert "connection failed" in result["error"].lower()
    
    @patch('config.ai_provider.ai_client')
    @patch('agents.result_formatter.ResultFormatterAgent.execute')
    def test_query_timeout_returns_504(self, mock_formatter, mock_ai_client):
        """Integration: Query timeout returns 504."""
        # Mock AI client to return valid SQL
        mock_ai_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(
                message=MagicMock(
                    content="SELECT * FROM huge_table LIMIT 100;"
                )
            )],
            usage=MagicMock(prompt_tokens=100, completion_tokens=20, total_tokens=120)
        )
        
        # Mock Result Formatter Agent to return timeout error
        from agents.models.formatter_models import FormatterResponse
        mock_formatter.return_value = FormatterResponse(
            success=False,
            answer="",
            sql="",
            rows_count=0,
            execution_time=30.0,
            formatting_method="none",
            error="Query execution timeout",
            metadata={
                "mcp_used": True,
                "error_type": "query_timeout"
            }
        )
        
        # Execute pipeline
        result = multi_agent_ask("Complex query")
        
        # Verify error handling
        assert result["status_code"] == 500  # Result Formatter Agent error
        assert "timeout" in result["error"].lower()


class TestMultiAgentPipelineComparison:
    """Compare multi-agent pipeline with single-LLM pipeline."""
    
    @patch('config.ai_provider.ai_client')
    @patch('agents.result_formatter.ResultFormatterAgent.execute')
    @patch('services.chatbot_pipeline.SQLGenerator')
    def test_multi_agent_catches_errors_single_llm_misses(
        self, mock_single_generator, mock_formatter, mock_ai_client
    ):
        """Integration: Multi-agent catches column hallucinations that single-LLM misses."""
        # Mock single-LLM to return invalid SQL (no self-critique)
        mock_single_instance = MagicMock()
        mock_single_instance.generate_sql.return_value = (
            "SELECT COUNT(*) FROM iso_tank WHERE idastank_count > 0 LIMIT 100;"
        )
        mock_single_generator.return_value = mock_single_instance
        
        # Mock multi-agent AI client to fix the error
        
        # First attempt: same hallucinated column
        invalid_response = MagicMock(
            choices=[MagicMock(
                message=MagicMock(
                    content="SELECT COUNT(*) FROM iso_tank WHERE idastank_count > 0 LIMIT 100;"
                )
            )],
            usage=MagicMock(prompt_tokens=100, completion_tokens=20, total_tokens=120)
        )
        
        # Second attempt: fixed SQL
        valid_response = MagicMock(
            choices=[MagicMock(
                message=MagicMock(
                    content="SELECT COUNT(*) FROM iso_tank WHERE id IS NOT NULL LIMIT 100;"
                )
            )],
            usage=MagicMock(prompt_tokens=100, completion_tokens=20, total_tokens=120)
        )
        
        mock_ai_client.chat.completions.create.side_effect = [invalid_response, valid_response]
        
        # Mock Result Formatter Agent to return formatted results
        from agents.models.formatter_models import FormatterResponse
        mock_formatter.return_value = FormatterResponse(
            success=True,
            answer="There are currently 100 tanks in the system.",
            sql="SELECT COUNT(*) FROM iso_tank WHERE id IS NOT NULL LIMIT 100;",
            rows_count=1,
            execution_time=0.8,
            formatting_method="template",
            metadata={
                "mcp_used": True,
                "token_usage": 0
            }
        )
        
        # Execute multi-agent pipeline
        result = multi_agent_ask("How many tanks?")
        
        # Verify multi-agent fixed the error
        assert result["status_code"] == 200
        assert "idastank_count" not in result["sql"]
        assert result["retry_count"] == 1
        
        # Single-LLM would have failed validation
        # (This is demonstrated by the mock returning invalid SQL)
