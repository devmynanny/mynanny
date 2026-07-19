"""
Tests for /accounting/reconciliation: clean rows pass, broken splits and
missing cancellation records are flagged.
"""

from datetime import datetime, timedelta

from app import models
from app.db import SessionLocal

from tests.test_booking_flow_api import client, _auth, _seed_parent, _seed_nanny, _iso_z


def _db():
    return SessionLocal()


def _seed_admin(db) -> models.User:
    admin = models.User(
        name="Recon Admin",
        role="admin",
        email=f"admin_{datetime.utcnow().timestamp()}@example.com",
        password_hash="x",
        is_admin=True,
        is_active=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


def _seed_paid_request(db, parent, nanny, *, total=33000, fee=9000, wage=24000,
                       status="approved", **extra) -> models.BookingRequest:
    start = datetime.utcnow() + timedelta(days=1)
    req = models.BookingRequest(
        id=int(datetime.utcnow().timestamp() * 1000000) % 900000000,
        parent_user_id=parent.id,
        nanny_id=nanny.id,
        status=status,
        requested_starts_at=start,
        requested_ends_at=start + timedelta(hours=4),
        start_dt=_iso_z(start),
        end_dt=_iso_z(start + timedelta(hours=4)),
        payment_status="paid",
        paid_at=datetime.utcnow(),
        total_cents=total,
        booking_fee_cents=fee,
        wage_cents=wage,
        **extra,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


def test_clean_paid_request_has_no_problems():
    db = _db()
    try:
        admin = _seed_admin(db)
        parent = _seed_parent(db)
        nanny = _seed_nanny(db)
        req = _seed_paid_request(db, parent, nanny)

        res = client.get("/admin/accounting/reconciliation?range=day", headers=_auth(admin))
        assert res.status_code == 200, res.text
        rows = {r["booking_request_id"]: r for r in res.json()["results"]}
        assert req.id in rows
        assert rows[req.id]["problems"] == []
    finally:
        db.close()


def test_fee_plus_wage_mismatch_is_flagged():
    db = _db()
    try:
        admin = _seed_admin(db)
        parent = _seed_parent(db)
        nanny = _seed_nanny(db)
        req = _seed_paid_request(db, parent, nanny, total=33000, fee=9000, wage=20000)

        res = client.get("/admin/accounting/reconciliation?range=day", headers=_auth(admin))
        rows = {r["booking_request_id"]: r for r in res.json()["results"]}
        assert "fee_plus_wage_mismatch" in rows[req.id]["problems"]
    finally:
        db.close()


def test_cancelled_paid_without_split_is_flagged():
    db = _db()
    try:
        admin = _seed_admin(db)
        parent = _seed_parent(db)
        nanny = _seed_nanny(db)
        req = _seed_paid_request(db, parent, nanny, status="cancelled")

        res = client.get("/admin/accounting/reconciliation?range=day", headers=_auth(admin))
        rows = {r["booking_request_id"]: r for r in res.json()["results"]}
        assert "cancelled_paid_but_no_split_recorded" in rows[req.id]["problems"]
    finally:
        db.close()


def test_correct_cancellation_split_passes():
    db = _db()
    try:
        admin = _seed_admin(db)
        parent = _seed_parent(db)
        nanny = _seed_nanny(db)
        # Scenario C split on total 33000 / fee 9000 / wage 24000:
        # company keeps 6750, nanny keeps 7200, refund 19050.
        req = _seed_paid_request(
            db, parent, nanny, status="cancelled",
            company_retained_cents=6750,
            nanny_retained_cents=7200,
            refund_cents=19050,
            refund_status="processed",
            refund_processed_at=datetime.utcnow(),
        )

        res = client.get("/admin/accounting/reconciliation?range=day", headers=_auth(admin))
        rows = {r["booking_request_id"]: r for r in res.json()["results"]}
        assert rows[req.id]["problems"] == []
    finally:
        db.close()


def test_only_mismatches_filter():
    db = _db()
    try:
        admin = _seed_admin(db)
        parent = _seed_parent(db)
        nanny = _seed_nanny(db)
        good = _seed_paid_request(db, parent, nanny)
        bad = _seed_paid_request(db, parent, nanny, total=0)

        res = client.get(
            "/admin/accounting/reconciliation?range=day&only_mismatches=true",
            headers=_auth(admin),
        )
        ids = {r["booking_request_id"] for r in res.json()["results"]}
        assert bad.id in ids
        assert good.id not in ids
    finally:
        db.close()


def test_requires_admin():
    db = _db()
    try:
        parent = _seed_parent(db)
        res = client.get("/admin/accounting/reconciliation", headers=_auth(parent))
        assert res.status_code in (401, 403)
    finally:
        db.close()
