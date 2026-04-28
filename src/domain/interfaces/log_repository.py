from typing import Protocol
from uuid import UUID

from src.domain.models.request_log import RequestLog


class LogRepository(Protocol):
    async def create(self, log: RequestLog) -> None: ...

    async def list_by_user(
        self,
        user_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[RequestLog]: ...

    async def get_user_stats(self, user_id: UUID, days: int = 30) -> dict: ...

    async def get_overview_stats(self, days: int = 1) -> dict: ...

    async def get_account_stats(self, days: int = 30) -> list[dict]: ...

    async def get_model_stats(self, days: int = 30) -> list[dict]: ...
