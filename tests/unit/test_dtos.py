"""Unit tests for application-layer DTOs."""

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.application.dto.account_dto import (
    AccountCreateRequest,
    AccountResponse,
    AccountTestResponse,
    AccountUpdateRequest,
)
from src.application.dto.stats_dto import (
    AccountStatItem,
    ModelStat,
    ModelStatItem,
    OverviewStatsResponse,
    UserStatsResponse,
)
from src.application.dto.user_dto import (
    ApiKeyResponse,
    LoginRequest,
    TokenResponse,
    UserCreateRequest,
    UserResponse,
    UserUpdateRequest,
)
from src.domain.models.account import AccountStatus
from src.domain.models.user import UserRole


def test_account_create_defaults():
    req = AccountCreateRequest(name="Test", email="t@t.com", auth_token="tok")
    assert req.max_connections == 10
    assert req.priority == 0
    assert req.proxy_url is None


def test_account_create_all_fields():
    req = AccountCreateRequest(
        name="Prod Account",
        email="prod@example.com",
        auth_token="sk-ant-api03-secret",
        proxy_url="socks5://proxy.example.com:1080",
        max_connections=5,
        priority=10,
    )
    assert req.name == "Prod Account"
    assert req.email == "prod@example.com"
    assert req.auth_token == "sk-ant-api03-secret"
    assert req.proxy_url == "socks5://proxy.example.com:1080"
    assert req.max_connections == 5
    assert req.priority == 10


def test_account_create_invalid_email():
    with pytest.raises(ValidationError) as exc_info:
        AccountCreateRequest(name="Test", email="not-an-email", auth_token="tok")
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("email",) for e in errors)


def test_account_create_missing_required_fields():
    with pytest.raises(ValidationError):
        AccountCreateRequest(name="Test", email="t@t.com")  # missing auth_token

    with pytest.raises(ValidationError):
        AccountCreateRequest(email="t@t.com", auth_token="tok")  # missing name

    with pytest.raises(ValidationError):
        AccountCreateRequest(name="Test", auth_token="tok")  # missing email


def test_account_update_all_optional():
    req = AccountUpdateRequest()
    assert req.name is None
    assert req.auth_token is None
    assert req.proxy_url is None
    assert req.max_connections is None
    assert req.priority is None


def test_account_update_partial():
    req = AccountUpdateRequest(name="New Name", max_connections=20)
    assert req.name == "New Name"
    assert req.max_connections == 20
    assert req.auth_token is None


def test_account_update_full():
    req = AccountUpdateRequest(
        name="Updated",
        auth_token="new-token",
        proxy_url="http://proxy:8080",
        max_connections=15,
        priority=5,
    )
    assert req.name == "Updated"
    assert req.auth_token == "new-token"
    assert req.proxy_url == "http://proxy:8080"
    assert req.max_connections == 15
    assert req.priority == 5


def test_account_response_construction():
    now = datetime.now(UTC)
    resp = AccountResponse(
        id=uuid.uuid4(),
        name="Test",
        email="test@example.com",
        status=AccountStatus.AVAILABLE,
        rate_limit_until=None,
        max_connections=10,
        priority=0,
        active_connections=0,
        created_at=now,
        last_used_at=None,
    )
    assert resp.status == AccountStatus.AVAILABLE
    assert resp.active_connections == 0  # default
    assert resp.rate_limit_until is None
    assert resp.last_used_at is None


def test_account_response_with_rate_limit():
    now = datetime.now(UTC)
    resp = AccountResponse(
        id=uuid.uuid4(),
        name="Limited",
        email="l@example.com",
        status=AccountStatus.RATE_LIMITED,
        rate_limit_until=now,
        max_connections=10,
        priority=0,
        created_at=now,
        last_used_at=now,
    )
    assert resp.status == AccountStatus.RATE_LIMITED
    assert resp.rate_limit_until == now
    assert resp.last_used_at == now


def test_account_response_from_attributes():
    """model_config from_attributes allows constructing from ORM-like objects."""
    now = datetime.now(UTC)

    class FakeORM:
        id = uuid.uuid4()
        name = "ORM Account"
        email = "orm@example.com"
        status = AccountStatus.AVAILABLE
        rate_limit_until = None
        max_connections = 10
        priority = 0
        active_connections = 3
        created_at = now
        last_used_at = None

    resp = AccountResponse.model_validate(FakeORM())
    assert resp.name == "ORM Account"
    assert resp.active_connections == 3


def test_account_response_active_connections_default():
    now = datetime.now(UTC)
    resp = AccountResponse(
        id=uuid.uuid4(),
        name="T",
        email="t@t.com",
        status=AccountStatus.AVAILABLE,
        rate_limit_until=None,
        max_connections=10,
        priority=0,
        created_at=now,
        last_used_at=None,
    )
    assert resp.active_connections == 0


def test_account_test_response_success():
    resp = AccountTestResponse(status="ok", latency_ms=42)
    assert resp.status == "ok"
    assert resp.latency_ms == 42
    assert resp.detail is None


def test_account_test_response_failure():
    resp = AccountTestResponse(status="error", detail="Connection refused")
    assert resp.status == "error"
    assert resp.detail == "Connection refused"
    assert resp.latency_ms is None


def test_account_test_response_defaults():
    resp = AccountTestResponse(status="ok")
    assert resp.latency_ms is None
    assert resp.detail is None


def test_user_create_defaults():
    req = UserCreateRequest(username="alice", email="alice@example.com", password="pass123!")
    assert req.role == UserRole.USER


def test_user_create_admin_role():
    req = UserCreateRequest(
        username="bob", email="bob@example.com", password="pass123!", role=UserRole.ADMIN
    )
    assert req.role == UserRole.ADMIN


def test_user_create_invalid_email():
    with pytest.raises(ValidationError) as exc_info:
        UserCreateRequest(username="alice", email="bad-email", password="pass")
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("email",) for e in errors)


def test_user_create_missing_required():
    with pytest.raises(ValidationError):
        UserCreateRequest(email="a@a.com", password="pass")  # missing username

    with pytest.raises(ValidationError):
        UserCreateRequest(username="alice", password="pass")  # missing email

    with pytest.raises(ValidationError):
        UserCreateRequest(username="alice", email="a@a.com")  # missing password


def test_user_update_all_optional():
    req = UserUpdateRequest()
    assert req.email is None
    assert req.password is None
    assert req.is_active is None
    assert req.role is None


def test_user_update_partial():
    req = UserUpdateRequest(is_active=False)
    assert req.is_active is False
    assert req.email is None


def test_user_update_invalid_email():
    with pytest.raises(ValidationError):
        UserUpdateRequest(email="not-valid")


def test_user_update_role_change():
    req = UserUpdateRequest(role=UserRole.ADMIN)
    assert req.role == UserRole.ADMIN


def test_user_response_construction():
    now = datetime.now(UTC)
    resp = UserResponse(
        id=uuid.uuid4(),
        username="alice",
        email="alice@example.com",
        role=UserRole.USER,
        is_active=True,
        api_key_prefix="ccp_test1234",
        created_at=now,
    )
    assert resp.username == "alice"
    assert resp.is_active is True
    assert resp.api_key_prefix == "ccp_test1234"


def test_user_response_no_api_key():
    now = datetime.now(UTC)
    resp = UserResponse(
        id=uuid.uuid4(),
        username="bob",
        email="bob@example.com",
        role=UserRole.USER,
        is_active=True,
        api_key_prefix=None,
        created_at=now,
    )
    assert resp.api_key_prefix is None


def test_user_response_from_attributes():
    now = datetime.now(UTC)

    class FakeUserORM:
        id = uuid.uuid4()
        username = "charlie"
        email = "charlie@example.com"
        role = UserRole.ADMIN
        is_active = True
        api_key_prefix = "ccp_adminpfx"
        created_at = now

    resp = UserResponse.model_validate(FakeUserORM())
    assert resp.username == "charlie"
    assert resp.role == UserRole.ADMIN


def test_login_request_construction():
    req = LoginRequest(username="alice", password="secret123")
    assert req.username == "alice"
    assert req.password == "secret123"


def test_login_request_missing_fields():
    with pytest.raises(ValidationError):
        LoginRequest(username="alice")  # missing password

    with pytest.raises(ValidationError):
        LoginRequest(password="secret")  # missing username


def test_token_response_default_type():
    resp = TokenResponse(access_token="eyJ...")
    assert resp.token_type == "bearer"
    assert resp.access_token == "eyJ..."


def test_token_response_custom_type():
    resp = TokenResponse(access_token="tok", token_type="jwt")
    assert resp.token_type == "jwt"


def test_api_key_response():
    resp = ApiKeyResponse(api_key="ccp_abcdefghijklmnopqrstuvwxyz123456", prefix="ccp_abcdefgh")
    assert resp.api_key.startswith("ccp_")
    assert resp.prefix == "ccp_abcdefgh"


def test_model_stat_construction():
    stat = ModelStat(model="claude-haiku-4-5", count=100, tokens=5000)
    assert stat.model == "claude-haiku-4-5"
    assert stat.count == 100
    assert stat.tokens == 5000


def test_model_stat_missing_fields():
    with pytest.raises(ValidationError):
        ModelStat(model="claude-haiku-4-5", count=10)  # missing tokens

    with pytest.raises(ValidationError):
        ModelStat(count=10, tokens=500)  # missing model


def test_user_stats_response_construction():
    stats = UserStatsResponse(
        total_requests=200,
        total_input_tokens=10000,
        total_output_tokens=5000,
        models=[ModelStat(model="claude-haiku", count=200, tokens=15000)],
        days=30,
    )
    assert stats.total_requests == 200
    assert len(stats.models) == 1
    assert stats.models[0].model == "claude-haiku"


def test_user_stats_response_empty_models():
    stats = UserStatsResponse(
        total_requests=0,
        total_input_tokens=0,
        total_output_tokens=0,
        models=[],
        days=7,
    )
    assert stats.models == []
    assert stats.days == 7


def test_user_stats_response_multiple_models():
    stats = UserStatsResponse(
        total_requests=500,
        total_input_tokens=25000,
        total_output_tokens=12500,
        models=[
            ModelStat(model="claude-haiku", count=300, tokens=15000),
            ModelStat(model="claude-sonnet", count=200, tokens=22500),
        ],
        days=30,
    )
    assert len(stats.models) == 2


def test_overview_stats_response():
    stats = OverviewStatsResponse(
        total_requests=1000,
        active_users=25,
        total_input_tokens=50000,
        total_output_tokens=25000,
        days=7,
    )
    assert stats.active_users == 25
    assert stats.days == 7


def test_overview_stats_response_missing_fields():
    with pytest.raises(ValidationError):
        OverviewStatsResponse(total_requests=100, active_users=5)


def test_account_stat_item():
    item = AccountStatItem(
        account_id=str(uuid.uuid4()),
        count=50,
        input_tokens=2500,
        output_tokens=1250,
    )
    assert item.count == 50
    assert item.input_tokens == 2500
    assert item.output_tokens == 1250


def test_account_stat_item_zero_tokens():
    item = AccountStatItem(account_id="acc-123", count=0, input_tokens=0, output_tokens=0)
    assert item.count == 0


def test_model_stat_item():
    item = ModelStatItem(model="claude-opus", count=10, input_tokens=500, output_tokens=250)
    assert item.model == "claude-opus"
    assert item.count == 10
    assert item.input_tokens == 500
    assert item.output_tokens == 250


def test_model_stat_item_missing_field():
    with pytest.raises(ValidationError):
        ModelStatItem(model="claude-opus", count=10, input_tokens=500)  # missing output_tokens
