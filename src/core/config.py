from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:changeme@localhost:5432/claude_proxy"

    # Security
    SECRET_KEY: str = "change-me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # First admin (created on first boot)
    FIRST_ADMIN_USERNAME: str = "admin"
    FIRST_ADMIN_EMAIL: str = "admin@example.com"
    FIRST_ADMIN_PASSWORD: str = "changeme123!"

    # Anthropic upstream
    ANTHROPIC_BASE_URL: str = "https://api.anthropic.com"

    # Proxy behavior
    REQUEST_TIMEOUT_SECONDS: float = 300.0
    MAX_PROMPT_LOG_CHARS: int = 50_000
    ENABLE_PROMPT_LOGGING: bool = True

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Logging
    LOG_LEVEL: str = "INFO"


settings = Settings()
