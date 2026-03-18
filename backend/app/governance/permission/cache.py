"""Permission cache using Redis."""
import json
from typing import Optional, Set

import redis.asyncio as redis

from app.config import settings


class PermissionCache:
    """Redis-based permission cache."""

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self._redis = redis_client
        self._prefix = "perm:"
        self._ttl = 3600  # 1 hour TTL

    async def _get_redis(self) -> redis.Redis:
        """Get Redis client."""
        if self._redis is None:
            self._redis = redis.from_url(
                settings.redis_url, decode_responses=True
            )
        return self._redis

    def _key(self, user_id: str) -> str:
        """Get cache key for user."""
        return f"{self._prefix}{user_id}"

    async def get(self, user_id: str) -> Optional[Set[str]]:
        """Get cached permissions for user."""
        client = await self._get_redis()
        data = await client.get(self._key(user_id))
        if data is None:
            return None
        return set(json.loads(data))

    async def set(self, user_id: str, permissions: Set[str]) -> None:
        """Cache permissions for user."""
        client = await self._get_redis()
        await client.setex(
            self._key(user_id),
            self._ttl,
            json.dumps(list(permissions)),
        )

    async def delete(self, user_id: str) -> None:
        """Delete cached permissions for user."""
        client = await self._get_redis()
        await client.delete(self._key(user_id))

    async def clear_all(self) -> None:
        """Clear all cached permissions."""
        client = await self._get_redis()
        keys = await client.keys(f"{self._prefix}*")
        if keys:
            await client.delete(*keys)