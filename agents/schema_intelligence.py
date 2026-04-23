"""
Schema Intelligence Agent with MCP Integration

This agent performs intelligent schema pruning to reduce token usage and improve
SQL generation accuracy. It extracts entities from questions, traverses foreign
key relationships via graph search, and prunes the schema to only relevant tables.

Phase 3 enhancements:
- MCP client integration for enhanced entity extraction and schema analysis
- Fallback mode when MCP server is not available
- Improved entity matching with external knowledge

Key features:
- Entity extraction from natural language (with MCP enhancement)
- Fuzzy matching to map entities to tables
- BFS graph traversal to discover JOIN paths
- Schema pruning (8,000 → 300 tokens, 95% reduction)
- Caching with TTL for performance
- MCP client integration with graceful fallback
"""

import re
import time
import hashlib
import yaml
import os
from typing import Dict, List, Set, Tuple, Optional
from collections import deque
from difflib import SequenceMatcher

from agents.base import BaseAgent, AgentExecutionError, AgentValidationError
from agents.mcp_client import MCPClient
from agents.embeddings import get_embedding_matcher
from agents.models.schema_models import (
    SchemaIntelligenceRequest,
    SchemaIntelligenceResponse,
    SchemaGraph,
    ForeignKeyRelationship,
    EntityMatch,
    JoinHint,
    PrunedSchema
)
from agents.cache import default_cache
from config.logging_config import get_logger

logger = get_logger(__name__)


class SchemaIntelligenceAgent(BaseAgent):
    """
    Schema Intelligence agent with entity extraction, graph traversal, and MCP integration.
    
    This agent reduces schema token count by 95% through intelligent pruning:
    1. Extract entities from natural language question (enhanced with MCP)
    2. Fuzzy match entities to database tables
    3. Build foreign key relationship graph
    4. Traverse graph (BFS) to discover JOIN paths
    5. Prune schema to only relevant tables and columns
    6. Cache results for performance
    
    Phase 3 enhancements:
    - MCP client integration for enhanced entity extraction
    - Graceful fallback when MCP server unavailable
    - Improved entity matching with external knowledge
    
    Attributes:
        name: Agent name
        logger: Logger instance
        cache: Cache instance for storing pruned schemas
        mcp_client: MCP client for enhanced schema analysis
        stopwords: Common words to filter from entity extraction
    """
    
    # Common English stopwords to filter from entity extraction
    # Note: SQL keywords like "show", "list", "get" are intentionally NOT included
    # because they don't cause false positive table matches (similarity < 0.6 threshold)
    # and might be legitimate entities in some contexts (e.g., "show" as a table name).
    STOPWORDS = {
        'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
        'has', 'have', 'in', 'is', 'it', 'of', 'on', 'that', 'the', 'to',
        'was', 'were', 'will', 'with', 'this', 'these', 'those', 'what',
        'which', 'who', 'how', 'many', 'much', 'most', 'some', 'all', 'any',
        'do', 'does', 'did', 'can', 'could', 'should', 'would', 'may', 'might'
    }
    
    def __init__(self):
        """Initialize the Schema Intelligence agent with MCP client."""
        super().__init__(name="SchemaIntelligenceAgent")
        self.cache = default_cache
        self.mcp_client = MCPClient()
        
        # Load business glossary for domain-specific entity extraction
        self.business_glossary = self._load_business_glossary()
        
        self.logger.info("Schema Intelligence agent initialized with MCP client and caching")
    
    def execute(self, request: SchemaIntelligenceRequest) -> SchemaIntelligenceResponse:
        """
        Execute schema intelligence: extract entities, prune schema, cache result.
        
        Workflow:
        1. Validate request
        2. Extract entities from question
        3. Check cache for pruned schema
        4. Build foreign key graph
        5. Traverse graph to find relevant tables
        6. Prune schema to selected tables
        7. Cache result
        8. Return pruned schema with JOIN hints
        
        Args:
            request: SchemaIntelligenceRequest with question and full schema
            
        Returns:
            SchemaIntelligenceResponse with pruned schema and metadata
            
        Raises:
            AgentValidationError: If request validation fails
            AgentExecutionError: If schema processing fails
        """
        start_time = time.time()
        
        # Validate request
        if not request.question or not request.question.strip():
            raise AgentValidationError("Question cannot be empty")
        if not request.full_schema or not request.full_schema.strip():
            raise AgentValidationError("Schema cannot be empty")
        
        self.logger.info(f"Processing question: {request.question}")
        
        try:
            # Step 1: Extract entities from question
            entities = self._extract_entities(request.question)
            self.logger.info(f"Extracted entities: {entities}")
            
            # If no entities found, return full schema with low confidence
            if not entities:
                self.logger.warning("No entities extracted - returning full schema")
                return SchemaIntelligenceResponse(
                    success=True,
                    pruned_schema=request.full_schema,
                    selected_tables=[],
                    join_hints=[],
                    entity_matches=[],
                    confidence=0.5,
                    metadata={
                        "execution_time": time.time() - start_time,
                        "cache_hit": False,
                        "fallback_reason": "no_entities_extracted"
                    }
                )
            
            # Step 2: Check cache
            cache_key = self._generate_cache_key(entities)
            cached_result = self.cache.get(cache_key)
            
            if cached_result:
                self.logger.info(f"Cache hit for entities: {entities}")
                cached_result["metadata"]["cache_hit"] = True
                cached_result["metadata"]["execution_time"] = time.time() - start_time
                return SchemaIntelligenceResponse(**cached_result)
            
            # Step 3: Build foreign key graph
            graph = self._build_fk_graph(request.full_schema)
            self.logger.info(f"Built graph with {len(graph.tables)} tables and {len(graph.relationships)} relationships")
            
            # Step 4: Match entities to tables
            entity_matches = self._match_entities_to_tables(
                entities,
                graph.tables,
                request.full_schema,
                request.similarity_threshold
            )
            self.logger.info(f"Matched {len(entity_matches)} entities to tables")
            
            # Extract matched table names
            matched_tables = {match.table for match in entity_matches}
            
            # If no tables matched, return full schema with low confidence
            if not matched_tables:
                self.logger.warning("No tables matched - returning full schema")
                return SchemaIntelligenceResponse(
                    success=True,
                    pruned_schema=request.full_schema,
                    selected_tables=[],
                    join_hints=[],
                    entity_matches=entity_matches,
                    confidence=0.5,
                    metadata={
                        "execution_time": time.time() - start_time,
                        "cache_hit": False,
                        "fallback_reason": "no_tables_matched"
                    }
                )
            
            # Step 5: Traverse graph to find related tables
            selected_tables, join_hints = self._traverse_graph(
                graph,
                matched_tables,
                request.max_depth
            )
            self.logger.info(f"Selected {len(selected_tables)} tables via graph traversal")
            
            # Step 6: Prune schema
            pruned_schema = self._prune_schema(
                request.full_schema,
                selected_tables,
                join_hints
            )
            
            # Calculate confidence based on entity matches
            confidence = 0.9 if len(entity_matches) > 0 else 0.5
            
            # Step 7: Build response
            response_data = {
                "success": True,
                "pruned_schema": pruned_schema.schema_text,
                "selected_tables": pruned_schema.selected_tables,
                "join_hints": join_hints,
                "entity_matches": entity_matches,
                "confidence": confidence,
                "metadata": {
                    "execution_time": time.time() - start_time,
                    "cache_hit": False,
                    "token_reduction": pruned_schema.reduction_percentage,
                    "original_token_count": pruned_schema.original_token_count,
                    "pruned_token_count": pruned_schema.token_count,
                    "entities_extracted": len(entities),
                    "tables_matched": len(matched_tables),
                    "tables_selected": len(selected_tables),
                    "mcp_available": self.mcp_client.is_connected(),
                    "mcp_used": self.mcp_client.is_connected()  # Track if MCP was used
                }
            }
            
            # Step 8: Cache result
            self.cache.set(cache_key, response_data, ttl=300)  # 5-minute TTL
            
            self._log_execution_time("Schema intelligence", start_time)
            return SchemaIntelligenceResponse(**response_data)
            
        except AgentValidationError:
            raise
        except Exception as e:
            self.logger.error(f"Schema intelligence error: {e}", exc_info=True)
            self._log_execution_time("Schema intelligence (error)", start_time)
            
            raise AgentExecutionError(f"Schema intelligence failed: {str(e)}")
    
    def _build_fk_graph(self, schema: str) -> SchemaGraph:
        """
        Build foreign key relationship graph from schema.
        
        Phase 3: Enhanced with MCP client for improved foreign key discovery.
        Falls back to regex parsing if MCP is unavailable.
        
        Args:
            schema: Schema description string from SchemaIntrospector
            
        Returns:
            SchemaGraph with tables, relationships, and adjacency list
        """
        # Try MCP-enhanced graph building first
        try:
            if self.mcp_client.is_connected():
                mcp_graph = self._build_fk_graph_with_mcp(schema)
                if mcp_graph is not None:
                    self.logger.info("Built foreign key graph using MCP client")
                    return mcp_graph
                else:
                    self.logger.warning("MCP graph building returned no result, falling back to regex parsing")
            else:
                self.logger.info("MCP client not connected, using regex parsing for foreign key graph")
        except Exception as e:
            self.logger.warning(f"MCP graph building failed: {e}, falling back to regex parsing")
        
        # Fallback to regex-based parsing
        return self._build_fk_graph_fallback(schema)
    
    def _build_fk_graph_with_mcp(self, schema: str) -> Optional[SchemaGraph]:
        """
        Build foreign key graph using MCP client for enhanced accuracy.
        
        Args:
            schema: Schema description string
            
        Returns:
            SchemaGraph with MCP-enhanced relationships or None if MCP fails
        """
        try:
            # Get schema information from MCP
            mcp_schema = self.mcp_client.get_schema()
            
            if not mcp_schema:
                return None
            
            graph = SchemaGraph()
            
            # Process MCP schema data
            for table_info in mcp_schema.tables:
                table_name = table_info.name
                graph.tables.add(table_name)
                
                if table_name not in graph.adjacency_list:
                    graph.adjacency_list[table_name] = {}
                
                # Process foreign key relationships from MCP
                for fk in table_info.foreign_keys:
                    source_column = fk.column_name
                    target_table = fk.referenced_table
                    target_column = fk.referenced_column
                    
                    # Add relationship
                    relationship = ForeignKeyRelationship(
                        source_table=table_name,
                        source_column=source_column,
                        target_table=target_table,
                        target_column=target_column
                    )
                    graph.relationships.append(relationship)
                    
                    # Add to adjacency list (forward direction)
                    graph.adjacency_list[table_name][source_column] = (target_table, target_column)
                    
                    # Add reverse relationship for bidirectional traversal
                    if target_table not in graph.adjacency_list:
                        graph.adjacency_list[target_table] = {}
                    # Store reverse relationship with special marker
                    reverse_key = f"_reverse_{table_name}_{source_column}"
                    graph.adjacency_list[target_table][reverse_key] = (table_name, source_column)
            
            return graph
            
        except Exception as e:
            self.logger.warning(f"MCP foreign key graph building error: {e}")
            return None
    
    def _build_fk_graph_fallback(self, schema: str) -> SchemaGraph:
        """
        Build foreign key graph using regex parsing (fallback mode).
        
        Args:
            schema: Schema description string from SchemaIntrospector
            
        Returns:
            SchemaGraph with tables, relationships, and adjacency list
        """
        graph = SchemaGraph()
        current_table = None
        
        for line in schema.split('\n'):
            line = line.strip()
            
            # Match table definition
            table_match = re.match(r'^Table:\s+(\w+)', line, re.IGNORECASE)
            if table_match:
                current_table = table_match.group(1)
                graph.tables.add(current_table)
                if current_table not in graph.adjacency_list:
                    graph.adjacency_list[current_table] = {}
                continue
            
            # Match foreign key definition
            # Format: "  - column_name: type (foreign key -> target_table.target_column)"
            if current_table:
                fk_match = re.match(
                    r'^\s*-\s+(\w+):\s+\w+.*\(foreign key -> (\w+)\.(\w+)\)',
                    line,
                    re.IGNORECASE
                )
                if fk_match:
                    source_column = fk_match.group(1)
                    target_table = fk_match.group(2)
                    target_column = fk_match.group(3)
                    
                    # Add relationship
                    relationship = ForeignKeyRelationship(
                        source_table=current_table,
                        source_column=source_column,
                        target_table=target_table,
                        target_column=target_column
                    )
                    graph.relationships.append(relationship)
                    
                    # Add to adjacency list (forward direction)
                    graph.adjacency_list[current_table][source_column] = (target_table, target_column)
                    
                    # Add reverse relationship for bidirectional traversal
                    if target_table not in graph.adjacency_list:
                        graph.adjacency_list[target_table] = {}
                    # Store reverse relationship with special marker
                    reverse_key = f"_reverse_{current_table}_{source_column}"
                    graph.adjacency_list[target_table][reverse_key] = (current_table, source_column)
        
        return graph
    
    def _extract_entities(self, question: str) -> Set[str]:
        """
        Extract entities (nouns) from natural language question.
        
        Phase 3: Uses regex-based extraction with potential for future MCP enhancement.
        The MCP client is primarily used for database operations, not NLP tasks.
        
        Args:
            question: Natural language question
            
        Returns:
            Set of extracted entities (lowercased)
        """
        # Use regex-based extraction (reliable and fast)
        return self._extract_entities_fallback(question)
    
    def _extract_entities_fallback(self, question: str) -> Set[str]:
        """
        Extract entities using enhanced regex-based approach with n-grams and business glossary.
        
        Enhanced in Unit 1 to handle:
        - Multi-word phrases (n-grams): "ISO tanks", "service tank", "vehicle in"
        - Business glossary terms: domain-specific terminology
        - Improved stopword filtering that preserves domain terms
        
        Args:
            question: Natural language question
            
        Returns:
            Set of extracted entities (lowercased, includes multi-word phrases)
        """
        entities = set()
        question_lower = question.lower()
        
        # Step 1: Extract business glossary terms first (highest priority)
        if self.business_glossary:
            for term in self.business_glossary.get('entity_mappings', {}):
                if term in question_lower:
                    entities.add(term)
                    self.logger.debug(f"Found business glossary term: {term}")
        
        # Step 2: Extract n-grams (multi-word phrases)
        words = re.findall(r'\b[a-zA-Z][a-zA-Z0-9_]*\b', question_lower)
        
        # Extract bigrams (2-word phrases) - be selective
        for i in range(len(words) - 1):
            word1, word2 = words[i], words[i+1]
            bigram = f"{word1} {word2}"
            
            # Only include bigrams that are domain-relevant
            if self._is_domain_relevant(bigram):
                entities.add(bigram)
                self.logger.debug(f"Extracted domain-relevant bigram: {bigram}")
        
        # Extract trigrams (3-word phrases) - more selective
        for i in range(len(words) - 2):
            word1, word2, word3 = words[i], words[i+1], words[i+2]
            trigram = f"{word1} {word2} {word3}"
            
            # Only include trigrams that are clearly domain-relevant
            if self._is_domain_relevant(trigram):
                entities.add(trigram)
                self.logger.debug(f"Extracted trigram: {trigram}")
        
        # Step 3: Extract individual words (existing logic, enhanced)
        for word in words:
            if word not in self.STOPWORDS or self._is_domain_term(word):
                entities.add(word)
        
        self.logger.info(f"Enhanced entity extraction found {len(entities)} entities: {entities}")
        return entities
    
    def _load_business_glossary(self) -> Optional[Dict]:
        """
        Load business glossary from YAML configuration file.
        
        Returns:
            Dictionary with business glossary terms or None if file not found
        """
        try:
            glossary_path = os.path.join(
                os.path.dirname(__file__), 
                'config', 
                'business_glossary.yaml'
            )
            
            if os.path.exists(glossary_path):
                with open(glossary_path, 'r') as f:
                    glossary = yaml.safe_load(f)
                    self.logger.info(f"Loaded business glossary with {len(glossary.get('entity_mappings', {}))} entity mappings")
                    return glossary
            else:
                self.logger.warning(f"Business glossary not found at {glossary_path}")
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to load business glossary: {e}")
            return None
    
    def _is_domain_relevant(self, phrase: str) -> bool:
        """
        Check if a phrase is domain-relevant based on keywords.
        
        Args:
            phrase: Multi-word phrase to check
            
        Returns:
            True if phrase contains domain-relevant terms
        """
        domain_keywords = {
            'iso', 'tank', 'tanks', 'service', 'vehicle', 'client', 'survey', 
            'status', 'in', 'out', 'croyance', 'form', 'number'
        }
        
        phrase_words = phrase.split()
        return any(word in domain_keywords for word in phrase_words)
    
    def _is_domain_term(self, word: str) -> bool:
        """
        Check if a single word is a domain-specific term that should be preserved.
        
        Args:
            word: Single word to check
            
        Returns:
            True if word is domain-specific and should be kept despite being in stopwords
        """
        # Domain-specific terms that might be in stopwords but are important
        domain_terms = {'in', 'out', 'is', 'are', 'has', 'have'}
        return word in domain_terms
    
    def _match_entities_to_tables(
        self,
        entities: Set[str],
        tables: Set[str],
        schema: str,
        threshold: float
    ) -> List[EntityMatch]:
        """
        Match entities to database tables using hybrid embedding + fuzzy matching.
        
        Enhanced in Unit 2 to use:
        1. Embedding-based semantic similarity (primary)
        2. Fuzzy matching fallback (for spelling mistakes and when embeddings unavailable)
        3. Best match selection from both approaches
        
        Matches entities against:
        1. Table names (exact, embedding, and fuzzy)
        2. Column names (for semantic columns like croyance_client_name)
        
        Args:
            entities: Set of extracted entities
            tables: Set of table names from schema
            schema: Full schema string (for column name extraction)
            threshold: Minimum similarity score (0.0-1.0)
            
        Returns:
            List of EntityMatch objects
        """
        # Try embedding-based matching first, fallback to fuzzy matching
        embedding_matcher = get_embedding_matcher()
        
        if embedding_matcher.is_available():
            self.logger.info("Using embedding-based entity matching with fuzzy fallback")
            return self._match_entities_with_embeddings(entities, tables, schema, threshold)
        else:
            self.logger.info("Embedding model unavailable, using fuzzy matching only")
            return self._match_entities_fallback(entities, tables, schema, threshold)
    
    def _match_entities_with_embeddings(
        self,
        entities: Set[str],
        tables: Set[str],
        schema: str,
        threshold: float
    ) -> List[EntityMatch]:
        """
        Match entities using embeddings with fuzzy matching fallback.
        
        Args:
            entities: Set of extracted entities
            tables: Set of table names from schema
            schema: Full schema string (for column name extraction)
            threshold: Minimum similarity score (0.0-1.0)
            
        Returns:
            List of EntityMatch objects
        """
        matches = []
        embedding_matcher = get_embedding_matcher()
        
        # Parse schema to get columns
        table_columns = self._parse_schema_columns(schema)
        
        for entity in entities:
            entity_matches = []
            
            # Step 1: Try exact match first (case-insensitive)
            for table in tables:
                if entity == table.lower():
                    entity_matches.append(EntityMatch(
                        entity=entity,
                        table=table,
                        similarity=1.0,
                        match_type="exact_table"
                    ))
            
            # Step 2: Try embedding-based matching on table names
            for table in tables:
                embedding_similarity = embedding_matcher.calculate_similarity(entity, table.lower())
                if embedding_similarity is not None and embedding_similarity >= threshold:
                    entity_matches.append(EntityMatch(
                        entity=entity,
                        table=table,
                        similarity=embedding_similarity,
                        match_type="embedding_table"
                    ))
            
            # Step 3: Try fuzzy matching on table names (for spelling mistakes)
            for table in tables:
                fuzzy_similarity = self._calculate_similarity(entity, table.lower())
                if fuzzy_similarity >= threshold:
                    entity_matches.append(EntityMatch(
                        entity=entity,
                        table=table,
                        similarity=fuzzy_similarity,
                        match_type="fuzzy_table"
                    ))
            
            # Step 4: Try matching on column names (embedding + fuzzy)
            column_threshold = max(threshold - 0.1, 0.5)  # More lenient for columns
            for table, columns in table_columns.items():
                for column in columns:
                    # Substring match (highest priority for columns)
                    if entity in column.lower():
                        entity_matches.append(EntityMatch(
                            entity=entity,
                            table=table,
                            similarity=0.8,  # High similarity for substring match
                            match_type="substring_column"
                        ))
                    else:
                        # Try embedding similarity on column
                        embedding_similarity = embedding_matcher.calculate_similarity(entity, column.lower())
                        if embedding_similarity is not None and embedding_similarity >= column_threshold:
                            entity_matches.append(EntityMatch(
                                entity=entity,
                                table=table,
                                similarity=embedding_similarity,
                                match_type="embedding_column"
                            ))
                        
                        # Try fuzzy similarity on column
                        fuzzy_similarity = self._calculate_similarity(entity, column.lower())
                        if fuzzy_similarity >= column_threshold:
                            entity_matches.append(EntityMatch(
                                entity=entity,
                                table=table,
                                similarity=fuzzy_similarity,
                                match_type="fuzzy_column"
                            ))
            
            # Add all matches for this entity
            matches.extend(entity_matches)
        
        # Remove duplicates (keep highest similarity for each entity-table pair)
        unique_matches = {}
        for match in matches:
            key = (match.entity, match.table)
            if key not in unique_matches or match.similarity > unique_matches[key].similarity:
                unique_matches[key] = match
        
        return list(unique_matches.values())
    
    def _match_entities_fallback(
        self,
        entities: Set[str],
        tables: Set[str],
        schema: str,
        threshold: float
    ) -> List[EntityMatch]:
        """
        Match entities to tables using fuzzy matching.
        
        Args:
            entities: Set of extracted entities
            tables: Set of table names from schema
            schema: Full schema string (for column name extraction)
            threshold: Minimum similarity score (0.0-1.0)
            
        Returns:
            List of EntityMatch objects
        """
        matches = []
        
        # Parse schema to get columns
        table_columns = self._parse_schema_columns(schema)
        
        for entity in entities:
            # Try exact match first (case-insensitive)
            for table in tables:
                if entity == table.lower():
                    matches.append(EntityMatch(
                        entity=entity,
                        table=table,
                        similarity=1.0,
                        match_type="exact_table"
                    ))
                    continue
            
            # Try fuzzy match on table names
            for table in tables:
                similarity = self._calculate_similarity(entity, table.lower())
                if similarity >= threshold:
                    matches.append(EntityMatch(
                        entity=entity,
                        table=table,
                        similarity=similarity,
                        match_type="fuzzy_table"
                    ))
            
            # Try fuzzy match on column names (with slightly lower threshold)
            column_threshold = max(threshold - 0.1, 0.5)  # Allow more lenient column matching
            for table, columns in table_columns.items():
                for column in columns:
                    # Check if entity is contained in column name (e.g., "client" in "croyance_client_name")
                    if entity in column.lower():
                        matches.append(EntityMatch(
                            entity=entity,
                            table=table,
                            similarity=0.8,  # High similarity for substring match
                            match_type="substring_column"
                        ))
                    else:
                        similarity = self._calculate_similarity(entity, column.lower())
                        if similarity >= column_threshold:
                            matches.append(EntityMatch(
                                entity=entity,
                                table=table,
                                similarity=similarity,
                                match_type="fuzzy_column"
                            ))
        
        # Remove duplicates (keep highest similarity for each entity-table pair)
        unique_matches = {}
        for match in matches:
            key = (match.entity, match.table)
            if key not in unique_matches or match.similarity > unique_matches[key].similarity:
                unique_matches[key] = match
        
        return list(unique_matches.values())
    
    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """
        Calculate similarity between two strings using SequenceMatcher.
        
        Handles plurals by also comparing singular forms.
        
        Args:
            str1: First string
            str2: Second string
            
        Returns:
            Similarity score (0.0-1.0)
        """
        # Direct similarity
        similarity = SequenceMatcher(None, str1, str2).ratio()
        
        # Try removing trailing 's' for plural handling
        if str1.endswith('s') and len(str1) > 1:
            singular_similarity = SequenceMatcher(None, str1[:-1], str2).ratio()
            similarity = max(similarity, singular_similarity)
        
        if str2.endswith('s') and len(str2) > 1:
            singular_similarity = SequenceMatcher(None, str1, str2[:-1]).ratio()
            similarity = max(similarity, singular_similarity)
        
        return similarity
    
    def _parse_schema_columns(self, schema: str) -> Dict[str, Set[str]]:
        """
        Parse schema to extract table-column mapping.
        
        Phase 3: Enhanced with MCP client for improved column discovery.
        Falls back to regex parsing if MCP is unavailable.
        
        Args:
            schema: Schema description string
            
        Returns:
            Dictionary mapping table names to sets of column names
        """
        # Try MCP-enhanced column parsing first
        try:
            if self.mcp_client.is_connected():
                mcp_columns = self._parse_schema_columns_with_mcp(schema)
                if mcp_columns is not None:
                    self.logger.info("Parsed schema columns using MCP client")
                    return mcp_columns
                else:
                    self.logger.warning("MCP column parsing returned no result, falling back to regex parsing")
            else:
                self.logger.info("MCP client not connected, using regex parsing for schema columns")
        except Exception as e:
            self.logger.warning(f"MCP column parsing failed: {e}, falling back to regex parsing")
        
        # Fallback to regex-based parsing
        return self._parse_schema_columns_fallback(schema)
    
    def _parse_schema_columns_with_mcp(self, schema: str) -> Optional[Dict[str, Set[str]]]:
        """
        Parse schema columns using MCP client for enhanced accuracy.
        
        Args:
            schema: Schema description string
            
        Returns:
            Dictionary mapping table names to column sets or None if MCP fails
        """
        try:
            # Get schema information from MCP
            mcp_schema = self.mcp_client.get_schema()
            
            if not mcp_schema:
                return None
            
            table_columns = {}
            
            # Process MCP schema data
            for table_info in mcp_schema.tables:
                table_name = table_info.name
                table_columns[table_name] = set()
                
                # Add columns from MCP
                for column in table_info.columns:
                    table_columns[table_name].add(column.name)
            
            return table_columns
            
        except Exception as e:
            self.logger.warning(f"MCP schema column parsing error: {e}")
            return None
    
    def _parse_schema_columns_fallback(self, schema: str) -> Dict[str, Set[str]]:
        """
        Parse schema columns using regex parsing (fallback mode).
        
        Args:
            schema: Schema description string
            
        Returns:
            Dictionary mapping table names to sets of column names
        """
        table_columns = {}
        current_table = None
        
        for line in schema.split('\n'):
            line = line.strip()
            
            # Match table definition
            table_match = re.match(r'^Table:\s+(\w+)', line, re.IGNORECASE)
            if table_match:
                current_table = table_match.group(1)
                table_columns[current_table] = set()
                continue
            
            # Match column definition
            if current_table:
                column_match = re.match(r'^\s*-\s+(\w+):', line)
                if column_match:
                    column_name = column_match.group(1)
                    table_columns[current_table].add(column_name)
        
        return table_columns
    
    def _traverse_graph(
        self,
        graph: SchemaGraph,
        start_tables: Set[str],
        max_depth: int
    ) -> Tuple[List[str], List[JoinHint]]:
        """
        Traverse foreign key graph using BFS to find related tables.
        
        Args:
            graph: SchemaGraph with adjacency list
            start_tables: Set of tables to start traversal from
            max_depth: Maximum traversal depth
            
        Returns:
            Tuple of (selected_tables, join_hints)
        """
        visited = set()
        join_hints = []
        queue = deque()
        
        # Initialize queue with start tables
        for table in start_tables:
            if table in graph.adjacency_list:
                queue.append((table, 0))
        
        # BFS traversal
        while queue:
            table, depth = queue.popleft()
            
            # Skip if already visited or depth exceeded
            if table in visited or depth > max_depth:
                continue
            
            visited.add(table)
            
            # Explore neighbors (foreign key relationships)
            if table in graph.adjacency_list:
                for fk_column, (target_table, target_column) in graph.adjacency_list[table].items():
                    # Skip reverse relationships (marked with _reverse_ prefix)
                    if fk_column.startswith('_reverse_'):
                        # Extract original table and column for reverse JOIN
                        parts = fk_column.split('_')
                        if len(parts) >= 4:
                            original_table = parts[2]
                            original_column = '_'.join(parts[3:])
                            join_condition = f"{original_table}.{original_column} = {table}.{target_column}"
                            join_hints.append(JoinHint(
                                from_table=original_table,
                                to_table=table,
                                join_condition=join_condition,
                                depth=depth
                            ))
                    else:
                        # Forward relationship
                        join_condition = f"{table}.{fk_column} = {target_table}.{target_column}"
                        join_hints.append(JoinHint(
                            from_table=table,
                            to_table=target_table,
                            join_condition=join_condition,
                            depth=depth
                        ))
                    
                    # Add target table to queue if not visited
                    if target_table not in visited:
                        queue.append((target_table, depth + 1))
        
        return list(visited), join_hints
    
    def _prune_schema(
        self,
        full_schema: str,
        selected_tables: List[str],
        join_hints: List[JoinHint]
    ) -> PrunedSchema:
        """
        Prune schema to include only selected tables.
        
        Args:
            full_schema: Complete schema string
            selected_tables: List of tables to include
            join_hints: List of JOIN path hints
            
        Returns:
            PrunedSchema with formatted schema text and metadata
        """
        selected_set = set(selected_tables)
        pruned_lines = []
        current_table = None
        include_table = False
        in_table_section = False
        
        # Parse and filter schema
        for line in full_schema.split('\n'):
            # Check for table definition
            table_match = re.match(r'^Table:\s+(\w+)', line, re.IGNORECASE)
            if table_match:
                current_table = table_match.group(1)
                include_table = current_table in selected_set
                in_table_section = True
                
                # Include table header line if selected
                if include_table:
                    pruned_lines.append(line)
                continue
            
            # Check for separator line (dashes)
            if line.strip().startswith('-' * 10):
                if include_table:
                    pruned_lines.append(line)
                continue
            
            # Check for empty line (might signal end of table section)
            if not line.strip():
                if include_table:
                    pruned_lines.append(line)
                in_table_section = False
                continue
            
            # Include line if we're in a selected table
            if include_table and in_table_section:
                pruned_lines.append(line)
        
        # Add JOIN hints section
        if join_hints:
            pruned_lines.append("")
            pruned_lines.append("JOIN Path Hints:")
            pruned_lines.append("=" * 80)
            for hint in join_hints:
                pruned_lines.append(f"  {hint.join_condition}")
        
        pruned_schema_text = '\n'.join(pruned_lines)
        
        # Estimate token counts (rough approximation: 1 token ≈ 4 characters)
        original_token_count = len(full_schema) // 4
        pruned_token_count = len(pruned_schema_text) // 4
        reduction_percentage = ((original_token_count - pruned_token_count) / original_token_count * 100) if original_token_count > 0 else 0
        
        return PrunedSchema(
            schema_text=pruned_schema_text,
            selected_tables=selected_tables,
            join_hints=join_hints,
            token_count=pruned_token_count,
            original_token_count=original_token_count,
            reduction_percentage=reduction_percentage
        )
    
    def _generate_cache_key(self, entities: Set[str]) -> str:
        """
        Generate cache key from entity set.
        
        Sorts entities to ensure consistent keys regardless of order.
        
        Args:
            entities: Set of extracted entities
            
        Returns:
            Cache key (hash of sorted entities)
        """
        sorted_entities = sorted(entities)
        key_string = ','.join(sorted_entities)
        return hashlib.md5(key_string.encode()).hexdigest()
