"""
Tests for Query Refinement Agent

Test coverage:
- Happy path: Temporal resolution and entity mapping
- Edge case: Ambiguous queries requiring clarification
- Error path: AI provider errors
- Integration: Business glossary usage
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from agents.query_refinement import QueryRefinementAgent
from agents.models.refinement_models import RefinementRequest, RefinementResponse
from agents.base import AgentExecutionError


class TestQueryRefinementAgent:
    """Test suite for QueryRefinementAgent."""
    
    @pytest.fixture
    def agent(self):
        """Create QueryRefinementAgent instance with mocked AI client."""
        with patch('agents.query_refinement.ai_client') as mock_ai_client:
            agent = QueryRefinementAgent()
            agent.ai_client = mock_ai_client
            return agent
    
    @pytest.fixture
    def sample_business_glossary(self):
        """Sample business glossary for testing."""
        return {
            "temporal_terms": {
                "this_month": "WHERE created_at >= DATE_TRUNC('month', CURRENT_DATE)",
                "last_quarter": "WHERE created_at >= DATE_TRUNC('quarter', CURRENT_DATE - INTERVAL '3 months')",
                "today": "WHERE DATE(created_at) = CURRENT_DATE"
            },
            "entity_mappings": {
                "clients": "vehicle_in.croyance_client_name",
                "tanks": "iso_tank table (for ISO tanks) or service_tank table (for service tanks)",
                "tank_status": "iso_tank_status or service_tank_status"
            }
        }
    
    @pytest.fixture
    def mock_ai_response(self):
        """Mock AI response for testing."""
        mock_response = Mock()
        mock_choice = Mock()
        mock_choice.message.content = "Retrieve count of ISO tanks grouped by croyance_client_name WHERE created_at >= DATE_TRUNC('month', CURRENT_DATE) ORDER BY count DESC"
        mock_response.choices = [mock_choice]
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 150
        mock_response.usage.completion_tokens = 50
        mock_response.usage.total_tokens = 200
        return mock_response
    
    # Happy path tests
    
    def test_temporal_resolution_this_month(self, agent, sample_business_glossary, mock_ai_response):
        """Test temporal resolution for 'this month'."""
        agent.ai_client.chat.completions.create.return_value = mock_ai_response
        
        request = RefinementRequest(
            question="Which clients have the most tanks this month?",
            db_schema="Table: iso_tank",
            business_glossary=sample_business_glossary,
            current_datetime=datetime(2024, 3, 15, 10, 30, 0)
        )
        
        response = agent.execute(request)
        
        assert response.success is True
        assert "DATE_TRUNC('month', CURRENT_DATE)" in response.refined_query
        assert "croyance_client_name" in response.refined_query
        assert response.confidence >= 0.8
        assert len(response.clarification_questions) == 0
    
    def test_entity_mapping_tanks(self, agent, sample_business_glossary):
        """Test entity mapping for 'tanks'."""
        mock_response = Mock()
        mock_choice = Mock()
        mock_choice.message.content = "Retrieve tank_number and iso_tank_status from iso_tank table"
        mock_response.choices = [mock_choice]
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 30
        mock_response.usage.total_tokens = 130
        agent.ai_client.chat.completions.create.return_value = mock_response
        
        request = RefinementRequest(
            question="Show me tanks",
            db_schema="Table: iso_tank",
            business_glossary=sample_business_glossary
        )
        
        response = agent.execute(request)
        
        assert response.success is True
        assert "iso_tank" in response.refined_query
        assert response.confidence >= 0.7
    
    def test_temporal_resolution_today(self, agent, sample_business_glossary):
        """Test temporal resolution for 'today'."""
        mock_response = Mock()
        mock_choice = Mock()
        mock_choice.message.content = "Retrieve COUNT(*) from iso_tank WHERE DATE(created_at) = CURRENT_DATE"
        mock_response.choices = [mock_choice]
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 120
        mock_response.usage.completion_tokens = 40
        mock_response.usage.total_tokens = 160
        agent.ai_client.chat.completions.create.return_value = mock_response
        
        request = RefinementRequest(
            question="How many tanks came in today?",
            db_schema="Table: iso_tank",
            business_glossary=sample_business_glossary
        )
        
        response = agent.execute(request)
        
        assert response.success is True
        assert "DATE(created_at) = CURRENT_DATE" in response.refined_query
        assert "COUNT(*)" in response.refined_query
        assert response.confidence >= 0.8
    
    def test_last_quarter_resolution(self, agent, sample_business_glossary):
        """Test temporal resolution for 'last quarter'."""
        mock_response = Mock()
        mock_choice = Mock()
        mock_choice.message.content = "Retrieve tanks WHERE created_at >= DATE_TRUNC('quarter', CURRENT_DATE - INTERVAL '3 months')"
        mock_response.choices = [mock_choice]
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 140
        mock_response.usage.completion_tokens = 45
        mock_response.usage.total_tokens = 185
        agent.ai_client.chat.completions.create.return_value = mock_response
        
        request = RefinementRequest(
            question="Show me tanks from last quarter",
            db_schema="Table: iso_tank",
            business_glossary=sample_business_glossary
        )
        
        response = agent.execute(request)
        
        assert response.success is True
        assert "DATE_TRUNC('quarter', CURRENT_DATE - INTERVAL '3 months')" in response.refined_query
        assert response.confidence >= 0.8
    
    # Edge case tests - Ambiguous queries
    
    def test_ambiguous_query_with_clarification(self, agent, sample_business_glossary):
        """Test ambiguous query requiring clarification."""
        mock_response = Mock()
        mock_choice = Mock()
        mock_choice.message.content = "[CLARIFICATION_NEEDED] Do you mean best by revenue or by quantity? What time period should be considered?"
        mock_response.choices = [mock_choice]
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 110
        mock_response.usage.completion_tokens = 25
        mock_response.usage.total_tokens = 135
        agent.ai_client.chat.completions.create.return_value = mock_response
        
        request = RefinementRequest(
            question="Show me the best products",
            db_schema="Table: iso_tank",
            business_glossary=sample_business_glossary
        )
        
        response = agent.execute(request)
        
        assert response.success is True
        assert response.confidence == 0.5
        assert len(response.clarification_questions) > 0
        assert "revenue" in response.clarification_questions[0] or "quantity" in response.clarification_questions[0]
    
    def test_query_with_no_business_terms(self, agent, sample_business_glossary):
        """Test query with no business terms (should pass through with minimal changes)."""
        mock_response = Mock()
        mock_choice = Mock()
        mock_choice.message.content = "Retrieve all records from unknown_table"
        mock_response.choices = [mock_choice]
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 90
        mock_response.usage.completion_tokens = 20
        mock_response.usage.total_tokens = 110
        agent.ai_client.chat.completions.create.return_value = mock_response
        
        request = RefinementRequest(
            question="Show me unknown table data",
            db_schema="Table: unknown_table",
            business_glossary=sample_business_glossary
        )
        
        response = agent.execute(request)
        
        assert response.success is True
        assert response.confidence >= 0.6
        assert len(response.clarification_questions) == 0
    
    # Error path tests
    
    def test_ai_provider_error(self, agent, sample_business_glossary):
        """Test AI provider error handling."""
        agent.ai_client.chat.completions.create.side_effect = Exception("API rate limit exceeded")
        
        request = RefinementRequest(
            question="Show me tanks",
            db_schema="Table: iso_tank",
            business_glossary=sample_business_glossary
        )
        
        response = agent.execute(request)
        
        assert response.success is False
        assert response.confidence == 0.0
        assert "Query refinement failed" in response.error
        assert "API rate limit exceeded" in response.error
    
    def test_empty_ai_response(self, agent, sample_business_glossary):
        """Test handling of empty AI response."""
        mock_response = Mock()
        mock_choice = Mock()
        mock_choice.message.content = ""
        mock_response.choices = [mock_choice]
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 0
        mock_response.usage.total_tokens = 100
        agent.ai_client.chat.completions.create.return_value = mock_response
        
        request = RefinementRequest(
            question="Show me tanks",
            db_schema="Table: iso_tank",
            business_glossary=sample_business_glossary
        )
        
        response = agent.execute(request)
        
        assert response.success is True
        assert response.refined_query == ""
        assert response.confidence == 0.5  # Low confidence for empty response
    
    # Integration tests
    
    def test_complex_query_with_multiple_terms(self, agent, sample_business_glossary):
        """Test complex query with multiple business terms."""
        mock_response = Mock()
        mock_choice = Mock()
        mock_choice.message.content = "Retrieve COUNT(*) as tank_count FROM iso_tank it JOIN vehicle_in vi ON it.vehicle_in_id = vi.id WHERE it.created_at >= DATE_TRUNC('month', CURRENT_DATE) GROUP BY vi.croyance_client_name ORDER BY tank_count DESC"
        mock_response.choices = [mock_choice]
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 200
        mock_response.usage.completion_tokens = 80
        mock_response.usage.total_tokens = 280
        agent.ai_client.chat.completions.create.return_value = mock_response
        
        request = RefinementRequest(
            question="Which clients have the most tanks this month?",
            db_schema="Table: iso_tank, vehicle_in",
            business_glossary=sample_business_glossary
        )
        
        response = agent.execute(request)
        
        assert response.success is True
        assert "DATE_TRUNC('month', CURRENT_DATE)" in response.refined_query
        assert "croyance_client_name" in response.refined_query
        assert "COUNT(*)" in response.refined_query
        assert "GROUP BY" in response.refined_query
        assert "ORDER BY" in response.refined_query
        assert response.confidence >= 0.9  # High confidence for complex transformation
    
    def test_metadata_includes_execution_info(self, agent, sample_business_glossary, mock_ai_response):
        """Test response metadata includes execution information."""
        agent.ai_client.chat.completions.create.return_value = mock_ai_response
        
        request = RefinementRequest(
            question="Show me tanks from this month",
            db_schema="Table: iso_tank",
            business_glossary=sample_business_glossary
        )
        
        response = agent.execute(request)
        
        assert response.success is True
        assert response.metadata is not None
        assert "execution_time" in response.metadata
        assert "original_question" in response.metadata
        assert "glossary_terms_used" in response.metadata
        assert response.metadata["original_question"] == "Show me tanks from this month"
        assert response.metadata["glossary_terms_used"] >= 1  # Should find "this month" and "tanks"
    
    def test_confidence_scoring_patterns(self, agent, sample_business_glossary):
        """Test confidence scoring for different refinement patterns."""
        # High confidence: temporal + entity + aggregation
        mock_response_high = Mock()
        mock_choice_high = Mock()
        mock_choice_high.message.content = "Retrieve COUNT(*) FROM iso_tank WHERE created_at >= DATE_TRUNC('month', CURRENT_DATE) GROUP BY croyance_client_name ORDER BY count DESC"
        mock_response_high.choices = [mock_choice_high]
        mock_response_high.usage = Mock()
        mock_response_high.usage.prompt_tokens = 150
        mock_response_high.usage.completion_tokens = 60
        mock_response_high.usage.total_tokens = 210
        
        # Medium confidence: some transformation
        mock_response_medium = Mock()
        mock_choice_medium = Mock()
        mock_choice_medium.message.content = "Retrieve tank_number FROM iso_tank WHERE status = 'active'"
        mock_response_medium.choices = [mock_choice_medium]
        mock_response_medium.usage = Mock()
        mock_response_medium.usage.prompt_tokens = 100
        mock_response_medium.usage.completion_tokens = 30
        mock_response_medium.usage.total_tokens = 130
        
        # Low confidence: no transformation
        mock_response_low = Mock()
        mock_choice_low = Mock()
        mock_choice_low.message.content = "Show me tanks"  # Same as input
        mock_response_low.choices = [mock_choice_low]
        mock_response_low.usage = Mock()
        mock_response_low.usage.prompt_tokens = 80
        mock_response_low.usage.completion_tokens = 10
        mock_response_low.usage.total_tokens = 90
        
        # Test high confidence
        agent.ai_client.chat.completions.create.return_value = mock_response_high
        request_high = RefinementRequest(
            question="Which clients have the most tanks this month?",
            db_schema="Table: iso_tank",
            business_glossary=sample_business_glossary
        )
        response_high = agent.execute(request_high)
        
        # Test medium confidence
        agent.ai_client.chat.completions.create.return_value = mock_response_medium
        request_medium = RefinementRequest(
            question="Show me active tanks",
            db_schema="Table: iso_tank",
            business_glossary=sample_business_glossary
        )
        response_medium = agent.execute(request_medium)
        
        # Test low confidence
        agent.ai_client.chat.completions.create.return_value = mock_response_low
        request_low = RefinementRequest(
            question="Show me tanks",
            db_schema="Table: iso_tank",
            business_glossary=sample_business_glossary
        )
        response_low = agent.execute(request_low)
        
        # Verify confidence ordering
        assert response_high.confidence > response_medium.confidence > response_low.confidence
        assert response_high.confidence >= 0.9
        assert response_medium.confidence >= 0.6
        assert response_low.confidence == 0.5
    
    def test_anthropic_sdk_support(self, agent, sample_business_glossary):
        """Test Anthropic SDK support."""
        # Mock Anthropic response format
        mock_response = Mock()
        mock_content = Mock()
        mock_content.text = "Retrieve tanks WHERE created_at >= DATE_TRUNC('month', CURRENT_DATE)"
        mock_response.content = [mock_content]
        mock_response.usage = Mock()
        mock_response.usage.input_tokens = 120
        mock_response.usage.output_tokens = 40
        
        # Create a mock Anthropic client
        mock_anthropic_client = Mock()
        mock_anthropic_client.messages.create.return_value = mock_response
        
        # Temporarily change SDK type and client
        original_sdk_type = agent.sdk_type
        original_ai_client = agent.ai_client
        agent.sdk_type = "anthropic"
        agent.ai_client = mock_anthropic_client
        
        try:
            request = RefinementRequest(
                question="Show me tanks from this month",
                db_schema="Table: iso_tank",
                business_glossary=sample_business_glossary
            )
            
            response = agent.execute(request)
            
            assert response.success is True
            assert "DATE_TRUNC('month', CURRENT_DATE)" in response.refined_query
            assert response.confidence >= 0.8
        finally:
            # Restore original SDK type and client
            agent.sdk_type = original_sdk_type
            agent.ai_client = original_ai_client
    
    def test_business_glossary_loading(self, agent):
        """Test business glossary is loaded correctly."""
        assert agent.business_glossary is not None
        assert "temporal_terms" in agent.business_glossary
        assert "entity_mappings" in agent.business_glossary
        assert len(agent.temporal_terms) > 0
        assert len(agent.entity_mappings) > 0
    
    def test_glossary_terms_counting(self, agent, sample_business_glossary):
        """Test counting of glossary terms in questions."""
        # Question with multiple terms
        count_multiple = agent._count_glossary_terms_used(
            "Which clients have the most tanks this month?",
            sample_business_glossary
        )
        assert count_multiple >= 2  # "clients", "tanks", "this month"
        
        # Question with no terms
        count_none = agent._count_glossary_terms_used(
            "Show me unknown data",
            sample_business_glossary
        )
        assert count_none == 0
        
        # Question with one term
        count_one = agent._count_glossary_terms_used(
            "Show me tanks",
            sample_business_glossary
        )
        assert count_one >= 1  # "tanks"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])