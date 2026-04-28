"""
Shared fixtures for all test layers.

Unit tests:     no DB — use mock repos injected directly
Integration:    real test DB via TEST_DATABASE_URL env var
E2E:            running stack at PROXY_URL env var
"""

import json
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from src.domain.models.account import Account, AccountStatus, AuthType
from src.domain.models.user import User, UserRole
from src.infrastructure.state.account_state_manager import AccountStateManager


@pytest.fixture
def sample_account() -> Account:
    return Account(
        id=uuid.uuid4(),
        name="Test Account",
        email="test@example.com",
        auth_token="encrypted_token",
        auth_type=AuthType.API_KEY,
        proxy_url=None,
        status=AccountStatus.AVAILABLE,
        rate_limit_until=None,
        max_connections=10,
        priority=0,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        last_used_at=None,
    )


@pytest.fixture
def sample_user() -> User:
    return User(
        id=uuid.uuid4(),
        username="testuser",
        email="testuser@example.com",
        password_hash="$2b$12$fakehash",
        role=UserRole.USER,
        is_active=True,
        api_key_hash=None,
        api_key_prefix="ccp_testtest",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def admin_user() -> User:
    return User(
        id=uuid.uuid4(),
        username="admin",
        email="admin@example.com",
        password_hash="$2b$12$fakehash",
        role=UserRole.ADMIN,
        is_active=True,
        api_key_hash=None,
        api_key_prefix="ccp_admintest",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def state_manager() -> AccountStateManager:
    return AccountStateManager()


@pytest.fixture
def mock_account_repo():
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_user_repo():
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_log_repo():
    repo = AsyncMock()
    return repo


def make_anthropic_response(
    content: str = "Hello!", model: str = "claude-3-haiku-20240307"
) -> dict:
    return {
        "id": f"msg_{uuid.uuid4().hex[:24]}",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": content}],
        "model": model,
        "stop_reason": "end_turn",
        "usage": {
            "input_tokens": 10,
            "output_tokens": 5,
        },
    }


def make_sse_stream(content: str = "Hello!") -> bytes:
    """Build a minimal SSE stream similar to Anthropic's streaming response."""
    events = [
        {
            "type": "message_start",
            "message": {
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "usage": {"input_tokens": 10},
            },
        },
        {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": content},
        },
        {"type": "content_block_stop", "index": 0},
        {
            "type": "message_delta",
            "delta": {"stop_reason": "end_turn"},
            "usage": {"output_tokens": 5},
        },
        {"type": "message_stop"},
    ]
    lines = []
    for event in events:
        lines.append(f"event: {event['type']}\ndata: {json.dumps(event)}\n")
    lines.append("data: [DONE]\n")
    return "\n".join(lines).encode()
