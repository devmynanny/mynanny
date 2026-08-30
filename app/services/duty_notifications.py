from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app import models
from app.services.notifications import notify
from app.utils.time import utc_now


ACTIVE_DUTY_STATUSES = ("approved", "accepted", "active", "in_progress")
DELIVERED_NOTIFICATION_STATUSES = (
    "pending",
    "accepted",
    "queued",
    "sending",
    "sent",
    "delivered",
    "read",
)


def _aware(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _already_sent(db: Session, user_id: Optional[int], event_type: str, reference_id: int) -> bool:
    if user_id is None:
        return True
    return (
        db.query(models.NotificationLog.id)
        .filter(
            models.NotificationLog.user_id == user_id,
            models.NotificationLog.event_type == event_type,
            models.NotificationLog.reference_id == reference_id,
            models.NotificationLog.status.in_(DELIVERED_NOTIFICATION_STATUSES),
        )
        .first()
        is not None
    )


def notify_once(
    db: Session,
    *,
    user_id: Optional[int],
    event_type: str,
    message: str,
    booking_id: int,
    action_url: str = "/bookings",
) -> bool:
    if _already_sent(db, user_id, event_type, booking_id):
        return False
    notify(
        db,
        user_id,
        event_type,
        message,
        reference_id=booking_id,
        action_url=action_url,
    )
    return True


def _booking_people(db: Session, booking: models.Booking) -> tuple[Optional[models.User], Optional[models.User]]:
    parent = db.query(models.User).filter(models.User.id == booking.client_user_id).first()
    nanny = db.query(models.Nanny).filter(models.Nanny.id == booking.nanny_id).first()
    nanny_user = db.query(models.User).filter(models.User.id == nanny.user_id).first() if nanny else None
    return parent, nanny_user


def run_duty_notification_sweep(db: Session, *, now: Optional[datetime] = None) -> dict[str, int]:
    """Send one-time duty reminders and escalate missed operational events."""
    current = _aware(now or utc_now())
    if current is None:
        return {"start_reminders": 0, "missed_check_ins": 0, "checkout_reminders": 0}

    window_start = (current - timedelta(hours=2)).replace(tzinfo=None)
    window_end = (current + timedelta(hours=2)).replace(tzinfo=None)
    bookings = (
        db.query(models.Booking)
        .filter(
            models.Booking.status.in_(ACTIVE_DUTY_STATUSES),
            models.Booking.starts_at <= window_end,
            models.Booking.ends_at >= window_start,
        )
        .all()
    )

    counts = {"start_reminders": 0, "missed_check_ins": 0, "checkout_reminders": 0}
    for booking in bookings:
        starts_at = _aware(booking.starts_at)
        ends_at = _aware(booking.ends_at)
        if not starts_at or not ends_at:
            continue
        parent, nanny = _booking_people(db, booking)
        nanny_name = getattr(nanny, "name", None) or "Your nanny"
        booking_id = int(booking.id)

        minutes_to_start = (starts_at - current).total_seconds() / 60.0
        if not booking.check_in_at and 45 <= minutes_to_start <= 75:
            if notify_once(
                db,
                user_id=getattr(nanny, "id", None),
                event_type="booking_start_reminder",
                message=f"Booking #{booking_id} starts in about one hour. Open the booking to review the location and check-in instructions.",
                booking_id=booking_id,
            ):
                counts["start_reminders"] += 1

        minutes_after_start = (current - starts_at).total_seconds() / 60.0
        if not booking.check_in_at and 15 <= minutes_after_start and current < ends_at:
            nanny_notified = notify_once(
                db,
                user_id=getattr(nanny, "id", None),
                event_type="missed_check_in",
                message=f"You have not checked in for booking #{booking_id}. Check in now or contact My Nanny if you cannot attend.",
                booking_id=booking_id,
            )
            notify_once(
                db,
                user_id=getattr(parent, "id", None),
                event_type="nanny_late_alert",
                message=f"{nanny_name} has not checked in for booking #{booking_id}. Operations has been alerted.",
                booking_id=booking_id,
            )
            for admin in db.query(models.User).filter(models.User.is_admin.is_(True), models.User.is_active.is_(True)).all():
                notify_once(
                    db,
                    user_id=admin.id,
                    event_type="duty_attention_required",
                    message=f"Booking #{booking_id} is at least 15 minutes late with no nanny check-in.",
                    booking_id=booking_id,
                    action_url="/operations",
                )
            if nanny_notified:
                counts["missed_check_ins"] += 1

        minutes_after_end = (current - ends_at).total_seconds() / 60.0
        if booking.check_in_at and not booking.check_out_at and 0 <= minutes_after_end <= 120:
            if notify_once(
                db,
                user_id=getattr(nanny, "id", None),
                event_type="checkout_reminder",
                message=f"Booking #{booking_id} has reached its scheduled finish time. Check out when care has ended.",
                booking_id=booking_id,
            ):
                counts["checkout_reminders"] += 1

    db.commit()
    return counts
