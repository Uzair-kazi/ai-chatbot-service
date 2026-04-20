# Admin AI Chatbot — Requirements Document
> Tank Depot Admin Portal · Natural Language Database Queries
> 
> **Date:** April 20, 2026  
> **Status:** Ready for Planning

---

## Problem Statement

Admins managing the Tank Depot system need to answer ad-hoc business questions about tanks, clients, operators, and operations. Currently, they must either:
- Ask developers to write custom SQL queries (slow, blocks engineering)
- Use existing dashboard endpoints (limited to pre-built views)
- Manually export and analyze data in spreadsheets (time-consuming)

This creates friction for time-sensitive business decisions and operational insights.

## Solution Overview

Build an AI-powered chatbot that lets admins ask natural language questions about the PostgreSQL database. The AI translates questions into SQL, executes them safely, and returns human-readable answers.

**Core flow:**
```
Admin question → AI generates SQL → Backend executes SQL → AI formats answer → Admin sees result
```

## Goals

1. **Enable self-service data exploration** — Admins can answer their own questions without developer help
2. **Maintain security** — Chatbot can only read data, never modify it
3. **Provide transparency** — Admins can see the SQL query that was executed
4. **Support flexible AI providers** — Easy to switch between DeepSeek, OpenAI, Anthropic, or local models

## Non-Goals

- Data exports (CSV/Excel downloads) — out of scope for Phase 1
- Scheduled/recurring queries — manual queries only
- Data visualization (charts/graphs) — text answers only
- Write operations (INSERT/UPDATE/DELETE) — read-only by design

## User Personas

**Primary:** Admin users with `role_name = "admin"` or `role_name = "Admin"`
- Need quick answers to business questions
- Comfortable with seeing SQL queries
- Trust the system to query safely

## Success Criteria

1. **Accuracy:** AI generates correct SQL for 80%+ of realistic business questions
2. **Security:** Zero write operations possible, even if AI is compromised
3. **Performance:** Responses return in under 5 seconds for typical queries
4. **Transparency:** Every answer shows the SQL query that was executed
5. **Swappability:** Can switch AI providers by changing environment variables only

## Architecture Decisions

### Separate Python Service

**Decision:** Build as a standalone FastAPI service, separate from the existing Node.js/Express backend.

**Rationale:**
- Clean separation of concerns
- Leverages Python's mature AI ecosystem
- Can be deployed and scaled independently
- Doesn't add complexity to the existing Express codebase

**Trade-offs:**
- Requires maintaining two backend services
- Duplicate environment configuration
- Separate deployment pipeline

### Authentication Flow

**Decision:** Python service validates JWT tokens directly.

**Flow:**
1. Frontend sends JWT token (from existing auth) to Python service
2. Python service verifies token using shared `JWT_SECRET_KEY`
3. Python service checks user role is admin
4. If valid, process the query; otherwise return 401

**Requirements:**
- Python service needs access to `JWT_SECRET_KEY` from environment
- Must verify token signature and expiration
- Must extract user role and validate it's admin

### Database Access

**Decision:** Full schema visibility with read-only database user.

**Implementation:**
- Create a new PostgreSQL user: `chatbot_readonly`
- Grant `SELECT` permission on all tables in the schema
- Revoke all other permissions (INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE)
- Python service connects using this user only

**Security layers:**
1. Database-level: Read-only user permissions
2. Application-level: SQL keyword blocklist (DROP, DELETE, UPDATE, etc.)
3. Application-level: Whitelist (only SELECT queries allowed)

### AI Provider Configuration

**Decision:** Swappable AI provider via environment variables only.

**Configuration file:** `config/ai_provider.py`
- Reads `AI_PROVIDER`, `AI_API_KEY`, `AI_BASE_URL`, `AI_MODEL` from `.env`
- Initializes the correct SDK based on provider type
- Exports a single `ai_client` that the rest of the app imports

**Supported providers:**
- DeepSeek (default, using OpenAI-compatible API)
- OpenAI (GPT-4o, GPT-4o-mini)
- Anthropic (Claude Sonnet)
- Groq (Llama models)
- Ollama (local self-hosted models)

**Switching providers:** Change `.env` values only, no code changes required.

## Functional Requirements

### FR1: Natural Language Query Processing

**As an admin, I can ask questions in plain English and get answers.**

**Examples:**
- "How many ISO tanks are currently in 'IN' status?"
- "Which clients have the most tanks this month?"
- "Show me all tanks that haven't been surveyed in 90 days"
- "What's the average time between vehicle in and vehicle out?"
- "List all operators with more than 10 active tanks"

**Acceptance criteria:**
- System accepts free-form text input
- AI generates a valid PostgreSQL SELECT query
- Query executes against the database
- Results are formatted into a human-readable answer
- Response time is under 5 seconds for typical queries

### FR2: SQL Transparency

**As an admin, I can see the exact SQL query that was executed.**

**Acceptance criteria:**
- Every response includes the generated SQL query
- SQL is displayed in a collapsible/expandable section
- SQL is syntax-highlighted or formatted as code
- Admins can copy the SQL for manual verification

### FR3: Safety Validation

**As a system, I prevent any write operations, even if the AI is tricked.**

**Acceptance criteria:**
- Queries containing `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`, `GRANT`, `REVOKE` are blocked
- Only queries starting with `SELECT` are allowed
- Blocked queries return a clear error message: "That question can't be answered safely"
- Database user has no write permissions at the PostgreSQL level

### FR4: Rate Limiting

**As a system, I prevent runaway AI API costs.**

**Acceptance criteria:**
- Each admin user is limited to 20 requests per minute
- Exceeded limits return HTTP 429 with a retry-after header
- Rate limits are per-user (based on JWT token user ID)

### FR5: Audit Logging

**As a system, I log every query for compliance and debugging.**

**Log entries include:**
- Timestamp
- Admin user ID and email
- Question asked
- SQL query generated
- Number of rows returned
- Success/failure status
- Error message (if failed)

**Storage:** `logs/chat_audit.log` file

### FR6: Error Handling

**As an admin, I receive clear error messages when something goes wrong.**

**Error scenarios:**

| Error Type | HTTP Code | User Message |
|---|---|---|
| SQL safety blocked | 400 | "That question can't be answered safely." |
| AI API failure | 502 | "AI service unavailable. Try again shortly." |
| Database connection failure | 503 | "Database unavailable. Try again shortly." |
| Invalid/empty question | 400 | "Please enter a question." |
| Unauthorized (not admin) | 401 | "You must be an admin to use this feature." |
| Rate limit exceeded | 429 | "Too many requests. Please wait before trying again." |
| General exception | 500 | "Something went wrong. Try rephrasing your question." |

**Requirements:**
- Never expose raw error messages or stack traces to the frontend
- Log full error details server-side for debugging

## Technical Constraints

### Database

- **Type:** PostgreSQL (existing tank-depot database)
- **Connection:** Read-only user with SELECT-only permissions
- **Schema:** Full Prisma schema visibility (all tables accessible)
- **Query limits:** Maximum 100 rows returned per query (enforced by AI prompt)

### Authentication

- **Method:** JWT token validation
- **Secret:** Shared `JWT_SECRET_KEY` with Node.js backend
- **Role check:** User must have `role_name = "admin"` or `role_name = "Admin"`

### AI Provider

- **Default:** DeepSeek API
- **Fallbacks:** OpenAI, Anthropic, Groq, Ollama
- **Configuration:** Environment variables only (no code changes to switch)
- **API key:** Stored in `.env`, never committed to git

### Deployment

- **Service:** Standalone Python FastAPI application
- **Deployment:** Separate from Node.js backend (independent deployment)
- **Port:** Configurable via environment variable (default: 8000)
- **CORS:** Must allow requests from the existing frontend origin

## Phase 1 Scope (Current Focus)

Phase 1 covers **Project Setup & Database Prep** only:

### 1.1 Project Initialization
- Create Python project structure
- Set up virtual environment
- Create `requirements.txt` with dependencies:
  - `fastapi`
  - `uvicorn`
  - `openai` (for OpenAI-compatible APIs)
  - `anthropic` (for Claude)
  - `python-dotenv`
  - `psycopg2-binary` (PostgreSQL driver)
  - `pyjwt` (JWT validation)
- Create `.env` and `.env.example` files

### 1.2 Read-Only Database User
- Create PostgreSQL user: `chatbot_readonly`
- Grant `SELECT` permission on all tables in the schema
- Revoke all other permissions
- Test that this user cannot execute write operations
- Store connection string in `.env` as `DB_URL`

### 1.3 Schema Auto-Generator
- Build `services/schema.py` module
- Connect to database using read-only user
- Query `information_schema.columns` to get:
  - All table names
  - All column names and data types
  - Foreign key relationships (if possible)
- Format output as clean text description
- This text will be injected into AI prompts

### 1.4 AI Provider Configuration
- Create `config/ai_provider.py` module
- Read environment variables:
  - `AI_PROVIDER` (e.g., "deepseek", "openai", "anthropic")
  - `AI_API_KEY`
  - `AI_BASE_URL`
  - `AI_MODEL`
  - `SDK_TYPE` (e.g., "openai_compatible", "anthropic")
- Initialize the correct AI client based on `SDK_TYPE`
- Export a single `ai_client` and `model_name`
- No other files should initialize AI clients directly

### 1.5 JWT Authentication Setup
- Create `middleware/auth.py` module
- Implement JWT token validation:
  - Extract token from `Authorization: Bearer <token>` header
  - Verify signature using `JWT_SECRET_KEY`
  - Check token expiration
  - Extract user payload (id, email, role)
- Implement admin role check:
  - Verify `role_name` is "admin" or "Admin"
  - Return 401 if not admin
- Apply to all chatbot endpoints

## Out of Scope (Future Phases)

- **Phase 2:** Core AI pipeline (SQL generation, execution, formatting)
- **Phase 3:** API endpoints and security middleware
- **Phase 4:** Frontend chat UI
- **Phase 5:** Testing and hardening

## Open Questions

None — all decisions finalized for Phase 1.

## References

- Original plan document: `admin_chatbot_plan.md`
- Tank Depot backend: `tank-depot/server/`
- Existing auth middleware: `tank-depot/server/src/middleware/auth.ts`
- Database schema: `tank-depot/server/prisma/schema/schema.prisma`

---

**Next Steps:** Proceed to planning Phase 1 implementation tasks.
