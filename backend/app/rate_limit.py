"""
Rate limiting (Phase 9.4), via slowapi.

A single shared Limiter instance, imported by any router that needs to
decorate an endpoint with @limiter.limit(...). Kept in its own module
(rather than defined in main.py) so app/api/*.py files can import it
without a circular import back to main.py.

STORAGE: uses Redis when REDIS_URL is configured (the same Redis instance
Phase 9.2 already uses for sessions/audio cache) so rate limits are shared
correctly across multiple backend worker processes in production - a
per-process in-memory counter would let each worker allow its own full
quota, defeating the point. Falls back to slowapi's built-in in-memory
storage when Redis isn't configured, matching this project's established
pattern (app/storage.py) of "Redis when available, safe local fallback
otherwise."

ENABLED/DISABLED: controlled by RATE_LIMIT_ENABLED in .env. Tests run with
this off (see tests/conftest.py) so test assertions aren't flaky depending
on how many requests a test happens to fire.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings

_storage_uri = settings.REDIS_URL if settings.REDIS_URL else "memory://"

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=_storage_uri,
    enabled=settings.RATE_LIMIT_ENABLED,
    # If Redis is configured but happens to be briefly unreachable, don't
    # take the whole API down over a rate-limit check - fail open rather
    # than 500ing every request.
    in_memory_fallback_enabled=True,
    swallow_errors=True,
)
