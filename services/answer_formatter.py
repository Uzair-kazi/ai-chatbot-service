"""
Answer Formatter Service

This module formats SQL query results into natural language summaries using AI.
It takes raw query results and generates human-readable answers.
"""

from typing import Dict, Any, List
from config.ai_provider import ai_client, model_name, SDK_TYPE
from config.logging_config import get_logger

logger = get_logger(__name__)


class AnswerFormattingError(Exception):
    """Raised when answer formatting fails."""
    pass


class AnswerFormatter:
    """Formats query results into natural language using AI."""
    
    def __init__(self):
        """Initialize the answer formatter."""
        self.ai_client = ai_client
        self.model_name = model_name
        self.sdk_type = SDK_TYPE
    
    def format_answer(self, question: str, sql: str, results: Dict[str, Any]) -> str:
        """
        Format query results into a natural language answer.
        
        Args:
            question: Original user question
            sql: SQL query that was executed
            results: Query results dict with columns, rows, row_count
            
        Returns:
            Natural language answer string
            
        Raises:
            AnswerFormattingError: If formatting fails after retry
        """
        logger.info(f"Formatting answer for question: {question}")
        
        # Handle empty results
        if results["row_count"] == 0:
            logger.info("No results found, returning empty result message")
            return "No results found for your question."
        
        # Build prompt with results
        prompt = self._build_prompt(question, sql, results)
        
        # Try to format answer (with one retry on failure)
        for attempt in range(2):
            try:
                answer = self._call_ai(prompt)
                
                logger.info(f"Answer formatted successfully (length: {len(answer)} chars)")
                return answer
                
            except Exception as e:
                if attempt == 0:
                    logger.warning(f"Answer formatting attempt {attempt + 1} failed: {e}. Retrying...")
                    continue
                else:
                    logger.error(f"Answer formatting failed after {attempt + 1} attempts: {e}")
                    raise AnswerFormattingError(f"Failed to format answer: {e}")
    
    def _build_prompt(self, question: str, sql: str, results: Dict[str, Any]) -> str:
        """
        Build the prompt for AI to format the answer.
        
        Args:
            question: Original user question
            sql: SQL query that was executed
            results: Query results
            
        Returns:
            Formatted prompt string
        """
        # Get first 10 rows for summarization
        rows_to_show = results["rows"][:10]
        total_rows = results["row_count"]
        
        # Format rows as a readable table
        rows_text = self._format_rows_as_text(rows_to_show, results["columns"])
        
        # Build truncation message if needed
        truncation_msg = ""
        if total_rows > 10:
            truncation_msg = f"\n(Showing 10 of {total_rows} total rows)"
        
        prompt = f"""You are a helpful assistant that summarizes database query results.

ORIGINAL QUESTION:
{question}

SQL QUERY USED:
{sql}

QUERY RESULTS (showing {min(total_rows, 10)} of {total_rows} rows):
{rows_text}{truncation_msg}

Provide a concise, natural language answer that:
- Directly answers the user's question
- References actual numbers from the results
- Mentions if results were truncated (showing X of Y)
- Uses clear, professional language
- Formats large numbers with commas (e.g., "1,234 tanks" not "1234 tanks")
- For single-row results (like COUNT), format as a sentence
- For multiple rows, format as a bulleted list or summary

ANSWER:
"""
        
        return prompt
    
    def _format_rows_as_text(self, rows: List[Dict], columns: List[str]) -> str:
        """
        Format rows as readable text for the prompt.
        
        Args:
            rows: List of row dictionaries
            columns: List of column names
            
        Returns:
            Formatted text representation of rows
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
        
        # For multiple rows, format as a simple table
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
    
    def _call_ai(self, prompt: str) -> str:
        """Call the AI provider to format the answer."""
        if self.sdk_type == "openai_compatible":
            # OpenAI-compatible API
            response = self.ai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # Slightly higher for more natural language
                max_tokens=500
            )
            
            answer = response.choices[0].message.content.strip()
            
            # Log token usage
            if hasattr(response, 'usage'):
                logger.info(f"Token usage - prompt: {response.usage.prompt_tokens}, "
                          f"completion: {response.usage.completion_tokens}, "
                          f"total: {response.usage.total_tokens}")
            
            return answer
            
        elif self.sdk_type == "anthropic":
            # Anthropic API
            response = self.ai_client.messages.create(
                model=self.model_name,
                max_tokens=500,
                temperature=0.3,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            answer = response.content[0].text.strip()
            
            # Log token usage
            if hasattr(response, 'usage'):
                logger.info(f"Token usage - input: {response.usage.input_tokens}, "
                          f"output: {response.usage.output_tokens}")
            
            return answer
        
        else:
            raise AnswerFormattingError(f"Unsupported SDK type: {self.sdk_type}")
