---
title: "feat: Admin AI Chatbot Phase 2 - SQL Generation and Execution Pipeline"
type: feat
status: active
date: 2026-04-20
origin: ai-service-croyance/docs/brainstorms/admin-chatbot-phase2-requirements.md
---

# feat: Admin AI Chatbot Phase 2 - SQL Generation and Execution Pipeline

## Overview

Build the core intelligence pipeline that translates natural language questions into SQL queries, validates safety, executes them against the database, and formats results into human-readable answers. This phase transforms the Phase 1 foundation (database access, AI provider config) into a working chatbot capable of answering business questions.

## Problem Frame

Admins need to query business data without writing SQL. The system must generate accurate SQL from natural language, prevent dangerous operations, handle errors gracefully, and return clear answers. The pipeline must be transparent (always show the SQL used) and safe (block all write operations).

## Requirements Trace

- R1. Generate accurate SQL from natural language using few-shot prompting (FR1)
- R2. Validate all table/column references exist before execution (FR2)
- R3. Block all write operations and SQL injection attempts (FR3)
- R4. Execute queries with 60-second timeout and proper error handling (FR4)
- R5. Format results into natural language summaries (FR5)
- R6. Orchestrate the complete pipeline with logging and error handling (FR6)
- R7. Achieve 80%+ SQL accuracy on realistic questions (Success Criteria)
- R8. Block 100% of adversarial inputs (Success Criteria)
- R9. Complete 90% of queries in under 5 seconds (Success Criteria)

## Scope Boundaries

**In scope:**
- SQL generation with few-shot examples
- Pre-validation of table/column names
- Safety guards (blocklist + whitelist)
- Query execution with timeout
- Answer formatting with AI
- Pipeline orchestration
- Comprehensive test suite

**Out of scope:**
- Query optimization (rely on database indexes)
- Result caching (defer to Phase 5)
- Multi-turn conversations (each question is independent)
- Natural language follow-ups
- API endpoints (Phase 3)
- Frontend UI (Phase 4)

## Context & Research

### Relevant Code and Patterns

**Phase 1 Foundation:**
- `services/schema.py` - Database schema introspection with connection pooling
- `config/ai_provider.py` - Swappable AI client (OpenAI-compatible and Anthropic SDKs)
- `tests/test_ai_provider.py` - Test patterns for AI integration

**Patterns to follow:**
- Connection pooling pattern from `SchemaIntrospector` class
- Environment variable validation from `ai_provider.py`
- Error handling with specific exception types
- Test structure with pytest and environment-based skipping

**Technology stack:**
- Python 3.9+
- psycopg2 for PostgreSQL access
- OpenAI SDK (openai>=1.14.0) for OpenAI-compatible providers
- Anthropic SDK (anthropic>=0.21.0) for Claude
- pytest for testing

### Institutional Learnings

None identified - this is a greenfield AI service.

### External References

None required - the requirements document provides sufficient technical direction based on established SQL safety patterns and AI prompt engineering best practices.

## Key Technical Decisions

**Decision:** Use few-shot prompting with 3-5 examples instead of zero-shot
**Rationale:** Reduces AI hallucination of non-existent tables/columns, improves JOIN logic, and teaches schema patterns through examples. Trade-off: increases prompt token cost, but accuracy gain justifies it.

**Decision:** Pre-validate table/column names before execution
**Rationale:** Catches AI hallucinations early with clear error messages, prevents wasted database queries. Trade-off: adds latency (~100ms), but error clarity is worth it.

**Decision:** 60-second query timeout
**Rationale:** Allows complex analytical queries while preventing infinite hangs. Trade-off: some legitimate queries may timeout, but 60s is generous for typical admin questions.

**Decision:** Always summarize results with AI, never return raw tables
**Rationale:** Consistent UX, reduces frontend complexity, encourages conversational interaction. Trade-off: admins can't copy/paste result data, but they can see the SQL and run it manually if needed.

**Decision:** Two-layer safety validation (blocklist + whitelist)
**Rationale:** Defense in depth - blocklist catches dangerous keywords, whitelist ensures only SELECT queries pass. Both layers are cheap to run and critical for security.

## Open Questions

### Resolved During Planning

**Q:** Should we retry SQL generation if pre-validation fails?
**A:** No - fail fast on first attempt. If error rate is high in production, add retry logic in Phase 5. Keeps Phase 2 simple.

**Q:** How to handle SQL with subqueries or CTEs in pre-validation?
**A:** Start with simple regex-based extraction for table/column names. If it misses complex queries, enhance in Phase 5 based on real usage patterns.

### Deferred to Implementation

**Q:** Exact few-shot examples to include in the prompt
**Why deferred:** Need to test different examples against the actual tank-depot schema to find the most effective set. Will iterate during implementation.

**Q:** Whether to use SQL parser library or regex for table/column extraction
**Why deferred:** Start with regex (simpler, no dependencies). If accuracy is insufficient, add sqlparse library.

## Output Structure

```
services/
├── __init__.py                 # Existing
├── schema.py                   # Existing (Phase 1)
├── sql_generator.py            # NEW - SQL generation with few-shot prompting
├── sql_validator.py            # NEW - Pre-validation and safety guards
├── sql_executor.py             # NEW - Query execution with timeout
├── answer_formatter.py         # NEW - AI-powered result summarization
└── chatbot_pipeline.py         # NEW - Pipeline orchestrator

tests/
├── test_ai_provider.py         # Existing (Phase 1)
├── test_schema.py              # Existing (Phase 1)
├── test_sql_generator.py       # NEW
├── test_sql_validator.py       # NEW
├── test_sql_executor.py        # NEW
├── test_answer_formatter.py    # NEW
└── test_chatbot_pipeline.py    # NEW - Integration tests

config/
├── __init__.py                 # NEW
├── ai_provider.py              # Existing (Phase 1)
└── logging_config.py           # NEW - Centralized logging setup
```

## Implementation Units

- [x] **Unit 1: Logging Configuration**

**Goal:** Set up centralized logging for audit trail and debugging.

**Requirements:** R6 (pipeline orchestration with logging)

**Dependencies:** None

**Files:**
- Create: `config/__init__.py`
- Create: `config/logging_config.py`
- Test: `tests/test_logging_config.py`

**Approach:**
- Configure Python logging to write to `logs/chat_audit.log`
- Use rotating file handler (max 10MB per file, keep 5 backups)
- Log format: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`
- Expose `get_logger(name)` function for consistent logger creation
- Create logs directory if it doesn't exist

**Patterns to follow:**
- Environment variable validation pattern from `config/ai_provider.py`

**Test scenarios:**
- Happy path: Logger writes to file successfully
- Happy path: Log rotation works when file exceeds 10MB
- Edge case: Logs directory doesn't exist - should create it automatically
- Edge case: Logs directory is not writable - should raise clear error

**Verification:**
- Import `get_logger` and write test log entries
- Verify `logs/chat_audit.log` is created with correct format
- Verify log rotation creates backup files

- [x] **Unit 2: SQL Generator Service**

**Goal:** Generate SQL queries from natural language using AI with few-shot examples.

**Requirements:** R1 (SQL generation with few-shot prompting), R7 (80%+ accuracy)

**Dependencies:** Unit 1 (logging)

**Files:**
- Create: `services/sql_generator.py`
- Test: `tests/test_sql_generator.py`

**Approach:**
- Create `SQLGenerator` class with `generate_sql(question: str, schema: str) -> str` method
- Build system prompt with schema description + 3-5 few-shot examples
- Few-shot examples cover: COUNT, JOIN, GROUP BY, date filtering, ORDER BY + LIMIT
- Use `ai_client` from `config/ai_provider.py` with SDK-specific call patterns
- For OpenAI-compatible: `client.chat.completions.create(model=model_name, messages=[...])`
- For Anthropic: `client.messages.create(model=model_name, messages=[...])`
- Extract SQL from response (strip markdown code blocks if present)
- Always append `LIMIT 100` if not present
- Log: question, generated SQL, token usage
- Handle API failures with retry (once) then raise `SQLGenerationError`

**Patterns to follow:**
- SDK type detection from `config/ai_provider.py`
- Connection pooling pattern from `services/schema.py`
- Error handling with custom exception types

**Test scenarios:**
- Happy path: Generate SQL for "How many ISO tanks are in 'IN' status?" → `SELECT COUNT(*) FROM iso_tank WHERE iso_tank_status = 'IN' LIMIT 100`
- Happy path: Generate SQL for "Which clients have the most tanks?" → includes JOIN, GROUP BY, ORDER BY, LIMIT
- Happy path: SQL without LIMIT gets LIMIT 100 appended automatically
- Edge case: Empty question → raise `ValueError` with clear message
- Edge case: AI returns markdown code block → strip backticks and language tag
- Error path: AI API failure → retry once, then raise `SQLGenerationError`
- Integration: Works with both OpenAI-compatible and Anthropic SDKs

**Verification:**
- Generate SQL for 5 realistic questions from requirements
- Verify all generated SQL includes LIMIT clause
- Verify SQL is syntactically valid (no markdown artifacts)
- Verify logging captures question and SQL

- [x] **Unit 3: SQL Validator Service - Pre-Validation**

**Goal:** Validate that all table and column references in generated SQL exist in the database schema.

**Requirements:** R2 (pre-validate table/column names)

**Dependencies:** Unit 1 (logging)

**Files:**
- Create: `services/sql_validator.py` (part 1 - pre-validation)
- Test: `tests/test_sql_validator.py` (part 1)

**Approach:**
- Create `SQLValidator` class with `validate_references(sql: str, schema: str) -> tuple[bool, str]` method
- Extract table names from SQL using regex: `FROM\s+(\w+)`, `JOIN\s+(\w+)`
- Extract column names from SQL using regex: `SELECT\s+([\w\s,.*]+)`, `WHERE\s+(\w+)`, `ORDER BY\s+(\w+)`, `GROUP BY\s+(\w+)`
- Parse schema string to build set of valid table names and dict of valid columns per table
- Check each extracted table/column against schema
- Handle table aliases (e.g., `FROM iso_tank AS t` → validate `iso_tank`, ignore `t`)
- Handle qualified column names (e.g., `iso_tank.tank_number` → validate `tank_number` in `iso_tank`)
- Handle aggregate functions (e.g., `COUNT(*)`, `SUM(amount)`) → skip validation for `*` and function names
- Skip validation for SQL functions (e.g., `CURRENT_DATE`, `DATE_TRUNC`)
- Return `(True, "")` if all references valid, `(False, "Table/column 'X' does not exist")` otherwise
- Log: validation result, invalid references if any

**Patterns to follow:**
- Schema parsing pattern from `services/schema.py`
- Error message format from `config/ai_provider.py`

**Test scenarios:**
- Happy path: Valid SQL with existing tables/columns → returns `(True, "")`
- Happy path: SQL with table alias → validates original table name, ignores alias
- Happy path: SQL with qualified column names → validates column in correct table
- Happy path: SQL with aggregate functions → skips validation for `COUNT(*)`, `SUM(amount)`
- Happy path: SQL with SQL functions → skips validation for `CURRENT_DATE`, `DATE_TRUNC`
- Edge case: Non-existent table → returns `(False, "Table 'orders' does not exist")`
- Edge case: Non-existent column → returns `(False, "Column 'invalid_col' does not exist")`
- Edge case: Empty SQL → returns `(False, "SQL cannot be empty")`

**Verification:**
- Validate SQL against actual tank-depot schema
- Verify false positives are minimal (legitimate queries pass)
- Verify false negatives are zero (invalid references are caught)
- Verify validation completes in under 100ms

- [x] **Unit 4: SQL Validator Service - Safety Guards**

**Goal:** Block all dangerous SQL operations through blocklist and whitelist validation.

**Requirements:** R3 (block write operations and SQL injection), R8 (100% adversarial blocking)

**Dependencies:** Unit 3 (pre-validation in same file)

**Files:**
- Modify: `services/sql_validator.py` (add safety methods)
- Test: `tests/test_sql_validator.py` (add safety tests)

**Approach:**
- Add `check_safety(sql: str) -> tuple[bool, str]` method to `SQLValidator` class
- Layer 1 - Keyword blocklist (case-insensitive): `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`, `GRANT`, `REVOKE`, `CREATE`, `REPLACE`
- Layer 2 - Whitelist: Only allow queries starting with `SELECT` (after trimming whitespace and converting to uppercase)
- Return `(True, "")` if safe, `(False, "That question can't be answered safely")` for blocklist violations
- Return `(False, "Only SELECT queries are allowed")` for whitelist violations
- Log: safety check result, blocked SQL if unsafe

**Patterns to follow:**
- Defense-in-depth security pattern (multiple validation layers)
- Clear error messages without exposing internal details

**Test scenarios:**
- Happy path: Valid SELECT query → returns `(True, "")`
- Error path: SQL with DROP → returns `(False, "That question can't be answered safely")`
- Error path: SQL with DELETE → blocked
- Error path: SQL with UPDATE → blocked
- Error path: SQL with INSERT → blocked
- Error path: SQL injection attempt `; DELETE FROM iso_tank WHERE 1=1; --` → blocked
- Error path: SQL starting with non-SELECT → returns `(False, "Only SELECT queries are allowed")`
- Edge case: SELECT with lowercase → passes (case-insensitive)
- Edge case: SELECT with leading whitespace → passes (trimmed before check)

**Verification:**
- Test with 10+ adversarial inputs from requirements
- Verify 100% blocking rate for dangerous operations
- Verify zero false positives (legitimate SELECT queries pass)

- [x] **Unit 5: SQL Executor Service**

**Goal:** Execute validated SQL queries with timeout and comprehensive error handling.

**Requirements:** R4 (execute with 60s timeout and error handling), R9 (90% under 5s)

**Dependencies:** Unit 1 (logging)

**Files:**
- Create: `services/sql_executor.py`
- Test: `tests/test_sql_executor.py`

**Approach:**
- Create `SQLExecutor` class with `execute_query(sql: str) -> dict` method
- Use connection pool from `services/schema.py` pattern (reuse `chatbot_readonly` user)
- Set PostgreSQL `statement_timeout` to 60 seconds before executing query
- Execute SQL and fetch up to 100 rows
- Return structured result: `{ "columns": [...], "rows": [...], "row_count": N }`
- Always close connection in `finally` block
- Log: SQL executed, row count, execution time
- Error handling with specific exceptions:
  - Query timeout → raise `QueryTimeoutError` (custom exception)
  - Database connection failure → raise `DatabaseConnectionError`
  - SQL syntax error → raise `SQLSyntaxError`
  - Permission denied → raise `PermissionDeniedError`

**Patterns to follow:**
- Connection pooling from `services/schema.py`
- Error handling with custom exception types
- Resource cleanup in `finally` blocks

**Test scenarios:**
- Happy path: Execute valid SELECT query → returns structured result with columns, rows, row_count
- Happy path: Query returns 0 rows → returns empty rows array with row_count=0
- Happy path: Query returns 150 rows → returns first 100 rows with row_count=150
- Edge case: Query takes 2 seconds → completes successfully, logs execution time
- Error path: Query timeout (mock with pg_sleep(61)) → raises `QueryTimeoutError`
- Error path: Invalid SQL syntax → raises `SQLSyntaxError`
- Error path: Database connection failure (mock) → raises `DatabaseConnectionError`
- Error path: Permission denied (try to access non-existent table) → raises `PermissionDeniedError`
- Integration: Connection is always closed even when exception occurs

**Verification:**
- Execute 5 realistic queries against tank-depot database
- Verify 90% complete in under 5 seconds
- Verify timeout mechanism works (test with pg_sleep)
- Verify connection pool doesn't leak connections

- [x] **Unit 6: Answer Formatter Service**

**Goal:** Format query results into natural language summaries using AI.

**Requirements:** R5 (format answers with AI)

**Dependencies:** Unit 1 (logging)

**Files:**
- Create: `services/answer_formatter.py`
- Test: `tests/test_answer_formatter.py`

**Approach:**
- Create `AnswerFormatter` class with `format_answer(question: str, sql: str, results: dict) -> str` method
- Build prompt with: original question + SQL used + first 10 rows + total row count
- Use `ai_client` from `config/ai_provider.py` with SDK-specific call patterns
- Prompt instructs AI to: directly answer question, reference actual numbers, mention if truncated, use clear language
- Extract answer text from AI response
- Handle empty results: return "No results found for your question."
- Handle single row: format as sentence, not list
- Handle multiple rows: format as bulleted list or summary
- Log: question, row count, answer length, token usage
- Handle API failures with retry (once) then raise `AnswerFormattingError`

**Patterns to follow:**
- SDK type detection from `config/ai_provider.py`
- Error handling with retry logic from Unit 2

**Test scenarios:**
- Happy path: Single row result (COUNT query) → "There are currently 47 ISO tanks with status 'IN'."
- Happy path: Multiple rows (top clients) → bulleted list or summary sentence
- Happy path: Empty results → "No results found for your question."
- Happy path: Truncated results (showing 10 of 47) → mentions truncation in answer
- Edge case: Large numbers → formatted with commas (e.g., "1,234 tanks")
- Error path: AI API failure → retry once, then raise `AnswerFormattingError`
- Integration: Works with both OpenAI-compatible and Anthropic SDKs

**Verification:**
- Format answers for 5 different result types (single row, multiple rows, empty, truncated, large numbers)
- Verify answers are concise and human-readable
- Verify answers reference actual numbers from results
- Verify formatting completes in under 2 seconds

- [x] **Unit 7: Pipeline Orchestrator**

**Goal:** Wire all stages together into a single `ask(question)` function with comprehensive error handling.

**Requirements:** R6 (pipeline orchestration), R9 (90% under 5s)

**Dependencies:** Units 2-6 (all services)

**Files:**
- Create: `services/chatbot_pipeline.py`
- Test: `tests/test_chatbot_pipeline.py`

**Approach:**
- Create `ask(question: str) -> dict` function as main entry point
- Pipeline stages:
  1. Get database schema from `services/schema.py`
  2. Generate SQL using `SQLGenerator`
  3. Pre-validate table/column names using `SQLValidator.validate_references()`
  4. Run safety guard using `SQLValidator.check_safety()`
  5. Execute SQL using `SQLExecutor`
  6. Format answer using `AnswerFormatter`
  7. Return: `{ "answer": str, "sql": str, "rows_count": int }`
- Each stage has try/except with context about which stage failed
- Log: start time, end time, total duration, stage durations
- Map internal exceptions to HTTP-friendly error responses:
  - `SQLGenerationError` → 500 "Failed to generate SQL query"
  - `QueryTimeoutError` → 504 "Query took too long. Try simplifying your question."
  - `DatabaseConnectionError` → 503 "Database unavailable. Try again shortly."
  - `SQLSyntaxError` → 400 "Invalid SQL query generated. Try rephrasing your question."
  - `PermissionDeniedError` → 403 "Access denied to that table or column."
  - Validation failures → 400 with specific error message
- Pipeline is stateless (no caching between requests)

**Patterns to follow:**
- Error handling with context from `services/schema.py`
- Logging pattern from Unit 1

**Test scenarios:**
- Happy path: Complete pipeline for "How many ISO tanks are in 'IN' status?" → returns answer, SQL, row count
- Happy path: Complete pipeline for complex JOIN query → completes successfully
- Happy path: Pipeline completes in under 5 seconds for typical query
- Error path: SQL generation fails → returns 500 with user-friendly message
- Error path: Pre-validation fails → returns 400 with specific table/column error
- Error path: Safety guard blocks query → returns 400 with safety message
- Error path: Query timeout → returns 504 with timeout message
- Error path: Database connection failure → returns 503 with retry message
- Integration: All stages log to chat_audit.log
- Integration: Pipeline handles both OpenAI-compatible and Anthropic providers

**Verification:**
- Run pipeline with 10 realistic questions from requirements
- Verify 90% complete in under 5 seconds
- Verify all errors return user-friendly messages (no stack traces)
- Verify logs contain complete audit trail for each request

- [x] **Unit 8: Comprehensive Test Suite**

**Goal:** Create integration tests and adversarial test suite to validate success criteria.

**Requirements:** R7 (80%+ accuracy), R8 (100% adversarial blocking), R9 (90% under 5s)

**Dependencies:** Unit 7 (pipeline orchestrator)

**Files:**
- Create: `tests/test_integration.py`
- Create: `tests/test_adversarial.py`
- Create: `tests/fixtures/realistic_questions.json`
- Create: `tests/fixtures/adversarial_inputs.json`

**Approach:**
- Create 20+ realistic business questions in `realistic_questions.json` with expected SQL patterns
- Create 10+ adversarial inputs in `adversarial_inputs.json` (SQL injection, write operations)
- Integration tests:
  - Test complete pipeline with realistic questions
  - Verify SQL accuracy (80%+ threshold)
  - Verify performance (90%+ under 5s)
  - Verify answer quality (contains expected information)
- Adversarial tests:
  - Test all adversarial inputs are blocked
  - Verify 100% blocking rate
  - Verify error messages don't expose internal details
- Use pytest markers: `@pytest.mark.integration`, `@pytest.mark.slow`
- Skip tests if AI provider not configured (follow pattern from `test_ai_provider.py`)

**Patterns to follow:**
- Test structure from `tests/test_ai_provider.py`
- Environment-based test skipping
- Pytest fixtures for test data

**Test scenarios:**
- Integration: 20+ realistic questions → 80%+ generate correct SQL
- Integration: 20+ realistic questions → 90%+ complete in under 5s
- Integration: All questions return human-readable answers
- Adversarial: SQL injection attempts → 100% blocked
- Adversarial: Write operations (DROP, DELETE, UPDATE, INSERT) → 100% blocked
- Adversarial: Blocked queries return safe error messages (no stack traces)

**Verification:**
- Run full test suite with `pytest tests/ -v`
- Verify success criteria are met:
  - 80%+ SQL accuracy
  - 100% adversarial blocking
  - 90%+ queries under 5s
- Verify test coverage is >80% for all services

## System-Wide Impact

**Interaction graph:**
- Pipeline orchestrator calls all services in sequence
- Each service is independent and testable in isolation
- Services share logging configuration but have no other dependencies
- AI client is shared across SQL generator and answer formatter

**Error propagation:**
- Internal exceptions (e.g., `SQLGenerationError`) bubble up to pipeline orchestrator
- Pipeline orchestrator maps internal exceptions to HTTP-friendly responses
- All errors are logged with full context before being transformed
- User-facing errors never expose stack traces or internal details

**State lifecycle risks:**
- Pipeline is stateless - no caching or session state
- Database connections are pooled and always closed in `finally` blocks
- AI client is initialized once at module load time (from Phase 1)
- No risk of partial writes (read-only database user)

**API surface parity:**
- Phase 3 will wrap `ask()` function in FastAPI endpoint
- Return format `{ answer, sql, rows_count }` is the contract for Phase 3
- Error responses follow HTTP status code conventions

**Integration coverage:**
- Test complete pipeline end-to-end with realistic questions
- Test error handling at each stage
- Test both OpenAI-compatible and Anthropic SDK paths
- Test connection pool doesn't leak under error conditions

**Unchanged invariants:**
- Phase 1 components (`schema.py`, `ai_provider.py`) are not modified
- Database schema remains read-only
- JWT authentication (Phase 1) is not used yet (Phase 3 will integrate it)

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| AI generates invalid SQL despite few-shot examples | Pre-validation catches this before execution; iterate on examples during implementation |
| Pre-validation has false positives (rejects valid SQL) | Start conservative with regex; enhance based on real usage; log all validation failures for analysis |
| 60s timeout is too short for some queries | Log all timeout queries; adjust threshold in Phase 5 if needed; current value is generous for typical admin questions |
| AI summarization loses important details | Always return SQL alongside answer so admins can run it manually; log answer quality issues |
| Token costs are high (2 AI calls per question) | Monitor costs in logs; optimize prompts if needed; consider caching in Phase 5 |
| Regex-based table/column extraction misses complex SQL | Start simple; add sqlparse library if accuracy is insufficient; log all validation failures |

## Documentation / Operational Notes

**Logging:**
- All pipeline stages log to `logs/chat_audit.log`
- Log format includes timestamp, stage name, duration, and outcome
- Rotate logs at 10MB (keep 5 backups)
- Monitor logs for: SQL accuracy issues, timeout patterns, validation failures, API errors

**Performance monitoring:**
- Log execution time for each stage and total pipeline
- Track: SQL generation time, validation time, query execution time, answer formatting time
- Alert if 90% threshold (5s) is consistently exceeded

**Cost monitoring:**
- Log token usage for SQL generation and answer formatting
- Track daily token consumption and cost
- Optimize prompts if costs exceed budget

**Error patterns to watch:**
- High validation failure rate → improve few-shot examples
- Frequent timeouts → investigate query patterns or adjust threshold
- API failures → check provider status and retry logic

## Sources & References

- **Origin document:** [ai-service-croyance/docs/brainstorms/admin-chatbot-phase2-requirements.md](../brainstorms/admin-chatbot-phase2-requirements.md)
- **Phase 1 Plan:** [ai-service-croyance/docs/plans/2026-04-20-001-feat-admin-chatbot-phase1-setup-plan.md](2026-04-20-001-feat-admin-chatbot-phase1-setup-plan.md)
- **Original Plan:** [ai-service-croyance/admin_chatbot_plan.md](../../admin_chatbot_plan.md)
- **Database Schema:** [tank-depot/server/prisma/schema/schema.prisma](../../../tank-depot/server/prisma/schema/schema.prisma)
- Related code: `services/schema.py`, `config/ai_provider.py`
