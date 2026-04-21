"""
FastAPI Application Entry Point

This module creates and configures the FastAPI application for the Admin AI Chatbot.
It sets up middleware, routers, and lifespan handlers for the production REST API.

Environment Variables:
- PORT: Server port (default: 8000)
- HOST: Server host (default: 0.0.0.0)
- ENVIRONMENT: Environment name (default: development)
- CORS_ORIGINS: Comma-separated list of allowed origins (default: *)
- SERVICE_VERSION: Service version for health checks (default: 1.0.0)
"""

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from dotenv import load_dotenv

from api.routes import router as api_router
from api.errors import validation_exception_handler, generic_exception_handler
from middleware.rate_limiter import RateLimitMiddleware, LoginRateLimitMiddleware, rate_limiter, login_rate_limiter
from middleware.request_logger import RequestLoggingMiddleware
from config.logging_config import get_logger

# Load environment variables
load_dotenv()

# Get configuration from environment
PORT = int(os.getenv("PORT", "8000"))
HOST = os.getenv("HOST", "0.0.0.0")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "1.0.0")

# Parse CORS origins
if CORS_ORIGINS == "*":
    cors_origins = ["*"]
else:
    cors_origins = [origin.strip() for origin in CORS_ORIGINS.split(",")]

# Initialize logger
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Lifespan context manager for application startup and shutdown.
    
    Replaces deprecated @app.on_event decorators with modern lifespan pattern.
    """
    # Startup
    logger.info(f"Starting Admin AI Chatbot API v{SERVICE_VERSION}")
    logger.info(f"Environment: {ENVIRONMENT}")
    logger.info(f"CORS Origins: {cors_origins}")
    logger.info(f"Server: {HOST}:{PORT}")
    
    # Warn about CORS wildcard in production
    if ENVIRONMENT == "production" and CORS_ORIGINS == "*":
        logger.warning(
            "CORS_ORIGINS is set to '*' (wildcard) in production environment. "
            "This allows requests from any origin and may pose a security risk. "
            "Consider setting specific allowed origins in the CORS_ORIGINS environment variable."
        )
    
    yield
    
    # Shutdown
    logger.info("Shutting down Admin AI Chatbot API")
    rate_limiter.shutdown()  # Gracefully shutdown rate limiter
    login_rate_limiter.shutdown()  # Gracefully shutdown login rate limiter

# Create FastAPI application with lifespan
app = FastAPI(
    title="Admin AI Chatbot API",
    description="""
    Production-ready REST API for natural language database queries.
    
    ## Features
    
    * **Natural Language Queries**: Ask questions in plain English, get formatted answers
    * **SQL Generation**: AI-powered SQL query generation from natural language
    * **Safety Validation**: Automatic SQL safety checks to prevent destructive operations
    * **JWT Authentication**: Secure admin-only access with JWT tokens
    * **Rate Limiting**: 20 requests per minute per user
    * **Request Logging**: Comprehensive audit logging with request IDs
    * **Health Monitoring**: Health check and metrics endpoints for operational visibility
    
    ## Authentication
    
    All `/v1/ask` endpoints require a valid JWT token with admin role.
    
    Include the token in the Authorization header:
    ```
    Authorization: Bearer <your-jwt-token>
    ```
    
    ## Rate Limiting
    
    The API enforces rate limiting of 20 requests per minute per user.
    Rate limit headers are included in responses:
    - `X-RateLimit-Limit`: Maximum requests per window
    - `X-RateLimit-Remaining`: Remaining requests in current window
    - `X-RateLimit-Reset`: Unix timestamp when the window resets
    
    ## Error Handling
    
    All errors return a consistent JSON structure:
    ```json
    {
        "error": {
            "code": "ERROR_CODE",
            "message": "Human-readable error message",
            "status": 400,
            "timestamp": "2026-04-20T10:30:00Z"
        }
    }
    ```
    
    ## Request Tracing
    
    All responses include an `X-Request-ID` header for request tracing and debugging.
    """,
    version=SERVICE_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
    openapi_tags=[
        {
            "name": "Questions",
            "description": "Natural language question endpoints (requires authentication)"
        },
        {
            "name": "Monitoring",
            "description": "Health check and metrics endpoints (public)"
        }
    ]
)

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add rate limiting middleware (login-specific must come before general)
app.add_middleware(LoginRateLimitMiddleware)
app.add_middleware(RateLimitMiddleware)

# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware)

# Register exception handlers
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# Include API router with /v1 prefix
app.include_router(api_router, prefix="/v1")


# Root endpoint for basic connectivity check
@app.get("/")
async def root():
    """Root endpoint - redirects to API documentation."""
    return {
        "message": "Admin AI Chatbot API",
        "version": SERVICE_VERSION,
        "docs": "/docs",
        "health": "/v1/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        reload=(ENVIRONMENT == "development")
    )
