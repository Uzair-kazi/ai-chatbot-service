# Admin AI Chatbot — Phase 3 Requirements
> Production-Ready API: FastAPI Endpoints, Security Middleware, and Monitoring
> 
> **Date:** April 20, 2026  
> **Status:** Ready for Planning

---

## Problem Statement

Phase 1 established the foundation (database access, AI provider config, authentication). Phase 2 built the core intelligence pipeline (SQL generation, validation, execution, formatting). Phase 3 exposes this functionality through a production-ready REST API.

Admins need a reliable, secure, and well-documented HTTP API to:
- Submit natural language questions
- Receive formatted answers with SQL transparency
- Monitor service health and performance
- Be protected from abuse through rate limiting

## Solution Overview

Build a FastAPI application that wraps the Phase 2 pipeline with production-grade features: authentication, rate limiting, CORS, error handling, health checks, and auto-generated API documentation.

**API Structure:**
```
POST /v1/ask          - Submit a question (requires JWT auth)
GET  /v1/health       - Health check endpoint
GET  /v1/metrics      - Service metrics (optional)
GET  /docs            - Auto-generated Swagger UI
GET  /redoc           - Auto-generated ReDoc UI
```

## Goals

1. **Production-Ready** — Secure, monitored, and resilient API
2. **Developer-Friendly** — Auto-generated docs, clear error messages
3. **Future-Proof** — Versioned endpoints (`/v1/`) for backward compatibility
4. **Observable** — Health checks and metrics for monitoring
5. **Secure** — JWT auth, rate limiting, CORS protection

## Non-Goals

- Redis-based rate limiting (defer to Phase 5 - use in-memory for now)
- Query history/persistence (defer to Phase 5)
- WebSocket support for streaming responses (defer to Phase 5)
- Multi-tenancy or organization-level isolation (single admin role only)
- Advanced metrics (Prometheus, Grafana) - basic metrics only

## User Personas

**Primary:** Frontend developers integrating the chatbot
- Need clear API documentation
- Expect standard REST conventions
- Want predictable error responses
- Need CORS support for local development

**Secondary:** DevOps/SRE teams
- Need health check endpoints for monitoring
- Want structured error logs
- Expect graceful degradation under load

## Success Criteria

1. **API Completeness:** All endpoints documented and functional
2. **Security:** 100% of requests require valid JWT tokens
3. **Rate Limiting:** Enforces 20 requests/minute per user
4. **Error Handling:** All errors return consistent JSON format
5. **Documentation:** Auto-generated OpenAPI docs accessible at `/docs`
6. **Health Monitoring:** `/health` endpoint returns service status

## Architecture Decisions

### API Versioning: `/v1/` Prefix

**Decision:** All endpoints use `/v1/` prefix for future-proofing.

**Rationale:**
- Allows breaking changes in `/v2/` without affecting existing clients
- Industry standard practice for REST APIs
- Low cost to implement upfront, high cost to retrofit later

**Trade-offs:**
- Slightly longer URLs
- Requires discipline to maintain version consistency

**Implementation:**
```python
# API Router with version prefix
api_router = APIRouter(prefix="/v1")

@api_router.post("/ask")
async def ask_question(...):
    ...
```

### In-Memory Rate Limiting

**Decision:** Use in-memory rate limiting with sliding window algorithm.

**Rationale:**
- Simple to implement (no external dependencies)
- Sufficient for single-instance deployment
- Easy to test and debug
- Can be upgraded to Redis in Phase 5 if needed

**Trade-offs:**
- Rate limits reset on service restart
- Not suitable for multi-instance deployments (yet)
- No persistence across restarts

**Implementation:**
- Track requests per user ID in a dictionary
- Use sliding window: `{user_id: [(timestamp1, timestamp2, ...)]}`
- Clean up old entries periodically
- Limit: 20 requests per 60-second window

**Phase 5 Enhancement Path:**
Document how to swap in Redis-based rate limiting:
```python
# Phase 3: In-memory
rate_limiter = InMemoryRateLimiter(max_requests=20, window_seconds=60)

# Phase 5: Redis (drop-in replacement)
rate_limiter = RedisRateLimiter(max_requests=20, window_seconds=60, redis_url=...)
```

### CORS: Allow All Origins (Development Mode)

**Decision:** Allow all origins (`*`) by default, with environment variable override.

**Rationale:**
- Simplifies local development (no CORS errors)
- Can be restricted in production via `CORS_ORIGINS` environment variable
- FastAPI makes this easy to configure

**Trade-offs:**
- Less secure if deployed without configuring `CORS_ORIGINS`
- Requires documentation to remind users to set production origins

**Implementation:**
```python
# Default: Allow all origins for development
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Production Configuration:**
```env
# .env for production
CORS_ORIGINS="https://admin.tankdepot.com,https://staging.tankdepot.com"
```

### Error Response Format

**Decision:** Consistent JSON error format for all failures.

**Format:**
```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests. Please wait before trying again.",
    "status": 429,
    "timestamp": "2026-04-20T10:30:00Z"
  }
}
```

**Rationale:**
- Predictable structure for frontend error handling
- Includes machine-readable error code
- Human-readable message
- Timestamp for debugging

**Error Codes:**
- `UNAUTHORIZED` - Missing or invalid JWT token
- `FORBIDDEN` - Valid token but not admin role
- `RATE_LIMIT_EXCEEDED` - Too many requests
- `INVALID_REQUEST` - Malformed request body
- `QUERY_UNSAFE` - SQL safety check failed
- `QUERY_TIMEOUT` - Query exceeded 60s timeout
- `DATABASE_ERROR` - Database connection failure
- `AI_SERVICE_ERROR` - AI provider API failure
- `INTERNAL_ERROR` - Unexpected server error

## Functional Requirements

### FR1: POST /v1/ask - Submit Question

**As an admin, I can submit a natural language question and receive an answer.**

**Request:**
```http
POST /v1/ask HTTP/1.1
Host: localhost:8000
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "question": "How many ISO tanks are in 'IN' status?"
}
```

**Response (Success):**
```json
{
  "answer": "There are currently 47 ISO tanks with status 'IN'.",
  "sql": "SELECT COUNT(*) FROM iso_tank WHERE iso_tank_status = 'IN' LIMIT 100;",
  "rows_count": 1,
  "execution_time_ms": 1234,
  "timestamp": "2026-04-20T10:30:00Z"
}
```

**Response (Error):**
```json
{
  "error": {
    "code": "QUERY_UNSAFE",
    "message": "That question can't be answered safely.",
    "status": 400,
    "timestamp": "2026-04-20T10:30:00Z"
  }
}
```

**Acceptance Criteria:**
- Requires valid JWT token in `Authorization: Bearer <token>` header
- Validates request body with Pydantic model
- Calls `chatbot_pipeline.ask(question)` from Phase 2
- Maps pipeline status codes to HTTP status codes
- Returns consistent JSON format
- Logs request and response to `logs/chat_audit.log`
- Enforces rate limiting (20 requests/minute per user)

**Validation Rules:**
- `question` field is required
- `question` must be a non-empty string
- `question` must be between 1 and 500 characters

### FR2: GET /v1/health - Health Check

**As a monitoring system, I can check if the service is healthy.**

**Request:**
```http
GET /v1/health HTTP/1.1
Host: localhost:8000
```

**Response (Healthy):**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "checks": {
    "database": "ok",
    "ai_provider": "ok"
  },
  "timestamp": "2026-04-20T10:30:00Z"
}
```

**Response (Unhealthy):**
```json
{
  "status": "unhealthy",
  "version": "1.0.0",
  "checks": {
    "database": "error: connection refused",
    "ai_provider": "ok"
  },
  "timestamp": "2026-04-20T10:30:00Z"
}
```

**Acceptance Criteria:**
- No authentication required (public endpoint)
- Returns 200 if all checks pass
- Returns 503 if any check fails
- Checks database connectivity (simple SELECT 1 query)
- Checks AI provider configuration (validates env vars, no API call)
- Includes service version from environment variable or package metadata
- Response time under 1 second

### FR3: GET /v1/metrics - Service Metrics (Optional)

**As an operator, I can view basic service metrics.**

**Request:**
```http
GET /v1/metrics HTTP/1.1
Host: localhost:8000
```

**Response:**
```json
{
  "requests": {
    "total": 1234,
    "success": 1100,
    "errors": 134
  },
  "rate_limiting": {
    "active_users": 5,
    "blocked_requests": 23
  },
  "performance": {
    "avg_response_time_ms": 2345,
    "p95_response_time_ms": 4500,
    "p99_response_time_ms": 8900
  },
  "timestamp": "2026-04-20T10:30:00Z"
}
```

**Acceptance Criteria:**
- No authentication required (public endpoint)
- Tracks request counts (total, success, errors)
- Tracks rate limiting stats
- Tracks response time percentiles
- Resets on service restart (in-memory only)
- Response time under 100ms

**Note:** This is a basic metrics endpoint. Phase 5 can add Prometheus integration.

### FR4: JWT Authentication Middleware

**As a system, I protect all `/v1/ask` endpoints with JWT authentication.**

**Acceptance Criteria:**
- Extract JWT token from `Authorization: Bearer <token>` header
- Validate token signature using `JWT_SECRET_KEY`
- Check token expiration
- Verify user has admin role
- Return 401 if token is missing, invalid, or expired
- Return 403 if user is not admin
- Attach decoded user payload to request context

**Error Responses:**

| Scenario | Status | Error Code | Message |
|----------|--------|------------|---------|
| Missing header | 401 | `UNAUTHORIZED` | "Authorization header is required" |
| Invalid format | 401 | `UNAUTHORIZED` | "Invalid Authorization header format" |
| Expired token | 401 | `UNAUTHORIZED` | "Token has expired" |
| Invalid signature | 401 | `UNAUTHORIZED` | "Invalid token signature" |
| Not admin | 403 | `FORBIDDEN` | "Admin access required" |

**Implementation:**
- Use existing `middleware/auth.py` functions
- Apply as FastAPI dependency: `Depends(get_current_admin_user)`
- Health and metrics endpoints bypass authentication

### FR5: Rate Limiting Middleware

**As a system, I limit each user to 20 requests per minute.**

**Acceptance Criteria:**
- Track requests per user ID (from JWT token)
- Use sliding window algorithm (60-second window)
- Allow 20 requests per window
- Return 429 if limit exceeded
- Include `Retry-After` header with seconds until next allowed request
- Clean up old entries every 5 minutes to prevent memory leaks

**Error Response:**
```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests. Please wait 45 seconds before trying again.",
    "status": 429,
    "retry_after": 45,
    "timestamp": "2026-04-20T10:30:00Z"
  }
}
```

**HTTP Headers:**
```
HTTP/1.1 429 Too Many Requests
Retry-After: 45
X-RateLimit-Limit: 20
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1713612045
```

**Implementation:**
- In-memory dictionary: `{user_id: [timestamp1, timestamp2, ...]}`
- Filter timestamps older than 60 seconds
- Count remaining timestamps
- If count >= 20, reject with 429
- Background task cleans up old entries every 5 minutes

### FR6: CORS Middleware

**As a frontend developer, I can make requests from my local development environment.**

**Acceptance Criteria:**
- Allow all origins by default (`*`)
- Support environment variable override: `CORS_ORIGINS`
- Allow credentials (cookies, authorization headers)
- Allow all HTTP methods
- Allow all headers
- Include proper CORS headers in responses

**Configuration:**
```env
# Development (default)
CORS_ORIGINS="*"

# Production
CORS_ORIGINS="https://admin.tankdepot.com,https://staging.tankdepot.com"
```

**Implementation:**
- Use FastAPI's `CORSMiddleware`
- Parse `CORS_ORIGINS` as comma-separated list
- Default to `["*"]` if not set

### FR7: Global Exception Handler

**As a system, I handle all exceptions gracefully and return consistent error responses.**

**Acceptance Criteria:**
- Catch all unhandled exceptions
- Log full stack trace server-side
- Return user-friendly error message
- Never expose internal details (stack traces, file paths, etc.)
- Return consistent JSON error format
- Map exception types to appropriate HTTP status codes

**Exception Mapping:**

| Exception Type | Status | Error Code | Message |
|----------------|--------|------------|---------|
| `ValidationError` (Pydantic) | 400 | `INVALID_REQUEST` | "Invalid request format" |
| `HTTPException` (FastAPI) | varies | varies | (use exception message) |
| `SQLGenerationError` | 500 | `AI_SERVICE_ERROR` | "Failed to generate SQL query" |
| `QueryTimeoutError` | 504 | `QUERY_TIMEOUT` | "Query took too long" |
| `DatabaseConnectionError` | 503 | `DATABASE_ERROR` | "Database unavailable" |
| `SQLSyntaxError` | 400 | `INVALID_REQUEST` | "Invalid SQL generated" |
| `PermissionDeniedError` | 403 | `FORBIDDEN` | "Access denied" |
| `Exception` (catch-all) | 500 | `INTERNAL_ERROR` | "An unexpected error occurred" |

**Implementation:**
- Use FastAPI's `@app.exception_handler` decorator
- Import custom exceptions from Phase 2 services
- Log full exception details with `logger.exception()`
- Return sanitized error response

### FR8: Request/Response Logging

**As a system, I log all API requests and responses for audit and debugging.**

**Log Format:**
```
2026-04-20 10:30:00 - api - INFO - POST /v1/ask - user_id=123 - status=200 - duration=1234ms
```

**Log Fields:**
- Timestamp
- HTTP method and path
- User ID (from JWT token)
- Response status code
- Request duration in milliseconds
- Error message (if failed)

**Acceptance Criteria:**
- Log every request to `logs/chat_audit.log`
- Use existing logging configuration from Phase 2
- Include request ID for tracing (generated UUID)
- Log request body for `/v1/ask` (question only, not full payload)
- Never log sensitive data (JWT tokens, passwords)

### FR9: Auto-Generated API Documentation

**As a developer, I can view interactive API documentation.**

**Acceptance Criteria:**
- Swagger UI available at `/docs`
- ReDoc UI available at `/redoc`
- OpenAPI schema available at `/openapi.json`
- All endpoints documented with:
  - Request/response schemas
  - Example requests and responses
  - Authentication requirements
  - Error responses
- Documentation includes descriptions and examples

**Implementation:**
- FastAPI generates this automatically
- Add docstrings to endpoint functions
- Use Pydantic models for request/response validation
- Include `examples` in Pydantic models

## Technical Constraints

### FastAPI

- **Version:** `fastapi>=0.110.0`
- **Server:** `uvicorn[standard]>=0.29.0`
- **Validation:** Pydantic models for request/response
- **Middleware:** CORS, authentication, rate limiting, exception handling

### Deployment

- **Port:** Configurable via `PORT` environment variable (default: 8000)
- **Host:** `0.0.0.0` (listen on all interfaces)
- **Workers:** Single worker for Phase 3 (in-memory rate limiting)
- **Reload:** Disabled in production, enabled in development

### Environment Variables

New variables for Phase 3:
```env
# Server Configuration
PORT=8000
HOST=0.0.0.0
ENVIRONMENT=development  # or "production"

# CORS Configuration
CORS_ORIGINS=*  # Comma-separated list, or "*" for all

# Rate Limiting
RATE_LIMIT_REQUESTS=20
RATE_LIMIT_WINDOW_SECONDS=60

# Service Metadata
SERVICE_VERSION=1.0.0
```

### Performance

- `/v1/ask` endpoint: < 5 seconds (typical), < 65 seconds (max with timeout)
- `/v1/health` endpoint: < 1 second
- `/v1/metrics` endpoint: < 100ms
- Rate limiting overhead: < 10ms per request

## Implementation Units (High-Level)

Phase 3 will be broken into these implementation units during planning:

1. **FastAPI Application Setup** — Main app, routers, middleware stack
2. **Request/Response Models** — Pydantic models for validation
3. **POST /v1/ask Endpoint** — Main chatbot endpoint with auth
4. **Rate Limiting Middleware** — In-memory sliding window rate limiter
5. **CORS Middleware** — Cross-origin request handling
6. **Global Exception Handler** — Consistent error responses
7. **Health Check Endpoint** — GET /v1/health with dependency checks
8. **Metrics Endpoint** — GET /v1/metrics with basic stats
9. **Request Logging** — Audit trail for all requests
10. **API Documentation** — Swagger/ReDoc with examples
11. **Testing Suite** — API integration tests

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| In-memory rate limiting doesn't scale to multiple instances | Document Redis upgrade path in Phase 5; sufficient for single-instance deployment |
| CORS `*` is insecure in production | Document production configuration; add warning in README |
| Rate limit resets on restart | Acceptable for Phase 3; Redis persistence in Phase 5 |
| No request ID tracing across services | Add request ID header; can integrate with distributed tracing in Phase 5 |
| Metrics are basic and reset on restart | Sufficient for Phase 3; Prometheus integration in Phase 5 |

## Open Questions

### Resolved During Brainstorming

**Q:** Should we use Redis for rate limiting?  
**A:** No - start with in-memory, document Redis upgrade path for Phase 5.

**Q:** How should we handle CORS?  
**A:** Allow all origins by default for development, support environment variable override for production.

**Q:** Should we version the API?  
**A:** Yes - use `/v1/` prefix for future-proofing.

### Deferred to Implementation

**Q:** Exact structure of metrics response  
**Why deferred:** Need to see what metrics are easy to track during implementation.

**Q:** Whether to include request ID in all responses  
**Why deferred:** Depends on whether it adds value for debugging; can add if needed.

## Success Metrics

**Phase 3 is successful when:**

1. **API Completeness:** All endpoints (`/v1/ask`, `/v1/health`, `/v1/metrics`) are functional
2. **Security:** 100% of `/v1/ask` requests require valid JWT tokens
3. **Rate Limiting:** Enforces 20 requests/minute per user
4. **Documentation:** Swagger UI at `/docs` is complete and accurate
5. **Error Handling:** All errors return consistent JSON format
6. **Health Monitoring:** `/v1/health` accurately reports service status

## References

- **Phase 1 Requirements:** `docs/brainstorms/admin-chatbot-requirements.md`
- **Phase 1 Plan:** `docs/plans/2026-04-20-001-feat-admin-chatbot-phase1-setup-plan.md`
- **Phase 2 Requirements:** `docs/brainstorms/admin-chatbot-phase2-requirements.md`
- **Phase 2 Plan:** `docs/plans/2026-04-20-002-feat-admin-chatbot-phase2-sql-pipeline-plan.md`
- **Existing Auth Middleware:** `middleware/auth.py`
- **Pipeline Orchestrator:** `services/chatbot_pipeline.py`

---

**Next Steps:** Create implementation plan for Phase 3 with detailed tasks and test scenarios.
