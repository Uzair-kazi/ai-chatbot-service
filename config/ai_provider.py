"""
AI Provider Configuration

This module provides a swappable AI provider abstraction that allows switching
between different AI providers (DeepSeek, OpenAI, Anthropic, Groq, Ollama) by
changing environment variables only, without any code changes.

Supported Providers:
- DeepSeek (OpenAI-compatible API)
- OpenAI (GPT-4o, GPT-4o-mini)
- Anthropic (Claude Sonnet)
- Groq (Llama models)
- Ollama (local self-hosted models)

Environment Variables Required:
- AI_PROVIDER: Provider name (e.g., "deepseek", "openai", "anthropic")
- AI_API_KEY: API key for the provider
- AI_BASE_URL: API endpoint URL (not used for Anthropic)
- AI_MODEL: Model name to use
- SDK_TYPE: Either "openai_compatible" or "anthropic"

Example .env configurations:

DeepSeek:
    AI_PROVIDER="deepseek"
    AI_API_KEY="your_key"
    AI_BASE_URL="https://api.deepseek.com"
    AI_MODEL="deepseek-chat"
    SDK_TYPE="openai_compatible"

OpenAI:
    AI_PROVIDER="openai"
    AI_API_KEY="sk-..."
    AI_BASE_URL="https://api.openai.com/v1"
    AI_MODEL="gpt-4o"
    SDK_TYPE="openai_compatible"

Anthropic:
    AI_PROVIDER="anthropic"
    AI_API_KEY="sk-ant-..."
    AI_MODEL="claude-sonnet-4-20250514"
    SDK_TYPE="anthropic"
"""

import os
from typing import Union
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Read configuration from environment
AI_PROVIDER = os.getenv("AI_PROVIDER")
AI_API_KEY = os.getenv("AI_API_KEY")
AI_BASE_URL = os.getenv("AI_BASE_URL")
AI_MODEL = os.getenv("AI_MODEL")
SDK_TYPE = os.getenv("SDK_TYPE")

# Validate required environment variables
if not AI_API_KEY:
    raise ValueError(
        "AI_API_KEY environment variable is required. "
        "Please set it in your .env file."
    )

if not AI_MODEL:
    raise ValueError(
        "AI_MODEL environment variable is required. "
        "Please set it in your .env file."
    )

if not SDK_TYPE:
    raise ValueError(
        "SDK_TYPE environment variable is required. "
        "Must be either 'openai_compatible' or 'anthropic'."
    )

if SDK_TYPE not in ["openai_compatible", "anthropic"]:
    raise ValueError(
        f"Invalid SDK_TYPE: {SDK_TYPE}. "
        "Must be either 'openai_compatible' or 'anthropic'."
    )

# Initialize the appropriate AI client based on SDK_TYPE
if SDK_TYPE == "openai_compatible":
    # OpenAI-compatible providers: DeepSeek, OpenAI, Groq, Ollama
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError(
            "openai package is required for OpenAI-compatible providers. "
            "Install it with: pip install openai"
        )
    
    if not AI_BASE_URL:
        raise ValueError(
            "AI_BASE_URL environment variable is required for OpenAI-compatible providers. "
            "Please set it in your .env file."
        )
    
    ai_client = OpenAI(
        api_key=AI_API_KEY,
        base_url=AI_BASE_URL
    )
    
elif SDK_TYPE == "anthropic":
    # Anthropic Claude
    try:
        from anthropic import Anthropic
    except ImportError:
        raise ImportError(
            "anthropic package is required for Anthropic provider. "
            "Install it with: pip install anthropic"
        )
    
    ai_client = Anthropic(
        api_key=AI_API_KEY
    )

else:
    # This should never happen due to validation above, but just in case
    raise ValueError(f"Unsupported SDK_TYPE: {SDK_TYPE}")

# Export the configured client and model name
model_name = AI_MODEL
provider_name = AI_PROVIDER or "unknown"

# Type hint for the client (Union of possible types)
AIClient = Union[type(ai_client)]

__all__ = ["ai_client", "model_name", "provider_name", "SDK_TYPE"]
