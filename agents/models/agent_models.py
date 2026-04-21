"""
Agent Communication Models

This module defines the base Pydantic models used for communication between agents.
All agents use these models to ensure type safety and consistent interfaces.

Models:
- AgentRequest: Base request model containing question, schema, and optional context
- AgentResponse: Base response model containing success status, data, error, and confidence
"""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, field_validator


class AgentRequest(BaseModel):
    """
    Base request model for all agents.
    
    All agent requests must include a question and database schema. Optional context
    can be provided for additional information.
    
    Attributes:
        question: Natural language question from user
        db_schema: Database schema description
        context: Optional additional context (e.g., user preferences, history)
        
    Example:
        request = AgentRequest(
            question="How many ISO tanks are in 'IN' status?",
            db_schema="Table: iso_tank\\n  - id: uuid\\n  - status: varchar",
            context={"user_id": "123"}
        )
    """
    
    question: str = Field(
        ...,
        description="Natural language question from user",
        min_length=1
    )
    db_schema: str = Field(
        ...,
        description="Database schema description",
        min_length=1
    )
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional additional context"
    )
    
    @field_validator("question")
    @classmethod
    def validate_question(cls, v: str) -> str:
        """Validate that question is not empty or whitespace-only."""
        if not v or not v.strip():
            raise ValueError("Question cannot be empty or whitespace-only")
        return v.strip()
    
    @field_validator("db_schema")
    @classmethod
    def validate_db_schema(cls, v: str) -> str:
        """Validate that db_schema is not empty or whitespace-only."""
        if not v or not v.strip():
            raise ValueError("Schema cannot be empty or whitespace-only")
        return v.strip()


class AgentResponse(BaseModel):
    """
    Base response model for all agents.
    
    All agent responses include success status, optional data, optional error message,
    confidence score, and metadata.
    
    Attributes:
        success: Whether the agent execution succeeded
        data: Optional result data (structure depends on agent type)
        error: Optional error message (present if success=False)
        confidence: Confidence score between 0.0 and 1.0 (1.0 = highest confidence)
        metadata: Optional metadata (e.g., retry count, execution time, token usage)
        
    Example:
        response = AgentResponse(
            success=True,
            data={"sql": "SELECT * FROM iso_tank LIMIT 100;"},
            confidence=0.9,
            metadata={"retry_count": 0, "execution_time": 1.23}
        )
    """
    
    success: bool = Field(
        ...,
        description="Whether the agent execution succeeded"
    )
    data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional result data"
    )
    error: Optional[str] = Field(
        default=None,
        description="Optional error message"
    )
    confidence: float = Field(
        default=1.0,
        description="Confidence score between 0.0 and 1.0",
        ge=0.0,
        le=1.0
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Optional metadata"
    )
    
    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        """Validate that confidence is between 0.0 and 1.0."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")
        return v


class OrchestratorResponse(AgentResponse):
    """
    Response model for Orchestrator agent.
    
    Extends AgentResponse with orchestration-specific metadata like routing
    strategy and agent selection.
    
    Attributes:
        success: Whether orchestration succeeded (inherited)
        data: Result data (inherited)
        error: Error message (inherited)
        confidence: Confidence score (inherited)
        metadata: Metadata (inherited)
        routed_to: Name of agent(s) the request was routed to
        routing_strategy: Strategy used for routing (e.g., "simple", "complex", "multi-agent")
        escalated: Whether the request was escalated to human review
        
    Example:
        response = OrchestratorResponse(
            success=True,
            data={"sql": "SELECT * FROM iso_tank LIMIT 100;"},
            confidence=0.9,
            routed_to="SQLGenerationAgent",
            routing_strategy="simple",
            escalated=False
        )
    """
    
    routed_to: Optional[str] = Field(
        default=None,
        description="Name of agent(s) the request was routed to"
    )
    routing_strategy: str = Field(
        default="simple",
        description="Strategy used for routing"
    )
    escalated: bool = Field(
        default=False,
        description="Whether the request was escalated to human review"
    )
