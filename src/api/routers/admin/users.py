from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.dependencies import get_current_admin, get_stats_service, get_user_service
from src.application.dto.stats_dto import UserStatsResponse
from src.application.dto.user_dto import (
    ApiKeyResponse,
    UserCreateRequest,
    UserResponse,
    UserUpdateRequest,
)
from src.application.services.stats_service import StatsService
from src.application.services.user_service import UserService
from src.domain.exceptions import UserNotFoundError
from src.domain.models.user import User

router = APIRouter(prefix="/admin/users", tags=["admin"])


@router.get("", response_model=list[UserResponse])
async def list_users(
    _: User = Depends(get_current_admin),
    service: UserService = Depends(get_user_service),
):
    users = await service.list_users()
    return [
        UserResponse(
            id=u.id,
            username=u.username,
            email=u.email,
            role=u.role,
            is_active=u.is_active,
            api_key_prefix=u.api_key_prefix,
            created_at=u.created_at,
        )
        for u in users
    ]


@router.post("", response_model=ApiKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    req: UserCreateRequest,
    _: User = Depends(get_current_admin),
    service: UserService = Depends(get_user_service),
):
    _, raw_key = await service.create_user(req)
    return ApiKeyResponse(api_key=raw_key, prefix=raw_key[:12])


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    _: User = Depends(get_current_admin),
    service: UserService = Depends(get_user_service),
):
    try:
        u = await service.get_by_id(user_id)
    except UserNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    return UserResponse(
        id=u.id,
        username=u.username,
        email=u.email,
        role=u.role,
        is_active=u.is_active,
        api_key_prefix=u.api_key_prefix,
        created_at=u.created_at,
    )


@router.get("/{user_id}/stats", response_model=UserStatsResponse)
async def get_user_stats(
    user_id: UUID,
    days: int = 30,
    _: User = Depends(get_current_admin),
    stats_service: StatsService = Depends(get_stats_service),
):
    return await stats_service.get_user_stats(user_id, days)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    req: UserUpdateRequest,
    _: User = Depends(get_current_admin),
    service: UserService = Depends(get_user_service),
):
    try:
        u = await service.update_user(user_id, req)
    except UserNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    return UserResponse(
        id=u.id,
        username=u.username,
        email=u.email,
        role=u.role,
        is_active=u.is_active,
        api_key_prefix=u.api_key_prefix,
        created_at=u.created_at,
    )


@router.post("/{user_id}/api-key/rotate", response_model=ApiKeyResponse)
async def rotate_user_api_key(
    user_id: UUID,
    _: User = Depends(get_current_admin),
    service: UserService = Depends(get_user_service),
):
    try:
        _, raw_key = await service.rotate_api_key(user_id)
    except UserNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    return ApiKeyResponse(api_key=raw_key, prefix=raw_key[:12])
