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

# Load environment variables from .env file
load_dotenv()

# ============================================
# Configuration
# ============================================

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "x-ai/grok-4.1-fast")


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
