"""
Tests for the 5-hour pre-booking buffer rule and the 100m duty geofence.

Rules (APP_RULES.md sections 5 and 7):
- A nanny with an active booking is unavailable for the 5 hours before that
  booking starts, EXCEPT when the new request is from the same parent.
- Check-in/check-out require being within 100m of the booking location.
"""

from datetime import datetime, timedelta

from app import models
from app.db import SessionLocal
from app.routers.public import _is_nanny_available

from tests.test_booking_flow_api import (
    client,
    _auth,
    _seed_parent,
    _seed_nanny,
    _add_availability,
    _iso_z,
)


def _db():
    return SessionLocal()


def _seed_booking(db, nanny, parent, start, end, *, lat=None, lng=None) -> models.Booking:
    booking = models.Booking(
        nanny_id=nanny.id,
        client_user_id=parent.id,
        day=start.date(),
        status="approved",
        price_cents=0,
        starts_at=start,
        ends_at=end,
        start_dt=_iso_z(start),
        end_dt=_iso_z(end),
        lat=lat,
        lng=lng,
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return booking


def _day_window(days_ahead: int, start_hour: int, end_hour: int):
    day = (datetime.utcnow() + timedelta(days=days_ahead)).replace(
        hour=start_hour, minute=0, second=0, microsecond=0
    )
    return day, day.replace(hour=end_hour)


# ---------------------------------------------------------------------------
# 5-hour pre-booking buffer
# ---------------------------------------------------------------------------

def test_booking_overlap_blocks_availability():
    db = _db()
    try:
        parent = _seed_parent(db)
        other_parent = _seed_parent(db)
        nanny = _seed_nanny(db)
        start, end = _day_window(3, 9, 17)
        _add_availability(db, nanny.id, start.replace(hour=6), end.replace(hour=23))
        _seed_booking(db, nanny, parent, start, end)

        assert _is_nanny_available(db, nanny.id, start, end, other_parent.id) is False
    finally:
        db.close()


def test_five_hour_buffer_blocks_different_parent():
    db = _db()
    try:
        parent = _seed_parent(db)
        other_parent = _seed_parent(db)
        nanny = _seed_nanny(db)

        booked_start, booked_end = _day_window(3, 14, 18)
        _add_availability(
            db, nanny.id,
            booked_start.replace(hour=6), booked_end.replace(hour=23),
        )
        _seed_booking(db, nanny, parent, booked_start, booked_end)

        # Request 10:00-13:00 same day: inside the 5h buffer (buffer covers
        # 09:00-14:00) -> blocked for a DIFFERENT parent.
        req_start = booked_start.replace(hour=10)
        req_end = booked_start.replace(hour=13)
        assert _is_nanny_available(db, nanny.id, req_start, req_end, other_parent.id) is False
    finally:
        db.close()


def test_five_hour_buffer_waived_for_same_parent():
    db = _db()
    try:
        parent = _seed_parent(db)
        nanny = _seed_nanny(db)

        booked_start, booked_end = _day_window(3, 14, 18)
        _add_availability(
            db, nanny.id,
            booked_start.replace(hour=6), booked_end.replace(hour=23),
        )
        _seed_booking(db, nanny, parent, booked_start, booked_end)

        req_start = booked_start.replace(hour=10)
        req_end = booked_start.replace(hour=13)
        # Same parent: buffer does not apply.
        assert _is_nanny_available(db, nanny.id, req_start, req_end, parent.id) is True
    finally:
        db.close()


def test_outside_buffer_available_for_any_parent():
    db = _db()
    try:
        parent = _seed_parent(db)
        other_parent = _seed_parent(db)
        nanny = _seed_nanny(db)

        booked_start, booked_end = _day_window(3, 14, 18)
        _add_availability(
            db, nanny.id,
            booked_start.replace(hour=6), booked_end.replace(hour=23),
        )
        _seed_booking(db, nanny, parent, booked_start, booked_end)

        # 06:00-08:00 ends more than 5h before the 14:00 booking (buffer
        # starts 09:00) -> available even for a different parent.
        req_start = booked_start.replace(hour=6)
        req_end = booked_start.replace(hour=8)
        assert _is_nanny_available(db, nanny.id, req_start, req_end, other_parent.id) is True
    finally:
        db.close()


def test_no_availability_rows_means_unavailable():
    db = _db()
    try:
        parent = _seed_parent(db)
        nanny = _seed_nanny(db)
        start, end = _day_window(3, 9, 12)
        assert _is_nanny_available(db, nanny.id, start, end, parent.id) is False
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 100m duty geofence
# ---------------------------------------------------------------------------

# Johannesburg CBD reference point.
JHB_LAT, JHB_LNG = -26.2041, 28.0473
# ~1.1km north (approx 0.01 degrees latitude).
FAR_LAT = JHB_LAT + 0.01


def test_check_in_blocked_outside_100m():
    db = _db()
    try:
        parent = _seed_parent(db)
        nanny = _seed_nanny(db)
        nanny_user = db.query(models.User).filter(models.User.id == nanny.user_id).first()
        start = datetime.utcnow() - timedelta(minutes=30)
        end = start + timedelta(hours=4)
        booking = _seed_booking(
            db, nanny, parent, start, end, lat=JHB_LAT, lng=JHB_LNG,
        )

        res = client.post(
            f"/nannies/me/bookings/{booking.id}/check-in",
            json={"lat": FAR_LAT, "lng": JHB_LNG},
            headers=_auth(nanny_user),
        )
        assert res.status_code == 409

        db.expire_all()
        booking = db.query(models.Booking).get(booking.id)
        assert booking.check_in_at is None
    finally:
        db.close()


def test_check_in_allowed_within_100m_and_sets_status():
    db = _db()
    try:
        parent = _seed_parent(db)
        nanny = _seed_nanny(db)
        nanny_user = db.query(models.User).filter(models.User.id == nanny.user_id).first()
        start = datetime.utcnow() - timedelta(minutes=30)
        end = start + timedelta(hours=4)
        booking = _seed_booking(
            db, nanny, parent, start, end, lat=JHB_LAT, lng=JHB_LNG,
        )

        res = client.post(
            f"/nannies/me/bookings/{booking.id}/check-in",
            json={"lat": JHB_LAT, "lng": JHB_LNG},
            headers=_auth(nanny_user),
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["ok"] is True
        assert body["check_in_at"]
        assert body["check_in_distance_m"] <= 100

        db.expire_all()
        booking = db.query(models.Booking).get(booking.id)
        assert booking.check_in_at is not None
        assert booking.status == "accepted"  # approved -> accepted on check-in
    finally:
        db.close()


def test_check_in_is_idempotent():
    db = _db()
    try:
        parent = _seed_parent(db)
        nanny = _seed_nanny(db)
        nanny_user = db.query(models.User).filter(models.User.id == nanny.user_id).first()
        start = datetime.utcnow() - timedelta(minutes=30)
        end = start + timedelta(hours=4)
        booking = _seed_booking(
            db, nanny, parent, start, end, lat=JHB_LAT, lng=JHB_LNG,
        )

        first = client.post(
            f"/nannies/me/bookings/{booking.id}/check-in",
            json={"lat": JHB_LAT, "lng": JHB_LNG},
            headers=_auth(nanny_user),
        )
        second = client.post(
            f"/nannies/me/bookings/{booking.id}/check-in",
            json={"lat": JHB_LAT, "lng": JHB_LNG},
            headers=_auth(nanny_user),
        )
        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json()["check_in_at"] == first.json()["check_in_at"]
    finally:
        db.close()
