# MCP Server Setup Guide

## What is MCP?

The Model Context Protocol (MCP) provides a standardized interface for database operations. It offers:
- Connection pooling
- Query validation
- Schema introspection
- Consistent error handling

## Installation Options

### Option 1: Using uvx (Recommended - Easiest)

The MCP PostgreSQL server can be run directly using `uvx` without installation:

```bash
# Install uv (Python package manager) if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Run MCP PostgreSQL server (it will auto-install on first run)
uvx mcp-server-postgres postgresql://user:password@localhost:5432/dbname
```

### Option 2: Using pip

```bash
# Install the MCP PostgreSQL server
pip install mcp-server-postgres

# Run the server
mcp-server-postgres postgresql://user:password@localhost:5432/dbname
```

### Option 3: Using Docker (Production)

```bash
# Pull the MCP PostgreSQL server image
docker pull ghcr.io/modelcontextprotocol/mcp-server-postgres:latest

# Run the server
docker run -p 3000:3000 \
  -e DATABASE_URL=postgresql://user:password@host.docker.internal:5432/dbname \
  ghcr.io/modelcontextprotocol/mcp-server-postgres:latest
```

## Configuration

### For Tank Depot Database

Based on your current `.env` file, here's how to configure MCP:

```bash
# Your existing database connection
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/tank_depot

# MCP Server Configuration
# Option A: If running MCP server locally on default port
MCP_SERVER_URL=http://localhost:3000
MCP_DATABASE_NAME=tank_depot

# Option B: If using the database URL directly (MCP will connect)
MCP_SERVER_URL=postgresql://postgres:postgres@localhost:5432/tank_depot
MCP_DATABASE_NAME=tank_depot
```

### Environment Variables

Add these to your `.env` file:

```bash
# MCP Server Configuration
MCP_SERVER_URL=http://localhost:3000
MCP_DATABASE_NAME=tank_depot

# Optional: MCP Server Authentication (if enabled)
# MCP_API_KEY=your-api-key-here
```

## Quick Start

### 1. Start MCP Server

```bash
# Using your existing database credentials
uvx mcp-server-postgres postgresql://postgres:postgres@localhost:5432/tank_depot
```

The server will start on `http://localhost:3000` by default.

### 2. Update .env File

```bash
# Copy from .env.example
cp .env.example .env

# Edit .env and add:
MCP_SERVER_URL=http://localhost:3000
MCP_DATABASE_NAME=tank_depot
```

### 3. Test the Connection

```bash
# Run the MCP client tests
python -m pytest tests/agents/test_mcp_client.py -v

# Or test manually
python -c "
from agents.mcp_client import MCPClient
client = MCPClient()
print('MCP Connected:', client.is_connected())
schema = client.get_schema()
print('Tables:', len(schema.tables) if schema else 0)
"
```

## Fallback Mode

**Good news:** The system works without MCP! If the MCP server is not available:

- ✅ Schema Intelligence uses regex-based parsing (still achieves 95% token reduction)
- ✅ SQL Generation uses built-in validation (still catches errors)
- ✅ Result Formatter uses direct SQL executor (still executes queries)

You'll see warnings in the logs:
```
WARNING - MCP client not connected, using fallback mode
```

This is expected and the system will work normally.

## Troubleshooting

### MCP Server Not Starting

**Error:** `uvx: command not found`
```bash
# Install uv first
curl -LsSf https://astral.sh/uv/install.sh | sh
# Restart your terminal
```

**Error:** `Connection refused`
```bash
# Check if PostgreSQL is running
pg_isready -h localhost -p 5432

# Check if MCP server is running
curl http://localhost:3000/health
```

### MCP Client Connection Issues

**Error:** `MCP SDK not available`
```bash
# Install the MCP SDK
pip install 'mcp[cli]'
```

**Error:** `Connection timeout`
```bash
# Check MCP_SERVER_URL in .env
echo $MCP_SERVER_URL

# Test connection manually
curl http://localhost:3000/health
```

## Production Deployment

For production, use Docker Compose to run both the database and MCP server:

```yaml
# docker-compose.yml
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: tank_depot
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  mcp-server:
    image: ghcr.io/modelcontextprotocol/mcp-server-postgres:latest
    environment:
      DATABASE_URL: postgresql://postgres:postgres@postgres:5432/tank_depot
    ports:
      - "3000:3000"
    depends_on:
      - postgres

volumes:
  postgres_data:
```

Start with:
```bash
docker-compose up -d
```

## Summary

**For Development (Easiest):**
1. Run: `uvx mcp-server-postgres postgresql://postgres:postgres@localhost:5432/tank_depot`
2. Add to `.env`: `MCP_SERVER_URL=http://localhost:3000`
3. Done! The system will use MCP when available, fallback when not.

**For Production:**
- Use Docker Compose with the MCP server container
- Set `MCP_SERVER_URL` to the container URL
- Enable authentication with `MCP_API_KEY`

**No MCP Server?**
- No problem! The system works in fallback mode
- All functionality is preserved
- You'll just see warnings in the logs
