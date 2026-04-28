import uuid
from uuid import UUID

from src.application.dto.user_dto import UserCreateRequest, UserUpdateRequest
from src.core.logger import logger
from src.core.security import (
    generate_api_key,
    hash_password,
    verify_api_key,
    verify_password,
)
from src.domain.exceptions import InvalidCredentialsError, UserNotFoundError
from src.domain.interfaces.user_repository import UserRepository
from src.domain.models.user import User, UserRole


class UserService:
    def __init__(self, repo: UserRepository) -> None:
        self._repo = repo

    async def authenticate(self, username: str, password: str) -> User:
        user = await self._repo.get_by_username(username)
        if not user or not verify_password(password, user.password_hash):
            raise InvalidCredentialsError("Invalid username or password")
        if not user.is_active:
            raise InvalidCredentialsError("Account is disabled")
        return user

    async def get_by_api_key(self, raw_key: str) -> User | None:
        """Find user by raw API key (ccp_...). Returns None if not found/invalid."""
        if not raw_key.startswith("ccp_"):
            return None
        prefix = raw_key[:12]
        user = await self._repo.get_by_api_key_prefix(prefix)
        if not user or not user.api_key_hash:
            return None
        if not verify_api_key(raw_key, user.api_key_hash):
            return None
        if not user.is_active:
            return None
        return user

    async def get_by_id(self, user_id: UUID) -> User:
        user = await self._repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(f"User {user_id} not found")
        return user

    async def list_users(self) -> list[User]:
        return await self._repo.list_all()

    async def create_user(self, req: UserCreateRequest) -> tuple[User, str]:
        """Returns (user, raw_api_key)."""
        raw_key, key_hash, key_prefix = generate_api_key()
        user = User(
            id=uuid.uuid4(),
            username=req.username,
            email=req.email,
            password_hash=hash_password(req.password),
            role=UserRole(req.role),
            is_active=True,
            api_key_hash=key_hash,
            api_key_prefix=key_prefix,
            created_at=None,
            updated_at=None,
        )
        user = await self._repo.create(user)
        logger.info(f"Created user {user.id} ({user.username}) role={user.role}")
        return user, raw_key

    async def update_user(self, user_id: UUID, req: UserUpdateRequest) -> User:
        user = await self.get_by_id(user_id)
        if req.email is not None:
            user.email = req.email
        if req.password is not None:
            user.password_hash = hash_password(req.password)
        if req.is_active is not None:
            user.is_active = req.is_active
        if req.role is not None:
            user.role = UserRole(req.role)
        return await self._repo.update(user)

    async def rotate_api_key(self, user_id: UUID) -> tuple[User, str]:
        """Returns (user, new_raw_api_key)."""
        user = await self.get_by_id(user_id)
        raw_key, key_hash, key_prefix = generate_api_key()
        user.api_key_hash = key_hash
        user.api_key_prefix = key_prefix
        user = await self._repo.update(user)
        logger.info(f"Rotated API key for user {user_id}")
        return user, raw_key

    async def ensure_admin_exists(self, username: str, email: str, password: str) -> None:
        count = await self._repo.count()
        if count == 0:
            req = UserCreateRequest(
                username=username,
                email=email,
                password=password,
                role=UserRole.ADMIN,
            )
            user, _ = await self.create_user(req)
            logger.info(f"Created initial admin user: {user.username}")
