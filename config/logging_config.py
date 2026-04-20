"""
Centralized Logging Configuration

This module provides a consistent logging setup for the AI chatbot service.
All logs are written to logs/chat_audit.log with automatic rotation.

Usage:
    from config.logging_config import get_logger
    
    logger = get_logger(__name__)
    logger.info("Processing question")
"""

import os
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


# Log directory and file paths
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_FILE = LOG_DIR / "chat_audit.log"

# Log format
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Rotation settings
MAX_BYTES = 10 * 1024 * 1024  # 10MB
BACKUP_COUNT = 5


def setup_logging():
    """
    Set up the logging configuration.
    
    Creates the logs directory if it doesn't exist and configures
    a rotating file handler for all loggers.
    
    Raises:
        PermissionError: If logs directory cannot be created or is not writable
    """
    # Create logs directory if it doesn't exist
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
    except PermissionError as e:
        raise PermissionError(
            f"Cannot create logs directory at {LOG_DIR}. "
            f"Please check permissions: {e}"
        )
    
    # Test if directory is writable
    if not os.access(LOG_DIR, os.W_OK):
        raise PermissionError(
            f"Logs directory {LOG_DIR} is not writable. "
            "Please check permissions."
        )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()
    
    # Create rotating file handler
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    file_handler.setFormatter(formatter)
    
    # Add handler to root logger
    root_logger.addHandler(file_handler)
    
    # Also add console handler for development
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the specified name.
    
    This function ensures logging is set up before returning the logger.
    
    Args:
        name: Logger name (typically __name__ from the calling module)
        
    Returns:
        Configured logger instance
        
    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Processing started")
    """
    # Ensure logging is set up
    if not logging.getLogger().handlers:
        setup_logging()
    
    return logging.getLogger(name)


# Initialize logging on module import
setup_logging()
