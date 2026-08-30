from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app import models
from app.utils.time import utc_now
from app.utils.email import EmailMessage, get_email_client
from app.services import messaging
from app.services.notification_controls import load_notification_controls
from app.services.notification_dispatch import claim_notification_dispatch
from app.services.whatsapp_templates import WHATSAPP_UTILITY_TEMPLATES

WHATSAPP_TEMPLATE_NAMES = set(WHATSAPP_UTILITY_TEMPLATES)

# ---------------------------------------------------------------------------
# Notification policy matrix (single source of truth).
#
# channels are tried in order until one succeeds (fallback chain).
# "in_app" entries are ALWAYS written in addition (they are pop-ups for
# action-required confirmations, not a delivery fallback).
# Default for unlisted event types: ("chat", "email").
# ---------------------------------------------------------------------------
NOTIFICATION_POLICY: dict[str, dict] = {
    # Payments - critical, user must know immediately.
    "payment_success": {"channels": ("chat", "email")},
    "payment_failed": {"channels": ("chat", "email"), "in_app": True},
    "refund_processed": {"channels": ("chat", "email"), "in_app": True},
    "charge_query_refund_approved": {"channels": ("chat", "email"), "in_app": True},
    "charge_query_opened": {"channels": ("chat", "email"), "in_app": True},
    "charge_query_denied": {"channels": ("chat", "email"), "in_app": True},
    "charge_query_failed": {"channels": ("chat", "email"), "in_app": True},
    # Booking lifecycle.
    "booking_confirmed": {"channels": ("chat", "email"), "in_app": True},
    "booking_cancelled": {"channels": ("chat", "email"), "in_app": True},
    "notification_system_test": {"channels": ("chat", "email"), "in_app": True},
    "nanny_no_show_parent_notice": {"channels": ("chat", "email"), "in_app": True},
    "parent_no_show_nanny_notice": {"channels": ("chat", "email"), "in_app": True},
    "nanny_accepted": {"channels": ("chat", "email")},
    "nanny_checked_in": {"channels": ("chat", "email")},
    "booking_start_reminder": {"channels": ("chat", "email"), "in_app": True},
    "missed_check_in": {"channels": ("chat", "email"), "in_app": True},
    "nanny_late_alert": {"channels": ("chat", "email"), "in_app": True},
    "checkout_reminder": {"channels": ("chat", "email"), "in_app": True},
    "check_in_confirmation_required": {"channels": ("chat", "email"), "in_app": True},
    "check_out_confirmation_required": {"channels": ("chat", "email"), "in_app": True},
    "service_fee_adjusted": {"channels": ("chat", "email"), "in_app": True},
    "service_refund_requested": {"channels": ("chat", "email"), "in_app": True},
    "service_time_corrected": {"channels": ("chat", "email"), "in_app": True},
    "service_time_disputed": {"channels": ("chat", "email"), "in_app": True},
    "duty_attention_required": {"channels": ("email",), "in_app": True},
    # Action required - in-app pop-up mandatory.
    "overtime_request": {"channels": ("chat", "email"), "in_app": True},
    "review_request": {"channels": ("chat", "email"), "in_app": True},
    # Request lifecycle - parent must act or know quickly.
    "new_booking_request": {"channels": ("chat", "email")},
    "nanny_declined": {"channels": ("chat", "email")},
    "no_nanny_yet": {"channels": ("chat", "email"), "in_app": True},
    "request_expired": {"channels": ("chat", "email"), "in_app": True},
    "deciding_reminder": {"channels": ("chat", "email")},
    "broadcast_position_filled": {"channels": ("chat", "email"), "in_app": True},
    "broadcast_filled": {"channels": ("chat", "email"), "in_app": True},
    "broadcast_closed_nanny": {"channels": ("chat", "email"), "in_app": True},
    # Payment retry flow.
    "payment_pending": {"channels": ("chat", "email")},
    "booking_cancelled_nanny": {"channels": ("chat", "email"), "in_app": True},
    # Payouts.
    "payout_pending": {"channels": ("chat", "email")},
    "payout_sent": {"channels": ("chat", "email")},
    # Account.
    "nanny_approved": {"channels": ("chat", "email")},
    "nanny_reactivated": {"channels": ("chat", "email"), "in_app": True},
    "passport_expiry_warning": {"channels": ("chat", "email"), "in_app": True},
    "passport_expired_suspension": {"channels": ("chat", "email"), "in_app": True},
    "passport_renewal_approved": {"channels": ("chat", "email"), "in_app": True},
}

DEFAULT_POLICY = {"channels": ("chat", "email"), "in_app": False}

# Retry policy for the scheduled sweep.
RETRY_MAX_ATTEMPTS = 3
RETRY_WINDOW_HOURS = 48


def _notification_log_exists(db: Session) -> bool:
    from app.db import session_table_exists
    return session_table_exists(db, "notification_log")


def _in_app_notifications_exist(db: Session) -> bool:
    from app.db import session_table_exists
    return session_table_exists(db, "in_app_notifications")


def _log_notification(
    db: Session,
    *,
    user_id: Optional[int],
    event_type: str,
    channel: str,
    status: str,
    error_message: Optional[str] = None,
    reference_id: Optional[int] = None,
    message: Optional[str] = None,
    provider_message_id: Optional[str] = None,
    destination: Optional[str] = None,
    test_redirected: bool = False,
) -> None:
    try:
        if not _notification_log_exists(db):
            return
        # A stale notification-log schema must not invalidate the caller's
        # business transaction. The savepoint contains any insert failure.
        with db.begin_nested():
            db.execute(
                text(
                    """
                    INSERT INTO notification_log (user_id, event_type, channel, status, error_message, reference_id, message, provider_message_id, destination, test_redirected, created_at)
                    VALUES (:user_id, :event_type, :channel, :status, :error_message, :reference_id, :message, :provider_message_id, :destination, :test_redirected, :created_at)
                    """
                ),
                {
                    "user_id": user_id,
                    "event_type": event_type,
                    "channel": channel,
                    "status": status,
                    "error_message": error_message,
                    "reference_id": reference_id,
                    "message": message,
                    "provider_message_id": provider_message_id,
                    "destination": destination,
                    "test_redirected": bool(test_redirected),
                    "created_at": utc_now(),
                },
            )
    except Exception:
        # Notification logging is diagnostic and remains best-effort.
        return


def _resolve_chat_channel(db: Session, user_id: Optional[int]) -> str:
    """Resolve the abstract "chat" policy slot to the user's actual
    preferred messaging channel (whatsapp default)."""
    if not user_id:
        return "whatsapp"
    user = db.query(models.User).filter(models.User.id == user_id).first()
    pref = getattr(user, "preferred_messaging_channel", None) if user else None
    return pref or "whatsapp"


def send_notification(
    db: Session,
    user_id: Optional[int],
    event_type: str,
    channel: str,
    message: str,
    template_name: Optional[str] = None,
    reference_id: Optional[int] = None,
    action_url: Optional[str] = None,
    claim_checked: bool = False,
) -> bool:
    controls = load_notification_controls(db)
    user = db.query(models.User).filter(models.User.id == user_id).first() if user_id else None
    original_destination: Optional[str] = None
    if channel == "whatsapp":
        original_destination = getattr(user, "phone", None) if user else None
    elif channel == "telegram":
        original_destination = getattr(user, "telegram_chat_id", None) if user else None
    elif channel == "email":
        original_destination = getattr(user, "email", None) if user else None

    if channel in {"whatsapp", "telegram", "email"} and not controls.effective_enabled:
        _log_notification(
            db,
            user_id=user_id,
            event_type=event_type,
            channel=channel,
            status="suppressed",
            error_message="system notifications disabled by admin or emergency environment override",
            reference_id=reference_id,
            message=message,
            destination=original_destination,
        )
        return False

    if (
        channel in {"whatsapp", "telegram", "email"}
        and not claim_checked
        and user_id is not None
        and reference_id is not None
        and not claim_notification_dispatch(
            db,
            user_id=user_id,
            event_type=event_type,
            reference_id=reference_id,
        )
    ):
        return False

    test_redirected = False
    if controls.test_mode and channel in {"whatsapp", "telegram", "email"}:
        if channel != "whatsapp" or not controls.test_phone:
            _log_notification(
                db,
                user_id=user_id,
                event_type=event_type,
                channel=channel,
                status="suppressed",
                error_message="test mode routes external notifications to the configured WhatsApp test number only",
                reference_id=reference_id,
                message=message,
                destination=original_destination,
            )
            return False
        intended_name = getattr(user, "name", None) or f"user #{user_id or 'unknown'}"
        intended_phone = original_destination or "no phone"
        message = f"[TEST for {intended_name} ({intended_phone})]\n{message}"
        template_name = None
        test_redirected = True

    if channel == "whatsapp":
        phone = controls.test_phone if test_redirected else original_destination
        if not phone:
            _log_notification(
                db,
                user_id=user_id,
                event_type=event_type,
                channel=channel,
                status="failed",
                error_message="missing phone number",
                reference_id=reference_id,
                message=message,
                destination=phone,
                test_redirected=test_redirected,
            )
            return False
        try:
            ok, provider_result = messaging.send_whatsapp_message(phone, message, template_name=template_name)
        except Exception as exc:
            ok, provider_result = False, str(exc)
        _log_notification(
            db,
            user_id=user_id,
            event_type=event_type,
            channel=channel,
            status="sent" if ok else "failed",
            error_message=None if ok else provider_result[:500],
            reference_id=reference_id,
            message=message,
            provider_message_id=provider_result if ok else None,
            destination=phone,
            test_redirected=test_redirected,
        )
        return ok

    if channel == "telegram":
        chat_id = original_destination
        if not chat_id:
            _log_notification(
                db,
                user_id=user_id,
                event_type=event_type,
                channel=channel,
                status="failed",
                error_message="missing telegram chat id - not linked",
                reference_id=reference_id,
                message=message,
                destination=chat_id,
            )
            return False
        ok, error = messaging.send_telegram_message(chat_id, message)
        _log_notification(
            db,
            user_id=user_id,
            event_type=event_type,
            channel=channel,
            status="sent" if ok else "failed",
            error_message=None if ok else error[:500],
            reference_id=reference_id,
            message=message,
            destination=chat_id,
        )
        return ok

    if channel == "email":
        email = original_destination
        if not email:
            _log_notification(
                db,
                user_id=user_id,
                event_type=event_type,
                channel=channel,
                status="failed",
                error_message="missing email",
                reference_id=reference_id,
                message=message,
                destination=email,
            )
            return False
        try:
            get_email_client().send(EmailMessage(to=[email], subject=event_type.replace("_", " ").title(), body=message))
            _log_notification(
                db,
                user_id=user_id,
                event_type=event_type,
                channel=channel,
                status="sent",
                reference_id=reference_id,
                message=message,
                destination=email,
            )
            return True
        except Exception as exc:
            _log_notification(
                db,
                user_id=user_id,
                event_type=event_type,
                channel=channel,
                status="failed",
                error_message=str(exc)[:500],
                reference_id=reference_id,
                message=message,
                destination=email,
            )
            return False

    if channel == "in_app":
        try:
            if _in_app_notifications_exist(db) and user_id is not None:
                db.execute(
                    text(
                        """
                        INSERT INTO in_app_notifications (user_id, title, body, action_url, read, created_at)
                        VALUES (:user_id, :title, :body, :action_url, 0, :created_at)
                        """
                    ),
                    {
                        "user_id": user_id,
                        "title": event_type.replace("_", " ").title(),
                        "body": message,
                        "action_url": action_url,
                        "created_at": utc_now(),
                    },
                )
            _log_notification(
                db,
                user_id=user_id,
                event_type=event_type,
                channel=channel,
                status="sent",
                reference_id=reference_id,
                message=message,
            )
            return True
        except Exception as exc:
            _log_notification(
                db,
                user_id=user_id,
                event_type=event_type,
                channel=channel,
                status="failed",
                error_message=str(exc)[:500],
                reference_id=reference_id,
                message=message,
            )
            return False

    _log_notification(
        db,
        user_id=user_id,
        event_type=event_type,
        channel=channel,
        status="failed",
        error_message="unsupported channel",
        reference_id=reference_id,
        message=message,
    )
    return False


def notify(
    db: Session,
    user_id: Optional[int],
    event_type: str,
    message: str,
    reference_id: Optional[int] = None,
    action_url: Optional[str] = None,
    include_in_app: bool = True,
    deduplicate: bool = True,
    idempotency_key: Optional[str] = None,
) -> bool:
    """Policy-driven delivery: consult NOTIFICATION_POLICY for the event's
    channel fallback chain, write an in-app notification when the policy
    demands one, and log every attempt (with the message body, enabling the
    retry sweep). Returns True if any fallback channel delivered."""
    policy = NOTIFICATION_POLICY.get(event_type, DEFAULT_POLICY)

    controls = load_notification_controls(db)
    if (
        controls.effective_enabled
        and deduplicate
        and user_id is not None
        and reference_id is not None
        and not claim_notification_dispatch(
            db,
            user_id=user_id,
            event_type=event_type,
            reference_id=reference_id,
            idempotency_key=idempotency_key,
        )
    ):
        return False

    delivered = False
    for channel in policy.get("channels", DEFAULT_POLICY["channels"]):
        if channel == "chat":
            resolved_channel = "whatsapp" if controls.test_mode else _resolve_chat_channel(db, user_id)
        else:
            resolved_channel = channel
        ok = send_notification(
            db,
            user_id,
            event_type,
            resolved_channel,
            message,
            template_name=event_type if (resolved_channel == "whatsapp" and event_type in WHATSAPP_TEMPLATE_NAMES) else None,
            reference_id=reference_id,
            action_url=action_url,
            claim_checked=True,
        )
        if ok:
            delivered = True
            break

    if include_in_app and policy.get("in_app"):
        send_notification(
            db,
            user_id,
            event_type,
            "in_app",
            message,
            reference_id=reference_id,
            action_url=action_url,
            claim_checked=True,
        )

    return delivered


def record_twilio_delivery_status(
    db: Session,
    provider_message_id: str,
    provider_status: str,
    error_message: Optional[str] = None,
) -> bool:
    """Reconcile Twilio's asynchronous delivery result.

    Twilio can accept a message and only later report that Meta rejected it.
    On the first terminal failure, update the original WhatsApp attempt and
    deliver the policy's email fallback. Repeated callbacks are idempotent.
    """
    normalized_status = (provider_status or "").strip().lower()
    if not provider_message_id or normalized_status not in {
        "accepted", "queued", "sending", "sent", "delivered", "read", "failed", "undelivered"
    }:
        return False

    row = (
        db.query(models.NotificationLog)
        .filter(
            models.NotificationLog.channel == "whatsapp",
            models.NotificationLog.provider_message_id == provider_message_id,
        )
        .order_by(models.NotificationLog.id.desc())
        .first()
    )
    if not row:
        return False

    is_failure = normalized_status in {"failed", "undelivered"}
    already_failed = row.status == "failed"
    row.status = "failed" if is_failure else normalized_status
    row.error_message = (error_message or "")[:500] or None

    if is_failure and not already_failed:
        policy = NOTIFICATION_POLICY.get(row.event_type, DEFAULT_POLICY)
        if "email" in policy.get("channels", DEFAULT_POLICY["channels"]):
            email_already_sent = (
                db.query(models.NotificationLog.id)
                .filter(
                    models.NotificationLog.user_id == row.user_id,
                    models.NotificationLog.event_type == row.event_type,
                    models.NotificationLog.reference_id == row.reference_id,
                    models.NotificationLog.channel == "email",
                    models.NotificationLog.status == "sent",
                )
                .first()
                is not None
            )
            if not email_already_sent:
                send_notification(
                    db,
                    row.user_id,
                    row.event_type,
                    "email",
                    row.message or row.event_type.replace("_", " ").title(),
                    reference_id=row.reference_id,
                    claim_checked=True,
                )
    return True


def send_critical(
    db: Session,
    user_id: Optional[int],
    event_type: str,
    message: str,
    reference_id: Optional[int] = None,
) -> bool:
    # Backward-compatible alias; policy-driven since the notification
    # reliability work.
    return notify(db, user_id, event_type, message, reference_id=reference_id)


def retry_failed_notifications(
    db: Session,
    max_attempts: int = RETRY_MAX_ATTEMPTS,
    window_hours: int = RETRY_WINDOW_HOURS,
) -> int:
    """Scheduled sweep: re-deliver recently failed notifications.

    A (user_id, event_type, reference_id) tuple is retried when:
    - its most recent rows in the window are all 'failed' (no 'sent' row), and
    - it has fewer than max_attempts failed attempts, and
    - a message body was persisted (pre-upgrade rows without one are skipped).
    Each retry goes through notify(), which logs a fresh attempt row, so
    attempts are naturally counted. Returns number of tuples retried."""
    if not _notification_log_exists(db):
        return 0

    from datetime import timedelta

    cutoff = utc_now() - timedelta(hours=window_hours)
    rows = (
        db.query(models.NotificationLog)
        .filter(
            models.NotificationLog.created_at >= cutoff,
            models.NotificationLog.channel.in_(["whatsapp", "telegram", "email"]),
        )
        .order_by(models.NotificationLog.created_at.asc())
        .all()
    )

    grouped: dict[tuple, dict] = {}
    for row in rows:
        key = (row.user_id, row.event_type, row.reference_id)
        entry = grouped.setdefault(key, {"failed": 0, "sent": False, "message": None})
        if row.status in {"accepted", "queued", "sending", "sent", "delivered", "read"}:
            entry["sent"] = True
        elif row.status == "failed":
            entry["failed"] += 1
            if row.message:
                entry["message"] = row.message

    retried = 0
    for (user_id, event_type, reference_id), entry in grouped.items():
        if entry["sent"] or not entry["message"]:
            continue
        if entry["failed"] >= max_attempts:
            continue
        notify(
            db,
            user_id,
            event_type,
            entry["message"],
            reference_id=reference_id,
            include_in_app=False,
            deduplicate=False,
        )
        retried += 1

    if retried:
        db.commit()
    return retried
