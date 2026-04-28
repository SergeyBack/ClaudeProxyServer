from fastapi import APIRouter, Depends

from src.api.dependencies import get_account_service, get_current_admin, get_stats_service
from src.application.dto.account_dto import AccountResponse
from src.application.dto.stats_dto import (
    AccountStatItem,
    ModelStatItem,
    OverviewStatsResponse,
)
from src.application.services.account_service import AccountService
from src.application.services.stats_service import StatsService
from src.domain.models.user import User

router = APIRouter(prefix="/admin/stats", tags=["admin"])


@router.get("/overview", response_model=OverviewStatsResponse)
async def overview(
    days: int = 1,
    _: User = Depends(get_current_admin),
    stats: StatsService = Depends(get_stats_service),
):
    return await stats.get_overview(days)


@router.get("/accounts", response_model=list[AccountStatItem])
async def account_stats(
    days: int = 30,
    _: User = Depends(get_current_admin),
    stats: StatsService = Depends(get_stats_service),
):
    return await stats.get_account_stats(days)


@router.get("/models", response_model=list[ModelStatItem])
async def model_stats(
    days: int = 30,
    _: User = Depends(get_current_admin),
    stats: StatsService = Depends(get_stats_service),
):
    return await stats.get_model_stats(days)


@router.get("/banned", response_model=list[AccountResponse])
async def banned_accounts(
    _: User = Depends(get_current_admin),
    service: AccountService = Depends(get_account_service),
):
    accounts = await service.get_banned_accounts()
    return [
        AccountResponse(
            id=a.id,
            name=a.name,
            email=a.email,
            auth_type=a.auth_type,
            status=a.status,
            rate_limit_until=a.rate_limit_until,
            max_connections=a.max_connections,
            priority=a.priority,
            created_at=a.created_at,
            last_used_at=a.last_used_at,
        )
        for a in accounts
    ]
