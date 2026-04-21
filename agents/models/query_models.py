"""
Query-Specific Models

This module defines Pydantic models specific to SQL generation and query processing.
These models extend the base agent models with SQL-specific fields.

Models:
- SQLGenerationRequest: Request model for SQL generation with retry and temperature settings
- SQLGenerationResponse: Response model for SQL generation with validation issues and retry count
"""

from typing import List, Optional
from pydantic import Field, field_validator
from agents.models.agent_models import AgentRequest, AgentResponse


class SQLGenerationRequest(AgentRequest):
    """
    Request model for SQL generation.
    
    Extends AgentRequest with SQL-specific parameters like max retries and temperature.
    
    Attributes:
        question: Natural language question (inherited)
        schema: Database schema (inherited)
        context: Optional context (inherited)
        max_retries: Maximum number of retry attempts for self-critique loop
        temperature: AI temperature for generation (0.0-1.0, lower = more deterministic)
        
    Example:
        request = SQLGenerationRequest(
            question="How many ISO tanks?",
            schema="Table: iso_tank...",
            max_retries=2,
            temperature=0.1
        )
    """
    
    max_retries: int = Field(
        default=2,
        description="Maximum number of retry attempts",
        ge=0,
        le=5
    )
    temperature: float = Field(
        default=0.1,
        description="AI temperature for generation",
        ge=0.0,
        le=1.0
    )
    
    @field_validator("max_retries")
    @classmethod
    def validate_max_retries(cls, v: int) -> int:
        """Validate that max_retries is reasonable (0-5)."""
        if not 0 <= v <= 5:
            raise ValueError("max_retries must be between 0 and 5")
        return v
    
    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        """Validate that temperature is between 0.0 and 1.0."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("temperature must be between 0.0 and 1.0")
        return v


class SQLGenerationResponse(AgentResponse):
    """
    Response model for SQL generation.
    
    Extends AgentResponse with SQL-specific fields like the generated SQL,
    validation issues, and retry count.
    
    Attributes:
        success: Whether generation succeeded (inherited)
        data: Result data (inherited)
        error: Error message (inherited)
        confidence: Confidence score (inherited)
        metadata: Metadata (inherited)
        sql: Generated SQL query (None if generation failed)
        validation_issues: List of validation issues found during self-critique
        retry_count: Number of retry attempts made
        
    Example:
        response = SQLGenerationResponse(
            success=True,
            sql="SELECT COUNT(*) FROM iso_tank LIMIT 100;",
            validation_issues=[],
            retry_count=0,
            confidence=0.9
        )
    """
    
    sql: Optional[str] = Field(
        default=None,
        description="Generated SQL query"
    )
    validation_issues: List[str] = Field(
        default_factory=list,
        description="List of validation issues"
    )
    retry_count: int = Field(
        default=0,
        description="Number of retry attempts made",
        ge=0
    )
    
    @field_validator("retry_count")
    @classmethod
    def validate_retry_count(cls, v: int) -> int:
        """Validate that retry_count is non-negative."""
        if v < 0:
            raise ValueError("retry_count must be non-negative")
        return v
