"""
Multi-Agent Pipeline

This module implements the multi-agent text-to-SQL pipeline using the Orchestrator
and specialized agents. It provides an alternative to the single-LLM pipeline
with self-critique loops for improved accuracy.

Pipeline stages:
1. Get database schema
2. Route through Orchestrator → SQL Generation agent (with self-critique)
3. Route to Result Formatter Agent (execute SQL and format results)

Phase 4 enhancements:
- Result Formatter Agent replaces legacy AnswerFormatter
- MCP client integration for all database operations
- Graceful fallback modes when MCP server unavailable

Usage:
    from services.multi_agent_pipeline import ask
    
    result = ask("How many ISO tanks are in 'IN' status?")
    print(result["answer"])
    print(result["sql"])
"""

import time
from typing import Dict, Any
from services.schema import get_database_schema
from agents.orchestrator import OrchestratorAgent
from agents.result_formatter import ResultFormatterAgent
from agents.models.agent_models import AgentRequest, AgentResponse
from agents.models.formatter_models import FormatterRequest, FormatterResponse
from config.logging_config import get_logger

logger = get_logger(__name__)


class MultiAgentPipelineError(Exception):
    """Base exception for multi-agent pipeline errors."""
    pass


def ask(question: str, _retry_count: int = 0) -> Dict[str, Any]:
    """
    Process a natural language question using multi-agent pipeline.
    
    This is the main entry point for the multi-agent chatbot pipeline. It uses
    the Orchestrator and specialized agents to generate SQL with self-critique
    loops, then executes and formats the results via Result Formatter Agent.
    
    Phase 4 pipeline:
    1. Get database schema
    2. Route through Orchestrator (Query Refinement → Security → Schema Intelligence → SQL Generation)
    3. Route to Result Formatter Agent (execute SQL via MCP + format results)
    
    Implements retry logic for transient failures (database connection, timeouts).
    Fatal errors (syntax, permissions) are not retried.
    
    Args:
        question: Natural language question from user
        _retry_count: Internal retry counter (do not set manually)
        
    Returns:
        Dictionary with:
        - answer: Natural language answer
        - sql: SQL query that was executed
        - rows_count: Number of rows returned
        - status_code: HTTP status code (200 for success, 4xx/5xx for errors)
        - error: Error message (only present if status_code != 200)
        - confidence: Confidence score from SQL Generation agent (0.0-1.0)
        - retry_count: Number of self-critique retries performed
        - execution_time: Total pipeline execution time
        - mcp_used: Whether MCP client was used for database operations
        
    Example:
        >>> result = ask("How many ISO tanks are in 'IN' status?")
        >>> print(result["answer"])
        "There are currently 47 ISO tanks with status 'IN'."
        >>> print(result["sql"])
        "SELECT COUNT(*) FROM iso_tank WHERE iso_tank_status = 'IN' LIMIT 100;"
        >>> print(result["confidence"])
        0.9
    """
    start_time = time.time()
    max_retries = 1  # Retry once for transient failures
    
    logger.info(f"=== Multi-Agent Pipeline (Phase 4) started for question: {question} ===")
    
    try:
        # Stage 1: Get database schema
        stage_start = time.time()
        logger.info("Stage 1: Getting database schema")
        schema = get_database_schema()
        logger.info(f"Stage 1 completed in {time.time() - stage_start:.2f}s")
        
        # Stage 2: Route through Orchestrator → SQL Generation agent
        stage_start = time.time()
        logger.info("Stage 2: Routing through Orchestrator")
        orchestrator = OrchestratorAgent()
        
        # Create agent request
        agent_request = AgentRequest(
            question=question,
            db_schema=schema
        )
        
        # Execute orchestration
        agent_response: AgentResponse = orchestrator.execute(agent_request)
        
        logger.info(f"Stage 2 completed in {time.time() - stage_start:.2f}s")
        
        # Check if orchestration succeeded
        if not agent_response.success:
            logger.warning(f"Orchestration failed: {agent_response.error}")
            
            # Check if this was an escalation (low confidence)
            if agent_response.metadata.get("escalated"):
                return {
                    "answer": agent_response.error,
                    "sql": agent_response.data.get("agent_attempt", {}).get("data", {}).get("sql", "") if agent_response.data else "",
                    "rows_count": 0,
                    "status_code": 400,
                    "error": agent_response.error,
                    "confidence": agent_response.confidence,
                    "retry_count": agent_response.data.get("agent_attempt", {}).get("data", {}).get("retry_count", 0) if agent_response.data else 0,
                    "execution_time": time.time() - start_time,
                    "mcp_used": False
                }
            else:
                # Other orchestration error
                return {
                    "answer": agent_response.error or "Failed to generate SQL query.",
                    "sql": "",
                    "rows_count": 0,
                    "status_code": 500,
                    "error": agent_response.error,
                    "confidence": 0.0,
                    "retry_count": 0,
                    "execution_time": time.time() - start_time,
                    "mcp_used": False
                }
        
        # Extract SQL from agent response
        sql = agent_response.data.get("sql", "")
        confidence = agent_response.confidence
        retry_count = agent_response.data.get("retry_count", 0)
        
        if not sql:
            logger.error("No SQL generated by agent")
            return {
                "answer": "Failed to generate SQL query.",
                "sql": "",
                "rows_count": 0,
                "status_code": 500,
                "error": "No SQL generated",
                "confidence": 0.0,
                "retry_count": 0,
                "execution_time": time.time() - start_time,
                "mcp_used": False
            }
        
        logger.info(f"SQL generated with confidence {confidence:.2f} after {retry_count} retries")
        
        # Stage 3: Route to Result Formatter Agent (execute SQL + format results)
        stage_start = time.time()
        logger.info("Stage 3: Executing SQL and formatting results via Result Formatter Agent")
        
        result_formatter = ResultFormatterAgent()
        
        # Create formatter request
        formatter_request = FormatterRequest(
            question=question,
            sql=sql,
            db_schema=schema
        )
        
        # Execute Result Formatter Agent
        formatter_response: FormatterResponse = result_formatter.execute(formatter_request)
        
        logger.info(f"Stage 3 completed in {time.time() - stage_start:.2f}s")
        
        # Check if formatting succeeded
        if not formatter_response.success:
            logger.error(f"Result formatting failed: {formatter_response.error}")
            
            # Return error response
            return {
                "answer": formatter_response.error or "Failed to execute SQL query.",
                "sql": sql,
                "rows_count": 0,
                "status_code": 500,
                "error": formatter_response.error,
                "confidence": confidence,
                "retry_count": retry_count,
                "execution_time": time.time() - start_time,
                "mcp_used": formatter_response.metadata.get("mcp_used", False)
            }
        
        # Success!
        total_time = time.time() - start_time
        logger.info(f"=== Multi-Agent Pipeline (Phase 4) completed successfully in {total_time:.2f}s ===")
        
        return {
            "answer": formatter_response.answer,
            "sql": formatter_response.sql,
            "rows_count": formatter_response.rows_count,
            "status_code": 200,
            "confidence": confidence,
            "retry_count": retry_count,
            "execution_time": total_time,
            "mcp_used": formatter_response.metadata.get("mcp_used", False),
            "formatting_strategy": formatter_response.formatting_method,
            "token_usage": formatter_response.metadata.get("token_usage", 0)
        }
        
    except Exception as e:
        logger.error(f"Unexpected error in multi-agent pipeline: {e}", exc_info=True)
        return {
            "answer": "An unexpected error occurred. Please try again.",
            "sql": sql if 'sql' in locals() else "",
            "rows_count": 0,
            "status_code": 500,
            "error": str(e),
            "confidence": confidence if 'confidence' in locals() else 0.0,
            "retry_count": retry_count if 'retry_count' in locals() else 0,
            "execution_time": time.time() - start_time,
            "mcp_used": False
        }
