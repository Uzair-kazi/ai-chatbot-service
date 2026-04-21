"""
User Service

This module provides user authentication and credential management functions.
It handles database queries for user lookup and password verification.
"""

import os
from typing import Dict, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

from config.logging_config import get_logger

# Load environment variables
load_dotenv()

# Get logger
logger = get_logger(__name__)


def get_user_by_email(email: str) -> Optional[Dict]:
    """
    Fetch user record with role information by email.
    
    Args:
        email: User email address
        
    Returns:
        Dictionary containing user information and role, or None if user not found
        
    Raises:
        psycopg2.Error: If database connection or query fails
    """
    # Validate input
    if not email or not isinstance(email, str) or not email.strip():
        logger.debug(f"Invalid email provided: {repr(email)}")
        return None
    
    email = email.strip()
    
    # Get database URL
    db_url = os.getenv("DB_URL")
    if not db_url:
        raise ValueError("DB_URL environment variable is not configured")
    
    try:
        # Connect to database
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Query user with role information using JOIN
        query = """
            SELECT 
                u.id,
                u.email,
                u.name,
                u.password,
                u.role_id,
                r.role_name
            FROM "user" u
            JOIN roles r ON u.role_id = r.id
            WHERE u.email = %s
        """
        
        cursor.execute(query, (email,))
        user = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if user:
            # Convert RealDictRow to regular dict
            return dict(user)
        else:
            logger.debug(f"User not found for email: {email}")
            return None
            
    except psycopg2.Error as e:
        logger.error(f"Database error while fetching user: {e}")
        raise


__all__ = ["get_user_by_email"]
