"""
llm.py — Multi-Provider LLM Client
=====================================
Routes API calls to the correct provider:
  - Groq (groq:: prefix) — fast, reliable, per-account rate limits
  - OpenRouter (default) — wide model selection, shared free-tier

Groq is the recommended default for reliability.
"""

import os
import json
import time
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
    try:
        import streamlit as st
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.getenv(key, default)


OPENROUTER_API_KEY = _get_secret("OPENROUTER_API_KEY", "")
GROQ_API_KEY = _get_secret("GROQ_API_KEY", "")
DEFAULT_MODEL = _get_secret("DEFAULT_MODEL", "groq::meta-llama/llama-4-scout-17b-16e-instruct")

# Groq models use a special prefix so we know to route to Groq API
GROQ_MODEL_PREFIX = "groq::"

# Fallback chain: Groq first (reliable), then OpenRouter free models
# Only includes models with working API keys
def _build_fallback_list():
    """Build fallback list based on available API keys."""
    fallbacks = []
    if GROQ_API_KEY:
        fallbacks.append("groq::meta-llama/llama-4-scout-17b-16e-instruct")
        fallbacks.append("groq::llama-3.3-70b-versatile")
    if OPENROUTER_API_KEY:
        fallbacks.append("google/gemma-4-31b-it:free")
        fallbacks.append("meta-llama/llama-3.3-70b-instruct:free")
    return fallbacks

FREE_MODEL_FALLBACKS = _build_fallback_list()

# ============================================
# Provider Routing
# ============================================

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
        {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/ai-agent",
            "X-Title": "AI Agent",
        },
        model,
    )


def get_headers() -> dict:
    """Build the request headers for OpenRouter API."""
    return {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/ai-agent",
        "X-Title": "AI Agent",
    }


# ============================================
# Retry Logic
# ============================================

# Error codes that should trigger model switching (not a crash)
_RETRYABLE_STATUS_CODES = {429, 404, 401, 403, 500, 502, 503, 529}


def _should_retry(status_code: int) -> bool:
    """Check if an HTTP status code is retryable."""
    return status_code in _RETRYABLE_STATUS_CODES


def _get_wait_time(response, attempt: int) -> int:
    """Extract wait time from error response, with fallback."""
    try:
        err_data = response.json()
        wait = err_data.get("error", {}).get("metadata", {}).get("retry_after_seconds", None)
        if wait:
            return min(int(wait), 5)
    except Exception:
        pass
    return min(2 ** attempt, 5)  # Exponential backoff: 1s, 2s, 4s, capped at 5s


# ============================================
# Chat Completion (blocking)
# ============================================

def chat_completion(
    messages: list[dict],
    model: str = DEFAULT_MODEL,
    temperature: float = 0.3,
    max_tokens: int = 8192,
    stream: bool = False,
    stop: list[str] | None = None,
) -> str:
    """
    Send a chat completion request to Groq or OpenRouter.
    
    Automatically retries on failure and cycles through fallback models.
    
    Args:
        messages: List of message dicts with 'role' and 'content' keys.
        model: The model ID to use (groq:: prefix routes to Groq).
        temperature: Controls randomness (0.0 = deterministic, 1.0 = creative).
        max_tokens: Maximum tokens in the response.
        stream: Whether to stream the response (not used in basic mode).
        stop: Optional list of stop sequences to halt generation.
    
    Returns:
        The assistant's response text.
    """
    global _last_usage

    # Build fallback list: requested model first, then all fallbacks
    models_to_try = [model] + [m for m in FREE_MODEL_FALLBACKS if m != model]

    error_trail = []  # Track all failures for diagnostics
    for attempt, current_model in enumerate(models_to_try):
        # Groq 429: wait and retry SAME model (per-account limits reset in seconds)
        groq_retries = 2 if _is_groq_model(current_model) else 0
        for groq_retry in range(groq_retries + 1):
            try:
                api_url, headers, actual_model = _get_api_config(current_model)

                payload = {
                    "model": actual_model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
                if not _is_groq_model(current_model):
                    payload["include_reasoning"] = False
                if stop:
                    payload["stop"] = stop

                with httpx.Client(timeout=120.0) as client:
                    response = client.post(api_url, headers=headers, json=payload)

                # Success
                if response.status_code == 200:
                    data = response.json()
                    _last_usage = data.get("usage", {})
                    if "choices" in data and len(data["choices"]) > 0:
                        return data["choices"][0]["message"]["content"]
                    else:
                        raise Exception(f"Unexpected API response: {json.dumps(data)[:200]}")

                # Groq 429 — wait and retry same model (limits reset quickly)
                if _is_groq_model(current_model) and response.status_code == 429 and groq_retry < groq_retries:
                    wait = _get_wait_time(response, groq_retry)
                    short_name = current_model.replace('groq::', '').split('/')[-1]
                    print(f"⏳ Groq {short_name} rate limited. Waiting {wait}s (retry {groq_retry+1}/{groq_retries})...")
                    time.sleep(wait)
                    continue  # Retry same Groq model

                # Failed — log and move to next model
                short_name = current_model.replace('groq::', '').split('/')[-1]
                error_trail.append(f"{short_name}→{response.status_code}")

                if _should_retry(response.status_code) and attempt < len(models_to_try) - 1:
                    next_model = models_to_try[attempt + 1]
                    short_next = next_model.replace('groq::', '').split('/')[-1]
                    print(f"⏳ {short_name} failed ({response.status_code}). Switching to {short_next}...")
                break  # Exit groq_retry loop, move to next model

            except httpx.TimeoutException:
                short_name = current_model.replace('groq::', '').split('/')[-1]
                error_trail.append(f"{short_name}→timeout")
                break

            except httpx.ConnectError:
                raise Exception("❌ Cannot connect to API. Check your internet connection.")

    trail_str = " | ".join(error_trail) if error_trail else "unknown"
    raise Exception(f"❌ All models failed: {trail_str}. Please try again in 30 seconds.")


# ============================================
# Stream Chat Completion
# ============================================

def stream_chat_completion(
    messages: list[dict],
    model: str = DEFAULT_MODEL,
    temperature: float = 0.3,
    max_tokens: int = 8192,
    stop: list[str] | None = None,
):
    """
    Stream a chat completion response from Groq or OpenRouter.
    
    Yields chunks of text as they arrive (Server-Sent Events).
    Automatically retries on failure and cycles through fallback models.
    """
    global _last_usage

    # Build fallback list
    models_to_try = [model] + [m for m in FREE_MODEL_FALLBACKS if m != model]

    error_trail = []
    for attempt, current_model in enumerate(models_to_try):
        groq_retries = 2 if _is_groq_model(current_model) else 0
        for groq_retry in range(groq_retries + 1):
            try:
                api_url, headers, actual_model = _get_api_config(current_model)

                payload = {
                    "model": actual_model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": True,
                }
                if not _is_groq_model(current_model):
                    payload["include_reasoning"] = False
                if stop:
                    payload["stop"] = stop

                with httpx.Client(timeout=120.0) as client:
                    with client.stream("POST", api_url, headers=headers, json=payload) as response:
                        if response.status_code != 200:
                            # Groq 429 — wait and retry same model
                            if _is_groq_model(current_model) and response.status_code == 429 and groq_retry < groq_retries:
                                short_name = current_model.replace('groq::', '').split('/')[-1]
                                wait = 5
                                try:
                                    body = "".join(chunk for chunk in response.iter_text())
                                    err_data = json.loads(body)
                                    wait = min(int(err_data.get("error", {}).get("metadata", {}).get("retry_after_seconds", 5)), 10)
                                except Exception:
                                    pass
                                print(f"⏳ Groq {short_name} rate limited. Waiting {wait}s (retry {groq_retry+1}/{groq_retries})...")
                                time.sleep(wait)
                                continue  # Retry same Groq model

                            short_name = current_model.replace('groq::', '').split('/')[-1]
                            error_trail.append(f"{short_name}→{response.status_code}")

                            if _should_retry(response.status_code) and attempt < len(models_to_try) - 1:
                                next_model = models_to_try[attempt + 1]
                                short_next = next_model.replace('groq::', '').split('/')[-1]
                                print(f"⏳ {short_name} failed ({response.status_code}). Switching to {short_next}...")
                            break  # Exit groq_retry loop

                        # Parse SSE (Server-Sent Events) stream
                        for line in response.iter_lines():
                            if line.startswith("data: "):
                                data_str = line[6:]

                                if data_str.strip() == "[DONE]":
                                    return

                                try:
                                    data = json.loads(data_str)
                                    if "usage" in data:
                                        _last_usage = data["usage"]
                                    delta = data["choices"][0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        yield content
                                except (json.JSONDecodeError, KeyError, IndexError):
                                    continue
                        return  # Success

            except httpx.TimeoutException:
                short_name = current_model.replace('groq::', '').split('/')[-1]
                error_trail.append(f"{short_name}→timeout")
                break

            except httpx.ConnectError:
                raise Exception("❌ Cannot connect to API. Check your internet connection.")

    trail_str = " | ".join(error_trail) if error_trail else "unknown"
    raise Exception(f"❌ All models failed: {trail_str}. Please try again in 30 seconds.")
