"""Unit tests for LeastConnectionsStrategy — no DB, no network."""

import uuid
from datetime import UTC, datetime

import pytest

from src.application.routing.least_connections import LeastConnectionsStrategy
from src.domain.models.account import Account, AccountStatus, AuthType
from src.infrastructure.state.account_state_manager import AccountStateManager


def make_account(priority: int = 0, status: AccountStatus = AccountStatus.AVAILABLE) -> Account:
    return Account(
        id=uuid.uuid4(),
        name="acc",
        email="e@e.com",
        auth_token="tok",
        auth_type=AuthType.API_KEY,
        proxy_url=None,
        status=status,
        rate_limit_until=None,
        max_connections=10,
        priority=priority,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        last_used_at=None,
    )


@pytest.fixture
def strategy():
    return LeastConnectionsStrategy()


@pytest.fixture
def state():
    return AccountStateManager()


@pytest.mark.asyncio
async def test_returns_none_when_no_accounts(strategy, state):
    result = await strategy.select([], state)
    assert result is None


@pytest.mark.asyncio
async def test_returns_only_available_account(strategy, state):
    acc = make_account()
    result = await strategy.select([acc], state)
    assert result is acc


@pytest.mark.asyncio
async def test_skips_banned_accounts(strategy, state):
    banned = make_account(status=AccountStatus.BANNED)
    available = make_account()
    result = await strategy.select([banned, available], state)
    assert result is available


@pytest.mark.asyncio
async def test_skips_rate_limited_accounts(strategy, state):
    acc_a = make_account()
    acc_b = make_account()
    await state.mark_rate_limited(acc_a.id, retry_after=60)
    result = await strategy.select([acc_a, acc_b], state)
    assert result is acc_b


@pytest.mark.asyncio
async def test_picks_least_connections(strategy, state):
    acc_a = make_account()
    acc_b = make_account()
    # acc_a has 5 connections, acc_b has 1
    for _ in range(5):
        await state.acquire(acc_a.id)
    await state.acquire(acc_b.id)
    result = await strategy.select([acc_a, acc_b], state)
    assert result is acc_b


@pytest.mark.asyncio
async def test_priority_as_tiebreaker(strategy, state):
    low = make_account(priority=0)
    high = make_account(priority=10)
    # Both have 0 connections — high priority should win
    result = await strategy.select([low, high], state)
    assert result is high


@pytest.mark.asyncio
async def test_returns_none_when_all_banned(strategy, state):
    a = make_account(status=AccountStatus.BANNED)
    b = make_account(status=AccountStatus.RATE_LIMITED)
    result = await strategy.select([a, b], state)
    assert result is None
