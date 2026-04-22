"""
Agent Configuration Module

This module provides configuration loading utilities for agents.
Configuration files are stored in YAML format for human readability.
"""

import os
import yaml
from typing import Dict, Any
from pathlib import Path


def load_config(config_name: str) -> Dict[str, Any]:
    """
    Load configuration from YAML file.
    
    Args:
        config_name: Name of config file (without .yaml extension)
        
    Returns:
        Dictionary containing configuration data
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If config file has invalid YAML syntax
    """
    config_dir = Path(__file__).parent
    config_path = config_dir / f"{config_name}.yaml"
    
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    return config or {}


def load_business_glossary() -> Dict[str, Dict[str, str]]:
    """
    Load business glossary configuration.
    
    Returns:
        Dictionary containing temporal terms and entity mappings
    """
    return load_config("business_glossary")


def load_security_policies() -> Dict[str, Any]:
    """
    Load security policies configuration.
    
    Returns:
        Dictionary containing PII columns, blocked operations, and role permissions
    """
    return load_config("security_policies")


__all__ = ["load_config", "load_business_glossary", "load_security_policies"]
