from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI

from src.application.services.probe_service import ProbeService
from src.application.services.user_service import UserService
from src.core.config import settings
from src.core.database import AsyncSessionLocal, engine
from src.core.logger import logger, setup_logging
from src.domain.models.account import AccountStatus
from src.infrastructure.http.client_pool import ClientPool
from src.infrastructure.repositories.account_repository import SqlAccountRepository
from src.infrastructure.repositories.user_repository import SqlUserRepository
from src.infrastructure.state.redis_account_state_manager import RedisAccountStateManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("Starting Claude Proxy Server")

    # Init singletons
    redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=False)
    state_manager = RedisAccountStateManager(redis_client)
    client_pool = ClientPool()

    app.state.state_manager = state_manager
    app.state.client_pool = client_pool

    # Load accounts and initialize pool
    async with AsyncSessionLocal() as session:
        account_repo = SqlAccountRepository(session)
        accounts = await account_repo.list_all()

        active = [a for a in accounts if a.status != AccountStatus.DISABLED]
        await client_pool.initialize(active)

        # Restore persisted rate-limit state
        for account in active:
            if account.status == AccountStatus.RATE_LIMITED and account.rate_limit_until:
                await state_manager.restore_rate_limit(account.id, account.rate_limit_until)

        # Create first admin if no users exist
        user_repo = SqlUserRepository(session)
        user_service = UserService(repo=user_repo)
        await user_service.ensure_admin_exists(
            username=settings.FIRST_ADMIN_USERNAME,
            email=settings.FIRST_ADMIN_EMAIL,
            password=settings.FIRST_ADMIN_PASSWORD,
        )

    logger.info(f"Initialized {len(active)} Claude accounts")

    # Synthetic probe scheduler
    scheduler = AsyncIOScheduler(timezone="UTC")

    async def _run_probes() -> None:
        async with AsyncSessionLocal() as session:
            account_repo = SqlAccountRepository(session)
            accounts = await account_repo.list_all()
            probe_svc = ProbeService(account_repo, client_pool, state_manager)
            for acc in [a for a in accounts if a.status != AccountStatus.DISABLED]:
                result = await probe_svc.probe_account(acc)
                logger.info(f"[probe] {acc.name}: {result}")

    scheduler.add_job(_run_probes, "interval", minutes=5, id="account_probe")
    scheduler.start()
    logger.info("Probe scheduler started")

    yield

    scheduler.shutdown(wait=False)

    # Shutdown
    logger.info("Shutting down Claude Proxy Server")
    await client_pool.close_all()
    await redis_client.aclose()
    await engine.dispose()
