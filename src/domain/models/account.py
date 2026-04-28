from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class AccountStatus(StrEnum):
    AVAILABLE = "available"
    RATE_LIMITED = "rate_limited"
    BANNED = "banned"
    DISABLED = "disabled"


@dataclass
class Account:
    id: UUID
    name: str
    email: str
    auth_token: str  # AES-GCM encrypted sk-ant-api03- key
    proxy_url: str | None  # AES-GCM encrypted, or None
    status: AccountStatus
    rate_limit_until: datetime | None
    max_connections: int
    priority: int
    created_at: datetime
    updated_at: datetime
    last_used_at: datetime | None

    @property
    def is_available(self) -> bool:
        return self.status == AccountStatus.AVAILABLE
