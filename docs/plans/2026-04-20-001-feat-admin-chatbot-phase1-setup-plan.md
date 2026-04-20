---
title: "Admin AI Chatbot - Phase 1: Project Setup & Database Prep"
type: feat
status: active
date: 2026-04-20
origin: docs/brainstorms/admin-chatbot-requirements.md
---

# Admin AI Chatbot - Phase 1: Project Setup & Database Prep

## Overview

Establish the foundational infrastructure for an AI-powered admin chatbot that translates natural language questions into SQL queries. Phase 1 focuses exclusively on project initialization, database security setup, schema introspection, AI provider abstraction, and JWT authentication middleware. No query execution or frontend work is included in this phase.

## Problem Frame

Admins managing the Tank Depot system need to answer ad-hoc business questions about tanks, clients, operators, and operations without blocking developers or manually exporting data. This phase lays the groundwork for a secure, swappable AI-powered query system by establishing read-only database access, automatic schema discovery, provider-agnostic AI configuration, and admin authentication.

## Requirements Trace

- R1. **Maintain security** — Chatbot can only read data, never modify it (Phase 1: read-only DB user)
- R2. **Support flexible AI providers** — Easy to switch between DeepSeek, OpenAI, Anthropic, or local models (Phase 1: swappable config)
- R3. **Provide transparency** — Admins can see SQL queries (Phase 1: schema visibility foundation)
- R4. **Admin-only access** — Only authenticated admin users can use the chatbot (Phase 1: JWT auth middleware)

## Scope Boundaries

**In scope for Phase 1:**
- Python project structure and dependency management
- Read-only PostgreSQL user creation and testing
- Automatic database schema introspection
- AI provider configuration abstraction
- JWT token validation and admin role checking

**Out of scope for Phase 1:**
- SQL generation logic (Phase 2)
- Query execution and result formatting (Phase 2)
- API endpoints and rate limiting (Phase 3)
- Frontend chat UI (Phase 4)
- Testing and hardening (Phase 5)

## Context & Research

### Relevant Code and Patterns

**Tank Depot Backend (Node.js/Express):**
- `tank-depot/server/src/middleware/auth.ts` — JWT validation pattern to mirror
- `tank-depot/server/.env.example` — Environment variable structure
- `tank-depot/server/prisma/schema/schema.prisma` — Database schema to introspect

**Technology Stack:**
- Database: PostgreSQL (existing tank-depot database)
- Auth: JWT tokens with `JWT_SECRET_KEY` shared with Node.js backend
- Admin role: `role_name = "admin"` or `role_name = "Admin"`

### Key Patterns to Follow

1. **JWT validation** — Mirror the Node.js backend's token extraction from `Authorization: Bearer <token>` header
2. **Environment configuration** — Use `.env` files with `.env.example` templates (never commit secrets)
3. **Database connection** — Use connection pooling for PostgreSQL via `psycopg2`

## Key Technical Decisions

**Decision:** Use a separate Python FastAPI service instead of integrating into the Node.js backend  
**Rationale:** Clean separation of concerns, leverages Python's AI ecosystem, independent deployment. Trade-off: requires maintaining two services and duplicating auth logic.

**Decision:** Python service validates JWT tokens directly using shared secret  
**Rationale:** Simpler than proxying through Node.js, allows direct frontend-to-Python communication. Trade-off: both services need access to `JWT_SECRET_KEY`.

**Decision:** Create a dedicated read-only PostgreSQL user  
**Rationale:** Defense-in-depth security — even if AI is compromised, database-level permissions prevent writes. This is the most critical security control.

**Decision:** Auto-generate schema descriptions from `information_schema`  
**Rationale:** Keeps schema documentation in sync with database automatically. Reduces manual maintenance burden.

**Decision:** Swappable AI provider via environment variables only  
**Rationale:** Allows switching providers (DeepSeek → OpenAI → Anthropic) without code changes. All provider-specific logic isolated in `config/ai_provider.py`.

## Open Questions

### Resolved During Planning

**Q:** Should the Python service connect to the same PostgreSQL database as the Node.js backend?  
**A:** Yes — same database, but using a different (read-only) user for security isolation.

**Q:** How should the schema generator handle foreign key relationships?  
**A:** Query `information_schema.table_constraints` and `key_column_usage` to include FK relationships in the schema description. This significantly improves AI-generated SQL quality.

**Q:** Which JWT library should Python use?  
**A:** `PyJWT` — it's the standard Python JWT library and matches the Node.js backend's `jsonwebtoken` behavior.

### Deferred to Implementation

**Q:** Exact format of the schema description text for AI prompts  
**Why deferred:** The optimal format depends on testing different prompt structures in Phase 2. Phase 1 should generate a comprehensive schema; Phase 2 will refine the format based on SQL generation quality.

**Q:** Connection pool size for PostgreSQL  
**Why deferred:** Depends on expected load and server resources. Start with defaults; tune in Phase 5 based on performance testing.

## Output Structure

```
ai-service-croyance/
├── config/
│   └── ai_provider.py          # AI client initialization
├── services/
│   └── schema.py               # Database schema introspection
├── middleware/
│   └── auth.py                 # JWT validation and admin check
├── logs/
│   └── .gitkeep                # Placeholder for chat_audit.log
├── .env                        # Environment variables (gitignored)
├── .env.example                # Environment template
├── .gitignore                  # Python-specific ignores
├── requirements.txt            # Python dependencies
└── README.md                   # Setup instructions
```

## Implementation Units

- [x] **Unit 1: Python Project Initialization**

**Goal:** Create the Python project structure with dependency management and environment configuration.

**Requirements:** Foundation for all other Phase 1 units

**Dependencies:** None

**Files:**
- Create: `ai-service-croyance/.gitignore`
- Create: `ai-service-croyance/requirements.txt`
- Create: `ai-service-croyance/.env.example`
- Create: `ai-service-croyance/README.md`
- Create: `ai-service-croyance/logs/.gitkeep`

**Approach:**
- Set up `.gitignore` with Python-specific patterns (`.env`, `__pycache__`, `*.pyc`, `venv/`, `.pytest_cache/`)
- Create `requirements.txt` with pinned versions:
  - `fastapi>=0.110.0`
  - `uvicorn[standard]>=0.29.0`
  - `openai>=1.14.0` (for OpenAI-compatible APIs including DeepSeek)
  - `anthropic>=0.21.0` (for Claude)
  - `python-dotenv>=1.0.0`
  - `psycopg2-binary>=2.9.9` (PostgreSQL driver)
  - `PyJWT>=2.8.0` (JWT validation)
- Create `.env.example` with all required variables (see test scenarios for complete list)
- Create `README.md` with setup instructions: virtual environment creation, dependency installation, `.env` configuration
- Create `logs/.gitkeep` to ensure the logs directory exists in git

**Patterns to follow:**
- `tank-depot/server/.env.example` — environment variable structure
- `tank-depot/server/.gitignore` — gitignore patterns (adapt for Python)

**Test scenarios:**
- **Happy path:** `.env.example` contains all required variables with placeholder values (DB_URL, JWT_SECRET_KEY, AI_PROVIDER, AI_API_KEY, AI_BASE_URL, AI_MODEL, SDK_TYPE)
- **Happy path:** `requirements.txt` includes all dependencies with version constraints
- **Happy path:** `.gitignore` excludes `.env`, `__pycache__`, `*.pyc`, `venv/`, `.pytest_cache/`
- **Happy path:** `README.md` includes clear setup instructions for virtual environment and dependency installation

**Verification:**
- Running `pip install -r requirements.txt` in a fresh virtual environment succeeds without errors
- `.env.example` lists all environment variables needed for Phase 1
- `.gitignore` prevents committing sensitive files

---

- [x] **Unit 2: Read-Only Database User Creation**

**Goal:** Create a PostgreSQL user with SELECT-only permissions to enforce database-level security.

**Requirements:** R1 (Maintain security — read-only access)

**Dependencies:** Unit 1 (need `.env.example` to document the connection string)

**Files:**
- Create: `ai-service-croyance/scripts/create_readonly_user.sql`
- Create: `ai-service-croyance/scripts/test_readonly_user.sql`
- Modify: `ai-service-croyance/.env.example` (add DB_URL placeholder)
- Modify: `ai-service-croyance/README.md` (add database setup instructions)

**Approach:**
- Create SQL script to:
  1. Create user `chatbot_readonly` with a secure password
  2. Grant `CONNECT` on the database
  3. Grant `USAGE` on the schema (likely `public`)
  4. Grant `SELECT` on all tables in the schema
  5. Grant `SELECT` on all sequences (for reading auto-increment values)
  6. Revoke all other permissions explicitly
- Create test SQL script to verify:
  1. SELECT queries work
  2. INSERT/UPDATE/DELETE/DROP/TRUNCATE fail with permission errors
- Document the manual steps in README.md:
  1. Run `create_readonly_user.sql` as a superuser
  2. Run `test_readonly_user.sql` to verify permissions
  3. Add the connection string to `.env` as `DB_URL`

**Patterns to follow:**
- PostgreSQL GRANT/REVOKE syntax for role-based permissions
- Connection string format: `postgresql://chatbot_readonly:password@host:port/database`

**Test scenarios:**
- **Happy path:** `chatbot_readonly` user can execute `SELECT * FROM iso_tank LIMIT 1`
- **Happy path:** `chatbot_readonly` user can execute `SELECT * FROM information_schema.columns`
- **Error path:** `chatbot_readonly` user cannot execute `INSERT INTO iso_tank (...) VALUES (...)`
- **Error path:** `chatbot_readonly` user cannot execute `UPDATE iso_tank SET ...`
- **Error path:** `chatbot_readonly` user cannot execute `DELETE FROM iso_tank`
- **Error path:** `chatbot_readonly` user cannot execute `DROP TABLE iso_tank`
- **Error path:** `chatbot_readonly` user cannot execute `TRUNCATE TABLE iso_tank`
- **Error path:** `chatbot_readonly` user cannot execute `ALTER TABLE iso_tank ...`
- **Edge case:** `chatbot_readonly` user can read from newly created tables (test with `GRANT SELECT ON ALL TABLES IN SCHEMA public TO chatbot_readonly`)

**Verification:**
- All SELECT queries succeed
- All write operations (INSERT, UPDATE, DELETE, DROP, TRUNCATE, ALTER) fail with PostgreSQL permission errors
- Connection string in `.env` successfully connects to the database

---

- [x] **Unit 3: Database Schema Auto-Generator**

**Goal:** Build a service that introspects the PostgreSQL database and generates a human-readable schema description for AI prompts.

**Requirements:** R3 (Provide transparency — schema visibility foundation)

**Dependencies:** Unit 2 (need read-only database user and connection)

**Files:**
- Create: `ai-service-croyance/services/__init__.py`
- Create: `ai-service-croyance/services/schema.py`
- Test: `ai-service-croyance/tests/test_schema.py`

**Approach:**
- Create `services/schema.py` module with:
  - `get_database_schema()` function that:
    1. Connects to PostgreSQL using `DB_URL` from environment
    2. Queries `information_schema.columns` for all tables, columns, and data types
    3. Queries `information_schema.table_constraints` and `information_schema.key_column_usage` for foreign key relationships
    4. Formats the output as a clean text description:
       ```
       Table: iso_tank
       - id (uuid, primary key)
       - tank_number (text)
       - iso_tank_status (text)
       - vehicle_in_id (uuid, foreign key -> vehicle_in.id)
       - created_at (timestamp with time zone)
       ...
       ```
    5. Returns the formatted string
  - Use connection pooling with `psycopg2.pool.SimpleConnectionPool`
  - Handle connection errors gracefully (log and raise)
- The schema description will be injected into AI prompts in Phase 2

**Patterns to follow:**
- `tank-depot/server/prisma/schema/schema.prisma` — the schema to introspect
- PostgreSQL `information_schema` queries for metadata

**Test scenarios:**
- **Happy path:** `get_database_schema()` returns a non-empty string containing table names from the Prisma schema (iso_tank, service_tank, suraksha_tanker)
- **Happy path:** Schema description includes column names and data types for each table
- **Happy path:** Schema description includes foreign key relationships (e.g., "vehicle_in_id -> vehicle_in.id")
- **Error path:** If database connection fails, function raises a descriptive error (not a generic exception)
- **Edge case:** Schema description handles tables with no foreign keys
- **Edge case:** Schema description handles tables with composite primary keys
- **Integration:** Connecting with `DB_URL` from `.env` and querying `information_schema` succeeds

**Verification:**
- Running `get_database_schema()` returns a formatted string with all tables from the tank-depot database
- The output includes table names, column names, data types, and foreign key relationships
- Connection errors are caught and logged with clear messages

---

- [x] **Unit 4: AI Provider Configuration Abstraction**

**Goal:** Create a swappable AI provider configuration system that allows switching between DeepSeek, OpenAI, Anthropic, and other providers via environment variables only.

**Requirements:** R2 (Support flexible AI providers)

**Dependencies:** Unit 1 (need `.env` configuration)

**Files:**
- Create: `ai-service-croyance/config/__init__.py`
- Create: `ai-service-croyance/config/ai_provider.py`
- Modify: `ai-service-croyance/.env.example` (add AI provider variables)
- Test: `ai-service-croyance/tests/test_ai_provider.py`

**Approach:**
- Create `config/ai_provider.py` module that:
  1. Reads environment variables:
     - `AI_PROVIDER` (e.g., "deepseek", "openai", "anthropic")
     - `AI_API_KEY`
     - `AI_BASE_URL` (e.g., "https://api.deepseek.com")
     - `AI_MODEL` (e.g., "deepseek-chat", "gpt-4o", "claude-sonnet-4-20250514")
     - `SDK_TYPE` (e.g., "openai_compatible", "anthropic")
  2. Initializes the correct SDK client based on `SDK_TYPE`:
     - If `openai_compatible`: use `openai.OpenAI(api_key=..., base_url=...)`
     - If `anthropic`: use `anthropic.Anthropic(api_key=...)`
  3. Exports:
     - `ai_client` — the initialized client instance
     - `model_name` — the model string to use in API calls
     - `provider_name` — for logging/debugging
- No other files should initialize AI clients directly — all AI access goes through this module
- Add comprehensive comments explaining how to switch providers

**Patterns to follow:**
- OpenAI SDK initialization: `client = OpenAI(api_key=key, base_url=url)`
- Anthropic SDK initialization: `client = Anthropic(api_key=key)`
- Environment variable loading: `os.getenv()` with `python-dotenv`

**Test scenarios:**
- **Happy path:** When `SDK_TYPE=openai_compatible`, `ai_client` is an instance of `openai.OpenAI`
- **Happy path:** When `SDK_TYPE=anthropic`, `ai_client` is an instance of `anthropic.Anthropic`
- **Happy path:** `model_name` matches the value of `AI_MODEL` environment variable
- **Happy path:** `provider_name` matches the value of `AI_PROVIDER` environment variable
- **Error path:** If `AI_API_KEY` is missing, module raises a clear error on import
- **Error path:** If `SDK_TYPE` is invalid (not "openai_compatible" or "anthropic"), module raises a clear error
- **Edge case:** OpenAI-compatible client correctly uses custom `base_url` for DeepSeek/Groq/Ollama
- **Integration:** Importing `ai_client` from `config.ai_provider` succeeds when `.env` is properly configured

**Verification:**
- Changing only `.env` values (AI_PROVIDER, AI_API_KEY, AI_BASE_URL, AI_MODEL, SDK_TYPE) switches the provider without code changes
- `ai_client` is correctly initialized for both OpenAI-compatible and Anthropic SDKs
- Missing or invalid environment variables produce clear error messages

---

- [x] **Unit 5: JWT Authentication Middleware**

**Goal:** Implement JWT token validation and admin role checking to secure the chatbot endpoints.

**Requirements:** R4 (Admin-only access)

**Dependencies:** Unit 1 (need `.env` configuration for JWT_SECRET_KEY)

**Files:**
- Create: `ai-service-croyance/middleware/__init__.py`
- Create: `ai-service-croyance/middleware/auth.py`
- Modify: `ai-service-croyance/.env.example` (add JWT_SECRET_KEY placeholder)
- Test: `ai-service-croyance/tests/test_auth.py`

**Approach:**
- Create `middleware/auth.py` module with:
  - `verify_jwt_token(token: str) -> dict` function that:
    1. Decodes the JWT using `PyJWT.decode()` with `JWT_SECRET_KEY` from environment
    2. Verifies signature and expiration
    3. Returns the decoded payload (contains `id`, `email`, `name`, and role info)
    4. Raises `jwt.ExpiredSignatureError` or `jwt.InvalidTokenError` on failure
  - `is_admin_user(payload: dict) -> bool` function that:
    1. Extracts role information from the payload
    2. Checks if `role_name` is "admin" or "Admin" (case-insensitive comparison)
    3. Returns True if admin, False otherwise
  - `authenticate_admin(authorization_header: str) -> dict` function that:
    1. Extracts token from `Authorization: Bearer <token>` header
    2. Calls `verify_jwt_token(token)`
    3. Calls `is_admin_user(payload)`
    4. Returns payload if admin, raises `HTTPException(401)` otherwise
- Mirror the Node.js backend's JWT validation logic from `tank-depot/server/src/middleware/auth.ts`

**Patterns to follow:**
- `tank-depot/server/src/middleware/auth.ts` — JWT validation and admin check logic
- FastAPI dependency injection for middleware (will be used in Phase 3)

**Test scenarios:**
- **Happy path:** Valid JWT token with admin role returns decoded payload
- **Happy path:** Token with `role_name = "admin"` passes admin check
- **Happy path:** Token with `role_name = "Admin"` passes admin check (case-insensitive)
- **Error path:** Expired JWT token raises `jwt.ExpiredSignatureError`
- **Error path:** Invalid JWT signature raises `jwt.InvalidTokenError`
- **Error path:** Missing `Authorization` header raises `HTTPException(401)`
- **Error path:** Malformed `Authorization` header (not "Bearer <token>") raises `HTTPException(401)`
- **Error path:** Valid JWT token with non-admin role (e.g., "client", "surveyor") raises `HTTPException(401)` with message "You must be an admin to use this feature"
- **Edge case:** Token with missing role information raises `HTTPException(401)`
- **Integration:** JWT token generated by the Node.js backend (`tank-depot/server`) is successfully validated by the Python service using the same `JWT_SECRET_KEY`

**Verification:**
- Valid admin JWT tokens from the Node.js backend are accepted
- Non-admin tokens are rejected with 401
- Expired or invalid tokens are rejected with appropriate error messages
- The middleware correctly extracts and validates the `Authorization: Bearer <token>` header format

## System-Wide Impact

**Interaction graph:**
- This phase establishes foundational services that Phase 2-5 will depend on
- No callbacks or middleware chains yet (those come in Phase 3)

**Error propagation:**
- Database connection errors should bubble up with clear messages (not generic exceptions)
- JWT validation errors should return 401 with user-friendly messages
- AI provider initialization errors should fail fast on startup (not at first request)

**State lifecycle risks:**
- Database connection pool must be properly closed on shutdown
- No state is persisted in this phase (stateless services only)

**API surface parity:**
- JWT validation logic must match the Node.js backend's behavior exactly
- Both services must use the same `JWT_SECRET_KEY` and token format

**Integration coverage:**
- Unit 2: Verify read-only user permissions at the PostgreSQL level (not just application level)
- Unit 3: Verify schema introspection works against the actual tank-depot database
- Unit 5: Verify JWT tokens generated by Node.js backend are accepted by Python service

**Unchanged invariants:**
- The Node.js backend's authentication system remains unchanged
- The PostgreSQL database schema remains unchanged
- The frontend's JWT token generation remains unchanged

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| JWT secret mismatch between Node.js and Python services | Document the requirement clearly in README.md. Add a test in Phase 3 that validates a real token from the Node.js backend. |
| Read-only user permissions not properly restricted | Create comprehensive test SQL script (Unit 2) that verifies all write operations fail. Run this test before proceeding to Phase 2. |
| AI provider API key invalid or expired | Defer actual API calls to Phase 2. Phase 1 only validates that the configuration loads correctly. |
| Database schema changes after introspection | Schema introspection runs dynamically on each request (Phase 2), so it stays in sync. No caching in Phase 1. |
| PostgreSQL connection pool exhaustion | Use `psycopg2.pool.SimpleConnectionPool` with reasonable defaults (min=1, max=10). Tune in Phase 5 based on load testing. |

## Documentation / Operational Notes

**Setup instructions (README.md):**
1. Create Python virtual environment: `python3 -m venv venv`
2. Activate virtual environment: `source venv/bin/activate` (Linux/Mac) or `venv\Scripts\activate` (Windows)
3. Install dependencies: `pip install -r requirements.txt`
4. Copy `.env.example` to `.env` and fill in values:
   - `DB_URL`: PostgreSQL connection string for `chatbot_readonly` user
   - `JWT_SECRET_KEY`: Same secret used by the Node.js backend
   - `AI_PROVIDER`, `AI_API_KEY`, `AI_BASE_URL`, `AI_MODEL`, `SDK_TYPE`: AI provider configuration
5. Run database setup scripts:
   - `psql -U postgres -f scripts/create_readonly_user.sql`
   - `psql -U chatbot_readonly -f scripts/test_readonly_user.sql`
6. Verify setup: `python -c "from config.ai_provider import ai_client; from services.schema import get_database_schema; print('Setup OK')"`

**Security notes:**
- Never commit `.env` to git (already in `.gitignore`)
- Rotate `JWT_SECRET_KEY` if it is ever exposed
- Use a strong password for the `chatbot_readonly` PostgreSQL user
- Restrict network access to the PostgreSQL database (firewall rules)

**Deployment notes:**
- This phase does not include a runnable server (that comes in Phase 3)
- All units can be tested independently without starting a web server
- The Python service will eventually run on a separate port from the Node.js backend (default: 8000)

## Sources & References

- **Origin document:** [docs/brainstorms/admin-chatbot-requirements.md](../brainstorms/admin-chatbot-requirements.md)
- **Related code:** `tank-depot/server/src/middleware/auth.ts` (JWT validation pattern)
- **Related code:** `tank-depot/server/prisma/schema/schema.prisma` (database schema)
- **Related code:** `tank-depot/server/.env.example` (environment variable structure)
- **External docs:** [PyJWT documentation](https://pyjwt.readthedocs.io/)
- **External docs:** [psycopg2 documentation](https://www.psycopg.org/docs/)
- **External docs:** [OpenAI Python SDK](https://github.com/openai/openai-python)
- **External docs:** [Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python)
