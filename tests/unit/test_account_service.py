"""Unit tests for AccountService — no DB needed."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.application.dto.account_dto import AccountCreateRequest, AccountUpdateRequest
from src.application.services.account_service import AccountService
from src.domain.exceptions import AccountNotFoundError
from src.domain.models.account import Account, AccountStatus, AuthType


def make_account(
    status=AccountStatus.AVAILABLE,
    name="Test Account",
    email="test@example.com",
    max_connections=10,
    priority=0,
) -> Account:
    return Account(
        id=uuid.uuid4(),
        name=name,
        email=email,
        auth_token="encrypted_token",
        auth_type=AuthType.API_KEY,
        proxy_url=None,
        status=status,
        rate_limit_until=None,
        max_connections=max_connections,
        priority=priority,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        last_used_at=None,
    )


@pytest.fixture
def mock_pool():
    pool = MagicMock()
    pool.add = AsyncMock()
    pool.refresh = AsyncMock()
    pool.remove = AsyncMock()
    return pool


async def test_list_accounts_returns_accounts_with_connection_counts(
    mock_account_repo, mock_pool, state_manager
):
    acc1 = make_account(name="Acc1")
    acc2 = make_account(name="Acc2")
    mock_account_repo.list_all = AsyncMock(return_value=[acc1, acc2])
    service = AccountService(mock_account_repo, mock_pool, state_manager)

    # Give acc1 some connections
    await state_manager.acquire(acc1.id)
    await state_manager.acquire(acc1.id)

    result = await service.list_accounts()

    assert len(result) == 2
    acc1_result = next(r for r in result if r[0] is acc1)
    acc2_result = next(r for r in result if r[0] is acc2)
    assert acc1_result[1] == 2
    assert acc2_result[1] == 0


async def test_list_accounts_returns_empty_when_no_accounts(
    mock_account_repo, mock_pool, state_manager
):
    mock_account_repo.list_all = AsyncMock(return_value=[])
    service = AccountService(mock_account_repo, mock_pool, state_manager)

    result = await service.list_accounts()
    assert result == []


async def test_get_account_returns_account(mock_account_repo, mock_pool, state_manager):
    acc = make_account()
    mock_account_repo.get_by_id = AsyncMock(return_value=acc)
    service = AccountService(mock_account_repo, mock_pool, state_manager)

    result = await service.get_account(acc.id)
    assert result is acc


async def test_get_account_raises_when_not_found(mock_account_repo, mock_pool, state_manager):
    mock_account_repo.get_by_id = AsyncMock(return_value=None)
    service = AccountService(mock_account_repo, mock_pool, state_manager)

    with pytest.raises(AccountNotFoundError):
        await service.get_account(uuid.uuid4())


async def test_create_account_returns_created_account(mock_account_repo, mock_pool, state_manager):
    created = make_account(name="New Acc")
    mock_account_repo.create = AsyncMock(return_value=created)
    service = AccountService(mock_account_repo, mock_pool, state_manager)

    req = AccountCreateRequest(
        name="New Acc",
        email="new@ex.com",
        auth_token="sk-ant-raw-token",
    )
    with patch(
        "src.application.services.account_service.encrypt_token",
        return_value="encrypted_tok",
    ):
        result = await service.create_account(req)

    assert result is created


async def test_create_account_calls_pool_add(mock_account_repo, mock_pool, state_manager):
    created = make_account()
    mock_account_repo.create = AsyncMock(return_value=created)
    service = AccountService(mock_account_repo, mock_pool, state_manager)

    req = AccountCreateRequest(name="X", email="x@x.com", auth_token="token")
    with patch("src.application.services.account_service.encrypt_token", return_value="enc"):
        await service.create_account(req)

    mock_pool.add.assert_called_once_with(created)


async def test_create_account_encrypts_auth_token(mock_account_repo, mock_pool, state_manager):
    created = make_account()
    mock_account_repo.create = AsyncMock(return_value=created)
    service = AccountService(mock_account_repo, mock_pool, state_manager)

    req = AccountCreateRequest(name="X", email="x@x.com", auth_token="raw-token")
    with patch(
        "src.application.services.account_service.encrypt_token",
        return_value="encrypted_value",
    ) as mock_enc:
        await service.create_account(req)

    mock_enc.assert_any_call("raw-token")


async def test_create_account_encrypts_proxy_url_when_present(
    mock_account_repo, mock_pool, state_manager
):
    created = make_account()
    mock_account_repo.create = AsyncMock(return_value=created)
    service = AccountService(mock_account_repo, mock_pool, state_manager)

    req = AccountCreateRequest(
        name="X", email="x@x.com", auth_token="tok", proxy_url="socks5://proxy:1080"
    )
    with patch(
        "src.application.services.account_service.encrypt_token",
        return_value="enc",
    ) as mock_enc:
        await service.create_account(req)

    # encrypt_token called for both auth_token and proxy_url
    assert mock_enc.call_count == 2
    call_args = [c[0][0] for c in mock_enc.call_args_list]
    assert "tok" in call_args
    assert "socks5://proxy:1080" in call_args


async def test_create_account_none_proxy_url_skips_encryption(
    mock_account_repo, mock_pool, state_manager
):
    created = make_account()
    mock_account_repo.create = AsyncMock(return_value=created)
    service = AccountService(mock_account_repo, mock_pool, state_manager)

    req = AccountCreateRequest(name="X", email="x@x.com", auth_token="tok", proxy_url=None)
    with patch(
        "src.application.services.account_service.encrypt_token",
        return_value="enc",
    ) as mock_enc:
        await service.create_account(req)

    # encrypt_token called only once — for auth_token
    assert mock_enc.call_count == 1


async def test_create_account_sets_available_status(mock_account_repo, mock_pool, state_manager):
    created = make_account()
    mock_account_repo.create = AsyncMock(return_value=created)
    service = AccountService(mock_account_repo, mock_pool, state_manager)

    req = AccountCreateRequest(name="X", email="x@x.com", auth_token="tok")
    with patch("src.application.services.account_service.encrypt_token", return_value="enc"):
        await service.create_account(req)

    call_arg = mock_account_repo.create.call_args[0][0]
    assert call_arg.status == AccountStatus.AVAILABLE


async def test_update_account_updates_name(mock_account_repo, mock_pool, state_manager):
    acc = make_account(name="Old Name")
    mock_account_repo.get_by_id = AsyncMock(return_value=acc)
    updated = make_account(name="New Name")
    mock_account_repo.update = AsyncMock(return_value=updated)
    service = AccountService(mock_account_repo, mock_pool, state_manager)

    req = AccountUpdateRequest(name="New Name")
    result = await service.update_account(acc.id, req)

    assert result is updated
    call_arg = mock_account_repo.update.call_args[0][0]
    assert call_arg.name == "New Name"


async def test_update_account_encrypts_new_auth_token(mock_account_repo, mock_pool, state_manager):
    acc = make_account()
    mock_account_repo.get_by_id = AsyncMock(return_value=acc)
    mock_account_repo.update = AsyncMock(return_value=acc)
    service = AccountService(mock_account_repo, mock_pool, state_manager)

    req = AccountUpdateRequest(auth_token="new-raw-token")
    with patch(
        "src.application.services.account_service.encrypt_token",
        return_value="new-enc-token",
    ) as mock_enc:
        await service.update_account(acc.id, req)

    mock_enc.assert_called_once_with("new-raw-token")


async def test_update_account_calls_pool_refresh(mock_account_repo, mock_pool, state_manager):
    acc = make_account()
    mock_account_repo.get_by_id = AsyncMock(return_value=acc)
    updated = make_account()
    mock_account_repo.update = AsyncMock(return_value=updated)
    service = AccountService(mock_account_repo, mock_pool, state_manager)

    req = AccountUpdateRequest(name="Updated")
    await service.update_account(acc.id, req)

    mock_pool.refresh.assert_called_once_with(updated)


async def test_update_account_updates_max_connections(mock_account_repo, mock_pool, state_manager):
    acc = make_account(max_connections=5)
    mock_account_repo.get_by_id = AsyncMock(return_value=acc)
    mock_account_repo.update = AsyncMock(return_value=acc)
    service = AccountService(mock_account_repo, mock_pool, state_manager)

    req = AccountUpdateRequest(max_connections=20)
    await service.update_account(acc.id, req)

    call_arg = mock_account_repo.update.call_args[0][0]
    assert call_arg.max_connections == 20


async def test_update_account_updates_priority(mock_account_repo, mock_pool, state_manager):
    acc = make_account(priority=0)
    mock_account_repo.get_by_id = AsyncMock(return_value=acc)
    mock_account_repo.update = AsyncMock(return_value=acc)
    service = AccountService(mock_account_repo, mock_pool, state_manager)

    req = AccountUpdateRequest(priority=10)
    await service.update_account(acc.id, req)

    call_arg = mock_account_repo.update.call_args[0][0]
    assert call_arg.priority == 10


async def test_update_account_updates_proxy_url(mock_account_repo, mock_pool, state_manager):
    acc = make_account()
    mock_account_repo.get_by_id = AsyncMock(return_value=acc)
    mock_account_repo.update = AsyncMock(return_value=acc)
    service = AccountService(mock_account_repo, mock_pool, state_manager)

    req = AccountUpdateRequest(proxy_url="socks5://new-proxy:1080")
    with patch(
        "src.application.services.account_service.encrypt_token",
        return_value="enc-proxy",
    ):
        await service.update_account(acc.id, req)

    call_arg = mock_account_repo.update.call_args[0][0]
    assert call_arg.proxy_url == "enc-proxy"


async def test_update_account_raises_when_not_found(mock_account_repo, mock_pool, state_manager):
    mock_account_repo.get_by_id = AsyncMock(return_value=None)
    service = AccountService(mock_account_repo, mock_pool, state_manager)

    with pytest.raises(AccountNotFoundError):
        await service.update_account(uuid.uuid4(), AccountUpdateRequest(name="X"))


async def test_update_account_updates_auth_type(mock_account_repo, mock_pool, state_manager):
    acc = make_account()
    mock_account_repo.get_by_id = AsyncMock(return_value=acc)
    mock_account_repo.update = AsyncMock(return_value=acc)
    service = AccountService(mock_account_repo, mock_pool, state_manager)

    req = AccountUpdateRequest(auth_type=AuthType.SESSION_TOKEN)
    await service.update_account(acc.id, req)

    call_arg = mock_account_repo.update.call_args[0][0]
    assert call_arg.auth_type == AuthType.SESSION_TOKEN


async def test_delete_account_calls_repo_delete(mock_account_repo, mock_pool, state_manager):
    acc = make_account()
    mock_account_repo.get_by_id = AsyncMock(return_value=acc)
    mock_account_repo.delete = AsyncMock()
    service = AccountService(mock_account_repo, mock_pool, state_manager)

    await service.delete_account(acc.id)

    mock_account_repo.delete.assert_called_once_with(acc.id)


async def test_delete_account_calls_pool_remove(mock_account_repo, mock_pool, state_manager):
    acc = make_account()
    mock_account_repo.get_by_id = AsyncMock(return_value=acc)
    mock_account_repo.delete = AsyncMock()
    service = AccountService(mock_account_repo, mock_pool, state_manager)

    await service.delete_account(acc.id)

    mock_pool.remove.assert_called_once_with(acc.id)


async def test_delete_account_raises_when_not_found(mock_account_repo, mock_pool, state_manager):
    mock_account_repo.get_by_id = AsyncMock(return_value=None)
    service = AccountService(mock_account_repo, mock_pool, state_manager)

    with pytest.raises(AccountNotFoundError):
        await service.delete_account(uuid.uuid4())


async def test_unban_account_sets_status_to_available(mock_account_repo, mock_pool, state_manager):
    acc = make_account(status=AccountStatus.BANNED)
    mock_account_repo.get_by_id = AsyncMock(return_value=acc)
    mock_account_repo.update_status = AsyncMock()
    service = AccountService(mock_account_repo, mock_pool, state_manager)

    result = await service.unban_account(acc.id)

    mock_account_repo.update_status.assert_called_once_with(acc.id, AccountStatus.AVAILABLE, None)
    assert result.status == AccountStatus.AVAILABLE


async def test_unban_account_clears_rate_limit(mock_account_repo, mock_pool, state_manager):
    acc = make_account(status=AccountStatus.RATE_LIMITED)
    mock_account_repo.get_by_id = AsyncMock(return_value=acc)
    mock_account_repo.update_status = AsyncMock()
    service = AccountService(mock_account_repo, mock_pool, state_manager)

    # Set up a rate limit in state_manager
    await state_manager.mark_rate_limited(acc.id, 120)
    assert await state_manager.is_rate_limited(acc.id)

    await service.unban_account(acc.id)

    # Should have cleared the rate limit
    assert not await state_manager.is_rate_limited(acc.id)


async def test_unban_account_raises_when_not_found(mock_account_repo, mock_pool, state_manager):
    mock_account_repo.get_by_id = AsyncMock(return_value=None)
    service = AccountService(mock_account_repo, mock_pool, state_manager)

    with pytest.raises(AccountNotFoundError):
        await service.unban_account(uuid.uuid4())


async def test_unban_account_returns_account_with_cleared_rate_limit(
    mock_account_repo, mock_pool, state_manager
):
    acc = make_account(status=AccountStatus.BANNED)
    acc.rate_limit_until = datetime.now(UTC)
    mock_account_repo.get_by_id = AsyncMock(return_value=acc)
    mock_account_repo.update_status = AsyncMock()
    service = AccountService(mock_account_repo, mock_pool, state_manager)

    result = await service.unban_account(acc.id)

    assert result.rate_limit_until is None


async def test_get_banned_accounts_returns_banned_and_rate_limited(
    mock_account_repo, mock_pool, state_manager
):
    banned = make_account(status=AccountStatus.BANNED)
    rate_limited = make_account(status=AccountStatus.RATE_LIMITED)
    available = make_account(status=AccountStatus.AVAILABLE)
    mock_account_repo.list_all = AsyncMock(return_value=[banned, rate_limited, available])
    service = AccountService(mock_account_repo, mock_pool, state_manager)

    result = await service.get_banned_accounts()

    assert banned in result
    assert rate_limited in result
    assert available not in result


async def test_get_banned_accounts_includes_in_memory_rate_limited(
    mock_account_repo, mock_pool, state_manager
):
    available_but_limited = make_account(status=AccountStatus.AVAILABLE)
    mock_account_repo.list_all = AsyncMock(return_value=[available_but_limited])
    service = AccountService(mock_account_repo, mock_pool, state_manager)

    # Mark as rate-limited in state manager (not persisted to DB)
    await state_manager.mark_rate_limited(available_but_limited.id, 60)

    result = await service.get_banned_accounts()

    assert available_but_limited in result


async def test_get_banned_accounts_excludes_available_without_rate_limit(
    mock_account_repo, mock_pool, state_manager
):
    available = make_account(status=AccountStatus.AVAILABLE)
    mock_account_repo.list_all = AsyncMock(return_value=[available])
    service = AccountService(mock_account_repo, mock_pool, state_manager)

    result = await service.get_banned_accounts()

    assert available not in result


async def test_get_banned_accounts_returns_empty_when_all_available(
    mock_account_repo, mock_pool, state_manager
):
    acc1 = make_account(status=AccountStatus.AVAILABLE)
    acc2 = make_account(status=AccountStatus.AVAILABLE)
    mock_account_repo.list_all = AsyncMock(return_value=[acc1, acc2])
    service = AccountService(mock_account_repo, mock_pool, state_manager)

    result = await service.get_banned_accounts()

    assert result == []
