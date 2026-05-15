"""
llm.py — OpenRouter API Client
================================
Handles all communication with the OpenRouter API.
Uses Grok (x-ai/grok-4.1-fast) as the default model.

OpenRouter provides a unified API compatible with OpenAI's format,
so we just POST to their /chat/completions endpoint.
"""

import os
import json
import httpx
from dotenv import load_dotenv

# Load environment variables from .env file (local dev)
load_dotenv()

# ============================================
# Token Usage Tracking
# ============================================

_last_usage = None  # Stores usage from most recent call

def get_last_usage() -> dict:
    """Return token usage from the most recent LLM call."""
    return _last_usage or {}

def reset_usage_accumulator() -> dict:
    """Create a fresh usage accumulator for a multi-step agent run."""
    return {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "llm_calls": 0,
    }

def accumulate_usage(accumulator: dict, usage: dict) -> None:
    """Add a single LLM call's usage into the running total."""
    accumulator["prompt_tokens"] += usage.get("prompt_tokens", 0)
    accumulator["completion_tokens"] += usage.get("completion_tokens", 0)
    accumulator["total_tokens"] += usage.get("total_tokens", 0)
    accumulator["llm_calls"] += 1

# ============================================
# Configuration
# ============================================

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"


def _get_secret(key: str, default: str = "") -> str:
    """Get a secret from st.secrets (cloud) or os.environ (local)."""
    # Try Streamlit secrets first (for Streamlit Cloud deployment)
    try:
        import streamlit as st
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    # Fallback to environment variable
    return os.getenv(key, default)


OPENROUTER_API_KEY = _get_secret("OPENROUTER_API_KEY", "")
DEFAULT_MODEL = _get_secret("DEFAULT_MODEL", "deepseek/deepseek-v4-flash:free")


def get_headers() -> dict:
    """Build the request headers for OpenRouter API."""
    return {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/ai-agent",  # For OpenRouter rankings
        "X-Title": "AI Agent",
    }


def chat_completion(
    messages: list[dict],
    model: str = DEFAULT_MODEL,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    stream: bool = False,
) -> str:
    """
    Send a chat completion request to OpenRouter.
    
    Args:
        messages: List of message dicts with 'role' and 'content' keys.
                  Example: [{"role": "user", "content": "Hello!"}]
        model: The model ID to use (default: Grok).
        temperature: Controls randomness (0.0 = deterministic, 1.0 = creative).
        max_tokens: Maximum tokens in the response.
        stream: Whether to stream the response (not used in basic mode).
    
    Returns:
        The assistant's response text.
    
    Raises:
        Exception: If the API call fails after retries.
    """
    # Validate API key
    if not OPENROUTER_API_KEY or OPENROUTER_API_KEY == "your_key_here":
        raise ValueError(
            "🔑 OpenRouter API key not set! "
            "Please add your key to the .env file. "
            "Get a free key at: https://openrouter.ai/keys"
        )

    # Build the request payload
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    # Retry logic — try up to 3 times with increasing delays
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # Make the API call with a generous timeout
            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    OPENROUTER_API_URL,
                    headers=get_headers(),
                    json=payload,
                )

            # Check for HTTP errors
            if response.status_code != 200:
                error_detail = response.text
                raise Exception(
                    f"OpenRouter API error (HTTP {response.status_code}): {error_detail}"
                )

            # Parse the response
            data = response.json()

            # Capture token usage
            global _last_usage
            _last_usage = data.get("usage", {})

            # Extract the assistant's message
            if "choices" in data and len(data["choices"]) > 0:
                return data["choices"][0]["message"]["content"]
            else:
                raise Exception(f"Unexpected API response format: {json.dumps(data)}")

        except httpx.TimeoutException:
            if attempt < max_retries - 1:
                import time
                wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                print(f"⏳ Request timed out. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise Exception(
                    "❌ OpenRouter API timed out after 3 attempts. "
                    "Please check your internet connection."
                )

        except httpx.ConnectError:
            raise Exception(
                "❌ Cannot connect to OpenRouter API. "
                "Please check your internet connection."
            )


def stream_chat_completion(
    messages: list[dict],
    model: str = DEFAULT_MODEL,
    temperature: float = 0.7,
    max_tokens: int = 2048,
):
    """
    Stream a chat completion response from OpenRouter.
    
    Yields chunks of text as they arrive (Server-Sent Events).
    
    Args:
        messages: List of message dicts.
        model: The model ID to use.
        temperature: Controls randomness.
        max_tokens: Maximum tokens in the response.
    
    Yields:
        str: Chunks of the assistant's response.
    """
    if not OPENROUTER_API_KEY or OPENROUTER_API_KEY == "your_key_here":
        raise ValueError(
            "🔑 OpenRouter API key not set! "
            "Get a free key at: https://openrouter.ai/keys"
        )

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }

    with httpx.Client(timeout=60.0) as client:
        with client.stream(
            "POST",
            OPENROUTER_API_URL,
            headers=get_headers(),
            json=payload,
        ) as response:
            if response.status_code != 200:
                raise Exception(f"OpenRouter API error: {response.status_code}")

            # Parse SSE (Server-Sent Events) stream
            for line in response.iter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]  # Remove "data: " prefix

                    # Stream end signal
                    if data_str.strip() == "[DONE]":
                        break

                    try:
                        data = json.loads(data_str)
                        # Extract the delta content
                        delta = data["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue  # Skip malformed chunks
