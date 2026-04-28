from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.user import User, UserRole
from src.infrastructure.orm.models import UserORM


def _orm_to_domain(row: UserORM) -> User:
    return User(
        id=row.id,
        username=row.username,
        email=row.email,
        password_hash=row.password_hash,
        role=UserRole(row.role),
        is_active=row.is_active,
        api_key_hash=row.api_key_hash,
        api_key_prefix=row.api_key_prefix,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        row = await self._session.get(UserORM, user_id)
        return _orm_to_domain(row) if row else None

    async def get_by_username(self, username: str) -> User | None:
        result = await self._session.execute(select(UserORM).where(UserORM.username == username))
        row = result.scalar_one_or_none()
        return _orm_to_domain(row) if row else None

    async def get_by_api_key_prefix(self, prefix: str) -> User | None:
        result = await self._session.execute(
            select(UserORM).where(UserORM.api_key_prefix == prefix)
        )
        row = result.scalar_one_or_none()
        return _orm_to_domain(row) if row else None

    async def list_all(self) -> list[User]:
        result = await self._session.execute(select(UserORM))
        return [_orm_to_domain(r) for r in result.scalars().all()]

    async def create(self, user: User) -> User:
        row = UserORM(
            id=user.id,
            username=user.username,
            email=user.email,
            password_hash=user.password_hash,
            role=user.role.value,
            is_active=user.is_active,
            api_key_hash=user.api_key_hash,
            api_key_prefix=user.api_key_prefix,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return _orm_to_domain(row)

    async def update(self, user: User) -> User:
        row = await self._session.get(UserORM, user.id)
        if not row:
            raise ValueError(f"User {user.id} not found")
        row.username = user.username
        row.email = user.email
        row.password_hash = user.password_hash
        row.role = user.role.value
        row.is_active = user.is_active
        row.api_key_hash = user.api_key_hash
        row.api_key_prefix = user.api_key_prefix
        await self._session.commit()
        await self._session.refresh(row)
        return _orm_to_domain(row)

    async def count(self) -> int:
        result = await self._session.execute(select(func.count(UserORM.id)))
        return result.scalar_one()
