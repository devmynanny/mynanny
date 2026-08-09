"""Add conversations/messages/telegram_link_tokens + user messaging channel preference

Revision ID: d3e4f5a6b7c8
Revises: c7d8e9f0a1b2
Create Date: 2026-08-08

Backs the admin WhatsApp/Telegram conversations screen: a channel-agnostic
Conversation/Message pair (one Conversation per (channel, external_id), so a
user can have up to one per channel and history survives a channel switch),
plus a per-user preferred_messaging_channel and telegram_chat_id/link-token
flow for account linking.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d3e4f5a6b7c8"
down_revision: Union[str, None] = "c7d8e9f0a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("preferred_messaging_channel", sa.String(), nullable=False, server_default="whatsapp"))
    op.add_column("users", sa.Column("telegram_chat_id", sa.String(), nullable=True))
    op.create_unique_constraint("uq_users_telegram_chat_id", "users", ["telegram_chat_id"])

    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column("external_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("last_message_at", sa.DateTime(), nullable=True),
        sa.Column("last_inbound_at", sa.DateTime(), nullable=True),
        sa.Column("last_outbound_at", sa.DateTime(), nullable=True),
        sa.Column("unread_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("channel", "external_id", name="uq_conversation_channel_external_id"),
    )
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])
    op.create_index("ix_conversations_last_message_at", "conversations", ["last_message_at"])

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("direction", sa.String(), nullable=False),
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="received"),
        sa.Column("external_message_id", sa.String(), nullable=True),
        sa.Column("sender_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("channel", "external_message_id", name="uq_message_channel_external_id"),
    )
    op.create_index("ix_messages_conversation_id_created_at", "messages", ["conversation_id", "created_at"])

    op.create_table(
        "telegram_link_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token", sa.String(), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.Column("consumed_chat_id", sa.String(), nullable=True),
    )
    op.create_index("ix_telegram_link_tokens_user_id", "telegram_link_tokens", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_telegram_link_tokens_user_id", table_name="telegram_link_tokens")
    op.drop_table("telegram_link_tokens")

    op.drop_index("ix_messages_conversation_id_created_at", table_name="messages")
    op.drop_table("messages")

    op.drop_index("ix_conversations_last_message_at", table_name="conversations")
    op.drop_index("ix_conversations_user_id", table_name="conversations")
    op.drop_table("conversations")

    op.drop_constraint("uq_users_telegram_chat_id", "users", type_="unique")
    op.drop_column("users", "telegram_chat_id")
    op.drop_column("users", "preferred_messaging_channel")
