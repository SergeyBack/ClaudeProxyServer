"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2025-01-01 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("username", sa.String(100), unique=True, nullable=False),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("api_key_hash", sa.String(255), unique=True),
        sa.Column("api_key_prefix", sa.String(12)),
        sa.Column("role", sa.String(20), nullable=False, server_default="user"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("idx_users_api_key_prefix", "users", ["api_key_prefix"])

    op.create_table(
        "claude_accounts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("auth_token", sa.Text, nullable=False),
        sa.Column("auth_type", sa.String(20), nullable=False, server_default="api_key"),
        sa.Column("proxy_url", sa.Text),
        sa.Column("status", sa.String(20), nullable=False, server_default="available"),
        sa.Column("rate_limit_until", sa.DateTime(timezone=True)),
        sa.Column("max_connections", sa.Integer, nullable=False, server_default="10"),
        sa.Column("priority", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(255), unique=True, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("idx_refresh_tokens_user_id", "refresh_tokens", ["user_id"])

    op.create_table(
        "request_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column(
            "account_id",
            UUID(as_uuid=True),
            sa.ForeignKey("claude_accounts.id", ondelete="SET NULL"),
        ),
        sa.Column("request_id", sa.String(64), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("input_tokens", sa.Integer),
        sa.Column("output_tokens", sa.Integer),
        sa.Column("cache_read_tokens", sa.Integer),
        sa.Column("cache_write_tokens", sa.Integer),
        sa.Column("prompt_content", JSONB),
        sa.Column("response_content", JSONB),
        sa.Column("status_code", sa.SmallInteger, nullable=False),
        sa.Column("error_type", sa.String(100)),
        sa.Column("duration_ms", sa.Integer, nullable=False),
        sa.Column("is_streaming", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("idx_request_logs_user_id", "request_logs", ["user_id"])
    op.create_index("idx_request_logs_account_id", "request_logs", ["account_id"])
    op.create_index(
        "idx_request_logs_created_at",
        "request_logs",
        ["created_at"],
        postgresql_ops={"created_at": "DESC"},
    )
    op.create_index("idx_request_logs_model", "request_logs", ["model"])

    op.create_table(
        "admin_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("actor_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("entity_id", UUID(as_uuid=True)),
        sa.Column("payload", JSONB),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("idx_admin_events_created_at", "admin_events", ["created_at"])


def downgrade() -> None:
    op.drop_table("admin_events")
    op.drop_table("request_logs")
    op.drop_table("refresh_tokens")
    op.drop_table("claude_accounts")
    op.drop_table("users")
