"""
Query Refinement Models

This module defines Pydantic models for the Query Refinement Agent.
These models handle query transformation with business glossary and temporal resolution.

Models:
- RefinementRequest: Request model for query refinement
- RefinementResponse: Response model with refined query and confidence
"""

from typing import Dict, List, Optional
from datetime import datetime
from pydantic import Field, field_validator
from agents.models.agent_models import AgentRequest, AgentResponse


class RefinementRequest(AgentRequest):
    """
    Request model for query refinement.
    
    Extends AgentRequest with refinement-specific parameters like business glossary
    and current datetime for temporal resolution.
    
    Attributes:
        question: Natural language question (inherited, used as raw_question)
        db_schema: Database schema (inherited)
        context: Optional context (inherited)
        business_glossary: Business terminology mappings and temporal terms
        current_datetime: Current datetime for temporal ambiguity resolution
        
    Example:
        request = RefinementRequest(
            question="Which clients have the most tanks this month?",
            db_schema="Table: iso_tank...",
            business_glossary={
                "temporal_terms": {
                    "this_month": "WHERE created_at >= DATE_TRUNC('month', CURRENT_DATE)"
                },
                "entity_mappings": {
                    "clients": "vehicle_in.croyance_client_name"
                }
            },
            current_datetime=datetime.now()
        )
    """
    
    business_glossary: Optional[Dict[str, Dict[str, str]]] = Field(
        default=None,
        description="Business terminology mappings and temporal terms (None to use agent's default)"
    )
    current_datetime: datetime = Field(
        default_factory=datetime.now,
        description="Current datetime for temporal resolution"
    )
    
    @field_validator("business_glossary")
    @classmethod
    def validate_business_glossary(cls, v: Optional[Dict[str, Dict[str, str]]]) -> Optional[Dict[str, Dict[str, str]]]:
        """Validate that business_glossary has expected structure."""
        if v is None:
            return v
        
        if not isinstance(v, dict):
            raise ValueError("Business glossary must be a dictionary")
        
        # Validate nested structure if present
        for key, value in v.items():
            if not isinstance(value, dict):
                raise ValueError(f"Business glossary section '{key}' must be a dictionary")
        
        return v


class RefinementResponse(AgentResponse):
    """
    Response model for query refinement.
    
    Extends AgentResponse with refinement-specific fields like refined query,
    confidence score, and clarification questions.
    
    Attributes:
        success: Whether refinement succeeded (inherited)
        data: Result data (inherited)
        error: Error message (inherited)
        confidence: Confidence score (inherited)
        metadata: Metadata (inherited)
        refined_query: Refined query with explicit intent and resolved ambiguity
        clarification_questions: List of questions for ambiguous queries
        
    Example:
        response = RefinementResponse(
            success=True,
            refined_query="Retrieve count of ISO tanks grouped by croyance_client_name "
                         "WHERE created_at >= DATE_TRUNC('month', CURRENT_DATE) "
                         "ORDER BY count DESC",
            confidence=0.9,
            clarification_questions=[]
        )
    """
    
    refined_query: str = Field(
        default="",
        description="Refined query with explicit intent"
    )
    clarification_questions: List[str] = Field(
        default_factory=list,
        description="List of clarification questions for ambiguous queries"
    )
    
    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        """Validate that confidence is between 0.0 and 1.0."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")
        return v
