---
title: "feat: Multi-Agent Text-to-SQL Phase 1 - Core Agent Framework"
type: feat
status: active
date: 2026-04-21
origin: docs/brainstorms/multi-agent-text-to-sql-requirements.md
---

# Multi-Agent Text-to-SQL Phase 1 - Core Agent Framework

## Overview

Build the foundational multi-agent framework with Orchestrator and SQL Generation agents featuring self-critique loops. This phase establishes the base agent architecture, structured outputs using Pydantic models, and demonstrates the self-correction capability that will eliminate column hallucinations.

## Problem Frame

The current single-LLM chatbot hallucinates column names (~20% error rate), cannot self-correct, and provides poor error feedback. Phase 1 addresses the self-correction problem by implementing an Orchestrator that routes queries through a SQL Generation agent with built-in validation and retry logic.

(see origin: docs/brainstorms/multi-agent-text-to-sql-requirements.md)

## Requirements Trace

- R1. SQL Generation agent catches and fixes column hallucinations through self-critique
- R2. Self-critique loop reduces SQL errors by 50% compared to current single-shot generation
- R3. Orchestrator provides dynamic agent routing and conflict resolution foundation
- R4. All agents use structured Pydantic outputs for type safety and validation
- R5. Base agent class provides consistent interface for future agents
- R6. Unit tests verify agent behavior in isolation

## Scope Boundaries

**In scope for Phase 1:**
- Base agent class with structured outputs
- Orchestrator agent with simple routing logic
- SQL Generation agent with self-critique loop (2-3 retry attempts)
- Pydantic models for agent inputs/outputs
- Unit tests for each agent
- Integration with existing chatbot pipeline

**Explicit non-goals:**
- Query Refinement agent (Phase 3)
- Security & Governance agent (Phase 3)
- Schema Intelligence agent (Phase 2)
- Result Formatter agent (Phase 4)
- LangGraph integration (deferred - using simple Python orchestration first)
- Business glossary or few-shot examples (using existing patterns from sql_generator.py)

### Deferred to Separate Tasks

- Schema pruning and caching: Phase 2 (Schema Intelligence agent)
- Security policies and RBAC: Phase 3 (Security & Governance agent)
- Natural language result formatting: Phase 4 (Result Formatter agent)
- Production monitoring and observability: Phase 4

## Context & Research

### Relevant Code and Patterns

**Existing pipeline structure:**
- `services/chatbot_pipeline.py` - Current orchestration pattern with 6-stage pipeline
- `services/sql_generator.py` - Existing SQL generation with few-shot examples
- `config/ai_provider.py` - Swappable AI provider abstraction (OpenAI-compatible + Anthropic)
- `tests/test_chatbot_pipeline.py` - Comprehensive mocking patterns for pipeline testing

**Key patterns to follow:**
- Exception hierarchy: `PipelineError` base class with specific subtypes
- Retry logic: Exponential backoff for transient failures (0.5s, 1s)
- Logging: Structured logging with stage timing and token usage
- Testing: Mock-based unit tests with `@pytest.mark.integration` for real services

**AI provider integration:**
- Supports both OpenAI-compatible (DeepSeek, OpenAI, Groq) and Anthropic SDKs
- Environment-driven configuration (AI_PROVIDER, AI_MODEL, SDK_TYPE)
- Temperature 0.1 for deterministic SQL generation
- Token usage logging for cost tracking

### Institutional Learnings

None found in `docs/solutions/` - this is the first multi-agent implementation in this codebase.

### External References

**Research papers informing design:**
- MAC-SQL: Multi-Agent Collaboration for Text-to-SQL (Wang et al., COLING 2025) - agent orchestration patterns
- MARS-SQL: Multi-Agent Reinforcement Learning Framework (arXiv 2511.01008) - self-critique loops
- AgentiQL: Agent-Inspired Multi-Expert Framework (arXiv 2510.10661v2) - structured agent outputs

**Framework documentation:**
- Pydantic V2 documentation for structured outputs and validation
- Python typing module for type hints and protocols

## Key Technical Decisions

**Decision: Use simple Python orchestration instead of LangGraph for Phase 1**
- Rationale: Reduces complexity for initial implementation. LangGraph adds value for complex multi-agent workflows with state management, but Phase 1 has simple sequential routing. Defer framework adoption until Phase 2-3 when we have 4+ agents with complex interactions.

**Decision: Implement self-critique as internal agent method, not separate agent**
- Rationale: Self-critique is tightly coupled to SQL generation - it validates the same output it produces. Keeping it internal reduces inter-agent communication overhead and simplifies the initial architecture.

**Decision: Use Pydantic models for all agent inputs/outputs**
- Rationale: Type safety, automatic validation, and clear contracts between agents. Prevents runtime errors from malformed data and provides self-documenting interfaces.

**Decision: Reuse existing AI provider abstraction from sql_generator.py**
- Rationale: Already supports multiple providers (OpenAI-compatible + Anthropic) with environment-driven configuration. No need to rebuild this infrastructure.

**Decision: Keep existing few-shot examples in SQL Generation agent**
- Rationale: Current examples are domain-specific and working. Phase 1 focuses on self-correction, not prompt engineering. Defer example optimization to Phase 2 when we have Schema Intelligence to provide better context.

## Open Questions

### Resolved During Planning

**Q: Should we use LangGraph or build custom orchestration?**
- Resolution: Custom Python orchestration for Phase 1. LangGraph deferred to Phase 2-3 when complexity justifies the framework overhead.

**Q: How many retry attempts should the self-critique loop allow?**
- Resolution: 2-3 attempts with confidence decay (0.9 → 0.75 → 0.6). After 3 failures, escalate to human with low confidence flag.

**Q: Should confidence scores be exposed in the API response?**
- Resolution: Not in Phase 1. Internal metric only. Expose in Phase 4 when we have Result Formatter agent that can explain confidence to users.

### Deferred to Implementation

**Q: Exact confidence decay formula**
- Why deferred: Needs empirical tuning based on actual error patterns. Start with linear decay (0.15 per attempt) and adjust based on test results.

**Q: Optimal token limits for self-critique prompts**
- Why deferred: Depends on actual prompt lengths after implementation. Start with 500 tokens (same as current sql_generator.py) and monitor.

**Q: Whether to cache validation results between retry attempts**
- Why deferred: Optimization decision that depends on observed retry patterns. Implement simple version first, optimize if retry latency becomes an issue.

## Output Structure

```
agents/
├── __init__.py
├── base.py                    # Base agent class
├── orchestrator.py            # Orchestrator agent
├── sql_generation.py          # SQL Generation agent with self-critique
├── models/
│   ├── __init__.py
│   ├── query_models.py        # Query-related Pydantic models
│   └── agent_models.py        # Agent communication models
└── cache.py                   # Caching protocol (stub for Phase 2)

tests/agents/
├── __init__.py
├── test_base_agent.py
├── test_orchestrator.py
└── test_sql_generation.py
```

## High-Level Technical Design

> *This illustrates the intended approach and is directional guidance for review, not implementation specification. The implementing agent should treat it as context, not code to reproduce.*

**Agent Communication Flow:**

```
User Question
    ↓
Orchestrator.route(question, schema)
    ↓
    ├─ Simple query? → [SQL_Gen] → Result
    ├─ Complex query? → [SQL_Gen] → Result
    └─ Error? → Escalate
    
SQL_Gen.generate(question, schema)
    ↓
    ├─ Attempt 1: Generate SQL
    │   ↓
    │   Self-critique: Validate against schema
    │   ↓
    │   Valid? → Return (confidence=0.9)
    │   Invalid? → Retry with error feedback
    ↓
    ├─ Attempt 2: Regenerate with feedback
    │   ↓
    │   Self-critique: Validate again
    │   ↓
    │   Valid? → Return (confidence=0.75)
    │   Invalid? → Retry with error feedback
    ↓
    └─ Attempt 3: Final attempt
        ↓
        Valid? → Return (confidence=0.6)
        Invalid? → Escalate (low_confidence=True)
```

**Pydantic Model Structure:**

```python
# Agent communication models
class AgentRequest(BaseModel):
    question: str
    schema: str
    context: Optional[Dict[str, Any]] = None

class AgentResponse(BaseModel):
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    confidence: float = 1.0
    metadata: Dict[str, Any] = {}

# SQL Generation specific models
class SQLGenerationRequest(AgentRequest):
    max_retries: int = 2
    temperature: float = 0.1

class SQLGenerationResponse(AgentResponse):
    sql: Optional[str] = None
    validation_issues: List[str] = []
    retry_count: int = 0
```

## Implementation Units

- [x] **Unit 1: Base Agent Class and Pydantic Models**

**Goal:** Create the foundational base agent class and Pydantic models that all agents will inherit from and use for communication.

**Requirements:** R4, R5

**Dependencies:** None

**Files:**
- Create: `agents/__init__.py`
- Create: `agents/base.py`
- Create: `agents/models/__init__.py`
- Create: `agents/models/agent_models.py`
- Create: `agents/models/query_models.py`
- Create: `agents/cache.py` (stub for Phase 2)
- Test: `tests/agents/__init__.py`
- Test: `tests/agents/test_base_agent.py`

**Approach:**
- Base agent class provides abstract interface with `execute()` method
- All agents inherit from base and implement `execute()`
- Pydantic models enforce type safety for agent inputs/outputs
- Cache protocol defined as abstract interface (implementation in Phase 2)
- Logging integration using existing `config.logging_config.get_logger()`

**Patterns to follow:**
- Exception hierarchy pattern from `services/chatbot_pipeline.py` (base exception + specific subtypes)
- Logging pattern from `services/sql_generator.py` (structured logs with timing)
- Type hints pattern from `config/ai_provider.py` (Union types, Optional)

**Test scenarios:**
- Happy path: Base agent instantiation and abstract method enforcement
- Happy path: Pydantic model validation with valid data
- Edge case: Pydantic model validation with invalid data (missing required fields, wrong types)
- Edge case: Base agent raises NotImplementedError when execute() not overridden
- Integration: Base agent logging integration (verify logger is initialized correctly)

**Verification:**
- All Pydantic models validate correctly with valid and invalid inputs
- Base agent enforces abstract method implementation
- Tests pass with 100% coverage for base.py and models/

- [x] **Unit 2: SQL Generation Agent with Self-Critique Loop**

**Goal:** Implement SQL Generation agent that generates SQL, validates it against the schema, and retries with error feedback if validation fails.

**Requirements:** R1, R2, R4

**Dependencies:** Unit 1 (base agent class and models)

**Files:**
- Create: `agents/sql_generation.py`
- Modify: `agents/models/query_models.py` (add SQL-specific models)
- Test: `tests/agents/test_sql_generation.py`

**Approach:**
- Inherit from base agent class
- Reuse AI provider abstraction from `config/ai_provider.py`
- Implement self-critique loop: generate → validate → retry with feedback
- Confidence decay: 0.9 → 0.75 → 0.6 over 3 attempts
- Validation checks: table existence, column existence, JOIN validity
- Error feedback includes specific validation failures to guide regeneration
- Use existing few-shot examples from `services/sql_generator.py`

**Execution note:** Implement validation logic test-first to ensure self-critique catches all error types before integrating with AI generation.

**Patterns to follow:**
- Retry logic from `services/chatbot_pipeline.py` (exponential backoff, max retries)
- AI provider integration from `services/sql_generator.py` (SDK_TYPE branching, token logging)
- SQL cleaning from `services/sql_generator.py` (_clean_sql, _ensure_limit methods)

**Test scenarios:**
- Happy path: Generate valid SQL on first attempt (confidence=0.9)
- Happy path: Generate valid SQL on second attempt after validation failure (confidence=0.75)
- Happy path: Generate valid SQL on third attempt (confidence=0.6)
- Error path: All 3 attempts fail validation → return error with low_confidence=True
- Edge case: Empty question → raise ValueError
- Edge case: Invalid schema format → handle gracefully
- Integration: Self-critique catches column hallucination (e.g., "idastank_count" → "id")
- Integration: Self-critique catches table name errors
- Integration: Self-critique catches missing JOIN conditions

**Verification:**
- Self-critique loop reduces column hallucination rate by 50% (measured via test cases)
- Confidence scores decay correctly across retry attempts
- Validation feedback is specific enough to guide regeneration
- Token usage is logged for cost tracking

- [x] **Unit 3: Orchestrator Agent with Simple Routing**

**Goal:** Implement Orchestrator agent that analyzes query complexity and routes to appropriate agents (currently only SQL Generation, but extensible for future agents).

**Requirements:** R3, R4

**Dependencies:** Unit 2 (SQL Generation agent)

**Files:**
- Create: `agents/orchestrator.py`
- Modify: `agents/models/agent_models.py` (add orchestration models)
- Test: `tests/agents/test_orchestrator.py`

**Approach:**
- Inherit from base agent class
- Simple routing logic for Phase 1: all queries → SQL Generation agent
- Extensible routing framework for Phase 2-3 (query complexity analysis, agent team formation)
- Conflict resolution placeholder (not used in Phase 1, but interface defined)
- Escalation logic: if SQL Generation returns low_confidence=True, escalate to human
- Pass-through for agent responses (no transformation in Phase 1)

**Patterns to follow:**
- Pipeline orchestration pattern from `services/chatbot_pipeline.py` (stage-by-stage execution with timing)
- Error handling pattern from `services/chatbot_pipeline.py` (categorize exceptions, route appropriately)

**Test scenarios:**
- Happy path: Route simple query to SQL Generation agent → return successful response
- Happy path: Route complex query to SQL Generation agent → return successful response
- Error path: SQL Generation returns low_confidence=True → escalate with clear error message
- Error path: SQL Generation raises exception → catch and return error response
- Edge case: Empty question → validate before routing
- Integration: Orchestrator correctly passes schema to SQL Generation agent
- Integration: Orchestrator preserves confidence scores from SQL Generation agent

**Verification:**
- All queries route to SQL Generation agent successfully
- Escalation logic triggers correctly for low-confidence responses
- Orchestrator adds minimal latency overhead (<50ms)
- Error messages are clear and actionable

- [x] **Unit 4: Integration with Existing Chatbot Pipeline**

**Goal:** Integrate the new multi-agent system into the existing chatbot pipeline as an alternative to the current single-LLM approach.

**Requirements:** R1, R2, R3

**Dependencies:** Unit 3 (Orchestrator agent)

**Files:**
- Create: `services/multi_agent_pipeline.py`
- Modify: `api/routes.py` (add new endpoint `/v1/ask/multi-agent`)
- Modify: `tests/test_api_endpoints.py` (add tests for new endpoint)
- Test: `tests/integration/test_multi_agent_pipeline.py`

**Approach:**
- Create new `multi_agent_pipeline.py` with `ask()` function matching existing pipeline signature
- New endpoint `/v1/ask/multi-agent` uses multi-agent pipeline
- Existing `/v1/ask` endpoint unchanged (backward compatibility)
- Both pipelines return same response structure (AnswerResponse model)
- Multi-agent pipeline calls Orchestrator → SQL Generation → existing sql_executor and answer_formatter
- Feature flag in environment variable to switch default pipeline (future)

**Patterns to follow:**
- Pipeline structure from `services/chatbot_pipeline.py` (6-stage pattern, timing, error handling)
- API endpoint pattern from `api/routes.py` (authentication, rate limiting, error responses)
- Integration test pattern from `tests/test_integration.py` (skip if services not configured)

**Test scenarios:**
- Happy path: Multi-agent pipeline generates correct SQL and returns formatted answer
- Happy path: Multi-agent pipeline handles simple query (e.g., "How many ISO tanks?")
- Happy path: Multi-agent pipeline handles complex query with JOIN
- Error path: Multi-agent pipeline handles validation failure gracefully
- Error path: Multi-agent pipeline handles AI provider failure
- Integration: New endpoint requires authentication (JWT token)
- Integration: New endpoint respects rate limiting (20 req/min)
- Integration: Response structure matches existing `/v1/ask` endpoint

**Verification:**
- New endpoint returns same response structure as existing endpoint
- Multi-agent pipeline reduces SQL errors by 50% compared to single-LLM (measured via test suite)
- Backward compatibility: existing `/v1/ask` endpoint unchanged
- Integration tests pass with real database and AI provider

## System-Wide Impact

**Interaction graph:**
- New `agents/` module is independent - no callbacks or middleware affected
- `services/multi_agent_pipeline.py` calls existing `sql_executor` and `answer_formatter` services
- New API endpoint `/v1/ask/multi-agent` uses existing authentication and rate limiting middleware

**Error propagation:**
- Agent errors propagate through Orchestrator → multi_agent_pipeline → API endpoint
- Existing error handling in `api/routes.py` catches and formats agent errors
- No changes to existing error response structure

**State lifecycle risks:**
- Agents are stateless (no shared state between requests)
- Retry logic is per-request (no cross-request state)
- Cache protocol defined but not implemented (Phase 2 concern)

**API surface parity:**
- New endpoint `/v1/ask/multi-agent` matches existing `/v1/ask` response structure
- Both endpoints use same authentication, rate limiting, and error handling
- No breaking changes to existing API

**Integration coverage:**
- Integration tests verify multi-agent pipeline with real database and AI provider
- Integration tests verify new endpoint with authentication and rate limiting
- Unit tests verify agent behavior in isolation (mocked dependencies)

**Unchanged invariants:**
- Existing `/v1/ask` endpoint behavior unchanged
- Existing authentication and rate limiting unchanged
- Existing database schema and permissions unchanged
- Existing AI provider configuration unchanged

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Self-critique loop adds latency (2-3 AI calls vs 1) | Acceptable for Phase 1 - focus is correctness over speed. Optimize in Phase 2 with schema pruning (reduces token count by 95%). Monitor p95 latency and set alert at 5s. |
| Confidence decay formula may need tuning | Start with linear decay (0.15 per attempt). Log confidence scores and retry counts to inform tuning. Adjust in Phase 2 based on production data. |
| Retry logic may not converge for some queries | Max 3 attempts with escalation to human. Log non-converging queries for analysis. May need query refinement (Phase 3) for ambiguous questions. |
| Integration with existing pipeline may have edge cases | Comprehensive integration tests with real services. Run both pipelines in parallel for 2 weeks (A/B test) before switching default. |
| Pydantic validation overhead | Negligible compared to AI call latency (ms vs seconds). Benefit of type safety outweighs cost. |

## Documentation / Operational Notes

**Documentation updates:**
- Add `agents/README.md` explaining agent architecture and how to add new agents
- Update `README.md` with new endpoint `/v1/ask/multi-agent`
- Add docstrings to all agent classes and methods

**Operational notes:**
- New endpoint uses same database and AI provider as existing endpoint (no new infrastructure)
- Monitor token usage - self-critique loop uses 2-3x tokens per query
- Log retry counts and confidence scores for analysis
- Set up alerts for high retry rates (>30% of queries require retry)

**Rollout plan:**
- Phase 1: Deploy new endpoint `/v1/ask/multi-agent` alongside existing endpoint
- Week 1-2: A/B test with 10% traffic to new endpoint
- Week 3-4: Increase to 50% traffic if error rate <5%
- Week 5+: Switch default to multi-agent pipeline if success metrics met

## Success Metrics

**Accuracy metrics (from origin document):**
- SQL Accuracy: ≥95% of queries generate syntactically correct SQL (up from ~80%)
- Column Hallucination: <10% of queries contain non-existent columns (down from ~20%, target <5% by Phase 2)
- Self-Correction Rate: ≥50% of validation failures fixed on retry

**Performance metrics:**
- Latency (p95): <5 seconds end-to-end (acceptable for Phase 1, optimize in Phase 2)
- Retry Rate: <30% of queries require retry (indicates good first-attempt accuracy)
- Escalation Rate: <5% of queries escalated to human (indicates self-correction is working)

**Cost metrics:**
- Cost per Query: <$0.002 (2-3x current cost due to retries, acceptable for Phase 1)
- Token Usage: Log and monitor for optimization opportunities

## Sources & References

- **Origin document:** [docs/brainstorms/multi-agent-text-to-sql-requirements.md](docs/brainstorms/multi-agent-text-to-sql-requirements.md)
- **Related code:**
  - `services/chatbot_pipeline.py` - Current pipeline orchestration
  - `services/sql_generator.py` - Existing SQL generation
  - `config/ai_provider.py` - AI provider abstraction
  - `tests/test_chatbot_pipeline.py` - Testing patterns
- **Research papers:**
  - MAC-SQL: Multi-Agent Collaboration for Text-to-SQL (Wang et al., COLING 2025)
  - MARS-SQL: Multi-Agent Reinforcement Learning Framework (arXiv 2511.01008)
  - AgentiQL: Agent-Inspired Multi-Expert Framework (arXiv 2510.10661v2)
- **External docs:**
  - Pydantic V2 documentation: https://docs.pydantic.dev/latest/
