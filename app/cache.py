"""Redis integration (blueprint §9): caching + rate limiting now; Celery queue /
agent state later. OPTIONAL — if REDIS_URL is unset or unreachable, everything
degrades gracefully so the app still runs."""
from __future__ import annotations

import time

from .config import get_settings

settings = get_settings()

_client = None
_enabled = False

if settings.redis_url:
    try:
        import redis  # type: ignore

        _client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        _client.ping()
        _enabled = True
    except Exception:
        _client = None
        _enabled = False


def enabled() -> bool:
    return _enabled


def status() -> str:
    return "connected" if _enabled else ("configured" if settings.redis_url else "disabled")


def cache_get(key: str) -> str | None:
    if not _enabled:
        return None
    try:
        return _client.get(key)  # type: ignore[union-attr]
    except Exception:
        return None


def cache_set(key: str, value: str, ttl_seconds: int = 300) -> None:
    if not _enabled:
        return
    try:
        _client.setex(key, ttl_seconds, value)  # type: ignore[union-attr]
    except Exception:
        pass


import json


def session_set(user_id: str, data: dict, ttl_seconds: int = 3600) -> None:
    """Store per-user server-side session state (agent context, transient prefs).

    This is the mobile-native equivalent of a web session: the app authenticates
    with a Firebase bearer token (not a cookie), and this holds the short-lived
    state keyed to that user. No-op when Redis is disabled."""
    cache_set(f"sess:{user_id}", json.dumps(data), ttl_seconds)


def session_get(user_id: str) -> dict | None:
    raw = cache_get(f"sess:{user_id}")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def session_delete(user_id: str) -> None:
    if not _enabled:
        return
    try:
        _client.delete(f"sess:{user_id}")  # type: ignore[union-attr]
    except Exception:
        pass


def allow_request(user_id: str) -> bool:
    """Fixed-window per-user rate limit. Always allows when Redis is disabled."""
    if not _enabled:
        return True
    try:
        window = int(time.time() // 60)
        key = f"rl:{user_id}:{window}"
        count = _client.incr(key)  # type: ignore[union-attr]
        if count == 1:
            _client.expire(key, 60)  # type: ignore[union-attr]
        return count <= settings.rate_limit_per_min
    except Exception:
        return True
