"""
User Service

This module provides user authentication and credential management functions.
It handles database queries for user lookup and password verification.
"""

import os
from typing import Dict, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
import bcrypt
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


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain text password against a bcrypt hashed password.
    
    Uses bcrypt.checkpw() which provides constant-time comparison
    to prevent timing attacks.
    
    Args:
        plain_password: Plain text password to verify
        hashed_password: Bcrypt hashed password from database
        
    Returns:
        True if password matches, False otherwise
        
    Raises:
        TypeError: If either parameter is None
        ValueError: If hashed_password is empty or malformed
    """
    # Validate inputs
    if plain_password is None or hashed_password is None:
        raise TypeError("Password and hash cannot be None")
    
    if not isinstance(plain_password, str) or not isinstance(hashed_password, str):
        raise TypeError("Password and hash must be strings")
    
    if not hashed_password or not hashed_password.strip():
        raise ValueError("Hash cannot be empty")
    
    # Handle empty password - always return False
    if not plain_password:
        return False
    
    try:
        # Convert strings to bytes for bcrypt
        password_bytes = plain_password.encode('utf-8')
        hash_bytes = hashed_password.encode('utf-8')
        
        # Use bcrypt's constant-time comparison
        return bcrypt.checkpw(password_bytes, hash_bytes)
        
    except ValueError as e:
        # Malformed hash format
        logger.debug(f"Invalid hash format: {e}")
        raise ValueError(f"Invalid hash format: {e}")
    except Exception as e:
        # Other bcrypt errors
        logger.error(f"Password verification error: {e}")
        raise


__all__ = ["get_user_by_email", "verify_password"]
