"""Drop auth_type column

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-28 22:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("claude_accounts", "auth_type")


def downgrade() -> None:
    op.add_column(
        "claude_accounts",
        sa.Column("auth_type", sa.String(20), nullable=False, server_default="api_key"),
    )
