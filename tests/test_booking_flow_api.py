"""
End-to-end API tests for the core booking flow:

    parent (with saved card) -> booking request -> nanny accept -> paid booking

plus the guard rails around it (no card, no availability, past window,
suspended nanny, incomplete documents, decline path, overlap rejection).

Paystack, email, and Google Calendar are monkeypatched at the
app.routers.public import site so no external calls are made.
"""

from datetime import datetime, timedelta, time as dtime

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app import models
from app.db import SessionLocal
from app.routers import public as public_router
from app.routers.public import _create_access_token


client = TestClient(app)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _iso_z(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat() + "Z"


def _seed_parent(db, *, with_card: bool = True) -> models.User:
    user = models.User(
        name="Test Parent",
        role="parent",
        email=f"parent_{datetime.utcnow().timestamp()}@example.com",
        password_hash="x",
        is_admin=False,
        is_active=True,
    )
    if with_card:
        user.paystack_auth_code = "AUTH_test123"
        user.card_last4 = "4084"
        user.card_brand = "visa"
        user.card_saved_at = datetime.utcnow()
    db.add(user)
    db.commit()
    db.refresh(user)
    db.add(models.ParentProfile(user_id=user.id))
    db.commit()
    return user


def _seed_nanny(db, *, approved: bool = True, suspended: bool = False,
                with_docs: bool = True) -> models.Nanny:
    user = models.User(
        name="Test Nanny",
        role="nanny",
        email=f"nanny_{datetime.utcnow().timestamp()}@example.com",
        password_hash="x",
        is_admin=False,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    nanny = models.Nanny(user_id=user.id, approved=approved)
    nanny.is_suspended = suspended
    db.add(nanny)
    db.commit()
    db.refresh(nanny)
    profile = models.NannyProfile(
        nanny_id=nanny.id,
        nationality="South African",
        gender="female",
    )
    if with_docs:
        profile.sa_id_number = "9001014800086"
        profile.sa_id_document_url = "/static/uploads/test_id.pdf"
    db.add(profile)
    db.commit()
    return nanny


def _add_availability(db, nanny_id: int, start: datetime, end: datetime) -> None:
    db.add(models.NannyAvailability(
        nanny_id=nanny_id,
        date=start.date(),
        start_time=start.time(),
        end_time=end.time(),
        is_available=True,
        created_by="nanny",
        type="available",
        start_dt=_iso_z(start),
        end_dt=_iso_z(end),
    ))
    db.commit()


def _auth(user: models.User) -> dict:
    return {"Authorization": f"Bearer {_create_access_token(user)}"}


def _questionnaire() -> dict:
    return {
        "responsibilities": "Look after the kids",
        "adult_present": "yes",
        "booking_reason": "Date night",
        "meal_option": "meal_provided",
        "kids_count": 2,
        "disclaimer_basic_upkeep": True,
        "disclaimer_medicine": True,
        "disclaimer_extra_hours": True,
        "disclaimer_transport": True,
    }


def _create_request_payload(nanny_id: int, start: datetime, end: datetime) -> dict:
    payload = {"nanny_id": nanny_id, "start_dt": _iso_z(start), "end_dt": _iso_z(end)}
    payload.update(_questionnaire())
    return payload


def _future_window(hours_from_now: int = 48, duration_hours: int = 5):
    start = (datetime.utcnow() + timedelta(hours=hours_from_now)).replace(
        minute=0, second=0, microsecond=0, hour=9
    )
    return start, start + timedelta(hours=duration_hours)


@pytest.fixture(autouse=True)
def _isolate_external_services(monkeypatch):
    """No real Paystack charges, emails, or Google Calendar syncs in tests."""

    def fake_charge(**kwargs):
        return True, {
            "status": True,
            "data": {
                "status": "success",
                "reference": kwargs.get("reference") or "TESTREF",
                "id": 12345,
            },
        }

    monkeypatch.setattr(public_router, "create_supplementary_charge", fake_charge)
    monkeypatch.setattr(public_router, "send_notification", lambda *a, **k: None)
    monkeypatch.setattr(
        public_router, "_sync_confirmed_booking_request_to_google_calendar",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        public_router, "notify_booking_nanny_response", lambda *a, **k: None
    )
    yield


@pytest.fixture()
def db():
    session = SessionLocal()
    yield session
    session.close()


# ---------------------------------------------------------------------------
# booking request creation
# ---------------------------------------------------------------------------

def test_parent_without_card_cannot_create_request(db):
    parent = _seed_parent(db, with_card=False)
    nanny = _seed_nanny(db)
    start, end = _future_window()
    _add_availability(db, nanny.id, start, end)

    res = client.post(
        "/booking-requests",
        json=_create_request_payload(nanny.id, start, end),
        headers=_auth(parent),
    )
    assert res.status_code == 200
    assert res.json().get("requires_payment_method") is True


def test_create_request_happy_path_status_tbc(db):
    parent = _seed_parent(db)
    nanny = _seed_nanny(db)
    start, end = _future_window()
    _add_availability(db, nanny.id, start, end)

    res = client.post(
        "/booking-requests",
        json=_create_request_payload(nanny.id, start, end),
        headers=_auth(parent),
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "tbc"
    assert body["booking_request_id"]
    assert body["group_id"] == body["booking_request_id"]

    req = db.query(models.BookingRequest).filter(
        models.BookingRequest.id == body["booking_request_id"]
    ).first()
    assert req is not None
    assert req.payment_status == "pending_payment"
    assert req.total_cents and req.total_cents > 0
    assert req.wage_cents and req.wage_cents > 0


def test_create_request_fails_when_nanny_has_no_availability(db):
    parent = _seed_parent(db)
    nanny = _seed_nanny(db)  # no availability rows
    start, end = _future_window()

    res = client.post(
        "/booking-requests",
        json=_create_request_payload(nanny.id, start, end),
        headers=_auth(parent),
    )
    assert res.status_code == 409


def test_create_request_rejects_past_window(db):
    parent = _seed_parent(db)
    nanny = _seed_nanny(db)
    start = datetime.utcnow() - timedelta(days=1)
    end = start + timedelta(hours=4)
    _add_availability(db, nanny.id, start, end)

    res = client.post(
        "/booking-requests",
        json=_create_request_payload(nanny.id, start, end),
        headers=_auth(parent),
    )
    # Past windows are rejected with 409 (not 400) by
    # _validate_booking_windows_not_in_past. Locked in as current behavior.
    assert res.status_code == 409


def test_create_request_requires_questionnaire(db):
    parent = _seed_parent(db)
    nanny = _seed_nanny(db)
    start, end = _future_window()
    _add_availability(db, nanny.id, start, end)

    payload = {"nanny_id": nanny.id, "start_dt": _iso_z(start), "end_dt": _iso_z(end)}
    res = client.post("/booking-requests", json=payload, headers=_auth(parent))
    assert res.status_code == 400


def test_create_request_blocked_for_unapproved_nanny(db):
    parent = _seed_parent(db)
    nanny = _seed_nanny(db, approved=False)
    start, end = _future_window()
    _add_availability(db, nanny.id, start, end)

    res = client.post(
        "/booking-requests",
        json=_create_request_payload(nanny.id, start, end),
        headers=_auth(parent),
    )
    assert res.status_code == 400


# ---------------------------------------------------------------------------
# nanny accept flow (charge on acceptance)
# ---------------------------------------------------------------------------

def _create_request(db, parent, nanny, start, end) -> int:
    res = client.post(
        "/booking-requests",
        json=_create_request_payload(nanny.id, start, end),
        headers=_auth(parent),
    )
    assert res.status_code == 200, res.text
    return res.json()["booking_request_id"]


def test_accept_happy_path_charges_and_creates_booking(db):
    parent = _seed_parent(db)
    nanny = _seed_nanny(db)
    nanny_user = db.query(models.User).filter(models.User.id == nanny.user_id).first()
    start, end = _future_window()
    _add_availability(db, nanny.id, start, end)
    request_id = _create_request(db, parent, nanny, start, end)

    res = client.post(
        f"/nannies/me/booking-requests/{request_id}/accept",
        headers=_auth(nanny_user),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    assert body["payment_status"] == "paid"
    assert body["booking_id"]

    db.expire_all()
    req = db.query(models.BookingRequest).filter(
        models.BookingRequest.id == request_id
    ).first()
    assert req.status == "approved"
    assert req.nanny_response_status == "accepted"
    assert req.payment_status == "paid"
    assert req.paid_at is not None
    assert req.paystack_reference

    booking = db.query(models.Booking).filter(
        models.Booking.id == body["booking_id"]
    ).first()
    assert booking is not None
    assert booking.nanny_id == nanny.id
    assert booking.client_user_id == parent.id
    assert booking.booking_request_id == request_id

    # Acceptance must block the nanny's availability for that window.
    blocked = db.query(models.NannyAvailability).filter(
        models.NannyAvailability.nanny_id == nanny.id,
        models.NannyAvailability.type == "blocked",
    ).all()
    assert len(blocked) >= 1


def test_accept_is_idempotent_when_already_paid(db):
    parent = _seed_parent(db)
    nanny = _seed_nanny(db)
    nanny_user = db.query(models.User).filter(models.User.id == nanny.user_id).first()
    start, end = _future_window()
    _add_availability(db, nanny.id, start, end)
    request_id = _create_request(db, parent, nanny, start, end)

    first = client.post(
        f"/nannies/me/booking-requests/{request_id}/accept",
        headers=_auth(nanny_user),
    )
    assert first.status_code == 200
    second = client.post(
        f"/nannies/me/booking-requests/{request_id}/accept",
        headers=_auth(nanny_user),
    )
    assert second.status_code == 200
    assert second.json()["booking_id"] == first.json()["booking_id"]

    # Exactly one booking row per slot, not two.
    db.expire_all()
    bookings = db.query(models.Booking).filter(
        models.Booking.booking_request_id == request_id
    ).all()
    assert len(bookings) == 1


def test_accept_blocked_for_suspended_nanny(db):
    parent = _seed_parent(db)
    nanny = _seed_nanny(db)
    nanny_user = db.query(models.User).filter(models.User.id == nanny.user_id).first()
    start, end = _future_window()
    _add_availability(db, nanny.id, start, end)
    request_id = _create_request(db, parent, nanny, start, end)

    nanny.is_suspended = True
    db.commit()

    res = client.post(
        f"/nannies/me/booking-requests/{request_id}/accept",
        headers=_auth(nanny_user),
    )
    assert res.status_code == 403


def test_accept_blocked_when_documents_incomplete(db):
    parent = _seed_parent(db)
    nanny = _seed_nanny(db)
    nanny_user = db.query(models.User).filter(models.User.id == nanny.user_id).first()
    start, end = _future_window()
    _add_availability(db, nanny.id, start, end)
    request_id = _create_request(db, parent, nanny, start, end)

    profile = db.query(models.NannyProfile).filter(
        models.NannyProfile.nanny_id == nanny.id
    ).first()
    profile.sa_id_document_url = None
    db.commit()

    res = client.post(
        f"/nannies/me/booking-requests/{request_id}/accept",
        headers=_auth(nanny_user),
    )
    assert res.status_code == 403


def test_accept_fails_with_402_when_charge_fails(db, monkeypatch):
    parent = _seed_parent(db)
    nanny = _seed_nanny(db)
    nanny_user = db.query(models.User).filter(models.User.id == nanny.user_id).first()
    start, end = _future_window()
    _add_availability(db, nanny.id, start, end)
    request_id = _create_request(db, parent, nanny, start, end)

    def failing_charge(**kwargs):
        return False, {"message": "Insufficient funds", "data": {"status": "failed"}}

    monkeypatch.setattr(public_router, "create_supplementary_charge", failing_charge)

    res = client.post(
        f"/nannies/me/booking-requests/{request_id}/accept",
        headers=_auth(nanny_user),
    )
    assert res.status_code == 402

    db.expire_all()
    req = db.query(models.BookingRequest).filter(
        models.BookingRequest.id == request_id
    ).first()
    assert req.admin_reason == "payment_failed"
    assert req.payment_status != "paid"
    # No booking may exist after a failed charge.
    assert db.query(models.Booking).filter(
        models.Booking.booking_request_id == request_id
    ).count() == 0


def test_accept_blocked_when_parent_card_removed_before_acceptance(db):
    parent = _seed_parent(db)
    nanny = _seed_nanny(db)
    nanny_user = db.query(models.User).filter(models.User.id == nanny.user_id).first()
    start, end = _future_window()
    _add_availability(db, nanny.id, start, end)
    request_id = _create_request(db, parent, nanny, start, end)

    parent.paystack_auth_code = None
    db.commit()

    res = client.post(
        f"/nannies/me/booking-requests/{request_id}/accept",
        headers=_auth(nanny_user),
    )
    assert res.status_code == 409


def test_accept_rejects_overlapping_open_requests_from_same_parent(db):
    parent = _seed_parent(db)
    nanny_a = _seed_nanny(db)
    nanny_b = _seed_nanny(db)
    nanny_a_user = db.query(models.User).filter(models.User.id == nanny_a.user_id).first()
    start, end = _future_window()
    _add_availability(db, nanny_a.id, start, end)
    _add_availability(db, nanny_b.id, start, end)

    req_a = _create_request(db, parent, nanny_a, start, end)
    req_b = _create_request(db, parent, nanny_b, start, end)

    res = client.post(
        f"/nannies/me/booking-requests/{req_a}/accept",
        headers=_auth(nanny_a_user),
    )
    assert res.status_code == 200

    db.expire_all()
    other = db.query(models.BookingRequest).filter(
        models.BookingRequest.id == req_b
    ).first()
    assert other.status == "rejected"
    assert other.admin_reason == "filled"


# ---------------------------------------------------------------------------
# decline / respond flow
# ---------------------------------------------------------------------------

def test_nanny_can_decline_request(db):
    parent = _seed_parent(db)
    nanny = _seed_nanny(db)
    nanny_user = db.query(models.User).filter(models.User.id == nanny.user_id).first()
    start, end = _future_window()
    _add_availability(db, nanny.id, start, end)
    request_id = _create_request(db, parent, nanny, start, end)

    res = client.post(
        f"/nannies/me/booking-requests/{request_id}/respond",
        json={"response": "declined", "reason": "Not available"},
        headers=_auth(nanny_user),
    )
    assert res.status_code == 200, res.text

    db.expire_all()
    req = db.query(models.BookingRequest).filter(
        models.BookingRequest.id == request_id
    ).first()
    assert req.nanny_response_status == "declined"
    # Declining must never charge the parent.
    assert req.payment_status == "pending_payment"
    assert db.query(models.Booking).filter(
        models.Booking.booking_request_id == request_id
    ).count() == 0
