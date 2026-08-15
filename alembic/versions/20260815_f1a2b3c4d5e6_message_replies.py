"""Add persisted Communicator reply context.

Revision ID: f1a2b3c4d5e6
Revises: e0f1a2b3c4d5
"""

from alembic import op
import sqlalchemy as sa


revision = "f1a2b3c4d5e6"
down_revision = "e0f1a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column("reply_to_message_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_messages_reply_to_message_id_messages",
        "messages",
        "messages",
        ["reply_to_message_id"],
        ["id"],
    )
    op.create_index(
        "ix_messages_reply_to_message_id",
        "messages",
        ["reply_to_message_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_messages_reply_to_message_id", table_name="messages")
    op.drop_constraint(
        "fk_messages_reply_to_message_id_messages",
        "messages",
        type_="foreignkey",
    )
    op.drop_column("messages", "reply_to_message_id")
