"""
Estimate endpoint: must return pricing without a saved card (the card
requirement belongs at submission), and scale totals by requested count.
"""

from datetime import datetime, timedelta

from app import models
from app.db import SessionLocal

from tests.test_booking_flow_api import client, _auth, _seed_parent, _iso_z


def _db():
    return SessionLocal()


def _estimate_payload(requested_count=1):
    start = datetime.utcnow() + timedelta(days=2)
    end = start + timedelta(hours=4)
    return {
        "start_dt": _iso_z(start),
        "end_dt": _iso_z(end),
        "sleepover": False,
        "requested_nannies_count": requested_count,
        "kids_count": 1,
    }


def test_estimate_works_without_saved_card():
    db = _db()
    try:
        parent = _seed_parent(db)
        # The shared helper seeds a saved card; remove it for this test.
        parent.paystack_auth_code = None
        db.commit()
        assert not getattr(parent, "paystack_auth_code", None)
        res = client.post("/booking-requests/estimate", json=_estimate_payload(), headers=_auth(parent))
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["per_nanny_total_cents"] > 0
        assert data["selected_total_cents"] == data["per_nanny_total_cents"]
        assert "requires_payment_method" not in data
    finally:
        db.close()


def test_estimate_scales_by_requested_nannies_count():
    db = _db()
    try:
        parent = _seed_parent(db)
        one = client.post("/booking-requests/estimate", json=_estimate_payload(1), headers=_auth(parent)).json()
        three = client.post("/booking-requests/estimate", json=_estimate_payload(3), headers=_auth(parent)).json()
        assert three["selected_count"] == 3
        assert three["selected_total_cents"] == one["per_nanny_total_cents"] * 3
    finally:
        db.close()


def test_estimate_rejects_past_window():
    db = _db()
    try:
        parent = _seed_parent(db)
        start = datetime.utcnow() - timedelta(days=1)
        payload = {
            "start_dt": _iso_z(start),
            "end_dt": _iso_z(start + timedelta(hours=4)),
            "requested_nannies_count": 1,
        }
        res = client.post("/booking-requests/estimate", json=payload, headers=_auth(parent))
        assert res.status_code == 409
    finally:
        db.close()


def test_estimate_requires_parent_role():
    res = client.post("/booking-requests/estimate", json=_estimate_payload())
    assert res.status_code in (401, 403)
