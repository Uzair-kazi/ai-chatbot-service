"""
Tests for Orchestrator Agent

Test scenarios:
- Happy path: Route simple query to SQL Generation agent → return successful response
- Happy path: Route complex query to SQL Generation agent → return successful response
- Error path: SQL Generation returns low_confidence=True → escalate with clear error message
- Error path: SQL Generation raises exception → catch and return error response
- Edge case: Empty question → validate before routing
- Integration: Orchestrator correctly passes schema to SQL Generation agent
- Integration: Orchestrator preserves confidence scores from SQL Generation agent
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from agents.orchestrator import OrchestratorAgent
from agents.base import AgentValidationError, AgentExecutionError
from agents.models.agent_models import AgentRequest, AgentResponse
from agents.models.query_models import SQLGenerationResponse


class TestOrchestratorAgent:
    """Test suite for OrchestratorAgent."""
    
    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator instance for testing."""
        with patch('agents.orchestrator.SQLGenerationAgent'), \
             patch('agents.orchestrator.SchemaIntelligenceAgent'):
            return OrchestratorAgent()
    
    @pytest.fixture
    def valid_request(self):
        """Create valid agent request."""
        return AgentRequest(
            question="How many ISO tanks are in 'IN' status?",
            db_schema="Table: iso_tank\n  - id: uuid\n  - iso_tank_status: varchar"
        )
    
    # Happy path tests
    
    def test_route_simple_query_success(self, orchestrator, valid_request):
        """
        Happy path: Route simple query through Schema Intelligence → SQL Generation → return successful response.
        """
        # Mock Schema Intelligence response
        from agents.models.schema_models import SchemaIntelligenceResponse
        mock_schema_response = SchemaIntelligenceResponse(
            success=True,
            pruned_schema="Table: iso_tank\n  - id: uuid\n  - iso_tank_status: varchar",
            selected_tables=["iso_tank"],
            join_hints=[],
            entity_matches=[],
            confidence=0.9,
            metadata={"cache_hit": False, "token_reduction": 0}
        )
        
        # Mock SQL agent response
        mock_sql_response = SQLGenerationResponse(
            success=True,
            sql="SELECT COUNT(*) FROM iso_tank WHERE iso_tank_status = 'IN' LIMIT 100;",
            validation_issues=[],
            retry_count=0,
            confidence=0.9,
            metadata={"execution_time": 1.23}
        )
        
        orchestrator.schema_intelligence_agent = Mock()
        orchestrator.schema_intelligence_agent.execute.return_value = mock_schema_response
        orchestrator.sql_agent = Mock()
        orchestrator.sql_agent.execute.return_value = mock_sql_response
        
        # Execute
        response = orchestrator.execute(valid_request)
        
        # Verify
        assert response.success is True
        assert response.confidence == 0.9
        assert response.data is not None
        assert response.data["sql"] == "SELECT COUNT(*) FROM iso_tank WHERE iso_tank_status = 'IN' LIMIT 100;"
        assert response.data["retry_count"] == 0
        assert response.error is None
        assert response.metadata["agent"] == "SQLGenerationAgent"
        assert response.metadata["routing_strategy"] == "schema_intelligence"
        assert response.metadata["schema_intelligence_success"] is True
        
        # Verify Schema Intelligence was called
        orchestrator.schema_intelligence_agent.execute.assert_called_once()
        
        # Verify SQL agent was called correctly
        orchestrator.sql_agent.execute.assert_called_once()
        call_args = orchestrator.sql_agent.execute.call_args[0][0]
        assert call_args.question == valid_request.question
        assert call_args.max_retries == 2
        assert call_args.temperature == 0.1
    
    def test_route_complex_query_success(self, orchestrator):
        """
        Happy path: Route complex query to SQL Generation agent → return successful response.
        """
        # Complex query with JOIN
        complex_request = AgentRequest(
            question="Show ISO tanks with their vehicle in and out times",
            db_schema=(
                "Table: iso_tank\n"
                "  - id: uuid\n"
                "  - vehicle_in_id: uuid\n"
                "  - vehicle_out_id: uuid\n"
                "Table: vehicle_in\n"
                "  - id: uuid\n"
                "  - created_at: timestamp\n"
                "Table: vehicle_out\n"
                "  - id: uuid\n"
                "  - created_at: timestamp"
            )
        )
        
        # Mock Schema Intelligence response
        from agents.models.schema_models import SchemaIntelligenceResponse
        mock_schema_response = SchemaIntelligenceResponse(
            success=True,
            pruned_schema=(
                "Table: iso_tank\n"
                "  - id: uuid\n"
                "  - vehicle_in_id: uuid\n"
                "  - vehicle_out_id: uuid\n"
                "Table: vehicle_in\n"
                "  - id: uuid\n"
                "  - created_at: timestamp\n"
                "Table: vehicle_out\n"
                "  - id: uuid\n"
                "  - created_at: timestamp"
            ),
            selected_tables=["iso_tank", "vehicle_in", "vehicle_out"],
            join_hints=[],
            entity_matches=[],
            confidence=0.9,
            metadata={"cache_hit": False, "token_reduction": 0}
        )
        
        # Mock SQL agent response
        mock_sql_response = SQLGenerationResponse(
            success=True,
            sql=(
                "SELECT it.id, vi.created_at as in_time, vo.created_at as out_time "
                "FROM iso_tank it "
                "JOIN vehicle_in vi ON it.vehicle_in_id = vi.id "
                "JOIN vehicle_out vo ON it.vehicle_out_id = vo.id "
                "LIMIT 100;"
            ),
            validation_issues=[],
            retry_count=1,  # Took 2 attempts
            confidence=0.75,
            metadata={"execution_time": 2.45}
        )
        
        orchestrator.schema_intelligence_agent = Mock()
        orchestrator.schema_intelligence_agent.execute.return_value = mock_schema_response
        orchestrator.sql_agent = Mock()
        orchestrator.sql_agent.execute.return_value = mock_sql_response
        
        # Execute
        response = orchestrator.execute(complex_request)
        
        # Verify
        assert response.success is True
        assert response.confidence == 0.75
        assert response.data is not None
        assert "JOIN" in response.data["sql"]
        assert response.data["retry_count"] == 1
        assert response.error is None
    
    # Error path tests
    
    def test_low_confidence_escalation(self, orchestrator, valid_request):
        """
        Error path: SQL Generation returns low_confidence → escalate with clear error message.
        """
        # Mock Schema Intelligence response
        from agents.models.schema_models import SchemaIntelligenceResponse
        mock_schema_response = SchemaIntelligenceResponse(
            success=True,
            pruned_schema="Table: iso_tank\n  - id: uuid\n  - iso_tank_status: varchar",
            selected_tables=["iso_tank"],
            join_hints=[],
            entity_matches=[],
            confidence=0.9,
            metadata={"cache_hit": False, "token_reduction": 0}
        )
        
        # Mock SQL agent response with low confidence
        mock_sql_response = SQLGenerationResponse(
            success=True,
            sql="SELECT * FROM iso_tank LIMIT 100;",
            validation_issues=["Column 'idastank_count' does not exist"],
            retry_count=3,  # Max retries
            confidence=0.45,  # Below threshold (0.6)
            metadata={"execution_time": 3.67}
        )
        
        orchestrator.schema_intelligence_agent = Mock()
        orchestrator.schema_intelligence_agent.execute.return_value = mock_schema_response
        orchestrator.sql_agent = Mock()
        orchestrator.sql_agent.execute.return_value = mock_sql_response
        
        # Execute
        response = orchestrator.execute(valid_request)
        
        # Verify escalation
        assert response.success is False
        assert response.confidence == 0.45
        assert response.error is not None
        assert "requires human review" in response.error
        assert "Low confidence" in response.error
        
        # Verify escalation metadata
        assert response.metadata["escalated"] is True
        assert "escalation_reason" in response.metadata
        assert "Low confidence" in response.metadata["escalation_reason"]
        
        # Verify escalation data includes agent attempt
        assert response.data is not None
        assert "agent_attempt" in response.data
        assert response.data["agent_attempt"]["confidence"] == 0.45
        assert response.data["original_question"] == valid_request.question
    
    def test_sql_generation_failure(self, orchestrator, valid_request):
        """
        Error path: SQL Generation returns failure → return error response.
        """
        # Mock Schema Intelligence response
        from agents.models.schema_models import SchemaIntelligenceResponse
        mock_schema_response = SchemaIntelligenceResponse(
            success=True,
            pruned_schema="Table: iso_tank\n  - id: uuid\n  - iso_tank_status: varchar",
            selected_tables=["iso_tank"],
            join_hints=[],
            entity_matches=[],
            confidence=0.9,
            metadata={"cache_hit": False, "token_reduction": 0}
        )
        
        # Mock SQL agent response with failure
        mock_sql_response = SQLGenerationResponse(
            success=False,
            sql=None,
            validation_issues=["Table 'nonexistent_table' does not exist"],
            retry_count=2,
            confidence=0.6,
            error="Failed to generate valid SQL after 3 attempts",
            metadata={"execution_time": 3.12}
        )
        
        orchestrator.schema_intelligence_agent = Mock()
        orchestrator.schema_intelligence_agent.execute.return_value = mock_schema_response
        orchestrator.sql_agent = Mock()
        orchestrator.sql_agent.execute.return_value = mock_sql_response
        
        # Execute
        response = orchestrator.execute(valid_request)
        
        # Verify error response
        assert response.success is False
        assert response.confidence == 0.6
        assert response.error is not None
        assert "Failed to generate valid SQL" in response.error
        assert response.data is None
    
    def test_sql_agent_raises_validation_error(self, orchestrator, valid_request):
        """
        Error path: SQL Generation raises AgentValidationError → catch and return error response.
        """
        # Mock Schema Intelligence response
        from agents.models.schema_models import SchemaIntelligenceResponse
        mock_schema_response = SchemaIntelligenceResponse(
            success=True,
            pruned_schema="Table: iso_tank\n  - id: uuid\n  - iso_tank_status: varchar",
            selected_tables=["iso_tank"],
            join_hints=[],
            entity_matches=[],
            confidence=0.9,
            metadata={"cache_hit": False, "token_reduction": 0}
        )
        
        # Mock SQL agent to raise validation error
        orchestrator.schema_intelligence_agent = Mock()
        orchestrator.schema_intelligence_agent.execute.return_value = mock_schema_response
        orchestrator.sql_agent = Mock()
        orchestrator.sql_agent.execute.side_effect = AgentValidationError("Invalid schema format")
        
        # Execute
        response = orchestrator.execute(valid_request)
        
        # Verify error handling
        assert response.success is False
        assert response.confidence == 0.0
        assert response.error is not None
        assert "Validation error" in response.error
        assert "Invalid schema format" in response.error
        assert response.metadata["error_type"] == "validation_error"
    
    def test_sql_agent_raises_execution_error(self, orchestrator, valid_request):
        """
        Error path: SQL Generation raises AgentExecutionError → catch and return error response.
        """
        # Mock Schema Intelligence response
        from agents.models.schema_models import SchemaIntelligenceResponse
        mock_schema_response = SchemaIntelligenceResponse(
            success=True,
            pruned_schema="Table: iso_tank\n  - id: uuid\n  - iso_tank_status: varchar",
            selected_tables=["iso_tank"],
            join_hints=[],
            entity_matches=[],
            confidence=0.9,
            metadata={"cache_hit": False, "token_reduction": 0}
        )
        
        # Mock SQL agent to raise execution error
        orchestrator.schema_intelligence_agent = Mock()
        orchestrator.schema_intelligence_agent.execute.return_value = mock_schema_response
        orchestrator.sql_agent = Mock()
        orchestrator.sql_agent.execute.side_effect = AgentExecutionError("AI provider timeout")
        
        # Execute
        response = orchestrator.execute(valid_request)
        
        # Verify error handling
        assert response.success is False
        assert response.confidence == 0.0
        assert response.error is not None
        assert "Execution error" in response.error
        assert "AI provider timeout" in response.error
        assert response.metadata["error_type"] == "execution_error"
    
    def test_unexpected_exception(self, orchestrator, valid_request):
        """
        Error path: Unexpected exception → catch and return error response.
        """
        # Mock Schema Intelligence response
        from agents.models.schema_models import SchemaIntelligenceResponse
        mock_schema_response = SchemaIntelligenceResponse(
            success=True,
            pruned_schema="Table: iso_tank\n  - id: uuid\n  - iso_tank_status: varchar",
            selected_tables=["iso_tank"],
            join_hints=[],
            entity_matches=[],
            confidence=0.9,
            metadata={"cache_hit": False, "token_reduction": 0}
        )
        
        # Mock SQL agent to raise unexpected exception
        orchestrator.schema_intelligence_agent = Mock()
        orchestrator.schema_intelligence_agent.execute.return_value = mock_schema_response
        orchestrator.sql_agent = Mock()
        orchestrator.sql_agent.execute.side_effect = RuntimeError("Unexpected error")
        
        # Execute
        response = orchestrator.execute(valid_request)
        
        # Verify error handling
        assert response.success is False
        assert response.confidence == 0.0
        assert response.error is not None
        assert "Orchestration failed" in response.error
        assert "Unexpected error" in response.error
        assert response.metadata["error_type"] == "unexpected_error"
    
    # Edge case tests
    
    def test_empty_question_validation(self, orchestrator):
        """
        Edge case: Empty question → Pydantic validation catches it.
        """
        # Pydantic validation should catch empty question at model level
        from pydantic import ValidationError
        
        with pytest.raises(ValidationError) as exc_info:
            invalid_request = AgentRequest(
                question="",
                db_schema="Table: iso_tank\n  - id: uuid"
            )
        
        # Verify Pydantic caught the validation error
        assert "question" in str(exc_info.value)
    
    def test_whitespace_only_question(self, orchestrator):
        """
        Edge case: Whitespace-only question → Pydantic validation catches it.
        """
        # Pydantic validation should catch whitespace-only question
        from pydantic import ValidationError
        
        with pytest.raises(ValidationError) as exc_info:
            invalid_request = AgentRequest(
                question="   \n\t  ",
                db_schema="Table: iso_tank\n  - id: uuid"
            )
        
        # Verify Pydantic caught the validation error
        assert "question" in str(exc_info.value)
        assert "whitespace" in str(exc_info.value).lower()
    
    def test_empty_schema_validation(self, orchestrator):
        """
        Edge case: Empty schema → Pydantic validation catches it.
        """
        # Pydantic validation should catch empty schema
        from pydantic import ValidationError
        
        with pytest.raises(ValidationError) as exc_info:
            invalid_request = AgentRequest(
                question="How many tanks?",
                db_schema=""
            )
        
        # Verify Pydantic caught the validation error
        assert "db_schema" in str(exc_info.value)
    
    # Integration tests
    
    def test_schema_passed_correctly(self, orchestrator):
        """
        Integration: Orchestrator passes pruned schema from Schema Intelligence to SQL Generation agent.
        """
        # Create request with specific schema
        schema = (
            "Table: iso_tank\n"
            "  - id: uuid\n"
            "  - tank_number: varchar\n"
            "  - iso_tank_status: varchar\n"
            "Table: service_tank\n"
            "  - id: uuid\n"
            "  - service_tank_status: varchar"
        )
        
        request = AgentRequest(
            question="List all tanks",
            db_schema=schema
        )
        
        # Mock Schema Intelligence response (prunes to just iso_tank)
        from agents.models.schema_models import SchemaIntelligenceResponse
        pruned_schema = (
            "Table: iso_tank\n"
            "  - id: uuid\n"
            "  - tank_number: varchar\n"
            "  - iso_tank_status: varchar"
        )
        mock_schema_response = SchemaIntelligenceResponse(
            success=True,
            pruned_schema=pruned_schema,
            selected_tables=["iso_tank"],
            join_hints=[],
            entity_matches=[],
            confidence=0.9,
            metadata={"cache_hit": False, "token_reduction": 45.9}
        )
        
        # Mock SQL agent
        mock_sql_response = SQLGenerationResponse(
            success=True,
            sql="SELECT * FROM iso_tank LIMIT 100;",
            validation_issues=[],
            retry_count=0,
            confidence=0.9
        )
        
        orchestrator.schema_intelligence_agent = Mock()
        orchestrator.schema_intelligence_agent.execute.return_value = mock_schema_response
        orchestrator.sql_agent = Mock()
        orchestrator.sql_agent.execute.return_value = mock_sql_response
        
        # Execute
        response = orchestrator.execute(request)
        
        # Verify pruned schema was passed to SQL Generation
        call_args = orchestrator.sql_agent.execute.call_args[0][0]
        assert call_args.db_schema == pruned_schema
        assert "iso_tank" in call_args.db_schema
        assert "service_tank" not in call_args.db_schema  # Pruned out
    
    def test_confidence_preserved(self, orchestrator, valid_request):
        """
        Integration: Orchestrator preserves confidence scores from SQL Generation agent.
        """
        # Mock Schema Intelligence response
        from agents.models.schema_models import SchemaIntelligenceResponse
        mock_schema_response = SchemaIntelligenceResponse(
            success=True,
            pruned_schema="Table: iso_tank\n  - id: uuid\n  - iso_tank_status: varchar",
            selected_tables=["iso_tank"],
            join_hints=[],
            entity_matches=[],
            confidence=0.9,
            metadata={"cache_hit": False, "token_reduction": 0}
        )
        
        # Test different confidence levels
        confidence_levels = [0.9, 0.75, 0.6, 0.45]
        
        for expected_confidence in confidence_levels:
            # Mock SQL agent response
            mock_sql_response = SQLGenerationResponse(
                success=True,
                sql="SELECT * FROM iso_tank LIMIT 100;",
                validation_issues=[],
                retry_count=0,
                confidence=expected_confidence
            )
            
            orchestrator.schema_intelligence_agent = Mock()
            orchestrator.schema_intelligence_agent.execute.return_value = mock_schema_response
            orchestrator.sql_agent = Mock()
            orchestrator.sql_agent.execute.return_value = mock_sql_response
            
            # Execute
            response = orchestrator.execute(valid_request)
            
            # Verify confidence is preserved
            assert response.confidence == expected_confidence
    
    def test_context_passed_through(self, orchestrator):
        """
        Integration: Orchestrator passes context to SQL Generation agent.
        """
        # Create request with context
        request = AgentRequest(
            question="How many tanks?",
            db_schema="Table: iso_tank\n  - id: uuid",
            context={"user_id": "123", "preferences": {"limit": 50}}
        )
        
        # Mock Schema Intelligence response
        from agents.models.schema_models import SchemaIntelligenceResponse
        mock_schema_response = SchemaIntelligenceResponse(
            success=True,
            pruned_schema="Table: iso_tank\n  - id: uuid",
            selected_tables=["iso_tank"],
            join_hints=[],
            entity_matches=[],
            confidence=0.9,
            metadata={"cache_hit": False, "token_reduction": 0}
        )
        
        # Mock SQL agent
        mock_sql_response = SQLGenerationResponse(
            success=True,
            sql="SELECT * FROM iso_tank LIMIT 100;",
            validation_issues=[],
            retry_count=0,
            confidence=0.9
        )
        
        orchestrator.schema_intelligence_agent = Mock()
        orchestrator.schema_intelligence_agent.execute.return_value = mock_schema_response
        orchestrator.sql_agent = Mock()
        orchestrator.sql_agent.execute.return_value = mock_sql_response
        
        # Execute
        response = orchestrator.execute(request)
        
        # Verify context was passed
        call_args = orchestrator.sql_agent.execute.call_args[0][0]
        assert call_args.context == request.context
        assert call_args.context["user_id"] == "123"
    
    def test_metadata_enrichment(self, orchestrator, valid_request):
        """
        Integration: Orchestrator enriches metadata with routing and schema intelligence information.
        """
        # Mock Schema Intelligence response
        from agents.models.schema_models import SchemaIntelligenceResponse
        mock_schema_response = SchemaIntelligenceResponse(
            success=True,
            pruned_schema="Table: iso_tank\n  - id: uuid\n  - iso_tank_status: varchar",
            selected_tables=["iso_tank"],
            join_hints=[],
            entity_matches=[],
            confidence=0.9,
            metadata={"cache_hit": False, "token_reduction": 0}
        )
        
        # Mock SQL agent response
        mock_sql_response = SQLGenerationResponse(
            success=True,
            sql="SELECT * FROM iso_tank LIMIT 100;",
            validation_issues=[],
            retry_count=0,
            confidence=0.9,
            metadata={"execution_time": 1.23, "attempts": 1}
        )
        
        orchestrator.schema_intelligence_agent = Mock()
        orchestrator.schema_intelligence_agent.execute.return_value = mock_schema_response
        orchestrator.sql_agent = Mock()
        orchestrator.sql_agent.execute.return_value = mock_sql_response
        
        # Execute
        response = orchestrator.execute(valid_request)
        
        # Verify metadata enrichment
        assert "agent" in response.metadata
        assert response.metadata["agent"] == "SQLGenerationAgent"
        assert "routing_strategy" in response.metadata
        assert response.metadata["routing_strategy"] == "schema_intelligence"
        
        # Verify schema intelligence metadata
        assert "schema_intelligence_success" in response.metadata
        assert response.metadata["schema_intelligence_success"] is True
        assert "schema_token_reduction" in response.metadata
        
        # Verify original metadata is preserved
        assert "execution_time" in response.metadata
        assert response.metadata["execution_time"] == 1.23
        assert "attempts" in response.metadata
        assert response.metadata["attempts"] == 1
    
    def test_latency_overhead_minimal(self, orchestrator, valid_request):
        """
        Integration: Orchestrator adds minimal latency overhead (<50ms).
        """
        import time
        
        # Mock Schema Intelligence response
        from agents.models.schema_models import SchemaIntelligenceResponse
        mock_schema_response = SchemaIntelligenceResponse(
            success=True,
            pruned_schema="Table: iso_tank\n  - id: uuid\n  - iso_tank_status: varchar",
            selected_tables=["iso_tank"],
            join_hints=[],
            entity_matches=[],
            confidence=0.9,
            metadata={"cache_hit": False, "token_reduction": 0}
        )
        
        # Mock SQL agent with instant response
        mock_sql_response = SQLGenerationResponse(
            success=True,
            sql="SELECT * FROM iso_tank LIMIT 100;",
            validation_issues=[],
            retry_count=0,
            confidence=0.9,
            metadata={"execution_time": 0.0}
        )
        
        orchestrator.schema_intelligence_agent = Mock()
        orchestrator.schema_intelligence_agent.execute.return_value = mock_schema_response
        orchestrator.sql_agent = Mock()
        orchestrator.sql_agent.execute.return_value = mock_sql_response
        
        # Measure orchestration overhead
        start = time.time()
        response = orchestrator.execute(valid_request)
        overhead = time.time() - start
        
        # Verify minimal overhead (<50ms)
        assert overhead < 0.05  # 50ms
        assert response.success is True
    
    # Placeholder method tests (for future phases)
    
    def test_analyze_query_complexity_placeholder(self, orchestrator):
        """
        Test placeholder method for query complexity analysis (Phase 2-3).
        """
        # Currently returns "simple" for all queries
        complexity = orchestrator._analyze_query_complexity("How many tanks?")
        assert complexity == "simple"
        
        complexity = orchestrator._analyze_query_complexity(
            "Show me the average time between vehicle in and out for each tank type"
        )
        assert complexity == "simple"  # Will be "complex" in Phase 2-3
    
    def test_form_agent_team_placeholder(self, orchestrator):
        """
        Test placeholder method for agent team formation (Phase 2-3).
        """
        # Currently returns only SQL agent
        team = orchestrator._form_agent_team("simple", "How many tanks?")
        assert len(team) == 1
        assert team[0] == orchestrator.sql_agent
    
    def test_resolve_conflicts_placeholder(self, orchestrator):
        """
        Test placeholder method for conflict resolution (Phase 2-3).
        """
        # Create mock responses
        response1 = AgentResponse(
            success=True,
            data={"sql": "SELECT * FROM iso_tank LIMIT 100;"},
            confidence=0.9
        )
        
        response2 = AgentResponse(
            success=True,
            data={"sql": "SELECT COUNT(*) FROM iso_tank LIMIT 100;"},
            confidence=0.85
        )
        
        # Currently returns first response
        resolved = orchestrator._resolve_conflicts([response1, response2])
        assert resolved == response1
        
        # Empty list returns error
        resolved = orchestrator._resolve_conflicts([])
        assert resolved.success is False
        assert "No agent responses" in resolved.error
    
    def test_fallback_logging_on_schema_intelligence_failure(self, orchestrator, valid_request, caplog):
        """
        Integration: Fallback logging includes token count and reason when Schema Intelligence fails.
        """
        import logging
        
        # Mock Schema Intelligence to return failure
        from agents.models.schema_models import SchemaIntelligenceResponse
        mock_schema_response = SchemaIntelligenceResponse(
            success=False,
            pruned_schema="",
            selected_tables=[],
            join_hints=[],
            entity_matches=[],
            confidence=0.0,
            error="No entities extracted from question",
            metadata={}
        )
        
        # Mock SQL agent
        mock_sql_response = SQLGenerationResponse(
            success=True,
            sql="SELECT * FROM iso_tank LIMIT 100;",
            validation_issues=[],
            retry_count=0,
            confidence=0.9
        )
        
        orchestrator.schema_intelligence_agent = Mock()
        orchestrator.schema_intelligence_agent.execute.return_value = mock_schema_response
        orchestrator.sql_agent = Mock()
        orchestrator.sql_agent.execute.return_value = mock_sql_response
        
        # Execute with logging capture
        with caplog.at_level(logging.WARNING):
            response = orchestrator.execute(valid_request)
        
        # Verify fallback logging
        assert any("Schema Intelligence failed" in record.message for record in caplog.records)
        assert any("Falling back to full schema" in record.message for record in caplog.records)
        assert any("tokens" in record.message for record in caplog.records)
        
        # Verify metadata includes fallback reason and token count
        assert response.metadata["schema_intelligence_success"] is False
        assert "schema_fallback_reason" in response.metadata
        assert "schema_original_tokens" in response.metadata
        assert response.metadata["schema_original_tokens"] > 0
    
    def test_fallback_logging_on_schema_intelligence_exception(self, orchestrator, valid_request, caplog):
        """
        Integration: Fallback logging includes token count and reason when Schema Intelligence raises exception.
        """
        import logging
        
        # Mock Schema Intelligence to raise exception
        orchestrator.schema_intelligence_agent = Mock()
        orchestrator.schema_intelligence_agent.execute.side_effect = RuntimeError("Schema parsing error")
        
        # Mock SQL agent
        mock_sql_response = SQLGenerationResponse(
            success=True,
            sql="SELECT * FROM iso_tank LIMIT 100;",
            validation_issues=[],
            retry_count=0,
            confidence=0.9
        )
        
        orchestrator.sql_agent = Mock()
        orchestrator.sql_agent.execute.return_value = mock_sql_response
        
        # Execute with logging capture
        with caplog.at_level(logging.WARNING):
            response = orchestrator.execute(valid_request)
        
        # Verify fallback logging
        assert any("Schema Intelligence error" in record.message for record in caplog.records)
        assert any("Falling back to full schema" in record.message for record in caplog.records)
        assert any("tokens" in record.message for record in caplog.records)
        
        # Verify metadata includes fallback reason and token count
        assert response.metadata["schema_intelligence_success"] is False
        assert "schema_fallback_reason" in response.metadata
        assert "Schema parsing error" in response.metadata["schema_fallback_reason"]
        assert "schema_original_tokens" in response.metadata
        assert response.metadata["schema_original_tokens"] > 0


# Integration test with real SQL Generation agent (optional)
@pytest.mark.integration
class TestOrchestratorIntegration:
    """Integration tests with real SQL Generation agent."""
    
    def test_end_to_end_simple_query(self):
        """
        End-to-end test: Orchestrator → SQL Generation → Success.
        
        This test uses the real SQL Generation agent (mocked AI provider).
        """
        # Create orchestrator with real SQL agent
        with patch('agents.sql_generation.ai_client') as mock_ai_client:
            # Mock AI response
            mock_response = Mock()
            mock_response.choices = [
                Mock(message=Mock(content="SELECT COUNT(*) FROM iso_tank WHERE iso_tank_status = 'IN' LIMIT 100;"))
            ]
            mock_response.usage = Mock(prompt_tokens=100, completion_tokens=20, total_tokens=120)
            mock_ai_client.chat.completions.create.return_value = mock_response
            
            # Create orchestrator
            orchestrator = OrchestratorAgent()
            
            # Create request
            request = AgentRequest(
                question="How many ISO tanks are in 'IN' status?",
                db_schema="Table: iso_tank\n  - id: uuid\n  - iso_tank_status: varchar"
            )
            
            # Execute
            response = orchestrator.execute(request)
            
            # Verify
            assert response.success is True
            assert response.confidence >= 0.6
            assert response.data is not None
            assert "SELECT" in response.data["sql"]
            assert "iso_tank" in response.data["sql"]
