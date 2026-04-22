#!/bin/bash
# MCP Server Setup Script
# This script helps you set up the MCP PostgreSQL server for Phase 4 integration

set -e

echo "🚀 MCP Server Setup for Tank Depot"
echo "=================================="
echo ""

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "❌ uv is not installed"
    echo ""
    echo "Installing uv (Python package manager)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    echo ""
    echo "✅ uv installed successfully"
    echo "⚠️  Please restart your terminal and run this script again"
    exit 0
fi

echo "✅ uv is installed"
echo ""

# Load database credentials from .env
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
    echo "✅ Loaded database credentials from .env"
else
    echo "⚠️  .env file not found, using defaults"
    DATABASE_URL="postgresql://postgres:postgres@localhost:5432/tank_depot"
fi

echo ""
echo "Database URL: $DATABASE_URL"
echo ""

# Check if PostgreSQL is running
echo "Checking PostgreSQL connection..."
if pg_isready -h localhost -p 5432 &> /dev/null; then
    echo "✅ PostgreSQL is running"
else
    echo "❌ PostgreSQL is not running"
    echo ""
    echo "Please start PostgreSQL first:"
    echo "  - macOS: brew services start postgresql"
    echo "  - Linux: sudo systemctl start postgresql"
    echo "  - Docker: docker-compose up -d postgres"
    exit 1
fi

echo ""
echo "Starting MCP PostgreSQL server..."
echo "=================================="
echo ""
echo "The MCP server will run on http://localhost:3000"
echo "Press Ctrl+C to stop the server"
echo ""

# Run MCP server
uvx mcp-server-postgres "$DATABASE_URL"
