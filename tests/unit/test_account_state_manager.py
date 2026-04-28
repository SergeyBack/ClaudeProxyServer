"""Unit tests for AccountStateManager concurrency logic."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from src.infrastructure.state.account_state_manager import AccountStateManager


@pytest.fixture
def state():
    return AccountStateManager()


@pytest.mark.asyncio
async def test_acquire_increments(state):
    acc_id = uuid.uuid4()
    await state.acquire(acc_id)
    await state.acquire(acc_id)
    assert await state.get_connections(acc_id) == 2


@pytest.mark.asyncio
async def test_release_decrements(state):
    acc_id = uuid.uuid4()
    await state.acquire(acc_id)
    await state.acquire(acc_id)
    await state.release(acc_id)
    assert await state.get_connections(acc_id) == 1


@pytest.mark.asyncio
async def test_release_never_goes_negative(state):
    acc_id = uuid.uuid4()
    await state.release(acc_id)
    assert await state.get_connections(acc_id) == 0


@pytest.mark.asyncio
async def test_mark_rate_limited(state):
    acc_id = uuid.uuid4()
    await state.mark_rate_limited(acc_id, retry_after=60)
    assert await state.is_rate_limited(acc_id) is True


@pytest.mark.asyncio
async def test_rate_limit_expires(state):
    acc_id = uuid.uuid4()
    # Use a very short duration via restore to simulate expiry
    past = datetime.now(UTC) - timedelta(seconds=1)
    await state.restore_rate_limit(acc_id, past)
    # Should be cleared when checked
    assert await state.is_rate_limited(acc_id) is False


@pytest.mark.asyncio
async def test_clear_rate_limit(state):
    acc_id = uuid.uuid4()
    await state.mark_rate_limited(acc_id, retry_after=3600)
    await state.clear_rate_limit(acc_id)
    assert await state.is_rate_limited(acc_id) is False


@pytest.mark.asyncio
async def test_concurrent_acquire_release(state):
    acc_id = uuid.uuid4()

    async def worker():
        await state.acquire(acc_id)
        await asyncio.sleep(0)
        await state.release(acc_id)

    await asyncio.gather(*[worker() for _ in range(50)])
    assert await state.get_connections(acc_id) == 0
