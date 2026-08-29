"""Regression tests for client charge queries and partial refunds.

Paystack and notifications are mocked throughout: this suite must never move
money or contact a real parent while exercising finance decisions.
"""

from datetime import datetime, timedelta
import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

from app import models
from app.db import SessionLocal
from app.main import app
from app.routers import admin as admin_router
from app.routers import public as public_router
from app.routers.public import _create_access_token


client = TestClient(app)
PAYSTACK_SECRET = "sk_test_charge_disputes"


def _auth(user: models.User) -> dict[str, str]:
    return {"Authorization": f"Bearer {_create_access_token(user)}"}


def _seed_user(db, *, role: str, name: str) -> models.User:
    user = models.User(
        name=name,
        role=role,
        email=f"{role}_{datetime.utcnow().timestamp()}@example.com",
        password_hash="x",
        is_admin=role == "admin",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _seed_paid_booking(db):
    parent = _seed_user(db, role="parent", name="Charge Query Parent")
    db.add(models.ParentProfile(user_id=parent.id))

    nanny_user = _seed_user(db, role="nanny", name="Charge Query Nanny")
    nanny = models.Nanny(user_id=nanny_user.id, approved=True)
    db.add(nanny)
    db.flush()

    starts_at = (datetime.utcnow() + timedelta(days=2)).replace(microsecond=0)
    ends_at = starts_at + timedelta(hours=5)
    request_id = int(datetime.utcnow().timestamp() * 1_000_000)
    booking_request = models.BookingRequest(
        id=request_id,
        parent_user_id=parent.id,
        nanny_id=nanny.id,
        status="approved",
        start_dt=starts_at.isoformat() + "Z",
        end_dt=ends_at.isoformat() + "Z",
        requested_starts_at=starts_at,
        requested_ends_at=ends_at,
        payment_status="paid",
        paid_at=datetime.utcnow(),
        wage_cents=10_000,
        booking_fee_cents=3_000,
        total_cents=13_000,
        paystack_reference=f"BR-{request_id}",
        paystack_transaction_id=f"TX-{request_id}",
    )
    db.add(booking_request)
    db.flush()
    booking = models.Booking(
        booking_request_id=booking_request.id,
        nanny_id=nanny.id,
        client_user_id=parent.id,
        day=starts_at.date(),
        status="approved",
        price_cents=10_000,
        starts_at=starts_at,
        ends_at=ends_at,
    )
    db.add(booking)
    db.commit()
    db.refresh(booking_request)
    db.refresh(booking)
    return parent, booking_request, booking


def _open_query(db, parent, booking_request, *, amount_cents=4_000):
    response = client.post(
        f"/parents/me/booking-requests/{booking_request.id}/charge-disputes",
        headers=_auth(parent),
        json={
            "line_item": "nanny_wage",
            "amount_cents": amount_cents,
            "reason": "Nanny arrived late",
            "details": "Please review the payable time for this booking.",
        },
    )
    assert response.status_code == 200, response.text
    dispute = (
        db.query(models.ChargeDispute)
        .filter(models.ChargeDispute.id == response.json()["id"])
        .first()
    )
    assert dispute is not None
    return dispute


@pytest.fixture(autouse=True)
def _isolate_external_services(monkeypatch):
    monkeypatch.setenv("PAYSTACK_SECRET_KEY", PAYSTACK_SECRET)
    monkeypatch.setattr(public_router, "notify", lambda *args, **kwargs: None)
    monkeypatch.setattr(admin_router, "notify", lambda *args, **kwargs: None)
    yield


@pytest.fixture()
def db():
    session = SessionLocal()
    yield session
    session.close()


def test_parent_can_query_a_paid_line_item_and_duplicate_is_blocked(db):
    parent, booking_request, booking = _seed_paid_booking(db)
    dispute = _open_query(db, parent, booking_request)

    db.refresh(booking)
    assert dispute.status == "open"
    assert dispute.charge_amount_cents == 10_000
    assert dispute.disputed_amount_cents == 4_000
    assert booking.charge_dispute_hold is True

    duplicate = client.post(
        f"/parents/me/booking-requests/{booking_request.id}/charge-disputes",
        headers=_auth(parent),
        json={
            "line_item": "nanny_wage",
            "amount_cents": 1_000,
            "reason": "Same charge again",
        },
    )
    assert duplicate.status_code == 400
    assert "active query" in duplicate.json()["detail"]


def test_finance_partial_refund_stays_held_until_paystack_webhook(db, monkeypatch):
    parent, booking_request, booking = _seed_paid_booking(db)
    dispute = _open_query(db, parent, booking_request)
    admin = _seed_user(db, role="admin", name="Finance Admin")
    refund_calls = []

    def fake_refund(transaction, amount_cents):
        refund_calls.append((transaction, amount_cents))
        return True, {"data": {"reference": "RF-PARTIAL-1"}}

    monkeypatch.setattr(admin_router, "create_refund", fake_refund)
    approved = client.post(
        f"/admin/charge-disputes/{dispute.id}/approve",
        headers=_auth(admin),
        json={"amount_cents": 2_500, "reason": "Refund the late-arrival portion"},
    )
    assert approved.status_code == 200, approved.text
    assert refund_calls == [(booking_request.paystack_transaction_id, 2_500)]

    db.refresh(dispute)
    db.refresh(booking)
    assert dispute.status == "refund_requested"
    assert dispute.approved_refund_cents == 2_500
    assert dispute.paystack_refund_reference == "RF-PARTIAL-1"
    assert booking.charge_dispute_hold is True

    payload = {"event": "refund.processed", "data": {"reference": "RF-PARTIAL-1"}}
    raw = json.dumps(payload).encode()
    signature = hmac.new(PAYSTACK_SECRET.encode(), raw, hashlib.sha512).hexdigest()
    processed = client.post(
        "/paystack/webhook",
        content=raw,
        headers={"x-paystack-signature": signature, "content-type": "application/json"},
    )
    assert processed.status_code == 200, processed.text

    db.refresh(dispute)
    db.refresh(booking)
    assert dispute.status == "refunded"
    assert dispute.refunded_at is not None
    assert booking.charge_dispute_hold is False


def test_finance_denial_releases_the_nanny_payout_hold(db):
    parent, booking_request, booking = _seed_paid_booking(db)
    dispute = _open_query(db, parent, booking_request)
    admin = _seed_user(db, role="admin", name="Finance Admin")

    denied = client.post(
        f"/admin/charge-disputes/{dispute.id}/deny",
        headers=_auth(admin),
        json={"reason": "The attendance record confirms the full charge"},
    )
    assert denied.status_code == 200, denied.text

    db.refresh(dispute)
    db.refresh(booking)
    assert dispute.status == "denied"
    assert dispute.resolution_reason == "The attendance record confirms the full charge"
    assert booking.charge_dispute_hold is False
