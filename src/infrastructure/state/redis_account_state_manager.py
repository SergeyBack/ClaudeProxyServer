from datetime import UTC, datetime
from uuid import UUID

import redis.asyncio as aioredis


class RedisAccountStateManager:
    def __init__(self, redis: aioredis.Redis) -> None:
        self._r = redis

    def _conn_key(self, account_id: UUID) -> str:
        return f"conn:{account_id}"

    def _rl_key(self, account_id: UUID) -> str:
        return f"rl:{account_id}"

    async def acquire(self, account_id: UUID) -> None:
        await self._r.incr(self._conn_key(account_id))

    async def release(self, account_id: UUID) -> None:
        key = self._conn_key(account_id)
        val = await self._r.decr(key)
        if val < 0:
            await self._r.set(key, 0)

    async def get_connections(self, account_id: UUID) -> int:
        val = await self._r.get(self._conn_key(account_id))
        return int(val) if val else 0

    async def mark_rate_limited(self, account_id: UUID, retry_after: int) -> None:
        await self._r.set(self._rl_key(account_id), 1, ex=retry_after)

    async def restore_rate_limit(self, account_id: UUID, until: datetime) -> None:
        now = datetime.now(UTC)
        if until > now:
            ttl = int((until - now).total_seconds())
            await self._r.set(self._rl_key(account_id), 1, ex=ttl)

    async def is_rate_limited(self, account_id: UUID) -> bool:
        return await self._r.exists(self._rl_key(account_id)) == 1

    async def clear_rate_limit(self, account_id: UUID) -> None:
        await self._r.delete(self._rl_key(account_id))

    async def get_all_connections(self) -> dict[UUID, int]:
        keys = await self._r.keys("conn:*")
        if not keys:
            return {}
        values = await self._r.mget(keys)
        return {
            UUID(k.decode().removeprefix("conn:")): int(v) if v else 0
            for k, v in zip(keys, values)
        }
