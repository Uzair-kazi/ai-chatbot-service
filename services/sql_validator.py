"""
SQL Validator Service

This module validates SQL queries for safety and correctness:
1. Pre-validation: Checks that all table/column references exist in the schema
2. Safety guards: Blocks dangerous operations (writes, drops, injections)
"""

import re
from typing import Tuple
from config.logging_config import get_logger

logger = get_logger(__name__)


class SQLValidator:
    """Validates SQL queries for safety and schema correctness."""
    
    # Dangerous SQL keywords (blocklist)
    DANGEROUS_KEYWORDS = [
        'DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER',
        'TRUNCATE', 'GRANT', 'REVOKE', 'CREATE', 'REPLACE'
    ]
    
    # SQL functions to skip during validation
    SQL_FUNCTIONS = [
        'COUNT', 'SUM', 'AVG', 'MIN', 'MAX',
        'CURRENT_DATE', 'CURRENT_TIMESTAMP', 'NOW',
        'DATE_TRUNC', 'EXTRACT', 'COALESCE',
        'UPPER', 'LOWER', 'TRIM', 'LENGTH'
    ]
    
    def __init__(self):
        """Initialize the SQL validator."""
        pass
    
    def validate_references(self, sql: str, schema: str) -> Tuple[bool, str]:
        """
        Validate that all table and column references in SQL exist in the schema.
        
        Args:
            sql: SQL query to validate
            schema: Database schema description
            
        Returns:
            Tuple of (is_valid, error_message)
            - (True, "") if all references are valid
            - (False, "error message") if invalid references found
        """
        if not sql or not sql.strip():
            return (False, "SQL cannot be empty")
        
        logger.info("Validating SQL references against schema")
        
        # Parse schema to extract valid tables and columns
        valid_tables, valid_columns = self._parse_schema(schema)
        
        # Extract table references from SQL
        sql_tables = self._extract_tables(sql)
        
        # Validate tables
        for table in sql_tables:
            if table not in valid_tables:
                error_msg = f"Table '{table}' does not exist in the database"
                logger.warning(f"Validation failed: {error_msg}")
                return (False, error_msg)
        
        # Extract column references from SQL
        sql_columns = self._extract_columns(sql)
        
        # Validate columns (skip aggregate functions and SQL functions)
        for column in sql_columns:
            # Skip wildcard
            if column == '*':
                continue
            
            # Skip SQL functions
            if column.upper() in self.SQL_FUNCTIONS:
                continue
            
            # Skip aggregate function patterns like COUNT(*), SUM(amount)
            if re.match(r'^(COUNT|SUM|AVG|MIN|MAX)\(', column, re.IGNORECASE):
                continue
            
            # Check if column exists in any table
            column_found = False
            for table_columns in valid_columns.values():
                if column in table_columns:
                    column_found = True
                    break
            
            if not column_found:
                error_msg = f"Column '{column}' does not exist in the database"
                logger.warning(f"Validation failed: {error_msg}")
                return (False, error_msg)
        
        logger.info("SQL references validation passed")
        return (True, "")
    
    def check_safety(self, sql: str) -> Tuple[bool, str]:
        """
        Check if SQL query is safe (blocks dangerous operations).
        
        Uses two layers of validation:
        1. Keyword blocklist - blocks dangerous SQL keywords
        2. Whitelist - only allows SELECT queries
        
        Args:
            sql: SQL query to check
            
        Returns:
            Tuple of (is_safe, error_message)
            - (True, "") if query is safe
            - (False, "error message") if query is dangerous
        """
        if not sql or not sql.strip():
            return (False, "SQL cannot be empty")
        
        logger.info("Checking SQL safety")
        
        # Layer 1: Keyword blocklist (case-insensitive)
        sql_upper = sql.upper()
        for keyword in self.DANGEROUS_KEYWORDS:
            if re.search(r'\b' + keyword + r'\b', sql_upper):
                error_msg = "That question can't be answered safely"
                logger.warning(f"Safety check failed: Dangerous keyword '{keyword}' detected")
                return (False, error_msg)
        
        # Layer 2: Whitelist - only allow SELECT queries
        sql_trimmed = sql.strip().upper()
        if not sql_trimmed.startswith('SELECT'):
            error_msg = "Only SELECT queries are allowed"
            logger.warning(f"Safety check failed: Query does not start with SELECT")
            return (False, error_msg)
        
        logger.info("SQL safety check passed")
        return (True, "")
    
    def _parse_schema(self, schema: str) -> Tuple[set, dict]:
        """
        Parse schema description to extract valid tables and columns.
        
        Args:
            schema: Schema description string
            
        Returns:
            Tuple of (valid_tables, valid_columns)
            - valid_tables: set of table names
            - valid_columns: dict mapping table names to sets of column names
        """
        valid_tables = set()
        valid_columns = {}
        
        current_table = None
        
        for line in schema.split('\n'):
            line = line.strip()
            
            # Match table definition: "Table: table_name"
            table_match = re.match(r'^Table:\s+(\w+)', line, re.IGNORECASE)
            if table_match:
                current_table = table_match.group(1)
                valid_tables.add(current_table)
                valid_columns[current_table] = set()
                continue
            
            # Match column definition: "  - column_name: type ..."
            if current_table:
                column_match = re.match(r'^\s*-\s+(\w+):', line)
                if column_match:
                    column_name = column_match.group(1)
                    valid_columns[current_table].add(column_name)
        
        return valid_tables, valid_columns
    
    def _extract_tables(self, sql: str) -> set:
        """
        Extract table names from SQL query.
        
        Handles:
        - FROM clauses
        - JOIN clauses
        - Table aliases (e.g., "FROM iso_tank AS t" -> extracts "iso_tank")
        
        Args:
            sql: SQL query
            
        Returns:
            Set of table names
        """
        tables = set()
        
        # Pattern for FROM and JOIN clauses
        # Matches: FROM table_name, JOIN table_name, FROM table_name AS alias
        patterns = [
            r'\bFROM\s+(\w+)',
            r'\bJOIN\s+(\w+)',
            r'\bINNER\s+JOIN\s+(\w+)',
            r'\bLEFT\s+JOIN\s+(\w+)',
            r'\bRIGHT\s+JOIN\s+(\w+)',
            r'\bFULL\s+JOIN\s+(\w+)'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, sql, re.IGNORECASE)
            tables.update(matches)
        
        return tables
    
    def _extract_columns(self, sql: str) -> set:
        """
        Extract column names from SQL query.
        
        Handles:
        - SELECT clauses
        - WHERE clauses
        - ORDER BY clauses
        - GROUP BY clauses
        - Qualified column names (e.g., "table.column" -> extracts "column")
        - Aggregate functions (e.g., "COUNT(*)" -> extracts "*")
        
        Args:
            sql: SQL query
            
        Returns:
            Set of column names
        """
        columns = set()
        
        # Extract from SELECT clause
        select_match = re.search(r'SELECT\s+(.*?)\s+FROM', sql, re.IGNORECASE | re.DOTALL)
        if select_match:
            select_clause = select_match.group(1)
            # Split by comma and extract column names
            for item in select_clause.split(','):
                item = item.strip()
                
                # Handle qualified names (table.column)
                if '.' in item:
                    item = item.split('.')[-1]
                
                # Handle aliases (column AS alias)
                if ' AS ' in item.upper():
                    item = item.split(' AS ')[0].strip()
                
                # Handle aggregate functions
                func_match = re.match(r'(\w+)\((.*?)\)', item, re.IGNORECASE)
                if func_match:
                    func_name = func_match.group(1)
                    func_arg = func_match.group(2).strip()
                    if func_arg and func_arg != '*':
                        columns.add(func_arg)
                    else:
                        columns.add('*')
                else:
                    # Regular column name
                    column_name = re.sub(r'[^\w*]', '', item)
                    if column_name:
                        columns.add(column_name)
        
        # Extract from WHERE clause
        where_match = re.search(r'WHERE\s+(.*?)(?:GROUP BY|ORDER BY|LIMIT|;|$)', sql, re.IGNORECASE | re.DOTALL)
        if where_match:
            where_clause = where_match.group(1)
            # Extract column names (word before =, <, >, etc.)
            column_matches = re.findall(r'(\w+)\s*[=<>!]', where_clause)
            for col in column_matches:
                # Skip SQL keywords
                if col.upper() not in ['AND', 'OR', 'NOT', 'IN', 'IS', 'NULL']:
                    columns.add(col)
        
        # Extract from ORDER BY clause
        order_match = re.search(r'ORDER BY\s+(.*?)(?:LIMIT|;|$)', sql, re.IGNORECASE)
        if order_match:
            order_clause = order_match.group(1)
            # Split by comma and extract column names
            for item in order_clause.split(','):
                item = item.strip()
                # Remove ASC/DESC
                item = re.sub(r'\s+(ASC|DESC)$', '', item, flags=re.IGNORECASE)
                # Handle qualified names
                if '.' in item:
                    item = item.split('.')[-1]
                column_name = re.sub(r'[^\w]', '', item)
                if column_name:
                    columns.add(column_name)
        
        # Extract from GROUP BY clause
        group_match = re.search(r'GROUP BY\s+(.*?)(?:ORDER BY|LIMIT|;|$)', sql, re.IGNORECASE)
        if group_match:
            group_clause = group_match.group(1)
            # Split by comma and extract column names
            for item in group_clause.split(','):
                item = item.strip()
                # Handle qualified names
                if '.' in item:
                    item = item.split('.')[-1]
                column_name = re.sub(r'[^\w]', '', item)
                if column_name:
                    columns.add(column_name)
        
        return columns
