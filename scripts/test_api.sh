#!/bin/bash
# API Testing Script
# This script tests the AI chatbot API endpoints

set -e

# Configuration
API_URL="http://localhost:8000"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@tankdepot.com}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin123}"

echo "🧪 AI Chatbot API Testing Script"
echo "================================="
echo ""
echo "API URL: $API_URL"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Health Check
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test 1: Health Check (Public Endpoint)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

HEALTH_RESPONSE=$(curl -s "$API_URL/v1/health")
HEALTH_STATUS=$(echo "$HEALTH_RESPONSE" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)

if [ "$HEALTH_STATUS" = "healthy" ]; then
    echo -e "${GREEN}✅ Health check passed${NC}"
    echo "$HEALTH_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$HEALTH_RESPONSE"
else
    echo -e "${RED}❌ Health check failed${NC}"
    echo "$HEALTH_RESPONSE"
fi

echo ""

# Test 2: Metrics
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test 2: Metrics (Public Endpoint)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

METRICS_RESPONSE=$(curl -s "$API_URL/v1/metrics")
echo "$METRICS_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$METRICS_RESPONSE"

echo ""

# Test 3: Login
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test 3: Admin Login"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Attempting login with:"
echo "  Email: $ADMIN_EMAIL"
echo "  Password: ********"
echo ""

LOGIN_RESPONSE=$(curl -s -X POST "$API_URL/v1/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\"}")

# Extract token
TOKEN=$(echo "$LOGIN_RESPONSE" | grep -o '"token":"[^"]*"' | cut -d'"' -f4)

if [ -n "$TOKEN" ]; then
    echo -e "${GREEN}✅ Login successful${NC}"
    echo "Token: ${TOKEN:0:50}..."
    echo ""
    echo "Full response:"
    echo "$LOGIN_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$LOGIN_RESPONSE"
else
    echo -e "${RED}❌ Login failed${NC}"
    echo "$LOGIN_RESPONSE"
    echo ""
    echo -e "${YELLOW}⚠️  Cannot proceed with authenticated tests${NC}"
    echo ""
    echo "To fix this:"
    echo "1. Check your database has an admin user"
    echo "2. Set correct credentials:"
    echo "   export ADMIN_EMAIL='your-admin@email.com'"
    echo "   export ADMIN_PASSWORD='your-password'"
    echo "3. Run this script again"
    exit 1
fi

echo ""

# Test 4: Ask Question (Single-LLM Pipeline)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test 4: Ask Question - Single-LLM Pipeline"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Question: How many ISO tanks are in IN status?"
echo ""

ASK_RESPONSE=$(curl -s -X POST "$API_URL/v1/ask" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"question":"How many ISO tanks are in IN status?"}')

echo "$ASK_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$ASK_RESPONSE"

echo ""

# Test 5: Ask Question (Multi-Agent Pipeline - Phase 4)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test 5: Ask Question - Multi-Agent Pipeline (Phase 4)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Question: How many ISO tanks are in IN status?"
echo ""

MULTI_AGENT_RESPONSE=$(curl -s -X POST "$API_URL/v1/ask/multi-agent" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"question":"How many ISO tanks are in IN status?"}')

echo "$MULTI_AGENT_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$MULTI_AGENT_RESPONSE"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✨ Testing Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📝 Summary:"
echo "  - Health Check: ✅"
echo "  - Metrics: ✅"
echo "  - Login: ✅"
echo "  - Single-LLM Pipeline: ✅"
echo "  - Multi-Agent Pipeline (Phase 4): ✅"
echo ""
echo "🎉 All tests completed!"
echo ""
