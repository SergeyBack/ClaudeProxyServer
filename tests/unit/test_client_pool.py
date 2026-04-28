"""Unit tests for ClientPool — mocks httpx.AsyncClient, no network needed."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.models.account import Account, AccountStatus, AuthType
from src.infrastructure.http.client_pool import ClientPool


def make_account(proxy_url: str | None = None, account_id: uuid.UUID | None = None) -> Account:
    return Account(
        id=account_id or uuid.uuid4(),
        name="Test Account",
        email="test@example.com",
        auth_token="encrypted_token_placeholder",
        auth_type=AuthType.API_KEY,
        proxy_url=proxy_url,
        status=AccountStatus.AVAILABLE,
        rate_limit_until=None,
        max_connections=10,
        priority=0,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        last_used_at=None,
    )


def make_mock_client() -> MagicMock:
    """Create a mock httpx.AsyncClient with async aclose."""
    client = MagicMock()
    client.aclose = AsyncMock()
    return client


@pytest.mark.asyncio
async def test_add_stores_client():
    pool = ClientPool()
    account = make_account()
    mock_client = make_mock_client()

    with patch("httpx.AsyncClient", return_value=mock_client):
        await pool.add(account)

    assert pool.get(account.id) is mock_client


@pytest.mark.asyncio
async def test_get_returns_correct_client():
    pool = ClientPool()
    acc1 = make_account()
    acc2 = make_account()
    mock1 = make_mock_client()
    mock2 = make_mock_client()

    with patch("httpx.AsyncClient", side_effect=[mock1, mock2]):
        await pool.add(acc1)
        await pool.add(acc2)

    assert pool.get(acc1.id) is mock1
    assert pool.get(acc2.id) is mock2


@pytest.mark.asyncio
async def test_get_raises_key_error_for_unknown_id():
    pool = ClientPool()
    unknown_id = uuid.uuid4()
    with pytest.raises(KeyError):
        pool.get(unknown_id)


@pytest.mark.asyncio
async def test_get_raises_key_error_after_remove():
    pool = ClientPool()
    account = make_account()
    mock_client = make_mock_client()

    with patch("httpx.AsyncClient", return_value=mock_client):
        await pool.add(account)

    await pool.remove(account.id)

    with pytest.raises(KeyError):
        pool.get(account.id)


@pytest.mark.asyncio
async def test_remove_closes_client():
    pool = ClientPool()
    account = make_account()
    mock_client = make_mock_client()

    with patch("httpx.AsyncClient", return_value=mock_client):
        await pool.add(account)

    await pool.remove(account.id)

    mock_client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_remove_nonexistent_id_does_not_raise():
    """Removing an ID that was never added should silently do nothing."""
    pool = ClientPool()
    await pool.remove(uuid.uuid4())  # should not raise


@pytest.mark.asyncio
async def test_remove_only_removes_target():
    pool = ClientPool()
    acc1 = make_account()
    acc2 = make_account()
    mock1 = make_mock_client()
    mock2 = make_mock_client()

    with patch("httpx.AsyncClient", side_effect=[mock1, mock2]):
        await pool.add(acc1)
        await pool.add(acc2)

    await pool.remove(acc1.id)

    # acc2 should still be accessible
    assert pool.get(acc2.id) is mock2
    # acc1 should be gone
    with pytest.raises(KeyError):
        pool.get(acc1.id)


@pytest.mark.asyncio
async def test_close_all_closes_every_client():
    pool = ClientPool()
    accounts = [make_account() for _ in range(3)]
    mocks = [make_mock_client() for _ in range(3)]

    with patch("httpx.AsyncClient", side_effect=mocks):
        for account in accounts:
            await pool.add(account)

    await pool.close_all()

    for mock in mocks:
        mock.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_close_all_clears_pool():
    pool = ClientPool()
    account = make_account()
    mock_client = make_mock_client()

    with patch("httpx.AsyncClient", return_value=mock_client):
        await pool.add(account)

    await pool.close_all()

    with pytest.raises(KeyError):
        pool.get(account.id)


@pytest.mark.asyncio
async def test_close_all_empty_pool_does_not_raise():
    pool = ClientPool()
    await pool.close_all()  # should not raise


@pytest.mark.asyncio
async def test_refresh_closes_old_client():
    pool = ClientPool()
    account = make_account()
    old_mock = make_mock_client()
    new_mock = make_mock_client()

    with patch("httpx.AsyncClient", side_effect=[old_mock, new_mock]):
        await pool.add(account)
        await pool.refresh(account)

    old_mock.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_refresh_creates_new_client():
    pool = ClientPool()
    account = make_account()
    old_mock = make_mock_client()
    new_mock = make_mock_client()

    with patch("httpx.AsyncClient", side_effect=[old_mock, new_mock]):
        await pool.add(account)
        await pool.refresh(account)

    assert pool.get(account.id) is new_mock


@pytest.mark.asyncio
async def test_refresh_replaces_old_with_new():
    pool = ClientPool()
    account = make_account()
    old_mock = make_mock_client()
    new_mock = make_mock_client()

    with patch("httpx.AsyncClient", side_effect=[old_mock, new_mock]):
        await pool.add(account)
        first_client = pool.get(account.id)
        assert first_client is old_mock

        await pool.refresh(account)
        second_client = pool.get(account.id)
        assert second_client is new_mock
        assert second_client is not first_client


@pytest.mark.asyncio
async def test_refresh_account_not_previously_added():
    """refresh() on unknown account should just create a new client."""
    pool = ClientPool()
    account = make_account()
    mock_client = make_mock_client()

    with patch("httpx.AsyncClient", return_value=mock_client):
        await pool.refresh(account)

    assert pool.get(account.id) is mock_client


@pytest.mark.asyncio
async def test_initialize_adds_all_accounts():
    pool = ClientPool()
    accounts = [make_account() for _ in range(4)]
    mocks = [make_mock_client() for _ in range(4)]

    with patch("httpx.AsyncClient", side_effect=mocks):
        await pool.initialize(accounts)

    for i, account in enumerate(accounts):
        assert pool.get(account.id) is mocks[i]


@pytest.mark.asyncio
async def test_initialize_empty_list():
    pool = ClientPool()
    await pool.initialize([])  # should not raise


@pytest.mark.asyncio
async def test_initialize_single_account():
    pool = ClientPool()
    account = make_account()
    mock_client = make_mock_client()

    with patch("httpx.AsyncClient", return_value=mock_client):
        await pool.initialize([account])

    assert pool.get(account.id) is mock_client


@pytest.mark.asyncio
async def test_add_account_with_proxy_url_decrypts_and_passes_proxy():
    """When account.proxy_url is set, _create_client decrypts it and passes to httpx."""
    from src.core.security import encrypt_token

    pool = ClientPool()
    proxy_plaintext = "socks5://proxy.example.com:1080"
    encrypted_proxy = encrypt_token(proxy_plaintext)
    account = make_account(proxy_url=encrypted_proxy)
    mock_client = make_mock_client()

    with patch("httpx.AsyncClient", return_value=mock_client) as mock_constructor:
        await pool.add(account)

    # httpx.AsyncClient should have been called with proxy= set
    call_kwargs = mock_constructor.call_args.kwargs
    assert call_kwargs.get("proxy") == proxy_plaintext


@pytest.mark.asyncio
async def test_add_account_without_proxy_url():
    """When account.proxy_url is None, httpx.AsyncClient is called with proxy=None."""
    pool = ClientPool()
    account = make_account(proxy_url=None)
    mock_client = make_mock_client()

    with patch("httpx.AsyncClient", return_value=mock_client) as mock_constructor:
        await pool.add(account)

    call_kwargs = mock_constructor.call_args.kwargs
    assert call_kwargs.get("proxy") is None


@pytest.mark.asyncio
async def test_add_account_with_invalid_encrypted_proxy_falls_back_to_none():
    """Corrupted proxy_url should log a warning and create client without proxy."""
    pool = ClientPool()
    account = make_account(proxy_url="this-is-not-valid-base64-encrypted-data!!!")
    mock_client = make_mock_client()

    with patch("httpx.AsyncClient", return_value=mock_client) as mock_constructor:
        await pool.add(account)  # should not raise

    call_kwargs = mock_constructor.call_args.kwargs
    assert call_kwargs.get("proxy") is None
