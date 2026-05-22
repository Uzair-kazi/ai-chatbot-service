"""
SQL Validator Agent

This agent validates SQL queries against the database schema to catch hallucinations
and ensure query safety before execution. It's designed to be integrated into the
SQL Generation Agent's self-critique loop.

Key features:
- Table name validation (exact match, case-insensitive)
- Column name validation within referenced tables
- JOIN clause validation (ON conditions present)
- Safety rule enforcement (no dangerous operations)
- Specific error messages for retry feedback
"""

import re
from typing import Dict, List, Set, Tuple
from agents.base import BaseAgent, AgentValidationError, AgentExecutionError
from agents.models.query_models import SQLValidationRequest, SQLValidationResponse
from config.logging_config import get_logger

logger = get_logger(__name__)


class SQLValidator(BaseAgent):
    """
    SQL validation agent that checks queries against schema and safety rules.
    
    This validator is designed to catch hallucinations before they cause SQL errors:
    1. Validates all table names exist in schema (exact match, case-insensitive)
    2. Validates all column names exist in referenced tables
    3. Validates JOIN clauses have ON conditions
    4. Enforces safety rules (no DROP, DELETE, UPDATE, etc.)
    5. Returns specific error messages for retry feedback
    
    Attributes:
        name: Agent name
        logger: Logger instance
    """
    
    # SQL functions that are allowed (don't need column validation)
    ALLOWED_FUNCTIONS = {
        'COUNT', 'SUM', 'AVG', 'MIN', 'MAX',
        'CURRENT_DATE', 'CURRENT_TIMESTAMP', 'NOW',
        'DATE_TRUNC', 'EXTRACT', 'COALESCE',
        'UPPER', 'LOWER', 'TRIM', 'LENGTH', 'EPOCH',
        'DISTINCT', 'CASE', 'WHEN', 'THEN', 'ELSE', 'END'
    }
    
    # Dangerous SQL keywords that should never appear
    DANGEROUS_KEYWORDS = {
        'DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE',
        'TRUNCATE', 'GRANT', 'REVOKE', 'EXEC', 'EXECUTE',
        'MERGE', 'REPLACE', 'UPSERT'
    }
    
    def __init__(self):
        """Initialize the SQL validator."""
        super().__init__(name="SQLValidator")
        self.logger.info("SQL validator initialized")
    
    def execute(self, request) -> dict:
        """
        Execute method required by BaseAgent interface.
        
        This method delegates to the validate method for SQL validation.
        
        Args:
            request: SQLValidationRequest or dict with sql and schema
            
        Returns:
            Dictionary representation of SQLValidationResponse
        """
        # Handle both SQLValidationRequest objects and raw dicts
        if isinstance(request, dict):
            validation_request = SQLValidationRequest(**request)
        else:
            validation_request = request
        
        response = self.validate(validation_request)
        return response.model_dump()
    
    def validate(self, request: SQLValidationRequest) -> SQLValidationResponse:
        """
        Validate SQL query against schema and safety rules.
        
        Args:
            request: SQLValidationRequest with SQL query and schema
            
        Returns:
            SQLValidationResponse with validation result and specific issues
            
        Raises:
            AgentValidationError: If request validation fails
            AgentExecutionError: If validation process fails
        """
        # Validate request
        if not request.sql or not request.sql.strip():
            raise AgentValidationError("SQL query cannot be empty")
        if not request.schema or not request.schema.strip():
            raise AgentValidationError("Schema cannot be empty")
        
        self.logger.info(f"Validating SQL query: {request.sql[:100]}...")
        
        try:
            issues = []
            
            # Step 1: Check for empty SQL
            sql = request.sql.strip()
            if not sql:
                issues.append("SQL query is empty")
                return SQLValidationResponse(
                    is_valid=False,
                    issues=issues,
                    sql=request.sql,
                    schema=request.schema
                )
            
            # Step 2: Check safety rules (dangerous keywords)
            safety_issues = self._check_safety_rules(sql)
            issues.extend(safety_issues)
            
            # Step 3: Parse schema to get valid tables and columns
            valid_tables, valid_columns = self._parse_schema(request.schema)
            self.logger.info(f"Parsed schema: {len(valid_tables)} tables, {sum(len(cols) for cols in valid_columns.values())} columns")
            
            # Step 4: Extract and validate table names
            sql_tables = self._extract_tables(sql)
            self.logger.info(f"Extracted tables from SQL: {sql_tables}")
            
            for table in sql_tables:
                if table not in valid_tables:
                    issues.append(f"Table '{table}' does not exist in the database. Available tables: {', '.join(sorted(valid_tables))}")
            
            # Step 5: Extract and validate column names
            sql_columns = self._extract_columns(sql)
            self.logger.info(f"Extracted columns from SQL: {sql_columns}")
            
            for column in sql_columns:
                # Skip wildcard
                if column == '*':
                    continue
                
                # Skip SQL functions
                if column.upper() in self.ALLOWED_FUNCTIONS:
                    continue
                
                # Skip aggregate function patterns
                if re.match(r'^(COUNT|SUM|AVG|MIN|MAX)\(', column, re.IGNORECASE):
                    continue
                
                # Check if column exists in any table
                column_found = False
                for table_columns in valid_columns.values():
                    if column in table_columns:
                        column_found = True
                        break
                
                if not column_found:
                    # Provide helpful error message with available columns
                    all_columns = set()
                    for table_columns in valid_columns.values():
                        all_columns.update(table_columns)
                    
                    issues.append(f"Column '{column}' does not exist in the database. Available columns: {', '.join(sorted(all_columns))}")
            
            # Step 6: Check for JOINs without ON clauses
            if self._has_join_without_on(sql):
                issues.append("JOIN clause is missing ON condition. All JOINs must have explicit ON conditions.")
            
            # Step 7: Ensure query is SELECT only
            if not sql.upper().strip().startswith('SELECT'):
                issues.append("Only SELECT queries are allowed. Use SELECT to retrieve data.")
            
            # Return validation result
            is_valid = len(issues) == 0
            
            if is_valid:
                self.logger.info("SQL validation passed")
            else:
                self.logger.warning(f"SQL validation failed with {len(issues)} issues: {issues}")
            
            return SQLValidationResponse(
                is_valid=is_valid,
                issues=issues,
                sql=request.sql,
                schema=request.schema
            )
            
        except Exception as e:
            self.logger.error(f"SQL validation error: {e}", exc_info=True)
            raise AgentExecutionError(f"SQL validation failed: {str(e)}")
    
    def _check_safety_rules(self, sql: str) -> List[str]:
        """
        Check SQL safety rules (dangerous operations).
        
        Args:
            sql: SQL query to check
            
        Returns:
            List of safety violations
        """
        issues = []
        sql_upper = sql.upper()
        
        for keyword in self.DANGEROUS_KEYWORDS:
            if re.search(r'\b' + keyword + r'\b', sql_upper):
                issues.append(f"Dangerous keyword '{keyword}' is not allowed. Only SELECT queries are permitted.")
        
        return issues
    
    def _parse_schema(self, schema: str) -> Tuple[Set[str], Dict[str, Set[str]]]:
        """
        Parse schema to extract table names and column mappings.
        
        Args:
            schema: Schema description string
            
        Returns:
            Tuple of (valid_tables, table_to_columns_mapping)
        """
        valid_tables = set()
        valid_columns = {}
        current_table = None
        
        for line in schema.split('\n'):
            line = line.strip()
            
            # Match table definition
            table_match = re.match(r'^Table:\s+(\w+)', line, re.IGNORECASE)
            if table_match:
                current_table = table_match.group(1)
                valid_tables.add(current_table)
                valid_columns[current_table] = set()
                continue
            
            # Match column definition
            if current_table:
                column_match = re.match(r'^\s*-\s+(\w+):', line)
                if column_match:
                    column_name = column_match.group(1)
                    valid_columns[current_table].add(column_name)
        
        return valid_tables, valid_columns
    
    def _extract_tables(self, sql: str) -> Set[str]:
        """
        Extract table names from SQL query.
        
        Args:
            sql: SQL query
            
        Returns:
            Set of table names found in the query
        """
        tables = set()
        
        # Remove string literals to avoid false matches
        sql_cleaned = re.sub(r"'[^']*'", '', sql)
        sql_cleaned = re.sub(r'"[^"]*"', '', sql_cleaned)
        
        # Pattern to match table names after FROM, JOIN, UPDATE, etc.
        # This handles quoted table names and aliases
        patterns = [
            r'\bFROM\s+(?:"([^"]+)"|(\w+))',
            r'\bJOIN\s+(?:"([^"]+)"|(\w+))',
            r'\bINTO\s+(?:"([^"]+)"|(\w+))',
            r'\bUPDATE\s+(?:"([^"]+)"|(\w+))',
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, sql_cleaned, re.IGNORECASE)
            for match in matches:
                # Get the table name (either quoted or unquoted)
                table_name = match.group(1) or match.group(2)
                if table_name:
                    # Remove alias if present (e.g., "table_name alias" -> "table_name")
                    table_name = table_name.split()[0]
                    tables.add(table_name)
        
        return tables
    
    def _extract_columns(self, sql: str) -> Set[str]:
        """
        Extract column names from SQL query.
        
        Args:
            sql: SQL query
            
        Returns:
            Set of column names found in the query
        """
        columns = set()
        
        # Remove string literals to avoid false matches
        sql_cleaned = re.sub(r"'[^']*'", '', sql)
        sql_cleaned = re.sub(r'"[^"]*"', '', sql_cleaned)
        
        # Extract SELECT clause columns
        select_match = re.search(r'\bSELECT\s+(.*?)\s+FROM', sql_cleaned, re.IGNORECASE | re.DOTALL)
        if select_match:
            select_clause = select_match.group(1)
            
            # Split by comma and extract column names
            for item in select_clause.split(','):
                item = item.strip()
                
                # Skip empty items
                if not item:
                    continue
                
                # Handle table.column format
                if '.' in item:
                    parts = item.split('.')
                    if len(parts) == 2:
                        column = parts[1].strip()
                        # Remove quotes if present
                        column = re.sub(r'^["\']|["\']$', '', column)
                        columns.add(column)
                else:
                    # Direct column reference
                    column = item.strip()
                    # Remove quotes if present
                    column = re.sub(r'^["\']|["\']$', '', column)
                    # Skip functions and keywords
                    if not re.match(r'^(COUNT|SUM|AVG|MIN|MAX|DISTINCT)\s*\(', column, re.IGNORECASE):
                        columns.add(column)
        
        # Extract WHERE clause columns
        where_match = re.search(r'\bWHERE\s+(.*?)(?:\s+ORDER\s+BY|\s+GROUP\s+BY|\s+HAVING|\s+LIMIT|$)', sql_cleaned, re.IGNORECASE | re.DOTALL)
        if where_match:
            where_clause = where_match.group(1)
            
            # Extract column references (table.column or just column)
            column_matches = re.finditer(r'\b(?:(\w+)\.)?(\w+)\s*(?:[=<>!]+|IN|LIKE|BETWEEN)', where_clause, re.IGNORECASE)
            for match in column_matches:
                column = match.group(2)
                if column and column.upper() not in self.ALLOWED_FUNCTIONS:
                    columns.add(column)
        
        # Extract ORDER BY columns
        order_match = re.search(r'\bORDER\s+BY\s+(.*?)(?:\s+LIMIT|$)', sql_cleaned, re.IGNORECASE | re.DOTALL)
        if order_match:
            order_clause = order_match.group(1)
            
            for item in order_clause.split(','):
                item = item.strip()
                # Remove ASC/DESC
                item = re.sub(r'\s+(ASC|DESC)$', '', item, flags=re.IGNORECASE)
                
                # Handle table.column format
                if '.' in item:
                    parts = item.split('.')
                    if len(parts) == 2:
                        column = parts[1].strip()
                        columns.add(column)
                else:
                    column = item.strip()
                    if column and column.upper() not in self.ALLOWED_FUNCTIONS:
                        columns.add(column)
        
        return columns
    
    def _has_join_without_on(self, sql: str) -> bool:
        """
        Check if SQL has JOIN clauses without ON conditions.
        
        Args:
            sql: SQL query
            
        Returns:
            True if there are JOINs without ON conditions
        """
        # Find all JOIN clauses
        join_matches = re.finditer(r'\b(INNER\s+JOIN|LEFT\s+JOIN|RIGHT\s+JOIN|FULL\s+JOIN|JOIN)\s+\w+', sql, re.IGNORECASE)
        
        for match in join_matches:
            # Look for ON clause after this JOIN
            remaining_sql = sql[match.end():]
            
            # Check if there's an ON clause before the next JOIN or end of query
            on_match = re.search(r'\bON\b', remaining_sql, re.IGNORECASE)
            next_join_match = re.search(r'\b(INNER\s+JOIN|LEFT\s+JOIN|RIGHT\s+JOIN|FULL\s+JOIN|JOIN)\b', remaining_sql, re.IGNORECASE)
            
            # If no ON clause found, or ON clause is after the next JOIN, this JOIN is missing ON
            if not on_match or (next_join_match and on_match.start() > next_join_match.start()):
                return True
        
        return False