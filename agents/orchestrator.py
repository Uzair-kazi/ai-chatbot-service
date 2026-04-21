"""
Orchestrator Agent with Simple Routing

This agent analyzes incoming queries and routes them to appropriate specialized agents.
In Phase 1, all queries are routed to the SQL Generation agent. The orchestrator provides
an extensible framework for Phase 2-3 when multiple agents will be coordinated.

Routing logic (Phase 1):
- All queries → SQL Generation agent
- If SQL Generation returns low confidence (<0.6), escalate to human
- Pass-through agent responses without transformation

Future phases will add:
- Query complexity analysis
- Multi-agent team formation
- Conflict resolution between agents
- Response synthesis from multiple agents
"""

import time
from typing import Optional
from agents.base import BaseAgent, AgentExecutionError, AgentValidationError
from agents.sql_generation import SQLGenerationAgent
from agents.models.agent_models import AgentRequest, AgentResponse
from agents.models.query_models import SQLGenerationRequest, SQLGenerationResponse
from config.logging_config import get_logger

logger = get_logger(__name__)


class OrchestratorAgent(BaseAgent):
    """
    Orchestrator agent that routes queries to specialized agents.
    
    Phase 1 implementation:
    - Simple routing: all queries → SQL Generation agent
    - Escalation: low confidence responses → human review
    - Pass-through: agent responses returned without transformation
    
    Future phases will add complexity analysis, multi-agent coordination,
    and conflict resolution.
    
    Attributes:
        name: Agent name
        logger: Logger instance
        sql_agent: SQL Generation agent instance
        confidence_threshold: Minimum confidence for automatic responses (0.6)
    """
    
    # Confidence threshold for escalation
    CONFIDENCE_THRESHOLD = 0.6
    
    def __init__(self):
        """Initialize the Orchestrator agent."""
        super().__init__(name="OrchestratorAgent")
        
        # Initialize specialized agents
        self.sql_agent = SQLGenerationAgent()
        
        self.logger.info("Orchestrator initialized with SQL Generation agent")
    
    def execute(self, request: AgentRequest) -> AgentResponse:
        """
        Execute orchestration: analyze query and route to appropriate agent(s).
        
        Phase 1 routing logic:
        1. Validate request
        2. Route to SQL Generation agent
        3. Check confidence score
        4. Escalate if confidence < threshold
        5. Return agent response
        
        Args:
            request: AgentRequest with question and schema
            
        Returns:
            AgentResponse with success status, data, error, and confidence
            
        Raises:
            AgentValidationError: If request validation fails
            AgentExecutionError: If orchestration fails
        """
        start_time = time.time()
        
        # Validate request
        self._validate_request(request)
        
        self.logger.info(f"Orchestrating request: {request.question}")
        
        try:
            # Phase 1: Simple routing - all queries go to SQL Generation agent
            agent_response = self._route_to_sql_generation(request)
            
            # Check if escalation is needed
            if agent_response.success and agent_response.confidence < self.CONFIDENCE_THRESHOLD:
                self.logger.warning(
                    f"Low confidence response ({agent_response.confidence:.2f}). "
                    f"Escalating to human review."
                )
                
                # Escalate to human
                escalation_response = self._escalate_to_human(
                    request,
                    agent_response,
                    reason=f"Low confidence ({agent_response.confidence:.2f})"
                )
                
                self._log_execution_time("Orchestration (escalated)", start_time)
                return escalation_response
            
            # Return agent response (pass-through in Phase 1)
            self._log_execution_time("Orchestration", start_time)
            
            self.logger.info(
                f"Orchestration completed successfully. "
                f"Success: {agent_response.success}, "
                f"Confidence: {agent_response.confidence:.2f}"
            )
            
            return agent_response
            
        except AgentValidationError as e:
            # Validation error from SQL agent
            self.logger.error(f"Agent validation error: {e}")
            self._log_execution_time("Orchestration (validation error)", start_time)
            
            return AgentResponse(
                success=False,
                error=f"Validation error: {str(e)}",
                confidence=0.0,
                metadata={
                    "execution_time": time.time() - start_time,
                    "error_type": "validation_error"
                }
            )
            
        except AgentExecutionError as e:
            # Execution error from SQL agent
            self.logger.error(f"Agent execution error: {e}")
            self._log_execution_time("Orchestration (execution error)", start_time)
            
            return AgentResponse(
                success=False,
                error=f"Execution error: {str(e)}",
                confidence=0.0,
                metadata={
                    "execution_time": time.time() - start_time,
                    "error_type": "execution_error"
                }
            )
            
        except Exception as e:
            # Unexpected error
            self.logger.error(f"Unexpected orchestration error: {e}", exc_info=True)
            self._log_execution_time("Orchestration (unexpected error)", start_time)
            
            return AgentResponse(
                success=False,
                error=f"Orchestration failed: {str(e)}",
                confidence=0.0,
                metadata={
                    "execution_time": time.time() - start_time,
                    "error_type": "unexpected_error"
                }
            )
    
    def _route_to_sql_generation(self, request: AgentRequest) -> AgentResponse:
        """
        Route request to SQL Generation agent.
        
        Args:
            request: AgentRequest with question and schema
            
        Returns:
            AgentResponse from SQL Generation agent
        """
        self.logger.info("Routing to SQL Generation agent")
        
        # Convert AgentRequest to SQLGenerationRequest
        sql_request = SQLGenerationRequest(
            question=request.question,
            db_schema=request.db_schema,
            context=request.context,
            max_retries=2,  # Default retry count
            temperature=0.1  # Low temperature for deterministic SQL
        )
        
        # Execute SQL Generation agent
        sql_response: SQLGenerationResponse = self.sql_agent.execute(sql_request)
        
        # Convert SQLGenerationResponse to AgentResponse
        # In Phase 1, we pass through the SQL-specific response
        # In future phases, we might transform or synthesize responses
        agent_response = AgentResponse(
            success=sql_response.success,
            data={
                "sql": sql_response.sql,
                "validation_issues": sql_response.validation_issues,
                "retry_count": sql_response.retry_count
            } if sql_response.success else None,
            error=sql_response.error,
            confidence=sql_response.confidence,
            metadata={
                **sql_response.metadata,
                "agent": "SQLGenerationAgent",
                "routing_strategy": "simple"  # Phase 1 strategy
            }
        )
        
        return agent_response
    
    def _escalate_to_human(
        self,
        request: AgentRequest,
        agent_response: AgentResponse,
        reason: str
    ) -> AgentResponse:
        """
        Escalate request to human review.
        
        This method creates an escalation response that indicates the query
        requires human intervention. In production, this would trigger a
        notification or queue the request for manual review.
        
        Args:
            request: Original AgentRequest
            agent_response: Agent response that triggered escalation
            reason: Reason for escalation
            
        Returns:
            AgentResponse indicating escalation
        """
        self.logger.info(f"Escalating to human: {reason}")
        
        # Build escalation message
        error_message = (
            f"This query requires human review. Reason: {reason}. "
            f"The system attempted to process your question but could not "
            f"generate a high-confidence response."
        )
        
        # Include agent's attempt in metadata for human reviewer
        escalation_data = {
            "escalation_reason": reason,
            "original_question": request.question,
            "agent_attempt": {
                "success": agent_response.success,
                "confidence": agent_response.confidence,
                "data": agent_response.data,
                "error": agent_response.error
            }
        }
        
        return AgentResponse(
            success=False,
            data=escalation_data,
            error=error_message,
            confidence=agent_response.confidence,
            metadata={
                **agent_response.metadata,
                "escalated": True,
                "escalation_reason": reason
            }
        )
    
    # Placeholder methods for future phases
    
    def _analyze_query_complexity(self, question: str) -> str:
        """
        Analyze query complexity to determine routing strategy.
        
        Phase 2-3 implementation will classify queries as:
        - Simple: Single table, basic filters
        - Complex: Multiple tables, aggregations, subqueries
        - Ambiguous: Requires query refinement
        
        Args:
            question: Natural language question
            
        Returns:
            Complexity level: "simple", "complex", or "ambiguous"
        """
        # Placeholder for Phase 2-3
        return "simple"
    
    def _form_agent_team(self, complexity: str, question: str) -> list:
        """
        Form team of agents based on query complexity.
        
        Phase 2-3 implementation will coordinate multiple agents:
        - Schema Intelligence: Prune schema, provide context
        - Query Refinement: Clarify ambiguous questions
        - SQL Generation: Generate SQL
        - Security & Governance: Apply policies
        
        Args:
            complexity: Query complexity level
            question: Natural language question
            
        Returns:
            List of agent instances to execute
        """
        # Placeholder for Phase 2-3
        return [self.sql_agent]
    
    def _resolve_conflicts(self, responses: list) -> AgentResponse:
        """
        Resolve conflicts between multiple agent responses.
        
        Phase 2-3 implementation will handle:
        - Voting: Multiple agents generate SQL, pick best
        - Synthesis: Combine insights from multiple agents
        - Validation: Cross-validate responses
        
        Args:
            responses: List of AgentResponse objects
            
        Returns:
            Synthesized AgentResponse
        """
        # Placeholder for Phase 2-3
        if responses:
            return responses[0]
        
        return AgentResponse(
            success=False,
            error="No agent responses to resolve",
            confidence=0.0
        )
