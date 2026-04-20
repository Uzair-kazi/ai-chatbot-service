"""
SQL Generator Service

This module generates SQL queries from natural language questions using AI
with few-shot prompting. It includes example question-SQL pairs to teach
the AI about the database schema and improve accuracy.
"""

import re
from config.ai_provider import ai_client, model_name, SDK_TYPE
from config.logging_config import get_logger

logger = get_logger(__name__)


class SQLGenerationError(Exception):
    """Raised when SQL generation fails."""
    pass


class SQLGenerator:
    """Generates SQL queries from natural language using AI with few-shot examples."""
    
    # Few-shot examples covering common patterns
    FEW_SHOT_EXAMPLES = """
Example 1:
Question: "How many ISO tanks are currently in 'IN' status?"
SQL: SELECT COUNT(*) FROM iso_tank WHERE iso_tank_status = 'IN';

Example 2:
Question: "Which ISO tanks haven't been surveyed yet?"
SQL: SELECT tank_number, iso_tank_status FROM iso_tank WHERE survey_form_id IS NULL ORDER BY created_at DESC;

Example 3:
Question: "Show me all ISO tanks created this month"
SQL: SELECT tank_number, iso_tank_status, created_at FROM iso_tank WHERE created_at >= DATE_TRUNC('month', CURRENT_DATE) ORDER BY created_at DESC;

Example 4:
Question: "What's the average time between vehicle in and vehicle out?"
SQL: SELECT AVG(EXTRACT(EPOCH FROM (vo.created_at - vi.created_at))/3600) as avg_hours FROM iso_tank it JOIN vehicle_in vi ON it.vehicle_in_id = vi.id JOIN vehicle_out vo ON it.vehicle_out_id = vo.id WHERE vo.created_at IS NOT NULL;

Example 5:
Question: "List all service tanks with their status"
SQL: SELECT tank_number, service_tank_status, created_at FROM service_tank ORDER BY created_at DESC;
"""
    
    def __init__(self):
        """Initialize the SQL generator."""
        self.ai_client = ai_client
        self.model_name = model_name
        self.sdk_type = SDK_TYPE
    
    def generate_sql(self, question: str, schema: str) -> str:
        """
        Generate SQL query from natural language question.
        
        Args:
            question: Natural language question from user
            schema: Database schema description
            
        Returns:
            Generated SQL query string
            
        Raises:
            ValueError: If question is empty
            SQLGenerationError: If SQL generation fails after retry
        """
        if not question or not question.strip():
            raise ValueError("Question cannot be empty")
        
        logger.info(f"Generating SQL for question: {question}")
        
        # Build system prompt with schema and few-shot examples
        system_prompt = self._build_system_prompt(schema)
        
        # Try to generate SQL (with one retry on failure)
        for attempt in range(2):
            try:
                sql = self._call_ai(system_prompt, question)
                
                # Clean up the SQL (remove markdown, extra whitespace)
                sql = self._clean_sql(sql)
                
                # Ensure LIMIT clause exists
                sql = self._ensure_limit(sql)
                
                logger.info(f"Generated SQL: {sql}")
                return sql
                
            except Exception as e:
                if attempt == 0:
                    logger.warning(f"SQL generation attempt {attempt + 1} failed: {e}. Retrying...")
                    continue
                else:
                    logger.error(f"SQL generation failed after {attempt + 1} attempts: {e}")
                    raise SQLGenerationError(f"Failed to generate SQL query: {e}")
    
    def _build_system_prompt(self, schema: str) -> str:
        """Build the system prompt with schema and examples."""
        return f"""You are a SQL query generator for a PostgreSQL database.

{schema}

FEW-SHOT EXAMPLES:
{self.FEW_SHOT_EXAMPLES}

RULES:
- Return ONLY the SQL query, no markdown, no explanation, no code blocks
- Always use SELECT queries only
- Never use DROP, DELETE, UPDATE, INSERT, ALTER, TRUNCATE
- Always include LIMIT 100 to prevent large result sets (unless user specifies a different limit)
- Use proper JOINs when querying multiple tables
- Use date functions for time-based queries (e.g., DATE_TRUNC, CURRENT_DATE)
- Use snake_case for table and column names as shown in the schema
- For counting queries, use COUNT(*) or COUNT(column_name)
- For aggregations, use appropriate GROUP BY clauses

USER QUESTION:
"""
    
    def _call_ai(self, system_prompt: str, question: str) -> str:
        """Call the AI provider to generate SQL."""
        if self.sdk_type == "openai_compatible":
            # OpenAI-compatible API
            response = self.ai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": question}
                ],
                temperature=0.1,  # Low temperature for more deterministic output
                max_tokens=500
            )
            
            sql = response.choices[0].message.content.strip()
            
            # Log token usage
            if hasattr(response, 'usage'):
                logger.info(f"Token usage - prompt: {response.usage.prompt_tokens}, "
                          f"completion: {response.usage.completion_tokens}, "
                          f"total: {response.usage.total_tokens}")
            
            return sql
            
        elif self.sdk_type == "anthropic":
            # Anthropic API
            response = self.ai_client.messages.create(
                model=self.model_name,
                max_tokens=500,
                temperature=0.1,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": question}
                ]
            )
            
            sql = response.content[0].text.strip()
            
            # Log token usage
            if hasattr(response, 'usage'):
                logger.info(f"Token usage - input: {response.usage.input_tokens}, "
                          f"output: {response.usage.output_tokens}")
            
            return sql
        
        else:
            raise SQLGenerationError(f"Unsupported SDK type: {self.sdk_type}")
    
    def _clean_sql(self, sql: str) -> str:
        """
        Clean up SQL query by removing markdown code blocks and extra whitespace.
        
        Args:
            sql: Raw SQL from AI
            
        Returns:
            Cleaned SQL query
        """
        # Remove markdown code blocks (```sql ... ``` or ``` ... ```)
        sql = re.sub(r'^```(?:sql)?\s*\n?', '', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\n?```$', '', sql)
        
        # Remove extra whitespace and newlines
        sql = ' '.join(sql.split())
        
        # Ensure it ends with semicolon
        if not sql.endswith(';'):
            sql += ';'
        
        return sql
    
    def _ensure_limit(self, sql: str) -> str:
        """
        Ensure SQL query has a LIMIT clause to prevent large result sets.
        
        Args:
            sql: SQL query
            
        Returns:
            SQL query with LIMIT clause
        """
        # Check if LIMIT already exists (case-insensitive)
        if re.search(r'\bLIMIT\s+\d+', sql, re.IGNORECASE):
            return sql
        
        # Add LIMIT 100 before the semicolon
        if sql.endswith(';'):
            sql = sql[:-1] + ' LIMIT 100;'
        else:
            sql += ' LIMIT 100'
        
        return sql
