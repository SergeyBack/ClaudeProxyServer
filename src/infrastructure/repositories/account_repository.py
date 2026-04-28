from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.account import Account, AccountStatus, AuthType
from src.infrastructure.orm.models import ClaudeAccountORM


def _orm_to_domain(row: ClaudeAccountORM) -> Account:
    return Account(
        id=row.id,
        name=row.name,
        email=row.email,
        auth_token=row.auth_token,
        auth_type=AuthType(row.auth_type),
        proxy_url=row.proxy_url,
        status=AccountStatus(row.status),
        rate_limit_until=row.rate_limit_until,
        max_connections=row.max_connections,
        priority=row.priority,
        created_at=row.created_at,
        updated_at=row.updated_at,
        last_used_at=row.last_used_at,
    )


class SqlAccountRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, account_id: UUID) -> Account | None:
        row = await self._session.get(ClaudeAccountORM, account_id)
        return _orm_to_domain(row) if row else None

    async def list_available(self) -> list[Account]:
        result = await self._session.execute(
            select(ClaudeAccountORM).where(ClaudeAccountORM.status == AccountStatus.AVAILABLE)
        )
        return [_orm_to_domain(r) for r in result.scalars().all()]

    async def list_all(self) -> list[Account]:
        result = await self._session.execute(select(ClaudeAccountORM))
        return [_orm_to_domain(r) for r in result.scalars().all()]

    async def create(self, account: Account) -> Account:
        row = ClaudeAccountORM(
            id=account.id,
            name=account.name,
            email=account.email,
            auth_token=account.auth_token,
            auth_type=account.auth_type.value,
            proxy_url=account.proxy_url,
            status=account.status.value,
            rate_limit_until=account.rate_limit_until,
            max_connections=account.max_connections,
            priority=account.priority,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return _orm_to_domain(row)

    async def update(self, account: Account) -> Account:
        row = await self._session.get(ClaudeAccountORM, account.id)
        if not row:
            raise ValueError(f"Account {account.id} not found")
        row.name = account.name
        row.email = account.email
        row.auth_token = account.auth_token
        row.auth_type = account.auth_type.value
        row.proxy_url = account.proxy_url
        row.status = account.status.value
        row.rate_limit_until = account.rate_limit_until
        row.max_connections = account.max_connections
        row.priority = account.priority
        await self._session.commit()
        await self._session.refresh(row)
        return _orm_to_domain(row)

    async def delete(self, account_id: UUID) -> None:
        row = await self._session.get(ClaudeAccountORM, account_id)
        if row:
            await self._session.delete(row)
            await self._session.commit()

    async def update_status(
        self,
        account_id: UUID,
        status: AccountStatus,
        rate_limit_until: datetime | None = None,
    ) -> None:
        await self._session.execute(
            update(ClaudeAccountORM)
            .where(ClaudeAccountORM.id == account_id)
            .values(status=status.value, rate_limit_until=rate_limit_until)
        )
        await self._session.commit()

    async def update_last_used(self, account_id: UUID) -> None:
        await self._session.execute(
            update(ClaudeAccountORM)
            .where(ClaudeAccountORM.id == account_id)
            .values(last_used_at=datetime.now(UTC))
        )
        await self._session.commit()
