"""
Chatbot Pipeline Orchestrator

This module orchestrates the complete pipeline from natural language question
to formatted answer. It coordinates all services and handles errors gracefully.

Pipeline stages:
1. Get database schema
2. Generate SQL from question
3. Pre-validate table/column references
4. Run safety guards
5. Execute SQL query
6. Format answer

Usage:
    from services.chatbot_pipeline import ask
    
    result = ask("How many ISO tanks are in 'IN' status?")
    print(result["answer"])
    print(result["sql"])
"""

import time
from typing import Dict, Any
from services.schema import get_database_schema
from services.sql_generator import SQLGenerator, SQLGenerationError
from services.sql_validator import SQLValidator
from services.sql_executor import (
    get_executor,
    QueryTimeoutError,
    DatabaseConnectionError,
    SQLSyntaxError,
    PermissionDeniedError
)
from services.answer_formatter import AnswerFormatter, AnswerFormattingError
from config.logging_config import get_logger

logger = get_logger(__name__)


class PipelineError(Exception):
    """Base exception for pipeline errors."""
    pass


def ask(question: str) -> Dict[str, Any]:
    """
    Process a natural language question and return a formatted answer.
    
    This is the main entry point for the chatbot pipeline. It orchestrates
    all stages from SQL generation to answer formatting.
    
    Args:
        question: Natural language question from user
        
    Returns:
        Dictionary with:
        - answer: Natural language answer
        - sql: SQL query that was executed
        - rows_count: Number of rows returned
        - status_code: HTTP status code (200 for success, 4xx/5xx for errors)
        - error: Error message (only present if status_code != 200)
        
    Example:
        >>> result = ask("How many ISO tanks are in 'IN' status?")
        >>> print(result["answer"])
        "There are currently 47 ISO tanks with status 'IN'."
        >>> print(result["sql"])
        "SELECT COUNT(*) FROM iso_tank WHERE iso_tank_status = 'IN' LIMIT 100;"
    """
    start_time = time.time()
    
    logger.info(f"=== Pipeline started for question: {question} ===")
    
    try:
        # Stage 1: Get database schema
        stage_start = time.time()
        logger.info("Stage 1: Getting database schema")
        schema = get_database_schema()
        logger.info(f"Stage 1 completed in {time.time() - stage_start:.2f}s")
        
        # Stage 2: Generate SQL
        stage_start = time.time()
        logger.info("Stage 2: Generating SQL from question")
        generator = SQLGenerator()
        sql = generator.generate_sql(question, schema)
        logger.info(f"Stage 2 completed in {time.time() - stage_start:.2f}s")
        
        # Stage 3: Pre-validate table/column references
        stage_start = time.time()
        logger.info("Stage 3: Pre-validating SQL references")
        validator = SQLValidator()
        is_valid, validation_error = validator.validate_references(sql, schema)
        
        if not is_valid:
            logger.warning(f"Stage 3 failed: {validation_error}")
            return {
                "answer": validation_error,
                "sql": sql,
                "rows_count": 0,
                "status_code": 400,
                "error": validation_error
            }
        
        logger.info(f"Stage 3 completed in {time.time() - stage_start:.2f}s")
        
        # Stage 4: Run safety guards
        stage_start = time.time()
        logger.info("Stage 4: Checking SQL safety")
        is_safe, safety_error = validator.check_safety(sql)
        
        if not is_safe:
            logger.warning(f"Stage 4 failed: {safety_error}")
            return {
                "answer": safety_error,
                "sql": sql,
                "rows_count": 0,
                "status_code": 400,
                "error": safety_error
            }
        
        logger.info(f"Stage 4 completed in {time.time() - stage_start:.2f}s")
        
        # Stage 5: Execute SQL query
        stage_start = time.time()
        logger.info("Stage 5: Executing SQL query")
        executor = get_executor()
        results = executor.execute_query(sql)
        logger.info(f"Stage 5 completed in {time.time() - stage_start:.2f}s")
        
        # Stage 6: Format answer
        stage_start = time.time()
        logger.info("Stage 6: Formatting answer")
        formatter = AnswerFormatter()
        answer = formatter.format_answer(question, sql, results)
        logger.info(f"Stage 6 completed in {time.time() - stage_start:.2f}s")
        
        # Success!
        total_time = time.time() - start_time
        logger.info(f"=== Pipeline completed successfully in {total_time:.2f}s ===")
        
        return {
            "answer": answer,
            "sql": sql,
            "rows_count": results["row_count"],
            "status_code": 200
        }
        
    except SQLGenerationError as e:
        logger.error(f"SQL generation failed: {e}")
        return {
            "answer": "Failed to generate SQL query. Please try rephrasing your question.",
            "sql": "",
            "rows_count": 0,
            "status_code": 500,
            "error": str(e)
        }
        
    except QueryTimeoutError as e:
        logger.error(f"Query timeout: {e}")
        return {
            "answer": "Query took too long. Try simplifying your question.",
            "sql": sql if 'sql' in locals() else "",
            "rows_count": 0,
            "status_code": 504,
            "error": str(e)
        }
        
    except DatabaseConnectionError as e:
        logger.error(f"Database connection error: {e}")
        return {
            "answer": "Database unavailable. Try again shortly.",
            "sql": sql if 'sql' in locals() else "",
            "rows_count": 0,
            "status_code": 503,
            "error": str(e)
        }
        
    except SQLSyntaxError as e:
        logger.error(f"SQL syntax error: {e}")
        return {
            "answer": "Invalid SQL query generated. Try rephrasing your question.",
            "sql": sql if 'sql' in locals() else "",
            "rows_count": 0,
            "status_code": 400,
            "error": str(e)
        }
        
    except PermissionDeniedError as e:
        logger.error(f"Permission denied: {e}")
        return {
            "answer": "Access denied to that table or column.",
            "sql": sql if 'sql' in locals() else "",
            "rows_count": 0,
            "status_code": 403,
            "error": str(e)
        }
        
    except AnswerFormattingError as e:
        logger.error(f"Answer formatting failed: {e}")
        # Still return the SQL and results, just with a generic answer
        return {
            "answer": f"Query executed successfully and returned {results['row_count']} rows. See SQL for details.",
            "sql": sql if 'sql' in locals() else "",
            "rows_count": results["row_count"] if 'results' in locals() else 0,
            "status_code": 200,  # Query succeeded, just formatting failed
            "error": str(e)
        }
        
    except Exception as e:
        logger.error(f"Unexpected error in pipeline: {e}", exc_info=True)
        return {
            "answer": "An unexpected error occurred. Please try again.",
            "sql": sql if 'sql' in locals() else "",
            "rows_count": 0,
            "status_code": 500,
            "error": str(e)
        }
