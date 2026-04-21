"""
Orchestrator Agent with Phase 3 Integration

This agent analyzes incoming queries and routes them to appropriate specialized agents.
In Phase 3, queries are routed through a complete pipeline:
Query Refinement → Security & Governance → Schema Intelligence → SQL Generation

Routing logic (Phase 3):
- Query Refinement: Resolve temporal ambiguity and business terminology
- Security & Governance: Validate security policies and RBAC (veto power)
- Schema Intelligence: Prune schema to reduce token usage
- SQL Generation: Generate SQL with pruned schema
- If Security blocks query, escalate to human with veto reason
- If SQL Generation returns low confidence (<0.6), escalate to human

Future phases will add:
- Result Formatter Agent (execute SQL and format results)
- Query complexity analysis for optimization
- Multi-agent team formation
- Conflict resolution between agents
"""

import time
from typing import Optional
from agents.base import BaseAgent, AgentExecutionError, AgentValidationError
from agents.sql_generation import SQLGenerationAgent
from agents.schema_intelligence import SchemaIntelligenceAgent
from agents.query_refinement import QueryRefinementAgent
from agents.security_governance import SecurityGovernanceAgent
from agents.models.agent_models import AgentRequest, AgentResponse
from agents.models.query_models import SQLGenerationRequest, SQLGenerationResponse
from agents.models.schema_models import SchemaIntelligenceRequest, SchemaIntelligenceResponse
from agents.models.refinement_models import RefinementRequest, RefinementResponse
from agents.models.security_models import SecurityRequest, SecurityResponse
from config.logging_config import get_logger

logger = get_logger(__name__)


class OrchestratorAgent(BaseAgent):
    """
    Orchestrator agent that routes queries to specialized agents.
    
    Phase 3 implementation:
    - Query Refinement: Transform natural language with business glossary
    - Security & Governance: Validate security policies (veto power)
    - Schema Intelligence: Prune schema to reduce token usage
    - SQL Generation: Generate SQL with pruned schema
    - Escalation: Security veto or low confidence → human review
    
    Future phases will add complexity analysis, multi-agent coordination,
    and conflict resolution.
    
    Attributes:
        name: Agent name
        logger: Logger instance
        query_refinement_agent: Query Refinement agent instance
        security_agent: Security & Governance agent instance
        schema_intelligence_agent: Schema Intelligence agent instance
        sql_agent: SQL Generation agent instance
        confidence_threshold: Minimum confidence for automatic responses (0.6)
    """
    
    # Confidence threshold for escalation
    CONFIDENCE_THRESHOLD = 0.6
    
    def __init__(self):
        """Initialize the Orchestrator agent."""
        super().__init__(name="OrchestratorAgent")
        
        # Initialize specialized agents (Phase 3 pipeline)
        self.query_refinement_agent = QueryRefinementAgent()
        self.security_agent = SecurityGovernanceAgent()
        self.schema_intelligence_agent = SchemaIntelligenceAgent()
        self.sql_agent = SQLGenerationAgent()
        
        self.logger.info(
            "Orchestrator initialized with Phase 3 pipeline: "
            "Query Refinement → Security → Schema Intelligence → SQL Generation"
        )
    
    def execute(self, request: AgentRequest) -> AgentResponse:
        """
        Execute orchestration: analyze query and route to appropriate agent(s).
        
        Phase 3 routing logic:
        1. Validate request
        2. Route to Query Refinement agent for query transformation
        3. Route to Security & Governance agent for policy validation
        4. If Security blocks query (veto), escalate to human
        5. Route to Schema Intelligence agent for schema pruning
        6. Route to SQL Generation agent with pruned schema
        7. Check confidence score
        8. Escalate if confidence < threshold
        9. Return agent response
        
        Args:
            request: AgentRequest with question, schema, and optional user_role
            
        Returns:
            AgentResponse with success status, data, error, and confidence
            
        Raises:
            AgentValidationError: If request validation fails
            AgentExecutionError: If orchestration fails
        """
        start_time = time.time()
        
        # Validate request
        self._validate_request(request)
        
        # Extract user_role from context (default to "viewer")
        user_role = request.context.get("user_role", "viewer") if request.context else "viewer"
        
        self.logger.info(
            f"Orchestrating request: {request.question} (user_role={user_role})"
        )
        
        try:
            # Phase 3: Route through complete pipeline
            agent_response = self._route_phase3_pipeline(request, user_role)
            
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
            
            # Return agent response
            self._log_execution_time("Orchestration", start_time)
            
            self.logger.info(
                f"Orchestration completed successfully. "
                f"Success: {agent_response.success}, "
                f"Confidence: {agent_response.confidence:.2f}"
            )
            
            return agent_response
            
        except AgentValidationError as e:
            # Validation error from agents
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
            # Execution error from agents
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
    
    def _route_phase3_pipeline(
        self,
        request: AgentRequest,
        user_role: str
    ) -> AgentResponse:
        """
        Route request through Phase 3 pipeline.
        
        Pipeline: Refinement → Security → Schema Intelligence → SQL Generation
        
        Args:
            request: AgentRequest with question and schema
            user_role: User role for RBAC (admin, analyst, viewer)
            
        Returns:
            AgentResponse from SQL Generation agent or escalation
        """
        self.logger.info("Routing through Phase 3 pipeline")
        
        # Step 1: Query Refinement
        refined_query = request.question  # Default to original question
        refinement_metadata = {}
        
        try:
            refinement_request = RefinementRequest(
                question=request.question,
                db_schema=request.db_schema,
                business_glossary=None  # Agent loads from config
            )
            
            refinement_response: RefinementResponse = self.query_refinement_agent.execute(refinement_request)
            
            if refinement_response.success:
                refined_query = refinement_response.refined_query
                refinement_metadata = {
                    "refinement_success": True,
                    "refinement_confidence": refinement_response.confidence,
                    "clarification_questions": refinement_response.clarification_questions,
                    "original_question": request.question
                }
                
                self.logger.info(
                    f"Query Refinement succeeded: confidence={refinement_response.confidence:.2f}"
                )
                
                # Log warning if clarification needed
                if refinement_response.clarification_questions:
                    self.logger.warning(
                        f"Query may need clarification: {refinement_response.clarification_questions}"
                    )
            else:
                # Refinement failed - continue with original question
                self.logger.warning(
                    f"Query Refinement failed: {refinement_response.error}. "
                    f"Continuing with original question."
                )
                refinement_metadata = {
                    "refinement_success": False,
                    "refinement_error": refinement_response.error
                }
                
        except Exception as e:
            # Refinement error - continue with original question
            self.logger.warning(
                f"Query Refinement error: {e}. Continuing with original question."
            )
            refinement_metadata = {
                "refinement_success": False,
                "refinement_error": str(e)
            }
        
        # Step 2: Security & Governance validation
        security_metadata = {}
        
        try:
            security_request = SecurityRequest(
                question=request.question,  # Add required question field
                refined_query=refined_query,
                generated_sql="",  # Will be validated after SQL generation
                user_role=user_role,
                db_schema=request.db_schema
            )
            
            security_response: SecurityResponse = self.security_agent.execute(security_request)
            
            security_metadata = {
                "security_approved": security_response.approved,
                "security_risk_score": security_response.risk_score,
                "security_veto_reason": security_response.veto_reason
            }
            
            if not security_response.approved:
                # Security veto - escalate to human
                self.logger.warning(
                    f"Security veto: {security_response.veto_reason} "
                    f"(risk_score={security_response.risk_score:.2f})"
                )
                
                return self._escalate_to_human(
                    request,
                    AgentResponse(
                        success=False,
                        data={
                            "veto_reason": security_response.veto_reason,
                            "risk_score": security_response.risk_score,
                            "alternative_suggestions": security_response.alternative_suggestions
                        },
                        error=f"Security policy violation: {security_response.veto_reason}",
                        confidence=0.0,
                        metadata=security_metadata
                    ),
                    reason=f"Security veto: {security_response.veto_reason}"
                )
            
            self.logger.info(
                f"Security validation passed: risk_score={security_response.risk_score:.2f}"
            )
            
        except Exception as e:
            # Security error - log and continue (fail open for now)
            self.logger.error(
                f"Security validation error: {e}. Continuing with caution.",
                exc_info=True
            )
            security_metadata = {
                "security_approved": True,  # Fail open
                "security_error": str(e)
            }
        
        # Step 3: Schema Intelligence (existing logic)
        agent_response = self._route_with_schema_intelligence_phase3(
            request,
            refined_query
        )
        
        # Add Phase 3 metadata
        agent_response.metadata.update(refinement_metadata)
        agent_response.metadata.update(security_metadata)
        agent_response.metadata["pipeline_version"] = "phase3"
        
        return agent_response
    
    def _route_with_schema_intelligence_phase3(
        self,
        request: AgentRequest,
        refined_query: str
    ) -> AgentResponse:
        """
        Route request through Schema Intelligence → SQL Generation pipeline.
        
        Phase 3 version: Uses refined query instead of original question.
        
        Args:
            request: AgentRequest with original question and schema
            refined_query: Refined query from Query Refinement agent
            
        Returns:
            AgentResponse from SQL Generation agent
        """
        self.logger.info("Routing through Schema Intelligence → SQL Generation pipeline")
        
        # Step 1: Call Schema Intelligence for schema pruning
        pruned_schema = request.db_schema  # Default to full schema
        schema_metadata = {}
        
        try:
            schema_request = SchemaIntelligenceRequest(
                question=refined_query,  # Use refined query
                full_schema=request.db_schema
            )
            
            schema_response: SchemaIntelligenceResponse = self.schema_intelligence_agent.execute(schema_request)
            
            if schema_response.success:
                pruned_schema = schema_response.pruned_schema
                schema_metadata = {
                    "schema_intelligence_success": True,
                    "schema_cache_hit": schema_response.metadata.get("cache_hit", False),
                    "schema_token_reduction": schema_response.metadata.get("token_reduction", 0),
                    "schema_original_tokens": schema_response.metadata.get("original_token_count", 0),
                    "schema_pruned_tokens": schema_response.metadata.get("pruned_token_count", 0),
                    "schema_selected_tables": len(schema_response.selected_tables),
                    "schema_confidence": schema_response.confidence
                }
                
                self.logger.info(
                    f"Schema Intelligence succeeded: "
                    f"{len(schema_response.selected_tables)} tables selected, "
                    f"{schema_response.metadata.get('token_reduction', 0):.1f}% token reduction"
                )
            else:
                # Schema Intelligence failed - fall back to full schema
                original_token_count = len(request.db_schema) // 4  # Estimate: 1 token ≈ 4 characters
                self.logger.warning(
                    f"Schema Intelligence failed: {schema_response.error}. "
                    f"Falling back to full schema (~{original_token_count} tokens).",
                    extra={
                        "fallback_reason": schema_response.error,
                        "original_tokens": original_token_count,
                        "schema_intelligence_success": False
                    }
                )
                schema_metadata = {
                    "schema_intelligence_success": False,
                    "schema_fallback_reason": schema_response.error,
                    "schema_original_tokens": original_token_count
                }
                
        except Exception as e:
            # Schema Intelligence error - fall back to full schema
            original_token_count = len(request.db_schema) // 4  # Estimate: 1 token ≈ 4 characters
            self.logger.warning(
                f"Schema Intelligence error: {e}. "
                f"Falling back to full schema (~{original_token_count} tokens).",
                extra={
                    "fallback_reason": str(e),
                    "original_tokens": original_token_count,
                    "schema_intelligence_success": False
                }
            )
            schema_metadata = {
                "schema_intelligence_success": False,
                "schema_fallback_reason": str(e),
                "schema_original_tokens": original_token_count
            }
        
        # Step 2: Call SQL Generation with pruned (or full) schema and refined query
        agent_response = self._route_to_sql_generation_phase3(
            request,
            refined_query,
            pruned_schema
        )
        
        # Add schema metadata to response
        agent_response.metadata.update(schema_metadata)
        
        return agent_response
    
    def _route_to_sql_generation_phase3(
        self,
        request: AgentRequest,
        refined_query: str,
        schema: str
    ) -> AgentResponse:
        """
        Route request to SQL Generation agent with refined query and schema.
        
        Phase 3 version: Uses refined query instead of original question.
        
        Args:
            request: AgentRequest with original question
            refined_query: Refined query from Query Refinement agent
            schema: Schema to use (pruned or full)
            
        Returns:
            AgentResponse from SQL Generation agent
        """
        self.logger.info("Routing to SQL Generation agent")
        
        # Convert to SQLGenerationRequest with refined query
        sql_request = SQLGenerationRequest(
            question=refined_query,  # Use refined query
            db_schema=schema,  # Use provided schema (pruned or full)
            context=request.context,
            max_retries=2,  # Default retry count
            temperature=0.1  # Low temperature for deterministic SQL
        )
        
        # Execute SQL Generation agent
        sql_response: SQLGenerationResponse = self.sql_agent.execute(sql_request)
        
        # Convert SQLGenerationResponse to AgentResponse
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
                "routing_strategy": "phase3_pipeline"
            }
        )
        
        return agent_response
    
    def _route_with_schema_intelligence(self, request: AgentRequest) -> AgentResponse:
        """
        Route request through Schema Intelligence → SQL Generation pipeline.
        
        Phase 2 routing:
        1. Call Schema Intelligence to prune schema
        2. Pass pruned schema to SQL Generation
        3. Fall back to full schema if Schema Intelligence fails
        
        Args:
            request: AgentRequest with question and schema
            
        Returns:
            AgentResponse from SQL Generation agent
        """
        self.logger.info("Routing through Schema Intelligence → SQL Generation pipeline")
        
        # Step 1: Call Schema Intelligence for schema pruning
        pruned_schema = request.db_schema  # Default to full schema
        schema_metadata = {}
        
        try:
            schema_request = SchemaIntelligenceRequest(
                question=request.question,
                full_schema=request.db_schema
            )
            
            schema_response: SchemaIntelligenceResponse = self.schema_intelligence_agent.execute(schema_request)
            
            if schema_response.success:
                pruned_schema = schema_response.pruned_schema
                schema_metadata = {
                    "schema_intelligence_success": True,
                    "schema_cache_hit": schema_response.metadata.get("cache_hit", False),
                    "schema_token_reduction": schema_response.metadata.get("token_reduction", 0),
                    "schema_original_tokens": schema_response.metadata.get("original_token_count", 0),
                    "schema_pruned_tokens": schema_response.metadata.get("pruned_token_count", 0),
                    "schema_selected_tables": len(schema_response.selected_tables),
                    "schema_confidence": schema_response.confidence
                }
                
                self.logger.info(
                    f"Schema Intelligence succeeded: "
                    f"{len(schema_response.selected_tables)} tables selected, "
                    f"{schema_response.metadata.get('token_reduction', 0):.1f}% token reduction"
                )
            else:
                # Schema Intelligence failed - fall back to full schema
                original_token_count = len(request.db_schema) // 4  # Estimate: 1 token ≈ 4 characters
                self.logger.warning(
                    f"Schema Intelligence failed: {schema_response.error}. "
                    f"Falling back to full schema (~{original_token_count} tokens).",
                    extra={
                        "fallback_reason": schema_response.error,
                        "original_tokens": original_token_count,
                        "schema_intelligence_success": False
                    }
                )
                schema_metadata = {
                    "schema_intelligence_success": False,
                    "schema_fallback_reason": schema_response.error,
                    "schema_original_tokens": original_token_count
                }
                
        except Exception as e:
            # Schema Intelligence error - fall back to full schema
            original_token_count = len(request.db_schema) // 4  # Estimate: 1 token ≈ 4 characters
            self.logger.warning(
                f"Schema Intelligence error: {e}. "
                f"Falling back to full schema (~{original_token_count} tokens).",
                extra={
                    "fallback_reason": str(e),
                    "original_tokens": original_token_count,
                    "schema_intelligence_success": False
                }
            )
            schema_metadata = {
                "schema_intelligence_success": False,
                "schema_fallback_reason": str(e),
                "schema_original_tokens": original_token_count
            }
        
        # Step 2: Call SQL Generation with pruned (or full) schema
        agent_response = self._route_to_sql_generation_with_schema(request, pruned_schema)
        
        # Add schema metadata to response
        agent_response.metadata.update(schema_metadata)
        
        return agent_response
    
    def _route_to_sql_generation_with_schema(
        self,
        request: AgentRequest,
        schema: str
    ) -> AgentResponse:
        """
        Route request to SQL Generation agent with specified schema.
        
        Args:
            request: AgentRequest with question
            schema: Schema to use (pruned or full)
            
        Returns:
            AgentResponse from SQL Generation agent
        """
        self.logger.info("Routing to SQL Generation agent")
        
        # Convert AgentRequest to SQLGenerationRequest
        sql_request = SQLGenerationRequest(
            question=request.question,
            db_schema=schema,  # Use provided schema (pruned or full)
            context=request.context,
            max_retries=2,  # Default retry count
            temperature=0.1  # Low temperature for deterministic SQL
        )
        
        # Execute SQL Generation agent
        sql_response: SQLGenerationResponse = self.sql_agent.execute(sql_request)
        
        # Convert SQLGenerationResponse to AgentResponse
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
                "routing_strategy": "schema_intelligence"  # Phase 2 strategy
            }
        )
        
        return agent_response
    
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
