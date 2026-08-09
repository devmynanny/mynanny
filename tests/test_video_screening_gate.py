from datetime import datetime
import json

from app import models
from app.db import SessionLocal
from tests.test_booking_flow_api import _auth, _seed_nanny, client


def test_nanny_must_upload_all_four_clips_before_submission():
    db = SessionLocal()
    try:
        nanny = _seed_nanny(db, approved=False, with_docs=True)
        user = db.query(models.User).filter(models.User.id == nanny.user_id).first()
        profile = db.query(models.NannyProfile).filter(models.NannyProfile.nanny_id == nanny.id).first()
        profile.lat = -25.7479
        profile.lng = 28.2293
        db.commit()

        incomplete = client.post("/nannies/me/video-screening/complete", headers=_auth(user))
        assert incomplete.status_code == 409

        nanny.video_screening_json = json.dumps([
            {"question_index": index, "url": f"/static/test-q{index}.webm"}
            for index in range(4)
        ])
        db.commit()

        submitted = client.post("/nannies/me/video-screening/complete", headers=_auth(user))
        assert submitted.status_code == 200
        assert submitted.json()["video_screening_complete"] is True

        db.refresh(nanny)
        clips = json.loads(nanny.video_screening_json)
        assert {clip["question_index"] for clip in clips} == {0, 1, 2, 3}
    finally:
        db.close()


def test_admin_cannot_approve_application_before_video_screening():
    db = SessionLocal()
    try:
        nanny = _seed_nanny(db, approved=False, with_docs=True)
        admin = models.User(
            name="Screening Admin",
            role="admin",
            email=f"screening_admin_{datetime.utcnow().timestamp()}@example.com",
            password_hash="x",
            is_admin=True,
            is_active=True,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)

        blocked = client.patch(
            f"/admin/nannies/{nanny.id}/application",
            json={"status": "approved", "reason": ""},
            headers=_auth(admin),
        )
        assert blocked.status_code == 409
        assert "Video screening" in blocked.json()["detail"]

        nanny.video_screening_complete = True
        db.commit()
        missing_location = client.patch(
            f"/admin/nannies/{nanny.id}/application",
            json={"status": "approved", "reason": ""},
            headers=_auth(admin),
        )
        assert missing_location.status_code == 409
        assert "location" in missing_location.json()["detail"].lower()

        profile = db.query(models.NannyProfile).filter(models.NannyProfile.nanny_id == nanny.id).first()
        profile.lat = -25.7479
        profile.lng = 28.2293
        db.commit()
        approved = client.patch(
            f"/admin/nannies/{nanny.id}/application",
            json={"status": "approved", "reason": ""},
            headers=_auth(admin),
        )
        assert approved.status_code == 200
        assert approved.json()["approved"] is True
    finally:
        db.close()


def test_admin_can_update_candidate_profile_with_blank_date_and_telegram():
    db = SessionLocal()
    try:
        nanny = _seed_nanny(db, approved=False, with_docs=True)
        admin = models.User(
            name="Profile Admin",
            role="admin",
            email=f"profile_admin_{datetime.utcnow().timestamp()}@example.com",
            password_hash="x",
            is_admin=True,
            is_active=True,
        )
        db.add(admin)
        db.commit()
        response = client.patch(
            f"/admin/nannies/{nanny.user_id}/profile",
            json={
                "dob": None,
                "preferred_messaging_channel": "telegram",
                "medical_conditions": "None",
            },
            headers=_auth(admin),
        )
        assert response.status_code == 200, response.text
        user = db.query(models.User).filter(models.User.id == nanny.user_id).first()
        assert user.preferred_messaging_channel == "telegram"
    finally:
        db.close()
