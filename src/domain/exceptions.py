class ProxyError(Exception):
    """Base proxy error."""


class NoAvailableAccountError(ProxyError):
    """All Claude accounts are unavailable (rate-limited, banned, or disabled)."""


class AccountBannedError(ProxyError):
    """Account has been banned by Anthropic."""

    def __init__(self, account_id: str) -> None:
        super().__init__(f"Account {account_id} is banned")
        self.account_id = account_id


class AccountRateLimitedError(ProxyError):
    """Account hit rate limit."""

    def __init__(self, account_id: str, retry_after: int) -> None:
        super().__init__(f"Account {account_id} rate limited for {retry_after}s")
        self.account_id = account_id
        self.retry_after = retry_after


class UserNotFoundError(ProxyError):
    """User not found."""


class InvalidCredentialsError(ProxyError):
    """Invalid username/password or API key."""


class AccountNotFoundError(ProxyError):
    """Claude account not found."""


class PermissionDeniedError(ProxyError):
    """Insufficient permissions."""
