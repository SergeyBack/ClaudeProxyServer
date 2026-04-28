from uuid import UUID

from src.application.dto.stats_dto import (
    AccountStatItem,
    ModelStat,
    ModelStatItem,
    OverviewStatsResponse,
    UserStatsResponse,
)
from src.domain.interfaces.log_repository import LogRepository


class StatsService:
    def __init__(self, log_repo: LogRepository) -> None:
        self._log_repo = log_repo

    async def get_user_stats(self, user_id: UUID, days: int = 30) -> UserStatsResponse:
        raw = await self._log_repo.get_user_stats(user_id, days)
        return UserStatsResponse(
            total_requests=raw["total_requests"],
            total_input_tokens=raw["total_input_tokens"],
            total_output_tokens=raw["total_output_tokens"],
            models=[ModelStat(**m) for m in raw["models"]],
            days=days,
        )

    async def get_overview(self, days: int = 1) -> OverviewStatsResponse:
        raw = await self._log_repo.get_overview_stats(days)
        return OverviewStatsResponse(
            total_requests=raw["total_requests"],
            active_users=raw["active_users"],
            total_input_tokens=raw["total_input_tokens"],
            total_output_tokens=raw["total_output_tokens"],
            days=days,
        )

    async def get_account_stats(self, days: int = 30) -> list[AccountStatItem]:
        rows = await self._log_repo.get_account_stats(days)
        return [AccountStatItem(**r) for r in rows]

    async def get_model_stats(self, days: int = 30) -> list[ModelStatItem]:
        rows = await self._log_repo.get_model_stats(days)
        return [ModelStatItem(**r) for r in rows]
