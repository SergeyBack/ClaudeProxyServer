from fastapi import APIRouter, Depends

from src.api.dependencies import get_current_user_jwt, get_stats_service, get_user_service
from src.application.dto.stats_dto import UserStatsResponse
from src.application.dto.user_dto import ApiKeyResponse, UserResponse
from src.application.services.stats_service import StatsService
from src.application.services.user_service import UserService
from src.domain.models.user import User

router = APIRouter(prefix="/user", tags=["user"])


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user_jwt)):
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        api_key_prefix=user.api_key_prefix,
        created_at=user.created_at,
    )


@router.get("/usage", response_model=UserStatsResponse)
async def get_my_usage(
    days: int = 30,
    user: User = Depends(get_current_user_jwt),
    stats_service: StatsService = Depends(get_stats_service),
):
    return await stats_service.get_user_stats(user.id, days)


@router.post("/api-key/rotate", response_model=ApiKeyResponse)
async def rotate_api_key(
    user: User = Depends(get_current_user_jwt),
    user_service: UserService = Depends(get_user_service),
):
    _, raw_key = await user_service.rotate_api_key(user.id)
    return ApiKeyResponse(api_key=raw_key, prefix=raw_key[:12])
