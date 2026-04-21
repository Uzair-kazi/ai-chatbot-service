---
title: "fix: Phase 2 Code Review Findings - Orchestrator Tests and Logging"
type: fix
status: active
date: 2026-04-21
origin: Code review of feat/multi-agent-phase2-schema-intelligence branch
---

# Fix Phase 2 Code Review Findings - Orchestrator Tests and Logging

## Overview

Fix critical and high-priority findings from the Phase 2 Schema Intelligence code review. The review identified incomplete orchestrator test mocking (16/19 tests failing), missing fallback metrics logging, and potential entity extraction improvements. This plan addresses P1-1 (orchestrator test fixture), P1-2 (fallback logging), P1-3 (SQL keyword evaluation), and P2-5 (token reduction test verification).

## Problem Frame

The Phase 2 Schema Intelligence implementation is functionally complete with all 40 schema intelligence tests passing, but the orchestrator integration tests are failing due to incomplete mocking. The orchestrator now routes through Schema Intelligence → SQL Generation, but the test fixture only mocks SQL Generation. Additionally, the fallback path (when Schema Intelligence fails) doesn't log pruning metrics, making it harder to diagnose why fallback occurred.

(see origin: Code review of feat/multi-agent-phase2-schema-intelligence branch)

## Requirements Trace

- R1. All 19 orchestrator tests must pass with proper Schema Intelligence mocking
- R2. Fallback path must log pruning metrics for debugging
- R3. Entity extraction stopword list evaluated for SQL keywords
- R4. Token reduction test verification restored or rationale documented

## Scope Boundaries

**In scope:**
- Update orchestrator test fixture to mock Schema Intelligence agent
- Add fallback metrics logging to orchestrator
- Evaluate adding SQL keywords to stopword list
- Restore token reduction verification or document why table count is sufficient

**Explicit non-goals:**
- Refactoring orchestrator routing logic (already implemented)
- Adding new Schema Intelligence features
- Performance optimization beyond test fixes

## Context & Research

### Relevant Code and Patterns

**Existing test patterns:**
- `tests/agents/test_sql_generation.py` - Mock-based unit tests with validation scenarios
- `tests/agents/test_schema_intelligence.py` - Schema Intelligence agent tests with mock responses
- `agents/models/schema_models.py` - SchemaIntelligenceResponse model structure

**Orchestrator implementation:**
- `agents/orchestrator.py` - Routes through Schema Intelligence → SQL Generation
- `agents/orchestrator.py:_route_with_schema_intelligence()` - Fallback logic when Schema Intelligence fails

**Entity extraction:**
- `agents/schema_intelligence.py:STOPWORDS` - Current stopword list for entity extraction
- `agents/schema_intelligence.py:_extract_entities()` - Entity extraction implementation

### Institutional Learnings

None found in `docs/solutions/` - this is the first Phase 2 review fix.

### External References

None needed - fixing internal test and logging issues.

## Key Technical Decisions

**Decision: Mock Schema Intelligence in orchestrator test fixture**
- Rationale: Orchestrator now routes through Schema Intelligence before SQL Generation. Tests must mock both agents to verify the full pipeline. Mocking at the agent level (not internal methods) keeps tests maintainable.

**Decision: Log fallback metrics even when Schema Intelligence fails**
- Rationale: When fallback occurs, operators need to know whether it was due to no entities extracted, no tables matched, or an exception. Logging the reason helps diagnose issues without requiring code changes.

**Decision: Evaluate SQL keywords case-by-case, not blanket addition**
- Rationale: SQL keywords like "show", "list", "get" are common in natural language questions. Adding them to stopwords might filter legitimate entities (e.g., "show table"). Evaluate whether they cause false positives in practice before adding.

**Decision: Restore token reduction verification if possible, document if not**
- Rationale: The original test verified 95% token reduction. The weakened version only checks table count. If token reduction is still achievable with the current implementation, restore the verification. If not, document why table count is sufficient.

## Open Questions

### Resolved During Planning

**Q: Should we add SQL keywords to stopwords?**
- Resolution: Evaluate in P1-3. Check if "show", "list", "get" cause false positives in entity extraction. If they do, add them. If not, document why they're kept.

**Q: Why was token reduction verification weakened?**
- Resolution: Investigate in P2-5. Check git history for the commit that weakened the test. Understand the rationale and either restore verification or document why table count is sufficient.

### Deferred to Implementation

**Q: Optimal fuzzy matching threshold for SQL keywords**
- Why deferred: Needs empirical testing with real queries. Start with current threshold (0.6), adjust if SQL keywords cause issues.

## Implementation Units

- [x] **Unit 1: Update Orchestrator Test Fixture to Mock Schema Intelligence**

**Goal:** Fix 16 failing orchestrator tests by adding Schema Intelligence agent mocking to the test fixture.

**Requirements:** R1

**Dependencies:** None

**Files:**
- Modify: `ai-service-croyance/tests/agents/test_orchestrator.py`

**Approach:**
- Add Schema Intelligence agent mock to the `orchestrator` fixture
- Create helper method to generate mock `SchemaIntelligenceResponse` objects
- Update all 16 failing tests to mock Schema Intelligence responses
- Ensure mock responses include proper structure: `pruned_schema`, `selected_tables`, `join_hints`, `entity_matches`, `confidence`, `metadata`
- Verify mocks match the actual `SchemaIntelligenceResponse` model from `agents/models/schema_models.py`

**Patterns to follow:**
- `tests/agents/test_orchestrator.py:test_route_simple_query_success()` - Already has Schema Intelligence mocking pattern
- `tests/agents/test_schema_intelligence.py` - Schema Intelligence response structure

**Test scenarios:**
- Happy path: All 19 orchestrator tests pass with proper mocking
- Happy path: Schema Intelligence mock returns pruned schema → SQL Generation receives pruned schema
- Happy path: Schema Intelligence mock returns cache hit → metadata includes cache_hit=True
- Edge case: Schema Intelligence mock returns failure → orchestrator falls back to full schema
- Integration: Mock responses match actual SchemaIntelligenceResponse structure

**Verification:**
- All 19 orchestrator tests pass: `python -m pytest tests/agents/test_orchestrator.py -v`
- No test failures related to missing Schema Intelligence mocking
- Test execution time remains under 5 seconds (mocking should be fast)

- [x] **Unit 2: Add Fallback Metrics Logging to Orchestrator**

**Goal:** Log pruning metrics when Schema Intelligence fails and orchestrator falls back to full schema.

**Requirements:** R2

**Dependencies:** Unit 1 (test fixture must be working to verify logging)

**Files:**
- Modify: `ai-service-croyance/agents/orchestrator.py`
- Test: `ai-service-croyance/tests/agents/test_orchestrator.py`

**Approach:**
- In `_route_with_schema_intelligence()`, when Schema Intelligence fails (exception or `success=False`), log:
  - Fallback reason (exception message or `schema_response.error`)
  - Whether entities were extracted (if available from error context)
  - Whether tables were matched (if available from error context)
  - Original schema token count (estimate: `len(request.db_schema) // 4`)
- Use `self.logger.warning()` for fallback events (not errors, since fallback is expected behavior)
- Include structured metadata for log aggregation: `extra={"fallback_reason": reason, "original_tokens": token_count}`

**Patterns to follow:**
- `agents/orchestrator.py:_route_with_schema_intelligence()` - Existing fallback logic
- `agents/schema_intelligence.py:execute()` - Logging pattern with structured metadata

**Test scenarios:**
- Happy path: Schema Intelligence succeeds → no fallback logging
- Error path: Schema Intelligence raises exception → fallback logged with exception message
- Error path: Schema Intelligence returns `success=False` → fallback logged with error message
- Integration: Fallback log includes original token count estimate
- Integration: Fallback log includes structured metadata for aggregation

**Verification:**
- Fallback logging appears in test output when Schema Intelligence fails
- Log message includes fallback reason and token count
- No logging when Schema Intelligence succeeds (no noise)

- [x] **Unit 3: Evaluate SQL Keywords for Stopword List**

**Goal:** Determine whether SQL keywords like "show", "list", "get" should be added to the entity extraction stopword list.

**Requirements:** R3

**Dependencies:** None (can be done in parallel with Unit 1-2)

**Files:**
- Modify: `ai-service-croyance/agents/schema_intelligence.py` (if keywords are added)
- Test: `ai-service-croyance/tests/agents/test_schema_intelligence.py` (if keywords are added)

**Approach:**
- Review existing entity extraction tests to see if SQL keywords cause false positives
- Check if "show", "list", "get" appear in test questions and whether they should be filtered
- If SQL keywords cause false positives (e.g., "show" matches "show_table" incorrectly), add them to `STOPWORDS`
- If SQL keywords are legitimate entities (e.g., "list" in "client list"), document why they're kept
- Consider adding only the most problematic keywords, not all SQL keywords

**Patterns to follow:**
- `agents/schema_intelligence.py:STOPWORDS` - Current stopword list
- `tests/agents/test_schema_intelligence.py:TestEntityExtraction` - Entity extraction test patterns

**Test scenarios:**
- Happy path: "show me tanks" extracts "tanks" (not "show")
- Happy path: "list all clients" extracts "clients" (not "list")
- Happy path: "get tank status" extracts "tank", "status" (not "get")
- Edge case: "show table" extracts "table" (not "show")
- Integration: SQL keywords don't cause false positive table matches

**Verification:**
- If keywords are added: Entity extraction tests pass with new stopwords
- If keywords are not added: Document rationale in commit message or code comment
- No regression in existing entity extraction tests

- [x] **Unit 4: Restore Token Reduction Verification or Document Rationale**

**Goal:** Either restore the 95% token reduction verification in the test or document why table count verification is sufficient.

**Requirements:** R4

**Dependencies:** None (can be done in parallel with other units)

**Files:**
- Modify: `ai-service-croyance/tests/agents/test_schema_intelligence.py`

**Approach:**
- Investigate git history to find the commit that weakened the token reduction test
- Understand the rationale: Was it due to implementation changes, test flakiness, or incorrect expectations?
- If token reduction is still achievable (95% reduction from ~8,000 to ~300 tokens):
  - Restore the verification: `assert response.metadata["token_reduction"] >= 95.0`
  - Adjust test data if needed to ensure 95% reduction is realistic
- If token reduction is no longer achievable or not the right metric:
  - Document why table count is sufficient (e.g., "Token reduction varies by query complexity; table count is a more stable metric")
  - Add comment to test explaining the rationale

**Patterns to follow:**
- `tests/agents/test_schema_intelligence.py:test_agent_token_reduction_target()` - Current test implementation
- `agents/schema_intelligence.py:_prune_schema()` - Token count calculation

**Test scenarios:**
- Happy path: Token reduction test verifies 95% reduction (if restored)
- Happy path: Token reduction test verifies table count reduction (if kept)
- Integration: Test data supports the verification metric (token reduction or table count)

**Verification:**
- Test passes with restored or documented verification
- No flakiness in token reduction verification (if restored)
- Commit message or code comment explains the decision

## System-Wide Impact

**Interaction graph:**
- Orchestrator test fixture now mocks both Schema Intelligence and SQL Generation agents
- Fallback logging adds observability to Schema Intelligence failures

**Error propagation:**
- Fallback logging does not change error propagation (still falls back to full schema)
- Test mocking does not affect production behavior

**State lifecycle risks:**
- None - test-only changes and logging additions

**API surface parity:**
- No API changes - internal test and logging improvements

**Integration coverage:**
- Orchestrator tests now cover Schema Intelligence → SQL Generation pipeline
- Fallback path is observable via logging

**Unchanged invariants:**
- Orchestrator routing logic unchanged (already implemented in Phase 2)
- Schema Intelligence agent behavior unchanged
- SQL Generation agent behavior unchanged

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Token reduction verification may be flaky if test data doesn't support 95% reduction | Investigate git history to understand why it was weakened. If 95% is unrealistic, document why table count is sufficient. |
| SQL keywords may be legitimate entities in some contexts | Evaluate case-by-case. Only add keywords that cause clear false positives. Document decision in code comment. |
| Fallback logging may add noise if Schema Intelligence fails frequently | Use `logger.warning()` (not `logger.error()`) and include structured metadata for filtering. Monitor fallback rate in production. |

## Documentation / Operational Notes

**Documentation updates:**
- Add code comments explaining SQL keyword stopword decisions (if keywords are added or explicitly not added)
- Add code comments explaining token reduction test rationale (if verification is kept as table count)

**Operational notes:**
- Monitor fallback logging in production to identify Schema Intelligence issues
- If fallback rate is high (>10%), investigate entity extraction or fuzzy matching thresholds

## Sources & References

- **Origin document:** Code review of feat/multi-agent-phase2-schema-intelligence branch
- **Related code:**
  - `agents/orchestrator.py` - Orchestrator routing logic
  - `agents/schema_intelligence.py` - Entity extraction and schema pruning
  - `tests/agents/test_orchestrator.py` - Orchestrator tests (16/19 failing)
  - `tests/agents/test_schema_intelligence.py` - Schema Intelligence tests (40/40 passing)
- **Related PRs/issues:** Phase 2 Schema Intelligence implementation (feat/multi-agent-phase2-schema-intelligence branch)
