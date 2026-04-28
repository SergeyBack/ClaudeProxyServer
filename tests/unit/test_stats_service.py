"""Unit tests for StatsService — no DB needed."""

import uuid
from unittest.mock import AsyncMock

import pytest

from src.application.services.stats_service import StatsService


async def test_get_user_stats_returns_response_object(mock_log_repo):
    user_id = uuid.uuid4()
    mock_log_repo.get_user_stats = AsyncMock(
        return_value={
            "total_requests": 100,
            "total_input_tokens": 5000,
            "total_output_tokens": 2000,
            "models": [
                {"model": "claude-haiku-4-5-20251001", "count": 80, "tokens": 4000},
                {"model": "claude-sonnet-4-5", "count": 20, "tokens": 1000},
            ],
        }
    )
    service = StatsService(mock_log_repo)

    result = await service.get_user_stats(user_id, days=30)

    assert result.total_requests == 100
    assert result.total_input_tokens == 5000
    assert result.total_output_tokens == 2000
    assert result.days == 30
    assert len(result.models) == 2


async def test_get_user_stats_model_objects_have_correct_fields(mock_log_repo):
    user_id = uuid.uuid4()
    mock_log_repo.get_user_stats = AsyncMock(
        return_value={
            "total_requests": 10,
            "total_input_tokens": 100,
            "total_output_tokens": 50,
            "models": [
                {"model": "claude-haiku-4-5-20251001", "count": 10, "tokens": 150},
            ],
        }
    )
    service = StatsService(mock_log_repo)

    result = await service.get_user_stats(user_id)

    model_stat = result.models[0]
    assert model_stat.model == "claude-haiku-4-5-20251001"
    assert model_stat.count == 10
    assert model_stat.tokens == 150


async def test_get_user_stats_uses_days_parameter(mock_log_repo):
    user_id = uuid.uuid4()
    mock_log_repo.get_user_stats = AsyncMock(
        return_value={
            "total_requests": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "models": [],
        }
    )
    service = StatsService(mock_log_repo)

    result = await service.get_user_stats(user_id, days=7)

    mock_log_repo.get_user_stats.assert_called_once_with(user_id, 7)
    assert result.days == 7


async def test_get_user_stats_default_days_is_30(mock_log_repo):
    user_id = uuid.uuid4()
    mock_log_repo.get_user_stats = AsyncMock(
        return_value={
            "total_requests": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "models": [],
        }
    )
    service = StatsService(mock_log_repo)

    result = await service.get_user_stats(user_id)

    mock_log_repo.get_user_stats.assert_called_once_with(user_id, 30)
    assert result.days == 30


async def test_get_user_stats_with_empty_models(mock_log_repo):
    user_id = uuid.uuid4()
    mock_log_repo.get_user_stats = AsyncMock(
        return_value={
            "total_requests": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "models": [],
        }
    )
    service = StatsService(mock_log_repo)

    result = await service.get_user_stats(user_id)

    assert result.models == []
    assert result.total_requests == 0


async def test_get_overview_returns_response_object(mock_log_repo):
    mock_log_repo.get_overview_stats = AsyncMock(
        return_value={
            "total_requests": 500,
            "active_users": 10,
            "total_input_tokens": 25000,
            "total_output_tokens": 12000,
        }
    )
    service = StatsService(mock_log_repo)

    result = await service.get_overview(days=1)

    assert result.total_requests == 500
    assert result.active_users == 10
    assert result.total_input_tokens == 25000
    assert result.total_output_tokens == 12000
    assert result.days == 1


async def test_get_overview_uses_days_parameter(mock_log_repo):
    mock_log_repo.get_overview_stats = AsyncMock(
        return_value={
            "total_requests": 0,
            "active_users": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
        }
    )
    service = StatsService(mock_log_repo)

    result = await service.get_overview(days=7)

    mock_log_repo.get_overview_stats.assert_called_once_with(7)
    assert result.days == 7


async def test_get_overview_default_days_is_1(mock_log_repo):
    mock_log_repo.get_overview_stats = AsyncMock(
        return_value={
            "total_requests": 0,
            "active_users": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
        }
    )
    service = StatsService(mock_log_repo)

    result = await service.get_overview()

    mock_log_repo.get_overview_stats.assert_called_once_with(1)
    assert result.days == 1


async def test_get_overview_zero_values(mock_log_repo):
    mock_log_repo.get_overview_stats = AsyncMock(
        return_value={
            "total_requests": 0,
            "active_users": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
        }
    )
    service = StatsService(mock_log_repo)

    result = await service.get_overview()

    assert result.total_requests == 0
    assert result.active_users == 0


async def test_get_account_stats_returns_list_of_items(mock_log_repo):
    account_id_1 = str(uuid.uuid4())
    account_id_2 = str(uuid.uuid4())
    mock_log_repo.get_account_stats = AsyncMock(
        return_value=[
            {
                "account_id": account_id_1,
                "count": 200,
                "input_tokens": 10000,
                "output_tokens": 5000,
            },
            {"account_id": account_id_2, "count": 100, "input_tokens": 4000, "output_tokens": 2000},
        ]
    )
    service = StatsService(mock_log_repo)

    result = await service.get_account_stats(days=30)

    assert len(result) == 2
    assert result[0].account_id == account_id_1
    assert result[0].count == 200
    assert result[0].input_tokens == 10000
    assert result[0].output_tokens == 5000


async def test_get_account_stats_uses_days_parameter(mock_log_repo):
    mock_log_repo.get_account_stats = AsyncMock(return_value=[])
    service = StatsService(mock_log_repo)

    await service.get_account_stats(days=14)

    mock_log_repo.get_account_stats.assert_called_once_with(14)


async def test_get_account_stats_default_days_is_30(mock_log_repo):
    mock_log_repo.get_account_stats = AsyncMock(return_value=[])
    service = StatsService(mock_log_repo)

    await service.get_account_stats()

    mock_log_repo.get_account_stats.assert_called_once_with(30)


async def test_get_account_stats_returns_empty_list(mock_log_repo):
    mock_log_repo.get_account_stats = AsyncMock(return_value=[])
    service = StatsService(mock_log_repo)

    result = await service.get_account_stats()

    assert result == []


async def test_get_model_stats_returns_list_of_items(mock_log_repo):
    mock_log_repo.get_model_stats = AsyncMock(
        return_value=[
            {
                "model": "claude-haiku-4-5-20251001",
                "count": 300,
                "input_tokens": 15000,
                "output_tokens": 7000,
            },
            {
                "model": "claude-sonnet-4-5",
                "count": 50,
                "input_tokens": 3000,
                "output_tokens": 1500,
            },
        ]
    )
    service = StatsService(mock_log_repo)

    result = await service.get_model_stats(days=30)

    assert len(result) == 2
    assert result[0].model == "claude-haiku-4-5-20251001"
    assert result[0].count == 300
    assert result[0].input_tokens == 15000
    assert result[0].output_tokens == 7000


async def test_get_model_stats_uses_days_parameter(mock_log_repo):
    mock_log_repo.get_model_stats = AsyncMock(return_value=[])
    service = StatsService(mock_log_repo)

    await service.get_model_stats(days=90)

    mock_log_repo.get_model_stats.assert_called_once_with(90)


async def test_get_model_stats_default_days_is_30(mock_log_repo):
    mock_log_repo.get_model_stats = AsyncMock(return_value=[])
    service = StatsService(mock_log_repo)

    await service.get_model_stats()

    mock_log_repo.get_model_stats.assert_called_once_with(30)


async def test_get_model_stats_returns_empty_list(mock_log_repo):
    mock_log_repo.get_model_stats = AsyncMock(return_value=[])
    service = StatsService(mock_log_repo)

    result = await service.get_model_stats()

    assert result == []


async def test_get_model_stats_multiple_models(mock_log_repo):
    mock_log_repo.get_model_stats = AsyncMock(
        return_value=[
            {"model": "model-a", "count": 1, "input_tokens": 10, "output_tokens": 5},
            {"model": "model-b", "count": 2, "input_tokens": 20, "output_tokens": 10},
            {"model": "model-c", "count": 3, "input_tokens": 30, "output_tokens": 15},
        ]
    )
    service = StatsService(mock_log_repo)

    result = await service.get_model_stats()

    assert len(result) == 3
    models = [r.model for r in result]
    assert "model-a" in models
    assert "model-b" in models
    assert "model-c" in models
