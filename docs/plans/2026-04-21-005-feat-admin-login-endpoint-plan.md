---
title: Add Admin Login API Endpoint
type: feat
status: active
date: 2026-04-21
---

# Add Admin Login API Endpoint

## Overview

Add a `/v1/login` endpoint to enable admin users to authenticate directly through the AI service and receive JWT tokens, eliminating the dependency on the Node.js backend for token generation during development and testing.

## Problem Frame

Currently, the AI service validates JWT tokens but cannot issue them. Admins must obtain tokens from the Node.js backend (`tank-depot/server`), which creates friction during:
- Local development and testing
- Standalone deployment scenarios
- API testing and debugging

This plan adds a self-contained login endpoint that authenticates admin credentials against the PostgreSQL database and issues JWT tokens compatible with the existing authentication middleware.

## Requirements Trace

- R1. Admin users must be able to authenticate with email and password
- R2. Login endpoint must validate credentials against the PostgreSQL database
- R3. Issued JWT tokens must be compatible with existing `middleware/auth.py` validation
- R4. Login endpoint must enforce rate limiting to prevent brute force attacks
- R5. Failed login attempts must be logged for security auditing
- R6. Passwords must be validated using bcrypt hashing (matching Node.js backend)
- R7. Only users with admin role can successfully authenticate
- R8. Login endpoint must return clear error messages without leaking security information

## Scope Boundaries

**In scope:**
- POST `/v1/login` endpoint for email/password authentication
- Database query to fetch user credentials and role
- Password verification using bcrypt
- JWT token generation with user claims
- Rate limiting for login attempts (stricter than general API rate limit)
- Security logging for failed attempts

**Explicit non-goals:**
- User registration or password reset endpoints (admin users are managed in Node.js backend)
- Multi-factor authentication (defer to future phase)
- Session management or refresh tokens (stateless JWT only)
- Password strength validation on login (validation happens at registration in Node.js backend)
- Account lockout after failed attempts (defer to future phase)

## Context & Research

### Relevant Code and Patterns

- `middleware/auth.py` - Existing JWT validation logic, token structure, and admin role checking
- `api/routes.py` - Existing endpoint patterns, error handling, and response models
- `api/models.py` - Pydantic request/response models with validation
- `middleware/rate_limiter.py` - Existing rate limiting implementation
- `services/sql_executor.py` - Database connection and query execution patterns
- `.env` - JWT_SECRET_KEY configuration (must match for token compatibility)

### Database Schema Assumptions

Based on the Node.js backend integration, the database likely contains a `users` table with:
- `id` - User identifier
- `email` - User email (unique)
- `password` - Bcrypt hashed password
- `name` - User display name
- `role_id` - Foreign key to roles table

And a `roles` table with:
- `id` - Role identifier
- `role_name` - Role name (e.g., "admin", "user")

**Implementation note:** Unit 1 will verify the actual schema structure and adjust the query accordingly.

### External References

- **bcrypt**: Industry-standard password hashing (Node.js backend uses bcrypt)
- **JWT RFC 7519**: Token structure and claims
- **OWASP Authentication Cheat Sheet**: Security best practices for login endpoints

## Key Technical Decisions

- **Decision**: Use bcrypt for password verification
  - **Rationale**: Matches Node.js backend's hashing algorithm, ensuring password compatibility

- **Decision**: Issue JWT tokens with same structure as Node.js backend
  - **Rationale**: Ensures tokens work seamlessly with existing `middleware/auth.py` validation

- **Decision**: Stricter rate limiting for login endpoint (5 attempts per minute vs 20 for general API)
  - **Rationale**: Login endpoints are common brute force targets; stricter limits reduce attack surface

- **Decision**: Return generic "Invalid credentials" message for both wrong email and wrong password
  - **Rationale**: Prevents user enumeration attacks (attacker can't determine if email exists)

- **Decision**: Query database directly rather than creating a separate user service
  - **Rationale**: Lightweight approach appropriate for Phase 3; can refactor to service layer if complexity grows

## Open Questions

### Resolved During Planning

- **Q**: Should we support refresh tokens?
  - **A**: No, defer to future phase. Current JWT tokens have expiration; users re-login when expired.

- **Q**: Should we lock accounts after N failed attempts?
  - **A**: No, defer to future phase. Current rate limiting provides basic protection.

- **Q**: What token expiration time should we use?
  - **A**: Match Node.js backend convention (typically 24 hours). Make configurable via environment variable.

### Deferred to Implementation

- **Exact database schema**: Unit 1 will inspect actual table structure and column names
- **Token expiration duration**: Will check Node.js backend configuration or use sensible default (24h)

## Implementation Units

- [ ] **Unit 1: Database Schema Verification and User Query**

**Goal:** Verify database schema and implement user credential lookup query

**Requirements:** R2, R6

**Dependencies:** None

**Files:**
- Create: `services/user_service.py`
- Test: `tests/test_user_service.py`

**Approach:**
- Inspect PostgreSQL database to identify users and roles table structure
- Create `get_user_by_email(email: str)` function that returns user record with role information
- Use JOIN to fetch role_name in single query
- Handle case where user doesn't exist (return None)
- Use existing `sql_executor.py` connection pattern for consistency

**Patterns to follow:**
- `services/sql_executor.py` - Database connection and query execution
- `services/schema.py` - Database introspection patterns

**Test scenarios:**
- Happy path: Fetch existing admin user by email returns complete user record with role
- Happy path: Fetch existing non-admin user by email returns user record with non-admin role
- Edge case: Query with non-existent email returns None
- Edge case: Query with empty string email returns None
- Edge case: Query with malformed email returns None
- Error path: Database connection failure raises appropriate exception

**Verification:**
- Query successfully retrieves user records with role information
- Non-existent users return None without raising exceptions
- All test scenarios pass

---

- [ ] **Unit 2: Password Verification Service**

**Goal:** Implement bcrypt password verification

**Requirements:** R6

**Dependencies:** Unit 1

**Files:**
- Modify: `services/user_service.py`
- Modify: `tests/test_user_service.py`
- Modify: `requirements.txt` (add bcrypt dependency)

**Approach:**
- Add `bcrypt` to requirements.txt
- Create `verify_password(plain_password: str, hashed_password: str) -> bool` function
- Use bcrypt.checkpw() for verification
- Handle bcrypt exceptions gracefully (invalid hash format, etc.)
- Add timing-safe comparison to prevent timing attacks (bcrypt.checkpw already does this)

**Patterns to follow:**
- Standard bcrypt usage patterns from Python bcrypt library documentation

**Test scenarios:**
- Happy path: Correct password against valid bcrypt hash returns True
- Happy path: Incorrect password against valid bcrypt hash returns False
- Edge case: Empty password against hash returns False
- Edge case: Empty hash string raises ValueError
- Edge case: Malformed hash string raises ValueError
- Error path: None values for either parameter raise TypeError

**Verification:**
- Password verification correctly identifies matching and non-matching passwords
- Invalid inputs are handled gracefully with clear error messages
- All test scenarios pass

---

- [ ] **Unit 3: JWT Token Generation Service**

**Goal:** Implement JWT token generation compatible with existing auth middleware

**Requirements:** R3

**Dependencies:** Unit 1

**Files:**
- Create: `services/token_service.py`
- Test: `tests/test_token_service.py`

**Approach:**
- Create `generate_token(user: Dict) -> str` function
- Use PyJWT library (already in requirements.txt)
- Include claims: id, email, name, role_name
- Set expiration time from environment variable (default 24 hours)
- Use JWT_SECRET_KEY from environment (same as auth middleware)
- Use HS256 algorithm (matches auth middleware)

**Patterns to follow:**
- `middleware/auth.py` - JWT token structure and validation (reverse engineer the expected format)
- Existing JWT_SECRET_KEY usage pattern

**Test scenarios:**
- Happy path: Generate token for admin user, decode it, verify all claims present
- Happy path: Generate token for non-admin user, decode it, verify all claims present
- Integration: Generated token passes `middleware/auth.py` validation
- Integration: Generated admin token passes `is_admin_user()` check
- Integration: Generated non-admin token fails `is_admin_user()` check
- Edge case: Token expiration time is correctly set based on environment variable
- Edge case: Missing JWT_SECRET_KEY raises ValueError with clear message

**Verification:**
- Generated tokens contain all required claims
- Tokens are accepted by existing authentication middleware
- Token expiration is correctly configured
- All test scenarios pass

---

- [ ] **Unit 4: Login Request/Response Models**

**Goal:** Define Pydantic models for login endpoint

**Requirements:** R1, R8

**Dependencies:** None

**Files:**
- Modify: `api/models.py`
- Test: `tests/test_api_models.py` (if exists, otherwise create)

**Approach:**
- Create `LoginRequest` model with email and password fields
- Add validation: email format, password min length (1 char - actual validation happened at registration)
- Create `LoginResponse` model with token, user info (id, email, name, role)
- Add OpenAPI examples for documentation
- Follow existing model patterns in `api/models.py`

**Patterns to follow:**
- `api/models.py` - Existing Pydantic model patterns, validation, and examples

**Test scenarios:**
- Happy path: Valid email and password pass validation
- Edge case: Email field validates email format (reject invalid formats)
- Edge case: Password field rejects empty string
- Edge case: Password field accepts any non-empty string (no max length)
- Error path: Missing email field raises validation error
- Error path: Missing password field raises validation error

**Verification:**
- Models validate input correctly
- OpenAPI documentation shows clear examples
- All test scenarios pass

---

- [ ] **Unit 5: Login Endpoint Implementation**

**Goal:** Implement POST `/v1/login` endpoint with authentication logic

**Requirements:** R1, R2, R3, R7, R8

**Dependencies:** Units 1, 2, 3, 4

**Files:**
- Modify: `api/routes.py`
- Modify: `tests/test_api_endpoints.py` (if exists, otherwise create)

**Approach:**
- Add POST `/v1/login` route to router
- Accept `LoginRequest` body
- Call `get_user_by_email()` to fetch user
- If user not found, return 401 with generic "Invalid credentials" message
- Call `verify_password()` to check password
- If password wrong, return 401 with generic "Invalid credentials" message
- Check if user has admin role using role_name field
- If not admin, return 403 with "Admin access required" message
- Call `generate_token()` to create JWT
- Return `LoginResponse` with token and user info
- Add comprehensive OpenAPI documentation
- Log failed attempts with email (but not password) for security auditing

**Patterns to follow:**
- `api/routes.py` - Existing endpoint patterns, error handling, and documentation
- Existing error response format from `api/models.py`

**Test scenarios:**
- Happy path: Valid admin credentials return 200 with token and user info
- Happy path: Returned token can be used to call `/v1/ask` endpoint successfully
- Error path: Non-existent email returns 401 "Invalid credentials"
- Error path: Wrong password returns 401 "Invalid credentials"
- Error path: Valid credentials but non-admin role returns 403 "Admin access required"
- Error path: Missing email field returns 422 validation error
- Error path: Missing password field returns 422 validation error
- Error path: Malformed email format returns 422 validation error
- Integration: Failed login attempts are logged to audit log
- Integration: Successful login is logged to audit log

**Verification:**
- Endpoint authenticates admin users correctly
- Generic error messages prevent user enumeration
- Non-admin users are rejected
- Generated tokens work with existing protected endpoints
- Security events are logged
- All test scenarios pass

---

- [ ] **Unit 6: Login Rate Limiting**

**Goal:** Add stricter rate limiting for login endpoint

**Requirements:** R4

**Dependencies:** Unit 5

**Files:**
- Modify: `middleware/rate_limiter.py`
- Modify: `main.py` (apply rate limiter to login endpoint)
- Modify: `tests/test_rate_limiter.py`

**Approach:**
- Create separate rate limiter instance for login endpoint: 5 requests per minute (vs 20 for general API)
- Apply to `/v1/login` endpoint specifically
- Use IP address as rate limit key (not user ID, since user isn't authenticated yet)
- Return 429 with "Too many login attempts" message when limit exceeded
- Include Retry-After header

**Patterns to follow:**
- `middleware/rate_limiter.py` - Existing rate limiter implementation
- `main.py` - Existing rate limiter middleware application

**Test scenarios:**
- Happy path: 5 login requests within 1 minute succeed
- Error path: 6th login request within 1 minute returns 429
- Edge case: Rate limit resets after 60 seconds
- Edge case: Different IP addresses have independent rate limits
- Integration: Rate limit headers (X-RateLimit-*) are present in response
- Integration: Retry-After header indicates seconds until reset

**Verification:**
- Login endpoint has stricter rate limiting than general API
- Rate limits are enforced per IP address
- Rate limit headers provide clear feedback
- All test scenarios pass

---

- [ ] **Unit 7: Integration Tests and Documentation**

**Goal:** Add comprehensive integration tests and update API documentation

**Requirements:** All requirements

**Dependencies:** Units 1-6

**Files:**
- Modify: `tests/test_integration.py`
- Modify: `README.md`
- Create: `docs/api/login-endpoint.md` (optional detailed documentation)

**Approach:**
- Add integration test: Full login flow with real database
- Add integration test: Login → use token → call /v1/ask endpoint
- Add integration test: Rate limiting behavior across multiple requests
- Add integration test: Failed login attempts are logged
- Update README.md with login endpoint usage examples
- Update test_api.py script to optionally use login endpoint instead of hardcoded token
- Verify OpenAPI documentation is complete and accurate

**Patterns to follow:**
- `tests/test_integration.py` - Existing integration test patterns
- `README.md` - Existing documentation structure

**Test scenarios:**
- Integration: Admin user can login and use token to ask questions
- Integration: Non-admin user login is rejected
- Integration: Invalid credentials are rejected
- Integration: Rate limiting prevents brute force attempts
- Integration: All security events are logged correctly
- Integration: OpenAPI docs at /docs show login endpoint correctly

**Verification:**
- Complete end-to-end login flow works
- Documentation is clear and accurate
- Test script supports both login and hardcoded token modes
- All test scenarios pass

## System-Wide Impact

- **Interaction graph**: Login endpoint is independent of existing `/v1/ask` flow but generates tokens consumed by `middleware/auth.py`
- **Error propagation**: Database errors during login should return 503 (service unavailable), not expose internal details
- **State lifecycle risks**: None - login is stateless; no session state to manage
- **API surface parity**: Login endpoint follows same error response format as existing endpoints
- **Integration coverage**: Integration tests must verify generated tokens work with existing protected endpoints
- **Unchanged invariants**: Existing `/v1/ask`, `/v1/health`, `/v1/metrics` endpoints remain unchanged; existing JWT validation logic in `middleware/auth.py` remains unchanged

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Database schema differs from assumptions | Unit 1 verifies actual schema before proceeding; plan adjusts if needed |
| Bcrypt hash format incompatibility with Node.js | Use standard bcrypt library; verify against test user from Node.js backend |
| Token format incompatibility with existing auth | Unit 3 includes integration test with existing auth middleware |
| Brute force attacks on login endpoint | Strict rate limiting (5 req/min) and security logging |
| User enumeration via timing attacks | Use constant-time comparison; return generic error messages |
| Password exposure in logs | Never log passwords; log only email and outcome |

## Documentation / Operational Notes

**Environment Variables:**
- `JWT_TOKEN_EXPIRATION_HOURS` (optional, default: 24) - Token expiration time

**Security Considerations:**
- Login endpoint is public (no authentication required to call it)
- Rate limiting is critical - monitor for bypass attempts
- Failed login attempts are logged for security auditing
- Generic error messages prevent user enumeration

**Testing:**
- Integration tests require a test admin user in the database
- Test script (`test_api.py`) should be updated to support login flow

**Monitoring:**
- Track failed login attempt rate
- Alert on unusual patterns (many failures from single IP)
- Monitor rate limit hit rate

## Sources & References

- Related code: `middleware/auth.py`, `api/routes.py`, `api/models.py`
- Related PRs/issues: Phase 3 FastAPI implementation
- External docs: 
  - [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
  - [JWT RFC 7519](https://tools.ietf.org/html/rfc7519)
  - [Python bcrypt documentation](https://github.com/pyca/bcrypt/)
