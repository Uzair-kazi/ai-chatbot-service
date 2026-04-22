"""
Pydantic models for Result Formatter Agent

These models define the request and response structures for the Result Formatter Agent.
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class FormatterRequest(BaseModel):
    """
    Request model for Result Formatter Agent.
    
    Attributes:
        question: Original user question
        sql: SQL query to execute
        context: Optional context dictionary
    """
    question: str = Field(..., description="Original user question")
    sql: str = Field(..., description="SQL query to execute")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Optional context")


class FormatterResponse(BaseModel):
    """
    Response model for Result Formatter Agent.
    
    Attributes:
        success: Whether formatting succeeded
        answer: Natural language answer
        sql: SQL query that was executed
        rows_count: Number of rows returned
        execution_time: Query execution time in seconds
        formatting_method: Method used (template or llm)
        error: Error message if failed
        confidence: Confidence score (0.0-1.0)
        metadata: Additional metadata
    """
    success: bool = Field(..., description="Whether formatting succeeded")
    answer: str = Field(..., description="Natural language answer")
    sql: str = Field(..., description="SQL query that was executed")
    rows_count: int = Field(..., description="Number of rows returned")
    execution_time: float = Field(..., description="Query execution time in seconds")
    formatting_method: str = Field(..., description="Method used: template or llm")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    confidence: float = Field(default=1.0, description="Confidence score (0.0-1.0)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
