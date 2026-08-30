"""
Tests for /accounting/reconciliation: clean rows pass, broken splits and
missing cancellation records are flagged.
"""

from datetime import datetime, timedelta

from app import models
from app.db import SessionLocal
from app.routers import public as public_router

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


def test_refunds_all_includes_paid_requests_without_a_refund_status():
    db = _db()
    try:
        admin = _seed_admin(db)
        parent = _seed_parent(db)
        nanny = _seed_nanny(db)
        req = _seed_paid_request(db, parent, nanny, refund_status=None)

        res = client.get("/admin/refunds?status=all", headers=_auth(admin))
        assert res.status_code == 200, res.text
        ids = {row["request_id"] for row in res.json()["results"]}
        assert req.id in ids
    finally:
        db.close()


def test_pending_payouts_are_limited_to_the_reporting_period():
    db = _db()
    try:
        admin = _seed_admin(db)
        parent = _seed_parent(db)
        nanny = _seed_nanny(db)
        now = datetime.utcnow()
        current_req = _seed_paid_request(db, parent, nanny, nanny_retained_cents=24000)
        old_req = _seed_paid_request(db, parent, nanny, nanny_retained_cents=24000)
        current_booking = models.Booking(
            booking_request_id=current_req.id,
            nanny_id=nanny.id,
            client_user_id=parent.id,
            day=now.date(),
            status="completed",
            price_cents=0,
            starts_at=now - timedelta(hours=4),
            ends_at=now,
            payout_hold_until=now,
        )
        old_booking = models.Booking(
            booking_request_id=old_req.id,
            nanny_id=nanny.id,
            client_user_id=parent.id,
            day=(now - timedelta(days=60)).date(),
            status="completed",
            price_cents=0,
            starts_at=now - timedelta(days=60, hours=4),
            ends_at=now - timedelta(days=60),
            payout_hold_until=now - timedelta(days=60),
        )
        db.add_all([current_booking, old_booking])
        db.commit()
        db.refresh(current_booking)
        db.refresh(old_booking)

        start = (now - timedelta(days=2)).date().isoformat()
        end = (now + timedelta(days=2)).date().isoformat()
        res = client.get(
            f"/admin/accounting/payouts?range=custom&start={start}&end={end}",
            headers=_auth(admin),
        )
        assert res.status_code == 200, res.text
        booking_ids = {row["booking_id"] for row in res.json()["results"]}
        assert current_booking.id in booking_ids
        assert old_booking.id not in booking_ids
    finally:
        db.close()


def test_admin_booking_overview_derives_zero_prices_from_the_paid_request():
    db = _db()
    try:
        admin = _seed_admin(db)
        parent = _seed_parent(db)
        nanny = _seed_nanny(db)
        req = _seed_paid_request(db, parent, nanny, total=45500, fee=10500, wage=35000)
        start = datetime.utcnow() + timedelta(days=1)
        short_booking = models.Booking(
            booking_request_id=req.id,
            nanny_id=nanny.id,
            client_user_id=parent.id,
            day=start.date(),
            status="accepted",
            price_cents=0,
            starts_at=start,
            ends_at=start + timedelta(hours=1),
        )
        long_booking = models.Booking(
            booking_request_id=req.id,
            nanny_id=nanny.id,
            client_user_id=parent.id,
            day=start.date(),
            status="accepted",
            price_cents=0,
            starts_at=start + timedelta(hours=2),
            ends_at=start + timedelta(hours=4),
        )
        db.add_all([short_booking, long_booking])
        db.commit()
        db.refresh(short_booking)
        db.refresh(long_booking)

        res = client.get("/admin/bookings/overview", headers=_auth(admin))
        assert res.status_code == 200, res.text
        rows = {
            row["booking_id"]: row
            for section in res.json().values()
            if isinstance(section, list)
            for row in section
            if isinstance(row, dict) and row.get("booking_id") in {short_booking.id, long_booking.id}
        }
        assert rows[short_booking.id]["price_cents"] + rows[long_booking.id]["price_cents"] == 45500
        assert rows[long_booking.id]["price_cents"] > rows[short_booking.id]["price_cents"]
    finally:
        db.close()


def test_admin_booking_calendar_keeps_completed_and_review_bookings_visible(monkeypatch):
    db = _db()
    try:
        admin = _seed_admin(db)
        parent = _seed_parent(db)
        nanny = _seed_nanny(db)
        req = _seed_paid_request(db, parent, nanny)
        req.status = "pending_admin"
        start = datetime.utcnow() - timedelta(hours=2)
        booking = models.Booking(
            booking_request_id=req.id,
            nanny_id=nanny.id,
            client_user_id=parent.id,
            day=start.date(),
            status="admin_review",
            price_cents=req.total_cents,
            starts_at=start,
            ends_at=start + timedelta(hours=1),
            check_in_at=start,
            check_out_at=start + timedelta(hours=1, minutes=20),
            overrun_status="queried",
        )
        db.add(booking)
        db.commit()
        db.refresh(booking)

        def fail_if_notifications_run(*_args, **_kwargs):
            raise AssertionError("calendar reads must not dispatch notifications")

        monkeypatch.setattr(
            public_router,
            "_mark_overdue_booking_requests_notified",
            fail_if_notifications_run,
        )
        res = client.get("/admin/bookings/overview", headers=_auth(admin))
        assert res.status_code == 200, res.text
        calendar_ids = {
            row["booking_id"]
            for day in res.json()["month_calendar"]["days"]
            for row in day["bookings"]
        }
        assert booking.id in calendar_ids
    finally:
        db.close()
