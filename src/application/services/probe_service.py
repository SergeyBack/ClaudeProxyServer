from __future__ import annotations

import time
from typing import TYPE_CHECKING

from src.domain.models.account import Account

if TYPE_CHECKING:
    from src.infrastructure.http.client_pool import ClientPool
    from src.infrastructure.repositories.account_repository import SqlAccountRepository


class ProbeService:
    def __init__(
        self,
        account_repo: SqlAccountRepository,
        client_pool: ClientPool,
    ) -> None:
        self._repo = account_repo
        self._pool = client_pool

    async def probe_account(self, account: Account) -> dict:
        """Fire minimal request; return status dict."""
        from src.core.security import decrypt_token

        start = time.monotonic()
        try:
            token = decrypt_token(account.auth_token)
            client = self._pool.get(account.id)

            headers: dict[str, str] = {"anthropic-version": "2023-06-01"}
            if account.auth_type == "api_key":
                headers["x-api-key"] = token
            else:
                headers["authorization"] = f"Bearer {token}"

            resp = await client.post(
                "/v1/messages",
                headers=headers,
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 1,
                    "messages": [{"role": "user", "content": "hi"}],
                },
                timeout=15.0,
            )
            latency_ms = int((time.monotonic() - start) * 1000)
            if resp.status_code == 200:
                return {"status": "ok", "latency_ms": latency_ms}
            elif resp.status_code == 429:
                return {"status": "rate_limited", "latency_ms": latency_ms}
            elif resp.status_code in (401, 403):
                return {"status": "banned", "latency_ms": latency_ms}
            else:
                return {
                    "status": "error",
                    "latency_ms": latency_ms,
                    "detail": f"HTTP {resp.status_code}",
                }
        except Exception as exc:
            latency_ms = int((time.monotonic() - start) * 1000)
            return {"status": "error", "latency_ms": latency_ms, "detail": str(exc)}
