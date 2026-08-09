"""Conversation/message persistence: inbound ingestion, sender-to-user
matching, and the Telegram account-linking token lifecycle.

Routers (webhook handlers, admin endpoints) stay thin and call into this
module; this module owns the DB writes. Outbound transport lives in
app/services/messaging.py; this module never makes an HTTP call itself
except to send a linking confirmation, which goes through messaging.py too.
"""
from __future__ import annotations

import secrets
from datetime import timedelta
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.services import messaging
from app.utils.time import utc_now

TELEGRAM_LINK_TOKEN_TTL_MINUTES = 15


def _match_user_id(db: Session, *, channel: str, external_id: str) -> Optional[int]:
    if channel == "telegram":
        user = db.query(models.User).filter(models.User.telegram_chat_id == external_id).first()
        return user.id if user else None

    if channel == "whatsapp":
        user = (
            db.query(models.User)
            .filter(or_(models.User.phone == external_id, models.User.phone_alt == external_id))
            .first()
        )
        if user:
            return user.id
        # ParentProfile.phone can drift from User.phone - PATCH
        # /parents/{user_id}/profile-details only ever writes ParentProfile.phone,
        # never syncs User.phone. Check both so a parent who updated their number
        # post-signup still gets matched to their account.
        profile = db.query(models.ParentProfile).filter(models.ParentProfile.phone == external_id).first()
        if profile:
            return profile.user_id

    return None


def find_or_create_conversation(db: Session, *, channel: str, external_id: str) -> models.Conversation:
    conversation = (
        db.query(models.Conversation)
        .filter(models.Conversation.channel == channel, models.Conversation.external_id == external_id)
        .first()
    )
    if conversation:
        return conversation

    conversation = models.Conversation(
        channel=channel,
        external_id=external_id,
        user_id=_match_user_id(db, channel=channel, external_id=external_id),
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def _record_inbound_message(
    db: Session,
    conversation: models.Conversation,
    *,
    body: str,
    external_message_id: Optional[str],
) -> models.Message:
    if external_message_id:
        existing = (
            db.query(models.Message)
            .filter(
                models.Message.channel == conversation.channel,
                models.Message.external_message_id == external_message_id,
            )
            .first()
        )
        if existing:
            # Webhook retry (Twilio/Telegram both retry aggressively on non-2xx) -
            # already recorded, don't double-count unread or duplicate the row.
            return existing

    message = models.Message(
        conversation_id=conversation.id,
        direction="inbound",
        channel=conversation.channel,
        body=body,
        status="received",
        external_message_id=external_message_id,
    )
    db.add(message)

    now = utc_now()
    conversation.last_inbound_at = now
    conversation.last_message_at = now
    conversation.unread_count = (conversation.unread_count or 0) + 1

    db.commit()
    db.refresh(message)
    return message


def ingest_inbound_whatsapp(db: Session, *, from_phone: str, body: str, message_sid: Optional[str]) -> models.Message:
    conversation = find_or_create_conversation(db, channel="whatsapp", external_id=from_phone)
    return _record_inbound_message(db, conversation, body=body, external_message_id=message_sid)


def ingest_inbound_telegram(
    db: Session, *, chat_id: str, text: str, message_id: Optional[str]
) -> Optional[models.Message]:
    text = (text or "").strip()
    if text.startswith("/start"):
        parts = text.split(maxsplit=1)
        token = parts[1].strip() if len(parts) > 1 else ""
        _ok, reply = consume_telegram_link_token(db, token=token, chat_id=chat_id)
        messaging.send_telegram_message(chat_id, reply)
        # Linking plumbing, not a conversation the admin needs to read - the
        # token itself is a single-use credential, don't persist it verbatim.
        return None

    conversation = find_or_create_conversation(db, channel="telegram", external_id=chat_id)
    return _record_inbound_message(db, conversation, body=text, external_message_id=message_id)


def create_telegram_link_token(db: Session, user: models.User) -> models.TelegramLinkToken:
    token = models.TelegramLinkToken(
        user_id=user.id,
        token=secrets.token_urlsafe(24),
        expires_at=utc_now() + timedelta(minutes=TELEGRAM_LINK_TOKEN_TTL_MINUTES),
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    return token


def consume_telegram_link_token(db: Session, *, token: str, chat_id: str) -> tuple[bool, str]:
    row = db.query(models.TelegramLinkToken).filter(models.TelegramLinkToken.token == token).first()
    if not row:
        return False, "That link isn't valid. Please generate a new one from your My Nanny profile."
    if row.consumed_at is not None:
        return False, "That link has already been used. Please generate a new one from your My Nanny profile."
    if row.expires_at < utc_now():
        return False, "That link has expired. Please generate a new one from your My Nanny profile."

    user = db.query(models.User).filter(models.User.id == row.user_id).first()
    if not user:
        return False, "We couldn't find your My Nanny account. Please try again from the app."

    existing = (
        db.query(models.User)
        .filter(models.User.telegram_chat_id == chat_id, models.User.id != user.id)
        .first()
    )
    if existing:
        return False, "This Telegram account is already linked to a different My Nanny account."

    user.telegram_chat_id = chat_id
    row.consumed_at = utc_now()
    row.consumed_chat_id = chat_id
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return False, "This Telegram account is already linked to a different My Nanny account."

    return True, "Your Telegram is now connected to My Nanny. You'll receive messages here."
