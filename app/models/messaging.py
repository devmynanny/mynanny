from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import validates
from sqlalchemy.sql import func

from app.db import Base
from app.services.messaging_status import (
    CONVERSATION_CHANNELS,
    MESSAGE_DIRECTIONS,
    MESSAGE_STATUSES,
)


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True)
    channel = Column(String, nullable=False)
    # Phone number (no "whatsapp:" prefix) for whatsapp, chat_id for telegram.
    external_id = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    last_message_at = Column(DateTime, nullable=True)
    last_inbound_at = Column(DateTime, nullable=True)
    last_outbound_at = Column(DateTime, nullable=True)
    unread_count = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    @validates("channel")
    def _validate_channel(self, key, value):
        if value not in CONVERSATION_CHANNELS:
            raise ValueError(f"Invalid conversation channel {value!r}; allowed: {sorted(CONVERSATION_CHANNELS)}")
        return value

    __table_args__ = (
        UniqueConstraint("channel", "external_id", name="uq_conversation_channel_external_id"),
        Index("ix_conversations_user_id", "user_id"),
        Index("ix_conversations_last_message_at", "last_message_at"),
    )


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    direction = Column(String, nullable=False)
    channel = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="received")
    # Twilio message SID / Telegram message_id - dedupe key for webhook retries.
    external_message_id = Column(String, nullable=True)
    sender_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())

    @validates("direction")
    def _validate_direction(self, key, value):
        if value not in MESSAGE_DIRECTIONS:
            raise ValueError(f"Invalid message direction {value!r}; allowed: {sorted(MESSAGE_DIRECTIONS)}")
        return value

    @validates("channel")
    def _validate_channel(self, key, value):
        if value not in CONVERSATION_CHANNELS:
            raise ValueError(f"Invalid message channel {value!r}; allowed: {sorted(CONVERSATION_CHANNELS)}")
        return value

    @validates("status")
    def _validate_status(self, key, value):
        if value is not None and value not in MESSAGE_STATUSES:
            raise ValueError(f"Invalid message status {value!r}; allowed: {sorted(MESSAGE_STATUSES)}")
        return value

    __table_args__ = (
        UniqueConstraint("channel", "external_message_id", name="uq_message_channel_external_id"),
        Index("ix_messages_conversation_id_created_at", "conversation_id", "created_at"),
    )


class TelegramLinkToken(Base):
    __tablename__ = "telegram_link_tokens"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token = Column(String, nullable=False, unique=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    expires_at = Column(DateTime, nullable=False)
    consumed_at = Column(DateTime, nullable=True)
    consumed_chat_id = Column(String, nullable=True)

    __table_args__ = (
        Index("ix_telegram_link_tokens_user_id", "user_id"),
    )
