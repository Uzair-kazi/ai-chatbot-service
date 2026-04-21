"""
Schema Intelligence Models

This module defines Pydantic models for Schema Intelligence agent communication.
Models include requests, responses, and internal data structures for schema
processing, entity extraction, and graph traversal.
"""

from typing import Dict, List, Set, Tuple, Optional, Any
from pydantic import BaseModel, Field


class ForeignKeyRelationship(BaseModel):
    """
    Represents a foreign key relationship between tables.
    
    Attributes:
        source_table: Table containing the foreign key
        source_column: Foreign key column name
        target_table: Referenced table
        target_column: Referenced column (usually primary key)
    """
    source_table: str
    source_column: str
    target_table: str
    target_column: str


class SchemaGraph(BaseModel):
    """
    Graph representation of database schema with foreign key relationships.
    
    The graph is stored as an adjacency list where each table maps to its
    foreign key relationships.
    
    Attributes:
        tables: Set of all table names in the schema
        relationships: List of all foreign key relationships
        adjacency_list: Graph structure {table: {fk_column: (target_table, target_column)}}
        
    Example:
        graph = SchemaGraph(
            tables={"iso_tank", "vehicle_in"},
            relationships=[...],
            adjacency_list={
                "iso_tank": {
                    "vehicle_in_id": ("vehicle_in", "id")
                }
            }
        )
    """
    tables: Set[str] = Field(default_factory=set)
    relationships: List[ForeignKeyRelationship] = Field(default_factory=list)
    adjacency_list: Dict[str, Dict[str, Tuple[str, str]]] = Field(default_factory=dict)


class EntityMatch(BaseModel):
    """
    Represents a matched entity from natural language to database table.
    
    Attributes:
        entity: Original entity text from question
        table: Matched table name
        similarity: Similarity score (0.0-1.0)
        match_type: Type of match (table_name, column_name, exact, fuzzy)
    """
    entity: str
    table: str
    similarity: float = Field(ge=0.0, le=1.0)
    match_type: str


class JoinHint(BaseModel):
    """
    Represents a JOIN path hint discovered during graph traversal.
    
    Attributes:
        from_table: Source table
        to_table: Target table
        join_condition: SQL JOIN condition (e.g., "iso_tank.vehicle_in_id = vehicle_in.id")
        depth: Traversal depth where this relationship was found
    """
    from_table: str
    to_table: str
    join_condition: str
    depth: int


class PrunedSchema(BaseModel):
    """
    Pruned schema containing only relevant tables and columns.
    
    Attributes:
        schema_text: Formatted schema string (matches SchemaIntrospector format)
        selected_tables: List of tables included in pruned schema
        join_hints: List of JOIN path hints
        token_count: Estimated token count of pruned schema
        original_token_count: Estimated token count of original schema
        reduction_percentage: Percentage reduction in token count
    """
    schema_text: str
    selected_tables: List[str]
    join_hints: List[JoinHint]
    token_count: int
    original_token_count: int
    reduction_percentage: float


class SchemaIntelligenceRequest(BaseModel):
    """
    Request model for Schema Intelligence agent.
    
    Attributes:
        question: Natural language question from user
        full_schema: Complete database schema from SchemaIntrospector
        max_depth: Maximum graph traversal depth (default 2)
        similarity_threshold: Minimum similarity for entity matching (default 0.7)
    """
    question: str = Field(..., min_length=1)
    full_schema: str = Field(..., min_length=1)
    max_depth: int = Field(default=2, ge=0, le=5)
    similarity_threshold: float = Field(default=0.6, ge=0.0, le=1.0)


class SchemaIntelligenceResponse(BaseModel):
    """
    Response model for Schema Intelligence agent.
    
    Attributes:
        success: Whether schema pruning succeeded
        pruned_schema: Pruned schema with only relevant tables (None if failed)
        selected_tables: List of tables included in pruned schema
        join_hints: List of JOIN path hints
        entity_matches: List of entity-to-table matches
        confidence: Confidence score (0.0-1.0)
        error: Optional error message
        metadata: Additional metadata (cache hit, execution time, etc.)
    """
    success: bool
    pruned_schema: Optional[str] = None
    selected_tables: List[str] = Field(default_factory=list)
    join_hints: List[JoinHint] = Field(default_factory=list)
    entity_matches: List[EntityMatch] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
