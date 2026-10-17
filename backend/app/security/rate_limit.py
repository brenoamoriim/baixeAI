"""Fixed-window rate limiting backed by Redis."""

from functools import lru_cache

import redis

from app.core.config import get_settings
from app.core.errors import RateLimited


@lru_cache
def get_redis() -> redis.Redis:
    return redis.Redis.from_url(get_settings().redis_url, decode_responses=True)


def hit(key: str, *, limit: int, window_seconds: int) -> None:
    """Count one hit for `key`; raise RateLimited when over `limit` in the window."""
    client = get_redis()
    full_key = f"rl:{key}"
    pipe = client.pipeline()
    pipe.incr(full_key)
    pipe.expire(full_key, window_seconds, nx=True)
    count, _ = pipe.execute()
    if int(count) > limit:
        raise RateLimited("Muitas tentativas. Aguarde alguns minutos e tente novamente.")
