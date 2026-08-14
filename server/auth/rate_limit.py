"""Shared rate limiting. Redis when REDIS_URL is set; otherwise SQLite.

In-process limits cannot protect a multi-instance Render deployment.
"""

from __future__ import annotations

from typing import Protocol

import config
from auth.store import get_store


class RateLimiter(Protocol):
    def allow(
        self,
        key: str,
        *,
        limit: int,
        window_secs: int,
        now: float | None = None,
    ) -> bool: ...


class SqliteRateLimiter:
    def allow(
        self,
        key: str,
        *,
        limit: int,
        window_secs: int,
        now: float | None = None,
    ) -> bool:
        return get_store().hit_rate_limit(
            key, limit=limit, window_secs=window_secs, now=now
        )


class RedisRateLimiter:
    def __init__(self, url: str) -> None:
        import redis

        self._client = redis.Redis.from_url(url, decode_responses=True)

    def allow(
        self,
        key: str,
        *,
        limit: int,
        window_secs: int,
        now: float | None = None,
    ) -> bool:
        namespaced = f"lumina:rl:{key}"
        pipe = self._client.pipeline()
        pipe.incr(namespaced, 1)
        pipe.expire(namespaced, window_secs, nx=True)
        count, _ = pipe.execute()
        return int(count) <= limit


_LIMITER: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    global _LIMITER
    if _LIMITER is not None:
        return _LIMITER
    if config.REDIS_URL:
        try:
            _LIMITER = RedisRateLimiter(config.REDIS_URL)
            return _LIMITER
        except Exception:
            pass
    _LIMITER = SqliteRateLimiter()
    return _LIMITER


def reset_rate_limiter_for_tests() -> None:
    global _LIMITER
    _LIMITER = SqliteRateLimiter()
