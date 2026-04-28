from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.dependencies import get_account_service, get_current_admin, get_probe_service
from src.application.dto.account_dto import (
    AccountCreateRequest,
    AccountResponse,
    AccountTestResponse,
    AccountUpdateRequest,
)
from src.application.services.account_service import AccountService
from src.application.services.probe_service import ProbeService
from src.domain.exceptions import AccountNotFoundError
from src.domain.models.user import User

router = APIRouter(prefix="/admin/accounts", tags=["admin"])


@router.get("", response_model=list[AccountResponse])
async def list_accounts(
    _: User = Depends(get_current_admin),
    service: AccountService = Depends(get_account_service),
):
    items = await service.list_accounts()
    return [
        AccountResponse(
            id=account.id,
            name=account.name,
            email=account.email,
            status=account.status,
            rate_limit_until=account.rate_limit_until,
            max_connections=account.max_connections,
            priority=account.priority,
            active_connections=connections,
            created_at=account.created_at,
            last_used_at=account.last_used_at,
        )
        for account, connections in items
    ]


@router.post("", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(
    req: AccountCreateRequest,
    _: User = Depends(get_current_admin),
    service: AccountService = Depends(get_account_service),
):
    account = await service.create_account(req)
    return AccountResponse(
        id=account.id,
        name=account.name,
        email=account.email,
        status=account.status,
        rate_limit_until=account.rate_limit_until,
        max_connections=account.max_connections,
        priority=account.priority,
        created_at=account.created_at,
        last_used_at=account.last_used_at,
    )


@router.put("/{account_id}", response_model=AccountResponse)
async def update_account(
    account_id: UUID,
    req: AccountUpdateRequest,
    _: User = Depends(get_current_admin),
    service: AccountService = Depends(get_account_service),
):
    try:
        account = await service.update_account(account_id, req)
    except AccountNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    return AccountResponse(
        id=account.id,
        name=account.name,
        email=account.email,
        status=account.status,
        rate_limit_until=account.rate_limit_until,
        max_connections=account.max_connections,
        priority=account.priority,
        created_at=account.created_at,
        last_used_at=account.last_used_at,
    )


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    account_id: UUID,
    _: User = Depends(get_current_admin),
    service: AccountService = Depends(get_account_service),
):
    try:
        await service.delete_account(account_id)
    except AccountNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))


@router.post("/{account_id}/test", response_model=AccountTestResponse)
async def test_account(
    account_id: UUID,
    _: User = Depends(get_current_admin),
    service: AccountService = Depends(get_account_service),
    probe_svc: ProbeService = Depends(get_probe_service),
):
    try:
        account = await service.get_account(account_id)
    except AccountNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))

    result = await probe_svc.probe_account(account)
    return AccountTestResponse(**result)


@router.post("/{account_id}/unban", response_model=AccountResponse)
async def unban_account(
    account_id: UUID,
    _: User = Depends(get_current_admin),
    service: AccountService = Depends(get_account_service),
):
    try:
        account = await service.unban_account(account_id)
    except AccountNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    return AccountResponse(
        id=account.id,
        name=account.name,
        email=account.email,
        status=account.status,
        rate_limit_until=account.rate_limit_until,
        max_connections=account.max_connections,
        priority=account.priority,
        created_at=account.created_at,
        last_used_at=account.last_used_at,
    )
