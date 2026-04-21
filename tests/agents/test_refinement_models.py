"""
Tests for Query Refinement Pydantic Models

This module tests the refinement models including validation,
type safety, and edge cases.
"""

import pytest
from datetime import datetime
from pydantic import ValidationError
from agents.models.refinement_models import RefinementRequest, RefinementResponse


# ============================================================================
# RefinementRequest Tests - Happy Path
# ============================================================================

def test_refinement_request_with_business_glossary():
    """Test that RefinementRequest validates with business glossary."""
    request = RefinementRequest(
        question="Which clients have the most tanks this month?",
        db_schema="Table: iso_tank\n  - id: uuid\n  - croyance_client_name: varchar",
        business_glossary={
            "temporal_terms": {
                "this_month": "WHERE created_at >= DATE_TRUNC('month', CURRENT_DATE)"
            },
            "entity_mappings": {
                "clients": "vehicle_in.croyance_client_name"
            }
        }
    )
    
    assert request.question == "Which clients have the most tanks this month?"
    assert "temporal_terms" in request.business_glossary
    assert "entity_mappings" in request.business_glossary
    assert request.business_glossary["temporal_terms"]["this_month"] == "WHERE created_at >= DATE_TRUNC('month', CURRENT_DATE)"


def test_refinement_request_with_current_datetime():
    """Test that RefinementRequest accepts current_datetime."""
    now = datetime(2024, 3, 15, 10, 30, 0)
    request = RefinementRequest(
        question="Show me tanks from today",
        db_schema="Table: iso_tank",
        current_datetime=now
    )
    
    assert request.current_datetime == now


def test_refinement_request_default_current_datetime():
    """Test that RefinementRequest uses default current_datetime."""
    before = datetime.now()
    request = RefinementRequest(
        question="Show me tanks",
        db_schema="Table: iso_tank"
    )
    after = datetime.now()
    
    # Should be between before and after
    assert before <= request.current_datetime <= after


def test_refinement_request_empty_business_glossary():
    """Test that RefinementRequest accepts empty business glossary."""
    request = RefinementRequest(
        question="Show me tanks",
        db_schema="Table: iso_tank",
        business_glossary={}
    )
    
    assert request.business_glossary == {}


def test_refinement_request_with_context():
    """Test that RefinementRequest accepts context."""
    request = RefinementRequest(
        question="Show me tanks",
        db_schema="Table: iso_tank",
        context={"user_id": "123", "session_id": "abc"}
    )
    
    assert request.context == {"user_id": "123", "session_id": "abc"}


def test_refinement_request_complex_business_glossary():
    """Test that RefinementRequest accepts complex business glossary."""
    request = RefinementRequest(
        question="Show me client tanks from last quarter",
        db_schema="Table: iso_tank",
        business_glossary={
            "temporal_terms": {
                "this_month": "WHERE created_at >= DATE_TRUNC('month', CURRENT_DATE)",
                "last_quarter": "WHERE created_at >= DATE_TRUNC('quarter', CURRENT_DATE - INTERVAL '3 months')",
                "today": "WHERE DATE(created_at) = CURRENT_DATE"
            },
            "entity_mappings": {
                "clients": "vehicle_in.croyance_client_name",
                "tanks": "iso_tank table (for ISO tanks) or service_tank table (for service tanks)",
                "tank_status": "iso_tank_status or service_tank_status"
            }
        }
    )
    
    assert len(request.business_glossary["temporal_terms"]) == 3
    assert len(request.business_glossary["entity_mappings"]) == 3


# ============================================================================
# RefinementRequest Tests - Edge Cases and Validation
# ============================================================================

def test_refinement_request_empty_raw_question_raises_error():
    """Test that empty raw_question raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        RefinementRequest(
            question="",
            db_schema="Table: iso_tank"
        )
    
    errors = exc_info.value.errors()
    assert len(errors) > 0
    assert any("question" in str(error).lower() for error in errors)


def test_refinement_request_whitespace_raw_question_raises_error():
    """Test that whitespace-only raw_question raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        RefinementRequest(
            question="   ",
            db_schema="Table: iso_tank"
        )
    
    errors = exc_info.value.errors()
    assert len(errors) > 0
    assert any("question" in str(error).lower() for error in errors)


def test_refinement_request_wrong_type_business_glossary():
    """Test that wrong type for business_glossary raises ValidationError."""
    with pytest.raises(ValidationError):
        RefinementRequest(
            question="Show me tanks",
            db_schema="Table: iso_tank",
            business_glossary="not a dict"  # Should be dict
        )


def test_refinement_request_invalid_nested_business_glossary():
    """Test that invalid nested structure in business_glossary raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        RefinementRequest(
            question="Show me tanks",
            db_schema="Table: iso_tank",
            business_glossary={
                "temporal_terms": "not a dict"  # Should be dict
            }
        )
    
    errors = exc_info.value.errors()
    assert len(errors) > 0
    assert any("business_glossary" in str(error).lower() for error in errors)


def test_refinement_request_wrong_type_current_datetime():
    """Test that wrong type for current_datetime raises ValidationError."""
    with pytest.raises(ValidationError):
        RefinementRequest(
            question="Show me tanks",
            db_schema="Table: iso_tank",
            current_datetime="invalid-datetime"  # Should be datetime object
        )


# ============================================================================
# RefinementResponse Tests - Happy Path
# ============================================================================

def test_refinement_response_success():
    """Test that RefinementResponse validates with success."""
    response = RefinementResponse(
        success=True,
        refined_query="Retrieve count of ISO tanks grouped by croyance_client_name "
                     "WHERE created_at >= DATE_TRUNC('month', CURRENT_DATE) "
                     "ORDER BY count DESC",
        confidence=0.9,
        clarification_questions=[]
    )
    
    assert response.success is True
    assert "DATE_TRUNC" in response.refined_query
    assert response.confidence == 0.9
    assert response.clarification_questions == []


def test_refinement_response_with_clarification_questions():
    """Test that RefinementResponse accepts clarification questions."""
    response = RefinementResponse(
        success=True,
        refined_query="Show best products",
        confidence=0.5,
        clarification_questions=[
            "Do you mean best by revenue or by quantity?",
            "What time period should be considered?"
        ]
    )
    
    assert len(response.clarification_questions) == 2
    assert "revenue or by quantity" in response.clarification_questions[0]


def test_refinement_response_low_confidence():
    """Test that RefinementResponse accepts low confidence."""
    response = RefinementResponse(
        success=True,
        refined_query="Ambiguous query",
        confidence=0.3,
        clarification_questions=["Please clarify your intent"]
    )
    
    assert response.confidence == 0.3
    assert len(response.clarification_questions) == 1


def test_refinement_response_high_confidence():
    """Test that RefinementResponse accepts high confidence."""
    response = RefinementResponse(
        success=True,
        refined_query="SELECT COUNT(*) FROM iso_tank WHERE DATE(created_at) = CURRENT_DATE",
        confidence=0.95
    )
    
    assert response.confidence == 0.95


def test_refinement_response_default_values():
    """Test that RefinementResponse uses default values."""
    response = RefinementResponse(success=True)
    
    assert response.refined_query == ""
    assert response.clarification_questions == []
    assert response.confidence == 1.0


def test_refinement_response_with_metadata():
    """Test that RefinementResponse accepts metadata."""
    response = RefinementResponse(
        success=True,
        refined_query="Refined query",
        confidence=0.9,
        metadata={
            "execution_time": 0.5,
            "token_usage": 200,
            "glossary_terms_matched": 2
        }
    )
    
    assert response.metadata["glossary_terms_matched"] == 2


# ============================================================================
# RefinementResponse Tests - Edge Cases and Validation
# ============================================================================

def test_refinement_response_confidence_boundary_values():
    """Test that confidence accepts boundary values 0.0 and 1.0."""
    response_min = RefinementResponse(
        success=True,
        refined_query="Query",
        confidence=0.0
    )
    
    response_max = RefinementResponse(
        success=True,
        refined_query="Query",
        confidence=1.0
    )
    
    assert response_min.confidence == 0.0
    assert response_max.confidence == 1.0


def test_refinement_response_confidence_below_zero_raises_error():
    """Test that confidence below 0.0 raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        RefinementResponse(
            success=True,
            refined_query="Query",
            confidence=-0.1
        )
    
    errors = exc_info.value.errors()
    assert len(errors) > 0
    assert any("confidence" in str(error).lower() for error in errors)


def test_refinement_response_confidence_above_one_raises_error():
    """Test that confidence above 1.0 raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        RefinementResponse(
            success=True,
            refined_query="Query",
            confidence=1.1
        )
    
    errors = exc_info.value.errors()
    assert len(errors) > 0
    assert any("confidence" in str(error).lower() for error in errors)


def test_refinement_response_wrong_type_refined_query():
    """Test that wrong type for refined_query raises ValidationError."""
    with pytest.raises(ValidationError):
        RefinementResponse(
            success=True,
            refined_query=123,  # Should be string
            confidence=0.9
        )


def test_refinement_response_wrong_type_clarification_questions():
    """Test that wrong type for clarification_questions raises ValidationError."""
    with pytest.raises(ValidationError):
        RefinementResponse(
            success=True,
            refined_query="Query",
            clarification_questions="not a list",  # Should be list
            confidence=0.9
        )


def test_refinement_response_wrong_type_confidence():
    """Test that wrong type for confidence raises ValidationError."""
    with pytest.raises(ValidationError):
        RefinementResponse(
            success=True,
            refined_query="Query",
            confidence="high"  # Should be float
        )


# ============================================================================
# Integration Tests
# ============================================================================

def test_refinement_request_response_round_trip():
    """Test that request and response work together."""
    request = RefinementRequest(
        question="Which clients have the most tanks this month?",
        db_schema="Table: iso_tank",
        business_glossary={
            "temporal_terms": {
                "this_month": "WHERE created_at >= DATE_TRUNC('month', CURRENT_DATE)"
            },
            "entity_mappings": {
                "clients": "vehicle_in.croyance_client_name"
            }
        }
    )
    
    response = RefinementResponse(
        success=True,
        refined_query="Retrieve count of ISO tanks grouped by croyance_client_name "
                     "WHERE created_at >= DATE_TRUNC('month', CURRENT_DATE) "
                     "ORDER BY count DESC",
        confidence=0.9,
        clarification_questions=[]
    )
    
    assert request.question == "Which clients have the most tanks this month?"
    assert "temporal_terms" in request.business_glossary
    assert response.refined_query != request.question
    assert "DATE_TRUNC" in response.refined_query
    assert response.confidence == 0.9


def test_refinement_models_json_serialization():
    """Test that models can be serialized to JSON."""
    request = RefinementRequest(
        question="Show me tanks",
        db_schema="Table: iso_tank",
        business_glossary={"temporal_terms": {"today": "WHERE DATE(created_at) = CURRENT_DATE"}}
    )
    
    response = RefinementResponse(
        success=True,
        refined_query="Retrieve tanks from today",
        confidence=0.9
    )
    
    # Should not raise exception
    request_json = request.model_dump_json()
    response_json = response.model_dump_json()
    
    assert "Show me tanks" in request_json
    assert "refined_query" in response_json


def test_refinement_models_dict_conversion():
    """Test that models can be converted to dict."""
    request = RefinementRequest(
        question="Show me tanks",
        db_schema="Table: iso_tank",
        business_glossary={"temporal_terms": {}}
    )
    
    request_dict = request.model_dump()
    
    assert request_dict["question"] == "Show me tanks"
    assert "business_glossary" in request_dict


def test_refinement_response_confidence_pattern():
    """Test confidence pattern for different query clarity levels."""
    # Clear query
    response_clear = RefinementResponse(
        success=True,
        refined_query="SELECT COUNT(*) FROM iso_tank",
        confidence=0.9,
        clarification_questions=[]
    )
    
    # Ambiguous query
    response_ambiguous = RefinementResponse(
        success=True,
        refined_query="Show products",
        confidence=0.7,
        clarification_questions=[]
    )
    
    # Needs clarification
    response_unclear = RefinementResponse(
        success=True,
        refined_query="Show best items",
        confidence=0.5,
        clarification_questions=["By revenue or quantity?"]
    )
    
    assert response_clear.confidence > response_ambiguous.confidence > response_unclear.confidence
    assert len(response_clear.clarification_questions) == 0
    assert len(response_unclear.clarification_questions) > 0


def test_refinement_temporal_resolution_pattern():
    """Test temporal resolution pattern."""
    request = RefinementRequest(
        question="Show me tanks from this month",
        db_schema="Table: iso_tank",
        business_glossary={
            "temporal_terms": {
                "this_month": "WHERE created_at >= DATE_TRUNC('month', CURRENT_DATE)",
                "last_quarter": "WHERE created_at >= DATE_TRUNC('quarter', CURRENT_DATE - INTERVAL '3 months')",
                "today": "WHERE DATE(created_at) = CURRENT_DATE"
            }
        },
        current_datetime=datetime(2024, 3, 15, 10, 30, 0)
    )
    
    response = RefinementResponse(
        success=True,
        refined_query="Retrieve ISO tanks WHERE created_at >= DATE_TRUNC('month', CURRENT_DATE)",
        confidence=0.9
    )
    
    assert "this_month" in request.business_glossary["temporal_terms"]
    assert "DATE_TRUNC('month', CURRENT_DATE)" in response.refined_query


def test_refinement_business_terminology_mapping_pattern():
    """Test business terminology mapping pattern."""
    request = RefinementRequest(
        question="Show me clients with tanks",
        db_schema="Table: vehicle_in, iso_tank",
        business_glossary={
            "entity_mappings": {
                "clients": "vehicle_in.croyance_client_name",
                "tanks": "iso_tank table"
            }
        }
    )
    
    response = RefinementResponse(
        success=True,
        refined_query="Retrieve croyance_client_name from vehicle_in JOIN iso_tank",
        confidence=0.85
    )
    
    assert "clients" in request.business_glossary["entity_mappings"]
    assert "croyance_client_name" in response.refined_query


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
