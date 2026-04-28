import uuid
from uuid import UUID

from src.application.dto.account_dto import AccountCreateRequest, AccountUpdateRequest
from src.core.logger import logger
from src.core.security import encrypt_token
from src.domain.exceptions import AccountNotFoundError
from src.domain.interfaces.account_repository import AccountRepository
from src.domain.interfaces.account_state_manager import IAccountStateManager
from src.domain.models.account import Account, AccountStatus, AuthType
from src.infrastructure.http.client_pool import ClientPool


class AccountService:
    def __init__(
        self,
        repo: AccountRepository,
        pool: ClientPool,
        state: IAccountStateManager,
    ) -> None:
        self._repo = repo
        self._pool = pool
        self._state = state

    async def list_accounts(self) -> list[tuple[Account, int]]:
        """Return accounts with live connection count."""
        accounts = await self._repo.list_all()
        result = []
        for account in accounts:
            connections = await self._state.get_connections(account.id)
            result.append((account, connections))
        return result

    async def get_account(self, account_id: UUID) -> Account:
        account = await self._repo.get_by_id(account_id)
        if not account:
            raise AccountNotFoundError(f"Account {account_id} not found")
        return account

    async def create_account(self, req: AccountCreateRequest) -> Account:
        encrypted_token = encrypt_token(req.auth_token)
        encrypted_proxy = encrypt_token(req.proxy_url) if req.proxy_url else None

        account = Account(
            id=uuid.uuid4(),
            name=req.name,
            email=req.email,
            auth_token=encrypted_token,
            auth_type=AuthType(req.auth_type),
            proxy_url=encrypted_proxy,
            status=AccountStatus.AVAILABLE,
            rate_limit_until=None,
            max_connections=req.max_connections,
            priority=req.priority,
            created_at=None,  # set by DB
            updated_at=None,
            last_used_at=None,
        )
        account = await self._repo.create(account)
        await self._pool.add(account)
        logger.info(f"Created account {account.id} ({account.name})")
        return account

    async def update_account(self, account_id: UUID, req: AccountUpdateRequest) -> Account:
        account = await self.get_account(account_id)

        if req.name is not None:
            account.name = req.name
        if req.auth_token is not None:
            account.auth_token = encrypt_token(req.auth_token)
        if req.auth_type is not None:
            account.auth_type = AuthType(req.auth_type)
        if req.proxy_url is not None:
            account.proxy_url = encrypt_token(req.proxy_url)
        if req.max_connections is not None:
            account.max_connections = req.max_connections
        if req.priority is not None:
            account.priority = req.priority

        account = await self._repo.update(account)
        await self._pool.refresh(account)
        return account

    async def delete_account(self, account_id: UUID) -> None:
        await self.get_account(account_id)
        await self._repo.delete(account_id)
        await self._pool.remove(account_id)
        logger.info(f"Deleted account {account_id}")

    async def unban_account(self, account_id: UUID) -> Account:
        account = await self.get_account(account_id)
        await self._repo.update_status(account_id, AccountStatus.AVAILABLE, None)
        await self._state.clear_rate_limit(account_id)
        account.status = AccountStatus.AVAILABLE
        account.rate_limit_until = None
        logger.info(f"Unbanned account {account_id}")
        return account

    async def get_banned_accounts(self) -> list[Account]:
        accounts = await self._repo.list_all()
        banned = [
            a for a in accounts if a.status in (AccountStatus.BANNED, AccountStatus.RATE_LIMITED)
        ]
        # Also check in-memory rate limits
        still_limited = []
        for a in accounts:
            if a.status == AccountStatus.AVAILABLE and await self._state.is_rate_limited(a.id):
                still_limited.append(a)
        return banned + still_limited
