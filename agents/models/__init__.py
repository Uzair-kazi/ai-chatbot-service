"""
Agent Models

This module provides Pydantic models for agent communication.
All models enforce type safety and automatic validation.

Models:
- AgentRequest: Base request model for all agents
- AgentResponse: Base response model for all agents
- SQLGenerationRequest: Request model for SQL generation
- SQLGenerationResponse: Response model for SQL generation
"""

from agents.models.agent_models import AgentRequest, AgentResponse
from agents.models.query_models import SQLGenerationRequest, SQLGenerationResponse

__all__ = [
    "AgentRequest",
    "AgentResponse",
    "SQLGenerationRequest",
    "SQLGenerationResponse",
]
