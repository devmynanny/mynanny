"""
Expiry sweep for stale booking-request adverts.

Policy (documented in APP_RULES.md):
- A booking request still awaiting a nanny response (status 'tbc' or
  'pending_admin', response not 'accepted') whose requested start time has
  passed can no longer be fulfilled - acceptance is already blocked at
  accept-time by _validate_booking_windows_not_in_past.
- The sweep marks such requests status='rejected' with admin_reason='expired'
  so dashboards stop showing them as live work, and reporting can distinguish
  expiry from human rejection via admin_reason.
- Requests a nanny has already accepted are never touched by the sweep.
"""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from app import models

EXPIRED_ADMIN_REASON = "expired"


def _naive_utc(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    try:
        text = str(value).strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        if " " in text and "T" not in text:
            text = text.replace(" ", "T")
        parsed = datetime.fromisoformat(text)
        return parsed.replace(tzinfo=None) if parsed.tzinfo else parsed
    except Exception:
        return None


def _request_start(req: models.BookingRequest) -> Optional[datetime]:
    return _naive_utc(getattr(req, "requested_starts_at", None)) or _naive_utc(
        getattr(req, "start_dt", None)
    )


def is_request_expired(req: models.BookingRequest, now: Optional[datetime] = None) -> bool:
    """An open advert is expired once its start time has passed."""
    if req.status not in ("tbc", "pending_admin"):
        return False
    if (getattr(req, "nanny_response_status", None) or "").lower() == "accepted":
        return False
    start = _request_start(req)
    if start is None:
        return False
    return start <= (now or datetime.utcnow())


def _notification_already_sent(db: Session, user_id: int, event_type: str, reference_id: int) -> bool:
    try:
        return (
            db.query(models.NotificationLog)
            .filter(
                models.NotificationLog.user_id == user_id,
                models.NotificationLog.event_type == event_type,
                models.NotificationLog.reference_id == reference_id,
            )
            .first()
            is not None
        )
    except Exception:
        return True  # fail closed: don't spam if the log can't be read


def expire_stale_booking_requests(db: Session, now: Optional[datetime] = None) -> int:
    """Mark all expired open adverts as rejected/expired. Returns count.

    Also:
    - notifies the parent (once per group) when a request expires unfilled
    - nudges the parent (once per group) when a request starting within 12h
      still has no acceptance
    - reminds nannies who marked 'still deciding' when the job starts within 24h
    """
    from datetime import timedelta

    from app.services.notifications import send_notification

    current = now or datetime.utcnow()
    candidates = (
        db.query(models.BookingRequest)
        .filter(models.BookingRequest.status.in_(["tbc", "pending_admin"]))
        .all()
    )

    expired_count = 0
    expired_groups: dict[int, models.BookingRequest] = {}
    nudge_groups: dict[int, models.BookingRequest] = {}

    for req in candidates:
        if is_request_expired(req, current):
            req.status = "rejected"
            req.admin_reason = EXPIRED_ADMIN_REASON
            req.admin_decided_at = current
            expired_count += 1
            gid = req.group_id or req.id
            expired_groups.setdefault(gid, req)
            continue

        start = _request_start(req)
        if start is None:
            continue

        # Pre-start nudge: unaccepted and starting within 12 hours.
        if current <= start <= current + timedelta(hours=12):
            gid = req.group_id or req.id
            nudge_groups.setdefault(gid, req)

        # Deciding reminder: nanny sat on it and the job starts within 24 hours.
        if (
            (getattr(req, "nanny_response_status", None) or "").lower() == "deciding"
            and start <= current + timedelta(hours=24)
        ):
            nanny_row = db.query(models.Nanny).filter(models.Nanny.id == req.nanny_id).first()
            nanny_user_id = getattr(nanny_row, "user_id", None)
            if nanny_user_id and not _notification_already_sent(db, nanny_user_id, "deciding_reminder", req.id):
                send_notification(
                    db,
                    nanny_user_id,
                    "deciding_reminder",
                    "email",
                    "You marked a booking request as 'still deciding' and it starts soon. Please accept or decline it so the client is not left waiting.",
                    reference_id=int(req.id),
                )

    if expired_count:
        db.commit()

    # Parent notifications: one per group, deduplicated via the notification log.
    for gid, req in expired_groups.items():
        parent_id = req.parent_user_id
        if parent_id and not _notification_already_sent(db, parent_id, "request_expired", gid):
            send_notification(
                db,
                parent_id,
                "request_expired",
                "email",
                "Unfortunately no nanny accepted your booking request before its start time, and it has now expired. Please create a new booking — sending it to more nannies improves your chances.",
                reference_id=int(gid),
            )

    for gid, req in nudge_groups.items():
        if gid in expired_groups:
            continue
        parent_id = req.parent_user_id
        if parent_id and not _notification_already_sent(db, parent_id, "no_nanny_yet", gid):
            send_notification(
                db,
                parent_id,
                "no_nanny_yet",
                "email",
                "Your booking starts within 12 hours and no nanny has accepted yet. You can send the request to more nannies from your bookings page to improve your chances.",
                reference_id=int(gid),
            )

    try:
        db.commit()
    except Exception:
        db.rollback()

    return expired_count
