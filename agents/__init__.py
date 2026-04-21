"""
Multi-Agent Framework

This module provides the foundational multi-agent framework for the AI service.
All agents inherit from the base agent class and use structured Pydantic models
for type-safe communication.

Architecture:
- Base agent class: Abstract interface that all agents implement
- Pydantic models: Type-safe data structures for agent inputs/outputs
- Cache protocol: Abstract interface for caching (implementation in Phase 2)

Usage:
    from agents.base import BaseAgent
    from agents.models.agent_models import AgentRequest, AgentResponse
    
    class MyAgent(BaseAgent):
        def execute(self, request: AgentRequest) -> AgentResponse:
            # Implementation here
            pass
"""

from agents.base import BaseAgent, AgentError, AgentExecutionError, AgentValidationError

__all__ = [
    "BaseAgent",
    "AgentError",
    "AgentExecutionError",
    "AgentValidationError",
]
