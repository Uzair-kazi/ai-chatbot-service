"""
Tests for Query-Specific Pydantic Models

This module tests the SQL generation models including validation,
type safety, and edge cases.
"""

import pytest
from pydantic import ValidationError
from agents.models.query_models import SQLGenerationRequest, SQLGenerationResponse


# ============================================================================
# SQLGenerationRequest Tests - Happy Path
# ============================================================================

def test_sql_generation_request_with_defaults():
    """Test that SQLGenerationRequest uses default values."""
    request = SQLGenerationRequest(
        question="How many ISO tanks?",
        db_schema="Table: iso_tank\n  - id: uuid"
    )
    
    assert request.question == "How many ISO tanks?"
    assert request.db_schema == "Table: iso_tank\n  - id: uuid"
    assert request.max_retries == 2  # Default
    assert request.temperature == 0.1  # Default
    assert request.context is None


def test_sql_generation_request_with_custom_values():
    """Test that SQLGenerationRequest accepts custom values."""
    request = SQLGenerationRequest(
        question="How many ISO tanks?",
        db_schema="Table: iso_tank\n  - id: uuid",
        max_retries=3,
        temperature=0.2
    )
    
    assert request.max_retries == 3
    assert request.temperature == 0.2


def test_sql_generation_request_with_context():
    """Test that SQLGenerationRequest accepts context."""
    request = SQLGenerationRequest(
        question="How many ISO tanks?",
        db_schema="Table: iso_tank\n  - id: uuid",
        context={"user_id": "123"}
    )
    
    assert request.context == {"user_id": "123"}


# ============================================================================
# SQLGenerationRequest Tests - Edge Cases and Validation
# ============================================================================

def test_sql_generation_request_max_retries_boundary_values():
    """Test that max_retries accepts boundary values 0 and 5."""
    request_min = SQLGenerationRequest(
        question="How many ISO tanks?",
        db_schema="Table: iso_tank\n  - id: uuid",
        max_retries=0
    )
    
    request_max = SQLGenerationRequest(
        question="How many ISO tanks?",
        db_schema="Table: iso_tank\n  - id: uuid",
        max_retries=5
    )
    
    assert request_min.max_retries == 0
    assert request_max.max_retries == 5


def test_sql_generation_request_max_retries_below_zero_raises_error():
    """Test that max_retries below 0 raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        SQLGenerationRequest(
            question="How many ISO tanks?",
            db_schema="Table: iso_tank\n  - id: uuid",
            max_retries=-1
        )
    
    errors = exc_info.value.errors()
    assert len(errors) > 0
    assert any("max_retries" in str(error).lower() for error in errors)


def test_sql_generation_request_max_retries_above_five_raises_error():
    """Test that max_retries above 5 raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        SQLGenerationRequest(
            question="How many ISO tanks?",
            db_schema="Table: iso_tank\n  - id: uuid",
            max_retries=6
        )
    
    errors = exc_info.value.errors()
    assert len(errors) > 0
    assert any("max_retries" in str(error).lower() for error in errors)


def test_sql_generation_request_temperature_boundary_values():
    """Test that temperature accepts boundary values 0.0 and 1.0."""
    request_min = SQLGenerationRequest(
        question="How many ISO tanks?",
        db_schema="Table: iso_tank\n  - id: uuid",
        temperature=0.0
    )
    
    request_max = SQLGenerationRequest(
        question="How many ISO tanks?",
        db_schema="Table: iso_tank\n  - id: uuid",
        temperature=1.0
    )
    
    assert request_min.temperature == 0.0
    assert request_max.temperature == 1.0


def test_sql_generation_request_temperature_below_zero_raises_error():
    """Test that temperature below 0.0 raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        SQLGenerationRequest(
            question="How many ISO tanks?",
            db_schema="Table: iso_tank\n  - id: uuid",
            temperature=-0.1
        )
    
    errors = exc_info.value.errors()
    assert len(errors) > 0
    assert any("temperature" in str(error).lower() for error in errors)


def test_sql_generation_request_temperature_above_one_raises_error():
    """Test that temperature above 1.0 raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        SQLGenerationRequest(
            question="How many ISO tanks?",
            db_schema="Table: iso_tank\n  - id: uuid",
            temperature=1.1
        )
    
    errors = exc_info.value.errors()
    assert len(errors) > 0
    assert any("temperature" in str(error).lower() for error in errors)


def test_sql_generation_request_wrong_type_max_retries():
    """Test that wrong type for max_retries raises ValidationError."""
    with pytest.raises(ValidationError):
        SQLGenerationRequest(
            question="How many ISO tanks?",
            db_schema="Table: iso_tank\n  - id: uuid",
            max_retries="two"  # Should be int
        )


def test_sql_generation_request_wrong_type_temperature():
    """Test that wrong type for temperature raises ValidationError."""
    with pytest.raises(ValidationError):
        SQLGenerationRequest(
            question="How many ISO tanks?",
            db_schema="Table: iso_tank\n  - id: uuid",
            temperature="low"  # Should be float
        )


# ============================================================================
# SQLGenerationResponse Tests - Happy Path
# ============================================================================

def test_sql_generation_response_success():
    """Test that SQLGenerationResponse validates with success."""
    response = SQLGenerationResponse(
        success=True,
        sql="SELECT COUNT(*) FROM iso_tank LIMIT 100;",
        validation_issues=[],
        retry_count=0,
        confidence=0.9
    )
    
    assert response.success is True
    assert response.sql == "SELECT COUNT(*) FROM iso_tank LIMIT 100;"
    assert response.validation_issues == []
    assert response.retry_count == 0
    assert response.confidence == 0.9


def test_sql_generation_response_with_validation_issues():
    """Test that SQLGenerationResponse accepts validation issues."""
    response = SQLGenerationResponse(
        success=False,
        sql="SELECT invalid_column FROM iso_tank;",
        validation_issues=["Column 'invalid_column' does not exist"],
        retry_count=1,
        confidence=0.75
    )
    
    assert response.success is False
    assert len(response.validation_issues) == 1
    assert "invalid_column" in response.validation_issues[0]
    assert response.retry_count == 1


def test_sql_generation_response_with_multiple_validation_issues():
    """Test that SQLGenerationResponse accepts multiple validation issues."""
    response = SQLGenerationResponse(
        success=False,
        sql="SELECT col1, col2 FROM invalid_table;",
        validation_issues=[
            "Table 'invalid_table' does not exist",
            "Column 'col1' does not exist",
            "Column 'col2' does not exist"
        ],
        retry_count=2,
        confidence=0.6
    )
    
    assert len(response.validation_issues) == 3
    assert response.retry_count == 2


def test_sql_generation_response_default_values():
    """Test that SQLGenerationResponse uses default values."""
    response = SQLGenerationResponse(success=True)
    
    assert response.sql is None
    assert response.validation_issues == []
    assert response.retry_count == 0
    assert response.confidence == 1.0


def test_sql_generation_response_with_metadata():
    """Test that SQLGenerationResponse accepts metadata."""
    response = SQLGenerationResponse(
        success=True,
        sql="SELECT * FROM iso_tank LIMIT 100;",
        metadata={"execution_time": 1.23, "token_usage": 500}
    )
    
    assert response.metadata == {"execution_time": 1.23, "token_usage": 500}


# ============================================================================
# SQLGenerationResponse Tests - Edge Cases and Validation
# ============================================================================

def test_sql_generation_response_retry_count_negative_raises_error():
    """Test that negative retry_count raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        SQLGenerationResponse(
            success=True,
            retry_count=-1
        )
    
    errors = exc_info.value.errors()
    assert len(errors) > 0
    assert any("retry_count" in str(error).lower() for error in errors)


def test_sql_generation_response_retry_count_zero():
    """Test that retry_count accepts zero."""
    response = SQLGenerationResponse(
        success=True,
        retry_count=0
    )
    
    assert response.retry_count == 0


def test_sql_generation_response_wrong_type_sql():
    """Test that wrong type for sql raises ValidationError."""
    with pytest.raises(ValidationError):
        SQLGenerationResponse(
            success=True,
            sql=123  # Should be string or None
        )


def test_sql_generation_response_wrong_type_validation_issues():
    """Test that wrong type for validation_issues raises ValidationError."""
    with pytest.raises(ValidationError):
        SQLGenerationResponse(
            success=True,
            validation_issues="not a list"  # Should be list
        )


def test_sql_generation_response_wrong_type_retry_count():
    """Test that wrong type for retry_count raises ValidationError."""
    with pytest.raises(ValidationError):
        SQLGenerationResponse(
            success=True,
            retry_count="one"  # Should be int
        )


# ============================================================================
# Integration Tests
# ============================================================================

def test_sql_generation_request_response_round_trip():
    """Test that request and response work together."""
    request = SQLGenerationRequest(
        question="How many ISO tanks?",
        db_schema="Table: iso_tank\n  - id: uuid",
        max_retries=2,
        temperature=0.1
    )
    
    response = SQLGenerationResponse(
        success=True,
        sql="SELECT COUNT(*) FROM iso_tank LIMIT 100;",
        validation_issues=[],
        retry_count=0,
        confidence=0.9
    )
    
    assert request.question == "How many ISO tanks?"
    assert request.max_retries == 2
    assert response.success is True
    assert response.sql == "SELECT COUNT(*) FROM iso_tank LIMIT 100;"
    assert response.retry_count == 0


def test_sql_generation_models_json_serialization():
    """Test that models can be serialized to JSON."""
    request = SQLGenerationRequest(
        question="How many ISO tanks?",
        db_schema="Table: iso_tank\n  - id: uuid"
    )
    
    response = SQLGenerationResponse(
        success=True,
        sql="SELECT COUNT(*) FROM iso_tank LIMIT 100;"
    )
    
    # Should not raise exception
    request_json = request.model_dump_json()
    response_json = response.model_dump_json()
    
    assert "How many ISO tanks?" in request_json
    assert "SELECT COUNT(*)" in response_json


def test_sql_generation_models_dict_conversion():
    """Test that models can be converted to dict."""
    request = SQLGenerationRequest(
        question="How many ISO tanks?",
        db_schema="Table: iso_tank\n  - id: uuid",
        max_retries=3
    )
    
    request_dict = request.model_dump()
    
    assert request_dict["question"] == "How many ISO tanks?"
    assert request_dict["max_retries"] == 3
    assert request_dict["temperature"] == 0.1


def test_sql_generation_response_confidence_decay_pattern():
    """Test confidence decay pattern across retry attempts."""
    # First attempt
    response1 = SQLGenerationResponse(
        success=True,
        sql="SELECT * FROM iso_tank LIMIT 100;",
        retry_count=0,
        confidence=0.9
    )
    
    # Second attempt (after retry)
    response2 = SQLGenerationResponse(
        success=True,
        sql="SELECT * FROM iso_tank LIMIT 100;",
        retry_count=1,
        confidence=0.75
    )
    
    # Third attempt (after second retry)
    response3 = SQLGenerationResponse(
        success=True,
        sql="SELECT * FROM iso_tank LIMIT 100;",
        retry_count=2,
        confidence=0.6
    )
    
    assert response1.confidence > response2.confidence > response3.confidence
    assert response1.retry_count < response2.retry_count < response3.retry_count


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
