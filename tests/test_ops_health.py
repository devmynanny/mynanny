"""
Tests for admin ops endpoints: impersonation auditing, ops health snapshot,
webhook rejection logging.
"""

from datetime import datetime

from app import models
from app.db import SessionLocal

from tests.test_booking_flow_api import client, _auth, _seed_parent
from tests.test_accounting_reconciliation import _seed_admin


def _db():
    return SessionLocal()


def test_impersonation_is_audited():
    db = _db()
    try:
        admin = _seed_admin(db)
        target = _seed_parent(db)

        res = client.post(
            "/admin/impersonate",
            json={"user_id": target.id},
            headers=_auth(admin),
        )
        assert res.status_code == 200, res.text
        assert res.json().get("access_token")

        row = (
            db.query(models.AuditLog)
            .filter(
                models.AuditLog.action == "impersonate",
                models.AuditLog.target_user_id == target.id,
            )
            .order_by(models.AuditLog.id.desc())
            .first()
        )
        assert row is not None
        assert row.actor_user_id == admin.id

        # And it shows up in the impersonation listing.
        res = client.get("/admin/ops/impersonations", headers=_auth(admin))
        assert res.status_code == 200
        listed = [r for r in res.json()["results"] if r["target_user_id"] == target.id]
        assert listed and listed[0]["admin_user_id"] == admin.id
    finally:
        db.close()


def test_webhook_rejection_is_audited():
    db = _db()
    try:
        before = (
            db.query(models.AuditLog)
            .filter(models.AuditLog.action == "webhook_rejected")
            .count()
        )
        res = client.post(
            "/paystack/webhook",
            json={"event": "charge.success", "data": {}},
        )
        assert res.status_code == 400

        after = (
            db.query(models.AuditLog)
            .filter(models.AuditLog.action == "webhook_rejected")
            .count()
        )
        assert after == before + 1
    finally:
        db.close()


def test_ops_health_snapshot_shape_and_admin_only():
    db = _db()
    try:
        admin = _seed_admin(db)
        parent = _seed_parent(db)

        res = client.get("/admin/ops/health", headers=_auth(parent))
        assert res.status_code in (401, 403)

        res = client.get("/admin/ops/health", headers=_auth(admin))
        assert res.status_code == 200, res.text
        body = res.json()
        for key in (
            "failed_notifications_24h",
            "webhook_rejections_24h",
            "stuck_payouts",
            "refunds_awaiting_review",
            "stale_open_adverts",
            "impersonations_7d",
            "nannies_flagged_for_review",
        ):
            assert key in body["checks"]
        assert isinstance(body["attention_needed"], list)
        assert isinstance(body["ok"], bool)
    finally:
        db.close()


def test_ops_health_flags_refunds_awaiting_review():
    db = _db()
    try:
        admin = _seed_admin(db)
        parent = _seed_parent(db)
        from tests.test_accounting_reconciliation import _seed_paid_request
        from tests.test_booking_flow_api import _seed_nanny

        nanny = _seed_nanny(db)
        _seed_paid_request(
            db, parent, nanny, status="cancelled",
            refund_status="requested",
        )

        res = client.get("/admin/ops/health", headers=_auth(admin))
        body = res.json()
        assert body["checks"]["refunds_awaiting_review"] >= 1
        assert "refunds_awaiting_review" in body["attention_needed"]
        assert body["ok"] is False
    finally:
        db.close()
