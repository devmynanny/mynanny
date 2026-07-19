"""
Tests for the Paystack webhook: signature enforcement and charge.success
payment reconciliation.
"""

import hashlib
import hmac
import json
from datetime import datetime, timedelta

from app import models
from app.db import SessionLocal

from tests.test_booking_flow_api import client, _seed_parent, _seed_nanny, _iso_z


SECRET = "sk_test_webhook_secret"


def _db():
    return SessionLocal()


def _signed_post(payload: dict, secret: str = SECRET):
    body = json.dumps(payload).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha512).hexdigest()
    return client.post(
        "/paystack/webhook",
        content=body,
        headers={
            "content-type": "application/json",
            "x-paystack-signature": signature,
        },
    )


def _seed_pending_request(db) -> models.BookingRequest:
    parent = _seed_parent(db)
    nanny = _seed_nanny(db)
    start = datetime.utcnow() + timedelta(days=2)
    end = start + timedelta(hours=4)
    req = models.BookingRequest(
        id=int(datetime.utcnow().timestamp() * 1000000) % 900000000,
        parent_user_id=parent.id,
        nanny_id=nanny.id,
        status="tbc",
        start_dt=_iso_z(start),
        end_dt=_iso_z(end),
        requested_starts_at=start,
        requested_ends_at=end,
        payment_status="pending_payment",
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


def test_webhook_rejects_missing_signature(monkeypatch):
    monkeypatch.setenv("PAYSTACK_SECRET_KEY", SECRET)
    res = client.post(
        "/paystack/webhook",
        json={"event": "charge.success", "data": {}},
    )
    assert res.status_code == 400


def test_webhook_rejects_bad_signature(monkeypatch):
    monkeypatch.setenv("PAYSTACK_SECRET_KEY", SECRET)
    body = json.dumps({"event": "charge.success", "data": {}}).encode()
    res = client.post(
        "/paystack/webhook",
        content=body,
        headers={
            "content-type": "application/json",
            "x-paystack-signature": "deadbeef" * 16,
        },
    )
    assert res.status_code == 400


def test_webhook_rejects_when_secret_not_configured(monkeypatch):
    monkeypatch.delenv("PAYSTACK_SECRET_KEY", raising=False)
    res = _signed_post({"event": "charge.success", "data": {}})
    assert res.status_code == 400


def test_webhook_charge_success_marks_request_paid(monkeypatch):
    monkeypatch.setenv("PAYSTACK_SECRET_KEY", SECRET)
    db = _db()
    try:
        req = _seed_pending_request(db)
        res = _signed_post({
            "event": "charge.success",
            "data": {
                "reference": f"BR-{req.id}-TEST",
                "id": 987654,
                "metadata": {"booking_request_id": req.id},
            },
        })
        assert res.status_code == 200

        db.expire_all()
        updated = db.query(models.BookingRequest).get(req.id)
        assert updated.payment_status == "paid"
        assert updated.paid_at is not None
        assert updated.paystack_reference == f"BR-{req.id}-TEST"
        assert updated.paystack_transaction_id == "987654"
    finally:
        db.close()


def test_webhook_unknown_event_is_acknowledged_without_changes(monkeypatch):
    monkeypatch.setenv("PAYSTACK_SECRET_KEY", SECRET)
    db = _db()
    try:
        req = _seed_pending_request(db)
        res = _signed_post({"event": "subscription.create", "data": {}})
        assert res.status_code == 200

        db.expire_all()
        updated = db.query(models.BookingRequest).get(req.id)
        assert updated.payment_status == "pending_payment"
    finally:
        db.close()
