"""
Tests for Agent Pydantic Models

This module tests the Pydantic models used for agent communication,
including validation, type safety, and edge cases.
"""

import pytest
from pydantic import ValidationError
from agents.models.agent_models import AgentRequest, AgentResponse


# ============================================================================
# AgentRequest Tests - Happy Path
# ============================================================================

def test_agent_request_with_required_fields():
    """Test that AgentRequest validates with required fields."""
    request = AgentRequest(
        question="How many ISO tanks?",
        db_schema="Table: iso_tank\n  - id: uuid"
    )
    
    assert request.question == "How many ISO tanks?"
    assert request.db_schema == "Table: iso_tank\n  - id: uuid"
    assert request.context is None


def test_agent_request_with_context():
    """Test that AgentRequest accepts optional context."""
    request = AgentRequest(
        question="How many ISO tanks?",
        db_schema="Table: iso_tank\n  - id: uuid",
        context={"user_id": "123", "session_id": "abc"}
    )
    
    assert request.context == {"user_id": "123", "session_id": "abc"}


def test_agent_request_strips_whitespace():
    """Test that AgentRequest strips leading/trailing whitespace."""
    request = AgentRequest(
        question="  How many ISO tanks?  ",
        db_schema="  Table: iso_tank\n  - id: uuid  "
    )
    
    assert request.question == "How many ISO tanks?"
    assert request.db_schema == "Table: iso_tank\n  - id: uuid"


# ============================================================================
# AgentRequest Tests - Edge Cases and Validation
# ============================================================================

def test_agent_request_empty_question_raises_error():
    """Test that empty question raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        AgentRequest(
            question="",
            db_schema="Table: iso_tank\n  - id: uuid"
        )
    
    errors = exc_info.value.errors()
    assert len(errors) > 0
    assert any("question" in str(error).lower() for error in errors)


def test_agent_request_whitespace_only_question_raises_error():
    """Test that whitespace-only question raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        AgentRequest(
            question="   ",
            db_schema="Table: iso_tank\n  - id: uuid"
        )
    
    errors = exc_info.value.errors()
    assert len(errors) > 0


def test_agent_request_empty_schema_raises_error():
    """Test that empty schema raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        AgentRequest(
            question="How many ISO tanks?",
            db_schema=""
        )
    
    errors = exc_info.value.errors()
    assert len(errors) > 0
    assert any("schema" in str(error).lower() for error in errors)


def test_agent_request_whitespace_only_schema_raises_error():
    """Test that whitespace-only schema raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        AgentRequest(
            question="How many ISO tanks?",
            db_schema="   "
        )
    
    errors = exc_info.value.errors()
    assert len(errors) > 0


def test_agent_request_missing_question_raises_error():
    """Test that missing question field raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        AgentRequest(db_schema="Table: iso_tank\n  - id: uuid")
    
    errors = exc_info.value.errors()
    assert len(errors) > 0
    assert any(error["loc"] == ("question",) for error in errors)


def test_agent_request_missing_schema_raises_error():
    """Test that missing db_schema field raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        AgentRequest(question="How many ISO tanks?")
    
    errors = exc_info.value.errors()
    assert len(errors) > 0
    assert any(error["loc"] == ("db_schema",) for error in errors)


def test_agent_request_wrong_type_question():
    """Test that wrong type for question raises ValidationError."""
    with pytest.raises(ValidationError):
        AgentRequest(
            question=123,  # Should be string
            db_schema="Table: iso_tank\n  - id: uuid"
        )


def test_agent_request_wrong_type_context():
    """Test that wrong type for context raises ValidationError."""
    with pytest.raises(ValidationError):
        AgentRequest(
            question="How many ISO tanks?",
            db_schema="Table: iso_tank\n  - id: uuid",
            context="not a dict"  # Should be dict
        )


# ============================================================================
# AgentResponse Tests - Happy Path
# ============================================================================

def test_agent_response_success_with_data():
    """Test that AgentResponse validates with success and data."""
    response = AgentResponse(
        success=True,
        data={"sql": "SELECT * FROM iso_tank LIMIT 100;"},
        confidence=0.9
    )
    
    assert response.success is True
    assert response.data == {"sql": "SELECT * FROM iso_tank LIMIT 100;"}
    assert response.confidence == 0.9
    assert response.error is None
    assert response.metadata == {}


def test_agent_response_failure_with_error():
    """Test that AgentResponse validates with failure and error message."""
    response = AgentResponse(
        success=False,
        error="SQL generation failed",
        confidence=0.0
    )
    
    assert response.success is False
    assert response.error == "SQL generation failed"
    assert response.confidence == 0.0
    assert response.data is None


def test_agent_response_with_metadata():
    """Test that AgentResponse accepts metadata."""
    response = AgentResponse(
        success=True,
        data={"result": "done"},
        metadata={"retry_count": 2, "execution_time": 1.23}
    )
    
    assert response.metadata == {"retry_count": 2, "execution_time": 1.23}


def test_agent_response_default_confidence():
    """Test that AgentResponse defaults confidence to 1.0."""
    response = AgentResponse(success=True)
    
    assert response.confidence == 1.0


def test_agent_response_default_metadata():
    """Test that AgentResponse defaults metadata to empty dict."""
    response = AgentResponse(success=True)
    
    assert response.metadata == {}


# ============================================================================
# AgentResponse Tests - Edge Cases and Validation
# ============================================================================

def test_agent_response_confidence_below_zero_raises_error():
    """Test that confidence below 0.0 raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        AgentResponse(
            success=True,
            confidence=-0.1
        )
    
    errors = exc_info.value.errors()
    assert len(errors) > 0
    assert any("confidence" in str(error).lower() for error in errors)


def test_agent_response_confidence_above_one_raises_error():
    """Test that confidence above 1.0 raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        AgentResponse(
            success=True,
            confidence=1.1
        )
    
    errors = exc_info.value.errors()
    assert len(errors) > 0
    assert any("confidence" in str(error).lower() for error in errors)


def test_agent_response_confidence_boundary_values():
    """Test that confidence accepts boundary values 0.0 and 1.0."""
    response_min = AgentResponse(success=True, confidence=0.0)
    response_max = AgentResponse(success=True, confidence=1.0)
    
    assert response_min.confidence == 0.0
    assert response_max.confidence == 1.0


def test_agent_response_missing_success_raises_error():
    """Test that missing success field raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        AgentResponse()
    
    errors = exc_info.value.errors()
    assert len(errors) > 0
    assert any(error["loc"] == ("success",) for error in errors)


def test_agent_response_wrong_type_success():
    """Test that wrong type for success raises ValidationError."""
    # Pydantic may coerce string "true" to boolean True, so use a non-coercible value
    with pytest.raises(ValidationError):
        AgentResponse(success="not a boolean")  # Should be bool


def test_agent_response_wrong_type_confidence():
    """Test that wrong type for confidence raises ValidationError."""
    with pytest.raises(ValidationError):
        AgentResponse(
            success=True,
            confidence="high"  # Should be float
        )


def test_agent_response_wrong_type_data():
    """Test that wrong type for data raises ValidationError."""
    with pytest.raises(ValidationError):
        AgentResponse(
            success=True,
            data="not a dict"  # Should be dict
        )


def test_agent_response_wrong_type_metadata():
    """Test that wrong type for metadata raises ValidationError."""
    with pytest.raises(ValidationError):
        AgentResponse(
            success=True,
            metadata="not a dict"  # Should be dict
        )


# ============================================================================
# Integration Tests
# ============================================================================

def test_agent_request_response_round_trip():
    """Test that request and response work together."""
    request = AgentRequest(
        question="How many ISO tanks?",
        db_schema="Table: iso_tank\n  - id: uuid",
        context={"user_id": "123"}
    )
    
    response = AgentResponse(
        success=True,
        data={"sql": "SELECT COUNT(*) FROM iso_tank LIMIT 100;"},
        confidence=0.9,
        metadata={"retry_count": 0}
    )
    
    assert request.question == "How many ISO tanks?"
    assert response.success is True
    assert response.data["sql"] == "SELECT COUNT(*) FROM iso_tank LIMIT 100;"


def test_agent_models_json_serialization():
    """Test that models can be serialized to JSON."""
    request = AgentRequest(
        question="How many ISO tanks?",
        db_schema="Table: iso_tank\n  - id: uuid"
    )
    
    response = AgentResponse(
        success=True,
        data={"result": "done"}
    )
    
    # Should not raise exception
    request_json = request.model_dump_json()
    response_json = response.model_dump_json()
    
    assert "How many ISO tanks?" in request_json
    assert "done" in response_json


def test_agent_models_dict_conversion():
    """Test that models can be converted to dict."""
    request = AgentRequest(
        question="How many ISO tanks?",
        db_schema="Table: iso_tank\n  - id: uuid"
    )
    
    request_dict = request.model_dump()
    
    assert request_dict["question"] == "How many ISO tanks?"
    assert request_dict["db_schema"] == "Table: iso_tank\n  - id: uuid"
    assert request_dict["context"] is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


# ============================================================================
# OrchestratorResponse Tests
# ============================================================================

def test_orchestrator_response_with_routing_info():
    """Test OrchestratorResponse with routing metadata."""
    from agents.models.agent_models import OrchestratorResponse
    
    response = OrchestratorResponse(
        success=True,
        data={"sql": "SELECT * FROM iso_tank LIMIT 100;"},
        confidence=0.9,
        routed_to="SQLGenerationAgent",
        routing_strategy="simple",
        escalated=False,
        metadata={"execution_time": 1.23}
    )
    
    assert response.success is True
    assert response.confidence == 0.9
    assert response.routed_to == "SQLGenerationAgent"
    assert response.routing_strategy == "simple"
    assert response.escalated is False
    assert response.metadata["execution_time"] == 1.23


def test_orchestrator_response_with_escalation():
    """Test OrchestratorResponse with escalation flag."""
    from agents.models.agent_models import OrchestratorResponse
    
    response = OrchestratorResponse(
        success=False,
        error="Low confidence - requires human review",
        confidence=0.45,
        routed_to="SQLGenerationAgent",
        routing_strategy="simple",
        escalated=True,
        metadata={"escalation_reason": "Low confidence (0.45)"}
    )
    
    assert response.success is False
    assert response.escalated is True
    assert response.confidence == 0.45
    assert "Low confidence" in response.error
    assert response.metadata["escalation_reason"] == "Low confidence (0.45)"


def test_orchestrator_response_default_values():
    """Test OrchestratorResponse default values."""
    from agents.models.agent_models import OrchestratorResponse
    
    response = OrchestratorResponse(
        success=True,
        data={"result": "test"}
    )
    
    assert response.routed_to is None
    assert response.routing_strategy == "simple"
    assert response.escalated is False
    assert response.confidence == 1.0


def test_orchestrator_response_json_serialization():
    """Test OrchestratorResponse JSON serialization."""
    from agents.models.agent_models import OrchestratorResponse
    
    response = OrchestratorResponse(
        success=True,
        data={"sql": "SELECT * FROM iso_tank LIMIT 100;"},
        confidence=0.9,
        routed_to="SQLGenerationAgent",
        routing_strategy="simple",
        escalated=False
    )
    
    # Serialize to JSON
    json_str = response.model_dump_json()
    assert "SQLGenerationAgent" in json_str
    assert "simple" in json_str
    
    # Deserialize from JSON
    response_dict = response.model_dump()
    restored = OrchestratorResponse(**response_dict)
    assert restored.routed_to == "SQLGenerationAgent"
    assert restored.routing_strategy == "simple"
    assert restored.escalated is False
