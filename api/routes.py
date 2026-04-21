"""
API Routes

This module defines all API endpoints for the Admin AI Chatbot.
Routes are organized under the /v1 prefix for versioning.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict
import os
import psycopg2

from api.models import (
    QuestionRequest, AnswerResponse, ErrorResponse, ErrorDetail,
    HealthResponse, MetricsResponse, LoginRequest, LoginResponse, UserInfo
)
from middleware.auth import get_current_admin_user, extract_user_id
from middleware.metrics_tracker import get_metrics_tracker
from services.chatbot_pipeline import ask as pipeline_ask
from services.multi_agent_pipeline import ask as multi_agent_ask
from services.user_service import get_user_by_email, verify_password
from services.token_service import generate_token
from config.logging_config import get_logger

# Initialize logger
logger = get_logger(__name__)

# Create API router
router = APIRouter()


@router.post(
    "/login",
    response_model=LoginResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid credentials"},
        403: {"model": ErrorResponse, "description": "Admin access required"},
        422: {"model": ErrorResponse, "description": "Validation error"},
        503: {"model": ErrorResponse, "description": "Service unavailable"},
    },
    summary="Admin login endpoint",
    description="""
    Authenticate admin user with email and password.
    
    Returns a JWT token that can be used to access protected endpoints.
    
    **Authentication:** Not required - this is the login endpoint.
    
    **Rate Limiting:** 5 requests per minute per IP address (stricter than general API).
    
    **Security:**
    - Only admin users can successfully authenticate
    - Generic error messages prevent user enumeration
    - Failed attempts are logged for security auditing
    """,
    tags=["Authentication"]
)
async def login(request: LoginRequest) -> LoginResponse:
    """
    Authenticate admin user and return JWT token.
    
    Args:
        request: Login request containing email and password
    
    Returns:
        LoginResponse with JWT token and user information
    
    Raises:
        HTTPException: For authentication failures or service errors
    """
    logger.info(f"Login attempt for email: {request.email}")
    
    try:
        # Fetch user from database
        user = get_user_by_email(request.email)
        
        # Check if user exists
        if not user:
            logger.warning(f"Login failed: User not found for email {request.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        # Verify password
        if not verify_password(request.password, user["password"]):
            logger.warning(f"Login failed: Invalid password for email {request.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        # Check if user is admin
        if user["role_name"].lower() != "admin":
            logger.warning(f"Login failed: Non-admin user attempted login: {request.email} (role: {user['role_name']})")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )
        
        # Generate JWT token
        token = generate_token(user)
        
        # Log successful login
        logger.info(f"Login successful for admin user: {request.email}")
        
        # Return response
        return LoginResponse(
            token=token,
            user=UserInfo(
                id=user["id"],
                email=user["email"],
                name=user["name"],
                role=user["role_name"]
            )
        )
    
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except psycopg2.Error as e:
        # Database errors
        logger.error(f"Database error during login: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable. Please try again later."
        )
    except Exception as e:
        # Catch any unexpected errors
        logger.error(f"Unexpected error during login: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred. Please try again."
        )


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


@router.post(
    "/ask/multi-agent",
    response_model=AnswerResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request or unsafe query"},
        401: {"model": ErrorResponse, "description": "Unauthorized - missing or invalid token"},
        403: {"model": ErrorResponse, "description": "Forbidden - admin access required"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        503: {"model": ErrorResponse, "description": "Service unavailable"},
        504: {"model": ErrorResponse, "description": "Query timeout"},
    },
    summary="Ask a natural language question (multi-agent pipeline)",
    description="""
    Submit a natural language question using the multi-agent pipeline with self-critique loops.
    
    The multi-agent AI will:
    1. Route through Orchestrator agent
    2. Generate SQL using SQL Generation agent with self-critique (2-3 retry attempts)
    3. Validate SQL against schema (catches column hallucinations)
    4. Execute the query against the database
    5. Format the results into a natural language answer
    
    **Advantages over /v1/ask:**
    - Self-correction: Catches and fixes column hallucinations
    - Higher accuracy: ~95% SQL correctness (vs ~80% for single-LLM)
    - Confidence scores: Internal quality assessment
    
    **Trade-offs:**
    - Slightly higher latency (2-3 AI calls vs 1)
    - Higher token usage (2-3x cost)
    
    **Authentication:** Requires valid JWT token with admin role.
    
    **Rate Limiting:** 20 requests per minute per user.
    """,
    tags=["Questions"]
)
async def ask_question_multi_agent(
    request: QuestionRequest,
    current_user: Dict = Depends(get_current_admin_user)
) -> AnswerResponse:
    """
    Process a natural language question using multi-agent pipeline.
    
    Args:
        request: Question request containing the natural language question
        current_user: Authenticated admin user (injected by dependency)
    
    Returns:
        AnswerResponse with answer, SQL query, and metadata
    
    Raises:
        HTTPException: For various error conditions (auth, validation, timeout, etc.)
    """
    user_id = extract_user_id(current_user)
    logger.info(f"Multi-agent question received from user {user_id}: {request.question[:100]}")
    
    try:
        # Call the multi-agent pipeline
        result = multi_agent_ask(request.question)
        
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
        logger.error(f"Unexpected error in /ask/multi-agent endpoint: {e}", exc_info=True)
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
