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
}


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
) -> None:
    if not _notification_log_exists(db):
        return
    db.execute(
        text(
            """
            INSERT INTO notification_log (user_id, event_type, channel, status, error_message, reference_id, created_at)
            VALUES (:user_id, :event_type, :channel, :status, :error_message, :reference_id, :created_at)
            """
        ),
        {
            "user_id": user_id,
            "event_type": event_type,
            "channel": channel,
            "status": status,
            "error_message": error_message,
            "reference_id": reference_id,
            "created_at": datetime.utcnow(),
        },
    )


def _twilio_whatsapp_send(to_number: str, body: str, template_name: Optional[str] = None) -> tuple[bool, str]:
    sid = (os.getenv("TWILIO_ACCOUNT_SID") or "").strip()
    token = (os.getenv("TWILIO_AUTH_TOKEN") or "").strip()
    from_number = (os.getenv("TWILIO_WHATSAPP_FROM") or "").strip()
    if not sid or not token or not from_number:
        return False, "Twilio WhatsApp not configured"

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
    )
    return False


def send_critical(
    db: Session,
    user_id: Optional[int],
    event_type: str,
    message: str,
    reference_id: Optional[int] = None,
) -> bool:
    whatsapp_ok = send_notification(
        db,
        user_id,
        event_type,
        "whatsapp",
        message,
        template_name=event_type if event_type in WHATSAPP_TEMPLATE_NAMES else None,
        reference_id=reference_id,
    )
    if whatsapp_ok:
        return True
    return send_notification(db, user_id, event_type, "email", message, reference_id=reference_id)
