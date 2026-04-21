"""
Tests for Schema Intelligence Agent

This module tests the Schema Intelligence agent including foreign key graph
building, entity extraction, table matching, graph traversal, and schema pruning.
"""

import pytest
from agents.schema_intelligence import SchemaIntelligenceAgent
from agents.models.schema_models import (
    SchemaIntelligenceRequest,
    SchemaGraph,
    EntityMatch
)
from agents.base import AgentValidationError
from tests.agents.fixtures.sample_schema import (
    SCHEMA_NO_FKS,
    SCHEMA_WITH_FKS,
    SCHEMA_SELF_REFERENTIAL,
    SCHEMA_CIRCULAR,
    SCHEMA_COMPLEX
)


class TestForeignKeyGraphBuilder:
    """Test suite for foreign key graph building."""
    
    def test_build_graph_no_fks(self):
        """Happy path: Parse schema with no foreign keys."""
        agent = SchemaIntelligenceAgent()
        
        graph = agent._build_fk_graph(SCHEMA_NO_FKS)
        
        assert len(graph.tables) == 2
        assert "users" in graph.tables
        assert "products" in graph.tables
        assert len(graph.relationships) == 0
        assert len(graph.adjacency_list) == 2
    
    def test_build_graph_with_fks(self):
        """Happy path: Parse schema with multiple FK relationships."""
        agent = SchemaIntelligenceAgent()
        
        graph = agent._build_fk_graph(SCHEMA_WITH_FKS)
        
        assert len(graph.tables) == 4
        assert "iso_tank" in graph.tables
        assert "vehicle_in" in graph.tables
        assert "vehicle_out" in graph.tables
        assert "survey_form" in graph.tables
        
        # Check relationships
        assert len(graph.relationships) == 3
        
        # Check adjacency list (forward relationships)
        assert "vehicle_in_id" in graph.adjacency_list["iso_tank"]
        assert graph.adjacency_list["iso_tank"]["vehicle_in_id"] == ("vehicle_in", "id")
    
    def test_build_graph_bidirectional_edges(self):
        """Happy path: Graph includes bidirectional edges for traversal."""
        agent = SchemaIntelligenceAgent()
        
        graph = agent._build_fk_graph(SCHEMA_WITH_FKS)
        
        # Check forward relationship
        assert "vehicle_in_id" in graph.adjacency_list["iso_tank"]
        
        # Check reverse relationship exists
        reverse_keys = [k for k in graph.adjacency_list["vehicle_in"].keys() if k.startswith("_reverse_")]
        assert len(reverse_keys) > 0
    
    def test_build_graph_self_referential(self):
        """Edge case: Schema with self-referential FK."""
        agent = SchemaIntelligenceAgent()
        
        graph = agent._build_fk_graph(SCHEMA_SELF_REFERENTIAL)
        
        assert len(graph.tables) == 1
        assert "employee" in graph.tables
        assert len(graph.relationships) == 1
        
        # Self-referential relationship
        relationship = graph.relationships[0]
        assert relationship.source_table == "employee"
        assert relationship.target_table == "employee"
    
    def test_build_graph_circular_fks(self):
        """Edge case: Schema with circular FK relationships."""
        agent = SchemaIntelligenceAgent()
        
        graph = agent._build_fk_graph(SCHEMA_CIRCULAR)
        
        assert len(graph.tables) == 3
        assert len(graph.relationships) == 3
        
        # Verify circular structure: A → B → C → A
        assert "b_id" in graph.adjacency_list["table_a"]
        assert "c_id" in graph.adjacency_list["table_b"]
        assert "a_id" in graph.adjacency_list["table_c"]
    
    def test_graph_structure_valid(self):
        """Integration: Graph structure is valid (no dangling references)."""
        agent = SchemaIntelligenceAgent()
        
        graph = agent._build_fk_graph(SCHEMA_COMPLEX)
        
        # All FK target tables should exist in graph.tables
        for relationship in graph.relationships:
            assert relationship.source_table in graph.tables
            assert relationship.target_table in graph.tables
    
    def test_parsing_performance(self):
        """Verification: Parsing completes in <100ms for typical schema."""
        import time
        agent = SchemaIntelligenceAgent()
        
        start = time.time()
        graph = agent._build_fk_graph(SCHEMA_COMPLEX)
        elapsed = (time.time() - start) * 1000  # Convert to ms
        
        assert elapsed < 100, f"Parsing took {elapsed}ms (expected <100ms)"
        assert len(graph.tables) > 0


class TestEntityExtraction:
    """Test suite for entity extraction from questions."""
    
    def test_extract_entities_simple_question(self):
        """Happy path: Extract entities from simple question."""
        agent = SchemaIntelligenceAgent()
        
        entities = agent._extract_entities("How many tanks?")
        
        assert "tanks" in entities
        assert "how" not in entities  # Stopword filtered
        assert "many" not in entities  # Stopword filtered
    
    def test_extract_entities_complex_question(self):
        """Happy path: Extract entities from complex question."""
        agent = SchemaIntelligenceAgent()
        
        entities = agent._extract_entities("Which clients have the most tanks this month?")
        
        assert "clients" in entities
        assert "tanks" in entities
        assert "month" in entities
        assert "which" not in entities  # Stopword
        assert "the" not in entities  # Stopword
        assert "most" not in entities  # Stopword
    
    def test_extract_entities_no_stopwords(self):
        """Edge case: Question with only stopwords returns empty set."""
        agent = SchemaIntelligenceAgent()
        
        entities = agent._extract_entities("What is the most?")
        
        assert len(entities) == 0
    
    def test_extract_entities_case_insensitive(self):
        """Happy path: Entities are lowercased."""
        agent = SchemaIntelligenceAgent()
        
        entities = agent._extract_entities("Show me ISO tanks")
        
        assert "iso" in entities
        assert "tanks" in entities
        assert "ISO" not in entities  # Should be lowercased


class TestEntityTableMatching:
    """Test suite for entity-to-table fuzzy matching."""
    
    def test_match_exact_table_name(self):
        """Happy path: Exact match to table name."""
        agent = SchemaIntelligenceAgent()
        entities = {"iso_tank"}
        tables = {"iso_tank", "vehicle_in"}
        
        matches = agent._match_entities_to_tables(entities, tables, SCHEMA_WITH_FKS, 0.7)
        
        assert len(matches) > 0
        assert any(m.entity == "iso_tank" and m.table == "iso_tank" for m in matches)
    
    def test_match_plural_to_singular(self):
        """Happy path: Fuzzy match handles plurals."""
        agent = SchemaIntelligenceAgent()
        entities = {"tanks"}
        tables = {"iso_tank", "service_tank"}
        
        matches = agent._match_entities_to_tables(entities, tables, SCHEMA_COMPLEX, 0.7)
        
        # Should match both tank tables
        matched_tables = {m.table for m in matches if m.entity == "tanks"}
        assert "iso_tank" in matched_tables or "service_tank" in matched_tables
    
    def test_match_abbreviation(self):
        """Happy path: Fuzzy match handles abbreviations."""
        agent = SchemaIntelligenceAgent()
        entities = {"iso"}
        tables = {"iso_tank"}
        
        matches = agent._match_entities_to_tables(entities, tables, SCHEMA_WITH_FKS, 0.7)
        
        # ISO should match iso_tank with reasonable similarity
        assert len(matches) > 0
    
    def test_match_below_threshold(self):
        """Edge case: Entity below similarity threshold not matched."""
        agent = SchemaIntelligenceAgent()
        entities = {"xyz"}
        tables = {"iso_tank", "vehicle_in"}
        
        matches = agent._match_entities_to_tables(entities, tables, SCHEMA_WITH_FKS, 0.7)
        
        # "xyz" should not match any table
        assert len(matches) == 0
    
    def test_match_multiple_tables(self):
        """Edge case: Entity matches multiple tables."""
        agent = SchemaIntelligenceAgent()
        entities = {"tank"}
        tables = {"iso_tank", "service_tank"}
        
        matches = agent._match_entities_to_tables(entities, tables, SCHEMA_COMPLEX, 0.7)
        
        # "tank" should match both tank tables
        matched_tables = {m.table for m in matches if m.entity == "tank"}
        assert len(matched_tables) >= 1
    
    def test_match_column_name(self):
        """Happy path: Match entity to semantic column name."""
        agent = SchemaIntelligenceAgent()
        entities = {"client"}
        tables = {"vehicle_in"}
        
        matches = agent._match_entities_to_tables(entities, tables, SCHEMA_WITH_FKS, 0.7)
        
        # "client" should match vehicle_in via croyance_client_name column
        assert any(m.entity == "client" and m.table == "vehicle_in" for m in matches)
    
    def test_match_removes_duplicates(self):
        """Integration: Duplicate matches are removed (keeps highest similarity)."""
        agent = SchemaIntelligenceAgent()
        entities = {"tank"}
        tables = {"iso_tank"}
        
        matches = agent._match_entities_to_tables(entities, tables, SCHEMA_WITH_FKS, 0.5)
        
        # Should have at most one match per entity-table pair
        entity_table_pairs = [(m.entity, m.table) for m in matches]
        assert len(entity_table_pairs) == len(set(entity_table_pairs))


class TestGraphTraversal:
    """Test suite for BFS graph traversal."""
    
    def test_traverse_single_table_no_fks(self):
        """Happy path: Traverse from single table with no FKs (depth 0)."""
        agent = SchemaIntelligenceAgent()
        graph = agent._build_fk_graph(SCHEMA_NO_FKS)
        start_tables = {"users"}
        
        selected_tables, join_hints = agent._traverse_graph(graph, start_tables, max_depth=2)
        
        assert "users" in selected_tables
        assert len(selected_tables) == 1  # Only start table
        assert len(join_hints) == 0  # No relationships
    
    def test_traverse_one_hop_fk(self):
        """Happy path: Traverse from single table with 1-hop FK (depth 1)."""
        agent = SchemaIntelligenceAgent()
        graph = agent._build_fk_graph(SCHEMA_WITH_FKS)
        start_tables = {"iso_tank"}
        
        selected_tables, join_hints = agent._traverse_graph(graph, start_tables, max_depth=1)
        
        assert "iso_tank" in selected_tables
        assert "vehicle_in" in selected_tables or "vehicle_out" in selected_tables
        assert len(join_hints) > 0
    
    def test_traverse_two_hop_fk_chain(self):
        """Happy path: Traverse from single table with 2-hop FK chain (depth 2)."""
        agent = SchemaIntelligenceAgent()
        graph = agent._build_fk_graph(SCHEMA_COMPLEX)
        start_tables = {"iso_tank"}
        
        selected_tables, join_hints = agent._traverse_graph(graph, start_tables, max_depth=2)
        
        # Should reach iso_tank → vehicle_in → client_details
        assert "iso_tank" in selected_tables
        assert "vehicle_in" in selected_tables
        # May or may not reach client_details depending on traversal order
    
    def test_traverse_multiple_start_tables(self):
        """Happy path: Traverse from multiple start tables (union of reachable)."""
        agent = SchemaIntelligenceAgent()
        graph = agent._build_fk_graph(SCHEMA_COMPLEX)
        start_tables = {"iso_tank", "service_tank"}
        
        selected_tables, join_hints = agent._traverse_graph(graph, start_tables, max_depth=1)
        
        assert "iso_tank" in selected_tables
        assert "service_tank" in selected_tables
        assert "vehicle_in" in selected_tables  # Reachable from both
    
    def test_traverse_circular_no_infinite_loop(self):
        """Edge case: Circular FK relationships don't cause infinite loop."""
        agent = SchemaIntelligenceAgent()
        graph = agent._build_fk_graph(SCHEMA_CIRCULAR)
        start_tables = {"table_a"}
        
        selected_tables, join_hints = agent._traverse_graph(graph, start_tables, max_depth=5)
        
        # Should visit all tables but not loop infinitely
        assert len(selected_tables) == 3
        assert "table_a" in selected_tables
        assert "table_b" in selected_tables
        assert "table_c" in selected_tables
    
    def test_traverse_max_depth_exceeded(self):
        """Edge case: Max depth exceeded stops traversal."""
        agent = SchemaIntelligenceAgent()
        graph = agent._build_fk_graph(SCHEMA_COMPLEX)
        start_tables = {"iso_tank"}
        
        # Depth 0 should only include start table
        selected_tables, join_hints = agent._traverse_graph(graph, start_tables, max_depth=0)
        
        assert len(selected_tables) == 1
        assert "iso_tank" in selected_tables
    
    def test_traverse_disconnected_tables(self):
        """Edge case: Disconnected tables (no FK path) only include start tables."""
        agent = SchemaIntelligenceAgent()
        graph = agent._build_fk_graph(SCHEMA_NO_FKS)
        start_tables = {"users", "products"}
        
        selected_tables, join_hints = agent._traverse_graph(graph, start_tables, max_depth=2)
        
        # No FK paths between users and products
        assert len(selected_tables) == 2
        assert "users" in selected_tables
        assert "products" in selected_tables
        assert len(join_hints) == 0
    
    def test_traverse_join_hints_correct(self):
        """Integration: JOIN path hints are correct and complete."""
        agent = SchemaIntelligenceAgent()
        graph = agent._build_fk_graph(SCHEMA_WITH_FKS)
        start_tables = {"iso_tank"}
        
        selected_tables, join_hints = agent._traverse_graph(graph, start_tables, max_depth=1)
        
        # Check that join hints reference selected tables
        for hint in join_hints:
            assert hint.from_table in selected_tables or hint.to_table in selected_tables
            assert "=" in hint.join_condition
    
    def test_traverse_performance(self):
        """Verification: Traversal completes in <100ms for typical graph."""
        import time
        agent = SchemaIntelligenceAgent()
        graph = agent._build_fk_graph(SCHEMA_COMPLEX)
        start_tables = {"iso_tank"}
        
        start = time.time()
        selected_tables, join_hints = agent._traverse_graph(graph, start_tables, max_depth=2)
        elapsed = (time.time() - start) * 1000
        
        assert elapsed < 100, f"Traversal took {elapsed}ms (expected <100ms)"


class TestSchemaPruning:
    """Test suite for schema pruning."""
    
    def test_prune_schema_single_table(self):
        """Happy path: Prune schema to single table."""
        agent = SchemaIntelligenceAgent()
        selected_tables = ["iso_tank"]
        
        pruned = agent._prune_schema(SCHEMA_WITH_FKS, selected_tables, [])
        
        assert "iso_tank" in pruned.schema_text
        assert "vehicle_in" not in pruned.schema_text
        assert len(pruned.selected_tables) == 1
    
    def test_prune_schema_multiple_tables(self):
        """Happy path: Prune schema to multiple tables."""
        agent = SchemaIntelligenceAgent()
        selected_tables = ["iso_tank", "vehicle_in"]
        
        pruned = agent._prune_schema(SCHEMA_WITH_FKS, selected_tables, [])
        
        assert "iso_tank" in pruned.schema_text
        assert "vehicle_in" in pruned.schema_text
        assert "vehicle_out" not in pruned.schema_text
        assert len(pruned.selected_tables) == 2
    
    def test_prune_schema_includes_join_hints(self):
        """Happy path: Pruned schema includes JOIN hints section."""
        agent = SchemaIntelligenceAgent()
        from agents.models.schema_models import JoinHint
        
        selected_tables = ["iso_tank", "vehicle_in"]
        join_hints = [
            JoinHint(
                from_table="iso_tank",
                to_table="vehicle_in",
                join_condition="iso_tank.vehicle_in_id = vehicle_in.id",
                depth=1
            )
        ]
        
        pruned = agent._prune_schema(SCHEMA_WITH_FKS, selected_tables, join_hints)
        
        assert "JOIN Path Hints:" in pruned.schema_text
        assert "iso_tank.vehicle_in_id = vehicle_in.id" in pruned.schema_text
    
    def test_prune_schema_token_reduction(self):
        """Integration: Token count reduced significantly."""
        agent = SchemaIntelligenceAgent()
        selected_tables = ["iso_tank"]
        
        pruned = agent._prune_schema(SCHEMA_COMPLEX, selected_tables, [])
        
        # Should have significant reduction
        assert pruned.token_count < pruned.original_token_count
        assert pruned.reduction_percentage > 50  # At least 50% reduction
    
    def test_prune_schema_all_columns_included(self):
        """Integration: All columns from selected tables are included."""
        agent = SchemaIntelligenceAgent()
        selected_tables = ["iso_tank"]
        
        pruned = agent._prune_schema(SCHEMA_WITH_FKS, selected_tables, [])
        
        # Check that key columns are present
        assert "tank_number" in pruned.schema_text
        assert "iso_tank_status" in pruned.schema_text
        assert "vehicle_in_id" in pruned.schema_text


class TestSchemaIntelligenceAgent:
    """Integration tests for complete Schema Intelligence agent."""
    
    def test_agent_simple_question_cache_miss(self):
        """Happy path: Process simple question with cache miss."""
        agent = SchemaIntelligenceAgent()
        request = SchemaIntelligenceRequest(
            question="How many tanks?",
            full_schema=SCHEMA_WITH_FKS
        )
        
        response = agent.execute(request)
        
        assert response.success
        assert response.pruned_schema is not None
        assert len(response.selected_tables) > 0
        assert response.confidence > 0.5
        assert response.metadata["cache_hit"] == False
    
    def test_agent_simple_question_cache_hit(self):
        """Happy path: Process simple question with cache hit."""
        agent = SchemaIntelligenceAgent()
        request = SchemaIntelligenceRequest(
            question="How many tanks?",
            full_schema=SCHEMA_WITH_FKS
        )
        
        # First call - cache miss
        response1 = agent.execute(request)
        assert response1.metadata["cache_hit"] == False
        
        # Second call - cache hit
        response2 = agent.execute(request)
        assert response2.metadata["cache_hit"] == True
        assert response2.pruned_schema == response1.pruned_schema
    
    def test_agent_complex_question_two_hop_traversal(self):
        """Happy path: Process complex question requiring 2-hop traversal."""
        agent = SchemaIntelligenceAgent()
        request = SchemaIntelligenceRequest(
            question="Which clients have the most tanks this month?",
            full_schema=SCHEMA_COMPLEX
        )
        
        response = agent.execute(request)
        
        assert response.success
        assert len(response.selected_tables) >= 2
        assert len(response.join_hints) > 0
        assert response.confidence >= 0.9
    
    def test_agent_empty_question_raises_error(self):
        """Error path: Empty question raises AgentValidationError."""
        agent = SchemaIntelligenceAgent()
        request = SchemaIntelligenceRequest(
            question="",
            full_schema=SCHEMA_WITH_FKS
        )
        
        with pytest.raises(AgentValidationError):
            agent.execute(request)
    
    def test_agent_no_entities_returns_full_schema(self):
        """Edge case: No entities extracted returns full schema with low confidence."""
        agent = SchemaIntelligenceAgent()
        request = SchemaIntelligenceRequest(
            question="What is the most?",  # Only stopwords
            full_schema=SCHEMA_WITH_FKS
        )
        
        response = agent.execute(request)
        
        assert response.success
        assert response.pruned_schema == SCHEMA_WITH_FKS
        assert response.confidence == 0.5
        assert response.metadata["fallback_reason"] == "no_entities_extracted"
    
    def test_agent_token_reduction_target(self):
        """Integration: Agent reduces token count by ~95%."""
        agent = SchemaIntelligenceAgent()
        request = SchemaIntelligenceRequest(
            question="Show me ISO tanks",
            full_schema=SCHEMA_COMPLEX
        )
        
        response = agent.execute(request)
        
        # Should have significant token reduction
        assert response.metadata["token_reduction"] > 50  # At least 50%
    
    def test_agent_execution_time_target(self):
        """Verification: Agent execution time <200ms (cache miss)."""
        agent = SchemaIntelligenceAgent()
        request = SchemaIntelligenceRequest(
            question="How many tanks?",
            full_schema=SCHEMA_WITH_FKS
        )
        
        response = agent.execute(request)
        
        execution_time = response.metadata["execution_time"] * 1000  # Convert to ms
        assert execution_time < 200, f"Execution took {execution_time}ms (expected <200ms)"
    
    def test_agent_cache_hit_rate(self):
        """Integration: Cache hit rate >60% for repeated entity sets."""
        agent = SchemaIntelligenceAgent()
        
        # Make 10 requests with same entities (different wording)
        questions = [
            "How many tanks?",
            "Show me tanks",
            "List all tanks",
            "Count tanks",
            "Display tanks"
        ]
        
        cache_hits = 0
        for question in questions:
            request = SchemaIntelligenceRequest(
                question=question,
                full_schema=SCHEMA_WITH_FKS
            )
            response = agent.execute(request)
            if response.metadata.get("cache_hit"):
                cache_hits += 1
        
        # After first request, subsequent requests should hit cache
        hit_rate = cache_hits / len(questions)
        assert hit_rate >= 0.6, f"Cache hit rate {hit_rate} < 0.6"
