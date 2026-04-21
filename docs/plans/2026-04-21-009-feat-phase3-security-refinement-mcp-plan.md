---
title: Phase 3 - Security & Governance, Query Refinement, and MCP Integration
type: feat
status: active
date: 2026-04-21
origin: docs/brainstorms/multi-agent-text-to-sql-requirements.md
---

# Phase 3 - Security & Governance, Query Refinement, and MCP Integration

## Overview

Implement Phase 3 of the multi-agent text-to-SQL system: Security & Governance Agent with veto power, Query Refinement Agent with business glossary, and MCP (Model Context Protocol) integration for database operations. This phase adds critical security controls, business domain understanding, and standardizes database access through MCP.

## Problem Frame

Phase 1 and Phase 2 delivered SQL generation with self-critique and schema intelligence. However, the system still lacks:

1. **Security governance** - No RBAC enforcement, PII detection, or dangerous operation blocking
2. **Business domain understanding** - Cannot resolve temporal ambiguity ("this month") or map business terminology ("clients" → table.column)
3. **Standardized database layer** - Direct PostgreSQL calls scattered across codebase, no connection pooling, inconsistent error handling

Phase 3 addresses these gaps by adding two new agents and migrating to MCP as the database execution layer.

## Requirements Trace

From origin document (docs/brainstorms/multi-agent-text-to-sql-requirements.md):

- R1. Security & Governance Agent must have **unconditional veto power** to halt pipeline
- R2. Block 100% of dangerous operations (DROP, DELETE, UPDATE, INSERT, ALTER, TRUNCATE, GRANT, REVOKE)
- R3. Block 100% of PII exposure attempts (driver_mobile_number, license_number, visitor.mobile_number, email)
- R4. Enforce role-based access control (admin, analyst, viewer roles)
- R5. Query Refinement Agent must resolve temporal ambiguity ("this month" → DATE_TRUNC)
- R6. Map business terminology to database concepts using business glossary
- R7. All database operations must go through MCP layer (no direct psycopg2 calls)
- R8. MCP integration must provide schema introspection, query validation, and query execution
- R9. Maintain backward compatibility with existing agents (Orchestrator, Schema Intelligence, SQL Generation)

## Scope Boundaries

**In scope:**
- Security & Governance Agent with policy-based validation (no LLM calls)
- Query Refinement Agent with LLM-based query transformation
- MCP client wrapper for database operations
- Configuration files for business glossary and security policies
- Pydantic models for security and refinement
- Unit tests for new agents
- Integration tests for Phase 3 pipeline

**Out of scope (deferred to Phase 4):**
- Result Formatter Agent (executes SQL and formats results)
- Full end-to-end pipeline integration
- Performance optimization and caching tuning
- Monitoring and observability
- Production deployment

### Deferred to Separate Tasks

- MCP server installation and configuration (user/ops responsibility, not code)
- Database schema changes or migrations
- Frontend UI changes
- API endpoint modifications (handled in Phase 4 integration)

## Context & Research

### Relevant Code and Patterns

**Existing agent implementations:**
- `agents/base.py` - BaseAgent abstract class with execute() method, logging, timing
- `agents/orchestrator.py` - Orchestrator with routing logic, confidence threshold (0.6), escalation
- `agents/schema_intelligence.py` - Entity extraction, graph traversal, schema pruning, caching
- `agents/sql_generation.py` - Self-critique loop, validation, retry with confidence decay
- `agents/cache.py` - InMemoryCache with TTL and LRU eviction

**Existing models:**
- `agents/models/agent_models.py` - AgentRequest, AgentResponse base models
- `agents/models/query_models.py` - SQLGenerationRequest, SQLGenerationResponse
- `agents/models/schema_models.py` - SchemaIntelligenceRequest, SchemaIntelligenceResponse

**Configuration patterns:**
- `config/ai_provider.py` - Swappable AI provider (OpenAI-compatible, Anthropic)
- `config/logging_config.py` - Structured logging with get_logger()
- Environment variables in `.env` for API keys, model names, database credentials

**Testing patterns:**
- `tests/agents/` - Unit tests with pytest, mocking, fixtures
- `tests/integration/` - Integration tests with real database
- `tests/fixtures/` - Shared test data and mocks

### Institutional Learnings

None found (learnings-researcher agent not available).

### External References

From origin document:
- [Agentic Text-to-SQL (nirmalya.net, 2026)](https://www.nirmalya.net/posts/2026/03/agentic-text-to-sql/) - Five-agent architecture with security veto
- [Multi-Agent System for Text-to-SQL (ClickIT Tech, 2025)](https://www.clickittech.com/ai/multi-agent-system-for-text-to-sql/) - LangChain + LangGraph implementation
- MCP (Model Context Protocol) documentation for database operations

## Key Technical Decisions

**Decision 1: Security Agent uses policy-based validation (no LLM)**
- **Rationale:** Security decisions must be deterministic and auditable. LLM-based security would introduce non-determinism and potential bypasses. Policy-based validation is faster, cheaper, and more reliable.

**Decision 2: Query Refinement Agent uses LLM with business glossary**
- **Rationale:** Temporal ambiguity and business terminology mapping require semantic understanding. LLM can interpret "this month" → DATE_TRUNC and "clients" → vehicle_in.croyance_client_name using glossary as context.

**Decision 3: MCP client wrapper instead of direct MCP SDK usage**
- **Rationale:** Wrap MCP SDK in `agents/mcp_client.py` to provide consistent error handling, logging, and retry logic. Agents call wrapper methods (get_schema, validate_query, execute_query) instead of raw MCP SDK.

**Decision 4: YAML configuration files for business glossary and security policies**
- **Rationale:** Non-developers (domain experts, security team) can update glossary and policies without code changes. YAML is human-readable and version-controlled.

**Decision 5: Security Agent runs after Query Refinement**
- **Rationale:** Security validation needs the refined query (explicit intent) to detect PII exposure and dangerous operations. Running before refinement would miss semantic threats.

**Decision 6: Defer MCP server installation to user/ops**
- **Rationale:** MCP server setup (uvx mcp-server-postgres) is environment-specific and requires database credentials. Code assumes MCP server is configured and running.

## Open Questions

### Resolved During Planning

**Q1: Should Security Agent validate SQL or refined query?**
- **Resolution:** Validate both. Check refined query for semantic threats (PII column names), then validate generated SQL for syntax threats (DROP, DELETE keywords).

**Q2: How to handle MCP connection failures?**
- **Resolution:** MCP client wrapper catches connection errors and returns structured error response. Agents propagate error to Orchestrator, which escalates to human.

**Q3: Should Query Refinement run for all queries or only ambiguous ones?**
- **Resolution:** Run for all queries initially. Orchestrator can optimize later by skipping refinement for simple queries (Phase 4 optimization).

**Q4: Where to store business glossary and security policies?**
- **Resolution:** `agents/config/business_glossary.yaml` and `agents/config/security_policies.yaml`. Load at agent initialization, cache in memory.

### Deferred to Implementation

**Q5: Exact MCP error codes and retry strategies**
- **Why deferred:** MCP SDK error types will be discovered during implementation. Wrapper will handle common errors (connection timeout, query timeout, syntax error) with appropriate retry logic.

**Q6: Performance impact of Query Refinement on simple queries**
- **Why deferred:** Measure latency in integration tests. If refinement adds >500ms for simple queries, add Orchestrator optimization to skip refinement (Phase 4).

**Q7: Business glossary completeness**
- **Why deferred:** Start with core terms from origin document (clients, tanks, this_month, tank_status). Expand glossary based on production query patterns.

## Implementation Units

- [ ] **Unit 1: Create Pydantic models for security and refinement**

**Goal:** Define type-safe data structures for Security and Query Refinement agents

**Requirements:** R1, R2, R3, R4, R5, R6

**Dependencies:** None (uses existing agents/models/ structure)

**Files:**
- Create: `agents/models/security_models.py`
- Create: `agents/models/refinement_models.py`
- Test: `tests/agents/test_security_models.py`
- Test: `tests/agents/test_refinement_models.py`

**Approach:**
- `security_models.py` defines SecurityRequest, SecurityResponse, SecurityResult, RiskScore, VetoReason
- SecurityRequest contains refined_query (str), user_role (str), schema (str)
- SecurityResponse contains approved (bool), risk_score (float), veto_reason (Optional[str]), alternative_suggestions (List[str])
- `refinement_models.py` defines RefinementRequest, RefinementResponse, RefinedQuery
- RefinementRequest contains raw_question (str), business_glossary (Dict), current_datetime (datetime)
- RefinementResponse contains refined_query (str), confidence (float), clarification_questions (List[str])

**Patterns to follow:**
- `agents/models/agent_models.py` - BaseModel with Field validators
- `agents/models/query_models.py` - Request/Response pattern extending AgentRequest/AgentResponse

**Test scenarios:**
- Happy path: Valid SecurityRequest with all required fields
- Happy path: Valid RefinementRequest with business glossary
- Edge case: SecurityRequest with empty user_role (should raise ValidationError)
- Edge case: RefinementRequest with empty raw_question (should raise ValidationError)
- Edge case: SecurityResponse with risk_score > 1.0 (should raise ValidationError)
- Edge case: RefinementResponse with confidence < 0.0 (should raise ValidationError)

**Verification:**
- All model fields have correct types and validators
- Pydantic validation catches invalid inputs
- Models serialize/deserialize correctly to JSON
- Test coverage >90% for model validation logic

---

- [ ] **Unit 2: Create configuration files for business glossary and security policies**

**Goal:** Define domain knowledge and security rules in YAML format

**Requirements:** R2, R3, R4, R6

**Dependencies:** None

**Files:**
- Create: `agents/config/business_glossary.yaml`
- Create: `agents/config/security_policies.yaml`
- Create: `agents/config/__init__.py`

**Approach:**
- `business_glossary.yaml` maps business terms to database concepts:
  ```yaml
  temporal_terms:
    this_month: "WHERE created_at >= DATE_TRUNC('month', CURRENT_DATE)"
    last_quarter: "WHERE created_at >= DATE_TRUNC('quarter', CURRENT_DATE - INTERVAL '3 months')"
    today: "WHERE DATE(created_at) = CURRENT_DATE"
  
  entity_mappings:
    clients: "vehicle_in.croyance_client_name"
    tanks: "iso_tank table (for ISO tanks) or service_tank table (for service tanks)"
    tank_status: "iso_tank_status or service_tank_status"
    survey_status: "survey_form_id IS NULL means not surveyed"
  ```

- `security_policies.yaml` defines PII columns, blocked operations, role permissions:
  ```yaml
  pii_columns:
    - vehicle_in.driver_mobile_number
    - vehicle_in.license_number
    - visitor.mobile_number
    - SurakshaClientEmail.email
  
  blocked_operations:
    - DROP
    - DELETE
    - UPDATE
    - INSERT
    - ALTER
    - TRUNCATE
    - GRANT
    - REVOKE
  
  role_permissions:
    admin:
      tables: all
      columns: all
    analyst:
      tables:
        - iso_tank
        - vehicle_in
        - service_tank
      excluded_columns:
        - vehicle_in.driver_mobile_number
        - vehicle_in.license_number
    viewer:
      tables:
        - iso_tank
      columns:
        - tank_number
        - iso_tank_status
        - created_at
  ```

**Patterns to follow:**
- YAML format for human-readable configuration
- Nested structure for logical grouping
- Comments explaining each section

**Test scenarios:**
- Test expectation: none -- configuration files are data, not code. Validation happens in agent initialization.

**Verification:**
- YAML files parse without syntax errors
- All required keys present (pii_columns, blocked_operations, role_permissions)
- Business glossary covers core terms from origin document
- Security policies match requirements R2, R3, R4

---

- [ ] **Unit 3: Implement Security & Governance Agent**

**Goal:** Policy-based security validation with veto power

**Requirements:** R1, R2, R3, R4

**Dependencies:** Unit 1 (security models), Unit 2 (security policies)

**Files:**
- Create: `agents/security_governance.py`
- Test: `tests/agents/test_security_governance.py`

**Approach:**
- SecurityGovernanceAgent extends BaseAgent
- Load security_policies.yaml at initialization, cache in memory
- execute() method takes SecurityRequest, returns SecurityResponse
- Validation checks (in order):
  1. Check for dangerous operations (DROP, DELETE, etc.) in refined query and SQL
  2. Check for PII column access based on user role
  3. Validate user role has permission for requested tables
  4. Calculate risk score based on checks
  5. Return approved=True if all checks pass, approved=False with veto_reason if any check fails
- No LLM calls - pure policy-based validation
- Risk scoring: risk_score = 0.0 baseline, +0.5 for PII, +0.2 for cross-domain JOIN, +0.1 for large result set, 1.0 for dangerous operation (automatic block)

**Patterns to follow:**
- `agents/base.py` - BaseAgent with execute(), logging, timing
- `agents/sql_generation.py` - Validation logic with issue collection

**Test scenarios:**
- Happy path: Valid SELECT query with no PII, user has permission → approved=True, risk_score=0.0
- Happy path: Valid SELECT query with allowed columns for analyst role → approved=True
- Error path: Query contains DROP keyword → approved=False, veto_reason="Dangerous operation: DROP", risk_score=1.0
- Error path: Query accesses PII column (driver_mobile_number) for analyst role → approved=False, veto_reason="PII access denied"
- Error path: Query accesses table not in viewer role permissions → approved=False, veto_reason="Unauthorized table access"
- Edge case: Query with multiple violations → approved=False, veto_reason lists all violations
- Edge case: Empty refined query → approved=False, veto_reason="Empty query"
- Integration: Security agent blocks SQL injection attempt ("'; DROP TABLE iso_tank; --")

**Verification:**
- All dangerous operations blocked (100% block rate)
- All PII access attempts blocked for non-admin roles
- RBAC enforced correctly for all roles (admin, analyst, viewer)
- Risk score calculated correctly
- Veto reason provides actionable feedback
- Test coverage >95% for security validation logic

---

- [ ] **Unit 4: Implement Query Refinement Agent**

**Goal:** LLM-based query transformation with business glossary

**Requirements:** R5, R6

**Dependencies:** Unit 1 (refinement models), Unit 2 (business glossary)

**Files:**
- Create: `agents/query_refinement.py`
- Test: `tests/agents/test_query_refinement.py`

**Approach:**
- QueryRefinementAgent extends BaseAgent
- Load business_glossary.yaml at initialization, cache in memory
- execute() method takes RefinementRequest, returns RefinementResponse
- Build system prompt with business glossary context
- Call AI provider (OpenAI-compatible or Anthropic) to refine query
- System prompt instructs LLM to:
  1. Resolve temporal ambiguity using temporal_terms from glossary
  2. Map business terminology to database concepts using entity_mappings
  3. Clarify ambiguous intent (if needed, return clarification_questions)
  4. Output refined query with explicit intent
- Confidence score based on LLM response quality (0.9 if clear, 0.7 if ambiguous, 0.5 if clarification needed)
- Temperature: 0.3 (balance between determinism and creativity)

**Patterns to follow:**
- `agents/sql_generation.py` - AI provider integration, system prompt building
- `config/ai_provider.py` - Swappable AI provider (OpenAI-compatible, Anthropic)

**Test scenarios:**
- Happy path: "Which clients have the most tanks this month?" → refined query with DATE_TRUNC and croyance_client_name
- Happy path: "Show me tanks" → refined query specifying iso_tank table
- Happy path: "How many tanks came in today?" → refined query with DATE(created_at) = CURRENT_DATE
- Edge case: Ambiguous query "best products" → confidence=0.5, clarification_questions=["By revenue or quantity?"]
- Edge case: Query with no business terms → refined query unchanged, confidence=0.9
- Error path: AI provider error → RefinementResponse with success=False, error message
- Integration: Refinement agent resolves "last quarter" to DATE_TRUNC('quarter', CURRENT_DATE - INTERVAL '3 months')

**Verification:**
- Temporal ambiguity resolved correctly (this month, last quarter, today)
- Business terminology mapped to database concepts
- Clarification questions returned for ambiguous queries
- Confidence score reflects query clarity
- AI provider errors handled gracefully
- Test coverage >90% for refinement logic

---

- [ ] **Unit 5: Implement MCP client wrapper**

**Goal:** Standardized database operations through MCP

**Requirements:** R7, R8

**Dependencies:** None (MCP server assumed configured)

**Files:**
- Create: `agents/mcp_client.py`
- Test: `tests/agents/test_mcp_client.py`

**Approach:**
- MCPClient class wraps MCP SDK for database operations
- Methods:
  - `get_schema(table_name: Optional[str] = None) -> str` - Returns schema description (all tables or specific table)
  - `validate_query(sql: str) -> ValidationResult` - Dry-run validation, returns syntax errors and suggestions
  - `execute_query(sql: str) -> QueryResult` - Executes SQL, returns rows and metadata
- Connection management:
  - Initialize MCP connection at client creation
  - Automatic reconnection on connection failures (max 3 retries)
  - Connection pooling handled by MCP server
- Error handling:
  - Catch MCP SDK exceptions (ConnectionError, QueryError, TimeoutError)
  - Return structured error responses with helpful messages
  - Log all errors with request ID for tracing
- Configuration:
  - Read MCP server config from environment variables (MCP_SERVER_URL, MCP_DATABASE_NAME)
  - Default timeout: 30 seconds for queries, 10 seconds for validation

**Patterns to follow:**
- `config/ai_provider.py` - Client initialization with environment variables
- `agents/base.py` - Structured error handling with logging

**Test scenarios:**
- Happy path: get_schema() returns formatted schema string
- Happy path: get_schema("iso_tank") returns schema for specific table
- Happy path: validate_query("SELECT * FROM iso_tank") returns valid=True
- Happy path: execute_query("SELECT COUNT(*) FROM iso_tank") returns QueryResult with rows
- Error path: validate_query("SELECT * FROM nonexistent_table") returns valid=False with error message
- Error path: execute_query with syntax error → QueryError with helpful message
- Error path: MCP connection failure → ConnectionError, retry 3 times, then fail with error
- Edge case: Query timeout (>30s) → TimeoutError with suggestion to simplify query
- Integration: MCP client connects to real MCP server and executes query

**Verification:**
- All database operations go through MCP client (no direct psycopg2 calls)
- Schema introspection returns correct format
- Query validation catches syntax errors
- Query execution returns correct results
- Connection failures handled with retries
- Timeouts handled gracefully
- Test coverage >85% for MCP client logic (mock MCP SDK for unit tests)

---

- [ ] **Unit 6: Update Orchestrator to route through Security and Refinement agents**

**Goal:** Integrate new agents into orchestration pipeline

**Requirements:** R1, R5, R9

**Dependencies:** Unit 3 (Security Agent), Unit 4 (Refinement Agent)

**Files:**
- Modify: `agents/orchestrator.py`
- Test: `tests/agents/test_orchestrator.py`

**Approach:**
- Update Orchestrator routing logic to include Security and Refinement agents
- New pipeline: Refinement → Security → Schema Intelligence → SQL Generation → (Result Formatter in Phase 4)
- Routing logic:
  1. Call Query Refinement agent with raw question
  2. Call Security agent with refined query and user role
  3. If Security agent returns approved=False, escalate to human with veto reason
  4. If approved=True, continue to Schema Intelligence (existing)
  5. Continue to SQL Generation (existing)
- Add user_role parameter to AgentRequest (default: "viewer")
- Pass refined query to downstream agents instead of raw question
- Update metadata to include refinement_confidence and security_risk_score

**Patterns to follow:**
- Existing `_route_with_schema_intelligence()` method pattern
- Existing escalation logic in `_escalate_to_human()`

**Test scenarios:**
- Happy path: Simple query → Refinement → Security (approved) → Schema Intelligence → SQL Generation
- Happy path: Query with temporal ambiguity → Refinement resolves → Security approves → continues
- Error path: Query with dangerous operation → Refinement → Security (blocked) → escalate to human
- Error path: Query accessing PII → Refinement → Security (blocked) → escalate with veto reason
- Edge case: Refinement agent returns low confidence → continue but log warning
- Edge case: Security agent returns high risk score but approved → continue with warning
- Integration: Full pipeline with all agents (Refinement → Security → Schema → SQL)

**Verification:**
- Orchestrator routes through all Phase 3 agents
- Security veto halts pipeline immediately
- Refined query passed to downstream agents
- Metadata includes all agent outputs
- Escalation messages include veto reasons
- Test coverage >90% for new routing logic

---

- [ ] **Unit 7: Update Schema Intelligence Agent to use MCP client**

**Goal:** Replace direct schema introspection with MCP

**Requirements:** R7, R8, R9

**Dependencies:** Unit 5 (MCP client)

**Files:**
- Modify: `agents/schema_intelligence.py`
- Test: `tests/agents/test_schema_intelligence.py`

**Approach:**
- Replace schema parsing logic with MCP client calls
- In `_build_fk_graph()`, call `mcp_client.get_schema()` instead of parsing schema string
- MCP returns structured schema with foreign key relationships
- Update graph building to use MCP schema format
- Keep existing entity extraction, graph traversal, and pruning logic
- Add error handling for MCP connection failures (fall back to full schema if MCP unavailable)

**Patterns to follow:**
- Existing `_build_fk_graph()` method structure
- Existing error handling with fallback to full schema

**Test scenarios:**
- Happy path: MCP client returns schema → graph built correctly
- Happy path: Foreign key relationships extracted from MCP schema
- Error path: MCP connection failure → fall back to full schema, log warning
- Edge case: MCP returns empty schema → return full schema with low confidence
- Integration: Schema Intelligence uses MCP client with real database

**Verification:**
- Schema Intelligence uses MCP client for schema introspection
- No direct schema parsing (except fallback)
- Foreign key relationships extracted correctly
- MCP errors handled gracefully
- Test coverage maintained at >90%

---

- [ ] **Unit 8: Update SQL Generation Agent to use MCP validation**

**Goal:** Use MCP query validation in self-critique loop

**Requirements:** R7, R8, R9

**Dependencies:** Unit 5 (MCP client)

**Files:**
- Modify: `agents/sql_generation.py`
- Test: `tests/agents/test_sql_generation.py`

**Approach:**
- In `_validate_sql()`, call `mcp_client.validate_query(sql)` before custom validation
- MCP validation catches syntax errors, invalid table/column references
- Combine MCP validation results with existing safety checks (dangerous keywords, LIMIT clause)
- If MCP validation fails, include MCP error message in validation_issues for retry feedback
- Keep existing validation logic as additional safety layer

**Patterns to follow:**
- Existing `_validate_sql()` method structure
- Existing retry loop with validation feedback

**Test scenarios:**
- Happy path: MCP validation passes → continue with safety checks
- Happy path: MCP validation catches syntax error → add to validation_issues, retry
- Error path: MCP validation fails with table not found → retry with error feedback
- Error path: MCP connection failure → fall back to custom validation only, log warning
- Integration: SQL Generation uses MCP validation in self-critique loop

**Verification:**
- SQL Generation uses MCP validation before custom checks
- MCP validation errors included in retry feedback
- MCP errors handled gracefully with fallback
- Test coverage maintained at >90%

---

- [ ] **Unit 9: Integration tests for Phase 3 pipeline**

**Goal:** Verify end-to-end Phase 3 agent interactions

**Requirements:** All Phase 3 requirements

**Dependencies:** All previous units

**Files:**
- Create: `tests/integration/test_phase3_pipeline.py`

**Approach:**
- Test full pipeline: Refinement → Security → Schema Intelligence → SQL Generation
- Use real MCP client with test database
- Test scenarios covering happy path, security blocks, refinement edge cases
- Measure latency and verify <3s p95 target
- Verify security blocks work correctly (dangerous operations, PII access)
- Verify refinement resolves temporal ambiguity and business terminology

**Patterns to follow:**
- `tests/integration/test_multi_agent_pipeline.py` - Integration test structure

**Test scenarios:**
- Happy path: "Which clients have the most tanks this month?" → refined → approved → schema pruned → SQL generated
- Happy path: "Show me tanks" → refined to iso_tank → approved → SQL generated
- Error path: "DROP TABLE iso_tank" → refined → blocked by Security → escalated
- Error path: "Show me all driver license numbers" → refined → blocked by Security (PII) → escalated
- Error path: Analyst role accessing admin-only table → blocked by Security → escalated
- Edge case: Ambiguous query → refined with clarification questions → continues if user provides clarification
- Integration: Full pipeline with all agents, real MCP client, real database

**Verification:**
- All Phase 3 agents work together correctly
- Security blocks dangerous operations and PII access
- Refinement resolves temporal ambiguity and business terminology
- Pipeline latency <3s at p95
- Test coverage >85% for integration scenarios

---

## System-Wide Impact

**Interaction graph:**
- Query Refinement Agent → Security Agent (refined query input)
- Security Agent → Schema Intelligence Agent (security approval gates continuation)
- Security Agent → Orchestrator (veto halts pipeline, escalates to human)
- MCP Client → Schema Intelligence Agent (schema introspection)
- MCP Client → SQL Generation Agent (query validation)
- Orchestrator → All agents (routing and coordination)

**Error propagation:**
- Security veto → Orchestrator escalation → User receives veto reason and alternative suggestions
- MCP connection failure → Agent fallback → Log warning, continue with degraded functionality
- Refinement low confidence → Continue but log warning → May trigger clarification questions
- AI provider error in Refinement → Return error response → Orchestrator escalates

**State lifecycle risks:**
- Security policies loaded at agent initialization → Changes require agent restart (acceptable for Phase 3)
- Business glossary loaded at agent initialization → Changes require agent restart (acceptable for Phase 3)
- MCP connection state → Automatic reconnection on failure, max 3 retries
- Cache invalidation → Schema Intelligence cache TTL 5 minutes (existing, no change)

**API surface parity:**
- AgentRequest/AgentResponse interface unchanged → Backward compatible with Phase 1/2 agents
- New SecurityRequest/RefinementRequest extend AgentRequest → Compatible with existing patterns
- MCP client wrapper provides consistent interface → Easy to swap MCP implementation later

**Integration coverage:**
- Unit tests cover individual agent logic
- Integration tests cover cross-agent interactions (Refinement → Security → Schema → SQL)
- Adversarial tests cover security bypass attempts (SQL injection, PII access)
- Performance tests measure latency impact of new agents

**Unchanged invariants:**
- BaseAgent interface (execute method signature)
- AgentRequest/AgentResponse structure
- Orchestrator confidence threshold (0.6)
- Schema Intelligence caching strategy (TTL 5 minutes)
- SQL Generation retry logic (max 2 retries, confidence decay)

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| MCP server not configured or unavailable | MCP client wrapper provides fallback to existing logic (direct schema parsing, custom validation). Log warnings for ops team. |
| Security policies too restrictive (high false positive rate) | Start with permissive policies, tighten based on production data. Monitor security_block_rate metric (alert if >20%). |
| Query Refinement adds latency (>500ms) | Measure in integration tests. If too slow, add Orchestrator optimization to skip refinement for simple queries (Phase 4). |
| Business glossary incomplete | Start with core terms from origin document. Expand based on production query patterns. Log unmatched terms for review. |
| AI provider rate limits for Refinement | Use low temperature (0.3) and short max_tokens (300) to reduce cost. Cache refined queries by hash (future optimization). |
| Security Agent veto too aggressive | Provide alternative suggestions in veto reason. Monitor escalation_rate metric (alert if >10%). |

## Documentation / Operational Notes

**Configuration required:**
- MCP server must be configured and running (see origin document for MCP server configuration)
- Environment variables: MCP_SERVER_URL, MCP_DATABASE_NAME
- Business glossary and security policies in `agents/config/` (version controlled)

**Monitoring:**
- Add metrics: security_block_rate, refinement_latency, mcp_connection_failures
- Alert if security_block_rate >20% (possible policy issue)
- Alert if refinement_latency >500ms (performance issue)
- Alert if mcp_connection_failures >5% (infrastructure issue)

**Rollout:**
- Phase 3 agents integrated into Orchestrator but not exposed via API yet (Phase 4)
- Test in development environment with real database
- Validate security policies with security team before production
- Validate business glossary with domain experts before production

**Backward compatibility:**
- Existing agents (Schema Intelligence, SQL Generation) continue to work
- Orchestrator routing updated but maintains existing confidence threshold and escalation logic
- No API changes in Phase 3 (API integration in Phase 4)

## Sources & References

- **Origin document:** [docs/brainstorms/multi-agent-text-to-sql-requirements.md](docs/brainstorms/multi-agent-text-to-sql-requirements.md)
- Related code: `agents/base.py`, `agents/orchestrator.py`, `agents/schema_intelligence.py`, `agents/sql_generation.py`
- External docs: [Agentic Text-to-SQL (nirmalya.net, 2026)](https://www.nirmalya.net/posts/2026/03/agentic-text-to-sql/)
- External docs: MCP (Model Context Protocol) documentation
