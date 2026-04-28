import json
import time

import httpx
from fastapi import Request
from fastapi.responses import Response, StreamingResponse

from src.application.routing.strategy import RoutingStrategy
from src.core.config import settings
from src.core.logger import logger
from src.core.security import decrypt_token
from src.domain.exceptions import (
    AccountBannedError,
    AccountRateLimitedError,
    NoAvailableAccountError,
)
from src.domain.interfaces.account_repository import AccountRepository
from src.domain.interfaces.account_state_manager import IAccountStateManager
from src.domain.interfaces.log_repository import LogRepository
from src.domain.models.account import Account, AccountStatus
from src.domain.models.request_log import RequestLog
from src.domain.models.user import User
from src.infrastructure.http.client_pool import ClientPool
from src.infrastructure.metrics import (
    proxy_active_connections,
    proxy_tokens_input,
    proxy_tokens_output,
)

# Headers to strip from incoming requests before forwarding
_STRIP_HEADERS = frozenset(
    {
        "host",
        "content-length",
        "transfer-encoding",
        "connection",
        "x-forwarded-for",
        "x-real-ip",
        "x-request-id",
    }
)


class ProxyService:
    def __init__(
        self,
        account_repo: AccountRepository,
        log_repo: LogRepository,
        state: IAccountStateManager,
        pool: ClientPool,
        router: RoutingStrategy,
    ) -> None:
        self._account_repo = account_repo
        self._log_repo = log_repo
        self._state = state
        self._pool = pool
        self._router = router

    async def proxy_request(self, user: User, request: Request) -> Response:
        body_bytes = await request.body()
        try:
            payload = json.loads(body_bytes)
        except json.JSONDecodeError:
            payload = {}

        model = payload.get("model", "unknown")
        is_streaming = payload.get("stream", False)
        request_id = request.headers.get("x-request-id", _make_request_id())

        accounts = await self._account_repo.list_available()
        account = await self._router.select(accounts, self._state)
        if not account:
            raise NoAvailableAccountError("No Claude accounts available")

        await self._state.acquire(account.id)
        proxy_active_connections.labels(account_id=str(account.id)).inc()
        start_ms = time.monotonic()
        log = RequestLog(
            user_id=user.id,
            account_id=account.id,
            request_id=request_id,
            model=model,
            status_code=0,
            duration_ms=0,
            is_streaming=is_streaming,
        )

        if settings.ENABLE_PROMPT_LOGGING:
            messages = payload.get("messages", [])
            content = json.dumps(messages)
            if len(content) > settings.MAX_PROMPT_LOG_CHARS:
                content = content[: settings.MAX_PROMPT_LOG_CHARS] + "...[truncated]"
            log.prompt_content = {"messages": messages, "system": payload.get("system")}

        auth_token = decrypt_token(account.auth_token)
        client = self._pool.get(account.id)
        upstream_headers = _build_upstream_headers(request, auth_token)

        if is_streaming:
            # For streaming, lifecycle (release/log) is managed inside the generator
            # because StreamingResponse body executes after this function returns.
            return await self._stream_response(
                client, upstream_headers, payload, account, log, start_ms
            )

        try:
            return await self._sync_response(
                client, upstream_headers, payload, account, log, start_ms
            )
        except httpx.HTTPStatusError as exc:
            log.status_code = exc.response.status_code
            log.error_type = "http_error"
            await self._handle_upstream_error(exc, account)
            raise
        except Exception as exc:
            log.status_code = 500
            log.error_type = type(exc).__name__
            raise
        finally:
            await self._state.release(account.id)
            proxy_active_connections.labels(account_id=str(account.id)).dec()
            log.duration_ms = int((time.monotonic() - start_ms) * 1000)
            if log.status_code == 0:
                log.status_code = 200
            try:
                await self._log_repo.create(log)
                await self._account_repo.update_last_used(account.id)
            except Exception as exc:
                logger.error(f"Failed to write request log: {exc}")

    async def _sync_response(
        self,
        client: httpx.AsyncClient,
        headers: dict,
        payload: dict,
        account: Account,
        log: RequestLog,
        start_ms: float,
    ) -> Response:
        resp = await client.post("/v1/messages", json=payload, headers=headers)
        self._parse_rate_limit_headers(resp.headers, account)

        if resp.status_code == 429:
            retry_after = int(resp.headers.get("retry-after", "60"))
            await self._state.mark_rate_limited(account.id, retry_after)
            await self._account_repo.update_status(account.id, AccountStatus.RATE_LIMITED, None)

        resp.raise_for_status()

        body = resp.json()
        log.status_code = resp.status_code
        usage = body.get("usage", {})
        log.input_tokens = usage.get("input_tokens")
        log.output_tokens = usage.get("output_tokens")
        log.cache_read_tokens = usage.get("cache_read_input_tokens")
        log.cache_write_tokens = usage.get("cache_creation_input_tokens")
        if log.input_tokens:
            proxy_tokens_input.labels(account_id=str(account.id)).inc(log.input_tokens)
        if log.output_tokens:
            proxy_tokens_output.labels(account_id=str(account.id)).inc(log.output_tokens)
        if settings.ENABLE_PROMPT_LOGGING:
            log.response_content = body

        return Response(
            content=resp.content,
            status_code=resp.status_code,
            media_type="application/json",
            headers={"x-request-id": log.request_id},
        )

    async def _stream_response(
        self,
        client: httpx.AsyncClient,
        headers: dict,
        payload: dict,
        account: Account,
        log: RequestLog,
        start_ms: float,
    ) -> StreamingResponse:
        async def event_generator():
            try:
                async with client.stream(
                    "POST", "/v1/messages", json=payload, headers=headers
                ) as resp:
                    self._parse_rate_limit_headers(resp.headers, account)

                    if resp.status_code == 429:
                        retry_after = int(resp.headers.get("retry-after", "60"))
                        await self._state.mark_rate_limited(account.id, retry_after)
                        await self._account_repo.update_status(
                            account.id, AccountStatus.RATE_LIMITED, None
                        )

                    log.status_code = resp.status_code
                    buffer = b""

                    async for chunk in resp.aiter_bytes():
                        buffer += chunk
                        yield chunk

                    # Parse token usage from accumulated SSE
                    _extract_usage_from_sse(buffer, log)
                    if log.input_tokens:
                        proxy_tokens_input.labels(account_id=str(account.id)).inc(log.input_tokens)
                    if log.output_tokens:
                        proxy_tokens_output.labels(account_id=str(account.id)).inc(
                            log.output_tokens
                        )

            except Exception as exc:
                log.error_type = type(exc).__name__
                logger.error(f"Stream error for account {account.id}: {exc}")
                raise
            finally:
                await self._state.release(account.id)
                proxy_active_connections.labels(account_id=str(account.id)).dec()
                log.duration_ms = int((time.monotonic() - start_ms) * 1000)
                if log.status_code == 0:
                    log.status_code = 200
                try:
                    await self._log_repo.create(log)
                    await self._account_repo.update_last_used(account.id)
                except Exception as exc:
                    logger.error(f"Failed to write stream log: {exc}")

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "cache-control": "no-cache",
                "x-accel-buffering": "no",
                "x-request-id": log.request_id,
            },
        )

    def _parse_rate_limit_headers(self, headers: httpx.Headers, account: Account) -> None:
        remaining = headers.get("anthropic-ratelimit-requests-remaining")
        if remaining is not None and int(remaining) == 0:
            logger.warning(f"Account {account.id} hit request rate limit")

    async def _handle_upstream_error(self, exc: httpx.HTTPStatusError, account: Account) -> None:
        status = exc.response.status_code
        if status in (401, 403):
            logger.error(f"Account {account.id} appears banned (HTTP {status})")
            await self._account_repo.update_status(account.id, AccountStatus.BANNED)
            raise AccountBannedError(str(account.id))
        if status == 429:
            retry_after = int(exc.response.headers.get("retry-after", "60"))
            logger.warning(f"Account {account.id} rate limited for {retry_after}s")
            raise AccountRateLimitedError(str(account.id), retry_after)


def _make_request_id() -> str:
    import secrets

    return secrets.token_hex(16)


def _build_upstream_headers(request: Request, auth_token: str) -> dict:
    headers = {}
    for key, value in request.headers.items():
        if key.lower() in _STRIP_HEADERS:
            continue
        # Strip incoming auth — will be replaced with the account's credentials
        if key.lower() in ("authorization", "x-api-key"):
            continue
        headers[key] = value

    headers["x-api-key"] = auth_token
    return headers


def _extract_usage_from_sse(data: bytes, log: RequestLog) -> None:
    """Parse SSE stream to extract token usage from message_delta events."""
    try:
        text = data.decode("utf-8", errors="ignore")
        for line in text.split("\n"):
            if line.startswith("data: "):
                payload_str = line[6:]
                if payload_str.strip() == "[DONE]":
                    continue
                try:
                    event = json.loads(payload_str)
                    usage = event.get("usage") or event.get("message", {}).get("usage", {})
                    if usage:
                        log.input_tokens = usage.get("input_tokens", log.input_tokens)
                        log.output_tokens = usage.get("output_tokens", log.output_tokens)
                        log.cache_read_tokens = usage.get(
                            "cache_read_input_tokens", log.cache_read_tokens
                        )
                        log.cache_write_tokens = usage.get(
                            "cache_creation_input_tokens", log.cache_write_tokens
                        )
                except json.JSONDecodeError:
                    pass
    except Exception:
        pass
