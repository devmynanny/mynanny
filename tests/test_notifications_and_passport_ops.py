import json
from datetime import date, timedelta

from app import models
from app.db import SessionLocal
from tests.test_accounting_reconciliation import _seed_admin
from tests.test_booking_flow_api import _auth, _seed_nanny, client


def test_user_can_only_read_and_mark_own_notifications():
    db = SessionLocal()
    try:
        nanny = _seed_nanny(db)
        user = db.query(models.User).filter(models.User.id == nanny.user_id).first()
        other = _seed_admin(db)
        own = models.InAppNotification(user_id=user.id, title="Booking confirmed", body="Your booking is ready.")
        foreign = models.InAppNotification(user_id=other.id, title="Private admin alert", body="Not for nanny.")
        db.add_all([own, foreign])
        db.commit()
        db.refresh(own)

        response = client.get("/notifications", headers=_auth(user))
        assert response.status_code == 200, response.text
        assert response.json()["unread_count"] == 1
        assert [row["title"] for row in response.json()["results"]] == ["Booking confirmed"]
        assert response.json()["results"][0]["action_url"] == "/bookings"

        marked = client.patch(f"/notifications/{own.id}/read", headers=_auth(user))
        assert marked.status_code == 200, marked.text
        assert client.get("/notifications", headers=_auth(user)).json()["unread_count"] == 0
    finally:
        db.close()


def test_passport_queue_flags_expiring_and_pending_replacement():
    db = SessionLocal()
    try:
        admin = _seed_admin(db)
        nanny = _seed_nanny(db, with_docs=False)
        profile = db.query(models.NannyProfile).filter(models.NannyProfile.nanny_id == nanny.id).first()
        expiry = date.today() + timedelta(days=60)
        profile.nationality = "Zimbabwean"
        profile.passport_expiry = expiry.isoformat()
        profile.passport_document_url = "/uploads/new-passport.pdf"
        profile.document_approvals_json = json.dumps({})
        db.commit()

        response = client.get("/admin/passport-compliance", headers=_auth(admin))
        assert response.status_code == 200, response.text
        row = next(item for item in response.json()["results"] if item["nanny_id"] == nanny.id)
        assert row["state"] == "awaiting_approval"
        assert row["replacement_pending"] is True
        assert row["passport_approved"] is False
        assert row["days_remaining"] == 60
    finally:
        db.close()


def test_passport_queue_requires_admin():
    db = SessionLocal()
    try:
        nanny = _seed_nanny(db)
        user = db.query(models.User).filter(models.User.id == nanny.user_id).first()
        response = client.get("/admin/passport-compliance", headers=_auth(user))
        assert response.status_code in (401, 403)
    finally:
        db.close()
