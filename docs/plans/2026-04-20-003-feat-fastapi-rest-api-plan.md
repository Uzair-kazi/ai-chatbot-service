---
title: Production-Ready FastAPI REST API
type: feat
status: active
date: 2026-04-20
origin: docs/brainstorms/admin-chatbot-phase3-requirements.md
---

# Production-Ready FastAPI REST API

## Overview

Phase 3 wraps the Phase 2 SQL pipeline with a production-ready FastAPI REST API. This adds HTTP endpoints, JWT authentication, rate limiting, CORS, error handling, health checks, metrics, and auto-generated OpenAPI documentation.

## Problem Frame

Admins need a reliable, secure, and well-documented HTTP API to submit natural language questions, receive formatted answers with SQL transparency, monitor service health, and be protected from abuse through rate limiting. The Phase 2 pipeline (`services/chatbot_pipeline.py`) already handles the core intelligence work - this phase exposes it through a production HTTP interface.

## Requirements Trace

- R1. **API Completeness:** All endpoints (`/v1/ask`, `/v1/health`, `/v1/metrics`) documented and functional
- R2. **Security:** 100% of `/v1/ask` requests require valid JWT tokens
- R3. **Rate Limiting:** Enforces 20 requests/minute per user
- R4. **Error Handling:** All errors return consistent JSON format
- R5. **Documentation:** Auto-generated OpenAPI docs accessible at `/docs`
- R6. **Health Monitoring:** `/v1/health` endpoint returns service status

## Scope Boundaries

**In scope:**
- FastAPI application with `/v1/` versioned endpoints
- JWT authentication using existing `middleware/auth.py`
- In-memory rate limiting (sliding window, 20 req/min per user)
- CORS middleware (allow `*` by default, env override for production)
- Consistent JSON error responses
- Health check with database and AI provider validation
- Basic metrics endpoint (request counts, rate limiting stats, response times)
- Request/response logging to `logs/chat_audit.log`
- Auto-generated Swagger UI and ReDoc

**Out of scope (deferred to Phase 5):**
- Redis-based rate limiting
- Query history/persistence
- WebSocket support for streaming responses
- Multi-tenancy or organization-level isolation
- Advanced metrics (Prometheus, Grafana)

## Context & Research

### Relevant Code and Patterns

- `middleware/auth.py` - JWT validation with `get_current_admin_user()` FastAPI dependency
- `services/chatbot_pipeline.py` - Returns `{answer, sql, rows_count, status_code, error}`
- `config/logging_config.py` - Logging configuration
- Exception classes: `SQLGenerationError`, `QueryTimeoutError`, `DatabaseConnectionError`, `SQLSyntaxError`, `PermissionDeniedError`, `AnswerFormattingError`

### Technology Stack

- FastAPI >= 0.110.0
- Uvicorn[standard] >= 0.29.0
- Pydantic for request/response validation
- Existing: PyJWT, psycopg2, openai/anthropic SDKs

## Key Technical Decisions

**API Versioning (`/v1/` prefix):**
- Allows breaking changes in `/v2/` without affecting existing clients
- Industry standard practice
- Low cost to implement upfront, high cost to retrofit later
- (see origin: docs/brainstorms/admin-chatbot-phase3-requirements.md)

**In-Memory Rate Limiting:**
- Simple to implement, no external dependencies
- Sufficient for single-instance deployment
- Sliding window algorithm: track timestamps per user ID
- Trade-off: Rate limits reset on service restart, not suitable for multi-instance yet
- Phase 5 enhancement path documented for Redis upgrade
- (see origin: docs/brainstorms/admin-chatbot-phase3-requirements.md)

**CORS Allow All Origins (Development Mode):**
- Default `CORS_ORIGINS="*"` simplifies local development
- Environment variable override for production
- Trade-off: Less secure if deployed without configuring `CORS_ORIGINS`
- (see origin: docs/brainstorms/admin-chatbot-phase3-requirements.md)

**Consistent Error Response Format:**
- All errors return `{error: {code, message, status, timestamp}}`
- Predictable structure for frontend error handling
- Machine-readable error codes + human-readable messages
- (see origin: docs/brainstorms/admin-chatbot-phase3-requirements.md)

## Open Questions

### Resolved During Planning

None - all architectural decisions documented in origin requirements.

### Deferred to Implementation

- **Exact metrics response structure:** Will determine based on what's easy to track during implementation
- **Request ID in responses:** Will add if it proves valuable for debugging
- **Exact cleanup interval for rate limiter:** May adjust from 5 minutes based on memory profiling

## Output Structure

```
ai-service-croyance/
├── main.py                          # FastAPI application entry point
├── api/
│   ├── __init__.py
│   ├── routes.py                    # API route definitions
│   ├── models.py                    # Pydantic request/response models
│   ├── dependencies.py              # FastAPI dependencies (auth, rate limiting)
│   └── errors.py                    # Error response utilities
├── middleware/
│   ├── auth.py                      # (existing)
│   ├── rate_limiter.py              # In-memory rate limiting
│   ├── request_logger.py            # Request/response logging
│   └── cors.py                      # CORS configuration
├── tests/
│   ├── test_api_endpoints.py        # API integration tests
│   ├── test_rate_limiter.py         # Rate limiting tests
│   └── test_error_handling.py       # Error response tests
└── requirements.txt                 # (update with new dependencies)
```

## Implementation Units

- [ ] **Unit 1: FastAPI Application Setup**

**Goal:** Create the FastAPI application with basic structure, routers, and middleware stack.

**Requirements:** R1, R5

**Dependencies:** None

**Files:**
- Create: `main.py`
- Create: `api/__init__.py`
- Create: `api/routes.py`
- Modify: `requirements.txt`

**Approach:**
- Create FastAPI app instance in `main.py`
- Configure CORS middleware using `CORS_ORIGINS` env var (default `*`)
- Set up API router with `/v1` prefix
- Configure uvicorn server settings (host, port from env)
- Add basic startup/shutdown event handlers

**Patterns to follow:**
- FastAPI application factory pattern
- Environment-based configuration (similar to `config/ai_provider.py`)

**Test scenarios:**
- Happy path: App starts successfully and responds to health check
- Edge case: Missing environment variables use sensible defaults
- Error path: Invalid CORS_ORIGINS format is handled gracefully

**Verification:**
- `uvicorn main:app --reload` starts without errors
- OpenAPI docs accessible at `/docs`
- CORS headers present in responses

---

- [ ] **Unit 2: Pydantic Request/Response Models**

**Goal:** Define Pydantic models for request validation and response serialization.

**Requirements:** R1, R4

**Dependencies:** Unit 1

**Files:**
- Create: `api/models.py`
- Create: `tests/test_api_models.py`

**Approach:**
- `QuestionRequest` model: `question: str` with validation (1-500 chars, non-empty after trim)
- `AnswerResponse` model: `answer, sql, rows_count, execution_time_ms, timestamp`
- `ErrorResponse` model: `error: {code, message, status, timestamp}`
- `HealthResponse` model: `status, version, checks: {database, ai_provider}, timestamp`
- `MetricsResponse` model: `requests, rate_limiting, performance, timestamp`
- Add examples to models for OpenAPI docs

**Patterns to follow:**
- Pydantic BaseModel with Field validators
- ISO 8601 timestamps

**Test scenarios:**
- Happy path: Valid question request passes validation
- Edge case: Question with exactly 1 and 500 characters passes
- Edge case: Whitespace-only question is rejected
- Edge case: Question with 501 characters is rejected
- Error path: Empty question field returns validation error
- Error path: Non-string question field returns validation error

**Verification:**
- All models serialize/deserialize correctly
- Validation rules enforce constraints
- OpenAPI schema includes examples

---

- [ ] **Unit 3: POST /v1/ask Endpoint**

**Goal:** Implement the main chatbot endpoint that accepts questions and returns answers.

**Requirements:** R1, R2

**Dependencies:** Unit 2, existing `middleware/auth.py`, existing `services/chatbot_pipeline.py`

**Files:**
- Modify: `api/routes.py`
- Create: `tests/test_api_endpoints.py`

**Approach:**
- Define `POST /v1/ask` route with `Depends(get_current_admin_user)` for auth
- Accept `QuestionRequest` body
- Call `chatbot_pipeline.ask(question)`
- Map pipeline `status_code` to HTTP status
- Return `AnswerResponse` or `ErrorResponse` based on pipeline result
- Add endpoint docstring for OpenAPI docs

**Patterns to follow:**
- FastAPI dependency injection for auth
- Pipeline dict → Pydantic model mapping
- Existing pipeline error handling

**Test scenarios:**
- Happy path: Valid question with JWT returns answer
- Happy path: Response includes answer, SQL, row count, timestamp
- Error path: Missing Authorization header returns 401
- Error path: Invalid JWT token returns 401
- Error path: Expired JWT token returns 401
- Error path: Non-admin user returns 403
- Error path: Invalid question format returns 400
- Error path: Pipeline safety check failure returns 400
- Error path: Pipeline timeout returns 504
- Error path: Database connection failure returns 503
- Integration: End-to-end request with real JWT and pipeline

**Verification:**
- Endpoint requires valid JWT token
- Pipeline errors map to correct HTTP status codes
- Response format matches `AnswerResponse` schema

---

- [ ] **Unit 4: Rate Limiting Middleware**

**Goal:** Implement in-memory rate limiting with sliding window algorithm.

**Requirements:** R3

**Dependencies:** Unit 3

**Files:**
- Create: `middleware/rate_limiter.py`
- Create: `tests/test_rate_limiter.py`

**Approach:**
- Track requests per user ID in dict: `{user_id: [timestamp1, timestamp2, ...]}`
- Sliding window: filter timestamps older than 60 seconds
- Allow 20 requests per 60-second window
- Return 429 with `Retry-After` header if limit exceeded
- Background task cleans up old entries every 5 minutes
- Add rate limit headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`

**Patterns to follow:**
- FastAPI middleware pattern
- Background tasks for cleanup

**Test scenarios:**
- Happy path: First request from user passes
- Happy path: 20th request within 60 seconds passes
- Edge case: 21st request within 60 seconds returns 429
- Edge case: Request after 60 seconds resets window
- Edge case: Multiple users tracked independently
- Error path: 429 response includes Retry-After header
- Error path: 429 response includes rate limit headers
- Integration: Rate limit applies to /v1/ask but not /v1/health

**Verification:**
- Rate limiting enforces 20 req/min per user
- 429 responses include correct headers
- Cleanup task prevents memory leaks

---

- [ ] **Unit 5: CORS Middleware**

**Goal:** Configure CORS to allow cross-origin requests from frontend.

**Requirements:** R1

**Dependencies:** Unit 1

**Files:**
- Modify: `main.py`
- Modify: `.env.example`

**Approach:**
- Use FastAPI's `CORSMiddleware`
- Parse `CORS_ORIGINS` env var as comma-separated list
- Default to `["*"]` if not set
- Allow credentials, all methods, all headers

**Patterns to follow:**
- FastAPI middleware configuration
- Environment variable parsing (similar to `config/ai_provider.py`)

**Test scenarios:**
- Happy path: CORS headers present in responses
- Edge case: Multiple origins in CORS_ORIGINS are parsed correctly
- Edge case: Default `*` allows any origin

**Verification:**
- CORS headers present in all responses
- Preflight OPTIONS requests handled correctly
- Production config example in `.env.example`

---

- [ ] **Unit 6: Global Exception Handler**

**Goal:** Catch all unhandled exceptions and return consistent error responses.

**Requirements:** R4

**Dependencies:** Unit 2

**Files:**
- Create: `api/errors.py`
- Modify: `main.py`
- Create: `tests/test_error_handling.py`

**Approach:**
- Use FastAPI's `@app.exception_handler` decorator
- Map exception types to HTTP status codes and error codes:
  - `ValidationError` (Pydantic) → 400 `INVALID_REQUEST`
  - `HTTPException` (FastAPI) → varies
  - `SQLGenerationError` → 500 `AI_SERVICE_ERROR`
  - `QueryTimeoutError` → 504 `QUERY_TIMEOUT`
  - `DatabaseConnectionError` → 503 `DATABASE_ERROR`
  - `SQLSyntaxError` → 400 `INVALID_REQUEST`
  - `PermissionDeniedError` → 403 `FORBIDDEN`
  - `Exception` (catch-all) → 500 `INTERNAL_ERROR`
- Log full exception details with `logger.exception()`
- Return sanitized `ErrorResponse`

**Patterns to follow:**
- Existing exception classes from `services/`
- Logging via `config/logging_config.get_logger(__name__)`

**Test scenarios:**
- Happy path: Pydantic ValidationError returns 400 with INVALID_REQUEST
- Happy path: Pipeline exceptions map to correct status codes
- Error path: Unhandled exception returns 500 with INTERNAL_ERROR
- Error path: Stack traces never exposed in response
- Integration: Exception handler logs full details server-side

**Verification:**
- All exception types handled
- Error responses match `ErrorResponse` schema
- Stack traces logged but not exposed

---

- [ ] **Unit 7: Health Check Endpoint**

**Goal:** Implement health check endpoint for monitoring.

**Requirements:** R6

**Dependencies:** Unit 2

**Files:**
- Modify: `api/routes.py`
- Modify: `tests/test_api_endpoints.py`

**Approach:**
- Define `GET /v1/health` route (no auth required)
- Check database connectivity: simple `SELECT 1` query
- Check AI provider config: validate env vars exist (no API call)
- Return 200 if all checks pass, 503 if any fail
- Include service version from `SERVICE_VERSION` env var or package metadata
- Response time target: under 1 second

**Patterns to follow:**
- Database connection check (similar to `services/sql_executor.py`)
- Environment variable validation (similar to `config/ai_provider.py`)

**Test scenarios:**
- Happy path: All checks pass, returns 200 with healthy status
- Happy path: Response includes version and check details
- Error path: Database connection failure returns 503 with unhealthy status
- Error path: Missing AI env vars returns 503 with unhealthy status
- Edge case: Response time under 1 second

**Verification:**
- Health check accessible without authentication
- Returns correct status based on dependency health
- Response time under 1 second

---

- [ ] **Unit 8: Metrics Endpoint**

**Goal:** Implement basic metrics endpoint for operational visibility.

**Requirements:** R1

**Dependencies:** Unit 2, Unit 4

**Files:**
- Modify: `api/routes.py`
- Create: `middleware/metrics_tracker.py`
- Modify: `tests/test_api_endpoints.py`

**Approach:**
- Define `GET /v1/metrics` route (no auth required)
- Track in-memory metrics:
  - Request counts: total, success, errors
  - Rate limiting: active users, blocked requests
  - Performance: avg/p95/p99 response times
- Metrics reset on service restart
- Response time target: under 100ms

**Patterns to follow:**
- In-memory state management (similar to rate limiter)
- Middleware for request tracking

**Test scenarios:**
- Happy path: Metrics endpoint returns current stats
- Happy path: Request counts increment correctly
- Edge case: Metrics reset on service restart
- Edge case: Response time under 100ms

**Verification:**
- Metrics endpoint accessible without authentication
- Metrics track request activity accurately
- Response time under 100ms

---

- [ ] **Unit 9: Request Logging Middleware**

**Goal:** Log all API requests and responses for audit and debugging.

**Requirements:** R1

**Dependencies:** Unit 1

**Files:**
- Create: `middleware/request_logger.py`
- Modify: `main.py`

**Approach:**
- Middleware logs every request to `logs/chat_audit.log`
- Log format: `YYYY-MM-DD HH:MM:SS - api - INFO - METHOD /path - user_id=X - status=Y - duration=Zms`
- Include: timestamp, method, path, user ID (from JWT), status code, duration
- Generate request ID (UUID) for tracing
- Log request body for `/v1/ask` (question only, not full payload)
- Never log sensitive data (JWT tokens, passwords)

**Patterns to follow:**
- Logging via `config/logging_config.get_logger(__name__)`
- Existing log format in `logs/chat_audit.log`

**Test scenarios:**
- Happy path: Request logged with all required fields
- Happy path: Request ID generated and included
- Edge case: Unauthenticated requests log without user ID
- Error path: Sensitive data (JWT tokens) never logged

**Verification:**
- All requests logged to `logs/chat_audit.log`
- Log format matches specification
- No sensitive data in logs

---

- [ ] **Unit 10: API Documentation Enhancement**

**Goal:** Enhance auto-generated OpenAPI docs with descriptions and examples.

**Requirements:** R5

**Dependencies:** All previous units

**Files:**
- Modify: `api/routes.py`
- Modify: `api/models.py`
- Modify: `main.py`

**Approach:**
- Add docstrings to all endpoint functions
- Include request/response examples in Pydantic models
- Add authentication requirements to OpenAPI schema
- Document error responses for each endpoint
- Configure FastAPI app metadata (title, description, version)

**Patterns to follow:**
- FastAPI OpenAPI customization
- Pydantic model examples

**Test scenarios:**
- Happy path: Swagger UI accessible at `/docs`
- Happy path: ReDoc accessible at `/redoc`
- Happy path: OpenAPI schema at `/openapi.json`
- Edge case: All endpoints documented with examples
- Edge case: Authentication requirements visible in docs

**Verification:**
- Swagger UI and ReDoc accessible
- All endpoints documented with examples
- Authentication requirements clear

---

- [ ] **Unit 11: API Integration Tests**

**Goal:** Comprehensive integration tests for all API endpoints and middleware.

**Requirements:** All requirements

**Dependencies:** All previous units

**Files:**
- Modify: `tests/test_api_endpoints.py`
- Modify: `tests/test_rate_limiter.py`
- Modify: `tests/test_error_handling.py`

**Approach:**
- Use FastAPI TestClient for integration tests
- Test complete request/response cycles
- Test middleware interactions (auth + rate limiting + logging)
- Test error handling across all endpoints
- Mock external dependencies (database, AI provider) where appropriate

**Patterns to follow:**
- Existing test patterns in `tests/`
- FastAPI TestClient usage

**Test scenarios:**
- Integration: Complete /v1/ask flow with auth, rate limiting, logging
- Integration: Health check with database and AI provider checks
- Integration: Metrics endpoint tracks requests correctly
- Integration: Rate limiting applies to /v1/ask but not /v1/health
- Integration: Error responses consistent across all endpoints
- Integration: CORS headers present in all responses
- Integration: Request logging captures all required fields

**Verification:**
- All integration tests pass
- Test coverage includes all endpoints and middleware
- Tests run in isolation without side effects

## System-Wide Impact

**Interaction graph:**
- New FastAPI app wraps existing `services/chatbot_pipeline.py`
- Auth middleware (`middleware/auth.py`) integrated as FastAPI dependency
- Rate limiter middleware intercepts requests before routing
- Request logger middleware captures all requests/responses
- Exception handler catches all unhandled errors

**Error propagation:**
- Pipeline errors (from `services/`) → Exception handler → HTTP error response
- Auth failures → 401/403 HTTP responses
- Rate limit exceeded → 429 HTTP response
- Validation errors → 400 HTTP responses

**State lifecycle risks:**
- In-memory rate limiter state lost on restart (acceptable for Phase 3)
- In-memory metrics state lost on restart (acceptable for Phase 3)
- No state persistence required for Phase 3

**API surface parity:**
- `/v1/ask` is the only authenticated endpoint
- `/v1/health` and `/v1/metrics` are public
- All endpoints return consistent error format

**Integration coverage:**
- End-to-end tests verify auth + rate limiting + pipeline integration
- Health check tests verify database and AI provider connectivity
- Error handling tests verify exception → HTTP response mapping

**Unchanged invariants:**
- Phase 2 pipeline interface (`chatbot_pipeline.ask()`) remains unchanged
- Auth middleware interface (`get_current_admin_user()`) remains unchanged
- Logging configuration remains unchanged
- Database connection (read-only user) remains unchanged

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| In-memory rate limiting doesn't scale to multiple instances | Document Redis upgrade path; sufficient for single-instance deployment |
| CORS `*` is insecure in production | Document production configuration in `.env.example`; add warning in README |
| Rate limit resets on restart | Acceptable for Phase 3; Redis persistence in Phase 5 |
| Metrics are basic and reset on restart | Sufficient for Phase 3; Prometheus integration in Phase 5 |
| No request ID tracing across services | Add request ID header; can integrate with distributed tracing in Phase 5 |

## Documentation / Operational Notes

**Environment Variables (add to `.env.example`):**
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

**Running the Service:**
```bash
# Development
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Production
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
```

**Production Deployment Notes:**
- Set `CORS_ORIGINS` to specific allowed origins (not `*`)
- Set `ENVIRONMENT=production`
- Use single worker for Phase 3 (in-memory rate limiting)
- Monitor `/v1/health` endpoint for service health
- Monitor `/v1/metrics` endpoint for operational metrics

## Sources & References

- **Origin document:** [docs/brainstorms/admin-chatbot-phase3-requirements.md](../brainstorms/admin-chatbot-phase3-requirements.md)
- **Phase 1 Plan:** [docs/plans/2026-04-20-001-feat-admin-chatbot-phase1-setup-plan.md](2026-04-20-001-feat-admin-chatbot-phase1-setup-plan.md)
- **Phase 2 Plan:** [docs/plans/2026-04-20-002-feat-admin-chatbot-phase2-sql-pipeline-plan.md](2026-04-20-002-feat-admin-chatbot-phase2-sql-pipeline-plan.md)
- Related code: `middleware/auth.py`, `services/chatbot_pipeline.py`
- FastAPI documentation: https://fastapi.tiangolo.com/
