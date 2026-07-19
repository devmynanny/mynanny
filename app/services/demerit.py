from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app import models
from app.utils.email import EmailMessage, admin_emails, get_email_client


def _base_rating_for_nanny(db: Session, nanny_id: int) -> float:
    avg = (
        db.query(func.avg(models.Review.stars))
        .filter(
            models.Review.nanny_id == nanny_id,
            models.Review.approved == True,  # noqa: E712
        )
        .scalar()
    )
    if avg is None:
        return 5.0
    return float(avg)


def _notification_log_exists(db: Session) -> bool:
    from app.db import session_table_exists
    return session_table_exists(db, "notification_log")


def _log_notification_best_effort(
    db: Session,
    *,
    user_id: Optional[int],
    event_type: str,
    channel: str,
    status: str,
    error_message: Optional[str] = None,
    reference_id: Optional[str] = None,
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


def _notify_admin_best_effort(db: Session, subject: str, body: str, event_type: str) -> None:
    recipients = admin_emails()
    if not recipients:
        return
    try:
        get_email_client().send(EmailMessage(to=recipients, subject=subject, body=body))
        _log_notification_best_effort(
            db,
            user_id=None,
            event_type=event_type,
            channel="email",
            status="sent",
            reference_id=None,
        )
    except Exception as exc:
        _log_notification_best_effort(
            db,
            user_id=None,
            event_type=event_type,
            channel="email",
            status="failed",
            error_message=str(exc)[:500],
            reference_id=None,
        )


def apply_demerit(
    db: Session,
    nanny_id: int,
    reason: str,
    demerit_pct: float,
    weight: float,
    booking_id: int = None,
    applied_by: str = "system",
) -> None:
    nanny = db.query(models.Nanny).filter(models.Nanny.id == nanny_id).first()
    if not nanny:
        raise ValueError("Nanny not found")

    current = float(getattr(nanny, "rating_demerit_pct", 0.0) or 0.0)
    new_cumulative = current + float(demerit_pct)
    nanny.rating_demerit_pct = new_cumulative

    log = models.NannyDemeritLog(
        nanny_id=nanny_id,
        booking_id=booking_id,
        reason=reason,
        demerit_pct=float(demerit_pct),
        weight=float(weight),
        cumulative_demerit_pct=float(new_cumulative),
        applied_by=str(applied_by),
        applied_at=datetime.utcnow(),
    )
    db.add(log)

    base_rating = _base_rating_for_nanny(db, nanny_id)
    displayed_rating = base_rating * (1.0 - new_cumulative)
    if displayed_rating < 2.5:
        nanny.is_suspended = True
        nanny.suspended_at = datetime.utcnow()
        nanny.suspension_reason = "rating_below_threshold"
        _notify_admin_best_effort(
            db,
            subject=f"Nanny suspended: #{nanny_id}",
            body=f"Nanny {nanny_id} was automatically suspended because displayed rating dropped below 2.5.",
            event_type="nanny_suspended_rating_below_threshold",
        )

    db.commit()


def apply_cancellation_weight(
    db: Session,
    nanny_id: int,
    weight: float,
) -> None:
    nanny = db.query(models.Nanny).filter(models.Nanny.id == nanny_id).first()
    if not nanny:
        raise ValueError("Nanny not found")

    nanny.cancellation_count = int(getattr(nanny, "cancellation_count", 0) or 0) + 1

    db.add(
        models.NannyDemeritLog(
            nanny_id=nanny_id,
            booking_id=None,
            reason="cancellation_weight",
            demerit_pct=0.0,
            weight=float(weight),
            cumulative_demerit_pct=float(getattr(nanny, "rating_demerit_pct", 0.0) or 0.0),
            applied_by="system",
            applied_at=datetime.utcnow(),
        )
    )

    cutoff = datetime.utcnow() - timedelta(days=180)
    weighted_total_180d = (
        db.query(func.coalesce(func.sum(models.NannyDemeritLog.weight), 0.0))
        .filter(
            models.NannyDemeritLog.nanny_id == nanny_id,
            models.NannyDemeritLog.applied_at >= cutoff,
            models.NannyDemeritLog.reversed_at.is_(None),
        )
        .scalar()
    )
    weighted_total_180d = float(weighted_total_180d or 0.0)

    if weighted_total_180d >= 5.0 and not bool(getattr(nanny, "admin_review_flagged", False)):
        nanny.admin_review_flagged = True
        _notify_admin_best_effort(
            db,
            subject=f"Nanny cancellation threshold hit: #{nanny_id}",
            body=f"Nanny {nanny_id} reached weighted cancellations threshold: {weighted_total_180d:.2f}.",
            event_type="nanny_cancellation_threshold_hit",
        )

    db.commit()


def apply_no_show(
    db: Session,
    nanny_id: int,
    booking_id: int,
) -> None:
    nanny = db.query(models.Nanny).filter(models.Nanny.id == nanny_id).first()
    if not nanny:
        raise ValueError("Nanny not found")

    nanny.no_show_count = int(getattr(nanny, "no_show_count", 0) or 0) + 1
    db.commit()

    apply_demerit(
        db=db,
        nanny_id=nanny_id,
        reason="no_show",
        demerit_pct=0.30,
        weight=1.0,
        booking_id=booking_id,
    )
    apply_cancellation_weight(db=db, nanny_id=nanny_id, weight=1.0)

    nanny = db.query(models.Nanny).filter(models.Nanny.id == nanny_id).first()
    if nanny and int(getattr(nanny, "no_show_count", 0) or 0) >= 2:
        nanny.admin_review_flagged = True
        _notify_admin_best_effort(
            db,
            subject=f"Nanny fitness review required: #{nanny_id}",
            body=f"Nanny {nanny_id} has 2 or more no-shows and requires admin fitness review.",
            event_type="nanny_no_show_fitness_review_required",
        )
    db.commit()
