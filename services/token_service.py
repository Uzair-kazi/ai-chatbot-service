"""
Token Service

This module provides JWT token generation for authenticated users.
Tokens are compatible with the existing authentication middleware.
"""

import os
from typing import Dict
from datetime import datetime, timedelta, timezone
import jwt
from dotenv import load_dotenv

from config.logging_config import get_logger

# Load environment variables
load_dotenv()

# Get logger
logger = get_logger(__name__)


def generate_token(user: Dict) -> str:
    """
    Generate a JWT token for an authenticated user.
    
    The token structure matches the format expected by middleware/auth.py:
    - id: User ID
    - email: User email
    - name: User display name
    - role_name: User role (e.g., "Admin")
    - exp: Expiration timestamp
    
    Args:
        user: Dictionary containing user information (id, email, name, role_name)
        
    Returns:
        JWT token string
        
    Raises:
        ValueError: If JWT_SECRET_KEY is not configured or user data is invalid
    """
    # Get JWT secret
    jwt_secret = os.getenv("JWT_SECRET_KEY")
    if not jwt_secret:
        raise ValueError(
            "JWT_SECRET_KEY environment variable is required. "
            "This must match the secret used by the Node.js backend."
        )
    
    # Validate user data
    required_fields = ["id", "email", "name", "role_name"]
    for field in required_fields:
        if field not in user:
            raise ValueError(f"User data missing required field: {field}")
    
    # Get token expiration time from environment (default 24 hours)
    expiration_hours = int(os.getenv("JWT_TOKEN_EXPIRATION_HOURS", "24"))
    
    # Build token payload
    payload = {
        "id": user["id"],
        "email": user["email"],
        "name": user["name"],
        "role_name": user["role_name"],
        "exp": datetime.now(timezone.utc) + timedelta(hours=expiration_hours)
    }
    
    # Generate token using HS256 algorithm (matches middleware/auth.py)
    token = jwt.encode(payload, jwt_secret, algorithm="HS256")
    
    logger.debug(f"Generated token for user {user['email']} with {expiration_hours}h expiration")
    
    return token


__all__ = ["generate_token"]
