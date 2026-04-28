"""Unit tests for UserService — no DB needed."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.application.dto.user_dto import UserCreateRequest, UserUpdateRequest
from src.application.services.user_service import UserService
from src.domain.exceptions import InvalidCredentialsError, UserNotFoundError
from src.domain.models.user import User, UserRole


# ── Helpers ───────────────────────────────────────────────────────────────────


def make_user(
    username="alice",
    password_hash="$2b$12$fakehash",
    is_active=True,
    role=UserRole.USER,
    api_key_hash="$2b$12$apihash",
    api_key_prefix="ccp_testtest",
) -> User:
    return User(
        id=uuid.uuid4(),
        username=username,
        email=f"{username}@example.com",
        password_hash=password_hash,
        role=role,
        is_active=is_active,
        api_key_hash=api_key_hash,
        api_key_prefix=api_key_prefix,
        created_at=None,
        updated_at=None,
    )


# ── authenticate ──────────────────────────────────────────────────────────────


async def test_authenticate_returns_user_on_valid_credentials(mock_user_repo):
    user = make_user()
    mock_user_repo.get_by_username = AsyncMock(return_value=user)
    service = UserService(mock_user_repo)

    with patch("src.application.services.user_service.verify_password", return_value=True):
        result = await service.authenticate("alice", "correct-pass")

    assert result is user


async def test_authenticate_raises_on_wrong_password(mock_user_repo):
    user = make_user()
    mock_user_repo.get_by_username = AsyncMock(return_value=user)
    service = UserService(mock_user_repo)

    with patch("src.application.services.user_service.verify_password", return_value=False):
        with pytest.raises(InvalidCredentialsError):
            await service.authenticate("alice", "wrong-pass")


async def test_authenticate_raises_when_user_not_found(mock_user_repo):
    mock_user_repo.get_by_username = AsyncMock(return_value=None)
    service = UserService(mock_user_repo)

    with pytest.raises(InvalidCredentialsError):
        await service.authenticate("unknown", "any-pass")


async def test_authenticate_raises_when_user_inactive(mock_user_repo):
    user = make_user(is_active=False)
    mock_user_repo.get_by_username = AsyncMock(return_value=user)
    service = UserService(mock_user_repo)

    with patch("src.application.services.user_service.verify_password", return_value=True):
        with pytest.raises(InvalidCredentialsError) as exc_info:
            await service.authenticate("alice", "correct-pass")
    assert "disabled" in str(exc_info.value).lower()


async def test_authenticate_raises_invalid_credentials_not_found_error(mock_user_repo):
    mock_user_repo.get_by_username = AsyncMock(return_value=None)
    service = UserService(mock_user_repo)

    with pytest.raises(InvalidCredentialsError):
        await service.authenticate("nobody", "anything")


# ── get_by_api_key ────────────────────────────────────────────────────────────


async def test_get_by_api_key_returns_none_for_wrong_prefix(mock_user_repo):
    service = UserService(mock_user_repo)
    result = await service.get_by_api_key("bad_prefix_key")
    assert result is None
    mock_user_repo.get_by_api_key_prefix.assert_not_called()


async def test_get_by_api_key_returns_none_when_user_not_found(mock_user_repo):
    mock_user_repo.get_by_api_key_prefix = AsyncMock(return_value=None)
    service = UserService(mock_user_repo)

    result = await service.get_by_api_key("ccp_testtest1234567890")
    assert result is None


async def test_get_by_api_key_returns_none_when_no_hash(mock_user_repo):
    user = make_user(api_key_hash=None)
    mock_user_repo.get_by_api_key_prefix = AsyncMock(return_value=user)
    service = UserService(mock_user_repo)

    result = await service.get_by_api_key("ccp_testtest1234567890")
    assert result is None


async def test_get_by_api_key_returns_none_on_invalid_key(mock_user_repo):
    user = make_user(api_key_hash="$2b$12$correcthash")
    mock_user_repo.get_by_api_key_prefix = AsyncMock(return_value=user)
    service = UserService(mock_user_repo)

    with patch("src.application.services.user_service.verify_api_key", return_value=False):
        result = await service.get_by_api_key("ccp_testtest_wrong_key")
    assert result is None


async def test_get_by_api_key_returns_none_when_user_inactive(mock_user_repo):
    user = make_user(is_active=False, api_key_hash="$2b$12$hash")
    mock_user_repo.get_by_api_key_prefix = AsyncMock(return_value=user)
    service = UserService(mock_user_repo)

    with patch("src.application.services.user_service.verify_api_key", return_value=True):
        result = await service.get_by_api_key("ccp_testtest_valid_key")
    assert result is None


async def test_get_by_api_key_returns_user_on_valid_key(mock_user_repo):
    user = make_user(api_key_hash="$2b$12$hash")
    mock_user_repo.get_by_api_key_prefix = AsyncMock(return_value=user)
    service = UserService(mock_user_repo)

    with patch("src.application.services.user_service.verify_api_key", return_value=True):
        result = await service.get_by_api_key("ccp_testtest_valid_key_xyz")
    assert result is user


async def test_get_by_api_key_uses_first_12_chars_as_prefix(mock_user_repo):
    mock_user_repo.get_by_api_key_prefix = AsyncMock(return_value=None)
    service = UserService(mock_user_repo)

    raw_key = "ccp_abcdefghijklmnop"
    await service.get_by_api_key(raw_key)
    mock_user_repo.get_by_api_key_prefix.assert_called_once_with("ccp_abcdefgh")


# ── get_by_id ─────────────────────────────────────────────────────────────────


async def test_get_by_id_returns_user(mock_user_repo):
    user = make_user()
    mock_user_repo.get_by_id = AsyncMock(return_value=user)
    service = UserService(mock_user_repo)

    result = await service.get_by_id(user.id)
    assert result is user


async def test_get_by_id_raises_when_not_found(mock_user_repo):
    mock_user_repo.get_by_id = AsyncMock(return_value=None)
    service = UserService(mock_user_repo)

    with pytest.raises(UserNotFoundError):
        await service.get_by_id(uuid.uuid4())


# ── list_users ────────────────────────────────────────────────────────────────


async def test_list_users_returns_all(mock_user_repo):
    users = [make_user("alice"), make_user("bob")]
    mock_user_repo.list_all = AsyncMock(return_value=users)
    service = UserService(mock_user_repo)

    result = await service.list_users()
    assert result == users


async def test_list_users_returns_empty_list(mock_user_repo):
    mock_user_repo.list_all = AsyncMock(return_value=[])
    service = UserService(mock_user_repo)

    result = await service.list_users()
    assert result == []


# ── create_user ───────────────────────────────────────────────────────────────


async def test_create_user_returns_user_and_raw_key(mock_user_repo):
    created_user = make_user()
    mock_user_repo.create = AsyncMock(return_value=created_user)
    service = UserService(mock_user_repo)

    req = UserCreateRequest(username="alice", email="alice@ex.com", password="pass123!")
    with patch(
        "src.application.services.user_service.generate_api_key",
        return_value=("ccp_rawkey", "$2b$hash", "ccp_rawkey_"),
    ):
        with patch(
            "src.application.services.user_service.hash_password",
            return_value="$2b$12$hashed",
        ):
            user, raw_key = await service.create_user(req)

    assert user is created_user
    assert raw_key == "ccp_rawkey"


async def test_create_user_calls_repo_create(mock_user_repo):
    created_user = make_user()
    mock_user_repo.create = AsyncMock(return_value=created_user)
    service = UserService(mock_user_repo)

    req = UserCreateRequest(username="bob", email="bob@ex.com", password="pass123!")
    with patch(
        "src.application.services.user_service.generate_api_key",
        return_value=("ccp_rawkey", "$2b$hash", "ccp_rawkey_"),
    ):
        with patch(
            "src.application.services.user_service.hash_password",
            return_value="$2b$12$hashed",
        ):
            await service.create_user(req)

    mock_user_repo.create.assert_called_once()


async def test_create_user_sets_role_from_request(mock_user_repo):
    created_user = make_user(role=UserRole.ADMIN)
    mock_user_repo.create = AsyncMock(return_value=created_user)
    service = UserService(mock_user_repo)

    req = UserCreateRequest(
        username="admin", email="admin@ex.com", password="pass123!", role=UserRole.ADMIN
    )
    with patch(
        "src.application.services.user_service.generate_api_key",
        return_value=("ccp_rawkey", "$2b$hash", "ccp_rawkey_"),
    ):
        with patch(
            "src.application.services.user_service.hash_password",
            return_value="$2b$12$hashed",
        ):
            user, _ = await service.create_user(req)

    # Confirm role is set on the object passed to repo
    call_arg = mock_user_repo.create.call_args[0][0]
    assert call_arg.role == UserRole.ADMIN


async def test_create_user_hashes_password(mock_user_repo):
    created_user = make_user()
    mock_user_repo.create = AsyncMock(return_value=created_user)
    service = UserService(mock_user_repo)

    req = UserCreateRequest(username="carol", email="carol@ex.com", password="secret!")
    with patch(
        "src.application.services.user_service.generate_api_key",
        return_value=("ccp_rawkey", "$2b$hash", "ccp_rawkey_"),
    ):
        with patch(
            "src.application.services.user_service.hash_password",
            return_value="$2b$12$hashed",
        ) as mock_hash:
            await service.create_user(req)

    mock_hash.assert_called_once_with("secret!")


# ── update_user ───────────────────────────────────────────────────────────────


async def test_update_user_updates_email(mock_user_repo):
    user = make_user()
    mock_user_repo.get_by_id = AsyncMock(return_value=user)
    updated_user = make_user()
    updated_user.email = "new@example.com"
    mock_user_repo.update = AsyncMock(return_value=updated_user)
    service = UserService(mock_user_repo)

    req = UserUpdateRequest(email="new@example.com")
    result = await service.update_user(user.id, req)

    assert result is updated_user
    # The user's email was modified before calling update
    call_arg = mock_user_repo.update.call_args[0][0]
    assert call_arg.email == "new@example.com"


async def test_update_user_updates_password(mock_user_repo):
    user = make_user()
    mock_user_repo.get_by_id = AsyncMock(return_value=user)
    mock_user_repo.update = AsyncMock(return_value=user)
    service = UserService(mock_user_repo)

    req = UserUpdateRequest(password="newpass123!")
    with patch(
        "src.application.services.user_service.hash_password",
        return_value="$2b$12$newhash",
    ) as mock_hash:
        await service.update_user(user.id, req)

    mock_hash.assert_called_once_with("newpass123!")
    call_arg = mock_user_repo.update.call_args[0][0]
    assert call_arg.password_hash == "$2b$12$newhash"


async def test_update_user_updates_is_active(mock_user_repo):
    user = make_user(is_active=True)
    mock_user_repo.get_by_id = AsyncMock(return_value=user)
    mock_user_repo.update = AsyncMock(return_value=user)
    service = UserService(mock_user_repo)

    req = UserUpdateRequest(is_active=False)
    await service.update_user(user.id, req)

    call_arg = mock_user_repo.update.call_args[0][0]
    assert call_arg.is_active is False


async def test_update_user_updates_role(mock_user_repo):
    user = make_user(role=UserRole.USER)
    mock_user_repo.get_by_id = AsyncMock(return_value=user)
    mock_user_repo.update = AsyncMock(return_value=user)
    service = UserService(mock_user_repo)

    req = UserUpdateRequest(role=UserRole.ADMIN)
    await service.update_user(user.id, req)

    call_arg = mock_user_repo.update.call_args[0][0]
    assert call_arg.role == UserRole.ADMIN


async def test_update_user_raises_when_not_found(mock_user_repo):
    mock_user_repo.get_by_id = AsyncMock(return_value=None)
    service = UserService(mock_user_repo)

    req = UserUpdateRequest(email="x@x.com")
    with pytest.raises(UserNotFoundError):
        await service.update_user(uuid.uuid4(), req)


async def test_update_user_with_no_fields_does_not_modify(mock_user_repo):
    user = make_user()
    original_email = user.email
    original_hash = user.password_hash
    mock_user_repo.get_by_id = AsyncMock(return_value=user)
    mock_user_repo.update = AsyncMock(return_value=user)
    service = UserService(mock_user_repo)

    req = UserUpdateRequest()  # all None
    await service.update_user(user.id, req)

    call_arg = mock_user_repo.update.call_args[0][0]
    assert call_arg.email == original_email
    assert call_arg.password_hash == original_hash


# ── rotate_api_key ────────────────────────────────────────────────────────────


async def test_rotate_api_key_returns_user_and_new_key(mock_user_repo):
    user = make_user()
    mock_user_repo.get_by_id = AsyncMock(return_value=user)
    mock_user_repo.update = AsyncMock(return_value=user)
    service = UserService(mock_user_repo)

    with patch(
        "src.application.services.user_service.generate_api_key",
        return_value=("ccp_newkey", "$2b$newhash", "ccp_newkey_p"),
    ):
        result_user, raw_key = await service.rotate_api_key(user.id)

    assert result_user is user
    assert raw_key == "ccp_newkey"


async def test_rotate_api_key_updates_hash_and_prefix(mock_user_repo):
    user = make_user()
    mock_user_repo.get_by_id = AsyncMock(return_value=user)
    mock_user_repo.update = AsyncMock(return_value=user)
    service = UserService(mock_user_repo)

    with patch(
        "src.application.services.user_service.generate_api_key",
        return_value=("ccp_newkey", "$2b$newhash", "ccp_newpfx_"),
    ):
        await service.rotate_api_key(user.id)

    call_arg = mock_user_repo.update.call_args[0][0]
    assert call_arg.api_key_hash == "$2b$newhash"
    assert call_arg.api_key_prefix == "ccp_newpfx_"


async def test_rotate_api_key_raises_when_user_not_found(mock_user_repo):
    mock_user_repo.get_by_id = AsyncMock(return_value=None)
    service = UserService(mock_user_repo)

    with pytest.raises(UserNotFoundError):
        await service.rotate_api_key(uuid.uuid4())


# ── ensure_admin_exists ───────────────────────────────────────────────────────


async def test_ensure_admin_exists_creates_when_no_users(mock_user_repo):
    mock_user_repo.count = AsyncMock(return_value=0)
    admin = make_user(username="admin", role=UserRole.ADMIN)
    mock_user_repo.create = AsyncMock(return_value=admin)
    service = UserService(mock_user_repo)

    with patch(
        "src.application.services.user_service.generate_api_key",
        return_value=("ccp_adminkey", "$2b$hash", "ccp_adminkey"),
    ):
        with patch(
            "src.application.services.user_service.hash_password",
            return_value="$2b$12$adminhash",
        ):
            await service.ensure_admin_exists("admin", "admin@ex.com", "adminpass!")

    mock_user_repo.create.assert_called_once()


async def test_ensure_admin_exists_skips_when_users_exist(mock_user_repo):
    mock_user_repo.count = AsyncMock(return_value=5)
    service = UserService(mock_user_repo)

    await service.ensure_admin_exists("admin", "admin@ex.com", "adminpass!")

    mock_user_repo.create.assert_not_called()


async def test_ensure_admin_exists_creates_admin_role(mock_user_repo):
    mock_user_repo.count = AsyncMock(return_value=0)
    admin = make_user(username="admin", role=UserRole.ADMIN)
    mock_user_repo.create = AsyncMock(return_value=admin)
    service = UserService(mock_user_repo)

    with patch(
        "src.application.services.user_service.generate_api_key",
        return_value=("ccp_adminkey", "$2b$hash", "ccp_adminkey"),
    ):
        with patch(
            "src.application.services.user_service.hash_password",
            return_value="$2b$12$adminhash",
        ):
            await service.ensure_admin_exists("admin", "admin@ex.com", "adminpass!")

    call_arg = mock_user_repo.create.call_args[0][0]
    assert call_arg.role == UserRole.ADMIN
    assert call_arg.username == "admin"
