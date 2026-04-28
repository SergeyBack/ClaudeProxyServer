from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr

from src.domain.models.account import AccountStatus, AuthType


class AccountCreateRequest(BaseModel):
    name: str
    email: EmailStr
    auth_token: str  # raw token — will be encrypted
    auth_type: AuthType = AuthType.API_KEY
    proxy_url: str | None = None
    max_connections: int = 10
    priority: int = 0


class AccountUpdateRequest(BaseModel):
    name: str | None = None
    auth_token: str | None = None
    auth_type: AuthType | None = None
    proxy_url: str | None = None
    max_connections: int | None = None
    priority: int | None = None


class AccountResponse(BaseModel):
    id: UUID
    name: str
    email: str
    auth_type: AuthType
    status: AccountStatus
    rate_limit_until: datetime | None
    max_connections: int
    priority: int
    active_connections: int = 0
    created_at: datetime
    last_used_at: datetime | None

    model_config = {"from_attributes": True}


class AccountTestResponse(BaseModel):
    status: str
    latency_ms: int | None = None
    detail: str | None = None
