"""
Shared key-value storage with TTL support.

Backs two things that used to be plain Python dicts:
- conversation session history (app/agents/conversation.py)
- Twilio reply-audio cache (app/api/telephony.py)

Both were flagged since Phase 4/7 as "in-memory only, unsafe for multiple
production workers." This module is the fix: if REDIS_URL is configured
and reachable, everything goes through Redis (shared across any number of
server processes, with real TTL-based expiry). If REDIS_URL is unset or
Redis is unreachable, it transparently falls back to the exact same
in-memory dict behavior the project already had - so local development
without Redis running keeps working exactly as before, and conversation
session tests behave identically pass or fail.

WHY A FALLBACK INSTEAD OF REQUIRING REDIS: the instruction for this phase
was explicit - "do not blindly replace them... conversation behavior must
remain unchanged." Requiring Redis unconditionally would break any
existing local dev workflow that doesn't have Redis running. This module
uses Redis when it's there and gets out of the way when it isn't.

Values are JSON-serialized for the "json" methods (used for session
history - lists of dicts) and stored as raw bytes for the "bytes" methods
(used for audio clips).
"""

import json
import logging
import threading
import time
from typing import Any

from app.config import settings

logger = logging.getLogger("storage")

_redis_client = None
_redis_checked = False
_redis_lock = threading.Lock()


def _get_redis():
    """
    Lazily constructs and health-checks a Redis client once. If REDIS_URL
    is unset, or the ping fails, this returns None permanently for this
    process (no repeated connection attempts on every request) and callers
    fall back to the in-memory store.
    """
    global _redis_client, _redis_checked
    if _redis_checked:
        return _redis_client

    with _redis_lock:
        if _redis_checked:  # re-check inside the lock (another thread may have set it)
            return _redis_client
        _redis_checked = True

        if not settings.REDIS_URL:
            logger.info("REDIS_URL not set - using in-memory storage fallback (single-process only).")
            return None

        try:
            import redis as redis_lib
            client = redis_lib.from_url(settings.REDIS_URL, socket_connect_timeout=2, socket_timeout=2)
            client.ping()
            _redis_client = client
            logger.info("Connected to Redis at %s - using shared storage.", settings.REDIS_URL)
        except Exception as e:
            logger.warning(
                "Could not connect to Redis at %s (%s) - falling back to in-memory storage. "
                "This is fine for local single-process dev, but unsafe for multiple production workers.",
                settings.REDIS_URL, e,
            )
            _redis_client = None

        return _redis_client


# ---------------------------------------------------------------------------
# In-memory fallback store: dict value + expiry timestamp, same shape
# regardless of which store backs a given key, so callers don't care.
# ---------------------------------------------------------------------------

_memory_store: dict[str, tuple[Any, float | None]] = {}
_memory_lock = threading.Lock()


def _memory_get(key: str) -> Any | None:
    with _memory_lock:
        entry = _memory_store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if expires_at is not None and time.time() > expires_at:
            del _memory_store[key]
            return None
        return value


def _memory_set(key: str, value: Any, ttl_seconds: int | None) -> None:
    with _memory_lock:
        expires_at = (time.time() + ttl_seconds) if ttl_seconds else None
        _memory_store[key] = (value, expires_at)


def _memory_delete(key: str) -> None:
    with _memory_lock:
        _memory_store.pop(key, None)


# ---------------------------------------------------------------------------
# Public API - JSON values (used for conversation session history)
# ---------------------------------------------------------------------------

def get_json(key: str) -> Any | None:
    client = _get_redis()
    if client is not None:
        raw = client.get(key)
        return json.loads(raw) if raw is not None else None
    return _memory_get(key)


def set_json(key: str, value: Any, ttl_seconds: int | None = None) -> None:
    client = _get_redis()
    if client is not None:
        raw = json.dumps(value)
        if ttl_seconds:
            client.setex(key, ttl_seconds, raw)
        else:
            client.set(key, raw)
        return
    _memory_set(key, value, ttl_seconds)


def delete(key: str) -> None:
    client = _get_redis()
    if client is not None:
        client.delete(key)
        return
    _memory_delete(key)


# ---------------------------------------------------------------------------
# Public API - raw bytes (used for the Twilio audio cache)
# ---------------------------------------------------------------------------

def get_bytes(key: str) -> bytes | None:
    client = _get_redis()
    if client is not None:
        return client.get(key)  # redis-py returns bytes for non-decoded clients
    return _memory_get(key)


def set_bytes(key: str, value: bytes, ttl_seconds: int | None = None) -> None:
    client = _get_redis()
    if client is not None:
        if ttl_seconds:
            client.setex(key, ttl_seconds, value)
        else:
            client.set(key, value)
        return
    _memory_set(key, value, ttl_seconds)


def pop_bytes(key: str) -> bytes | None:
    """Get-and-delete in one call (used for the one-time-fetch audio cache)."""
    client = _get_redis()
    if client is not None:
        pipe = client.pipeline()
        pipe.get(key)
        pipe.delete(key)
        value, _ = pipe.execute()
        return value
    value = _memory_get(key)
    if value is not None:
        _memory_delete(key)
    return value


def backend_name() -> str:
    """For diagnostics/tests - which backend is actually active right now."""
    return "redis" if _get_redis() is not None else "memory"
