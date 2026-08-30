"""Permanent-placement workflow tests.

All payments and notifications are simulated. These tests must never contact
Paystack or send a real email/WhatsApp message.
"""

from itertools import count

import pytest
from fastapi.testclient import TestClient

from app import models
from app.db import SessionLocal
from app.main import app
from app.routers import placements as placements_router
from app.routers.public import _create_access_token


client = TestClient(app)
sequence = count(1)


def auth(user: models.User) -> dict[str, str]:
    return {"Authorization": f"Bearer {_create_access_token(user)}"}


def seed_user(db, role: str, *, admin: bool = False, name: str | None = None):
    suffix = next(sequence)
    user = models.User(
        name=name or f"{role.title()} {suffix}",
        role=role,
        email=f"permanent-{role}-{suffix}@example.com",
        password_hash="x",
        phone=f"+2782000{suffix:04d}",
        is_admin=admin,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def seed_nanny(db, *, opted_in: bool = True, name: str = "Thandi Private Surname"):
    user = seed_user(db, "nanny", name=name)
    nanny = models.Nanny(
        user_id=user.id,
        approved=True,
        profile_complete=True,
        video_screening_complete=True,
    )
    db.add(nanny)
    db.flush()
    profile = models.NannyProfile(
        nanny_id=nanny.id,
        bio="Experienced long-term caregiver",
        suburb="Sandton",
        city="Johannesburg",
        formatted_address="1 Private Home Street, Sandton",
        sa_id_number="9001010000000",
        sa_id_document_url="/media/private-id.pdf",
        police_clearance_document_url="/media/private-police.pdf",
        previous_jobs_json='[{"role":"Nanny","period":"3 years"}]',
    )
    preference = models.PermanentPlacementPreference(
        nanny_id=nanny.id,
        opted_in=opted_in,
        desired_salary_min_cents=700_000,
        desired_salary_max_cents=900_000,
        employment_types_json='["full_time","live_out"]',
        preferred_locations="Sandton and Midrand",
    )
    db.add_all([profile, preference])
    db.commit()
    db.refresh(nanny)
    return user, nanny


def enable_feature(db):
    row = db.query(models.AppSettings).filter(models.AppSettings.id == 1).first()
    if row is None:
        row = models.AppSettings(id=1)
        db.add(row)
    row.permanent_placements_enabled = True
    db.commit()


def create_brief(parent, tier="self_match"):
    response = client.post(
        "/parents/me/permanent-placements",
        headers=auth(parent),
        json={
            "service_tier": tier,
            "role_title": "Permanent nanny",
            "employment_type": "full_time",
            "schedule_summary": "Monday to Friday, 07:00 to 17:00",
            "hours_per_week": 45,
            "children_count": 2,
            "children_ages": ["2 years", "5 years"],
            "duties": "Childcare, school runs and children's meals",
            "salary_min_cents": 700_000,
            "salary_max_cents": 900_000,
            "location_suburb": "Sandton",
            "location_city": "Johannesburg",
            "location_province": "Gauteng",
            "drivers_license_required": True,
            "languages": ["English"],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def mark_paid(admin, placement_id: int, fee_type: str):
    response = client.post(
        f"/admin/permanent-placements/{placement_id}/payments/mark-paid",
        headers=auth(admin),
        json={"fee_type": fee_type, "reason": "Automated local test payment"},
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture(autouse=True)
def no_external_services(monkeypatch):
    monkeypatch.setattr(placements_router, "notify", lambda *args, **kwargs: False)
    yield


@pytest.fixture()
def db():
    session = SessionLocal()
    yield session
    session.close()


def test_pilot_switch_blocks_new_briefs_but_admin_can_open_it(db):
    parent = seed_user(db, "parent")
    admin = seed_user(db, "admin", admin=True)
    row = db.query(models.AppSettings).filter(models.AppSettings.id == 1).first()
    if row is None:
        row = models.AppSettings(id=1)
        db.add(row)
    row.permanent_placements_enabled = False
    db.commit()

    blocked = client.post(
        "/parents/me/permanent-placements",
        headers=auth(parent),
        json={
            "service_tier": "concierge",
            "role_title": "Permanent nanny",
            "schedule_summary": "Weekdays",
            "children_count": 1,
            "duties": "Childcare",
            "salary_min_cents": 500_000,
            "salary_max_cents": 700_000,
            "location_suburb": "Sandton",
            "location_city": "Johannesburg",
        },
    )
    assert blocked.status_code == 409

    opened = client.put(
        "/admin/permanent-placements/settings",
        headers=auth(admin),
        json={"enabled": True},
    )
    assert opened.status_code == 200
    assert opened.json()["enabled"] is True
    assert create_brief(parent, "concierge")["status"] == "awaiting_initial_payment"


def test_self_match_end_to_end_preserves_candidate_privacy(db):
    enable_feature(db)
    parent = seed_user(db, "parent", name="Test Family")
    admin = seed_user(db, "admin", admin=True)
    nanny_user, nanny = seed_nanny(db)
    placement = create_brief(parent)
    placement_id = placement["id"]

    assert placement["payments"][0]["fee_type"] == "activation"
    assert placement["payments"][0]["amount_cents"] == 35_000
    mark_paid(admin, placement_id, "activation")

    qualified = client.post(
        f"/admin/permanent-placements/{placement_id}/qualify",
        headers=auth(admin),
        json={"note": "Family brief is complete"},
    )
    assert qualified.status_code == 200, qualified.text
    assert qualified.json()["status"] == "awaiting_candidate_access"

    active = mark_paid(admin, placement_id, "candidate_access")
    assert active["status"] == "search_active"
    assert next(
        row for row in active["payments"] if row["fee_type"] == "candidate_access"
    )["amount_cents"] == 150_000

    invited = client.post(
        f"/admin/permanent-placements/{placement_id}/candidates",
        headers=auth(admin),
        json={"nanny_id": nanny.id},
    )
    assert invited.status_code == 200, invited.text
    candidate_id = invited.json()["id"]

    before_consent = client.get(
        f"/parents/me/permanent-placements/{placement_id}", headers=auth(parent)
    )
    assert before_consent.json()["candidates"] == []

    consent = client.post(
        f"/nannies/me/permanent-opportunities/{candidate_id}/respond",
        headers=auth(nanny_user),
        json={"decision": "accepted"},
    )
    assert consent.status_code == 200, consent.text

    released = client.post(
        f"/admin/permanent-placements/{placement_id}/candidates/{candidate_id}/release",
        headers=auth(admin),
    )
    assert released.status_code == 200, released.text

    parent_view = client.get(
        f"/parents/me/permanent-placements/{placement_id}", headers=auth(parent)
    ).json()
    candidate = parent_view["candidates"][0]
    assert candidate["first_name"] == "Thandi"
    assert candidate["broad_location"] == "Sandton, Johannesburg"
    assert "phone" not in candidate
    assert "email" not in candidate
    assert "full_name" not in candidate
    assert "exact_address" not in candidate
    assert "sa_id_number" not in candidate

    shortlisted = client.post(
        f"/parents/me/permanent-placements/{placement_id}/candidates/{candidate_id}/shortlist",
        headers=auth(parent),
        json={"note": "Strong experience"},
    )
    assert shortlisted.status_code == 200, shortlisted.text
    interview = client.post(
        f"/parents/me/permanent-placements/{placement_id}/candidates/{candidate_id}/request-interview",
        headers=auth(parent),
        json={"note": "Please arrange a video interview"},
    )
    assert interview.status_code == 200, interview.text

    scheduled = client.post(
        f"/admin/permanent-placements/{placement_id}/candidates/{candidate_id}/schedule-interview",
        headers=auth(admin),
        json={
            "scheduled_at": "2026-09-05T10:00:00",
            "interview_format": "video",
        },
    )
    assert scheduled.status_code == 200, scheduled.text

    interviewed = client.post(
        f"/admin/permanent-placements/{placement_id}/candidates/{candidate_id}/stage",
        headers=auth(admin),
        json={"status": "interviewed", "note": "Interview completed"},
    )
    assert interviewed.status_code == 200, interviewed.text
    trial = client.post(
        f"/admin/permanent-placements/{placement_id}/candidates/{candidate_id}/stage",
        headers=auth(admin),
        json={
            "status": "trial",
            "trial_scheduled_at": "2026-09-07T08:00:00",
            "note": "Paid directly to nanny",
        },
    )
    assert trial.status_code == 200, trial.text

    hired = client.post(
        f"/admin/permanent-placements/{placement_id}/candidates/{candidate_id}/hire",
        headers=auth(admin),
        json={"note": "Family confirmed appointment"},
    )
    assert hired.status_code == 200, hired.text
    assert hired.json()["status"] == "awaiting_success_fee"
    success_fee = next(
        row for row in hired.json()["payments"] if row["fee_type"] == "success"
    )
    assert success_fee["amount_cents"] == 150_000

    placed = mark_paid(admin, placement_id, "success")
    assert placed["status"] == "placed"
    assert placed["guarantee_until"] is not None


def test_self_match_upgrade_credits_candidate_access_fee(db):
    enable_feature(db)
    parent = seed_user(db, "parent")
    admin = seed_user(db, "admin", admin=True)
    nanny_user, nanny = seed_nanny(db, name="Naledi Test Candidate")
    placement_id = create_brief(parent)["id"]
    mark_paid(admin, placement_id, "activation")
    assert client.post(
        f"/admin/permanent-placements/{placement_id}/qualify",
        headers=auth(admin),
        json={"note": "Qualified"},
    ).status_code == 200
    mark_paid(admin, placement_id, "candidate_access")

    upgraded = client.post(
        f"/parents/me/permanent-placements/{placement_id}/upgrade",
        headers=auth(parent),
    )
    assert upgraded.status_code == 200, upgraded.text
    assert upgraded.json()["service_tier"] == "concierge"
    assert upgraded.json()["upgraded_from_self_match"] is True

    invited = client.post(
        f"/admin/permanent-placements/{placement_id}/candidates",
        headers=auth(admin),
        json={"nanny_id": nanny.id},
    )
    candidate_id = invited.json()["id"]
    client.post(
        f"/nannies/me/permanent-opportunities/{candidate_id}/respond",
        headers=auth(nanny_user),
        json={"decision": "accepted"},
    )
    client.post(
        f"/admin/permanent-placements/{placement_id}/candidates/{candidate_id}/release",
        headers=auth(admin),
    )
    hired = client.post(
        f"/admin/permanent-placements/{placement_id}/candidates/{candidate_id}/hire",
        headers=auth(admin),
        json={"note": "Placed"},
    )
    assert hired.status_code == 200, hired.text
    success_fee = next(
        row for row in hired.json()["payments"] if row["fee_type"] == "success"
    )
    assert success_fee["amount_cents"] == 350_000


def test_admin_cannot_invite_nanny_who_has_not_opted_in(db):
    enable_feature(db)
    parent = seed_user(db, "parent")
    admin = seed_user(db, "admin", admin=True)
    _, nanny = seed_nanny(db, opted_in=False)
    placement_id = create_brief(parent, "concierge")["id"]
    mark_paid(admin, placement_id, "application")
    client.post(
        f"/admin/permanent-placements/{placement_id}/qualify",
        headers=auth(admin),
        json={"note": "Qualified"},
    )

    response = client.post(
        f"/admin/permanent-placements/{placement_id}/candidates",
        headers=auth(admin),
        json={"nanny_id": nanny.id},
    )
    assert response.status_code == 409
    assert "opted-in" in response.json()["detail"]


def test_paystack_initialization_and_verification_use_exact_fee(db, monkeypatch):
    enable_feature(db)
    parent = seed_user(db, "parent")
    placement = create_brief(parent, "concierge")
    calls = []

    def fake_initialize(**kwargs):
        calls.append(kwargs)
        return True, {
            "data": {
                "authorization_url": "https://paystack.test/authorize",
                "reference": kwargs["reference"],
                "access_code": "test-access",
            }
        }

    monkeypatch.setattr(placements_router, "initialize_transaction", fake_initialize)
    initialized = client.post(
        f"/parents/me/permanent-placements/{placement['id']}/payments/application/initialize",
        headers=auth(parent),
        json={"callback_url": "http://localhost:3000/placements"},
    )
    assert initialized.status_code == 200, initialized.text
    assert calls[0]["amount_kobo"] == 50_000
    assert calls[0]["metadata"]["purpose"] == "permanent_placement_fee"
    reference = initialized.json()["reference"]

    monkeypatch.setattr(
        placements_router,
        "verify_transaction",
        lambda value: (
            True,
            {
                "data": {
                    "status": "success",
                    "amount": 50_000,
                    "reference": value,
                    "id": "test-transaction",
                    "metadata": {"placement_id": placement["id"]},
                }
            },
        ),
    )
    verified = client.post(
        f"/parents/me/permanent-placements/{placement['id']}/payments/verify",
        headers=auth(parent),
        json={"reference": reference},
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["status"] == "brief_submitted"
    assert verified.json()["payments"][0]["status"] == "paid"


def test_parent_can_request_in_period_rematch_and_admin_reopens_search(db):
    enable_feature(db)
    parent = seed_user(db, "parent")
    admin = seed_user(db, "admin", admin=True)
    placement = models.PermanentPlacement(
        parent_user_id=parent.id,
        service_tier="concierge",
        status="placed",
        role_title="Permanent nanny",
        employment_type="full_time",
        schedule_summary="Weekdays",
        children_count=1,
        duties="Childcare",
        salary_min_cents=700_000,
        salary_max_cents=900_000,
        location_suburb="Sandton",
        location_city="Johannesburg",
        guarantee_until=placements_router.utc_now()
        + placements_router.timedelta(days=30),
        replacement_status="not_requested",
    )
    db.add(placement)
    db.commit()
    db.refresh(placement)

    requested = client.post(
        f"/parents/me/permanent-placements/{placement.id}/request-replacement",
        headers=auth(parent),
        json={"reason": "The employment arrangement ended during the guarantee period."},
    )
    assert requested.status_code == 200, requested.text
    assert requested.json()["replacement_status"] == "requested"

    approved = client.post(
        f"/admin/permanent-placements/{placement.id}/replacement",
        headers=auth(admin),
        json={
            "decision": "approved",
            "note": "Approved within the 90-day replacement period",
        },
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["replacement_status"] == "approved"
    assert approved.json()["status"] == "search_active"
