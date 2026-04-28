from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.routing.least_connections import LeastConnectionsStrategy
from src.application.services.account_service import AccountService
from src.application.services.probe_service import ProbeService
from src.application.services.proxy_service import ProxyService
from src.application.services.stats_service import StatsService
from src.application.services.user_service import UserService
from src.core.database import get_db
from src.core.security import decode_access_token
from src.domain.interfaces.account_state_manager import IAccountStateManager
from src.domain.models.user import User, UserRole
from src.infrastructure.http.client_pool import ClientPool
from src.infrastructure.repositories.account_repository import SqlAccountRepository
from src.infrastructure.repositories.log_repository import SqlLogRepository
from src.infrastructure.repositories.user_repository import SqlUserRepository

bearer_scheme = HTTPBearer(auto_error=False)


def get_state_manager(request: Request) -> IAccountStateManager:
    return request.app.state.state_manager


def get_client_pool(request: Request) -> ClientPool:
    return request.app.state.client_pool


async def get_session(session: AsyncSession = Depends(get_db)) -> AsyncSession:
    return session


def get_user_service(session: AsyncSession = Depends(get_session)) -> UserService:
    return UserService(repo=SqlUserRepository(session))


def get_account_service(
    session: AsyncSession = Depends(get_session),
    pool: ClientPool = Depends(get_client_pool),
    state: IAccountStateManager = Depends(get_state_manager),
) -> AccountService:
    return AccountService(
        repo=SqlAccountRepository(session),
        pool=pool,
        state=state,
    )


def get_stats_service(session: AsyncSession = Depends(get_session)) -> StatsService:
    return StatsService(log_repo=SqlLogRepository(session))


def get_proxy_service(
    session: AsyncSession = Depends(get_session),
    pool: ClientPool = Depends(get_client_pool),
    state: IAccountStateManager = Depends(get_state_manager),
) -> ProxyService:
    return ProxyService(
        account_repo=SqlAccountRepository(session),
        log_repo=SqlLogRepository(session),
        state=state,
        pool=pool,
        router=LeastConnectionsStrategy(),
    )


def get_probe_service(
    session: AsyncSession = Depends(get_session),
    pool: ClientPool = Depends(get_client_pool),
) -> ProbeService:
    return ProbeService(
        account_repo=SqlAccountRepository(session),
        client_pool=pool,
    )


async def get_current_user_jwt(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    if not credentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    user_id = decode_access_token(credentials.credentials)
    if not user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    repo = SqlUserRepository(session)
    user = await repo.get_by_id(user_id)  # type: ignore[arg-type]
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user


async def get_current_admin(
    user: User = Depends(get_current_user_jwt),
) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    return user


async def get_current_user_from_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    user_service: UserService = Depends(get_user_service),
) -> User:
    if not credentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "API key required")
    user = await user_service.get_by_api_key(credentials.credentials)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API key")
    return user
