# Admin AI Chatbot - Phase 2: SQL Pipeline

AI-powered chatbot for the Tank Depot admin panel that translates natural language questions into SQL queries.

## Current Status

**Phase 2 Complete:** Core AI pipeline with SQL generation, validation, execution, and formatting.

## Features

### Phase 1: Foundation (Complete)
- Python project structure and dependency management
- Read-only PostgreSQL user for secure database access
- Automatic database schema introspection
- Swappable AI provider configuration (DeepSeek, OpenAI, Anthropic, etc.)
- JWT authentication middleware for admin-only access

### Phase 2: SQL Pipeline (Complete)
- **SQL Generation:** AI-powered SQL generation with few-shot prompting
- **Pre-Validation:** Validates table/column references before execution
- **Safety Guards:** Two-layer security (blocklist + whitelist) blocks all write operations
- **Query Execution:** Executes queries with 60-second timeout and comprehensive error handling
- **Answer Formatting:** AI-powered result summarization into natural language
- **Pipeline Orchestration:** Complete end-to-end pipeline with logging and error handling

## Prerequisites

- Python 3.9 or higher
- PostgreSQL database (existing tank-depot database)
- Access to the Node.js backend's `JWT_SECRET_KEY`
- AI provider API key (DeepSeek, OpenAI, or Anthropic)

## Setup Instructions

### 1. Create Python Virtual Environment

```bash
python3 -m venv venv
```

### 2. Activate Virtual Environment

**Linux/Mac:**
```bash
source venv/bin/activate
```

**Windows:**
```bash
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Copy the example environment file and fill in your values:

```bash
cp .env.example .env
```

Edit `.env` and configure:

- **DB_URL**: PostgreSQL connection string for the `chatbot_readonly` user (see Database Setup below)
- **JWT_SECRET_KEY**: Same secret used by the Node.js backend (found in `tank-depot/server/.env`)
- **AI_PROVIDER**: Provider name (e.g., "deepseek", "openai", "anthropic")
- **AI_API_KEY**: Your AI provider API key
- **AI_BASE_URL**: Provider API endpoint
- **AI_MODEL**: Model name to use
- **SDK_TYPE**: Either "openai_compatible" or "anthropic"

### 5. Database Setup

Create the read-only PostgreSQL user:

```bash
# Run as PostgreSQL superuser (replace 'tank_depot' with your database name)
psql -U postgres -d tank_depot -f scripts/create_readonly_user.sql
```

**Important:** Edit `scripts/create_readonly_user.sql` and change the password from `CHANGE_THIS_PASSWORD` to a strong password before running the script.

After creating the user, test the permissions:

```bash
# Test that the user can only read, not write (replace 'tank_depot' with your database name)
psql -U chatbot_readonly -d tank_depot -f scripts/test_readonly_user.sql
```

The `chatbot_readonly` user will have:
- ✅ SELECT permission on all tables
- ❌ No INSERT, UPDATE, DELETE, DROP, TRUNCATE, or ALTER permissions

**Expected test results:**
- Tests 1-2 (SELECT queries) should succeed
- Tests 3-8 (write operations) should fail with permission errors

Update your `.env` file with the connection string:
```env
DB_URL="postgresql://chatbot_readonly:your_password@localhost:5432/tank_depot"
```

### 6. Verify Setup

```bash
python -c "from config.ai_provider import ai_client; from services.schema import get_database_schema; print('Setup OK')"
```

## Project Structure

```
ai-service-croyance/
├── config/
│   ├── __init__.py                 # Config package
│   ├── ai_provider.py              # AI client initialization
│   └── logging_config.py           # Centralized logging setup
├── docs/
│   ├── solutions/                  # documented solutions to past problems (bugs, best practices, workflow patterns), organized by category with YAML frontmatter (module, tags, problem_type)
│   ├── brainstorms/                # requirements and brainstorming documents
│   └── plans/                      # implementation plans
├── services/
│   ├── __init__.py
│   ├── schema.py                   # Database schema introspection
│   ├── sql_generator.py            # SQL generation with few-shot prompting
│   ├── sql_validator.py            # Pre-validation and safety guards
│   ├── sql_executor.py             # Query execution with timeout
│   ├── answer_formatter.py         # AI-powered result summarization
│   └── chatbot_pipeline.py         # Pipeline orchestrator
├── middleware/
│   └── auth.py                     # JWT validation and admin check
├── scripts/
│   ├── create_readonly_user.sql
│   └── test_readonly_user.sql
├── logs/
│   └── chat_audit.log              # Audit trail (auto-created)
├── tests/
│   ├── fixtures/
│   │   ├── realistic_questions.json
│   │   └── adversarial_inputs.json
│   ├── test_schema.py
│   ├── test_ai_provider.py
│   ├── test_auth.py
│   ├── test_logging_config.py
│   ├── test_sql_generator.py
│   ├── test_sql_validator.py
│   ├── test_sql_executor.py
│   ├── test_answer_formatter.py
│   ├── test_chatbot_pipeline.py
│   ├── test_integration.py         # Integration tests
│   └── test_adversarial.py         # Security tests
├── .env                            # Environment variables (gitignored)
├── .env.example                    # Environment template
├── .gitignore                      # Python-specific ignores
├── requirements.txt                # Python dependencies
└── README.md                       # This file
```

## Usage

### REST API (Phase 3)

The service provides a production-ready REST API with FastAPI.

#### Starting the Server

```bash
# Development mode (with auto-reload)
python main.py

# Production mode
uvicorn main:app --host 0.0.0.0 --port 8000
```

The API will be available at:
- **API Base**: http://localhost:8000
- **Interactive Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

#### Authentication

**Login to get a JWT token:**

```bash
curl -X POST http://localhost:8000/v1/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "your_password"}'
```

Response:
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": "123",
    "email": "admin@example.com",
    "name": "Admin User",
    "role": "Admin"
  },
  "timestamp": "2026-04-21T10:30:00Z"
}
```

**Use the token to ask questions:**

```bash
curl -X POST http://localhost:8000/v1/ask \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "How many ISO tanks are in the database?"}'
```

Response:
```json
{
  "answer": "There are 4,701 ISO tanks in the database.",
  "sql": "SELECT COUNT(*) FROM iso_tank LIMIT 100;",
  "rows_count": 1,
  "execution_time_ms": 234,
  "timestamp": "2026-04-21T10:30:00Z"
}
```

#### Rate Limiting

- **General API**: 20 requests per minute per user
- **Login endpoint**: 5 requests per minute per IP address (stricter to prevent brute force)

Rate limit headers are included in all responses:
- `X-RateLimit-Limit`: Maximum requests per window
- `X-RateLimit-Remaining`: Remaining requests in current window
- `X-RateLimit-Reset`: Unix timestamp when the window resets

#### Testing the API

Use the included test script:

```bash
# Test with default question
python test_api.py

# Test with custom question
python test_api.py "Show me the top 5 ISO tanks by capacity"
```

The test script will:
1. Check if the server is running
2. Generate a JWT token (or use login endpoint)
3. Test the health endpoint
4. Ask a question
5. Display the response with rate limit information

### Basic Usage (Python)

```python
from services.chatbot_pipeline import ask

# Ask a question
result = ask("How many ISO tanks are in 'IN' status?")

print(result["answer"])      # Natural language answer
print(result["sql"])          # SQL query that was executed
print(result["rows_count"])   # Number of rows returned
print(result["status_code"])  # HTTP status code (200 = success)
```

### Example Questions

```python
# COUNT queries
ask("How many ISO tanks are there?")
ask("How many service tanks have status 'IN'?")

# FILTER queries
ask("Show me ISO tanks with status 'IN'")
ask("Which ISO tanks haven't been surveyed yet?")

# DATE queries
ask("List ISO tanks created today")
ask("Show me all ISO tanks created this month")

# AGGREGATION queries
ask("What are the different ISO tank statuses?")
ask("Show me the 10 most recently created ISO tanks")
```

### Response Format

```python
{
    "answer": "There are currently 47 ISO tanks with status 'IN'.",
    "sql": "SELECT COUNT(*) FROM iso_tank WHERE iso_tank_status = 'IN' LIMIT 100;",
    "rows_count": 1,
    "status_code": 200
}
```

### Error Handling

```python
result = ask("DROP TABLE iso_tank")

# Dangerous queries are blocked
assert result["status_code"] == 400
assert "can't be answered safely" in result["answer"]
```

## Testing

### Run Unit Tests

```bash
# Run all unit tests (no database/AI required)
pytest tests/ -v -m "not integration and not slow"

# Run specific test file
pytest tests/test_sql_validator.py -v

# Run with coverage
pytest tests/ --cov=services --cov=config
```

### Run Integration Tests

Integration tests require database and AI provider configuration:

```bash
# Run integration tests (requires DB_URL and AI_API_KEY)
pytest tests/test_integration.py -v -s

# Run adversarial tests (security validation)
pytest tests/test_adversarial.py -v -s

# Run all tests including integration
pytest tests/ -v
```

### Test Success Criteria

Phase 2 success criteria (validated by integration tests):
- ✅ **80%+ SQL accuracy** - Generates correct SQL patterns for realistic questions
- ✅ **100% adversarial blocking** - Blocks all dangerous operations (DROP, DELETE, UPDATE, INSERT)
- ✅ **90%+ performance** - Completes queries in under 5 seconds
- ✅ **Clear error messages** - No stack traces or internal details exposed

## Security Notes

- **Never commit `.env` to git** — it contains sensitive credentials
- The `chatbot_readonly` database user can only read data, never modify it
- **Two-layer SQL safety:** Blocklist catches dangerous keywords, whitelist ensures only SELECT queries
- **Pre-validation:** All table/column references are validated before execution
- **Query timeout:** 60-second limit prevents infinite hangs
- JWT tokens must match the Node.js backend's format exactly
- Rotate `JWT_SECRET_KEY` if it is ever exposed
- Use a strong password for the `chatbot_readonly` PostgreSQL user
- Restrict network access to the PostgreSQL database using firewall rules
- All queries are logged to `logs/chat_audit.log` for audit trail

## Architecture

### Pipeline Flow

```
User Question
    ↓
1. Get Database Schema
    ↓
2. Generate SQL (AI + few-shot examples)
    ↓
3. Pre-validate (check table/column names exist)
    ↓
4. Safety Guard (blocklist + whitelist)
    ↓
5. Execute SQL (with 60s timeout)
    ↓
6. Format Answer (AI summarizes results)
    ↓
Return: { answer, sql, rows_count }
```

### Key Design Decisions

- **Few-shot prompting:** 3-5 example question-SQL pairs teach the AI the schema
- **Pre-validation:** Catches AI hallucinations before wasting database queries
- **Defense in depth:** Two layers of safety validation (blocklist + whitelist)
- **Always summarize:** Consistent UX - every answer is natural language
- **Transparent:** Always return the SQL query alongside the answer
- **Stateless:** No caching or session state (simplifies Phase 2, defer to Phase 5)

## Switching AI Providers

To switch between AI providers, simply update the `.env` file:

**DeepSeek (default):**
```env
AI_PROVIDER="deepseek"
AI_API_KEY="your_deepseek_key"
AI_BASE_URL="https://api.deepseek.com"
AI_MODEL="deepseek-chat"
SDK_TYPE="openai_compatible"
```

**OpenAI:**
```env
AI_PROVIDER="openai"
AI_API_KEY="sk-..."
AI_BASE_URL="https://api.openai.com/v1"
AI_MODEL="gpt-4o"
SDK_TYPE="openai_compatible"
```

**Anthropic Claude:**
```env
AI_PROVIDER="anthropic"
AI_API_KEY="sk-ant-..."
AI_MODEL="claude-sonnet-4-20250514"
SDK_TYPE="anthropic"
```

No code changes required — just restart the service after updating `.env`.

## Next Steps

Phase 2 establishes the core AI pipeline. Future phases will add:
- **Phase 3**: API endpoints with FastAPI and security middleware
- **Phase 4**: Frontend chat UI
- **Phase 5**: Testing, hardening, and optimization (caching, query optimization)

## Related Documentation

- [Phase 1 Requirements](docs/brainstorms/admin-chatbot-requirements.md)
- [Phase 1 Plan](docs/plans/2026-04-20-001-feat-admin-chatbot-phase1-setup-plan.md)
- [Phase 2 Requirements](docs/brainstorms/admin-chatbot-phase2-requirements.md)
- [Phase 2 Plan](docs/plans/2026-04-20-002-feat-admin-chatbot-phase2-sql-pipeline-plan.md)
- [Tank Depot Backend](../tank-depot/server/)
