#!/usr/bin/env python3
"""
Demo script for Orchestrator Agent

This script demonstrates the Orchestrator Agent routing queries to the
SQL Generation agent and handling different scenarios.

Usage:
    python scripts/demo_orchestrator.py
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.orchestrator import OrchestratorAgent
from agents.models.agent_models import AgentRequest
from unittest.mock import Mock, patch


def demo_simple_query():
    """Demo: Simple query with high confidence."""
    print("\n" + "="*80)
    print("DEMO 1: Simple Query with High Confidence")
    print("="*80)
    
    # Mock AI provider
    with patch('agents.sql_generation.ai_client') as mock_ai:
        mock_response = Mock()
        mock_response.choices = [
            Mock(message=Mock(content="SELECT COUNT(*) FROM iso_tank WHERE iso_tank_status = 'IN' LIMIT 100;"))
        ]
        mock_response.usage = Mock(prompt_tokens=100, completion_tokens=20, total_tokens=120)
        mock_ai.chat.completions.create.return_value = mock_response
        
        # Create orchestrator
        orchestrator = OrchestratorAgent()
        
        # Create request
        request = AgentRequest(
            question="How many ISO tanks are in 'IN' status?",
            db_schema="Table: iso_tank\n  - id: uuid\n  - iso_tank_status: varchar"
        )
        
        # Execute
        print(f"\nQuestion: {request.question}")
        response = orchestrator.execute(request)
        
        # Display results
        print(f"\nSuccess: {response.success}")
        print(f"Confidence: {response.confidence}")
        print(f"SQL: {response.data['sql'] if response.data else 'N/A'}")
        print(f"Agent: {response.metadata.get('agent', 'N/A')}")
        print(f"Routing Strategy: {response.metadata.get('routing_strategy', 'N/A')}")


def demo_low_confidence_escalation():
    """Demo: Low confidence triggers escalation."""
    print("\n" + "="*80)
    print("DEMO 2: Low Confidence Escalation")
    print("="*80)
    
    # Mock SQL agent with low confidence
    with patch('agents.orchestrator.SQLGenerationAgent') as MockSQLAgent:
        from agents.models.query_models import SQLGenerationResponse
        
        mock_sql_agent = Mock()
        mock_sql_agent.execute.return_value = SQLGenerationResponse(
            success=True,
            sql="SELECT * FROM iso_tank LIMIT 100;",
            validation_issues=["Column 'idastank_count' does not exist"],
            retry_count=3,
            confidence=0.45,  # Below threshold
            metadata={"execution_time": 3.67}
        )
        
        MockSQLAgent.return_value = mock_sql_agent
        
        # Create orchestrator
        orchestrator = OrchestratorAgent()
        
        # Create request
        request = AgentRequest(
            question="Show me tanks with idastank_count > 5",
            db_schema="Table: iso_tank\n  - id: uuid\n  - tank_number: varchar"
        )
        
        # Execute
        print(f"\nQuestion: {request.question}")
        response = orchestrator.execute(request)
        
        # Display results
        print(f"\nSuccess: {response.success}")
        print(f"Confidence: {response.confidence}")
        print(f"Error: {response.error}")
        print(f"Escalated: {response.metadata.get('escalated', False)}")
        print(f"Escalation Reason: {response.metadata.get('escalation_reason', 'N/A')}")


def demo_complex_query():
    """Demo: Complex query with JOIN."""
    print("\n" + "="*80)
    print("DEMO 3: Complex Query with JOIN")
    print("="*80)
    
    # Mock AI provider
    with patch('agents.sql_generation.ai_client') as mock_ai:
        mock_response = Mock()
        mock_response.choices = [
            Mock(message=Mock(content="""
                SELECT it.tank_number, vi.created_at as in_time, vo.created_at as out_time
                FROM iso_tank it
                JOIN vehicle_in vi ON it.vehicle_in_id = vi.id
                JOIN vehicle_out vo ON it.vehicle_out_id = vo.id
                LIMIT 100;
            """))
        ]
        mock_response.usage = Mock(prompt_tokens=150, completion_tokens=40, total_tokens=190)
        mock_ai.chat.completions.create.return_value = mock_response
        
        # Create orchestrator
        orchestrator = OrchestratorAgent()
        
        # Create request
        request = AgentRequest(
            question="Show ISO tanks with their vehicle in and out times",
            db_schema=(
                "Table: iso_tank\n"
                "  - id: uuid\n"
                "  - tank_number: varchar\n"
                "  - vehicle_in_id: uuid\n"
                "  - vehicle_out_id: uuid\n"
                "Table: vehicle_in\n"
                "  - id: uuid\n"
                "  - created_at: timestamp\n"
                "Table: vehicle_out\n"
                "  - id: uuid\n"
                "  - created_at: timestamp"
            )
        )
        
        # Execute
        print(f"\nQuestion: {request.question}")
        response = orchestrator.execute(request)
        
        # Display results
        print(f"\nSuccess: {response.success}")
        print(f"Confidence: {response.confidence}")
        print(f"SQL: {response.data['sql'] if response.data else 'N/A'}")
        print(f"Retry Count: {response.data.get('retry_count', 0) if response.data else 0}")


def demo_error_handling():
    """Demo: Error handling when SQL generation fails."""
    print("\n" + "="*80)
    print("DEMO 4: Error Handling")
    print("="*80)
    
    # Mock SQL agent with failure
    with patch('agents.orchestrator.SQLGenerationAgent') as MockSQLAgent:
        from agents.models.query_models import SQLGenerationResponse
        
        mock_sql_agent = Mock()
        mock_sql_agent.execute.return_value = SQLGenerationResponse(
            success=False,
            sql=None,
            validation_issues=["Table 'nonexistent_table' does not exist"],
            retry_count=2,
            confidence=0.6,
            error="Failed to generate valid SQL after 3 attempts",
            metadata={"execution_time": 3.12}
        )
        
        MockSQLAgent.return_value = mock_sql_agent
        
        # Create orchestrator
        orchestrator = OrchestratorAgent()
        
        # Create request
        request = AgentRequest(
            question="Show me data from nonexistent_table",
            db_schema="Table: iso_tank\n  - id: uuid"
        )
        
        # Execute
        print(f"\nQuestion: {request.question}")
        response = orchestrator.execute(request)
        
        # Display results
        print(f"\nSuccess: {response.success}")
        print(f"Confidence: {response.confidence}")
        print(f"Error: {response.error}")


def main():
    """Run all demos."""
    print("\n" + "="*80)
    print("ORCHESTRATOR AGENT DEMONSTRATION")
    print("="*80)
    print("\nThis demo shows the Orchestrator Agent routing queries to the")
    print("SQL Generation agent and handling different scenarios.")
    
    try:
        demo_simple_query()
        demo_low_confidence_escalation()
        demo_complex_query()
        demo_error_handling()
        
        print("\n" + "="*80)
        print("DEMO COMPLETE")
        print("="*80)
        print("\nAll scenarios demonstrated successfully!")
        print("\nKey Features:")
        print("  ✓ Simple routing to SQL Generation agent")
        print("  ✓ Low confidence escalation (<0.6 threshold)")
        print("  ✓ Complex query handling with JOINs")
        print("  ✓ Error handling and clear error messages")
        print("  ✓ Metadata enrichment with routing information")
        
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
