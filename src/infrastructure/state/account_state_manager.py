import asyncio
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from uuid import UUID


class AccountStateManager:
    """
    In-memory tracker for active connections and rate-limit state.
    Thread-safe via asyncio.Lock (single event loop).

    For multi-worker deployments, replace with Redis-backed implementation
    (only this class changes — the interface stays the same).
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._connections: dict[UUID, int] = defaultdict(int)
        self._rate_limit_until: dict[UUID, datetime] = {}

    async def acquire(self, account_id: UUID) -> None:
        async with self._lock:
            self._connections[account_id] += 1

    async def release(self, account_id: UUID) -> None:
        async with self._lock:
            self._connections[account_id] = max(0, self._connections[account_id] - 1)

    async def get_connections(self, account_id: UUID) -> int:
        async with self._lock:
            return self._connections[account_id]

    async def mark_rate_limited(self, account_id: UUID, retry_after: int) -> None:
        async with self._lock:
            self._rate_limit_until[account_id] = datetime.now(UTC) + timedelta(seconds=retry_after)

    async def restore_rate_limit(self, account_id: UUID, until: datetime) -> None:
        """Seed from DB on startup so rate limits survive restarts."""
        if until > datetime.now(UTC):
            async with self._lock:
                self._rate_limit_until[account_id] = until

    async def is_rate_limited(self, account_id: UUID) -> bool:
        async with self._lock:
            until = self._rate_limit_until.get(account_id)
            if until is None:
                return False
            if datetime.now(UTC) >= until:
                del self._rate_limit_until[account_id]
                return False
            return True

    async def clear_rate_limit(self, account_id: UUID) -> None:
        async with self._lock:
            self._rate_limit_until.pop(account_id, None)

    async def get_all_connections(self) -> dict[UUID, int]:
        async with self._lock:
            return dict(self._connections)
