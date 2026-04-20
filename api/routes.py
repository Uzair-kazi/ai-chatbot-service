"""
API Routes

This module defines all API endpoints for the Admin AI Chatbot.
Routes are organized under the /v1 prefix for versioning.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict
import os
import psycopg2

from api.models import QuestionRequest, AnswerResponse, ErrorResponse, ErrorDetail, HealthResponse, MetricsResponse
from middleware.auth import get_current_admin_user, extract_user_id
from middleware.metrics_tracker import get_metrics_tracker
from services.chatbot_pipeline import ask as pipeline_ask
from config.logging_config import get_logger

# Initialize logger
logger = get_logger(__name__)

# Create API router
router = APIRouter()


@router.post(
    "/ask",
    response_model=AnswerResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request or unsafe query"},
        401: {"model": ErrorResponse, "description": "Unauthorized - missing or invalid token"},
        403: {"model": ErrorResponse, "description": "Forbidden - admin access required"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        503: {"model": ErrorResponse, "description": "Service unavailable"},
        504: {"model": ErrorResponse, "description": "Query timeout"},
    },
    summary="Ask a natural language question",
    description="""
    Submit a natural language question about the database and receive a formatted answer.
    
    The AI will:
    1. Generate a SQL query from your question
    2. Validate the query for safety
    3. Execute the query against the database
    4. Format the results into a natural language answer
    
    **Authentication:** Requires valid JWT token with admin role.
    
    **Rate Limiting:** 20 requests per minute per user.
    """,
    tags=["Questions"]
)
async def ask_question(
    request: QuestionRequest,
    current_user: Dict = Depends(get_current_admin_user)
) -> AnswerResponse:
    """
    Process a natural language question and return a formatted answer.
    
    Args:
        request: Question request containing the natural language question
        current_user: Authenticated admin user (injected by dependency)
    
    Returns:
        AnswerResponse with answer, SQL query, and metadata
    
    Raises:
        HTTPException: For various error conditions (auth, validation, timeout, etc.)
    """
    user_id = extract_user_id(current_user)
    logger.info(f"Question received from user {user_id}: {request.question[:100]}")
    
    try:
        # Call the pipeline
        result = pipeline_ask(request.question)
        
        # Map pipeline status code to HTTP response
        pipeline_status = result.get("status_code", 500)
        
        if pipeline_status == 200:
            # Success - return answer
            return AnswerResponse(
                answer=result["answer"],
                sql=result["sql"],
                rows_count=result["rows_count"],
                execution_time_ms=result.get("execution_time_ms")
            )
        else:
            # Pipeline returned an error - map to appropriate HTTP status
            error_message = result.get("error", result.get("answer", "An error occurred"))
            
            # Map pipeline status codes to HTTP status codes
            if pipeline_status == 400:
                # Validation or safety check failed
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error_message
                )
            elif pipeline_status == 403:
                # Permission denied
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=error_message
                )
            elif pipeline_status == 503:
                # Database unavailable
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=error_message
                )
            elif pipeline_status == 504:
                # Query timeout
                raise HTTPException(
                    status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                    detail=error_message
                )
            else:
                # Generic error
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=error_message
                )
    
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Catch any unexpected errors
        logger.error(f"Unexpected error in /ask endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred. Please try again."
        )


# Health check and metrics endpoints will be added in subsequent units



@router.get(
    "/health",
    response_model=HealthResponse,
    responses={
        503: {"model": ErrorResponse, "description": "Service unhealthy"},
    },
    summary="Health check endpoint",
    description="""
    Check the health status of the service and its dependencies.
    
    This endpoint verifies:
    - Database connectivity (simple SELECT 1 query)
    - AI provider configuration (environment variables present)
    
    **Authentication:** Not required - public endpoint for monitoring.
    
    Returns 200 if all checks pass, 503 if any check fails.
    """,
    tags=["Monitoring"]
)
async def health_check() -> HealthResponse:
    """
    Perform health checks on service dependencies.
    
    Returns:
        HealthResponse with overall status and individual check results
    
    Raises:
        HTTPException: 503 if any health check fails
    """
    checks = {}
    overall_healthy = True
    
    # Check 1: Database connectivity
    try:
        db_url = os.getenv("DB_URL")
        if not db_url:
            checks["database"] = {"status": "unhealthy", "message": "DB_URL not configured"}
            overall_healthy = False
        else:
            # Simple connection test
            conn = psycopg2.connect(db_url)
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            conn.close()
            checks["database"] = {"status": "healthy", "message": "Connected"}
    except Exception as e:
        checks["database"] = {"status": "unhealthy", "message": f"Connection failed: {str(e)[:100]}"}
        overall_healthy = False
    
    # Check 2: AI provider configuration
    try:
        ai_provider = os.getenv("AI_PROVIDER")
        ai_api_key = os.getenv("AI_API_KEY")
        ai_model = os.getenv("AI_MODEL")
        
        if not ai_provider or not ai_api_key or not ai_model:
            missing = []
            if not ai_provider:
                missing.append("AI_PROVIDER")
            if not ai_api_key:
                missing.append("AI_API_KEY")
            if not ai_model:
                missing.append("AI_MODEL")
            checks["ai_provider"] = {
                "status": "unhealthy",
                "message": f"Missing configuration: {', '.join(missing)}"
            }
            overall_healthy = False
        else:
            checks["ai_provider"] = {
                "status": "healthy",
                "message": f"Configured: {ai_provider}/{ai_model}"
            }
    except Exception as e:
        checks["ai_provider"] = {"status": "unhealthy", "message": f"Configuration error: {str(e)[:100]}"}
        overall_healthy = False
    
    # Get service version
    version = os.getenv("SERVICE_VERSION", "1.0.0")
    
    # Return response
    if overall_healthy:
        return HealthResponse(
            status="healthy",
            version=version,
            checks=checks
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "unhealthy",
                "version": version,
                "checks": checks
            }
        )



@router.get(
    "/metrics",
    response_model=MetricsResponse,
    summary="Metrics endpoint",
    description="""
    Get operational metrics for the service.
    
    This endpoint provides:
    - Request statistics (total, success, errors)
    - Rate limiting statistics (active users, blocked requests)
    - Performance metrics (average, p95, p99 response times)
    - Service uptime
    
    **Authentication:** Not required - public endpoint for monitoring.
    
    **Note:** Metrics are stored in-memory and reset on service restart.
    """,
    tags=["Monitoring"]
)
async def get_metrics() -> MetricsResponse:
    """
    Get current operational metrics.
    
    Returns:
        MetricsResponse with current metrics snapshot
    """
    metrics_tracker = get_metrics_tracker()
    metrics_data = metrics_tracker.get_metrics()
    
    return MetricsResponse(**metrics_data)
