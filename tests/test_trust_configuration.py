import json
from datetime import date, datetime

from app import models
from app.db import SessionLocal
from app.services.trust import build_nanny_trust_badges, nanny_meets_required_trust
from tests.test_booking_flow_api import _auth, client


def _admin(db, level: str) -> models.User:
    user = models.User(
        name=f"{level.title()} Admin",
        role="admin",
        email=f"{level}_{datetime.utcnow().timestamp()}@example.com",
        password_hash="x",
        is_admin=True,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.add(models.AdminProfile(user_id=user.id, access_level=level, is_superadmin=level == "superadmin"))
    db.commit()
    return user


def test_badges_require_admin_approval_and_required_gate():
    db = SessionLocal()
    try:
        settings = db.query(models.AppSettings).filter(models.AppSettings.id == 1).first()
        if not settings:
            settings = models.AppSettings(id=1)
            db.add(settings)
            db.commit()
        original = settings.trust_config_json
        settings.trust_config_json = json.dumps({"badges": [
            {"key": "identity", "label": "Identity verified", "required": True, "parent_visible": True},
            {"key": "driver", "label": "Driver ready", "required": False, "parent_visible": False},
        ]})
        user = models.User(name="Badge Nanny", role="nanny", email=f"badge_{datetime.utcnow().timestamp()}@example.com", password_hash="x", is_active=True, phone="+27820000000", profile_photo_url="/photo.jpg")
        db.add(user); db.commit(); db.refresh(user)
        nanny = models.Nanny(user_id=user.id, approved=True, video_screening_complete=True)
        db.add(nanny); db.commit(); db.refresh(nanny)
        profile = models.NannyProfile(nanny_id=nanny.id, nationality="South African", date_of_birth=date(1990, 1, 1), sa_id_document_url="/id.jpg", drivers_license_document_url="/licence.jpg", is_approved=1, application_status="approved")
        db.add(profile); db.commit(); db.refresh(profile)

        badges = build_nanny_trust_badges(db, nanny, profile, user)
        assert badges[0]["ready"] is True
        assert badges[0]["earned"] is False
        assert nanny_meets_required_trust(badges) is False

        profile.document_approvals_json = json.dumps({"sa_id_document_url": {"approved": True}})
        db.commit()
        badges = build_nanny_trust_badges(db, nanny, profile, user)
        assert badges[0]["earned"] is True
        assert badges[1]["earned"] is False
        assert nanny_meets_required_trust(badges) is True
        settings.trust_config_json = original
        db.commit()
    finally:
        db.close()


def test_scoped_admin_access_and_trust_change_audit():
    db = SessionLocal()
    original = None
    try:
        operations = _admin(db, "operations")
        finance = _admin(db, "finance")
        superadmin = _admin(db, "superadmin")
        settings = db.query(models.AppSettings).filter(models.AppSettings.id == 1).first()
        original = settings.trust_config_json if settings else None

        assert client.get("/admin/trust-config", headers=_auth(operations)).status_code == 403
        assert client.get("/admin/accounting/summary", headers=_auth(operations)).status_code == 403
        assert client.get("/admin/accounting/summary", headers=_auth(finance)).status_code == 200
        assert client.get("/admin/audit-logs", headers=_auth(finance)).status_code == 403

        payload = {"badges": [{"key": "approved", "label": "My Nanny approved", "required": True, "parent_visible": True}]}
        response = client.put("/admin/trust-config", headers=_auth(superadmin), json=payload)
        assert response.status_code == 200, response.text
        audit = db.query(models.AuditLog).filter(models.AuditLog.action == "trust_config_update", models.AuditLog.actor_user_id == superadmin.id).order_by(models.AuditLog.id.desc()).first()
        assert audit is not None
        assert "badges" in (audit.changed_fields or "")
    finally:
        settings = db.query(models.AppSettings).filter(models.AppSettings.id == 1).first()
        if settings:
            settings.trust_config_json = original
            db.commit()
        db.close()
