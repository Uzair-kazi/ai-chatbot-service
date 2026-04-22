"""
Result Formatter Agent

This agent executes SQL queries via MCP client and formats results as natural language.
It uses a hybrid approach: template-based formatting for simple results (fast, no cost)
and LLM-based formatting for complex results (higher quality).

Key features:
- Execute SQL via MCP client with fallback to direct SQL executor
- Hybrid formatting strategy (template vs LLM)
- SQL transparency (always show SQL used)
- Graceful error handling (timeout, syntax, permission denied)
- Token usage tracking for LLM calls
"""

import time
from typing import Dict, List, Any, Optional
from agents.base import BaseAgent, AgentExecutionError, AgentValidationError
from agents.models.formatter_models import FormatterRequest, FormatterResponse
from agents.mcp_client import MCPClient, MCPConnectionError, MCPQueryError, MCPTimeoutError
from services.sql_executor import get_executor, QueryTimeoutError, DatabaseConnectionError, SQLSyntaxError, PermissionDeniedError
from config.ai_provider import ai_client, model_name, SDK_TYPE
from config.logging_config import get_logger

logger = get_logger(__name__)


class ResultFormatterAgent(BaseAgent):
    """
    Result Formatter agent with hybrid formatting strategy.
    
    Executes SQL queries via MCP client (with fallback to direct SQL executor)
    and formats results using template-based or LLM-based approaches.
    
    Formatting Strategy:
    - Template-based (no LLM): Single values, empty results, simple lists (<10 rows)
    - LLM-based: Complex aggregations, multi-table JOINs, large result sets (>10 rows)
    
    Attributes:
        name: Agent name
        logger: Logger instance
        mcp_client: MCP client for database operations
        sql_executor: Fallback SQL executor
        ai_client: AI provider client
        model_name: AI model name
        sdk_type: SDK type (openai_compatible or anthropic)
    """
    
    def __init__(self):
        """Initialize the Result Formatter agent."""
        super().__init__(name="ResultFormatterAgent")
        
        # Database clients
        self.mcp_client = MCPClient()
        self.sql_executor = get_executor()
        
        # AI provider configuration
        self.ai_client = ai_client
        self.model_name = model_name
        self.sdk_type = SDK_TYPE
        
        self.logger.info(
            f"Result Formatter agent initialized. "
            f"MCP available: {self.mcp_client.is_connected()}, "
            f"AI provider: {self.sdk_type}"
        )
    
    def execute(self, request: FormatterRequest) -> FormatterResponse:
        """
        Execute SQL query and format results as natural language.
        
        Workflow:
        1. Validate request
        2. Execute SQL via MCP client (fallback to direct executor)
        3. Determine formatting strategy (template vs LLM)
        4. Format results as natural language
        5. Return formatted response with metadata
        
        Args:
            request: FormatterRequest with question and SQL
            
        Returns:
            FormatterResponse with formatted answer and metadata
            
        Raises:
            AgentValidationError: If request validation fails
        """
        start_time = time.time()
        
        # Validate request
        self._validate_formatter_request(request)
        
        self.logger.info(f"Executing SQL and formatting results: {request.sql[:100]}...")
        
        try:
            # Step 1: Execute SQL query
            query_results, execution_time = self._execute_sql(request.sql)
            
            # Step 2: Determine formatting strategy
            formatting_method = self._determine_formatting_method(
                query_results,
                request.question,
                request.sql
            )
            
            # Step 3: Format results
            if formatting_method == "template":
                answer = self._format_template_based(
                    request.question,
                    request.sql,
                    query_results
                )
                confidence = 1.0  # Template-based is deterministic
            else:  # LLM-based
                answer = self._format_llm_based(
                    request.question,
                    request.sql,
                    query_results
                )
                confidence = 0.9  # LLM-based has slight uncertainty
            
            # Step 4: Build response
            total_time = time.time() - start_time
            
            self.logger.info(
                f"Results formatted successfully using {formatting_method} method "
                f"in {total_time:.2f}s (execution: {execution_time:.2f}s)"
            )
            
            return FormatterResponse(
                success=True,
                answer=answer,
                sql=request.sql,
                rows_count=query_results["row_count"],
                execution_time=execution_time,
                formatting_method=formatting_method,
                confidence=confidence,
                metadata={
                    "total_time": total_time,
                    "mcp_used": self.mcp_client.is_connected(),
                    "original_question": request.question
                }
            )
            
        except (QueryTimeoutError, MCPTimeoutError) as e:
            # Timeout errors
            self.logger.error(f"Query timeout: {e}")
            return self._create_error_response(
                request,
                "Query took too long to execute. Try simplifying your question.",
                time.time() - start_time,
                error_type="timeout"
            )
            
        except (SQLSyntaxError, MCPQueryError) as e:
            # SQL syntax errors
            self.logger.error(f"SQL syntax error: {e}")
            return self._create_error_response(
                request,
                "Invalid SQL query. Please check the query syntax.",
                time.time() - start_time,
                error_type="syntax"
            )
            
        except (PermissionDeniedError,) as e:
            # Permission errors
            self.logger.error(f"Permission denied: {e}")
            return self._create_error_response(
                request,
                "Access denied to the requested data.",
                time.time() - start_time,
                error_type="permission"
            )
            
        except (DatabaseConnectionError, MCPConnectionError) as e:
            # Connection errors
            self.logger.error(f"Database connection error: {e}")
            return self._create_error_response(
                request,
                "Database temporarily unavailable. Please try again.",
                time.time() - start_time,
                error_type="connection"
            )
            
        except Exception as e:
            # Unexpected errors
            self.logger.error(f"Unexpected error in result formatting: {e}", exc_info=True)
            return self._create_error_response(
                request,
                "An unexpected error occurred while processing your query.",
                time.time() - start_time,
                error_type="unexpected"
            )
    
    def _validate_formatter_request(self, request: FormatterRequest) -> None:
        """
        Validate the formatter request.
        
        Args:
            request: FormatterRequest to validate
            
        Raises:
            AgentValidationError: If validation fails
        """
        if not request.question or not request.question.strip():
            raise AgentValidationError("Question cannot be empty")
        
        if not request.sql or not request.sql.strip():
            raise AgentValidationError("SQL cannot be empty")
        
        # Basic SQL safety check
        sql_upper = request.sql.upper().strip()
        if not sql_upper.startswith('SELECT'):
            raise AgentValidationError("Only SELECT queries are allowed")
    
    def _execute_sql(self, sql: str) -> tuple[Dict[str, Any], float]:
        """
        Execute SQL query via MCP client with fallback to direct executor.
        
        Args:
            sql: SQL query to execute
            
        Returns:
            Tuple of (query_results, execution_time)
            
        Raises:
            Various database and MCP exceptions
        """
        start_time = time.time()
        
        # Try MCP client first
        if self.mcp_client.is_connected():
            try:
                self.logger.info("Executing SQL via MCP client")
                mcp_result = self.mcp_client.execute_query(sql)
                
                execution_time = time.time() - start_time
                
                # Convert MCP result to expected format
                query_results = {
                    "columns": mcp_result.columns,
                    "rows": mcp_result.rows,
                    "row_count": mcp_result.row_count
                }
                
                self.logger.info(f"SQL executed via MCP: {mcp_result.row_count} rows")
                return query_results, execution_time
                
            except (MCPTimeoutError, MCPQueryError) as e:
                # Don't fall back for timeout/query errors - re-raise them
                self.logger.error(f"MCP execution error: {e}")
                raise
                
            except MCPConnectionError as e:
                self.logger.warning(f"MCP connection failed: {e}. Falling back to direct executor.")
            
            except Exception as e:
                self.logger.warning(f"MCP execution failed: {e}. Falling back to direct executor.")
        
        # Fallback to direct SQL executor
        self.logger.info("Executing SQL via direct executor (fallback)")
        query_results = self.sql_executor.execute_query(sql)
        execution_time = time.time() - start_time
        
        self.logger.info(f"SQL executed via direct executor: {query_results['row_count']} rows")
        return query_results, execution_time
    
    def _determine_formatting_method(
        self,
        query_results: Dict[str, Any],
        question: str,
        sql: str
    ) -> str:
        """
        Determine whether to use template-based or LLM-based formatting.
        
        Template-based (fast, no cost):
        - Single value results (COUNT, SUM, AVG)
        - Empty result sets
        - Simple lists (≤10 rows, ≤3 columns)
        
        LLM-based (higher quality):
        - Large result sets (>10 rows)
        - Complex aggregations (GROUP BY, multiple columns)
        - Multi-table JOINs
        
        Args:
            query_results: Query execution results
            question: Original user question
            sql: SQL query
            
        Returns:
            "template" or "llm"
        """
        row_count = query_results["row_count"]
        columns = query_results["columns"]
        sql_upper = sql.upper()
        
        # Empty results - always template
        if row_count == 0:
            return "template"
        
        # Single value results (aggregations) - template
        if row_count == 1 and len(columns) == 1:
            # Check if it's a simple aggregation
            if any(func in sql_upper for func in ["COUNT(", "SUM(", "AVG(", "MIN(", "MAX("]):
                return "template"
        
        # Simple lists - template
        if row_count <= 10 and len(columns) <= 3:
            # No GROUP BY or complex JOINs
            if "GROUP BY" not in sql_upper and "JOIN" not in sql_upper:
                return "template"
        
        # Everything else - LLM
        return "llm"
    
    def _format_template_based(
        self,
        question: str,
        sql: str,
        query_results: Dict[str, Any]
    ) -> str:
        """
        Format results using template-based approach (no LLM).
        
        Args:
            question: Original user question
            sql: SQL query
            query_results: Query execution results
            
        Returns:
            Formatted natural language answer
        """
        row_count = query_results["row_count"]
        rows = query_results["rows"]
        columns = query_results["columns"]
        
        # Empty results
        if row_count == 0:
            return "No results found for your query."
        
        # Single value (aggregation)
        if row_count == 1 and len(columns) == 1:
            value = rows[0][columns[0]]
            
            # Format numbers with commas
            if isinstance(value, (int, float)) and value >= 1000:
                formatted_value = f"{value:,}"
            else:
                formatted_value = str(value)
            
            return f"The answer is {formatted_value}."
        
        # Single row, multiple columns
        if row_count == 1:
            row = rows[0]
            parts = []
            for col in columns:
                value = row[col]
                if value is not None:
                    parts.append(f"{col}: {value}")
            
            if len(parts) <= 3:
                return f"Result: {', '.join(parts)}."
            else:
                return f"Found 1 record with {len(columns)} fields."
        
        # Multiple rows, simple list
        if row_count <= 10 and len(columns) <= 3:
            if len(columns) == 1:
                # Single column list
                col_name = columns[0]
                values = [str(row[col_name]) for row in rows]
                
                if row_count <= 5:
                    return f"Results: {', '.join(values)}."
                else:
                    return f"Found {row_count} results: {', '.join(values[:3])}, and {row_count - 3} more."
            else:
                # Multi-column list (keep simple)
                return f"Found {row_count} records with {len(columns)} fields each."
        
        # Fallback for other cases
        return f"Query returned {row_count} rows with {len(columns)} columns."
    
    def _format_llm_based(
        self,
        question: str,
        sql: str,
        query_results: Dict[str, Any]
    ) -> str:
        """
        Format results using LLM-based approach.
        
        Args:
            question: Original user question
            sql: SQL query
            query_results: Query execution results
            
        Returns:
            Formatted natural language answer
        """
        # Build prompt for LLM
        prompt = self._build_llm_prompt(question, sql, query_results)
        
        # Call AI provider
        try:
            answer = self._call_ai_provider(prompt)
            
            # Log token usage (already logged in _call_ai_provider)
            self.logger.info("LLM-based formatting completed successfully")
            
            return answer
            
        except Exception as e:
            self.logger.error(f"LLM formatting failed: {e}. Using template fallback.")
            
            # Fallback to template-based formatting
            return self._format_template_based(question, sql, query_results)
    
    def _build_llm_prompt(
        self,
        question: str,
        sql: str,
        query_results: Dict[str, Any]
    ) -> str:
        """
        Build prompt for LLM-based formatting.
        
        Args:
            question: Original user question
            sql: SQL query
            query_results: Query execution results
            
        Returns:
            Formatted prompt string
        """
        rows = query_results["rows"]
        columns = query_results["columns"]
        row_count = query_results["row_count"]
        
        # Show first 10 rows for context
        rows_to_show = rows[:10]
        
        # Format rows as readable text
        rows_text = self._format_rows_for_prompt(rows_to_show, columns)
        
        # Build truncation message
        truncation_msg = ""
        if row_count > 10:
            truncation_msg = f"\n(Showing first 10 of {row_count} total rows)"
        
        prompt = f"""You are a helpful assistant that summarizes database query results.

ORIGINAL QUESTION:
{question}

SQL QUERY USED:
{sql}

QUERY RESULTS ({min(row_count, 10)} of {row_count} rows):
{rows_text}{truncation_msg}

Provide a concise, natural language answer that:
- Directly answers the user's question
- References actual numbers from the results
- Mentions if results were truncated (showing X of Y)
- Uses clear, professional language
- Formats large numbers with commas (e.g., "1,234 tanks" not "1234 tanks")
- For aggregations, explain what the numbers mean
- For lists, summarize the key findings
- Keep the answer under 200 words

ANSWER:"""
        
        return prompt
    
    def _format_rows_for_prompt(
        self,
        rows: List[Dict[str, Any]],
        columns: List[str]
    ) -> str:
        """
        Format rows as readable text for LLM prompt.
        
        Args:
            rows: List of row dictionaries
            columns: List of column names
            
        Returns:
            Formatted text representation
        """
        if not rows:
            return "(No rows)"
        
        # For single row, format as key-value pairs
        if len(rows) == 1:
            row = rows[0]
            lines = []
            for col in columns:
                value = row.get(col, "NULL")
                lines.append(f"  {col}: {value}")
            return "\n".join(lines)
        
        # For multiple rows, format as simple table
        lines = []
        
        # Header
        header = " | ".join(columns)
        lines.append(header)
        lines.append("-" * len(header))
        
        # Rows
        for row in rows:
            values = [str(row.get(col, "NULL")) for col in columns]
            lines.append(" | ".join(values))
        
        return "\n".join(lines)
    
    def _call_ai_provider(self, prompt: str) -> str:
        """
        Call AI provider to format the answer.
        
        Args:
            prompt: Formatted prompt for LLM
            
        Returns:
            Generated natural language answer
        """
        if self.sdk_type == "openai_compatible":
            # OpenAI-compatible API
            response = self.ai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # Slightly higher for natural language
                max_tokens=300
            )
            
            answer = response.choices[0].message.content.strip()
            
            # Log token usage
            if hasattr(response, 'usage'):
                self.logger.info(
                    f"LLM token usage - prompt: {response.usage.prompt_tokens}, "
                    f"completion: {response.usage.completion_tokens}, "
                    f"total: {response.usage.total_tokens}"
                )
            
            return answer
            
        elif self.sdk_type == "anthropic":
            # Anthropic API
            response = self.ai_client.messages.create(
                model=self.model_name,
                max_tokens=300,
                temperature=0.3,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            answer = response.content[0].text.strip()
            
            # Log token usage
            if hasattr(response, 'usage'):
                self.logger.info(
                    f"LLM token usage - input: {response.usage.input_tokens}, "
                    f"output: {response.usage.output_tokens}"
                )
            
            return answer
        
        else:
            raise AgentExecutionError(f"Unsupported SDK type: {self.sdk_type}")
    
    def _create_error_response(
        self,
        request: FormatterRequest,
        error_message: str,
        execution_time: float,
        error_type: str
    ) -> FormatterResponse:
        """
        Create error response for failed formatting.
        
        Args:
            request: Original request
            error_message: User-friendly error message
            execution_time: Time spent before error
            error_type: Type of error for metadata
            
        Returns:
            FormatterResponse with error details
        """
        return FormatterResponse(
            success=False,
            answer=error_message,
            sql=request.sql,
            rows_count=0,
            execution_time=execution_time,
            formatting_method="error",
            error=error_message,
            confidence=0.0,
            metadata={
                "error_type": error_type,
                "original_question": request.question,
                "mcp_used": self.mcp_client.is_connected()
            }
        )