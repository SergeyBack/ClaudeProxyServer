from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class UserRole(StrEnum):
    ADMIN = "admin"
    USER = "user"


@dataclass
class User:
    id: UUID
    username: str
    email: str
    password_hash: str
    role: UserRole
    is_active: bool
    api_key_hash: str | None
    api_key_prefix: str | None
    created_at: datetime
    updated_at: datetime

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN
