"""
Tests for the model-level status write guards.

Every status column now validates its value on assignment against the
central vocabularies in app/services/booking_status.py. A rogue status
string must raise immediately instead of silently entering the database.
"""

from datetime import datetime, timedelta

import pytest

from app import models
from app.services.booking_status import (
    BOOKING_WRITE_STATUSES,
    PAYMENT_WRITE_STATUSES,
    REQUEST_WRITE_STATUSES,
    RESPONSE_WRITE_STATUSES,
)


def _request(**overrides):
    start = datetime.utcnow() + timedelta(days=1)
    base = dict(
        id=1,
        parent_user_id=1,
        nanny_id=1,
        requested_starts_at=start,
        requested_ends_at=start + timedelta(hours=4),
    )
    base.update(overrides)
    return models.BookingRequest(**base)


def test_request_accepts_all_allowed_statuses():
    req = _request()
    for status in REQUEST_WRITE_STATUSES:
        req.status = status  # must not raise


def test_request_rejects_unknown_status():
    req = _request()
    with pytest.raises(ValueError):
        req.status = "declined"  # legacy dead-code value, forbidden by DB CHECK
    with pytest.raises(ValueError):
        req.status = "totally_new_status"


def test_request_response_status_vocabulary():
    req = _request()
    for status in RESPONSE_WRITE_STATUSES:
        req.nanny_response_status = status
    with pytest.raises(ValueError):
        req.nanny_response_status = "maybe"


def test_request_payment_status_vocabulary():
    req = _request()
    for status in PAYMENT_WRITE_STATUSES:
        req.payment_status = status
    with pytest.raises(ValueError):
        req.payment_status = "failed"  # failure is admin_reason, never payment_status


def test_booking_status_vocabulary():
    booking = models.Booking(
        nanny_id=1,
        client_user_id=1,
        day=datetime.utcnow().date(),
        price_cents=0,
    )
    for status in BOOKING_WRITE_STATUSES:
        booking.status = status
    with pytest.raises(ValueError):
        booking.status = "some_new_status"


def test_constructor_also_validates():
    with pytest.raises(ValueError):
        _request(status="not_a_status")
