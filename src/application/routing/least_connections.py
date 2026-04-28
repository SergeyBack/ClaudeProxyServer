from src.domain.models.account import Account, AccountStatus
from src.infrastructure.state.account_state_manager import AccountStateManager


class LeastConnectionsStrategy:
    """
    Selects the account with the fewest active connections.
    Filters out banned, rate-limited, and disabled accounts.
    Uses priority as a tiebreaker (higher = preferred).
    """

    async def select(
        self,
        accounts: list[Account],
        state: AccountStateManager,
    ) -> Account | None:
        available: list[Account] = []
        for account in accounts:
            if account.status != AccountStatus.AVAILABLE:
                continue
            if await state.is_rate_limited(account.id):
                continue
            available.append(account)

        if not available:
            return None

        # Build (connections, -priority, account) tuples and pick minimum
        scored = []
        for account in available:
            connections = await state.get_connections(account.id)
            scored.append((connections, -account.priority, account))

        scored.sort(key=lambda x: (x[0], x[1]))
        return scored[0][2]
