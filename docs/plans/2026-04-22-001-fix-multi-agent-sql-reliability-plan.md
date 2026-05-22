---
title: Fix Multi-Agent Text-to-SQL Reliability
type: fix
status: active
date: 2026-04-22
origin: ai-service-croyance/docs/brainstorms/2026-04-22-fix-multi-agent-reliability-requirements.md
---

# Fix Multi-Agent Text-to-SQL Reliability

## Overview

Fix the admin chatbot's multi-agent text-to-SQL system to achieve 95%+ SQL accuracy across all AI models. The root cause is the Schema Intelligence Agent failing to prune the schema effectively (sends 32K chars instead of 300 chars), causing SQL Generation Agent to hallucinate table names. This plan implements targeted fixes to the schema pruning pipeline, adds pre-execution validation, and improves SQL generation prompts.

## Problem Frame

Admins need to ask any question about their data in natural language and get accurate answers. Currently, the system generates incorrect SQL with hallucinated table names (e.g., `iso_tanks` instead of `iso_tank`) because the SQL Generation Agent receives an overwhelming 32,524-character schema containing 50+ tables instead of a pruned 300-character schema with 2-3 relevant tables.

**Example failure:**
- Question: "How many ISO tanks are currently in?"
- Generated SQL: `SELECT COUNT(*) FROM iso_tanks LIMIT 100;`
- Actual table: `iso_tank` (singular)
- Result: SQL error, no answer

This problem persists across DeepSeek, Groq, Gemini, GPT, and Claude models, confirming it's architectural rather than model-specific.

## Requirements Trace

- R1. 95%+ SQL accuracy - generates correct table/column names for realistic admin questions
- R2. Schema pruning works - reduces 32K schema → 300 tokens (2-3 relevant tables only)
- R3. Validation layer - catches hallucinated table/column names before execution
- R4. Works across models - reliable with DeepSeek, Groq, Gemini, GPT, Claude
- R5. Must remain dynamic - no hardcoded SQL templates or predefined queries
- R6. Read-only database - security layer prevents all write operations
- R7. Swappable AI models - works with any OpenAI-compatible or Anthropic model

## Scope Boundaries

**In scope:**
- Fix Schema Intelligence Agent entity extraction and matching
- Add SQL validation layer before execution
- Improve SQL generation prompts with explicit table lists
- Test with golden query suite across multiple models

**Out of scope:**
- Hardcoded SQL templates or predefined queries
- Switching to tool-based architecture (LangChain style)
- Complete architectural redesign
- Frontend UI changes
- Database schema changes
- Adding new AI models beyond existing swappable config
- Conversational context (deferred to Phase 4 - optional)

## Context & Research

### Relevant Code and Patterns

- `agents/schema_intelligence.py` - Schema pruning agent with entity extraction, fuzzy matching, and graph traversal (currently not working effectively)
- `agents/sql_generation.py` - SQL generation with self-critique loop and validation
- `services/schema.py` - Database schema introspection (generates 32K char schema)
- `agents/models/schema_models.py` - Data models for schema intelligence
- `agents/models/query_models.py` - Data models for SQL generation
- `config/ai_provider.py` - Swappable AI model configuration

### Current Architecture

Multi-agent pipeline (6 agents):
1. Orchestrator - Routes queries and forms dynamic teams
2. Query Refinement - Resolves ambiguity (temporal terms, business terminology)
3. Security & Governance - RBAC, PII blocking, read-only enforcement
4. **Schema Intelligence** - Should prune schema 8K→300 tokens (NOT WORKING)
5. **SQL Generation** - Generates SQL with self-critique loop
6. Result Formatter - Natural language answers

### Root Cause Analysis

**Schema Intelligence Agent issues:**
- Entity extraction uses simple regex + stopword filtering - misses multi-word phrases like "ISO tanks"
- Fuzzy matching uses SequenceMatcher with 0.6 threshold - doesn't handle synonyms or semantic similarity
- Graph traversal includes too many tables via foreign key relationships
- No validation that pruned schema is actually <500 tokens
- Caching by entity set doesn't account for schema changes

**SQL Generation Agent issues:**
- Receives 32K char schema with 50+ tables
- Prompt doesn't emphasize exact table names strongly enough
- Few-shot examples don't cover common failure patterns
- No pre-execution validation - hallucinations cause SQL errors

## Key Technical Decisions

**Decision:** Use embedding-based entity matching with fuzzy matching fallback
**Rationale:** Embeddings handle synonyms ("tanks" → "iso_tank"), multi-word phrases ("ISO tanks"), and semantic similarity. Fuzzy matching catches spelling mistakes ("tanx" → "tank", "servey" → "survey"). Combined approach is more robust for production use.
**Alternative considered:** Pure LLM semantic parsing (rejected: higher cost, no proven benefit, adds latency)

**Decision:** Add pre-execution SQL validation layer
**Rationale:** Catches 100% of hallucinations before they cause errors, provides clear feedback for retry loop, better UX than post-execution error handling.
**Alternative considered:** Post-execution error handling (rejected: poor UX, wastes DB queries, doesn't prevent errors)

**Decision:** Keep swappable AI model config
**Rationale:** No single model is perfect, flexibility is valuable for cost optimization and vendor independence.
**Alternative considered:** Mandate specific model (rejected: vendor lock-in, cost constraints)

**Decision:** Aggressive schema pruning with validation
**Rationale:** Only include matched tables + 1-hop foreign keys, validate output is <500 tokens. Prevents overwhelming SQL agent with irrelevant tables.
**Alternative considered:** Include all related tables (rejected: defeats purpose of pruning, still sends too much context)

## Implementation Units

- [ ] **Unit 1: Improve Entity Extraction**

**Goal:** Extract multi-word phrases and handle domain-specific terminology

**Requirements:** R1, R2

**Dependencies:** None

**Files:**
- Modify: `ai-service-croyance/agents/schema_intelligence.py`
- Test: `ai-service-croyance/tests/test_schema_intelligence.py`

**Approach:**
- Add n-gram extraction (bigrams, trigrams) to capture multi-word phrases like "ISO tanks", "service tanks", "vehicle in"
- Enhance stopword filtering to preserve domain terms
- Add business glossary integration from `agents/config/business_glossary.yaml`
- Keep existing regex-based extraction as fallback

**Patterns to follow:**
- Existing `_extract_entities_fallback()` method structure
- Business glossary pattern from Query Refinement agent

**Test scenarios:**
- Happy path: Extract "ISO tanks" as single entity from "How many ISO tanks are currently in?"
- Happy path: Extract "service tank" from "List all service tanks with their status"
- Edge case: Handle questions with only single-word entities
- Edge case: Handle questions with no recognizable entities (return full schema)
- Error path: Handle empty or whitespace-only questions

**Verification:**
- Entity extraction returns multi-word phrases for test questions
- Business glossary terms are recognized and extracted
- Stopwords are filtered but domain terms are preserved

- [ ] **Unit 2: Implement Embedding-Based Entity Matching**

**Goal:** Replace fuzzy matching with semantic similarity using embeddings

**Requirements:** R1, R2

**Dependencies:** Unit 1

**Files:**
- Modify: `ai-service-croyance/agents/schema_intelligence.py`
- Create: `ai-service-croyance/agents/embeddings.py` (embedding utility)
- Modify: `ai-service-croyance/requirements.txt` (add sentence-transformers)
- Test: `ai-service-croyance/tests/test_schema_intelligence.py`

**Approach:**
- Use sentence-transformers library (all-MiniLM-L6-v2 model - fast, lightweight)
- Generate embeddings for entities and table/column names
- Calculate cosine similarity for semantic matching
- **Also run fuzzy matching in parallel** to catch spelling mistakes
- Take the best match from either approach (highest similarity score)
- Cache embeddings for table/column names (they don't change often)
- Keep pure fuzzy matching as fallback if embedding model fails to load

**Patterns to follow:**
- Existing `_match_entities_fallback()` method structure
- Caching pattern from existing `_generate_cache_key()` method

**Test scenarios:**
- Happy path: Match "tanks" to "iso_tank" table with high similarity (embedding)
- Happy path: Match "clients" to "croyance_client_name" column (embedding)
- Happy path: Match "tanks" with spelling mistake "tanx" to "iso_tank" (fuzzy matching)
- Happy path: Match "servey" (misspelled) to "survey_form" (fuzzy matching)
- Edge case: Handle plural/singular variations ("tank" vs "tanks")
- Edge case: Handle synonyms and abbreviations
- Edge case: Handle typos in multi-word phrases ("ISO tanx" → "iso_tank")
- Error path: Fallback to pure fuzzy matching if embedding model unavailable
- Integration: Combined approach handles both semantic similarity and spelling mistakes

**Verification:**
- Embedding-based matching achieves >0.8 similarity for known entity-table pairs
- Fallback to fuzzy matching works when embeddings unavailable
- Performance is acceptable (<100ms for matching 10 entities against 50 tables)

- [ ] **Unit 3: Aggressive Schema Pruning with Validation**

**Goal:** Prune schema to only matched tables + 1-hop foreign keys, validate <500 tokens

**Requirements:** R2

**Dependencies:** Unit 2

**Files:**
- Modify: `ai-service-croyance/agents/schema_intelligence.py`
- Test: `ai-service-croyance/tests/test_schema_intelligence.py`

**Approach:**
- After entity matching, select only matched tables (not all related tables)
- Traverse graph with max_depth=1 (only direct foreign key relationships)
- Validate pruned schema is <500 tokens (currently estimates ~4 chars/token)
- If pruned schema still >500 tokens, prioritize tables by match confidence
- Add fallback: if pruning fails completely, return top 5 most common tables

**Patterns to follow:**
- Existing `_traverse_graph()` method structure
- Existing `_prune_schema()` method structure
- Token counting pattern from existing `PrunedSchema` model

**Test scenarios:**
- Happy path: Prune 32K schema to <500 tokens for "ISO tanks" query
- Happy path: Include foreign key relationships (iso_tank → vehicle_in)
- Edge case: Handle queries matching many tables (prioritize by confidence)
- Edge case: Handle queries matching no tables (return top 5 common tables)
- Error path: Fallback to top 5 tables if pruning logic fails

**Verification:**
- Pruned schema is <500 tokens for all test queries
- Pruned schema includes matched tables + 1-hop foreign keys
- Fallback returns valid schema when pruning fails

- [ ] **Unit 4: Add SQL Validation Layer**

**Goal:** Validate SQL against schema before execution, catch hallucinations

**Requirements:** R3

**Dependencies:** Unit 3

**Files:**
- Create: `ai-service-croyance/agents/sql_validator.py`
- Modify: `ai-service-croyance/agents/sql_generation.py`
- Test: `ai-service-croyance/tests/test_sql_validator.py`

**Approach:**
- Create new SQLValidator class with validate() method
- Check all table names exist in schema (exact match, case-insensitive)
- Check all column names exist in referenced tables
- Check JOIN clauses have ON conditions
- Check safety rules (no DROP, DELETE, UPDATE, etc.)
- Return (is_valid, list of specific issues) for retry feedback
- Integrate into SQL Generation Agent's self-critique loop

**Patterns to follow:**
- Existing `_validate_sql_fallback()` method in SQL Generation Agent
- Existing `_parse_schema()` method for extracting valid tables/columns
- BaseAgent pattern for error handling

**Test scenarios:**
- Happy path: Valid SQL passes validation
- Error path: Detect hallucinated table name ("iso_tanks" instead of "iso_tank")
- Error path: Detect hallucinated column name
- Error path: Detect JOIN without ON clause
- Error path: Detect dangerous keywords (DROP, DELETE, UPDATE)
- Error path: Detect non-SELECT queries
- Integration: Validation catches hallucinations and provides specific feedback for retry

**Verification:**
- Validator catches 100% of hallucinated table names in test suite
- Validator catches 100% of hallucinated column names in test suite
- Validator provides specific, actionable error messages
- Integration with SQL Generation Agent retry loop works correctly

- [ ] **Unit 5: Improve SQL Generation Prompts**

**Goal:** Strengthen prompts with explicit table lists and negative examples

**Requirements:** R1, R4

**Dependencies:** Unit 4

**Files:**
- Modify: `ai-service-croyance/agents/sql_generation.py`
- Test: `ai-service-croyance/tests/test_sql_generation.py`

**Approach:**
- Add "AVAILABLE TABLES:" section to system prompt with exact table names from pruned schema
- Add "COMMON MISTAKES TO AVOID:" section with negative examples (pluralization, typos)
- Strengthen few-shot examples to emphasize exact table name usage
- Add validation feedback section that shows previous errors clearly
- Keep existing self-critique loop structure

**Patterns to follow:**
- Existing `_build_system_prompt()` method structure
- Existing few-shot examples in `FEW_SHOT_EXAMPLES` constant

**Test scenarios:**
- Happy path: Generate correct SQL for "ISO tanks" query using exact table name
- Happy path: Generate correct SQL with JOINs using exact table/column names
- Error path: Retry with validation feedback when first attempt has hallucinated names
- Integration: Improved prompts reduce hallucination rate by 50% compared to baseline

**Verification:**
- Generated SQL uses exact table names from schema
- Validation feedback is incorporated into retry attempts
- Hallucination rate decreases with improved prompts

- [ ] **Unit 6: Create Golden Query Test Suite**

**Goal:** Comprehensive test suite covering all common admin questions

**Requirements:** R1, R4

**Dependencies:** Units 1-5

**Files:**
- Create: `ai-service-croyance/tests/golden_queries.yaml`
- Create: `ai-service-croyance/tests/test_golden_queries.py`
- Test: `ai-service-croyance/tests/test_golden_queries.py`

**Approach:**
- Create YAML file with 50+ realistic admin questions
- Include expected SQL queries (or at least expected tables/columns)
- Cover all major domains: ISO tanks, service tanks, vehicle in/out, surveys, clients
- Include edge cases: temporal queries, aggregations, JOINs, filters
- Create test runner that executes full pipeline for each query
- Measure SQL accuracy, schema pruning effectiveness, validation catch rate

**Patterns to follow:**
- Existing test structure in `tests/` directory
- YAML configuration pattern from `agents/config/business_glossary.yaml`

**Test scenarios:**
- Happy path: All golden queries generate valid SQL
- Happy path: Schema pruning reduces tokens by >90% for all queries
- Happy path: Validation catches any hallucinations before execution
- Integration: Full pipeline achieves 95%+ accuracy on golden query suite
- Integration: Pipeline works consistently across multiple AI models

**Verification:**
- Golden query suite has 50+ realistic questions
- Test runner executes full pipeline end-to-end
- Metrics are collected: SQL accuracy, token reduction, validation catch rate
- Tests pass with 95%+ accuracy

## System-Wide Impact

**Interaction graph:**
- Schema Intelligence Agent → SQL Generation Agent (pruned schema)
- SQL Generation Agent → SQL Validator (validation before execution)
- SQL Validator → SQL Generation Agent (validation feedback for retry)

**Error propagation:**
- Schema Intelligence failures → return full schema with low confidence (graceful degradation)
- SQL Generation failures → return error with validation issues (clear feedback to user)
- Validation failures → trigger retry loop with specific feedback (self-healing)

**State lifecycle risks:**
- Schema caching by entity set may become stale if database schema changes (mitigation: 5-minute TTL)
- Embedding cache may grow large over time (mitigation: LRU cache with size limit)

**API surface parity:**
- No changes to external API contracts
- Internal agent interfaces remain compatible

**Integration coverage:**
- End-to-end test with full pipeline (Orchestrator → Schema Intelligence → SQL Generation → Validation)
- Cross-model testing (DeepSeek, Groq, Gemini, GPT, Claude)
- Schema change testing (verify system adapts when tables/columns renamed)

**Unchanged invariants:**
- Security layer still enforces read-only queries
- Orchestrator still routes queries to appropriate agents
- Result Formatter still generates natural language answers
- All agents remain swappable and independently testable

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Schema Intelligence still doesn't prune effectively after fixes | Add fallback: if pruning fails, use top 5 most common tables based on query frequency |
| Embedding model adds latency or memory overhead | Use lightweight model (all-MiniLM-L6-v2), cache embeddings, fallback to fuzzy matching |
| Validation is too strict, blocks valid queries | Tune validation rules iteratively, add override mechanism for admin users |
| Performance degrades with validation layer | Optimize validation (cache schema metadata), run validation in parallel with other checks |
| Complex spelling mistakes not caught by fuzzy matching | Document limitation, consider LLM-based preprocessing in future iteration if user feedback indicates need |
| Edge cases still fail (complex JOINs, subqueries) | Comprehensive golden query suite, gradual rollout with monitoring, iterate on failures |
| Different AI models have different failure modes | Test with multiple models, adjust prompts per model if needed, document model-specific quirks |

## Testing Strategy

1. **Unit tests** - Test each component in isolation (entity extraction, matching, pruning, validation)
2. **Integration tests** - Test full pipeline end-to-end with golden queries
3. **Cross-model tests** - Run same queries on DeepSeek, Groq, Gemini, GPT, Claude
4. **Adversarial tests** - Intentionally ambiguous questions, edge cases, malformed input
5. **Schema change tests** - Verify system adapts when tables/columns are renamed
6. **Performance tests** - Measure latency at p50, p95, p99 with validation layer

## Success Metrics

- **SQL accuracy:** 95%+ correct table/column names (currently ~50%)
- **Schema pruning:** <500 tokens per query (currently 32K)
- **Validation catch rate:** 100% of hallucinations caught before execution
- **Response time:** <3s at p95 (currently ~5s)
- **Cross-model consistency:** <5% accuracy variance across models

## Documentation / Operational Notes

**Documentation updates:**
- Update README with new validation layer architecture
- Document embedding model choice and fallback behavior
- Add troubleshooting guide for common failure modes

**Monitoring:**
- Track SQL accuracy rate in production
- Track schema pruning effectiveness (token reduction %)
- Track validation catch rate (hallucinations prevented)
- Track retry loop iterations (should decrease over time)
- Alert on accuracy drops below 90%

**Rollout:**
- Deploy to staging first, run golden query suite
- Gradual rollout to production (10% → 50% → 100%)
- Monitor metrics closely during rollout
- Rollback plan: revert to previous version if accuracy drops

## Sources & References

- **Origin document:** [ai-service-croyance/docs/brainstorms/2026-04-22-fix-multi-agent-reliability-requirements.md](ai-service-croyance/docs/brainstorms/2026-04-22-fix-multi-agent-reliability-requirements.md)
- Related code: `agents/schema_intelligence.py`, `agents/sql_generation.py`, `services/schema.py`
- External docs: [sentence-transformers documentation](https://www.sbert.net/)
