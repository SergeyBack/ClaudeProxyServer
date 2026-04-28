from typing import Protocol

from src.domain.models.account import Account
from src.infrastructure.state.account_state_manager import AccountStateManager


class RoutingStrategy(Protocol):
    async def select(
        self,
        accounts: list[Account],
        state: AccountStateManager,
    ) -> Account | None: ...
