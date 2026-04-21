"""
Integration Tests for Phase 3 Pipeline

These tests verify the complete Phase 3 pipeline with all agents working together:
Query Refinement → Security & Governance → Schema Intelligence → SQL Generation

Tests cover:
- Happy path: Complete pipeline execution
- Security veto scenarios (escalation to human)
- MCP client fallback scenarios
- Confidence scoring across the pipeline
- Performance requirements (<3s p95)

Run with: pytest tests/integration/test_phase3_pipeline.py -v
Skip with: pytest -m "not integration"
"""

import pytest
import time
from unittest.mock import patch, MagicMock
from agents.orchestrator import OrchestratorAgent
from agents.models.agent_models import AgentRequest, AgentResponse
from agents.models.refinement_models import RefinementResponse
from agents.models.security_models import SecurityResponse
from agents.models.schema_models import SchemaIntelligenceResponse
from agents.models.query_models import SQLGenerationResponse


# Skip all tests in this module if services are not configured
pytestmark = pytest.mark.integration


class TestPhase3PipelineIntegration:
    """Integration tests for Phase 3 pipeline with all agents."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.orchestrator = OrchestratorAgent()
        self.sample_schema = """
        CREATE TABLE iso_tank (
            id SERIAL PRIMARY KEY,
            tank_number VARCHAR(50) UNIQUE NOT NULL,
            iso_tank_status VARCHAR(20) DEFAULT 'OUT',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE vehicle_in (
            id SERIAL PRIMARY KEY,
            croyance_client_name VARCHAR(100),
            driver_mobile_number VARCHAR(20),  -- PII
            license_number VARCHAR(50),        -- PII
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    
    def _setup_successful_pipeline_mocks(self, refined_query="How many ISO tanks have status 'IN'?"):
        """Setup mocks for successful pipeline execution."""
        # Mock Query Refinement Agent
        refinement_response = RefinementResponse(
            success=True,
            refined_query=refined_query,
            confidence=0.9,
            clarification_questions=[],
            metadata={"refinement_time": 0.2}
        )
        
        # Mock Security Agent (approved)
        security_response = SecurityResponse(
            success=True,
            approved=True,
            risk_score=0.1,
            veto_reason=None,
            alternative_suggestions=[],
            metadata={"security_time": 0.1}
        )
        
        # Mock Schema Intelligence Agent
        schema_response = SchemaIntelligenceResponse(
            success=True,
            pruned_schema="CREATE TABLE iso_tank (id SERIAL PRIMARY KEY, tank_number VARCHAR(50), iso_tank_status VARCHAR(20));",
            selected_tables=["iso_tank"],
            confidence=0.95,
            metadata={
                "cache_hit": False,
                "token_reduction": 60.0,
                "original_token_count": 500,
                "pruned_token_count": 200,
                "schema_time": 0.3
            }
        )
        
        # Mock SQL Generation Agent
        sql_response = SQLGenerationResponse(
            success=True,
            sql="SELECT COUNT(*) FROM iso_tank WHERE iso_tank_status = 'IN' LIMIT 100;",
            confidence=0.92,
            validation_issues=[],
            retry_count=0,
            metadata={
                "generation_time": 0.5,
                "tokens_used": 150,
                "model_name": "gpt-4"
            }
        )
        
        # Apply mocks
        self.orchestrator.query_refinement_agent.execute = MagicMock(return_value=refinement_response)
        self.orchestrator.security_agent.execute = MagicMock(return_value=security_response)
        self.orchestrator.schema_intelligence_agent.execute = MagicMock(return_value=schema_response)
        self.orchestrator.sql_agent.execute = MagicMock(return_value=sql_response)
        
        return refined_query
    
    def test_complete_phase3_pipeline_happy_path(self):
        """Integration: Complete Phase 3 pipeline executes successfully."""
        # Setup successful mocks
        refined_query = self._setup_successful_pipeline_mocks()
        
        # Create request
        request = AgentRequest(
            question="Which clients have the most tanks this month?",
            db_schema=self.sample_schema,
            context={"user_role": "analyst"}
        )
        
        # Execute pipeline
        start_time = time.time()
        response = self.orchestrator.execute(request)
        execution_time = time.time() - start_time
        
        # Verify response
        assert response.success is True
        assert response.error is None
        assert response.confidence >= 0.6  # Above threshold
        
        # Verify SQL generation
        assert "sql" in response.data
        assert "SELECT COUNT(*)" in response.data["sql"]
        assert "iso_tank" in response.data["sql"]
        
        # Verify Phase 3 metadata
        assert response.metadata["pipeline_version"] == "phase3"
        assert response.metadata["routing_strategy"] == "phase3_pipeline"
        
        # Verify refinement metadata
        assert response.metadata["refinement_success"] is True
        assert response.metadata["refinement_confidence"] == 0.9
        assert response.metadata["original_question"] == request.question
        
        # Verify security metadata
        assert response.metadata["security_approved"] is True
        assert response.metadata["security_risk_score"] == 0.1
        assert response.metadata["security_veto_reason"] is None
        
        # Verify schema intelligence metadata
        assert response.metadata["schema_intelligence_success"] is True
        assert response.metadata["schema_token_reduction"] == 60.0
        assert response.metadata["schema_selected_tables"] == 1
        
        # Verify performance requirement (<3s)
        assert execution_time < 3.0
        
        # Verify agent calls
        self.orchestrator.query_refinement_agent.execute.assert_called_once()
        self.orchestrator.security_agent.execute.assert_called_once()
        self.orchestrator.schema_intelligence_agent.execute.assert_called_once()
        self.orchestrator.sql_agent.execute.assert_called_once()
        
        # Verify refined query passed to downstream agents
        security_call_args = self.orchestrator.security_agent.execute.call_args[0][0]
        assert security_call_args.refined_query == refined_query
        
        schema_call_args = self.orchestrator.schema_intelligence_agent.execute.call_args[0][0]
        assert schema_call_args.question == refined_query  # Uses refined query
    
    def test_temporal_ambiguity_resolution(self):
        """Integration: Query Refinement resolves temporal ambiguity."""
        # Setup mocks with temporal refinement
        refined_query = "SELECT COUNT(*) FROM iso_tank WHERE created_at >= DATE_TRUNC('month', CURRENT_DATE)"
        self._setup_successful_pipeline_mocks(refined_query)
        
        # Create request with temporal ambiguity
        request = AgentRequest(
            question="How many tanks came in this month?",
            db_schema=self.sample_schema,
            context={"user_role": "analyst"}
        )
        
        # Execute pipeline
        response = self.orchestrator.execute(request)
        
        # Verify response
        assert response.success is True
        assert response.metadata["refinement_success"] is True
        
        # Verify temporal resolution in refined query
        refinement_call_args = self.orchestrator.query_refinement_agent.execute.call_args[0][0]
        assert refinement_call_args.question == "How many tanks came in this month?"
        
        # Verify refined query passed to security
        security_call_args = self.orchestrator.security_agent.execute.call_args[0][0]
        assert "DATE_TRUNC" in security_call_args.refined_query or refined_query in security_call_args.refined_query
    
    def test_security_veto_dangerous_operation(self):
        """Integration: Security agent blocks dangerous operations and escalates."""
        # Setup refinement and schema mocks
        refinement_response = RefinementResponse(
            success=True,
            refined_query="DROP TABLE iso_tank;",
            confidence=0.8,
            clarification_questions=[],
            metadata={"refinement_time": 0.2}
        )
        
        # Mock Security Agent (BLOCKED)
        security_response = SecurityResponse(
            success=True,
            approved=False,  # VETO
            risk_score=1.0,
            veto_reason="Dangerous operation: DROP",
            alternative_suggestions=["Use SELECT to view data instead"],
            metadata={"security_time": 0.1}
        )
        
        # Apply mocks
        self.orchestrator.query_refinement_agent.execute = MagicMock(return_value=refinement_response)
        self.orchestrator.security_agent.execute = MagicMock(return_value=security_response)
        # Setup mocks for agents that shouldn't be called
        self.orchestrator.schema_intelligence_agent.execute = MagicMock()
        self.orchestrator.sql_agent.execute = MagicMock()
        
        # Create request with dangerous operation
        request = AgentRequest(
            question="Delete all tank data",
            db_schema=self.sample_schema,
            context={"user_role": "analyst"}  # Non-admin role
        )
        
        # Execute pipeline
        response = self.orchestrator.execute(request)
        
        # Verify escalation
        assert response.success is False
        assert "human review" in response.error.lower()
        assert "security veto" in response.error.lower()
        assert response.confidence == 0.0
        assert response.metadata["escalated"] is True
        assert response.metadata["escalation_reason"] == "Security veto: Dangerous operation: DROP"
        
        # Verify security metadata
        assert response.metadata["security_approved"] is False
        assert response.metadata["security_risk_score"] == 1.0
        assert response.metadata["security_veto_reason"] == "Dangerous operation: DROP"
        
        # Verify escalation data
        assert "escalation_reason" in response.data
        assert "veto_reason" in response.data["agent_attempt"]["data"]
        assert "alternative_suggestions" in response.data["agent_attempt"]["data"]
        assert response.data["agent_attempt"]["data"]["alternative_suggestions"] == ["Use SELECT to view data instead"]
        
        # Verify pipeline stopped at security (no schema/sql calls)
        self.orchestrator.query_refinement_agent.execute.assert_called_once()
        self.orchestrator.security_agent.execute.assert_called_once()
        assert not self.orchestrator.schema_intelligence_agent.execute.called
        assert not self.orchestrator.sql_agent.execute.called
    
    def test_security_veto_pii_access(self):
        """Integration: Security agent blocks PII access for non-admin roles."""
        # Setup refinement mock
        refinement_response = RefinementResponse(
            success=True,
            refined_query="Show me all driver mobile numbers",
            confidence=0.9,
            clarification_questions=[],
            metadata={"refinement_time": 0.2}
        )
        
        # Mock Security Agent (BLOCKED - PII access)
        security_response = SecurityResponse(
            success=True,
            approved=False,  # VETO
            risk_score=0.8,
            veto_reason="PII access denied for role 'analyst'",
            alternative_suggestions=["Request admin access or use aggregated data"],
            metadata={"security_time": 0.1}
        )
        
        # Apply mocks
        self.orchestrator.query_refinement_agent.execute = MagicMock(return_value=refinement_response)
        self.orchestrator.security_agent.execute = MagicMock(return_value=security_response)
        # Setup mocks for agents that shouldn't be called
        self.orchestrator.schema_intelligence_agent.execute = MagicMock()
        self.orchestrator.sql_agent.execute = MagicMock()
        
        # Create request accessing PII
        request = AgentRequest(
            question="Show me all driver phone numbers",
            db_schema=self.sample_schema,
            context={"user_role": "analyst"}  # Non-admin role
        )
        
        # Execute pipeline
        response = self.orchestrator.execute(request)
        
        # Verify escalation
        assert response.success is False
        assert "human review" in response.error.lower()
        assert "security veto" in response.error.lower()
        assert "PII access denied" in response.data["agent_attempt"]["data"]["veto_reason"]
        assert response.metadata["escalated"] is True
        
        # Verify security blocked PII access
        assert response.metadata["security_approved"] is False
        assert response.metadata["security_risk_score"] == 0.8
        
        # Verify pipeline stopped at security
        assert not self.orchestrator.schema_intelligence_agent.execute.called
        assert not self.orchestrator.sql_agent.execute.called
    
    def test_admin_role_bypasses_pii_restrictions(self):
        """Integration: Admin role can access PII columns."""
        # Setup mocks for admin access
        refined_query = "SELECT driver_mobile_number FROM vehicle_in WHERE id = 123"
        
        refinement_response = RefinementResponse(
            success=True,
            refined_query=refined_query,
            confidence=0.9,
            clarification_questions=[],
            metadata={"refinement_time": 0.2}
        )
        
        # Mock Security Agent (APPROVED for admin)
        security_response = SecurityResponse(
            success=True,
            approved=True,  # APPROVED
            risk_score=0.3,  # Higher risk but approved
            veto_reason=None,
            alternative_suggestions=[],
            metadata={"security_time": 0.1}
        )
        
        # Mock remaining pipeline
        schema_response = SchemaIntelligenceResponse(
            success=True,
            pruned_schema="CREATE TABLE vehicle_in (id SERIAL PRIMARY KEY, driver_mobile_number VARCHAR(20));",
            selected_tables=["vehicle_in"],
            confidence=0.95,
            metadata={"token_reduction": 40.0}
        )
        
        sql_response = SQLGenerationResponse(
            success=True,
            sql="SELECT driver_mobile_number FROM vehicle_in WHERE id = 123 LIMIT 100;",
            confidence=0.88,
            validation_issues=[],
            retry_count=0,
            metadata={"generation_time": 0.4}
        )
        
        # Apply mocks
        self.orchestrator.query_refinement_agent.execute = MagicMock(return_value=refinement_response)
        self.orchestrator.security_agent.execute = MagicMock(return_value=security_response)
        self.orchestrator.schema_intelligence_agent.execute = MagicMock(return_value=schema_response)
        self.orchestrator.sql_agent.execute = MagicMock(return_value=sql_response)
        
        # Create request with admin role
        request = AgentRequest(
            question="Get driver phone for vehicle ID 123",
            db_schema=self.sample_schema,
            context={"user_role": "admin"}  # Admin role
        )
        
        # Execute pipeline
        response = self.orchestrator.execute(request)
        
        # Verify success
        assert response.success is True
        assert response.error is None
        
        # Verify security approved with higher risk
        assert response.metadata["security_approved"] is True
        assert response.metadata["security_risk_score"] == 0.3  # Higher risk but approved
        
        # Verify complete pipeline execution
        assert "driver_mobile_number" in response.data["sql"]
        self.orchestrator.query_refinement_agent.execute.assert_called_once()
        self.orchestrator.security_agent.execute.assert_called_once()
        self.orchestrator.schema_intelligence_agent.execute.assert_called_once()
        self.orchestrator.sql_agent.execute.assert_called_once()
    
    def test_low_confidence_escalation_after_pipeline(self):
        """Integration: Low confidence after complete pipeline triggers escalation."""
        # Setup mocks with low final confidence
        refined_query = self._setup_successful_pipeline_mocks()
        
        # Override SQL Generation to return low confidence
        sql_response = SQLGenerationResponse(
            success=True,
            sql="SELECT * FROM unclear_table LIMIT 100;",
            confidence=0.4,  # Below threshold (0.6)
            validation_issues=["Table name unclear"],
            retry_count=2,  # Max retries reached
            metadata={"generation_time": 1.2}
        )
        self.orchestrator.sql_agent.execute = MagicMock(return_value=sql_response)
        
        # Create request
        request = AgentRequest(
            question="Show me some data",  # Ambiguous question
            db_schema=self.sample_schema,
            context={"user_role": "viewer"}
        )
        
        # Execute pipeline
        response = self.orchestrator.execute(request)
        
        # Verify escalation due to low confidence
        assert response.success is False
        assert "human review" in response.error.lower()
        assert response.confidence == 0.4  # Preserves original confidence
        assert response.metadata["escalated"] is True
        assert "Low confidence" in response.metadata["escalation_reason"]
        
        # Verify complete pipeline executed before escalation
        self.orchestrator.query_refinement_agent.execute.assert_called_once()
        self.orchestrator.security_agent.execute.assert_called_once()
        self.orchestrator.schema_intelligence_agent.execute.assert_called_once()
        self.orchestrator.sql_agent.execute.assert_called_once()
    
    @patch('agents.mcp_client.MCPClient')
    def test_mcp_client_fallback_scenario(self, mock_mcp_client_class):
        """Integration: MCP client fallback when server unavailable."""
        # Setup MCP client mock to simulate connection failure
        mock_mcp_instance = MagicMock()
        mock_mcp_instance.is_connected.return_value = False
        mock_mcp_client_class.return_value = mock_mcp_instance
        
        # Setup successful pipeline mocks
        self._setup_successful_pipeline_mocks()
        
        # Create request
        request = AgentRequest(
            question="How many tanks?",
            db_schema=self.sample_schema,
            context={"user_role": "analyst"}
        )
        
        # Execute pipeline
        response = self.orchestrator.execute(request)
        
        # Verify pipeline succeeds despite MCP unavailability
        assert response.success is True
        
        # Verify MCP metadata indicates fallback mode
        # (This would be set by Schema Intelligence and SQL Generation agents)
        # For now, just verify pipeline completes
        assert response.metadata["pipeline_version"] == "phase3"
    
    def test_query_refinement_failure_continues_with_original(self):
        """Integration: Pipeline continues with original question if refinement fails."""
        # Mock Query Refinement failure
        refinement_response = RefinementResponse(
            success=False,
            refined_query="",
            confidence=0.0,
            clarification_questions=[],
            error="AI provider error",
            metadata={"refinement_time": 0.1}
        )
        
        # Mock successful remaining pipeline
        security_response = SecurityResponse(
            success=True,
            approved=True,
            risk_score=0.2,
            veto_reason=None,
            alternative_suggestions=[],
            metadata={"security_time": 0.1}
        )
        
        schema_response = SchemaIntelligenceResponse(
            success=True,
            pruned_schema="CREATE TABLE iso_tank (id SERIAL PRIMARY KEY);",
            selected_tables=["iso_tank"],
            confidence=0.9,
            metadata={"token_reduction": 50.0}
        )
        
        sql_response = SQLGenerationResponse(
            success=True,
            sql="SELECT COUNT(*) FROM iso_tank LIMIT 100;",
            confidence=0.85,
            validation_issues=[],
            retry_count=0,
            metadata={"generation_time": 0.6}
        )
        
        # Apply mocks
        self.orchestrator.query_refinement_agent.execute = MagicMock(return_value=refinement_response)
        self.orchestrator.security_agent.execute = MagicMock(return_value=security_response)
        self.orchestrator.schema_intelligence_agent.execute = MagicMock(return_value=schema_response)
        self.orchestrator.sql_agent.execute = MagicMock(return_value=sql_response)
        
        # Create request
        request = AgentRequest(
            question="How many tanks?",
            db_schema=self.sample_schema,
            context={"user_role": "analyst"}
        )
        
        # Execute pipeline
        response = self.orchestrator.execute(request)
        
        # Verify pipeline succeeds despite refinement failure
        assert response.success is True
        assert response.confidence == 0.85
        
        # Verify refinement failure metadata
        assert response.metadata["refinement_success"] is False
        assert response.metadata["refinement_error"] == "AI provider error"
        
        # Verify original question used in security validation
        security_call_args = self.orchestrator.security_agent.execute.call_args[0][0]
        assert security_call_args.refined_query == request.question  # Falls back to original
        
        # Verify original question used in schema intelligence
        schema_call_args = self.orchestrator.schema_intelligence_agent.execute.call_args[0][0]
        assert schema_call_args.question == request.question  # Falls back to original
    
    def test_security_agent_error_fails_open(self):
        """Integration: Security agent error allows pipeline to continue (fail open)."""
        # Setup refinement mock
        refinement_response = RefinementResponse(
            success=True,
            refined_query="SELECT COUNT(*) FROM iso_tank",
            confidence=0.9,
            clarification_questions=[],
            metadata={"refinement_time": 0.2}
        )
        
        # Mock Security Agent error
        self.orchestrator.security_agent.execute = MagicMock(side_effect=Exception("Security service unavailable"))
        
        # Mock successful remaining pipeline
        schema_response = SchemaIntelligenceResponse(
            success=True,
            pruned_schema="CREATE TABLE iso_tank (id SERIAL PRIMARY KEY);",
            selected_tables=["iso_tank"],
            confidence=0.9,
            metadata={"token_reduction": 50.0}
        )
        
        sql_response = SQLGenerationResponse(
            success=True,
            sql="SELECT COUNT(*) FROM iso_tank LIMIT 100;",
            confidence=0.85,
            validation_issues=[],
            retry_count=0,
            metadata={"generation_time": 0.6}
        )
        
        # Apply mocks
        self.orchestrator.query_refinement_agent.execute = MagicMock(return_value=refinement_response)
        self.orchestrator.schema_intelligence_agent.execute = MagicMock(return_value=schema_response)
        self.orchestrator.sql_agent.execute = MagicMock(return_value=sql_response)
        
        # Create request
        request = AgentRequest(
            question="How many tanks?",
            db_schema=self.sample_schema,
            context={"user_role": "analyst"}
        )
        
        # Execute pipeline
        response = self.orchestrator.execute(request)
        
        # Verify pipeline succeeds despite security error (fail open)
        assert response.success is True
        assert response.confidence == 0.85
        
        # Verify security error metadata
        assert response.metadata["security_approved"] is True  # Fail open
        assert "security_error" in response.metadata
        assert "Security service unavailable" in response.metadata["security_error"]
        
        # Verify pipeline continued
        self.orchestrator.schema_intelligence_agent.execute.assert_called_once()
        self.orchestrator.sql_agent.execute.assert_called_once()
    
    def test_performance_requirement_under_3_seconds(self):
        """Integration: Pipeline completes within 3 second performance requirement."""
        # Setup fast mocks
        self._setup_successful_pipeline_mocks()
        
        # Create request
        request = AgentRequest(
            question="Quick query for performance test",
            db_schema=self.sample_schema,
            context={"user_role": "analyst"}
        )
        
        # Execute pipeline and measure time
        start_time = time.time()
        response = self.orchestrator.execute(request)
        execution_time = time.time() - start_time
        
        # Verify performance requirement
        assert execution_time < 3.0, f"Pipeline took {execution_time:.2f}s, exceeds 3s requirement"
        
        # Verify successful execution
        assert response.success is True
        assert response.confidence >= 0.6
        
        # Verify all agents executed
        self.orchestrator.query_refinement_agent.execute.assert_called_once()
        self.orchestrator.security_agent.execute.assert_called_once()
        self.orchestrator.schema_intelligence_agent.execute.assert_called_once()
        self.orchestrator.sql_agent.execute.assert_called_once()


class TestPhase3PipelineEdgeCases:
    """Edge case tests for Phase 3 pipeline."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.orchestrator = OrchestratorAgent()
        self.sample_schema = "CREATE TABLE test (id SERIAL PRIMARY KEY);"
    
    def test_empty_question_handled_gracefully(self):
        """Integration: Empty question is handled gracefully."""
        # Test that Pydantic validation catches empty question
        with pytest.raises(Exception) as exc_info:
            request = AgentRequest(
                question="",
                db_schema=self.sample_schema,
                context={"user_role": "viewer"}
            )
        
        # Verify validation error
        assert "validation error" in str(exc_info.value).lower() or "string_too_short" in str(exc_info.value)
    
    def test_missing_user_role_defaults_to_viewer(self):
        """Integration: Missing user_role defaults to 'viewer'."""
        # Setup mocks
        refinement_response = RefinementResponse(
            success=True,
            refined_query="SELECT COUNT(*) FROM test",
            confidence=0.9,
            clarification_questions=[],
            metadata={}
        )
        
        security_response = SecurityResponse(
            success=True,
            approved=True,
            risk_score=0.1,
            veto_reason=None,
            alternative_suggestions=[],
            metadata={}
        )
        
        # Apply mocks
        self.orchestrator.query_refinement_agent.execute = MagicMock(return_value=refinement_response)
        self.orchestrator.security_agent.execute = MagicMock(return_value=security_response)
        
        # Create request without user_role
        request = AgentRequest(
            question="Test question",
            db_schema=self.sample_schema,
            context={}  # No user_role
        )
        
        # Execute pipeline
        response = self.orchestrator.execute(request)
        
        # Verify default user_role used
        security_call_args = self.orchestrator.security_agent.execute.call_args[0][0]
        assert security_call_args.user_role == "viewer"  # Default role
    
    def test_confidence_scoring_across_pipeline(self):
        """Integration: Confidence scores are properly aggregated across pipeline."""
        # Setup mocks with varying confidence scores
        refinement_response = RefinementResponse(
            success=True,
            refined_query="SELECT COUNT(*) FROM test",
            confidence=0.8,  # Medium confidence
            clarification_questions=[],
            metadata={}
        )
        
        security_response = SecurityResponse(
            success=True,
            approved=True,
            risk_score=0.2,  # Low risk
            veto_reason=None,
            alternative_suggestions=[],
            metadata={}
        )
        
        schema_response = SchemaIntelligenceResponse(
            success=True,
            pruned_schema="CREATE TABLE test (id SERIAL PRIMARY KEY);",
            selected_tables=["test"],
            confidence=0.95,  # High confidence
            metadata={"token_reduction": 30.0}
        )
        
        sql_response = SQLGenerationResponse(
            success=True,
            sql="SELECT COUNT(*) FROM test LIMIT 100;",
            confidence=0.75,  # Medium confidence
            validation_issues=[],
            retry_count=0,
            metadata={}
        )
        
        # Apply mocks
        self.orchestrator.query_refinement_agent.execute = MagicMock(return_value=refinement_response)
        self.orchestrator.security_agent.execute = MagicMock(return_value=security_response)
        self.orchestrator.schema_intelligence_agent.execute = MagicMock(return_value=schema_response)
        self.orchestrator.sql_agent.execute = MagicMock(return_value=sql_response)
        
        # Create request
        request = AgentRequest(
            question="Test confidence scoring",
            db_schema=self.sample_schema,
            context={"user_role": "analyst"}
        )
        
        # Execute pipeline
        response = self.orchestrator.execute(request)
        
        # Verify final confidence comes from SQL Generation (last agent)
        assert response.confidence == 0.75
        
        # Verify individual agent confidences in metadata
        assert response.metadata["refinement_confidence"] == 0.8
        assert response.metadata["schema_confidence"] == 0.95
        
        # Verify above threshold (no escalation)
        assert response.success is True
        assert response.metadata.get("escalated", False) is False