"""
Tests for logging configuration.
"""

import os
import logging
from pathlib import Path
import pytest
from config.logging_config import get_logger, LOG_DIR, LOG_FILE


def test_get_logger_creates_logger():
    """Test that get_logger returns a valid logger instance."""
    logger = get_logger("test_module")
    
    assert logger is not None
    assert isinstance(logger, logging.Logger)
    assert logger.name == "test_module"


def test_logs_directory_exists():
    """Test that logs directory is created automatically."""
    assert LOG_DIR.exists()
    assert LOG_DIR.is_dir()


def test_logger_writes_to_file():
    """Test that logger successfully writes to log file."""
    logger = get_logger("test_write")
    
    # Write a test message
    test_message = "Test log entry for verification"
    logger.info(test_message)
    
    # Verify log file exists
    assert LOG_FILE.exists()
    
    # Verify message was written
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        log_content = f.read()
        assert test_message in log_content
        assert "test_write" in log_content
        assert "INFO" in log_content


def test_log_format():
    """Test that log entries have the correct format."""
    logger = get_logger("test_format")
    logger.info("Format test message")
    
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
        # Get the last line (most recent log entry)
        last_line = lines[-1]
        
        # Check format: timestamp - name - level - message
        assert " - " in last_line
        assert "test_format" in last_line
        assert "INFO" in last_line
        assert "Format test message" in last_line


def test_multiple_loggers_use_same_file():
    """Test that multiple loggers write to the same log file."""
    logger1 = get_logger("module1")
    logger2 = get_logger("module2")
    
    logger1.info("Message from module1")
    logger2.info("Message from module2")
    
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        log_content = f.read()
        assert "module1" in log_content
        assert "module2" in log_content
        assert "Message from module1" in log_content
        assert "Message from module2" in log_content


def test_log_levels():
    """Test that different log levels are recorded correctly."""
    logger = get_logger("test_levels")
    
    logger.debug("Debug message")  # Should not appear (level is INFO)
    logger.info("Info message")
    logger.warning("Warning message")
    logger.error("Error message")
    
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        log_content = f.read()
        
        # DEBUG should not appear (root level is INFO)
        assert "Debug message" not in log_content
        
        # INFO, WARNING, ERROR should appear
        assert "Info message" in log_content
        assert "Warning message" in log_content
        assert "Error message" in log_content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
