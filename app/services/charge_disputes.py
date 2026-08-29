from sqlalchemy import or_
from sqlalchemy.orm import Session

from app import models


ACTIVE_DISPUTE_STATUSES = ("open", "refund_requested", "failed")


def related_booking_request_ids(db: Session, booking_request: models.BookingRequest) -> list[int]:
    group_id = booking_request.group_id or booking_request.id
    rows = (
        db.query(models.BookingRequest.id)
        .filter(
            models.BookingRequest.parent_user_id == booking_request.parent_user_id,
            or_(models.BookingRequest.group_id == group_id, models.BookingRequest.id == group_id),
        )
        .all()
    )
    return [int(row[0]) for row in rows]


def refresh_booking_dispute_holds(db: Session, booking_request_id: int) -> bool:
    booking_request = db.query(models.BookingRequest).filter(models.BookingRequest.id == booking_request_id).first()
    if not booking_request:
        return False
    request_ids = related_booking_request_ids(db, booking_request)
    active = bool(
        db.query(models.ChargeDispute.id)
        .filter(
            models.ChargeDispute.booking_request_id.in_(request_ids),
            models.ChargeDispute.status.in_(ACTIVE_DISPUTE_STATUSES),
        )
        .first()
    )
    db.query(models.Booking).filter(models.Booking.booking_request_id.in_(request_ids)).update(
        {models.Booking.charge_dispute_hold: active},
        synchronize_session=False,
    )
    return active
