"""
Tests for stale advert expiry: the sweep service, the nanny listing filter,
and the never-touch-accepted guarantee.
"""

from datetime import datetime, timedelta

from app import models
from app.db import SessionLocal
from app.services.advert_expiry import (
    EXPIRED_ADMIN_REASON,
    expire_stale_booking_requests,
    is_request_expired,
)

from tests.test_booking_flow_api import (
    client,
    _auth,
    _seed_parent,
    _seed_nanny,
    _add_availability,
    _create_request_payload,
    _future_window,
    _iso_z,
)


def _db():
    return SessionLocal()


def _seed_request(db, parent, nanny, start, end, *, status="tbc",
                  response_status="pending") -> models.BookingRequest:
    req = models.BookingRequest(
        id=int(datetime.utcnow().timestamp() * 1000000) % 900000000,
        parent_user_id=parent.id,
        nanny_id=nanny.id,
        status=status,
        start_dt=_iso_z(start),
        end_dt=_iso_z(end),
        requested_starts_at=start,
        requested_ends_at=end,
        nanny_response_status=response_status,
    )
    req.group_id = req.id
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


def test_is_request_expired_true_for_past_open_advert():
    db = _db()
    try:
        parent = _seed_parent(db)
        nanny = _seed_nanny(db)
        start = datetime.utcnow() - timedelta(hours=3)
        req = _seed_request(db, parent, nanny, start, start + timedelta(hours=2))
        assert is_request_expired(req) is True
    finally:
        db.close()


def test_is_request_expired_false_for_future_advert():
    db = _db()
    try:
        parent = _seed_parent(db)
        nanny = _seed_nanny(db)
        start = datetime.utcnow() + timedelta(days=2)
        req = _seed_request(db, parent, nanny, start, start + timedelta(hours=2))
        assert is_request_expired(req) is False
    finally:
        db.close()


def test_is_request_expired_false_for_accepted_request():
    db = _db()
    try:
        parent = _seed_parent(db)
        nanny = _seed_nanny(db)
        start = datetime.utcnow() - timedelta(hours=3)
        req = _seed_request(
            db, parent, nanny, start, start + timedelta(hours=2),
            status="tbc", response_status="accepted",
        )
        assert is_request_expired(req) is False
    finally:
        db.close()


def test_sweep_marks_expired_and_leaves_future_untouched():
    db = _db()
    try:
        parent = _seed_parent(db)
        nanny = _seed_nanny(db)
        past_start = datetime.utcnow() - timedelta(hours=5)
        future_start = datetime.utcnow() + timedelta(days=2)

        stale = _seed_request(db, parent, nanny, past_start, past_start + timedelta(hours=2))
        fresh = _seed_request(db, parent, nanny, future_start, future_start + timedelta(hours=2))
        accepted_stale = _seed_request(
            db, parent, nanny, past_start, past_start + timedelta(hours=2),
            response_status="accepted",
        )

        count = expire_stale_booking_requests(db)
        assert count >= 1

        db.expire_all()
        stale = db.query(models.BookingRequest).get(stale.id)
        fresh = db.query(models.BookingRequest).get(fresh.id)
        accepted_stale = db.query(models.BookingRequest).get(accepted_stale.id)

        assert stale.status == "rejected"
        assert stale.admin_reason == EXPIRED_ADMIN_REASON
        assert stale.admin_decided_at is not None

        assert fresh.status == "tbc"
        assert accepted_stale.status == "tbc"
        assert accepted_stale.admin_reason != EXPIRED_ADMIN_REASON
    finally:
        db.close()


def test_nanny_listing_hides_expired_adverts_before_sweep():
    db = _db()
    try:
        parent = _seed_parent(db)
        nanny = _seed_nanny(db)
        nanny_user = db.query(models.User).filter(models.User.id == nanny.user_id).first()

        past_start = datetime.utcnow() - timedelta(hours=5)
        stale = _seed_request(db, parent, nanny, past_start, past_start + timedelta(hours=2))

        future_start, future_end = _future_window()
        _add_availability(db, nanny.id, future_start, future_end)
        res = client.post(
            "/booking-requests",
            json=_create_request_payload(nanny.id, future_start, future_end),
            headers=_auth(parent),
        )
        assert res.status_code == 200
        fresh_id = res.json()["booking_request_id"]

        res = client.get("/nannies/me/booking-requests", headers=_auth(nanny_user))
        assert res.status_code == 200
        ids = {r["id"] for r in res.json()["results"]}
        assert fresh_id in ids
        assert stale.id not in ids
    finally:
        db.close()
