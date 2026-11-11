"""Redis-backed transient state with safe in-process fallbacks."""
from __future__ import annotations
import time
from redis.asyncio import Redis
from redis.exceptions import RedisError


class RuntimeStore:
    def __init__(self, redis_url: str) -> None:
        self.redis = Redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=5, socket_timeout=5)
        self.local: dict[str, tuple[str, float]] = {}

    async def ping(self) -> bool:
        try:
            return bool(await self.redis.ping())
        except RedisError:
            return False

    async def get(self, key: str) -> str | None:
        try:
            value = await self.redis.get(key)
            if value is not None:
                return value
        except RedisError:
            pass
        item = self.local.get(key)
        if item and item[1] > time.monotonic():
            return item[0]
        self.local.pop(key, None)
        return None

    async def set(self, key: str, value: str, ttl: int = 60) -> None:
        try:
            await self.redis.set(key, value, ex=ttl)
        except RedisError:
            self.local[key] = (value, time.monotonic() + ttl)

    async def delete(self, key: str) -> None:
        try:
            await self.redis.delete(key)
        except RedisError:
            pass
        self.local.pop(key, None)

    async def hit_limit(self, key: str, limit: int, ttl: int) -> tuple[bool, int]:
        """Atomically count a short-lived rate-limit key when Redis is available."""
        try:
            pipe = self.redis.pipeline()
            pipe.incr(key)
            pipe.expire(key, ttl)
            result = await pipe.execute()
            count = int(result[0])
        except RedisError:
            now = time.monotonic()
            old = self.local.get(key)
            count = int(old[0]) + 1 if old and old[1] > now else 1
            self.local[key] = (str(count), now + ttl)
        return count <= limit, count

    async def close(self) -> None:
        await self.redis.aclose()
