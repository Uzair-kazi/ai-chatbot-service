"""
Multi-Agent Pipeline

This module implements the multi-agent text-to-SQL pipeline using the Orchestrator
and SQL Generation agents. It provides an alternative to the single-LLM pipeline
with self-critique loops for improved accuracy.

Pipeline stages:
1. Get database schema
2. Route through Orchestrator → SQL Generation agent (with self-critique)
3. Execute SQL query
4. Format answer

Usage:
    from services.multi_agent_pipeline import ask
    
    result = ask("How many ISO tanks are in 'IN' status?")
    print(result["answer"])
    print(result["sql"])
"""

import time
from typing import Dict, Any
from services.schema import get_database_schema
from services.sql_executor import (
    get_executor,
    QueryTimeoutError,
    DatabaseConnectionError,
    SQLSyntaxError,
    PermissionDeniedError
)
from services.answer_formatter import AnswerFormatter, AnswerFormattingError
from agents.orchestrator import OrchestratorAgent
from agents.models.agent_models import AgentRequest, AgentResponse
from config.logging_config import get_logger

logger = get_logger(__name__)


class MultiAgentPipelineError(Exception):
    """Base exception for multi-agent pipeline errors."""
    pass


# Exception categories for retry logic
RETRYABLE_EXCEPTIONS = (DatabaseConnectionError, QueryTimeoutError)
FATAL_EXCEPTIONS = (SQLSyntaxError, PermissionDeniedError)


def ask(question: str, _retry_count: int = 0) -> Dict[str, Any]:
    """
    Process a natural language question using multi-agent pipeline.
    
    This is the main entry point for the multi-agent chatbot pipeline. It uses
    the Orchestrator and SQL Generation agents to generate SQL with self-critique
    loops, then executes and formats the results.
    
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
    
    logger.info(f"=== Multi-Agent Pipeline started for question: {question} ===")
    
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
                    "retry_count": agent_response.data.get("agent_attempt", {}).get("data", {}).get("retry_count", 0) if agent_response.data else 0
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
                    "retry_count": 0
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
                "retry_count": 0
            }
        
        logger.info(f"SQL generated with confidence {confidence:.2f} after {retry_count} retries")
        
        # Stage 3: Execute SQL query
        stage_start = time.time()
        logger.info("Stage 3: Executing SQL query")
        executor = get_executor()
        results = executor.execute_query(sql)
        logger.info(f"Stage 3 completed in {time.time() - stage_start:.2f}s")
        
        # Stage 4: Format answer
        stage_start = time.time()
        logger.info("Stage 4: Formatting answer")
        formatter = AnswerFormatter()
        answer = formatter.format_answer(question, sql, results)
        logger.info(f"Stage 4 completed in {time.time() - stage_start:.2f}s")
        
        # Success!
        total_time = time.time() - start_time
        logger.info(f"=== Multi-Agent Pipeline completed successfully in {total_time:.2f}s ===")
        
        return {
            "answer": answer,
            "sql": sql,
            "rows_count": results["row_count"],
            "status_code": 200,
            "confidence": confidence,
            "retry_count": retry_count
        }
        
    except RETRYABLE_EXCEPTIONS as e:
        # Transient failure - retry once
        exception_type = type(e).__name__
        logger.warning(f"Retryable exception ({exception_type}): {e}")
        
        if _retry_count < max_retries:
            logger.info(f"Retrying request (attempt {_retry_count + 1}/{max_retries})...")
            time.sleep(0.5 * (2 ** _retry_count))  # Exponential backoff: 0.5s, 1s
            return ask(question, _retry_count=_retry_count + 1)
        else:
            logger.error(f"Max retries ({max_retries}) exceeded for {exception_type}")
            
            if isinstance(e, QueryTimeoutError):
                return {
                    "answer": "Query took too long. Try simplifying your question.",
                    "sql": sql if 'sql' in locals() else "",
                    "rows_count": 0,
                    "status_code": 504,
                    "error": str(e),
                    "confidence": confidence if 'confidence' in locals() else 0.0,
                    "retry_count": retry_count if 'retry_count' in locals() else 0
                }
            else:  # DatabaseConnectionError
                return {
                    "answer": "Database unavailable. Try again shortly.",
                    "sql": sql if 'sql' in locals() else "",
                    "rows_count": 0,
                    "status_code": 503,
                    "error": str(e),
                    "confidence": confidence if 'confidence' in locals() else 0.0,
                    "retry_count": retry_count if 'retry_count' in locals() else 0
                }
        
    except FATAL_EXCEPTIONS as e:
        # Fatal error - do not retry
        exception_type = type(e).__name__
        logger.error(f"Fatal exception ({exception_type}): {e}")
        
        if isinstance(e, SQLSyntaxError):
            return {
                "answer": "Invalid SQL query generated. Try rephrasing your question.",
                "sql": sql if 'sql' in locals() else "",
                "rows_count": 0,
                "status_code": 400,
                "error": str(e),
                "confidence": confidence if 'confidence' in locals() else 0.0,
                "retry_count": retry_count if 'retry_count' in locals() else 0
            }
        elif isinstance(e, PermissionDeniedError):
            return {
                "answer": "Access denied to that table or column.",
                "sql": sql if 'sql' in locals() else "",
                "rows_count": 0,
                "status_code": 403,
                "error": str(e),
                "confidence": confidence if 'confidence' in locals() else 0.0,
                "retry_count": retry_count if 'retry_count' in locals() else 0
            }
        
    except AnswerFormattingError as e:
        logger.error(f"Answer formatting failed: {e}")
        # Still return the SQL and results, just with a generic answer
        return {
            "answer": f"Query executed successfully and returned {results['row_count']} rows. See SQL for details.",
            "sql": sql if 'sql' in locals() else "",
            "rows_count": results["row_count"] if 'results' in locals() else 0,
            "status_code": 200,  # Query succeeded, just formatting failed
            "error": str(e),
            "confidence": confidence if 'confidence' in locals() else 0.0,
            "retry_count": retry_count if 'retry_count' in locals() else 0
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
            "retry_count": retry_count if 'retry_count' in locals() else 0
        }
