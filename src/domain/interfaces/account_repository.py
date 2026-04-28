from typing import Protocol
from uuid import UUID

from src.domain.models.account import Account, AccountStatus


class AccountRepository(Protocol):
    async def get_by_id(self, account_id: UUID) -> Account | None: ...

    async def list_available(self) -> list[Account]: ...

    async def list_all(self) -> list[Account]: ...

    async def create(self, account: Account) -> Account: ...

    async def update(self, account: Account) -> Account: ...

    async def delete(self, account_id: UUID) -> None: ...

    async def update_status(
        self,
        account_id: UUID,
        status: AccountStatus,
        rate_limit_until=None,
    ) -> None: ...

    async def update_last_used(self, account_id: UUID) -> None: ...
