"""
Database Schema Introspection Service

This module connects to the PostgreSQL database and generates a human-readable
schema description for AI prompts. The schema includes table names, column names,
data types, and foreign key relationships.
"""

import os
from typing import Optional
import psycopg2
from psycopg2 import pool
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class SchemaIntrospector:
    """Introspects PostgreSQL database schema for AI prompt generation."""
    
    def __init__(self, db_url: Optional[str] = None):
        """
        Initialize the schema introspector.
        
        Args:
            db_url: PostgreSQL connection string. If None, reads from DB_URL env var.
        """
        self.db_url = db_url or os.getenv("DB_URL")
        if not self.db_url:
            raise ValueError("DB_URL environment variable is required")
        
        # Create connection pool (min=1, max=10)
        try:
            self.pool = psycopg2.pool.SimpleConnectionPool(
                1, 10, self.db_url
            )
        except psycopg2.Error as e:
            raise ConnectionError(f"Failed to connect to database: {e}")
    
    def get_database_schema(self) -> str:
        """
        Generate a human-readable schema description.
        
        Returns:
            Formatted string containing table names, columns, data types,
            and foreign key relationships.
            
        Raises:
            ConnectionError: If database connection fails
            RuntimeError: If schema introspection fails
        """
        conn = None
        try:
            conn = self.pool.getconn()
            cursor = conn.cursor()
            
            # Get all tables in the public schema
            cursor.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_type = 'BASE TABLE'
                ORDER BY table_name;
            """)
            tables = [row[0] for row in cursor.fetchall()]
            
            schema_description = []
            schema_description.append("Database Schema:")
            schema_description.append("=" * 80)
            schema_description.append("")
            
            for table in tables:
                schema_description.append(f"Table: {table}")
                schema_description.append("-" * 80)
                
                # Get columns for this table
                cursor.execute("""
                    SELECT 
                        column_name,
                        data_type,
                        character_maximum_length,
                        is_nullable,
                        column_default
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = %s
                    ORDER BY ordinal_position;
                """, (table,))
                
                columns = cursor.fetchall()
                
                # Get primary keys
                cursor.execute("""
                    SELECT kcu.column_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                      ON tc.constraint_name = kcu.constraint_name
                      AND tc.table_schema = kcu.table_schema
                    WHERE tc.constraint_type = 'PRIMARY KEY'
                      AND tc.table_schema = 'public'
                      AND tc.table_name = %s;
                """, (table,))
                
                primary_keys = {row[0] for row in cursor.fetchall()}
                
                # Get foreign keys
                cursor.execute("""
                    SELECT
                        kcu.column_name,
                        ccu.table_name AS foreign_table_name,
                        ccu.column_name AS foreign_column_name
                    FROM information_schema.table_constraints AS tc
                    JOIN information_schema.key_column_usage AS kcu
                      ON tc.constraint_name = kcu.constraint_name
                      AND tc.table_schema = kcu.table_schema
                    JOIN information_schema.constraint_column_usage AS ccu
                      ON ccu.constraint_name = tc.constraint_name
                      AND ccu.table_schema = tc.table_schema
                    WHERE tc.constraint_type = 'FOREIGN KEY'
                      AND tc.table_schema = 'public'
                      AND tc.table_name = %s;
                """, (table,))
                
                foreign_keys = {
                    row[0]: (row[1], row[2])
                    for row in cursor.fetchall()
                }
                
                # Format column information
                for col in columns:
                    col_name, data_type, max_length, nullable, default = col
                    
                    # Build column description
                    type_desc = data_type
                    if max_length:
                        type_desc += f"({max_length})"
                    
                    annotations = []
                    if col_name in primary_keys:
                        annotations.append("primary key")
                    if col_name in foreign_keys:
                        fk_table, fk_col = foreign_keys[col_name]
                        annotations.append(f"foreign key -> {fk_table}.{fk_col}")
                    if nullable == 'NO':
                        annotations.append("not null")
                    if default:
                        # Simplify default value display
                        default_val = default.split('::')[0]  # Remove type cast
                        if len(default_val) > 50:
                            default_val = default_val[:47] + "..."
                        annotations.append(f"default: {default_val}")
                    
                    annotation_str = f" ({', '.join(annotations)})" if annotations else ""
                    schema_description.append(f"  - {col_name}: {type_desc}{annotation_str}")
                
                schema_description.append("")
            
            cursor.close()
            return "\n".join(schema_description)
            
        except psycopg2.Error as e:
            raise RuntimeError(f"Failed to introspect database schema: {e}")
        finally:
            if conn:
                self.pool.putconn(conn)
    
    def close(self):
        """Close the connection pool."""
        if hasattr(self, 'pool') and self.pool:
            self.pool.closeall()


# Global instance for easy import
_introspector: Optional[SchemaIntrospector] = None


def get_database_schema() -> str:
    """
    Get the database schema description.
    
    This is a convenience function that creates a global SchemaIntrospector
    instance on first call and reuses it for subsequent calls.
    
    Returns:
        Formatted string containing the database schema.
        
    Raises:
        ValueError: If DB_URL environment variable is not set
        ConnectionError: If database connection fails
        RuntimeError: If schema introspection fails
    """
    global _introspector
    
    if _introspector is None:
        _introspector = SchemaIntrospector()
    
    return _introspector.get_database_schema()


def close_schema_introspector():
    """Close the global schema introspector connection pool."""
    global _introspector
    
    if _introspector is not None:
        _introspector.close()
        _introspector = None
