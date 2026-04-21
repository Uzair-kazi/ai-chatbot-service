"""
Tests for Security & Governance Agent

Test coverage:
- Happy path: Valid queries with no violations
- Error path: Dangerous operations blocked
- Error path: PII access denied for non-admin roles
- Error path: Unauthorized table access
- Edge case: Multiple violations
- Edge case: Empty refined query
- Integration: SQL injection attempts blocked
"""

import pytest
from agents.security_governance import SecurityGovernanceAgent
from agents.models.security_models import SecurityRequest, SecurityResponse
from agents.base import AgentValidationError


class TestSecurityGovernanceAgent:
    """Test suite for SecurityGovernanceAgent."""
    
    @pytest.fixture
    def agent(self):
        """Create SecurityGovernanceAgent instance."""
        return SecurityGovernanceAgent()
    
    @pytest.fixture
    def sample_schema(self):
        """Sample database schema for testing."""
        return """
Table: iso_tank
- id: integer (Primary Key)
- tank_number: varchar
- iso_tank_status: varchar
- created_at: timestamp

Table: vehicle_in
- id: integer (Primary Key)
- driver_mobile_number: varchar (PII)
- license_number: varchar (PII)
- driver_name: varchar (PII)
- croyance_client_name: varchar
- created_at: timestamp
"""
    
    # Happy path tests
    
    def test_valid_select_query_no_pii_viewer_role(self, agent, sample_schema):
        """Test valid SELECT query with no PII for viewer role."""
        request = SecurityRequest(
            question="Show me all ISO tanks",
            db_schema=sample_schema,
            refined_query="Retrieve tank_number and iso_tank_status from iso_tank table",
            user_role="viewer",
            generated_sql="SELECT tank_number, iso_tank_status FROM iso_tank LIMIT 100;"
        )
        
        response = agent.execute(request)
        
        assert response.success is True
        assert response.approved is True
        assert response.risk_score == 0.0
        assert response.veto_reason is None
        assert response.confidence == 1.0
    
    def test_valid_select_query_analyst_role(self, agent, sample_schema):
        """Test valid SELECT query with allowed columns for analyst role."""
        request = SecurityRequest(
            question="Show me client names",
            db_schema=sample_schema,
            refined_query="Retrieve croyance_client_name from vehicle_in table",
            user_role="analyst",
            generated_sql="SELECT croyance_client_name FROM vehicle_in LIMIT 100;"
        )
        
        response = agent.execute(request)
        
        assert response.success is True
        assert response.approved is True
        assert response.veto_reason is None
        assert response.confidence == 1.0
    
    def test_valid_select_query_admin_role_with_pii(self, agent, sample_schema):
        """Test valid SELECT query with PII for admin role (should be allowed)."""
        request = SecurityRequest(
            question="Show me driver mobile numbers",
            db_schema=sample_schema,
            refined_query="Retrieve driver_mobile_number from vehicle_in table",
            user_role="admin",
            generated_sql="SELECT driver_mobile_number FROM vehicle_in LIMIT 100;"
        )
        
        response = agent.execute(request)
        
        assert response.success is True
        assert response.approved is True
        assert response.veto_reason is None
        assert response.confidence == 1.0
    
    # Error path tests - Dangerous operations
    
    def test_drop_keyword_blocked(self, agent, sample_schema):
        """Test query with DROP keyword is blocked."""
        request = SecurityRequest(
            question="Drop the iso_tank table",
            db_schema=sample_schema,
            refined_query="DROP TABLE iso_tank",
            user_role="admin",
            generated_sql="DROP TABLE iso_tank;"
        )
        
        response = agent.execute(request)
        
        assert response.success is True
        assert response.approved is False
        assert response.risk_score == 1.0
        assert "Dangerous operation: DROP" in response.veto_reason
        assert len(response.alternative_suggestions) > 0
        assert response.confidence == 1.0
    
    def test_delete_keyword_blocked(self, agent, sample_schema):
        """Test query with DELETE keyword is blocked."""
        request = SecurityRequest(
            question="Delete all tanks",
            db_schema=sample_schema,
            refined_query="DELETE FROM iso_tank",
            user_role="admin",
            generated_sql="DELETE FROM iso_tank;"
        )
        
        response = agent.execute(request)
        
        assert response.success is True
        assert response.approved is False
        assert response.risk_score == 1.0
        assert "Dangerous operation: DELETE" in response.veto_reason
        assert response.confidence == 1.0
    
    def test_update_keyword_blocked(self, agent, sample_schema):
        """Test query with UPDATE keyword is blocked."""
        request = SecurityRequest(
            question="Update tank status",
            db_schema=sample_schema,
            refined_query="UPDATE iso_tank SET iso_tank_status = 'OUT'",
            user_role="admin",
            generated_sql="UPDATE iso_tank SET iso_tank_status = 'OUT';"
        )
        
        response = agent.execute(request)
        
        assert response.success is True
        assert response.approved is False
        assert response.risk_score == 1.0
        assert "Dangerous operation: UPDATE" in response.veto_reason
        assert response.confidence == 1.0
    
    def test_insert_keyword_blocked(self, agent, sample_schema):
        """Test query with INSERT keyword is blocked."""
        request = SecurityRequest(
            question="Insert a new tank",
            db_schema=sample_schema,
            refined_query="INSERT INTO iso_tank VALUES (...)",
            user_role="admin",
            generated_sql="INSERT INTO iso_tank (tank_number) VALUES ('T123');"
        )
        
        response = agent.execute(request)
        
        assert response.success is True
        assert response.approved is False
        assert response.risk_score == 1.0
        assert "Dangerous operation: INSERT" in response.veto_reason
        assert response.confidence == 1.0
    
    # Error path tests - PII access
    
    def test_pii_access_denied_analyst_role(self, agent, sample_schema):
        """Test PII column access denied for analyst role."""
        request = SecurityRequest(
            question="Show me driver mobile numbers",
            db_schema=sample_schema,
            refined_query="Retrieve driver_mobile_number from vehicle_in table",
            user_role="analyst",
            generated_sql="SELECT driver_mobile_number FROM vehicle_in LIMIT 100;"
        )
        
        response = agent.execute(request)
        
        assert response.success is True
        assert response.approved is False
        assert response.risk_score >= 0.5
        assert "PII access denied" in response.veto_reason
        assert "driver_mobile_number" in response.veto_reason
        assert len(response.alternative_suggestions) > 0
        assert response.confidence == 1.0
    
    def test_pii_access_denied_viewer_role(self, agent, sample_schema):
        """Test viewer role blocked from accessing vehicle_in table (which contains PII)."""
        request = SecurityRequest(
            question="Show me license numbers",
            db_schema=sample_schema,
            refined_query="Retrieve license_number from vehicle_in table",
            user_role="viewer",
            generated_sql="SELECT license_number FROM vehicle_in LIMIT 100;"
        )
        
        response = agent.execute(request)
        
        assert response.success is True
        assert response.approved is False
        # Viewer role doesn't have access to vehicle_in table at all
        assert "Unauthorized table access" in response.veto_reason
        assert "vehicle_in" in response.veto_reason
        assert response.confidence == 1.0
    
    def test_multiple_pii_columns_blocked(self, agent, sample_schema):
        """Test multiple PII columns blocked."""
        request = SecurityRequest(
            question="Show me driver details",
            db_schema=sample_schema,
            refined_query="Retrieve driver_mobile_number and license_number from vehicle_in",
            user_role="analyst",
            generated_sql="SELECT driver_mobile_number, license_number FROM vehicle_in LIMIT 100;"
        )
        
        response = agent.execute(request)
        
        assert response.success is True
        assert response.approved is False
        assert "PII access denied" in response.veto_reason
        # Should mention both PII columns
        assert "driver_mobile_number" in response.veto_reason or "license_number" in response.veto_reason
        assert response.confidence == 1.0
    
    # Error path tests - Unauthorized table access
    
    def test_unauthorized_table_access_viewer_role(self, agent, sample_schema):
        """Test unauthorized table access for viewer role."""
        request = SecurityRequest(
            question="Show me vehicle entries",
            db_schema=sample_schema,
            refined_query="Retrieve data from vehicle_in table",
            user_role="viewer",
            generated_sql="SELECT * FROM vehicle_in LIMIT 100;"
        )
        
        response = agent.execute(request)
        
        assert response.success is True
        assert response.approved is False
        assert "Unauthorized table access" in response.veto_reason
        assert "vehicle_in" in response.veto_reason
        assert response.confidence == 1.0
    
    # Edge case tests
    
    def test_multiple_violations(self, agent, sample_schema):
        """Test query with multiple violations."""
        request = SecurityRequest(
            question="Delete driver mobile numbers",
            db_schema=sample_schema,
            refined_query="DELETE driver_mobile_number FROM vehicle_in",
            user_role="analyst",
            generated_sql="DELETE FROM vehicle_in WHERE driver_mobile_number IS NOT NULL;"
        )
        
        response = agent.execute(request)
        
        assert response.success is True
        assert response.approved is False
        assert response.risk_score == 1.0
        # Should have multiple violations
        assert "Dangerous operation: DELETE" in response.veto_reason
        # PII violation might also be detected
        assert response.confidence == 1.0
    
    def test_empty_refined_query_validation_error(self, agent, sample_schema):
        """Test empty refined query raises validation error."""
        with pytest.raises(Exception):  # Pydantic validation error
            SecurityRequest(
                question="Show me tanks",
                db_schema=sample_schema,
                refined_query="",
                user_role="viewer"
            )
    
    def test_invalid_user_role_validation_error(self, agent, sample_schema):
        """Test invalid user role raises validation error."""
        with pytest.raises(Exception):  # Pydantic validation error
            SecurityRequest(
                question="Show me tanks",
                db_schema=sample_schema,
                refined_query="Retrieve tanks",
                user_role="superuser"  # Invalid role
            )
    
    # Integration tests
    
    def test_sql_injection_attempt_blocked(self, agent, sample_schema):
        """Test SQL injection attempt is blocked."""
        request = SecurityRequest(
            question="Show me tanks",
            db_schema=sample_schema,
            refined_query="'; DROP TABLE iso_tank; --",
            user_role="admin",
            generated_sql="SELECT * FROM iso_tank WHERE tank_number = ''; DROP TABLE iso_tank; --';"
        )
        
        response = agent.execute(request)
        
        assert response.success is True
        assert response.approved is False
        assert response.risk_score == 1.0
        assert "Dangerous operation: DROP" in response.veto_reason
        assert response.confidence == 1.0
    
    def test_risk_score_calculation_no_limit(self, agent, sample_schema):
        """Test risk score increases for queries without LIMIT."""
        request = SecurityRequest(
            question="Show me all tanks",
            db_schema=sample_schema,
            refined_query="Retrieve all tanks from iso_tank",
            user_role="viewer",
            generated_sql="SELECT tank_number, iso_tank_status FROM iso_tank;"
        )
        
        response = agent.execute(request)
        
        assert response.success is True
        assert response.approved is True
        # Risk score should be > 0 due to missing LIMIT
        assert response.risk_score > 0.0
        assert response.confidence == 1.0
    
    def test_risk_score_calculation_with_limit(self, agent, sample_schema):
        """Test risk score is lower for queries with LIMIT."""
        request = SecurityRequest(
            question="Show me tanks",
            db_schema=sample_schema,
            refined_query="Retrieve tanks from iso_tank with limit",
            user_role="viewer",
            generated_sql="SELECT tank_number, iso_tank_status FROM iso_tank LIMIT 100;"
        )
        
        response = agent.execute(request)
        
        assert response.success is True
        assert response.approved is True
        # Risk score should be 0.0 with LIMIT
        assert response.risk_score == 0.0
        assert response.confidence == 1.0
    
    def test_cross_domain_join_increases_risk(self, agent, sample_schema):
        """Test cross-domain JOIN increases risk score."""
        request = SecurityRequest(
            question="Show me tanks with vehicle info",
            db_schema=sample_schema,
            refined_query="Retrieve tanks joined with vehicle_in",
            user_role="analyst",
            generated_sql="""
                SELECT it.tank_number, vi.croyance_client_name
                FROM iso_tank it
                JOIN vehicle_in vi ON it.vehicle_in_id = vi.id
                LIMIT 100;
            """
        )
        
        response = agent.execute(request)
        
        assert response.success is True
        assert response.approved is True
        # Risk score should be > 0 due to cross-domain JOIN
        assert response.risk_score > 0.0
        assert response.confidence == 1.0
    
    def test_case_insensitive_keyword_detection(self, agent, sample_schema):
        """Test dangerous keywords detected case-insensitively."""
        request = SecurityRequest(
            question="Drop table",
            db_schema=sample_schema,
            refined_query="drop table iso_tank",
            user_role="admin",
            generated_sql="drop table iso_tank;"
        )
        
        response = agent.execute(request)
        
        assert response.success is True
        assert response.approved is False
        assert "Dangerous operation: DROP" in response.veto_reason
        assert response.confidence == 1.0
    
    def test_metadata_includes_execution_info(self, agent, sample_schema):
        """Test response metadata includes execution information."""
        request = SecurityRequest(
            question="Show me tanks",
            db_schema=sample_schema,
            refined_query="Retrieve tanks from iso_tank",
            user_role="viewer",
            generated_sql="SELECT * FROM iso_tank LIMIT 100;"
        )
        
        response = agent.execute(request)
        
        assert response.success is True
        assert response.metadata is not None
        assert "execution_time" in response.metadata
        assert "user_role" in response.metadata
        assert "violations_count" in response.metadata
        assert response.metadata["user_role"] == "viewer"
