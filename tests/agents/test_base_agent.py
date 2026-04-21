"""
Tests for Base Agent Class

This module tests the base agent class, exception hierarchy, and common functionality.
"""

import pytest
from agents.base import (
    BaseAgent,
    AgentError,
    AgentExecutionError,
    AgentValidationError
)
from agents.models.agent_models import AgentRequest, AgentResponse


# Concrete implementation for testing
class ConcreteTestAgent(BaseAgent):
    """Test agent that implements execute() method."""
    
    def __init__(self):
        super().__init__(name="TestAgent")
    
    def execute(self, request: AgentRequest) -> AgentResponse:
        """Simple implementation that returns success."""
        self._validate_request(request)
        return AgentResponse(
            success=True,
            data={"message": "Test execution successful"},
            confidence=1.0
        )


class IncompleteAgent(BaseAgent):
    """Test agent that does NOT implement execute() method."""
    
    def __init__(self):
        super().__init__(name="IncompleteAgent")
    
    # Intentionally not implementing execute() to test abstract method enforcement


# ============================================================================
# Happy Path Tests
# ============================================================================

def test_base_agent_initialization():
    """Test that base agent initializes correctly with name and logger."""
    agent = ConcreteTestAgent()
    
    assert agent is not None
    assert agent.name == "TestAgent"
    assert agent.logger is not None
    assert agent.logger.name == "agents.testagent"


def test_base_agent_execute_with_valid_request():
    """Test that agent executes successfully with valid request."""
    agent = ConcreteTestAgent()
    
    request = AgentRequest(
        question="How many ISO tanks?",
        db_schema="Table: iso_tank\n  - id: uuid"
    )
    
    response = agent.execute(request)
    
    assert response.success is True
    assert response.data == {"message": "Test execution successful"}
    assert response.confidence == 1.0
    assert response.error is None


def test_base_agent_validate_request_success():
    """Test that _validate_request passes with valid request."""
    agent = ConcreteTestAgent()
    
    request = AgentRequest(
        question="How many ISO tanks?",
        db_schema="Table: iso_tank\n  - id: uuid"
    )
    
    # Should not raise any exception
    agent._validate_request(request)


def test_base_agent_log_execution_time():
    """Test that _log_execution_time logs correctly."""
    import time
    
    agent = ConcreteTestAgent()
    start_time = time.time()
    
    # Should not raise any exception
    agent._log_execution_time("test operation", start_time)


# ============================================================================
# Edge Case Tests
# ============================================================================

def test_incomplete_agent_raises_not_implemented_error():
    """Test that agent without execute() implementation cannot be instantiated."""
    # Python's ABC prevents instantiation of abstract classes
    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        IncompleteAgent()


def test_validate_request_empty_question():
    """Test that Pydantic validator catches empty question."""
    # Pydantic validator will catch empty question during model creation
    with pytest.raises(Exception) as exc_info:
        AgentRequest(
            question="   ",  # Whitespace-only
            db_schema="Table: iso_tank\n  - id: uuid"
        )
    
    # Verify it's a validation error
    assert "question" in str(exc_info.value).lower() or "Question" in str(exc_info.value)


def test_validate_request_empty_schema():
    """Test that _validate_request raises error for empty schema."""
    agent = ConcreteTestAgent()
    
    # Pydantic validator will catch empty schema
    with pytest.raises(Exception):
        AgentRequest(
            question="How many ISO tanks?",
            db_schema=""
        )


# ============================================================================
# Exception Hierarchy Tests
# ============================================================================

def test_agent_error_is_base_exception():
    """Test that AgentError is the base exception."""
    error = AgentError("Test error")
    
    assert isinstance(error, Exception)
    assert str(error) == "Test error"


def test_agent_execution_error_inherits_from_agent_error():
    """Test that AgentExecutionError inherits from AgentError."""
    error = AgentExecutionError("Execution failed")
    
    assert isinstance(error, AgentError)
    assert isinstance(error, Exception)
    assert str(error) == "Execution failed"


def test_agent_validation_error_inherits_from_agent_error():
    """Test that AgentValidationError inherits from AgentError."""
    error = AgentValidationError("Validation failed")
    
    assert isinstance(error, AgentError)
    assert isinstance(error, Exception)
    assert str(error) == "Validation failed"


def test_exception_hierarchy_catch_base():
    """Test that catching AgentError catches all agent exceptions."""
    try:
        raise AgentExecutionError("Test")
    except AgentError as e:
        assert str(e) == "Test"
    
    try:
        raise AgentValidationError("Test")
    except AgentError as e:
        assert str(e) == "Test"


# ============================================================================
# Integration Tests
# ============================================================================

def test_base_agent_logging_integration():
    """Test that base agent integrates correctly with logging system."""
    agent = ConcreteTestAgent()
    
    # Verify logger is initialized
    assert agent.logger is not None
    assert agent.logger.name == "agents.testagent"
    
    # Verify logger can log messages (should not raise exception)
    agent.logger.info("Test log message")
    agent.logger.warning("Test warning message")
    agent.logger.error("Test error message")


def test_base_agent_with_context():
    """Test that agent handles optional context correctly."""
    agent = ConcreteTestAgent()
    
    request = AgentRequest(
        question="How many ISO tanks?",
        db_schema="Table: iso_tank\n  - id: uuid",
        context={"user_id": "123", "session_id": "abc"}
    )
    
    response = agent.execute(request)
    
    assert response.success is True
    assert request.context == {"user_id": "123", "session_id": "abc"}


def test_base_agent_multiple_executions():
    """Test that agent can execute multiple times."""
    agent = ConcreteTestAgent()
    
    request1 = AgentRequest(
        question="How many ISO tanks?",
        db_schema="Table: iso_tank\n  - id: uuid"
    )
    
    request2 = AgentRequest(
        question="List all service tanks",
        db_schema="Table: service_tank\n  - id: uuid"
    )
    
    response1 = agent.execute(request1)
    response2 = agent.execute(request2)
    
    assert response1.success is True
    assert response2.success is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
