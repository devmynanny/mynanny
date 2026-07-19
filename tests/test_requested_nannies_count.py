"""
Tests for the structured requested_nannies_count column on booking_requests.

Covers: column set on single and bulk creation, sanitization of bad values,
and the legacy client_notes backfill parser.
"""

from datetime import datetime, timedelta

from sqlalchemy import text

from app import models
from app.db import engine, _backfill_requested_nannies_count

from tests.test_booking_flow_api import (  # reuse seeded-flow helpers
    client,
    _auth,
    _seed_parent,
    _seed_nanny,
    _add_availability,
    _create_request_payload,
    _future_window,
)
from app.db import SessionLocal


def _db():
    return SessionLocal()


def test_single_create_stores_requested_nannies_count():
    db = _db()
    try:
        parent = _seed_parent(db)
        nanny = _seed_nanny(db)
        start, end = _future_window()
        _add_availability(db, nanny.id, start, end)

        payload = _create_request_payload(nanny.id, start, end)
        payload["requested_nannies_count"] = 3
        res = client.post("/booking-requests", json=payload, headers=_auth(parent))
        assert res.status_code == 200, res.text

        req = db.query(models.BookingRequest).filter(
            models.BookingRequest.id == res.json()["booking_request_id"]
        ).first()
        assert req.requested_nannies_count == 3
        # Human-readable prefix still present for backward compatibility.
        assert (req.client_notes or "").startswith("Nannies requested: 3")
    finally:
        db.close()


def test_create_defaults_to_one_nanny():
    db = _db()
    try:
        parent = _seed_parent(db)
        nanny = _seed_nanny(db)
        start, end = _future_window()
        _add_availability(db, nanny.id, start, end)

        res = client.post(
            "/booking-requests",
            json=_create_request_payload(nanny.id, start, end),
            headers=_auth(parent),
        )
        assert res.status_code == 200
        req = db.query(models.BookingRequest).filter(
            models.BookingRequest.id == res.json()["booking_request_id"]
        ).first()
        assert req.requested_nannies_count == 1
    finally:
        db.close()


def test_invalid_count_sanitized_to_one():
    db = _db()
    try:
        parent = _seed_parent(db)
        nanny = _seed_nanny(db)
        start, end = _future_window()
        _add_availability(db, nanny.id, start, end)

        payload = _create_request_payload(nanny.id, start, end)
        payload["requested_nannies_count"] = -5
        res = client.post("/booking-requests", json=payload, headers=_auth(parent))
        assert res.status_code == 200
        req = db.query(models.BookingRequest).filter(
            models.BookingRequest.id == res.json()["booking_request_id"]
        ).first()
        assert req.requested_nannies_count == 1
    finally:
        db.close()


def test_admin_list_exposes_requested_nannies_count():
    db = _db()
    try:
        parent = _seed_parent(db)
        nanny = _seed_nanny(db)
        start, end = _future_window()
        _add_availability(db, nanny.id, start, end)

        payload = _create_request_payload(nanny.id, start, end)
        payload["requested_nannies_count"] = 2
        res = client.post("/booking-requests", json=payload, headers=_auth(parent))
        assert res.status_code == 200
        created_id = res.json()["booking_request_id"]

        admin = models.User(
            name="Admin",
            role="admin",
            email=f"admin_{datetime.utcnow().timestamp()}@example.com",
            password_hash="x",
            is_admin=True,
            is_active=True,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)

        res = client.get("/admin/booking-requests?status=tbc", headers=_auth(admin))
        assert res.status_code == 200
        rows = {r["id"]: r for r in res.json()["results"]}
        assert rows[created_id]["requested_nannies_count"] == 2
    finally:
        db.close()


def test_backfill_parses_legacy_notes_prefix():
    db = _db()
    try:
        parent = _seed_parent(db)
        nanny = _seed_nanny(db)
        start = datetime.utcnow() + timedelta(days=3)
        end = start + timedelta(hours=4)

        legacy = models.BookingRequest(
            id=990001,
            parent_user_id=parent.id,
            nanny_id=nanny.id,
            status="tbc",
            requested_starts_at=start,
            requested_ends_at=end,
            client_notes="Nannies requested: 4\nAdditional notes: legacy row",
            requested_nannies_count=None,
        )
        no_prefix = models.BookingRequest(
            id=990002,
            parent_user_id=parent.id,
            nanny_id=nanny.id,
            status="tbc",
            requested_starts_at=start,
            requested_ends_at=end,
            client_notes="Additional notes: no prefix here",
            requested_nannies_count=None,
        )
        db.add_all([legacy, no_prefix])
        db.commit()

        # The ORM default fills the column on insert; real legacy rows
        # (created before the column existed) are NULL. Simulate that.
        with engine.begin() as conn:
            conn.execute(text(
                "UPDATE booking_requests SET requested_nannies_count = NULL "
                "WHERE id IN (990001, 990002)"
            ))

        with engine.begin() as conn:
            _backfill_requested_nannies_count(conn)

        db.expire_all()
        assert db.query(models.BookingRequest).get(990001).requested_nannies_count == 4
        assert db.query(models.BookingRequest).get(990002).requested_nannies_count == 1
    finally:
        db.close()
