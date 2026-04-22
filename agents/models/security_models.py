"""
Security & Governance Models

This module defines Pydantic models for the Security & Governance Agent.
These models handle security validation, risk scoring, and veto decisions.

Models:
- SecurityRequest: Request model for security validation
- SecurityResponse: Response model with approval decision and risk assessment
"""

from typing import List, Optional
from pydantic import Field, field_validator
from agents.models.agent_models import AgentRequest, AgentResponse


class SecurityRequest(AgentRequest):
    """
    Request model for security validation.
    
    Extends AgentRequest with security-specific parameters like refined query,
    user role, and generated SQL for validation.
    
    Attributes:
        question: Natural language question (inherited)
        db_schema: Database schema (inherited)
        context: Optional context (inherited)
        refined_query: Refined query with explicit intent from Query Refinement Agent
        user_role: User role for RBAC enforcement (admin, analyst, viewer)
        generated_sql: Optional generated SQL to validate (if available)
        
    Example:
        request = SecurityRequest(
            question="Show me all driver license numbers",
            db_schema="Table: vehicle_in...",
            refined_query="Retrieve driver_mobile_number and license_number from vehicle_in",
            user_role="analyst",
            generated_sql="SELECT driver_mobile_number, license_number FROM vehicle_in"
        )
    """
    
    refined_query: str = Field(
        ...,
        description="Refined query with explicit intent",
        min_length=1
    )
    user_role: str = Field(
        ...,
        description="User role for RBAC enforcement",
        min_length=1
    )
    generated_sql: Optional[str] = Field(
        default=None,
        description="Optional generated SQL to validate"
    )
    
    @field_validator("refined_query")
    @classmethod
    def validate_refined_query(cls, v: str) -> str:
        """Validate that refined_query is not empty or whitespace-only."""
        if not v or not v.strip():
            raise ValueError("Refined query cannot be empty or whitespace-only")
        return v.strip()
    
    @field_validator("user_role")
    @classmethod
    def validate_user_role(cls, v: str) -> str:
        """Validate that user_role is not empty and is a valid role."""
        if not v or not v.strip():
            raise ValueError("User role cannot be empty or whitespace-only")
        
        valid_roles = ["admin", "analyst", "viewer"]
        role = v.strip().lower()
        if role not in valid_roles:
            raise ValueError(f"User role must be one of {valid_roles}, got '{role}'")
        
        return role


class SecurityResponse(AgentResponse):
    """
    Response model for security validation.
    
    Extends AgentResponse with security-specific fields like approval decision,
    risk score, veto reason, and alternative suggestions.
    
    Attributes:
        success: Whether validation succeeded (inherited)
        data: Result data (inherited)
        error: Error message (inherited)
        confidence: Confidence score (inherited)
        metadata: Metadata (inherited)
        approved: Whether the query is approved (True) or vetoed (False)
        risk_score: Risk score between 0.0 and 1.0 (0.0 = no risk, 1.0 = critical risk)
        veto_reason: Optional reason for veto (present if approved=False)
        alternative_suggestions: List of alternative query suggestions
        
    Example:
        response = SecurityResponse(
            success=True,
            approved=False,
            risk_score=1.0,
            veto_reason="PII access denied: driver_mobile_number, license_number",
            alternative_suggestions=[
                "Request aggregated statistics instead of individual records",
                "Contact admin for PII access approval"
            ],
            confidence=1.0
        )
    """
    
    approved: bool = Field(
        ...,
        description="Whether the query is approved"
    )
    risk_score: float = Field(
        ...,
        description="Risk score between 0.0 and 1.0",
        ge=0.0,
        le=1.0
    )
    veto_reason: Optional[str] = Field(
        default=None,
        description="Optional reason for veto"
    )
    alternative_suggestions: List[str] = Field(
        default_factory=list,
        description="List of alternative query suggestions"
    )
    
    @field_validator("risk_score")
    @classmethod
    def validate_risk_score(cls, v: float) -> float:
        """Validate that risk_score is between 0.0 and 1.0."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Risk score must be between 0.0 and 1.0")
        return v
