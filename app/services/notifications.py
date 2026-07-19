from __future__ import annotations

import base64
import json
import os
from datetime import datetime
from typing import Optional
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError
from urllib.parse import quote

from sqlalchemy import text
from sqlalchemy.orm import Session

from app import models
from app.utils.email import EmailMessage, get_email_client

WHATSAPP_TEMPLATE_NAMES = {
    "nanny_accepted",
    "payment_due",
    "payment_success",
    "payment_failed",
    "booking_confirmed",
    "nanny_checked_in",
    "overtime_request",
    "payout_pending",
    "payout_sent",
    "nanny_approved",
    "booking_cancelled",
    "refund_processed",
    "review_request",
    # Broadcast / request lifecycle
    "new_booking_request",
    "nanny_declined",
    "no_nanny_yet",
    "request_expired",
    "deciding_reminder",
    # Payment retry flow
    "payment_pending",
    # Nanny-specific cancellation notice
    "booking_cancelled_nanny",
}

# ---------------------------------------------------------------------------
# Notification policy matrix (single source of truth).
#
# channels are tried in order until one succeeds (fallback chain).
# "in_app" entries are ALWAYS written in addition (they are pop-ups for
# action-required confirmations, not a delivery fallback).
# Default for unlisted event types: ("whatsapp", "email").
# ---------------------------------------------------------------------------
NOTIFICATION_POLICY: dict[str, dict] = {
    # Payments - critical, user must know immediately.
    "payment_success": {"channels": ("whatsapp", "email")},
    "payment_failed": {"channels": ("whatsapp", "email"), "in_app": True},
    "refund_processed": {"channels": ("whatsapp", "email")},
    # Booking lifecycle.
    "booking_confirmed": {"channels": ("whatsapp", "email")},
    "booking_cancelled": {"channels": ("whatsapp", "email"), "in_app": True},
    "nanny_accepted": {"channels": ("whatsapp", "email")},
    "nanny_checked_in": {"channels": ("whatsapp", "email")},
    # Action required - in-app pop-up mandatory.
    "overtime_request": {"channels": ("whatsapp", "email"), "in_app": True},
    "review_request": {"channels": ("whatsapp", "email"), "in_app": True},
    # Request lifecycle - parent must act or know quickly.
    "new_booking_request": {"channels": ("whatsapp", "email")},
    "nanny_declined": {"channels": ("whatsapp", "email")},
    "no_nanny_yet": {"channels": ("whatsapp", "email"), "in_app": True},
    "request_expired": {"channels": ("whatsapp", "email"), "in_app": True},
    "deciding_reminder": {"channels": ("whatsapp", "email")},
    # Payment retry flow.
    "payment_pending": {"channels": ("whatsapp", "email")},
    "booking_cancelled_nanny": {"channels": ("whatsapp", "email"), "in_app": True},
    # Payouts.
    "payout_pending": {"channels": ("whatsapp", "email")},
    "payout_sent": {"channels": ("whatsapp", "email")},
    # Account.
    "nanny_approved": {"channels": ("whatsapp", "email")},
    "nanny_reactivated": {"channels": ("whatsapp", "email")},
}

DEFAULT_POLICY = {"channels": ("whatsapp", "email"), "in_app": False}

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
) -> None:
    if not _notification_log_exists(db):
        return
    db.execute(
        text(
            """
            INSERT INTO notification_log (user_id, event_type, channel, status, error_message, reference_id, message, created_at)
            VALUES (:user_id, :event_type, :channel, :status, :error_message, :reference_id, :message, :created_at)
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
            "created_at": datetime.utcnow(),
        },
    )


def _twilio_whatsapp_send(to_number: str, body: str, template_name: Optional[str] = None) -> tuple[bool, str]:
    sid = (os.getenv("TWILIO_ACCOUNT_SID") or "").strip()
    token = (os.getenv("TWILIO_AUTH_TOKEN") or "").strip()
    from_number = (os.getenv("TWILIO_WHATSAPP_FROM") or "").strip()
    if not sid or not token or not from_number:
        return False, "Twilio WhatsApp not configured"

    # Twilio requires the whatsapp: prefix on both From and To.
    if not from_number.startswith("whatsapp:"):
        from_number = f"whatsapp:{from_number}"
    to_number = str(to_number).strip()
    if not to_number.startswith("whatsapp:"):
        to_number = f"whatsapp:{to_number}"

    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    payload = {
        "From": from_number,
        "To": to_number,
        "Body": body,
    }
    if template_name:
        payload["Body"] = body
    data = "&".join(f"{k}={quote(str(v))}" for k, v in payload.items()).encode("utf-8")
    auth = base64.b64encode(f"{sid}:{token}".encode("utf-8")).decode("ascii")
    req = urllib_request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urllib_request.urlopen(req, timeout=20) as res:
            res.read()
        return True, ""
    except (HTTPError, URLError) as exc:
        return False, str(exc)
    except Exception as exc:
        return False, str(exc)


def send_notification(
    db: Session,
    user_id: Optional[int],
    event_type: str,
    channel: str,
    message: str,
    template_name: Optional[str] = None,
    reference_id: Optional[int] = None,
) -> bool:
    if channel == "whatsapp":
        user = db.query(models.User).filter(models.User.id == user_id).first() if user_id else None
        phone = getattr(user, "phone", None) if user else None
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
            )
            return False
        ok, error = _twilio_whatsapp_send(phone, message, template_name=template_name)
        _log_notification(
            db,
            user_id=user_id,
            event_type=event_type,
            channel=channel,
            status="sent" if ok else "failed",
            error_message=None if ok else error[:500],
            reference_id=reference_id,
            message=message,
        )
        return ok

    if channel == "email":
        user = db.query(models.User).filter(models.User.id == user_id).first() if user_id else None
        email = getattr(user, "email", None) if user else None
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
                        "action_url": None,
                        "created_at": datetime.utcnow(),
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
) -> bool:
    """Policy-driven delivery: consult NOTIFICATION_POLICY for the event's
    channel fallback chain, write an in-app notification when the policy
    demands one, and log every attempt (with the message body, enabling the
    retry sweep). Returns True if any fallback channel delivered."""
    policy = NOTIFICATION_POLICY.get(event_type, DEFAULT_POLICY)

    delivered = False
    for channel in policy.get("channels", DEFAULT_POLICY["channels"]):
        ok = send_notification(
            db,
            user_id,
            event_type,
            channel,
            message,
            template_name=event_type if (channel == "whatsapp" and event_type in WHATSAPP_TEMPLATE_NAMES) else None,
            reference_id=reference_id,
        )
        if ok:
            delivered = True
            break

    if policy.get("in_app"):
        send_notification(db, user_id, event_type, "in_app", message, reference_id=reference_id)

    return delivered


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

    cutoff = datetime.utcnow() - timedelta(hours=window_hours)
    rows = (
        db.query(models.NotificationLog)
        .filter(
            models.NotificationLog.created_at >= cutoff,
            models.NotificationLog.channel.in_(["whatsapp", "email"]),
        )
        .order_by(models.NotificationLog.created_at.asc())
        .all()
    )

    grouped: dict[tuple, dict] = {}
    for row in rows:
        key = (row.user_id, row.event_type, row.reference_id)
        entry = grouped.setdefault(key, {"failed": 0, "sent": False, "message": None})
        if row.status == "sent":
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
        notify(db, user_id, event_type, entry["message"], reference_id=reference_id)
        retried += 1

    if retried:
        db.commit()
    return retried
