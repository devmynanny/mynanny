"""Track provider message IDs for asynchronous delivery callbacks.

Revision ID: a2b3c4d5e6f7
Revises: f1a2b3c4d5e6
"""

from alembic import op
import sqlalchemy as sa


revision = "a2b3c4d5e6f7"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "notification_log",
        sa.Column("provider_message_id", sa.String(), nullable=True),
    )
    op.create_index(
        "ix_notification_log_provider_message_id",
        "notification_log",
        ["provider_message_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_notification_log_provider_message_id", table_name="notification_log")
    op.drop_column("notification_log", "provider_message_id")
