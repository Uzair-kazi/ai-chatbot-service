"""
Pytest configuration for agent tests.

This file ensures that the project root is in the Python path
so that agent modules can be imported correctly.
"""

import sys
from pathlib import Path

# This code runs at import time, before pytest collects tests
project_root = Path(__file__).parent.parent.parent
project_root_str = str(project_root)

# Ensure project root is first in sys.path
if project_root_str in sys.path:
    sys.path.remove(project_root_str)
sys.path.insert(0, project_root_str)


def pytest_configure(config):
    """
    Pytest hook that runs before test collection.
    Ensures project root is in sys.path.
    """
    project_root = Path(__file__).parent.parent.parent
    project_root_str = str(project_root)
    
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)
