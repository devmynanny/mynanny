from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app import models
from app.services.paystack import create_transfer
from app.services.debt import deduct_debt_from_payout
from app.services.notifications import send_notification
from app.utils.email import EmailMessage, admin_emails, get_email_client


def _notification_log_exists(db: Session) -> bool:
    row = db.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='notification_log'")).fetchone()
    return row is not None


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


def _notify_admin(db: Session, subject: str, body: str, reference_id: str) -> None:
    admins = admin_emails()
    if not admins:
        return
    try:
        get_email_client().send(EmailMessage(to=admins, subject=subject, body=body))
        _log_notification_best_effort(
            db,
            user_id=None,
            event_type="payout_admin_alert",
            channel="email",
            status="sent",
            reference_id=reference_id,
        )
    except Exception as exc:
        _log_notification_best_effort(
            db,
            user_id=None,
            event_type="payout_admin_alert",
            channel="email",
            status="failed",
            error_message=str(exc)[:500],
            reference_id=reference_id,
        )


def _nanny_user(db: Session, nanny_id: int) -> Optional[models.User]:
    nanny = db.query(models.Nanny).filter(models.Nanny.id == nanny_id).first()
    if not nanny:
        return None
    return db.query(models.User).filter(models.User.id == nanny.user_id).first()


def _transfer_to_nanny_bank(
    *,
    db: Session,
    booking_id: int,
    nanny_id: int,
    amount_cents: int,
    reason: str,
) -> bool:
    bank = (
        db.query(models.NannyBankAccount)
        .filter(models.NannyBankAccount.nanny_id == nanny_id)
        .order_by(models.NannyBankAccount.is_default.desc(), models.NannyBankAccount.is_verified.desc(), models.NannyBankAccount.id.desc())
        .first()
    )
    if not bank:
        _notify_admin(
            db,
            subject=f"Payout skipped: missing bank account (booking #{booking_id})",
            body=f"No bank account is stored for nanny_id={nanny_id}. Booking={booking_id}.",
            reference_id=str(booking_id),
        )
        return False

    nanny = db.query(models.Nanny).filter(models.Nanny.id == nanny_id).first()
    recipient_code = getattr(bank, "paystack_recipient_code", None) or getattr(nanny, "paystack_recipient_code", None)
    if not recipient_code:
        _notify_admin(
            db,
            subject=f"Payout recipient missing code (booking #{booking_id})",
            body=f"Paystack recipient_code missing for nanny_id={nanny_id}.",
            reference_id=str(booking_id),
        )
        return False

    ok_transfer, transfer_data = create_transfer(
        amount_kobo=int(amount_cents),
        recipient_code=str(recipient_code),
        reason=reason,
    )
    if not ok_transfer:
        _notify_admin(
            db,
            subject=f"Payout transfer failed (booking #{booking_id})",
            body=f"Transfer failed for nanny_id={nanny_id}: {transfer_data}",
            reference_id=str(booking_id),
        )
        return False
    return True


def run_scheduled_payouts(db: Session) -> None:
    now = datetime.utcnow()

    bookings = (
        db.query(models.Booking)
        .filter(
            models.Booking.status == "completed",
            models.Booking.payout_hold_until.isnot(None),
            models.Booking.payout_hold_until <= now,
            models.Booking.payout_released_at.is_(None),
            models.Booking.payout_disputed == False,  # noqa: E712
        )
        .all()
    )
    for booking in bookings:
        try:
            with db.begin_nested():
                req = None
                if getattr(booking, "booking_request_id", None):
                    req = db.query(models.BookingRequest).filter(models.BookingRequest.id == booking.booking_request_id).first()
                payout_cents = int((req.nanny_retained_cents if req else 0) or 0)
                if payout_cents <= 0:
                    continue
                debt_result = deduct_debt_from_payout(db, int(booking.nanny_id), payout_cents, booking_id=int(booking.id))
                net_payout_cents = int(debt_result.get("net_payout_cents") or 0)
                deducted_cents = int(debt_result.get("total_deducted_cents") or 0)
                booking.payout_debt_deducted_cents = deducted_cents
                booking.payout_amount_cents = net_payout_cents
                transferred = _transfer_to_nanny_bank(
                    db=db,
                    booking_id=int(booking.id),
                    nanny_id=int(booking.nanny_id),
                    amount_cents=net_payout_cents,
                    reason=f"Nanny payout for booking {booking.id}",
                )
                if not transferred:
                    raise RuntimeError("payout transfer failed")
                booking.payout_released_at = datetime.utcnow()
                nanny_user = _nanny_user(db, int(booking.nanny_id))
                if nanny_user:
                    send_notification(
                        db,
                        nanny_user.id,
                        "payout_sent",
                        "email",
                        f"Your payment of R{(net_payout_cents/100):.2f} has been sent.",
                        reference_id=int(booking.id),
                    )
        except Exception:
            continue

    overrun_bookings = (
        db.query(models.Booking)
        .filter(
            models.Booking.status == "completed",
            models.Booking.overrun_amount_cents.isnot(None),
            models.Booking.overrun_hold_until.isnot(None),
            models.Booking.overrun_hold_until <= now,
            models.Booking.overrun_released_at.is_(None),
            models.Booking.overrun_disputed == False,  # noqa: E712
        )
        .all()
    )
    for booking in overrun_bookings:
        try:
            with db.begin_nested():
                amount_cents = int(booking.overrun_amount_cents or 0)
                if amount_cents <= 0:
                    continue
                transferred = _transfer_to_nanny_bank(
                    db=db,
                    booking_id=int(booking.id),
                    nanny_id=int(booking.nanny_id),
                    amount_cents=amount_cents,
                    reason=f"Overrun payout for booking {booking.id}",
                )
                if not transferred:
                    raise RuntimeError("overrun transfer failed")
                booking.overrun_released_at = datetime.utcnow()
                nanny_user = _nanny_user(db, int(booking.nanny_id))
                if nanny_user:
                    send_notification(
                        db,
                        nanny_user.id,
                        "payout_sent",
                        "email",
                        f"Your overrun payment of R{(amount_cents/100):.2f} has been sent.",
                        reference_id=int(booking.id),
                    )
        except Exception:
            continue

    db.commit()
