# Admin AI Chatbot - Phase 1: Setup

AI-powered chatbot for the Tank Depot admin panel that translates natural language questions into SQL queries.

## Phase 1 Scope

This phase establishes the foundational infrastructure:
- Python project structure and dependency management
- Read-only PostgreSQL user for secure database access
- Automatic database schema introspection
- Swappable AI provider configuration (DeepSeek, OpenAI, Anthropic, etc.)
- JWT authentication middleware for admin-only access

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
│   └── ai_provider.py          # AI client initialization
├── services/
│   └── schema.py               # Database schema introspection
├── middleware/
│   └── auth.py                 # JWT validation and admin check
├── scripts/
│   ├── create_readonly_user.sql
│   └── test_readonly_user.sql
├── logs/
│   └── .gitkeep                # Placeholder for chat_audit.log
├── tests/
│   ├── test_schema.py
│   ├── test_ai_provider.py
│   └── test_auth.py
├── .env                        # Environment variables (gitignored)
├── .env.example                # Environment template
├── .gitignore                  # Python-specific ignores
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

## Security Notes

- **Never commit `.env` to git** — it contains sensitive credentials
- The `chatbot_readonly` database user can only read data, never modify it
- JWT tokens must match the Node.js backend's format exactly
- Rotate `JWT_SECRET_KEY` if it is ever exposed
- Use a strong password for the `chatbot_readonly` PostgreSQL user
- Restrict network access to the PostgreSQL database using firewall rules

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

Phase 1 establishes the foundation. Future phases will add:
- **Phase 2**: Core AI pipeline (SQL generation, execution, formatting)
- **Phase 3**: API endpoints and security middleware
- **Phase 4**: Frontend chat UI
- **Phase 5**: Testing and hardening

## Related Documentation

- [Requirements Document](docs/brainstorms/admin-chatbot-requirements.md)
- [Implementation Plan](docs/plans/2026-04-20-001-feat-admin-chatbot-phase1-setup-plan.md)
- [Tank Depot Backend](../tank-depot/server/)
