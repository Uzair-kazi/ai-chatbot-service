"""
Tests for Security & Governance Pydantic Models

This module tests the security models including validation,
type safety, and edge cases.
"""

import pytest
from pydantic import ValidationError
from agents.models.security_models import SecurityRequest, SecurityResponse


# ============================================================================
# SecurityRequest Tests - Happy Path
# ============================================================================

def test_security_request_with_all_required_fields():
    """Test that SecurityRequest validates with all required fields."""
    request = SecurityRequest(
        question="Show me all driver license numbers",
        db_schema="Table: vehicle_in\n  - driver_mobile_number: varchar\n  - license_number: varchar",
        refined_query="Retrieve driver_mobile_number and license_number from vehicle_in",
        user_role="analyst"
    )
    
    assert request.question == "Show me all driver license numbers"
    assert request.refined_query == "Retrieve driver_mobile_number and license_number from vehicle_in"
    assert request.user_role == "analyst"
    assert request.generated_sql is None


def test_security_request_with_generated_sql():
    """Test that SecurityRequest accepts optional generated_sql."""
    request = SecurityRequest(
        question="How many ISO tanks?",
        db_schema="Table: iso_tank\n  - id: uuid",
        refined_query="Count all ISO tanks",
        user_role="viewer",
        generated_sql="SELECT COUNT(*) FROM iso_tank LIMIT 100;"
    )
    
    assert request.generated_sql == "SELECT COUNT(*) FROM iso_tank LIMIT 100;"


def test_security_request_with_admin_role():
    """Test that SecurityRequest accepts admin role."""
    request = SecurityRequest(
        question="Show all data",
        db_schema="Table: iso_tank",
        refined_query="Retrieve all columns from iso_tank",
        user_role="admin"
    )
    
    assert request.user_role == "admin"


def test_security_request_with_viewer_role():
    """Test that SecurityRequest accepts viewer role."""
    request = SecurityRequest(
        question="Show tanks",
        db_schema="Table: iso_tank",
        refined_query="Retrieve tank_number from iso_tank",
        user_role="viewer"
    )
    
    assert request.user_role == "viewer"


def test_security_request_role_case_insensitive():
    """Test that user_role is case-insensitive."""
    request = SecurityRequest(
        question="Show tanks",
        db_schema="Table: iso_tank",
        refined_query="Retrieve tank_number from iso_tank",
        user_role="ANALYST"
    )
    
    assert request.user_role == "analyst"


def test_security_request_with_context():
    """Test that SecurityRequest accepts context."""
    request = SecurityRequest(
        question="Show tanks",
        db_schema="Table: iso_tank",
        refined_query="Retrieve tank_number from iso_tank",
        user_role="analyst",
        context={"user_id": "123", "session_id": "abc"}
    )
    
    assert request.context == {"user_id": "123", "session_id": "abc"}


# ============================================================================
# SecurityRequest Tests - Edge Cases and Validation
# ============================================================================

def test_security_request_empty_refined_query_raises_error():
    """Test that empty refined_query raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        SecurityRequest(
            question="Show tanks",
            db_schema="Table: iso_tank",
            refined_query="",
            user_role="analyst"
        )
    
    errors = exc_info.value.errors()
    assert len(errors) > 0
    assert any("refined_query" in str(error).lower() for error in errors)


def test_security_request_whitespace_refined_query_raises_error():
    """Test that whitespace-only refined_query raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        SecurityRequest(
            question="Show tanks",
            db_schema="Table: iso_tank",
            refined_query="   ",
            user_role="analyst"
        )
    
    errors = exc_info.value.errors()
    assert len(errors) > 0
    assert any("refined_query" in str(error).lower() for error in errors)


def test_security_request_empty_user_role_raises_error():
    """Test that empty user_role raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        SecurityRequest(
            question="Show tanks",
            db_schema="Table: iso_tank",
            refined_query="Retrieve tank_number from iso_tank",
            user_role=""
        )
    
    errors = exc_info.value.errors()
    assert len(errors) > 0
    assert any("user_role" in str(error).lower() or "role" in str(error).lower() for error in errors)


def test_security_request_whitespace_user_role_raises_error():
    """Test that whitespace-only user_role raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        SecurityRequest(
            question="Show tanks",
            db_schema="Table: iso_tank",
            refined_query="Retrieve tank_number from iso_tank",
            user_role="   "
        )
    
    errors = exc_info.value.errors()
    assert len(errors) > 0
    assert any("user_role" in str(error).lower() or "role" in str(error).lower() for error in errors)


def test_security_request_invalid_user_role_raises_error():
    """Test that invalid user_role raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        SecurityRequest(
            question="Show tanks",
            db_schema="Table: iso_tank",
            refined_query="Retrieve tank_number from iso_tank",
            user_role="superuser"
        )
    
    errors = exc_info.value.errors()
    assert len(errors) > 0
    assert any("user_role" in str(error).lower() or "role" in str(error).lower() for error in errors)


def test_security_request_refined_query_strips_whitespace():
    """Test that refined_query strips leading/trailing whitespace."""
    request = SecurityRequest(
        question="Show tanks",
        db_schema="Table: iso_tank",
        refined_query="  Retrieve tank_number from iso_tank  ",
        user_role="analyst"
    )
    
    assert request.refined_query == "Retrieve tank_number from iso_tank"


def test_security_request_wrong_type_refined_query():
    """Test that wrong type for refined_query raises ValidationError."""
    with pytest.raises(ValidationError):
        SecurityRequest(
            question="Show tanks",
            db_schema="Table: iso_tank",
            refined_query=123,  # Should be string
            user_role="analyst"
        )


def test_security_request_wrong_type_user_role():
    """Test that wrong type for user_role raises ValidationError."""
    with pytest.raises(ValidationError):
        SecurityRequest(
            question="Show tanks",
            db_schema="Table: iso_tank",
            refined_query="Retrieve tank_number from iso_tank",
            user_role=123  # Should be string
        )


# ============================================================================
# SecurityResponse Tests - Happy Path
# ============================================================================

def test_security_response_approved():
    """Test that SecurityResponse validates with approved=True."""
    response = SecurityResponse(
        success=True,
        approved=True,
        risk_score=0.0,
        confidence=1.0
    )
    
    assert response.success is True
    assert response.approved is True
    assert response.risk_score == 0.0
    assert response.veto_reason is None
    assert response.alternative_suggestions == []


def test_security_response_vetoed_with_reason():
    """Test that SecurityResponse validates with approved=False and veto_reason."""
    response = SecurityResponse(
        success=True,
        approved=False,
        risk_score=1.0,
        veto_reason="Dangerous operation: DROP TABLE detected",
        confidence=1.0
    )
    
    assert response.approved is False
    assert response.risk_score == 1.0
    assert response.veto_reason == "Dangerous operation: DROP TABLE detected"


def test_security_response_with_alternative_suggestions():
    """Test that SecurityResponse accepts alternative suggestions."""
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
    
    assert len(response.alternative_suggestions) == 2
    assert "aggregated statistics" in response.alternative_suggestions[0]


def test_security_response_with_medium_risk_score():
    """Test that SecurityResponse accepts medium risk score."""
    response = SecurityResponse(
        success=True,
        approved=True,
        risk_score=0.5,
        confidence=0.8
    )
    
    assert response.risk_score == 0.5
    assert response.approved is True


def test_security_response_with_metadata():
    """Test that SecurityResponse accepts metadata."""
    response = SecurityResponse(
        success=True,
        approved=True,
        risk_score=0.2,
        metadata={
            "pii_columns_checked": 5,
            "dangerous_operations_checked": 8,
            "execution_time": 0.05
        },
        confidence=1.0
    )
    
    assert response.metadata["pii_columns_checked"] == 5
    assert response.metadata["execution_time"] == 0.05


# ============================================================================
# SecurityResponse Tests - Edge Cases and Validation
# ============================================================================

def test_security_response_risk_score_boundary_values():
    """Test that risk_score accepts boundary values 0.0 and 1.0."""
    response_min = SecurityResponse(
        success=True,
        approved=True,
        risk_score=0.0,
        confidence=1.0
    )
    
    response_max = SecurityResponse(
        success=True,
        approved=False,
        risk_score=1.0,
        veto_reason="Critical risk",
        confidence=1.0
    )
    
    assert response_min.risk_score == 0.0
    assert response_max.risk_score == 1.0


def test_security_response_risk_score_below_zero_raises_error():
    """Test that risk_score below 0.0 raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        SecurityResponse(
            success=True,
            approved=True,
            risk_score=-0.1,
            confidence=1.0
        )
    
    errors = exc_info.value.errors()
    assert len(errors) > 0
    assert any("risk_score" in str(error).lower() for error in errors)


def test_security_response_risk_score_above_one_raises_error():
    """Test that risk_score above 1.0 raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        SecurityResponse(
            success=True,
            approved=False,
            risk_score=1.1,
            veto_reason="Critical risk",
            confidence=1.0
        )
    
    errors = exc_info.value.errors()
    assert len(errors) > 0
    assert any("risk_score" in str(error).lower() for error in errors)


def test_security_response_wrong_type_approved():
    """Test that wrong type for approved raises ValidationError."""
    with pytest.raises(ValidationError):
        SecurityResponse(
            success=True,
            approved="invalid",  # Should be bool
            risk_score=0.0,
            confidence=1.0
        )


def test_security_response_wrong_type_risk_score():
    """Test that wrong type for risk_score raises ValidationError."""
    with pytest.raises(ValidationError):
        SecurityResponse(
            success=True,
            approved=True,
            risk_score="low",  # Should be float
            confidence=1.0
        )


def test_security_response_wrong_type_alternative_suggestions():
    """Test that wrong type for alternative_suggestions raises ValidationError."""
    with pytest.raises(ValidationError):
        SecurityResponse(
            success=True,
            approved=False,
            risk_score=1.0,
            veto_reason="Blocked",
            alternative_suggestions="not a list",  # Should be list
            confidence=1.0
        )


# ============================================================================
# Integration Tests
# ============================================================================

def test_security_request_response_round_trip():
    """Test that request and response work together."""
    request = SecurityRequest(
        question="Show me all driver license numbers",
        db_schema="Table: vehicle_in\n  - driver_mobile_number: varchar",
        refined_query="Retrieve driver_mobile_number and license_number from vehicle_in",
        user_role="analyst",
        generated_sql="SELECT driver_mobile_number, license_number FROM vehicle_in"
    )
    
    response = SecurityResponse(
        success=True,
        approved=False,
        risk_score=1.0,
        veto_reason="PII access denied: driver_mobile_number, license_number",
        alternative_suggestions=["Request aggregated statistics"],
        confidence=1.0
    )
    
    assert request.user_role == "analyst"
    assert request.refined_query == "Retrieve driver_mobile_number and license_number from vehicle_in"
    assert response.approved is False
    assert response.risk_score == 1.0
    assert "PII access denied" in response.veto_reason


def test_security_models_json_serialization():
    """Test that models can be serialized to JSON."""
    request = SecurityRequest(
        question="Show tanks",
        db_schema="Table: iso_tank",
        refined_query="Retrieve tank_number from iso_tank",
        user_role="viewer"
    )
    
    response = SecurityResponse(
        success=True,
        approved=True,
        risk_score=0.0,
        confidence=1.0
    )
    
    # Should not raise exception
    request_json = request.model_dump_json()
    response_json = response.model_dump_json()
    
    assert "viewer" in request_json
    assert "approved" in response_json


def test_security_models_dict_conversion():
    """Test that models can be converted to dict."""
    request = SecurityRequest(
        question="Show tanks",
        db_schema="Table: iso_tank",
        refined_query="Retrieve tank_number from iso_tank",
        user_role="analyst"
    )
    
    request_dict = request.model_dump()
    
    assert request_dict["user_role"] == "analyst"
    assert request_dict["refined_query"] == "Retrieve tank_number from iso_tank"


def test_security_response_risk_scoring_pattern():
    """Test risk scoring pattern for different scenarios."""
    # No risk
    response_safe = SecurityResponse(
        success=True,
        approved=True,
        risk_score=0.0,
        confidence=1.0
    )
    
    # PII risk
    response_pii = SecurityResponse(
        success=True,
        approved=False,
        risk_score=0.5,
        veto_reason="PII column access",
        confidence=1.0
    )
    
    # Dangerous operation
    response_dangerous = SecurityResponse(
        success=True,
        approved=False,
        risk_score=1.0,
        veto_reason="Dangerous operation: DROP",
        confidence=1.0
    )
    
    assert response_safe.risk_score < response_pii.risk_score < response_dangerous.risk_score
    assert response_safe.approved is True
    assert response_pii.approved is False
    assert response_dangerous.approved is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
