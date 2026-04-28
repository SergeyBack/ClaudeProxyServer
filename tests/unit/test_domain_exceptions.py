"""Unit tests for domain exceptions."""

import pytest

from src.domain.exceptions import (
    AccountBannedError,
    AccountNotFoundError,
    AccountRateLimitedError,
    InvalidCredentialsError,
    NoAvailableAccountError,
    PermissionDeniedError,
    ProxyError,
    UserNotFoundError,
)

# ── ProxyError base class ─────────────────────────────────────────────────────


def test_proxy_error_is_exception():
    err = ProxyError("base error")
    assert isinstance(err, Exception)
    assert str(err) == "base error"


def test_proxy_error_can_be_raised_and_caught():
    with pytest.raises(ProxyError):
        raise ProxyError("test")


# ── NoAvailableAccountError ───────────────────────────────────────────────────


def test_no_available_account_error_is_proxy_error():
    err = NoAvailableAccountError("no accounts")
    assert isinstance(err, ProxyError)
    assert str(err) == "no accounts"


def test_no_available_account_error_can_be_raised():
    with pytest.raises(NoAvailableAccountError):
        raise NoAvailableAccountError("all accounts busy")


def test_no_available_account_error_caught_as_proxy_error():
    with pytest.raises(ProxyError):
        raise NoAvailableAccountError("all accounts busy")


# ── AccountBannedError ────────────────────────────────────────────────────────


def test_account_banned_error_stores_account_id():
    err = AccountBannedError("acc-123")
    assert err.account_id == "acc-123"


def test_account_banned_error_message_contains_id():
    err = AccountBannedError("acc-456")
    assert "acc-456" in str(err)


def test_account_banned_error_is_proxy_error():
    err = AccountBannedError("acc-789")
    assert isinstance(err, ProxyError)


def test_account_banned_error_can_be_raised():
    with pytest.raises(AccountBannedError) as exc_info:
        raise AccountBannedError("my-account")
    assert exc_info.value.account_id == "my-account"


def test_account_banned_error_caught_as_proxy_error():
    with pytest.raises(ProxyError):
        raise AccountBannedError("some-id")


def test_account_banned_error_message_format():
    err = AccountBannedError("uuid-001")
    assert "banned" in str(err).lower()
    assert "uuid-001" in str(err)


# ── AccountRateLimitedError ───────────────────────────────────────────────────


def test_account_rate_limited_error_stores_account_id():
    err = AccountRateLimitedError("acc-123", 60)
    assert err.account_id == "acc-123"


def test_account_rate_limited_error_stores_retry_after():
    err = AccountRateLimitedError("acc-123", 120)
    assert err.retry_after == 120


def test_account_rate_limited_error_message_contains_id_and_seconds():
    err = AccountRateLimitedError("acc-99", 30)
    msg = str(err)
    assert "acc-99" in msg
    assert "30" in msg


def test_account_rate_limited_error_is_proxy_error():
    err = AccountRateLimitedError("acc-123", 60)
    assert isinstance(err, ProxyError)


def test_account_rate_limited_error_can_be_raised():
    with pytest.raises(AccountRateLimitedError) as exc_info:
        raise AccountRateLimitedError("acc-x", 45)
    assert exc_info.value.retry_after == 45


def test_account_rate_limited_error_caught_as_proxy_error():
    with pytest.raises(ProxyError):
        raise AccountRateLimitedError("acc-x", 60)


def test_account_rate_limited_error_zero_retry():
    err = AccountRateLimitedError("acc-0", 0)
    assert err.retry_after == 0


# ── UserNotFoundError ─────────────────────────────────────────────────────────


def test_user_not_found_error_is_proxy_error():
    err = UserNotFoundError("User X not found")
    assert isinstance(err, ProxyError)
    assert str(err) == "User X not found"


def test_user_not_found_error_can_be_raised():
    with pytest.raises(UserNotFoundError):
        raise UserNotFoundError("not found")


# ── InvalidCredentialsError ───────────────────────────────────────────────────


def test_invalid_credentials_error_is_proxy_error():
    err = InvalidCredentialsError("bad creds")
    assert isinstance(err, ProxyError)


def test_invalid_credentials_error_can_be_raised():
    with pytest.raises(InvalidCredentialsError):
        raise InvalidCredentialsError("wrong password")


def test_invalid_credentials_error_caught_as_proxy_error():
    with pytest.raises(ProxyError):
        raise InvalidCredentialsError("wrong")


# ── AccountNotFoundError ──────────────────────────────────────────────────────


def test_account_not_found_error_is_proxy_error():
    err = AccountNotFoundError("Account X not found")
    assert isinstance(err, ProxyError)


def test_account_not_found_error_can_be_raised():
    with pytest.raises(AccountNotFoundError):
        raise AccountNotFoundError("no account")


# ── PermissionDeniedError ─────────────────────────────────────────────────────


def test_permission_denied_error_is_proxy_error():
    err = PermissionDeniedError("forbidden")
    assert isinstance(err, ProxyError)


def test_permission_denied_error_can_be_raised():
    with pytest.raises(PermissionDeniedError):
        raise PermissionDeniedError("not allowed")


def test_permission_denied_error_caught_as_proxy_error():
    with pytest.raises(ProxyError):
        raise PermissionDeniedError("denied")


# ── Exception hierarchy ───────────────────────────────────────────────────────


def test_all_errors_are_subclasses_of_proxy_error():
    errors = [
        NoAvailableAccountError("x"),
        AccountBannedError("x"),
        AccountRateLimitedError("x", 1),
        UserNotFoundError("x"),
        InvalidCredentialsError("x"),
        AccountNotFoundError("x"),
        PermissionDeniedError("x"),
    ]
    for err in errors:
        assert isinstance(err, ProxyError), f"{type(err)} should be a ProxyError"


def test_all_errors_are_exceptions():
    errors = [
        ProxyError("x"),
        NoAvailableAccountError("x"),
        AccountBannedError("x"),
        AccountRateLimitedError("x", 1),
        UserNotFoundError("x"),
        InvalidCredentialsError("x"),
        AccountNotFoundError("x"),
        PermissionDeniedError("x"),
    ]
    for err in errors:
        assert isinstance(err, Exception), f"{type(err)} should be an Exception"
