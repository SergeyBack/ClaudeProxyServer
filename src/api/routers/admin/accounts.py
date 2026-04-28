import time
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.dependencies import get_account_service, get_client_pool, get_current_admin
from src.application.dto.account_dto import (
    AccountCreateRequest,
    AccountResponse,
    AccountTestResponse,
    AccountUpdateRequest,
)
from src.application.services.account_service import AccountService
from src.core.security import decrypt_token
from src.domain.exceptions import AccountNotFoundError
from src.domain.models.user import User
from src.infrastructure.http.client_pool import ClientPool

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
            auth_type=account.auth_type,
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
        auth_type=account.auth_type,
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
        auth_type=account.auth_type,
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
    pool: ClientPool = Depends(get_client_pool),
):
    try:
        account = await service.get_account(account_id)
    except AccountNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))

    auth_token = decrypt_token(account.auth_token)
    client = pool.get(account_id)

    headers = {"anthropic-version": "2023-06-01"}
    if auth_token.startswith("sk-ant-"):
        headers["x-api-key"] = auth_token
    else:
        headers["authorization"] = f"Bearer {auth_token}"

    start = time.monotonic()
    try:
        resp = await client.post(
            "/v1/messages",
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 1,
                "messages": [{"role": "user", "content": "hi"}],
            },
            headers=headers,
        )
        latency = int((time.monotonic() - start) * 1000)
        if resp.status_code == 200:
            return AccountTestResponse(status="ok", latency_ms=latency)
        return AccountTestResponse(
            status="error", latency_ms=latency, detail=f"HTTP {resp.status_code}"
        )
    except Exception as exc:
        return AccountTestResponse(status="error", detail=str(exc))


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
        auth_type=account.auth_type,
        status=account.status,
        rate_limit_until=account.rate_limit_until,
        max_connections=account.max_connections,
        priority=account.priority,
        created_at=account.created_at,
        last_used_at=account.last_used_at,
    )
