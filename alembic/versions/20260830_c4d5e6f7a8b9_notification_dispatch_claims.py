"""add notification dispatch claims

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-08-30
"""

from alembic import op
import sqlalchemy as sa


revision = "c4d5e6f7a8b9"
down_revision = "b3c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_dispatch_claims",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("reference_id", sa.Integer(), nullable=True),
        sa.Column(
            "claimed_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index(
        op.f("ix_notification_dispatch_claims_idempotency_key"),
        "notification_dispatch_claims",
        ["idempotency_key"],
        unique=True,
    )
    op.create_index(
        op.f("ix_notification_dispatch_claims_user_id"),
        "notification_dispatch_claims",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_notification_dispatch_claims_user_id"),
        table_name="notification_dispatch_claims",
    )
    op.drop_index(
        op.f("ix_notification_dispatch_claims_idempotency_key"),
        table_name="notification_dispatch_claims",
    )
    op.drop_table("notification_dispatch_claims")
