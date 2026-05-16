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
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


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
GROQ_API_KEY = _get_secret("GROQ_API_KEY", "")
DEFAULT_MODEL = _get_secret("DEFAULT_MODEL", "deepseek/deepseek-v4-flash:free")

# Fallback models to try when the primary model is rate-limited (429)
# Last resort: Groq (separate rate limits, won't be blocked by OpenRouter traffic)
FREE_MODEL_FALLBACKS = [
    "deepseek/deepseek-v4-flash:free",
    "google/gemma-4-31b-it:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "groq::meta-llama/llama-4-scout-17b-16e-instruct",  # Groq fallback
]

# Groq models use a special prefix so we know to route to Groq API
GROQ_MODEL_PREFIX = "groq::"


def _is_groq_model(model: str) -> bool:
    """Check if a model should be routed to Groq."""
    return model.startswith(GROQ_MODEL_PREFIX)


def _groq_model_id(model: str) -> str:
    """Strip the groq:: prefix to get the actual Groq model ID."""
    return model[len(GROQ_MODEL_PREFIX):]


def _get_api_config(model: str) -> tuple:
    """
    Get the API URL, headers, and model ID based on provider.
    Returns: (api_url, headers, actual_model_id)
    """
    if _is_groq_model(model):
        return (
            GROQ_API_URL,
            {
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            _groq_model_id(model),
        )
    return (
        OPENROUTER_API_URL,
        get_headers(),
        model,
    )


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
    temperature: float = 0.3,
    max_tokens: int = 8192,
    stream: bool = False,
    stop: list[str] | None = None,
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
        stop: Optional list of stop sequences to halt generation.
    
    Returns:
        The assistant's response text.
    
    Raises:
        Exception: If the API call fails after retries.
    """
    # Validate API key
    if _is_groq_model(model):
        if not GROQ_API_KEY:
            raise ValueError("🔑 Groq API key not set! Get a free key at: https://console.groq.com")
    elif not OPENROUTER_API_KEY or OPENROUTER_API_KEY == "your_key_here":
        raise ValueError(
            "🔑 OpenRouter API key not set! "
            "Please add your key to the .env file. "
            "Get a free key at: https://openrouter.ai/keys"
        )

    # Build the request payload
    api_url, headers, actual_model = _get_api_config(model)
    payload = {
        "model": actual_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    # OpenRouter-specific options
    if not _is_groq_model(model):
        payload["include_reasoning"] = False
    if stop:
        payload["stop"] = stop

    # Groq models: direct call, no fallback cycling
    if _is_groq_model(model):
        models_to_try = [model]
    else:
        models_to_try = [model] + [m for m in FREE_MODEL_FALLBACKS if m != model]

    max_retries = len(models_to_try)
    current_model = model
    for attempt in range(max_retries):
        try:
            current_model = models_to_try[attempt]
            api_url, headers, actual_model = _get_api_config(current_model)
            payload["model"] = actual_model
            # Make the API call with a generous timeout
            with httpx.Client(timeout=120.0) as client:
                response = client.post(
                    api_url,
                    headers=headers,
                    json=payload,
                )

            # Handle rate limiting (429) or model not found (404) — skip to next model
            if response.status_code in (429, 404):
                if attempt < max_retries - 1:
                    import time as _time
                    wait = 3
                    if response.status_code == 429:
                        try:
                            err_data = response.json()
                            wait = min(int(err_data.get("error", {}).get("metadata", {}).get("retry_after_seconds", 3)), 5)
                        except Exception:
                            pass
                    else:
                        wait = 0
                    next_model = models_to_try[attempt + 1] if attempt + 1 < len(models_to_try) else "?"
                    print(f"⏳ {current_model.split('/')[-1]} {'rate limited' if response.status_code == 429 else 'not found'}. Trying {next_model.split('/')[-1]}...")
                    if wait:
                        _time.sleep(wait)
                    continue
                else:
                    raise Exception(
                        "❌ All models are rate limited. Free-tier is very busy — please wait 30 seconds and try again."
                    )

            # Check for other HTTP errors
            if response.status_code != 200:
                error_detail = response.text
                raise Exception(
                    f"API error (HTTP {response.status_code}): {error_detail}"
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
                import time as _time
                wait_time = 2 ** (attempt + 1)
                print(f"⏳ Request timed out. Retrying in {wait_time}s...")
                _time.sleep(wait_time)
            else:
                raise Exception(
                    "❌ OpenRouter API timed out after multiple attempts. "
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
    temperature: float = 0.3,
    max_tokens: int = 8192,
    stop: list[str] | None = None,
):
    """
    Stream a chat completion response from OpenRouter.
    
    Yields chunks of text as they arrive (Server-Sent Events).
    
    Args:
        messages: List of message dicts.
        model: The model ID to use.
        temperature: Controls randomness.
        max_tokens: Maximum tokens in the response.
        stop: Optional stop sequences.
    
    Yields:
        str: Chunks of the assistant's response.
    """
    global _last_usage

    # Validate API key
    if _is_groq_model(model):
        if not GROQ_API_KEY:
            raise ValueError("🔑 Groq API key not set! Get a free key at: https://console.groq.com")
    elif not OPENROUTER_API_KEY or OPENROUTER_API_KEY == "your_key_here":
        raise ValueError(
            "🔑 OpenRouter API key not set! "
            "Get a free key at: https://openrouter.ai/keys"
        )

    api_url, headers, actual_model = _get_api_config(model)
    payload = {
        "model": actual_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }
    if not _is_groq_model(model):
        payload["include_reasoning"] = False
    if stop:
        payload["stop"] = stop

    # Groq: direct call; OpenRouter: cycle fallbacks on 429
    if _is_groq_model(model):
        models_to_try = [model]
    else:
        models_to_try = [model] + [m for m in FREE_MODEL_FALLBACKS if m != model]

    max_retries = len(models_to_try)
    for attempt in range(max_retries):
        current_model = models_to_try[attempt]
        api_url, headers, actual_model = _get_api_config(current_model)
        payload["model"] = actual_model
        with httpx.Client(timeout=120.0) as client:
            with client.stream(
                "POST",
                api_url,
                headers=headers,
                json=payload,
            ) as response:
                # Handle rate limiting (429) or model not found (404) — skip to next
                if response.status_code in (429, 404):
                    if attempt < max_retries - 1:
                        import time as _time
                        wait = 3
                        if response.status_code == 429:
                            try:
                                error_body = ""
                                for chunk in response.iter_text():
                                    error_body += chunk
                                import json as _json
                                err_data = _json.loads(error_body)
                                wait = min(int(err_data.get("error", {}).get("metadata", {}).get("retry_after_seconds", 3)), 5)
                            except Exception:
                                pass
                        else:
                            wait = 0
                        next_model = models_to_try[attempt + 1] if attempt + 1 < len(models_to_try) else "?"
                        print(f"⏳ {current_model.split('/')[-1]} {'rate limited' if response.status_code == 429 else 'not found'}. Trying {next_model.split('/')[-1]}...")
                        if wait:
                            _time.sleep(wait)
                        continue  # Retry
                    else:
                        raise Exception(
                            "❌ All models are rate limited. Free-tier is very busy — please wait 30 seconds and try again."
                        )

                if response.status_code != 200:
                    error_body = ""
                    try:
                        for chunk in response.iter_text():
                            error_body += chunk
                    except Exception:
                        pass
                    raise Exception(f"OpenRouter API error (HTTP {response.status_code}): {error_body}")

                # Parse SSE (Server-Sent Events) stream
                for line in response.iter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]  # Remove "data: " prefix

                        # Stream end signal
                        if data_str.strip() == "[DONE]":
                            return

                        try:
                            data = json.loads(data_str)
                            # Capture usage if present (usually in last chunk)
                            if "usage" in data:
                                _last_usage = data["usage"]
                            # Extract the delta content
                            delta = data["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue  # Skip malformed chunks
                return  # Success — exit retry loop

