"""
Base Agent Class

This module provides the abstract base class that all agents inherit from.
It enforces a consistent interface and provides common functionality like
logging and error handling.

All agents must implement the execute() method which takes an AgentRequest
and returns an AgentResponse.
"""

import time
from abc import ABC, abstractmethod
from typing import Optional
from config.logging_config import get_logger
from agents.models.agent_models import AgentRequest, AgentResponse


# Exception hierarchy for agent errors
class AgentError(Exception):
    """Base exception for all agent errors."""
    pass


class AgentExecutionError(AgentError):
    """Raised when agent execution fails."""
    pass


class AgentValidationError(AgentError):
    """Raised when agent input validation fails."""
    pass


class BaseAgent(ABC):
    """
    Abstract base class for all agents.
    
    All agents must inherit from this class and implement the execute() method.
    The base class provides common functionality like logging and timing.
    
    Attributes:
        name: Human-readable name of the agent
        logger: Logger instance for structured logging
        
    Example:
        class MyAgent(BaseAgent):
            def __init__(self):
                super().__init__(name="MyAgent")
            
            def execute(self, request: AgentRequest) -> AgentResponse:
                self.logger.info(f"Processing request: {request.question}")
                # Implementation here
                return AgentResponse(success=True, data={"result": "done"})
    """
    
    def __init__(self, name: str):
        """
        Initialize the base agent.
        
        Args:
            name: Human-readable name of the agent (e.g., "SQLGenerationAgent")
        """
        self.name = name
        self.logger = get_logger(f"agents.{name.lower().replace(' ', '_')}")
        self.logger.info(f"{self.name} initialized")
    
    @abstractmethod
    def execute(self, request: AgentRequest) -> AgentResponse:
        """
        Execute the agent's primary function.
        
        This method must be implemented by all subclasses. It takes a structured
        request and returns a structured response.
        
        Args:
            request: AgentRequest containing the question, schema, and optional context
            
        Returns:
            AgentResponse with success status, data, error message, and confidence
            
        Raises:
            AgentExecutionError: If execution fails
            AgentValidationError: If input validation fails
        """
        raise NotImplementedError(f"{self.name} must implement execute() method")
    
    def _log_execution_time(self, operation: str, start_time: float) -> None:
        """
        Log execution time for an operation.
        
        Args:
            operation: Name of the operation (e.g., "SQL generation")
            start_time: Start time from time.time()
        """
        elapsed = time.time() - start_time
        self.logger.info(f"{operation} completed in {elapsed:.2f}s")
    
    def _validate_request(self, request: AgentRequest) -> None:
        """
        Validate the agent request.
        
        Args:
            request: AgentRequest to validate
            
        Raises:
            AgentValidationError: If validation fails
        """
        if not request.question or not request.question.strip():
            raise AgentValidationError("Question cannot be empty")
        
        if not request.db_schema or not request.db_schema.strip():
            raise AgentValidationError("Schema cannot be empty")
