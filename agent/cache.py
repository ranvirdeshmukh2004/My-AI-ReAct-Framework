"""
cache.py — Redis Caching Layer
=================================
Caches LLM responses and tool results to save API costs
and speed up repeated queries.

Graceful fallback: uses in-memory dict if Redis is not configured.

TTL (time-to-live) per category:
- LLM responses: 1 hour
- Calculator: no expiry (deterministic)
- Weather: 30 minutes
- Wikipedia: 24 hours
- Web search: 15 minutes
- DateTime: 1 minute
- URL reader: 1 hour
"""

import os
import json
import hashlib
from datetime import datetime
from typing import Optional


# TTL in seconds per tool/category
CACHE_TTLS = {
    "llm": 3600,           # 1 hour
    "calculator": 0,       # Never expires (deterministic)
    "weather": 1800,       # 30 minutes
    "wikipedia": 86400,    # 24 hours
    "web_search": 900,     # 15 minutes
    "datetime": 60,        # 1 minute
    "read_url": 3600,      # 1 hour
    "read_file": 0,        # Never expires (file content is static)
    "python_executor": 0,  # Never expires (deterministic)
    "doc_search": 300,     # 5 minutes
}


import re


def _normalize(text: str) -> str:
    """
    Normalize text for cache key generation.
    Makes similar queries hit the same cache entry.
    
    'What's the weather in Tokyo?' → 'whats the weather in tokyo'
    'Weather in Tokyo'             → 'weather in tokyo'
    """
    text = text.lower().strip()
    # Remove punctuation
    text = re.sub(r"[^\w\s]", "", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text)
    # Remove common filler words for better matching
    stopwords = {"what", "is", "the", "whats", "tell", "me", "about",
                 "can", "you", "please", "give", "show", "find", "get",
                 "how", "does", "do", "a", "an", "of", "for", "in"}
    words = text.split()
    # Only remove stopwords if there are enough meaningful words left
    meaningful = [w for w in words if w not in stopwords]
    if len(meaningful) >= 2:
        text = " ".join(meaningful)
    return text


def _make_key(prefix: str, content: str) -> str:
    """Generate a cache key from prefix and normalized content hash."""
    normalized = _normalize(content)
    content_hash = hashlib.sha256(normalized.encode()).hexdigest()[:16]
    return f"ai_agent:{prefix}:{content_hash}"


class RedisCache:
    """
    Caching layer with Redis backend and in-memory fallback.
    
    Usage:
        cache = RedisCache()
        cache.set("llm", "prompt_text", "response_text")
        result = cache.get("llm", "prompt_text")
    """

    def __init__(self):
        """Initialize cache — tries Redis, falls back to in-memory."""
        self._redis = None
        self._memory_cache = {}  # Fallback: {key: {"value": ..., "expires": ...}}
        self._stats = {"hits": 0, "misses": 0}
        self._using_redis = False

        self._connect_redis()

    def _connect_redis(self):
        """Try to connect to Redis."""
        redis_url = self._get_redis_url()
        if not redis_url:
            return

        try:
            import redis
            self._redis = redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            # Test connection
            self._redis.ping()
            self._using_redis = True
        except Exception as e:
            print(f"⚠️ Redis connection failed ({e}), using in-memory cache")
            self._redis = None
            self._using_redis = False

    def _get_redis_url(self) -> str:
        """Get Redis URL from st.secrets or environment."""
        try:
            import streamlit as st
            if "REDIS_URL" in st.secrets:
                return st.secrets["REDIS_URL"]
        except Exception:
            pass
        return os.getenv("REDIS_URL", "")

    @property
    def is_redis(self) -> bool:
        """Whether Redis is connected."""
        return self._using_redis

    @property
    def stats(self) -> dict:
        """Cache hit/miss statistics."""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = (self._stats["hits"] / total * 100) if total > 0 else 0
        return {
            **self._stats,
            "total": total,
            "hit_rate": round(hit_rate, 1),
            "backend": "Redis" if self._using_redis else "Memory",
        }

    def get(self, category: str, content: str) -> Optional[str]:
        """
        Get a cached value.
        
        Args:
            category: Cache category (e.g., "llm", "calculator")
            content: The content to look up (prompt text or tool input)
        
        Returns:
            Cached value string, or None if not found.
        """
        key = _make_key(category, content)

        try:
            if self._using_redis and self._redis:
                result = self._redis.get(key)
                if result is not None:
                    self._stats["hits"] += 1
                    return result
                self._stats["misses"] += 1
                return None
            else:
                # In-memory fallback
                if key in self._memory_cache:
                    entry = self._memory_cache[key]
                    # Check expiry
                    if entry["expires"] == 0 or entry["expires"] > datetime.now().timestamp():
                        self._stats["hits"] += 1
                        return entry["value"]
                    else:
                        # Expired — remove it
                        del self._memory_cache[key]
                self._stats["misses"] += 1
                return None
        except Exception:
            self._stats["misses"] += 1
            return None

    def set(self, category: str, content: str, value: str) -> bool:
        """
        Store a value in cache.
        
        Args:
            category: Cache category (determines TTL)
            content: The content key (prompt text or tool input)
            value: The value to cache (response text or tool output)
        
        Returns:
            True if cached successfully.
        """
        key = _make_key(category, content)
        ttl = CACHE_TTLS.get(category, 3600)

        try:
            if self._using_redis and self._redis:
                if ttl == 0:
                    # No expiry
                    self._redis.set(key, value)
                else:
                    self._redis.setex(key, ttl, value)
                return True
            else:
                # In-memory fallback
                expires = 0 if ttl == 0 else (datetime.now().timestamp() + ttl)
                self._memory_cache[key] = {"value": value, "expires": expires}
                return True
        except Exception:
            return False

    def clear(self):
        """Clear all cached entries."""
        try:
            if self._using_redis and self._redis:
                # Only delete our keys (prefixed with ai_agent:)
                keys = self._redis.keys("ai_agent:*")
                if keys:
                    self._redis.delete(*keys)
            else:
                self._memory_cache.clear()
            self._stats = {"hits": 0, "misses": 0}
        except Exception:
            self._memory_cache.clear()

    def size(self) -> int:
        """Get number of cached entries."""
        try:
            if self._using_redis and self._redis:
                return len(self._redis.keys("ai_agent:*"))
            else:
                return len(self._memory_cache)
        except Exception:
            return 0
