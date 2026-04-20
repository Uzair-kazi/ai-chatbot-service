"""
Tests for AI provider configuration.

Note: These tests validate the configuration loading logic.
They do not make actual API calls to AI providers.
"""

import os
import pytest
from unittest.mock import patch


def test_ai_provider_requires_api_key():
    """Test that AI provider raises error if AI_API_KEY is not set."""
    with patch.dict(os.environ, {}, clear=True):
        # Remove the module from cache if it was already imported
        import sys
        if 'config.ai_provider' in sys.modules:
            del sys.modules['config.ai_provider']
        
        with pytest.raises(ValueError, match="AI_API_KEY environment variable is required"):
            import config.ai_provider


def test_ai_provider_requires_model():
    """Test that AI provider raises error if AI_MODEL is not set."""
    with patch.dict(os.environ, {"AI_API_KEY": "test_key"}, clear=True):
        import sys
        if 'config.ai_provider' in sys.modules:
            del sys.modules['config.ai_provider']
        
        with pytest.raises(ValueError, match="AI_MODEL environment variable is required"):
            import config.ai_provider


def test_ai_provider_requires_sdk_type():
    """Test that AI provider raises error if SDK_TYPE is not set."""
    with patch.dict(os.environ, {
        "AI_API_KEY": "test_key",
        "AI_MODEL": "test_model"
    }, clear=True):
        import sys
        if 'config.ai_provider' in sys.modules:
            del sys.modules['config.ai_provider']
        
        with pytest.raises(ValueError, match="SDK_TYPE environment variable is required"):
            import config.ai_provider


def test_ai_provider_validates_sdk_type():
    """Test that AI provider raises error for invalid SDK_TYPE."""
    with patch.dict(os.environ, {
        "AI_API_KEY": "test_key",
        "AI_MODEL": "test_model",
        "SDK_TYPE": "invalid_type"
    }, clear=True):
        import sys
        if 'config.ai_provider' in sys.modules:
            del sys.modules['config.ai_provider']
        
        with pytest.raises(ValueError, match="Invalid SDK_TYPE"):
            import config.ai_provider


def test_openai_compatible_requires_base_url():
    """Test that OpenAI-compatible providers require AI_BASE_URL."""
    with patch.dict(os.environ, {
        "AI_API_KEY": "test_key",
        "AI_MODEL": "test_model",
        "SDK_TYPE": "openai_compatible"
    }, clear=True):
        import sys
        if 'config.ai_provider' in sys.modules:
            del sys.modules['config.ai_provider']
        
        with pytest.raises(ValueError, match="AI_BASE_URL environment variable is required"):
            import config.ai_provider


@pytest.mark.skipif(
    not all([
        os.getenv("AI_API_KEY"),
        os.getenv("AI_MODEL"),
        os.getenv("SDK_TYPE")
    ]),
    reason="AI provider environment variables not set - skipping integration tests"
)
def test_ai_provider_loads_successfully():
    """Test that AI provider loads successfully with valid configuration."""
    from config.ai_provider import ai_client, model_name, provider_name, SDK_TYPE
    
    # Check that client was initialized
    assert ai_client is not None
    
    # Check that model_name matches environment variable
    assert model_name == os.getenv("AI_MODEL")
    
    # Check that SDK_TYPE is valid
    assert SDK_TYPE in ["openai_compatible", "anthropic"]


@pytest.mark.skipif(
    not all([
        os.getenv("AI_API_KEY"),
        os.getenv("AI_MODEL"),
        os.getenv("SDK_TYPE") == "openai_compatible"
    ]),
    reason="OpenAI-compatible provider not configured - skipping test"
)
def test_openai_compatible_client_type():
    """Test that OpenAI-compatible client is correct type."""
    from config.ai_provider import ai_client
    from openai import OpenAI
    
    assert isinstance(ai_client, OpenAI)


@pytest.mark.skipif(
    not all([
        os.getenv("AI_API_KEY"),
        os.getenv("AI_MODEL"),
        os.getenv("SDK_TYPE") == "anthropic"
    ]),
    reason="Anthropic provider not configured - skipping test"
)
def test_anthropic_client_type():
    """Test that Anthropic client is correct type."""
    from config.ai_provider import ai_client
    from anthropic import Anthropic
    
    assert isinstance(ai_client, Anthropic)


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
