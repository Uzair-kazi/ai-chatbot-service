"""
API Routes

This module defines all API endpoints for the Admin AI Chatbot.
Routes are organized under the /v1 prefix for versioning.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict

from api.models import QuestionRequest, AnswerResponse, ErrorResponse, ErrorDetail
from middleware.auth import get_current_admin_user
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
    """
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
    user_id = current_user.get("id") or current_user.get("user_id") or "unknown"
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

