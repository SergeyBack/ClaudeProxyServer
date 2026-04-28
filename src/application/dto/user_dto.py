from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr

from src.domain.models.user import UserRole


class UserCreateRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: UserRole = UserRole.USER


class UserUpdateRequest(BaseModel):
    email: EmailStr | None = None
    password: str | None = None
    is_active: bool | None = None
    role: UserRole | None = None


class UserResponse(BaseModel):
    id: UUID
    username: str
    email: str
    role: UserRole
    is_active: bool
    api_key_prefix: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ApiKeyResponse(BaseModel):
    api_key: str  # returned only once on creation/rotation
    prefix: str
