"""Permanent-placement workflow tests.

All payments and notifications are simulated. These tests must never contact
Paystack or send a real email/WhatsApp message.
"""

from datetime import date, time, timedelta
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
    session = SessionLocal()
    settings = (
        session.query(models.PermanentPlacementSettings)
        .filter(models.PermanentPlacementSettings.id == 1)
        .first()
    )
    if settings is None:
        settings = models.PermanentPlacementSettings(id=1)
        session.add(settings)
    defaults = {
        "currency": "ZAR",
        "self_match_activation_fee_cents": 35_000,
        "self_match_interview_package_fee_cents": 150_000,
        "self_match_placement_fee_cents": 150_000,
        "activation_fee_credits_toward_package": True,
        "concierge_consultation_fee_cents": 55_000,
        "concierge_engagement_fee_cents": 250_000,
        "concierge_success_balance_cents": 700_000,
        "self_match_profile_limit": 10,
        "self_match_interview_limit": 5,
        "concierge_interview_limit": 5,
        "candidate_access_days": 30,
        "replacement_period_days": 40,
        "replacement_credit_count": 3,
        "replacement_max_count": 1,
        "maybe_period_days": 4,
    }
    for field_name, value in defaults.items():
        setattr(settings, field_name, value)
    billing = session.query(models.BillingSettings).filter(models.BillingSettings.id == 1).first()
    if billing is None:
        billing = models.BillingSettings(id=1)
        session.add(billing)
    billing.issuer_legal_name = None
    billing.issuer_trading_name = "My Nanny"
    billing.issuer_email = None
    billing.issuer_phone = None
    billing.issuer_address = None
    billing.issuer_registration_number = None
    billing.issuer_vat_number = None
    billing.vat_registered = False
    billing.vat_rate_bps = 1500
    billing.prices_include_vat = None
    billing.tax_status_confirmed_at = None
    billing.invoice_prefix = "MN"
    session.commit()
    session.close()
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


def test_admin_can_configure_zero_fee_without_paystack_blocking_the_case(db):
    parent = seed_user(db, "parent", name="Zero Fee Family")
    admin = seed_user(db, "admin", admin=True)
    configured = client.put(
        "/admin/permanent-placements/settings",
        headers=auth(admin),
        json={
            "enabled": True,
            "self_match_activation_fee_cents": 0,
        },
    )
    assert configured.status_code == 200, configured.text
    assert configured.json()["pricing"]["self_match"]["activation_fee_cents"] == 0

    placement = create_brief(parent, "self_match")
    assert placement["status"] == "brief_submitted"
    activation = next(
        payment for payment in placement["payments"] if payment["fee_type"] == "activation"
    )
    assert activation["amount_cents"] == 0
    assert activation["status"] == "paid"
    assert placement["invoices"][0]["total_cents"] == 0
    assert placement["invoices"][0]["status"] == "draft"


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
    )["amount_cents"] == 115_000

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
    assert released.json()["introduction_expires_at"] is None

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
    accepted_interview = client.post(
        f"/nannies/me/permanent-opportunities/{candidate_id}/interview-response",
        headers=auth(nanny_user),
        json={"decision": "accepted"},
    )
    assert accepted_interview.status_code == 200, accepted_interview.text
    assert accepted_interview.json()["interview_credits"]["available"] == 4

    scheduled = client.post(
        f"/admin/permanent-placements/{placement_id}/candidates/{candidate_id}/schedule-interview",
        headers=auth(admin),
        json={
            "scheduled_at": "2026-09-05T10:00:00",
            "interview_format": "video",
        },
    )
    assert scheduled.status_code == 200, scheduled.text

    checked_in = client.post(
        f"/nannies/me/permanent-opportunities/{candidate_id}/interview-progress",
        headers=auth(nanny_user),
        json={"action": "check_in"},
    )
    assert checked_in.status_code == 200, checked_in.text
    assert checked_in.json()["interview_checked_in_at"] is not None
    completed = client.post(
        f"/nannies/me/permanent-opportunities/{candidate_id}/interview-progress",
        headers=auth(nanny_user),
        json={"action": "completed"},
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["interview_completed_at"] is not None

    maybe = client.post(
        f"/parents/me/permanent-placements/{placement_id}/candidates/{candidate_id}/interview-decision",
        headers=auth(parent),
        json={"decision": "maybe", "feedback": "Warm and experienced; we need a little time."},
    )
    assert maybe.status_code == 200, maybe.text
    maybe_candidate = maybe.json()["candidates"][0]
    assert maybe_candidate["parent_interview_decision"] == "maybe"
    assert maybe_candidate["maybe_until"] is not None

    requested_trial = client.post(
        f"/parents/me/permanent-placements/{placement_id}/candidates/{candidate_id}/interview-decision",
        headers=auth(parent),
        json={"decision": "trial", "feedback": "We would like to proceed to a paid trial."},
    )
    assert requested_trial.status_code == 200, requested_trial.text
    assert requested_trial.json()["candidates"][0]["status"] == "trial_requested"
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
    assert upgraded.json()["status"] == "awaiting_engagement_payment"
    engagement_fee = next(
        row for row in upgraded.json()["payments"] if row["fee_type"] == "engagement"
    )
    assert engagement_fee["amount_cents"] == 100_000
    active = mark_paid(admin, placement_id, "engagement")
    assert active["status"] == "search_active"

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
    assert success_fee["amount_cents"] == 700_000
    assert engagement_fee["amount_cents"] + success_fee["amount_cents"] == 800_000


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
    engagement = mark_paid(admin, placement_id, "engagement")
    assert engagement["status"] == "search_active"

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
    assert calls[0]["amount_kobo"] == 55_000
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
                    "amount": 55_000,
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
        + timedelta(days=30),
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
    assert approved.json()["replacement_count"] == 1
    assert approved.json()["interview_credits"]["included"] == 3
    assert approved.json()["interview_credits"]["available"] == 3

    db.expire_all()
    stored = (
        db.query(models.PermanentPlacement)
        .filter(models.PermanentPlacement.id == placement.id)
        .first()
    )
    stored.status = "placed"
    stored.replacement_status = "completed"
    stored.guarantee_until = placements_router.utc_now() + timedelta(days=10)
    db.commit()
    second_request = client.post(
        f"/parents/me/permanent-placements/{placement.id}/request-replacement",
        headers=auth(parent),
        json={"reason": "A second replacement is requested but is not included."},
    )
    assert second_request.status_code == 409
    assert "already been used" in second_request.json()["detail"]


def test_admin_pricing_applies_to_new_cases_without_repricing_existing_cases(db):
    enable_feature(db)
    admin = seed_user(db, "admin", admin=True)
    first_parent = seed_user(db, "parent")
    second_parent = seed_user(db, "parent")

    existing = create_brief(first_parent, "self_match")
    assert existing["payments"][0]["amount_cents"] == 35_000
    assert existing["pricing"]["self_match"]["candidate_access_fee_cents"] == 115_000

    updated = client.put(
        "/admin/permanent-placements/settings",
        headers=auth(admin),
        json={
            "self_match_activation_fee_cents": 40_000,
            "self_match_interview_package_fee_cents": 160_000,
            "self_match_placement_fee_cents": 175_000,
            "activation_fee_credits_toward_package": True,
            "concierge_consultation_fee_cents": 60_000,
            "concierge_engagement_fee_cents": 300_000,
            "concierge_success_balance_cents": 750_000,
        },
    )
    assert updated.status_code == 200, updated.text
    pricing = updated.json()["pricing"]
    assert pricing["self_match"]["candidate_access_fee_cents"] == 120_000
    assert pricing["self_match"]["total_if_placed_cents"] == 335_000
    assert pricing["concierge"]["success_fee_cents"] == 1_050_000
    assert pricing["concierge"]["total_if_placed_cents"] == 1_110_000

    # The first case retains its original snapshot and its pending amount.
    old_detail = client.get(
        f"/parents/me/permanent-placements/{existing['id']}", headers=auth(first_parent)
    ).json()
    assert old_detail["pricing"]["self_match"]["activation_fee_cents"] == 35_000
    assert old_detail["payments"][0]["amount_cents"] == 35_000
    mark_paid(admin, existing["id"], "activation")
    qualified = client.post(
        f"/admin/permanent-placements/{existing['id']}/qualify",
        headers=auth(admin),
        json={"note": "Existing case pricing check"},
    )
    assert qualified.status_code == 200, qualified.text
    assert next(
        payment
        for payment in qualified.json()["payments"]
        if payment["fee_type"] == "candidate_access"
    )["amount_cents"] == 115_000

    new_case = create_brief(second_parent, "self_match")
    assert new_case["payments"][0]["amount_cents"] == 40_000
    assert new_case["pricing"]["self_match"]["candidate_access_fee_cents"] == 120_000

    invalid = client.put(
        "/admin/permanent-placements/settings",
        headers=auth(admin),
        json={"self_match_interview_package_fee_cents": 30_000},
    )
    assert invalid.status_code == 422


def test_interview_credits_are_used_on_acceptance_and_restored_when_not_held(db):
    enable_feature(db)
    parent = seed_user(db, "parent")
    admin = seed_user(db, "admin", admin=True)
    placement_id = create_brief(parent, "self_match")["id"]
    mark_paid(admin, placement_id, "activation")
    assert client.post(
        f"/admin/permanent-placements/{placement_id}/qualify",
        headers=auth(admin),
        json={"note": "Qualified"},
    ).status_code == 200
    mark_paid(admin, placement_id, "candidate_access")

    invited_candidates = []
    for index in range(6):
        nanny_user, nanny = seed_nanny(db, name=f"Interview Candidate {index}")
        invited = client.post(
            f"/admin/permanent-placements/{placement_id}/candidates",
            headers=auth(admin),
            json={"nanny_id": nanny.id},
        )
        assert invited.status_code == 200, invited.text
        candidate_id = invited.json()["id"]
        assert client.post(
            f"/nannies/me/permanent-opportunities/{candidate_id}/respond",
            headers=auth(nanny_user),
            json={"decision": "accepted"},
        ).status_code == 200
        assert client.post(
            f"/admin/permanent-placements/{placement_id}/candidates/{candidate_id}/release",
            headers=auth(admin),
        ).status_code == 200
        assert client.post(
            f"/parents/me/permanent-placements/{placement_id}/candidates/{candidate_id}/request-interview",
            headers=auth(parent),
            json={"note": f"Invite {index}"},
        ).status_code == 200
        invited_candidates.append((nanny_user, candidate_id))

    for accepted_number, (nanny_user, candidate_id) in enumerate(invited_candidates[:5], start=1):
        response = client.post(
            f"/nannies/me/permanent-opportunities/{candidate_id}/interview-response",
            headers=auth(nanny_user),
            json={"decision": "accepted"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["interview_credits"]["available"] == 5 - accepted_number

    sixth_user, sixth_candidate = invited_candidates[5]
    full = client.post(
        f"/nannies/me/permanent-opportunities/{sixth_candidate}/interview-response",
        headers=auth(sixth_user),
        json={"decision": "accepted"},
    )
    assert full.status_code == 409

    restored = client.post(
        f"/admin/permanent-placements/{placement_id}/candidates/{invited_candidates[0][1]}/interview-outcome",
        headers=auth(admin),
        json={"outcome": "not_held", "reason": "Family emergency; interview did not happen"},
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["interview_credits"]["available"] == 1

    accepted_after_restore = client.post(
        f"/nannies/me/permanent-opportunities/{sixth_candidate}/interview-response",
        headers=auth(sixth_user),
        json={"decision": "accepted"},
    )
    assert accepted_after_restore.status_code == 200, accepted_after_restore.text
    assert accepted_after_restore.json()["interview_credits"]["available"] == 0

    events = (
        db.query(models.PermanentPlacementInterviewCreditEvent)
        .filter(models.PermanentPlacementInterviewCreditEvent.placement_id == placement_id)
        .all()
    )
    assert sum(event.delta for event in events) == -5
    assert any(event.event_type == "not_held" and event.delta == 1 for event in events)


def test_trial_offer_acceptance_restructures_short_term_calendar(db):
    enable_feature(db)
    parent = seed_user(db, "parent", name="Calendar Family")
    admin = seed_user(db, "admin", admin=True)
    nanny_user, nanny = seed_nanny(db, name="Calendar Candidate")
    placement_id = create_brief(parent, "self_match")["id"]
    mark_paid(admin, placement_id, "activation")
    assert client.post(
        f"/admin/permanent-placements/{placement_id}/qualify",
        headers=auth(admin),
        json={"note": "Qualified"},
    ).status_code == 200
    mark_paid(admin, placement_id, "candidate_access")

    invited = client.post(
        f"/admin/permanent-placements/{placement_id}/candidates",
        headers=auth(admin),
        json={"nanny_id": nanny.id},
    )
    assert invited.status_code == 200, invited.text
    candidate_id = invited.json()["id"]
    assert client.post(
        f"/nannies/me/permanent-opportunities/{candidate_id}/respond",
        headers=auth(nanny_user),
        json={"decision": "accepted"},
    ).status_code == 200
    assert client.post(
        f"/admin/permanent-placements/{placement_id}/candidates/{candidate_id}/release",
        headers=auth(admin),
    ).status_code == 200
    assert client.post(
        f"/parents/me/permanent-placements/{placement_id}/candidates/{candidate_id}/request-interview",
        headers=auth(parent),
        json={"note": "Please arrange the interview"},
    ).status_code == 200
    assert client.post(
        f"/nannies/me/permanent-opportunities/{candidate_id}/interview-response",
        headers=auth(nanny_user),
        json={"decision": "accepted"},
    ).status_code == 200
    assert client.post(
        f"/admin/permanent-placements/{placement_id}/candidates/{candidate_id}/schedule-interview",
        headers=auth(admin),
        json={"scheduled_at": "2026-09-05T10:00:00", "interview_format": "in_person", "interview_location": "My Nanny office"},
    ).status_code == 200
    assert client.post(
        f"/nannies/me/permanent-opportunities/{candidate_id}/interview-progress",
        headers=auth(nanny_user),
        json={"action": "completed"},
    ).status_code == 200

    assert client.post(
        f"/parents/me/permanent-placements/{placement_id}/candidates/{candidate_id}/interview-decision",
        headers=auth(parent),
        json={"decision": "trial", "feedback": "We would like a paid trial before making an offer."},
    ).status_code == 200
    first_trial = client.post(
        f"/parents/me/permanent-placements/{placement_id}/candidates/{candidate_id}/trial",
        headers=auth(parent),
        json={"starts_at": "2026-09-07T08:00:00", "ends_at": "2026-09-07T16:00:00", "note": "Transport arranged"},
    )
    assert first_trial.status_code == 200, first_trial.text
    alternative = client.post(
        f"/nannies/me/permanent-opportunities/{candidate_id}/trial-response",
        headers=auth(nanny_user),
        json={"decision": "change_requested", "alternative_at": "2026-09-08T08:00:00"},
    )
    assert alternative.status_code == 200, alternative.text
    assert alternative.json()["trial_status"] == "change_requested"
    second_trial = client.post(
        f"/parents/me/permanent-placements/{placement_id}/candidates/{candidate_id}/trial",
        headers=auth(parent),
        json={"starts_at": "2026-09-08T08:00:00", "ends_at": "2026-09-08T16:00:00"},
    )
    assert second_trial.status_code == 200, second_trial.text
    accepted_trial = client.post(
        f"/nannies/me/permanent-opportunities/{candidate_id}/trial-response",
        headers=auth(nanny_user),
        json={"decision": "accepted"},
    )
    assert accepted_trial.status_code == 200, accepted_trial.text
    assert accepted_trial.json()["trial_status"] == "accepted"

    # Existing nanny-created calendar rows must remain intact. The accepted
    # permanent role adds full-day weekday blocks and leaves Saturday free.
    monday_availability = models.NannyAvailability(
        nanny_id=nanny.id,
        date=date(2026, 9, 14),
        start_time=time(6, 0),
        end_time=time(22, 0),
        start_dt="2026-09-14T04:00:00Z",
        end_dt="2026-09-14T20:00:00Z",
        type="available",
        is_available=True,
        created_by="nanny",
    )
    saturday_availability = models.NannyAvailability(
        nanny_id=nanny.id,
        date=date(2026, 9, 12),
        start_time=time(8, 0),
        end_time=time(18, 0),
        start_dt="2026-09-12T06:00:00Z",
        end_dt="2026-09-12T16:00:00Z",
        type="available",
        is_available=True,
        created_by="nanny",
    )
    db.add_all([monday_availability, saturday_availability])
    db.commit()
    original_ids = {monday_availability.id, saturday_availability.id}

    assert client.post(
        f"/parents/me/permanent-placements/{placement_id}/candidates/{candidate_id}/interview-decision",
        headers=auth(parent),
        json={"decision": "offer", "feedback": "The trial went well and we would like to make an offer."},
    ).status_code == 200
    offer = client.post(
        f"/parents/me/permanent-placements/{placement_id}/candidates/{candidate_id}/offer",
        headers=auth(parent),
        json={
            "salary_cents": 850_000,
            "start_date": "2026-09-14",
            "working_days": [0, 1, 2, 3, 4],
            "start_time": "07:00",
            "end_time": "17:00",
            "terms": "Monday to Friday permanent nanny role with agreed childcare duties.",
        },
    )
    assert offer.status_code == 200, offer.text
    accepted_offer = client.post(
        f"/nannies/me/permanent-opportunities/{candidate_id}/offer-response",
        headers=auth(nanny_user),
        json={"decision": "accepted"},
    )
    assert accepted_offer.status_code == 200, accepted_offer.text
    assert accepted_offer.json()["placement_status"] == "awaiting_success_fee"
    assert accepted_offer.json()["blocked_calendar_days"] > 250

    db.expire_all()
    candidate = db.query(models.PermanentPlacementCandidate).filter_by(id=candidate_id).one()
    profile = db.query(models.NannyProfile).filter_by(nanny_id=nanny.id).one()
    payment = db.query(models.PermanentPlacementPayment).filter_by(
        placement_id=placement_id, fee_type="success"
    ).one()
    assert candidate.offer_status == "accepted"
    assert candidate.availability_restructured_at is not None
    assert profile.current_job_availability == "piece_and_permanent"
    assert payment.amount_cents == 150_000

    retained_ids = {
        row.id
        for row in db.query(models.NannyAvailability)
        .filter(models.NannyAvailability.id.in_(original_ids))
        .all()
    }
    assert retained_ids == original_ids
    monday_block = db.query(models.NannyAvailability).filter_by(
        nanny_id=nanny.id,
        date=date(2026, 9, 14),
        created_by="permanent_placement",
    ).one()
    assert monday_block.is_available is False
    assert monday_block.start_time == time(0, 0)
    assert monday_block.end_time == time(23, 59, 59)
    availability_payload = client.get(
        "/nannies/me/availability",
        headers=auth(nanny_user),
    ).json()["results"]
    monday_payload = next(row for row in availability_payload if row["id"] == monday_block.id)
    assert monday_payload["date"] == "2026-09-14"
    saturday_blocks = db.query(models.NannyAvailability).filter_by(
        nanny_id=nanny.id,
        date=date(2026, 9, 12),
        created_by="permanent_placement",
    ).count()
    assert saturday_blocks == 0


def test_interview_contact_requires_both_terms_and_locks_at_check_in(db):
    enable_feature(db)
    parent = seed_user(db, "parent", name="Contact Family")
    admin = seed_user(db, "admin", admin=True)
    nanny_user, nanny = seed_nanny(db, name="Contact Candidate")
    placement_id = create_brief(parent, "self_match")["id"]
    mark_paid(admin, placement_id, "activation")
    assert client.post(
        f"/admin/permanent-placements/{placement_id}/qualify",
        headers=auth(admin),
        json={"note": "Qualified"},
    ).status_code == 200
    mark_paid(admin, placement_id, "candidate_access")
    candidate_id = client.post(
        f"/admin/permanent-placements/{placement_id}/candidates",
        headers=auth(admin),
        json={"nanny_id": nanny.id},
    ).json()["id"]
    assert client.post(
        f"/nannies/me/permanent-opportunities/{candidate_id}/respond",
        headers=auth(nanny_user),
        json={"decision": "accepted"},
    ).status_code == 200
    assert client.post(
        f"/admin/permanent-placements/{placement_id}/candidates/{candidate_id}/release",
        headers=auth(admin),
    ).status_code == 200
    assert client.post(
        f"/parents/me/permanent-placements/{placement_id}/candidates/{candidate_id}/request-interview",
        headers=auth(parent),
        json={"note": "Interview request"},
    ).status_code == 200
    assert client.post(
        f"/nannies/me/permanent-opportunities/{candidate_id}/interview-response",
        headers=auth(nanny_user),
        json={"decision": "accepted"},
    ).status_code == 200

    parent_detail = client.get(
        f"/parents/me/permanent-placements/{placement_id}", headers=auth(parent)
    ).json()
    parent_candidate = parent_detail["candidates"][0]
    assert parent_candidate["contact_window_open"] is True
    assert parent_candidate["contact_details_visible"] is False
    assert "temporary_contact" not in parent_candidate

    before_terms = client.get(
        f"/permanent-placements/candidates/{candidate_id}/communication",
        headers=auth(parent),
    )
    assert before_terms.status_code == 200, before_terms.text
    assert before_terms.json()["can_message"] is False
    assert before_terms.json()["contact"] is None

    parent_terms = client.post(
        f"/permanent-placements/candidates/{candidate_id}/contact-terms",
        headers=auth(parent),
        json={"accepted": True},
    )
    assert parent_terms.status_code == 200, parent_terms.text
    assert parent_terms.json()["viewer_terms_accepted"] is True
    assert parent_terms.json()["can_message"] is False
    blocked_message = client.post(
        f"/permanent-placements/candidates/{candidate_id}/messages",
        headers=auth(parent),
        json={"body": "Confirming the interview location"},
    )
    assert blocked_message.status_code == 409

    nanny_terms = client.post(
        f"/permanent-placements/candidates/{candidate_id}/contact-terms",
        headers=auth(nanny_user),
        json={"accepted": True},
    )
    assert nanny_terms.status_code == 200, nanny_terms.text
    nanny_communication = nanny_terms.json()
    assert nanny_communication["can_message"] is True
    assert nanny_communication["contact"]["name"] == "Contact Family"
    assert nanny_communication["contact"]["phone"] == parent.phone
    assert "address" not in nanny_communication["contact"]

    sent = client.post(
        f"/permanent-placements/candidates/{candidate_id}/messages",
        headers=auth(parent),
        json={"body": "Please meet reception at 10:00."},
    )
    assert sent.status_code == 200, sent.text
    assert sent.json()["messages"][0]["body"] == "Please meet reception at 10:00."
    nanny_view = client.get(
        f"/permanent-placements/candidates/{candidate_id}/communication",
        headers=auth(nanny_user),
    ).json()
    assert nanny_view["messages"][0]["sender_role"] == "parent"
    assert nanny_view["contact"]["phone"] == parent.phone

    assert client.post(
        f"/admin/permanent-placements/{placement_id}/candidates/{candidate_id}/schedule-interview",
        headers=auth(admin),
        json={"scheduled_at": "2026-09-05T10:00:00", "interview_format": "in_person", "interview_location": "Reception"},
    ).status_code == 200
    checked_in = client.post(
        f"/nannies/me/permanent-opportunities/{candidate_id}/interview-progress",
        headers=auth(nanny_user),
        json={"action": "check_in"},
    )
    assert checked_in.status_code == 200, checked_in.text
    locked = client.get(
        f"/permanent-placements/candidates/{candidate_id}/communication",
        headers=auth(parent),
    ).json()
    assert locked["window_open"] is False
    assert locked["can_message"] is False
    assert locked["contact"] is None
    assert len(locked["messages"]) == 1
    after_check_in = client.post(
        f"/permanent-placements/candidates/{candidate_id}/messages",
        headers=auth(parent),
        json={"body": "This must be mediated by My Nanny."},
    )
    assert after_check_in.status_code == 409

    hidden_again = client.get(
        f"/parents/me/permanent-placements/{placement_id}", headers=auth(parent)
    ).json()["candidates"][0]
    assert hidden_again["contact_details_visible"] is False
    assert "temporary_contact" not in hidden_again


def test_invoice_issue_receipt_and_private_downloads_require_billing_setup(db, monkeypatch, tmp_path):
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("LOCAL_UPLOAD_ROOT", str(tmp_path))
    enable_feature(db)
    parent = seed_user(db, "parent", name="Invoice Family")
    other_parent = seed_user(db, "parent", name="Other Family")
    admin = seed_user(db, "admin", admin=True)
    placement = create_brief(parent, "concierge")
    placement_id = placement["id"]
    draft = placement["invoices"][0]
    assert draft["status"] == "draft"
    assert draft["invoice_number"] is None
    assert draft["total_cents"] == 55_000

    blocked_issue = client.post(
        f"/admin/invoices/{draft['id']}/issue",
        headers=auth(admin),
        json={"send_email": True},
    )
    assert blocked_issue.status_code == 409
    assert "legal business name" in blocked_issue.json()["detail"]

    configured = client.put(
        "/admin/billing/settings",
        headers=auth(admin),
        json={
            "issuer_legal_name": "My Nanny Test Entity",
            "issuer_trading_name": "My Nanny",
            "issuer_email": "billing@example.com",
            "issuer_phone": "+27110000000",
            "issuer_address": "1 Test Avenue\nJohannesburg\nGauteng",
            "issuer_registration_number": "TEST-REG-001",
            "vat_registered": False,
            "tax_status_confirmed": True,
            "invoice_prefix": "MNTEST",
        },
    )
    assert configured.status_code == 200, configured.text
    assert configured.json()["ready_to_issue"] is True

    monkeypatch.setattr(
        placements_router,
        "initialize_transaction",
        lambda **kwargs: (
            True,
            {
                "data": {
                    "authorization_url": "https://paystack.test/authorize",
                    "reference": kwargs["reference"],
                    "access_code": "test-access",
                }
            },
        ),
    )
    initialized = client.post(
        f"/parents/me/permanent-placements/{placement_id}/payments/application/initialize",
        headers=auth(parent),
        json={"callback_url": "http://localhost:3000/placements"},
    )
    assert initialized.status_code == 200, initialized.text
    issued = initialized.json()["invoice"]
    assert issued["status"] == "issued"
    assert issued["invoice_number"].startswith("MNTEST-INV-")
    assert issued["invoice_pdf_url"].startswith(f"/media/invoices/{parent.id}/")
    invoice_path = tmp_path / issued["invoice_pdf_url"].removeprefix("/media/")
    assert invoice_path.read_bytes().startswith(b"%PDF")

    own_download = client.get(issued["invoice_pdf_url"], headers=auth(parent))
    assert own_download.status_code == 200
    assert own_download.headers["content-type"].startswith("application/pdf")
    assert client.get(issued["invoice_pdf_url"], headers=auth(other_parent)).status_code == 403
    assert client.get(issued["invoice_pdf_url"]).status_code == 401

    reference = initialized.json()["reference"]
    monkeypatch.setattr(
        placements_router,
        "verify_transaction",
        lambda value: (
            True,
            {
                "data": {
                    "status": "success",
                    "amount": 55_000,
                    "reference": value,
                    "id": "test-paid-transaction",
                    "metadata": {"placement_id": placement_id},
                }
            },
        ),
    )
    verified = client.post(
        f"/parents/me/permanent-placements/{placement_id}/payments/verify",
        headers=auth(parent),
        json={"reference": reference},
    )
    assert verified.status_code == 200, verified.text
    paid_invoice = verified.json()["invoices"][0]
    assert paid_invoice["status"] == "paid"
    assert paid_invoice["receipt_number"].startswith("MNTEST-RCT-")
    receipt_path = tmp_path / paid_invoice["receipt_pdf_url"].removeprefix("/media/")
    assert receipt_path.read_bytes().startswith(b"%PDF")

    stored = db.query(models.Invoice).filter(models.Invoice.id == draft["id"]).one()
    assert stored.total_cents == 55_000
    assert stored.invoice_pdf_sha256
    assert stored.receipt_pdf_sha256
    assert stored.invoice_email_requested_at is not None
    assert stored.receipt_email_requested_at is not None
