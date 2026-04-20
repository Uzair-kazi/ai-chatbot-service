# Admin AI Chatbot — Phase 2 Requirements
> Core AI Pipeline: SQL Generation, Validation, Execution, and Formatting
> 
> **Date:** April 20, 2026  
> **Status:** Ready for Planning

---

## Problem Statement

Phase 1 established the foundation (database access, AI provider config, authentication). Phase 2 builds the core intelligence: translating natural language questions into SQL queries, executing them safely, and formatting results into human-readable answers.

Admins need a reliable pipeline that:
- Generates accurate SQL from natural language
- Prevents dangerous queries (writes, drops, injections)
- Handles query failures gracefully
- Returns clear, concise answers

## Solution Overview

Build a multi-stage pipeline that processes admin questions through SQL generation, validation, execution, and answer formatting.

**Core flow:**
```
Admin question
  ↓
1. Generate SQL (AI + few-shot examples)
  ↓
2. Pre-validate (check table/column names exist)
  ↓
3. Safety guard (blocklist + whitelist)
  ↓
4. Execute SQL (with 60s timeout)
  ↓
5. Format answer (AI summarizes results)
  ↓
Return: { answer, sql, rows_count }
```

## Goals

1. **Accuracy** — Generate correct SQL for 80%+ of realistic business questions
2. **Safety** — Prevent all write operations and SQL injection attempts
3. **Reliability** — Handle errors gracefully with clear messages
4. **Performance** — Complete typical queries in under 5 seconds
5. **Transparency** — Always return the SQL query alongside the answer

## Non-Goals

- Query optimization (use database indexes, not application logic)
- Caching query results (defer to Phase 5 if needed)
- Multi-turn conversations (each question is independent)
- Natural language follow-ups ("show me more details about that")

## User Personas

**Primary:** Admin users asking business questions
- Want quick answers without writing SQL
- Trust the system but want to verify the SQL
- Expect clear error messages when something fails

## Success Criteria

1. **SQL Accuracy:** 80%+ of test questions generate correct SQL
2. **Safety:** 100% of adversarial inputs are blocked
3. **Performance:** 90% of queries complete in under 5 seconds
4. **Error Clarity:** All error messages are actionable (no stack traces)
5. **Transparency:** Every response includes the executed SQL

## Architecture Decisions

### Few-Shot Prompt Engineering

**Decision:** Include 3-5 example question-SQL pairs in the system prompt.

**Rationale:**
- Teaches the AI the database schema through examples
- Reduces hallucination of non-existent tables/columns
- Improves JOIN logic and aggregation patterns
- More reliable than zero-shot prompting

**Trade-offs:**
- Increases prompt token count (cost)
- Examples need maintenance when schema changes
- May bias AI toward example patterns

**Example structure:**
```
Question: "How many ISO tanks are in 'IN' status?"
SQL: SELECT COUNT(*) FROM iso_tank WHERE iso_tank_status = 'IN';

Question: "Which clients have the most tanks this month?"
SQL: SELECT client_name, COUNT(*) as tank_count 
     FROM iso_tank 
     JOIN client ON iso_tank.client_id = client.id 
     WHERE created_at >= DATE_TRUNC('month', CURRENT_DATE)
     GROUP BY client_name 
     ORDER BY tank_count DESC 
     LIMIT 10;
```

### Pre-Validation of Table/Column Names

**Decision:** Validate all table and column references against the schema before executing SQL.

**Rationale:**
- Catches AI hallucinations early (before database execution)
- Provides clear error messages ("Table 'orders' does not exist")
- Prevents wasted database queries
- Reduces confusion for admins

**Trade-offs:**
- Adds latency (schema parsing + validation)
- Requires maintaining a schema cache
- May reject valid queries with aliases or subqueries

**Implementation approach:**
- Extract table names from SQL (regex or SQL parser)
- Extract column names from SELECT, WHERE, JOIN clauses
- Check against schema from `services/schema.py`
- Return validation error if any reference is invalid

### Query Timeout: 60 Seconds

**Decision:** Cancel queries that run longer than 60 seconds.

**Rationale:**
- Allows complex analytical queries to complete
- Prevents infinite hangs from poorly-formed SQL
- Protects database from resource exhaustion
- Balances flexibility with safety

**Trade-offs:**
- Some legitimate queries may timeout
- Admins may need to rephrase complex questions
- Timeout errors need clear messaging

**Implementation:**
- Use PostgreSQL `statement_timeout` setting
- Catch timeout exceptions and return 504 Gateway Timeout
- Error message: "Query took too long. Try simplifying your question."

### Always Summarize Results

**Decision:** Every answer is a natural language summary, never raw data tables.

**Rationale:**
- Consistent UX (admins always get readable answers)
- Reduces frontend complexity (no table rendering needed)
- Encourages conversational interaction
- Admins can still see raw SQL if they want to run it manually

**Trade-offs:**
- Admins can't directly copy/paste result data
- Summary may omit details from large result sets
- Requires additional AI call (cost + latency)

**Implementation:**
- Send first 10 rows to AI for summarization
- Include row count in summary ("47 tanks found...")
- Always show the SQL so admins can run it elsewhere if needed

## Functional Requirements

### FR1: SQL Generation with Few-Shot Examples

**As a system, I generate accurate SQL from natural language questions using few-shot prompting.**

**Acceptance criteria:**
- System prompt includes 3-5 example question-SQL pairs
- Examples cover common patterns: COUNT, JOIN, GROUP BY, date filtering
- AI returns only the SQL query (no markdown, no explanation)
- SQL always includes `LIMIT 100` to prevent massive result sets
- SQL never includes write operations (INSERT, UPDATE, DELETE, DROP, etc.)

**Example questions to support:**
- "How many ISO tanks are currently in 'IN' status?"
- "Which clients have the most tanks this month?"
- "Show me all tanks that haven't been surveyed in 90 days"
- "What's the average time between vehicle in and vehicle out?"
- "List all operators with more than 10 active tanks"

### FR2: Pre-Validation of SQL References

**As a system, I validate that all table and column names in the generated SQL exist in the database schema.**

**Acceptance criteria:**
- Extract all table names from SQL (FROM, JOIN clauses)
- Extract all column names from SQL (SELECT, WHERE, ORDER BY, GROUP BY clauses)
- Check each reference against the schema from `services/schema.py`
- If any reference is invalid, return error: "Table/column '[name]' does not exist in the database"
- Validation completes in under 100ms

**Edge cases:**
- Handle table aliases (e.g., `FROM iso_tank AS t`)
- Handle qualified column names (e.g., `iso_tank.tank_number`)
- Handle aggregate functions (e.g., `COUNT(*)`, `SUM(amount)`)
- Skip validation for SQL functions (e.g., `CURRENT_DATE`, `DATE_TRUNC`)

### FR3: SQL Safety Guard (Blocklist + Whitelist)

**As a system, I prevent all dangerous SQL operations through two layers of validation.**

**Layer 1 — Keyword Blocklist:**
- Block queries containing (case-insensitive): `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`, `GRANT`, `REVOKE`, `CREATE`, `REPLACE`
- Return error: "That question can't be answered safely"

**Layer 2 — Whitelist:**
- Only allow queries starting with `SELECT` (after trimming whitespace)
- Block queries starting with anything else
- Return error: "Only SELECT queries are allowed"

**Acceptance criteria:**
- Both layers run before query execution
- Validation is case-insensitive
- Clear error messages for blocked queries
- No false positives (legitimate SELECT queries are never blocked)

**Test cases:**
- ✅ Allow: `SELECT * FROM iso_tank WHERE tank_number = 'ABC123'`
- ❌ Block: `DROP TABLE iso_tank; --`
- ❌ Block: `; DELETE FROM iso_tank WHERE 1=1; --`
- ❌ Block: `UPDATE iso_tank SET tank_number = 'HACKED'`
- ❌ Block: `INSERT INTO iso_tank (tank_number) VALUES ('FAKE')`

### FR4: SQL Execution with Timeout

**As a system, I execute validated SQL queries with a 60-second timeout.**

**Acceptance criteria:**
- Connect to database using read-only user (`chatbot_readonly`)
- Set PostgreSQL `statement_timeout` to 60 seconds
- Execute the SQL query
- Fetch up to 100 rows maximum
- Return structured result: `{ columns: [...], rows: [...], row_count: N }`
- Always close database connection in a `finally` block

**Error handling:**
- Query timeout (60s exceeded): Return 504 with message "Query took too long. Try simplifying your question."
- Database connection failure: Return 503 with message "Database unavailable. Try again shortly."
- SQL syntax error: Return 400 with message "Invalid SQL query generated. Try rephrasing your question."
- Permission denied: Return 403 with message "Access denied to that table or column."

### FR5: Answer Formatting with AI

**As a system, I format query results into natural language summaries.**

**Acceptance criteria:**
- Send to AI: original question + SQL used + first 10 rows of results + total row count
- AI returns a concise, human-readable summary
- Summary references actual numbers from the results
- Summary mentions if results were truncated (e.g., "showing 10 of 47 results")
- Formatting completes in under 2 seconds

**Example:**
- Question: "How many ISO tanks are in 'IN' status?"
- SQL: `SELECT COUNT(*) FROM iso_tank WHERE iso_tank_status = 'IN'`
- Results: `[{ count: 47 }]`
- Answer: "There are currently 47 ISO tanks with status 'IN'."

**Edge cases:**
- Empty results: "No results found for your question."
- Single row: Format as a sentence, not a list
- Multiple rows: Format as a bulleted list or summary
- Large numbers: Use formatting (e.g., "1,234 tanks" not "1234 tanks")

### FR6: Pipeline Orchestration

**As a system, I orchestrate the complete pipeline from question to answer.**

**Public function:** `ask(question: str) -> dict`

**Pipeline stages:**
1. Get database schema from `services/schema.py`
2. Generate SQL using AI + few-shot examples
3. Pre-validate table/column names
4. Run safety guard (blocklist + whitelist)
5. Execute SQL with 60s timeout
6. Format answer using AI
7. Return: `{ answer: str, sql: str, rows_count: int }`

**Acceptance criteria:**
- Each stage has clear error handling
- Errors bubble up with context (which stage failed)
- All stages log to `logs/chat_audit.log`
- Pipeline completes in under 5 seconds for typical queries
- Pipeline is stateless (no caching between requests)

## Technical Constraints

### AI Provider

- Use `ai_client` from `config/ai_provider.py` (already configured in Phase 1)
- Support both OpenAI-compatible and Anthropic SDKs
- Handle API failures gracefully (retry once, then fail)
- Log token usage for cost monitoring

### Database

- Use read-only connection from Phase 1 (`chatbot_readonly` user)
- Set `statement_timeout` to 60 seconds
- Use connection pooling from `services/schema.py`
- Always close connections in `finally` blocks

### Performance

- SQL generation: < 2 seconds
- Pre-validation: < 100ms
- SQL execution: < 5 seconds (typical), < 60 seconds (max)
- Answer formatting: < 2 seconds
- **Total pipeline: < 10 seconds (typical), < 65 seconds (max)**

### Error Handling

- Never expose raw error messages or stack traces to admins
- Log full error details server-side for debugging
- Return user-friendly error messages with actionable guidance
- Include error type in response for frontend handling

## System Prompt Design

### SQL Generation Prompt Structure

```
You are a SQL query generator for a PostgreSQL database.

DATABASE SCHEMA:
{schema_description}

FEW-SHOT EXAMPLES:
{example_1}
{example_2}
{example_3}

RULES:
- Return ONLY the SQL query, no markdown, no explanation
- Always use SELECT queries only
- Never use DROP, DELETE, UPDATE, INSERT, ALTER, TRUNCATE
- Always include LIMIT 100 to prevent large result sets
- Use proper JOINs when querying multiple tables
- Use date functions for time-based queries (e.g., DATE_TRUNC, CURRENT_DATE)

USER QUESTION:
{question}

SQL QUERY:
```

### Answer Formatting Prompt Structure

```
You are a helpful assistant that summarizes database query results.

ORIGINAL QUESTION:
{question}

SQL QUERY USED:
{sql}

QUERY RESULTS (showing {shown_rows} of {total_rows} rows):
{results}

Provide a concise, natural language answer that:
- Directly answers the user's question
- References actual numbers from the results
- Mentions if results were truncated
- Uses clear, professional language

ANSWER:
```

## Implementation Units (High-Level)

Phase 2 will be broken into these implementation units during planning:

1. **SQL Generation Service** — AI prompt engineering with few-shot examples
2. **Pre-Validation Service** — Extract and validate table/column names
3. **SQL Safety Guard** — Blocklist + whitelist validation
4. **SQL Executor** — Execute with timeout and error handling
5. **Answer Formatter** — AI-powered result summarization
6. **Pipeline Orchestrator** — Wire all stages together with error handling
7. **Testing Suite** — Test with realistic questions and adversarial inputs

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| AI generates invalid SQL despite few-shot examples | Pre-validation catches this before execution |
| Pre-validation has false positives (rejects valid SQL) | Start conservative, tune based on real usage |
| 60s timeout is too short for some queries | Log timeout queries, adjust threshold in Phase 5 if needed |
| AI summarization loses important details | Always return SQL so admins can run it manually |
| Token costs are high (2 AI calls per question) | Monitor costs, optimize prompts, consider caching in Phase 5 |

## Open Questions

### Resolved During Brainstorming

**Q:** How should we handle AI hallucinations of table/column names?  
**A:** Use few-shot examples + pre-validation to catch errors early.

**Q:** What timeout is appropriate for complex queries?  
**A:** 60 seconds — allows analytical queries while preventing hangs.

**Q:** Should we always summarize results or support raw data views?  
**A:** Always summarize for consistency. Admins can see SQL if they want raw data.

### Deferred to Implementation

**Q:** Exact few-shot examples to include in the prompt  
**Why deferred:** Need to test different examples against real questions to find the best set.

**Q:** How to handle SQL with subqueries or CTEs in pre-validation  
**Why deferred:** Start with simple validation, enhance based on real usage patterns.

**Q:** Whether to retry SQL generation if pre-validation fails  
**Why deferred:** Depends on error rate — if high, add retry logic; if low, fail fast.

## Success Metrics

**Phase 2 is successful when:**

1. **Accuracy:** 80%+ of test questions generate correct SQL (measured with 20+ realistic questions)
2. **Safety:** 100% of adversarial inputs are blocked (measured with 10+ attack patterns)
3. **Performance:** 90% of queries complete in under 5 seconds (measured with query logs)
4. **Reliability:** Error messages are clear and actionable (verified through manual testing)
5. **Transparency:** Every response includes the SQL query (verified in integration tests)

## References

- **Phase 1 Requirements:** `docs/brainstorms/admin-chatbot-requirements.md`
- **Phase 1 Plan:** `docs/plans/2026-04-20-001-feat-admin-chatbot-phase1-setup-plan.md`
- **Original Plan:** `admin_chatbot_plan.md`
- **Database Schema:** `tank-depot/server/prisma/schema/schema.prisma`
- **Schema Service:** `services/schema.py`
- **AI Provider Config:** `config/ai_provider.py`

---

**Next Steps:** Create implementation plan for Phase 2 with detailed tasks and test scenarios.
