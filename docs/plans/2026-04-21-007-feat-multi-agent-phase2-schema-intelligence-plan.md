---
title: "feat: Multi-Agent Text-to-SQL Phase 2 - Schema Intelligence"
type: feat
status: active
date: 2026-04-21
origin: docs/brainstorms/multi-agent-text-to-sql-requirements.md
---

# Multi-Agent Text-to-SQL Phase 2 - Schema Intelligence

## Overview

Add intelligent schema pruning to reduce token usage by 95% and enable complex multi-table queries. The Schema Intelligence agent extracts entities from questions, traverses foreign key relationships via graph search, and prunes the full schema (~8,000 tokens) down to only relevant tables and columns (~300 tokens). This dramatically improves SQL Generation accuracy for complex JOINs while reducing cost and latency.

## Problem Frame

Phase 1's SQL Generation agent receives the full database schema (~8,000 tokens) for every query, which:
- Wastes 95% of the context window on irrelevant tables
- Increases token cost 10x unnecessarily
- Confuses the AI with too many similar table/column names
- Limits ability to handle complex multi-table queries (current success rate ~40%)

Phase 2 solves this by intelligently selecting only the 2-4 tables and ~20 columns actually needed for each query.

(see origin: docs/brainstorms/multi-agent-text-to-sql-requirements.md)

## Requirements Trace

- R1. Schema token count reduced from ~8,000 to ~300 (95% reduction)
- R2. Complex multi-table JOIN queries succeed ≥80% (up from ~40%)
- R3. Schema pruning results cached with 60% hit rate (5-minute TTL)
- R4. Entity extraction identifies relevant tables from natural language
- R5. Graph traversal discovers JOIN paths via foreign key relationships
- R6. Orchestrator routes queries through Schema Intelligence before SQL Generation

## Scope Boundaries

**In scope for Phase 2:**
- Schema Intelligence agent with entity extraction and graph traversal
- In-memory cache implementation with TTL and LRU eviction
- Foreign key relationship graph builder
- Entity-to-table mapping using semantic similarity
- Integration with Orchestrator (new routing logic)
- Unit and integration tests

**Explicit non-goals:**
- Query Refinement agent (Phase 3)
- Security & Governance agent (Phase 3)
- Result Formatter agent (Phase 4)
- Business glossary (Phase 3 - Query Refinement will use it)
- Redis or external cache (using in-memory cache for simplicity)
- LangGraph integration (still using simple Python orchestration)

### Deferred to Separate Tasks

- Query refinement and business terminology mapping: Phase 3
- Security policies and PII detection: Phase 3
- Natural language result formatting: Phase 4
- Cache persistence across restarts: Future optimization (if needed)

## Context & Research

### Relevant Code and Patterns

**Existing schema infrastructure:**
- `services/schema.py` - SchemaIntrospector with foreign key discovery already implemented
- `services/schema.py` provides `get_database_schema()` returning formatted string with FK relationships
- Foreign key format: `column_name: type (foreign key -> table.column)`

**Phase 1 agent patterns:**
- `agents/base.py` - Base agent class with execute() method and logging
- `agents/orchestrator.py` - Simple routing with extensibility placeholders
- `agents/models/agent_models.py` - Pydantic models for agent communication
- `agents/cache.py` - CacheProtocol abstract interface (NoOpCache stub)

**Testing patterns:**
- `tests/agents/test_sql_generation.py` - Mock-based unit tests with validation scenarios
- `tests/test_schema.py` - Schema introspection tests with real database

**Key patterns to follow:**
- Agent inheritance from BaseAgent with structured Pydantic inputs/outputs
- Logging with timing and structured metadata
- Exception hierarchy (AgentError → AgentExecutionError, AgentValidationError)
- Test isolation with mocks for external dependencies

### Institutional Learnings

None found in `docs/solutions/` - this is the first schema intelligence implementation.

### External References

**Research papers informing design:**
- CHESS: Contextual Harnessing for Efficient SQL Synthesis (Talaei et al., ICML 2025) - schema pruning via entity extraction
- MAC-SQL: Multi-Agent Collaboration for Text-to-SQL (Wang et al., COLING 2025) - graph-based schema selection
- AgentiQL: Agent-Inspired Multi-Expert Framework (arXiv 2510.10661v2) - semantic entity mapping

**Algorithm references:**
- Breadth-First Search (BFS) for graph traversal with max depth limit
- Levenshtein distance for fuzzy entity-to-table matching
- LRU cache eviction policy (Python functools.lru_cache patterns)

## Key Technical Decisions

**Decision: Use in-memory cache with TTL instead of Redis**
- Rationale: Simpler deployment (no new infrastructure), sufficient for Phase 2 scale (single-instance service). Schema changes are infrequent (5-minute TTL is safe). Can upgrade to Redis in future if multi-instance deployment needed.

**Decision: Build foreign key graph from existing SchemaIntrospector output**
- Rationale: `services/schema.py` already extracts FK relationships from PostgreSQL metadata. No need to duplicate this logic. Parse the formatted string to build graph structure.

**Decision: Use semantic similarity (fuzzy matching) for entity-to-table mapping**
- Rationale: Users say "clients" but table is "vehicle_in" (croyance_client_name column). Simple exact matching fails. Fuzzy matching with Levenshtein distance handles plurals, abbreviations, and synonyms.

**Decision: BFS graph traversal with max_depth=2**
- Rationale: Most queries need 1-2 JOINs. Depth 2 covers 95% of cases (e.g., iso_tank → vehicle_in → client_details). Deeper traversal adds noise without benefit. Configurable for future tuning.

**Decision: Cache key = hash(sorted(entity_set))**
- Rationale: Same entities in different order should hit cache (e.g., ["tanks", "clients"] == ["clients", "tanks"]). Sorting ensures consistent cache keys. Hash provides compact key representation.

**Decision: Integrate Schema Intelligence into Orchestrator routing**
- Rationale: Orchestrator already has routing logic. Add Schema Intelligence as pre-processing step before SQL Generation. Keeps orchestration centralized and maintains single entry point.

## Open Questions

### Resolved During Planning

**Q: Should we use external cache (Redis) or in-memory cache?**
- Resolution: In-memory cache for Phase 2. Simpler deployment, sufficient for current scale. Upgrade to Redis if multi-instance deployment needed.

**Q: How to handle entity extraction - rule-based or ML-based?**
- Resolution: Rule-based with fuzzy matching for Phase 2. Extract nouns from question, match against table/column names using Levenshtein distance. ML-based NER deferred to future optimization if needed.

**Q: What cache TTL and eviction policy?**
- Resolution: 5-minute TTL (schema changes are infrequent), LRU eviction with max 1000 entries. Monitor cache hit rate and adjust if needed.

**Q: Should Schema Intelligence agent call SQL Generation directly or return to Orchestrator?**
- Resolution: Return to Orchestrator. Maintains separation of concerns and allows Orchestrator to coordinate multiple agents in future phases.

### Deferred to Implementation

**Q: Optimal max_depth for graph traversal**
- Why deferred: Needs empirical tuning based on actual query patterns. Start with depth=2 (covers 95% of cases), log traversal depths, adjust if needed.

**Q: Fuzzy matching threshold for entity-to-table mapping**
- Why deferred: Needs testing with real queries. Start with Levenshtein distance threshold of 0.7 (70% similarity), tune based on false positive/negative rates.

**Q: Whether to include all columns or only referenced columns in pruned schema**
- Why deferred: Trade-off between context size and SQL Generation flexibility. Start with all columns from selected tables (simpler), optimize to referenced-only if token budget becomes issue.

## Output Structure

```
agents/
├── schema_intelligence.py     # NEW: Schema Intelligence agent
├── models/
│   └── schema_models.py       # NEW: Schema-specific Pydantic models
└── cache.py                   # MODIFY: Add InMemoryCache implementation

tests/agents/
├── test_schema_intelligence.py  # NEW: Unit tests
└── fixtures/
    └── sample_schema.py         # NEW: Test fixtures for schema data

tests/integration/
└── test_schema_intelligence_integration.py  # NEW: Integration tests
```

## High-Level Technical Design

> *This illustrates the intended approach and is directional guidance for review, not implementation specification. The implementing agent should treat it as context, not code to reproduce.*

**Schema Intelligence Flow:**

```
Question: "Which clients have the most tanks this month?"
    ↓
Schema Intelligence Agent
    ↓
1. Entity Extraction
   - Extract nouns: ["clients", "tanks", "month"]
   - Fuzzy match to tables:
     * "clients" → vehicle_in (croyance_client_name column)
     * "tanks" → iso_tank (table name)
     * "month" → created_at (temporal column)
   - Entities: {iso_tank, vehicle_in}
    ↓
2. Check Cache
   - Key: hash(sorted(["iso_tank", "vehicle_in"]))
   - Hit? → Return cached pruned schema
   - Miss? → Continue to graph traversal
    ↓
3. Graph Traversal (BFS, max_depth=2)
   - Start nodes: {iso_tank, vehicle_in}
   - Traverse foreign keys:
     * iso_tank.vehicle_in_id → vehicle_in.id
   - Selected tables: {iso_tank, vehicle_in}
   - JOIN path: iso_tank.vehicle_in_id = vehicle_in.id
    ↓
4. Schema Pruning
   - Include only selected tables
   - Include all columns from selected tables
   - Add relationship hints for JOINs
   - Token count: ~300 (vs ~8,000 full schema)
    ↓
5. Cache Result
   - Store pruned schema with 5-minute TTL
   - Return to Orchestrator
    ↓
Orchestrator → SQL Generation (with pruned schema)
```

**Foreign Key Graph Structure:**

```python
# Graph representation
graph = {
    "iso_tank": {
        "vehicle_in_id": ("vehicle_in", "id"),
        "vehicle_out_id": ("vehicle_out", "id"),
        "survey_form_id": ("survey_form", "id")
    },
    "vehicle_in": {
        "client_id": ("client_details", "id")
    },
    # ... other tables
}

# BFS traversal example
start_tables = ["iso_tank"]
max_depth = 2
visited = set()
queue = [(table, 0) for table in start_tables]

while queue:
    table, depth = queue.pop(0)
    if depth > max_depth or table in visited:
        continue
    visited.add(table)
    
    # Add neighbors (FK relationships)
    for fk_col, (target_table, target_col) in graph[table].items():
        if target_table not in visited:
            queue.append((target_table, depth + 1))
```

**Cache Implementation:**

```python
class InMemoryCache(CacheProtocol):
    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._access_times: Dict[str, float] = {}  # For LRU
    
    def get(self, key: str) -> Optional[Any]:
        if key not in self._cache:
            return None
        
        value, expiry = self._cache[key]
        if time.time() > expiry:
            # Expired
            del self._cache[key]
            del self._access_times[key]
            return None
        
        # Update access time for LRU
        self._access_times[key] = time.time()
        return value
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        # Evict if at capacity
        if len(self._cache) >= self._max_size:
            self._evict_lru()
        
        ttl = ttl or self._default_ttl
        expiry = time.time() + ttl
        self._cache[key] = (value, expiry)
        self._access_times[key] = time.time()
```

## Implementation Units

- [ ] **Unit 1: In-Memory Cache Implementation**

**Goal:** Implement production-ready in-memory cache with TTL and LRU eviction to replace the NoOpCache stub from Phase 1.

**Requirements:** R3

**Dependencies:** None (extends existing cache.py)

**Files:**
- Modify: `agents/cache.py`
- Test: `tests/agents/test_cache.py`

**Approach:**
- Implement InMemoryCache class extending CacheProtocol
- Store cache entries as (value, expiry_timestamp) tuples
- Track access times for LRU eviction
- Evict expired entries on get()
- Evict least-recently-used entry when at max capacity
- Thread-safe operations using threading.Lock (service is single-threaded but future-proof)
- Default: max_size=1000 entries, default_ttl=300 seconds (5 minutes)

**Patterns to follow:**
- CacheProtocol interface from `agents/cache.py`
- Time-based expiry pattern (time.time() for timestamps)
- LRU eviction using access time tracking

**Test scenarios:**
- Happy path: Set and get value within TTL
- Happy path: Get returns None for non-existent key
- Edge case: Get returns None for expired entry (TTL exceeded)
- Edge case: LRU eviction when cache reaches max_size
- Edge case: Set with custom TTL overrides default
- Integration: Cache operations are thread-safe (concurrent get/set)
- Integration: Delete removes entry and access time
- Integration: Clear removes all entries

**Verification:**
- Cache hit returns correct value within TTL
- Cache miss returns None after TTL expiry
- LRU eviction removes least-recently-used entry when at capacity
- All cache operations complete in <1ms (in-memory performance)

- [ ] **Unit 2: Foreign Key Graph Builder**

**Goal:** Parse schema output from SchemaIntrospector and build a directed graph of foreign key relationships for traversal.

**Requirements:** R5

**Dependencies:** None (uses existing services/schema.py)

**Files:**
- Create: `agents/models/schema_models.py`
- Create: `agents/schema_intelligence.py` (graph builder methods only)
- Test: `tests/agents/test_schema_intelligence.py` (graph builder tests)
- Test: `tests/agents/fixtures/sample_schema.py` (test fixtures)

**Approach:**
- Parse schema string from SchemaIntrospector.get_database_schema()
- Extract foreign key relationships using regex: `column_name: type (foreign key -> table.column)`
- Build adjacency list graph: `{table: {fk_column: (target_table, target_column)}}`
- Include reverse relationships for bidirectional traversal
- Validate graph structure (no dangling references, all FK targets exist)

**Patterns to follow:**
- Schema parsing pattern from `agents/sql_generation.py` (_parse_schema method)
- Graph representation using nested dictionaries (Python standard pattern)
- Pydantic models for structured graph data

**Test scenarios:**
- Happy path: Parse schema with multiple FK relationships
- Happy path: Build graph with bidirectional edges
- Edge case: Schema with no foreign keys (empty graph)
- Edge case: Schema with self-referential FK (e.g., employee.manager_id → employee.id)
- Edge case: Schema with circular FK relationships (A → B → C → A)
- Integration: Parse real schema from test database
- Integration: Graph includes all FK relationships from SchemaIntrospector

**Verification:**
- Graph contains all FK relationships from schema
- Bidirectional edges allow traversal in both directions
- Graph structure is valid (no dangling references)
- Parsing completes in <100ms for typical schema (~50 tables)

- [ ] **Unit 3: Entity Extraction and Table Mapping**

**Goal:** Extract entities (nouns) from natural language questions and map them to database tables using fuzzy matching.

**Requirements:** R4

**Dependencies:** Unit 2 (schema models)

**Files:**
- Modify: `agents/schema_intelligence.py` (entity extraction methods)
- Modify: `agents/models/schema_models.py` (entity models)
- Test: `tests/agents/test_schema_intelligence.py` (entity extraction tests)

**Approach:**
- Extract nouns from question using simple regex (words not in stopword list)
- Fuzzy match entities to table names using Levenshtein distance
- Fuzzy match entities to column names (for tables with semantic column names like croyance_client_name)
- Threshold: 0.7 similarity (70% match) to avoid false positives
- Handle plurals (e.g., "tanks" → "tank")
- Return set of matched table names

**Execution note:** Implement fuzzy matching test-first with known entity-to-table mappings to validate threshold tuning.

**Patterns to follow:**
- Text processing pattern from `agents/sql_generation.py` (_extract_columns method)
- Fuzzy matching using Python's difflib.SequenceMatcher or Levenshtein library
- Stopword filtering (common words like "the", "a", "is", "are")

**Test scenarios:**
- Happy path: Extract entities from simple question ("How many tanks?")
- Happy path: Extract entities from complex question ("Which clients have the most tanks this month?")
- Happy path: Fuzzy match handles plurals ("tanks" → "iso_tank")
- Happy path: Fuzzy match handles abbreviations ("ISO" → "iso_tank")
- Edge case: Question with no recognizable entities → return empty set
- Edge case: Entity matches multiple tables → return all matches
- Edge case: Entity below similarity threshold → not matched
- Integration: Extract entities from real user questions
- Integration: Map entities to correct tables from test database schema

**Verification:**
- Entity extraction identifies 90% of relevant tables for test queries
- Fuzzy matching threshold (0.7) balances precision and recall
- False positive rate <10% (entities matched to wrong tables)
- Extraction completes in <50ms per question

- [ ] **Unit 4: Graph Traversal and Schema Pruning**

**Goal:** Traverse foreign key graph starting from entity-matched tables to discover JOIN paths and prune schema to only relevant tables and columns.

**Requirements:** R1, R2, R5

**Dependencies:** Unit 2 (graph builder), Unit 3 (entity extraction)

**Files:**
- Modify: `agents/schema_intelligence.py` (traversal and pruning methods)
- Modify: `agents/models/schema_models.py` (pruned schema models)
- Test: `tests/agents/test_schema_intelligence.py` (traversal tests)

**Approach:**
- BFS traversal starting from entity-matched tables
- Max depth = 2 (configurable)
- Track visited tables to avoid cycles
- Collect JOIN path hints (FK relationships traversed)
- Prune schema to include only visited tables
- Include all columns from visited tables (optimization: only referenced columns deferred)
- Format pruned schema matching SchemaIntrospector output format
- Add JOIN hints section with discovered FK paths

**Patterns to follow:**
- BFS algorithm using queue (collections.deque)
- Schema formatting pattern from `services/schema.py` (SchemaIntrospector.get_database_schema)
- Visited set pattern for cycle detection

**Test scenarios:**
- Happy path: Traverse from single table with no FKs (depth 0)
- Happy path: Traverse from single table with 1-hop FK (depth 1)
- Happy path: Traverse from single table with 2-hop FK chain (depth 2)
- Happy path: Traverse from multiple start tables (union of reachable tables)
- Edge case: Circular FK relationships (A → B → A) → visited set prevents infinite loop
- Edge case: Max depth exceeded → stop traversal
- Edge case: Disconnected tables (no FK path) → include only start tables
- Integration: Prune real schema from ~8,000 to ~300 tokens
- Integration: Pruned schema includes all necessary tables for JOIN query

**Verification:**
- Token count reduced by 95% (8,000 → 300 tokens)
- Pruned schema includes all tables needed for test queries
- JOIN path hints are correct and complete
- Traversal completes in <100ms for typical graph (~50 tables)

- [ ] **Unit 5: Schema Intelligence Agent Integration**

**Goal:** Integrate all components into a complete Schema Intelligence agent that implements the BaseAgent interface and can be called by the Orchestrator.

**Requirements:** R1, R2, R3, R4, R5

**Dependencies:** Unit 1 (cache), Unit 2 (graph builder), Unit 3 (entity extraction), Unit 4 (traversal)

**Files:**
- Modify: `agents/schema_intelligence.py` (execute method and integration)
- Modify: `agents/models/schema_models.py` (request/response models)
- Test: `tests/agents/test_schema_intelligence.py` (integration tests)

**Approach:**
- Implement execute() method following BaseAgent interface
- Input: SchemaIntelligenceRequest (question, full_schema)
- Output: SchemaIntelligenceResponse (pruned_schema, selected_tables, join_hints, confidence)
- Workflow: extract entities → check cache → build graph → traverse → prune → cache result
- Cache key: hash(sorted(entity_set))
- Confidence scoring: 0.9 if entities found, 0.5 if no entities (fallback to full schema)
- Logging: entity extraction, cache hit/miss, traversal depth, token reduction

**Patterns to follow:**
- Agent structure from `agents/sql_generation.py` (execute method, logging, error handling)
- Pydantic models from `agents/models/agent_models.py` (request/response structure)
- Cache integration pattern (check cache → compute → store)

**Test scenarios:**
- Happy path: Process simple question with cache miss
- Happy path: Process simple question with cache hit
- Happy path: Process complex question requiring 2-hop traversal
- Error path: Empty question → raise AgentValidationError
- Error path: Invalid schema format → handle gracefully
- Edge case: No entities extracted → return full schema with low confidence
- Integration: Agent reduces token count by 95% for test queries
- Integration: Agent returns correct JOIN hints for multi-table queries
- Integration: Cache hit rate >60% for repeated entity sets

**Verification:**
- Agent implements BaseAgent interface correctly
- Token reduction meets 95% target (8,000 → 300)
- Cache hit rate >60% for typical query patterns
- Agent execution time <200ms (including cache miss)
- Confidence scores reflect entity extraction quality

- [ ] **Unit 6: Orchestrator Integration and Routing**

**Goal:** Update Orchestrator to route queries through Schema Intelligence before SQL Generation, replacing full schema with pruned schema.

**Requirements:** R6

**Dependencies:** Unit 5 (Schema Intelligence agent)

**Files:**
- Modify: `agents/orchestrator.py`
- Modify: `tests/agents/test_orchestrator.py`
- Test: `tests/integration/test_multi_agent_pipeline.py`

**Approach:**
- Add Schema Intelligence agent to Orchestrator initialization
- Update routing logic: Question → Schema Intelligence → SQL Generation → Result
- Pass pruned schema from Schema Intelligence to SQL Generation
- Preserve backward compatibility: if Schema Intelligence fails, fall back to full schema
- Update metadata to include schema pruning metrics (token reduction, cache hit)
- Log schema pruning effectiveness (token count before/after)

**Patterns to follow:**
- Orchestrator routing pattern from `agents/orchestrator.py` (_route_to_sql_generation method)
- Error handling with fallback pattern
- Metadata propagation through agent chain

**Test scenarios:**
- Happy path: Route simple query through Schema Intelligence → SQL Generation
- Happy path: Route complex query with 2-table JOIN
- Happy path: Cache hit reduces latency on repeated query
- Error path: Schema Intelligence fails → fall back to full schema
- Error path: Schema Intelligence returns empty schema → fall back to full schema
- Integration: End-to-end query with schema pruning
- Integration: Multi-table JOIN query succeeds with pruned schema
- Integration: Token usage reduced by 95% in SQL Generation

**Verification:**
- Orchestrator routes all queries through Schema Intelligence
- Fallback to full schema works correctly on Schema Intelligence failure
- Token usage reduced by 95% (measured via AI provider logs)
- Complex JOIN queries succeed ≥80% (up from ~40%)
- End-to-end latency <3s at p95 (schema pruning reduces AI call time)

## System-Wide Impact

**Interaction graph:**
- Schema Intelligence agent is new - no existing callbacks or middleware affected
- Orchestrator routing updated to include Schema Intelligence as pre-processing step
- SQL Generation agent receives pruned schema instead of full schema (input change)
- No changes to API endpoints or response structure

**Error propagation:**
- Schema Intelligence errors propagate through Orchestrator → multi_agent_pipeline → API endpoint
- Fallback to full schema prevents Schema Intelligence failures from blocking queries
- Existing error handling in Orchestrator catches and logs Schema Intelligence errors

**State lifecycle risks:**
- Cache state is per-process (in-memory) - lost on restart (acceptable for Phase 2)
- Cache eviction may cause temporary latency spikes (cache miss → recompute)
- No cross-request state dependencies (agents remain stateless)

**API surface parity:**
- No changes to API endpoints or response structure
- Schema pruning is transparent to API consumers
- Token usage reduction visible in logs but not exposed in API

**Integration coverage:**
- Integration tests verify end-to-end flow with schema pruning
- Integration tests verify fallback to full schema on Schema Intelligence failure
- Unit tests verify each component in isolation

**Unchanged invariants:**
- API endpoints and response structure unchanged
- Authentication and rate limiting unchanged
- Database schema and permissions unchanged
- SQL Generation agent interface unchanged (only input schema changes)

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Entity extraction may miss relevant tables (false negatives) | Fallback to full schema if no entities extracted. Log missed entities for analysis. Tune fuzzy matching threshold based on production data. Phase 3 Query Refinement will improve entity extraction with business glossary. |
| Graph traversal may include irrelevant tables (false positives) | Max depth=2 limits noise. Monitor pruned schema size and adjust depth if needed. Log traversal paths for analysis. |
| Cache may cause stale schema issues if database schema changes | 5-minute TTL is short enough for typical schema change frequency. Add cache invalidation endpoint for manual refresh if needed. |
| In-memory cache lost on service restart | Acceptable for Phase 2 - cache warms up quickly. Upgrade to Redis if persistence needed. |
| Fuzzy matching threshold (0.7) may need tuning | Start with 0.7, log match scores and false positive/negative rates. Adjust threshold based on production data. |
| BFS traversal may be slow for large schemas (>100 tables) | Max depth=2 limits traversal scope. Optimize with early termination if needed. Monitor traversal time and set alert at 200ms. |

## Documentation / Operational Notes

**Documentation updates:**
- Update `agents/README.md` with Schema Intelligence agent description
- Add docstrings to all new methods and classes
- Document cache configuration (max_size, TTL)

**Operational notes:**
- Monitor cache hit rate (target >60%)
- Monitor token reduction (target 95%)
- Monitor Schema Intelligence execution time (target <200ms)
- Log entity extraction quality (entities found vs missed)
- Set up alerts for low cache hit rate (<40%) or high execution time (>500ms)

**Configuration:**
- Cache max_size: 1000 entries (configurable via environment variable)
- Cache TTL: 300 seconds (5 minutes, configurable)
- Graph traversal max_depth: 2 (configurable)
- Fuzzy matching threshold: 0.7 (configurable)

**Rollout plan:**
- Deploy Schema Intelligence agent alongside existing Phase 1 agents
- Monitor token usage reduction and cache hit rate
- Verify complex JOIN query success rate improves to ≥80%
- No user-facing changes (transparent optimization)

## Success Metrics

**Accuracy metrics (from origin document):**
- Complex Query Success: ≥80% of multi-table JOIN queries succeed (up from ~40%)
- Schema Pruning Accuracy: ≥95% of pruned schemas include all necessary tables
- False Positive Rate: <10% of pruned schemas include unnecessary tables

**Performance metrics:**
- Token Reduction: 95% reduction (8,000 → 300 tokens)
- Cache Hit Rate: >60% for typical query patterns
- Schema Intelligence Latency: <200ms at p95 (cache miss)
- End-to-End Latency: <3s at p95 (reduced from Phase 1 due to smaller context)

**Cost metrics:**
- Cost per Query: <$0.001 (down from $0.002 in Phase 1 due to token reduction)
- Token Usage: 95% reduction in SQL Generation agent input tokens

## Sources & References

- **Origin document:** [docs/brainstorms/multi-agent-text-to-sql-requirements.md](docs/brainstorms/multi-agent-text-to-sql-requirements.md)
- **Phase 1 plan:** [docs/plans/2026-04-21-006-feat-multi-agent-phase1-core-framework-plan.md](docs/plans/2026-04-21-006-feat-multi-agent-phase1-core-framework-plan.md)
- **Related code:**
  - `services/schema.py` - SchemaIntrospector with FK discovery
  - `agents/base.py` - Base agent class
  - `agents/orchestrator.py` - Orchestrator routing
  - `agents/sql_generation.py` - SQL Generation agent
  - `agents/cache.py` - Cache protocol
- **Research papers:**
  - CHESS: Contextual Harnessing for Efficient SQL Synthesis (Talaei et al., ICML 2025)
  - MAC-SQL: Multi-Agent Collaboration for Text-to-SQL (Wang et al., COLING 2025)
  - AgentiQL: Agent-Inspired Multi-Expert Framework (arXiv 2510.10661v2)
- **Algorithm references:**
  - Breadth-First Search (BFS) for graph traversal
  - Levenshtein distance for fuzzy string matching
  - LRU cache eviction policy
