from uuid import UUID

import httpx

from src.core.config import settings
from src.core.logger import logger
from src.core.security import decrypt_token
from src.domain.models.account import Account


class ClientPool:
    """
    Maintains one httpx.AsyncClient per Claude account.
    Each client is pre-configured with the account's proxy (if any).
    """

    def __init__(self) -> None:
        self._clients: dict[UUID, httpx.AsyncClient] = {}

    async def initialize(self, accounts: list[Account]) -> None:
        for account in accounts:
            await self._create_client(account)
        logger.info(f"ClientPool initialized with {len(accounts)} accounts")

    def get(self, account_id: UUID) -> httpx.AsyncClient:
        client = self._clients.get(account_id)
        if client is None:
            raise KeyError(f"No client for account {account_id}")
        return client

    async def add(self, account: Account) -> None:
        await self._create_client(account)

    async def refresh(self, account: Account) -> None:
        old = self._clients.pop(account.id, None)
        if old:
            await old.aclose()
        await self._create_client(account)
        logger.info(f"ClientPool refreshed client for account {account.id}")

    async def remove(self, account_id: UUID) -> None:
        client = self._clients.pop(account_id, None)
        if client:
            await client.aclose()

    async def close_all(self) -> None:
        for client in self._clients.values():
            await client.aclose()
        self._clients.clear()
        logger.info("ClientPool closed all clients")

    async def _create_client(self, account: Account) -> None:
        proxy_url: str | None = None
        if account.proxy_url:
            try:
                proxy_url = decrypt_token(account.proxy_url)
            except Exception:
                logger.warning(f"Failed to decrypt proxy_url for account {account.id}")

        self._clients[account.id] = httpx.AsyncClient(
            base_url=settings.ANTHROPIC_BASE_URL,
            proxy=proxy_url,
            timeout=httpx.Timeout(settings.REQUEST_TIMEOUT_SECONDS),
            headers={
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            follow_redirects=True,
        )
        logger.debug(
            f"Created httpx client for account {account.id} (proxy={'yes' if proxy_url else 'no'})"
        )
