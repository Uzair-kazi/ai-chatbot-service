"""
FastAPI Application Entry Point

This module creates and configures the FastAPI application for the Admin AI Chatbot.
It sets up middleware, routers, and event handlers for the production REST API.

Environment Variables:
- PORT: Server port (default: 8000)
- HOST: Server host (default: 0.0.0.0)
- ENVIRONMENT: Environment name (default: development)
- CORS_ORIGINS: Comma-separated list of allowed origins (default: *)
- SERVICE_VERSION: Service version for health checks (default: 1.0.0)
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from api.routes import router as api_router
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

# Create FastAPI application
app = FastAPI(
    title="Admin AI Chatbot API",
    description="Production-ready REST API for natural language database queries",
    version=SERVICE_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router with /v1 prefix
app.include_router(api_router, prefix="/v1")


@app.on_event("startup")
async def startup_event():
    """Log application startup."""
    logger.info(f"Starting Admin AI Chatbot API v{SERVICE_VERSION}")
    logger.info(f"Environment: {ENVIRONMENT}")
    logger.info(f"CORS Origins: {cors_origins}")
    logger.info(f"Server: {HOST}:{PORT}")


@app.on_event("shutdown")
async def shutdown_event():
    """Log application shutdown."""
    logger.info("Shutting down Admin AI Chatbot API")


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
