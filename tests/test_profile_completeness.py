import json
from datetime import datetime

from app import models
from app.db import SessionLocal
from app.routers.public import (
    _parent_profile_missing_fields,
    nanny_meets_document_requirements,
    nanny_profile_missing_fields,
)


def test_non_sa_candidate_requires_uploaded_waiver_or_receipt_document():
    profile = models.NannyProfile(
        nanny_id=1,
        nationality="Zimbabwean",
        passport_number="P123456",
        passport_expiry="2030-01-01",
        passport_document_url="/passport.pdf",
        permit_status="waiver",
    )

    complete, missing = nanny_meets_document_requirements(profile)
    assert complete is False
    assert missing == ["work_permit_document_url"]

    profile.work_permit_document_url = "/waiver.pdf"
    complete, missing = nanny_meets_document_requirements(profile)
    assert complete is True
    assert missing == []


def test_candidate_completeness_reports_all_core_onboarding_gaps():
    user = models.User(name="Candidate", role="nanny", email="candidate@example.com", password_hash="x")
    profile = models.NannyProfile(nanny_id=1, nationality="South African")

    missing = nanny_profile_missing_fields(user, profile)

    assert "phone" in missing
    assert "profile_photo_url" in missing
    assert "date_of_birth" in missing
    assert "languages" in missing
    assert "home_location" in missing
    assert "sa_id_number" in missing
    assert "sa_id_document_url" in missing


def test_parent_completeness_returns_actionable_missing_fields():
    db = SessionLocal()
    try:
        user = models.User(
            name="Completeness Parent",
            role="parent",
            email=f"parent_completeness_{datetime.utcnow().timestamp()}@example.com",
            password_hash="x",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        db.add(models.ParentProfile(user_id=user.id, kids_count=1, kids_ages_json=json.dumps([])))
        db.commit()

        missing = _parent_profile_missing_fields(db, user.id)

        assert "phone" in missing
        assert "payment_authorisation" in missing
        assert "kids_ages" in missing
        assert "desired_tag_ids" in missing
        assert "home_language_id" in missing
        assert "residence_type" in missing
        assert "location" in missing
        assert "default_location" in missing
    finally:
        db.close()
