from datetime import datetime, timedelta

import pytest

from app import models
from app.db import SessionLocal
from app.main import app  # noqa: F401
from app.services import notifications
from app.services.duty_notifications import run_duty_notification_sweep


@pytest.fixture()
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(autouse=True)
def stub_delivery(monkeypatch):
    monkeypatch.setattr(notifications.messaging, "send_whatsapp_message", lambda *a, **k: (True, ""))


def _seed_people(db):
    stamp = datetime.utcnow().timestamp()
    parent = models.User(
        name="Duty Parent",
        role="parent",
        email=f"duty_parent_{stamp}@example.com",
        phone="+27820000001",
        password_hash="x",
        is_active=True,
    )
    nanny_user = models.User(
        name="Duty Nanny",
        role="nanny",
        email=f"duty_nanny_{stamp}@example.com",
        phone="+27820000002",
        password_hash="x",
        is_active=True,
    )
    admin = models.User(
        name="Duty Admin",
        role="admin",
        email=f"duty_admin_{stamp}@example.com",
        phone="+27820000003",
        password_hash="x",
        is_admin=True,
        is_active=True,
    )
    db.add_all([parent, nanny_user, admin])
    db.commit()
    nanny = models.Nanny(user_id=nanny_user.id, approved=True)
    db.add(nanny)
    db.commit()
    return parent, nanny_user, nanny, admin


def _booking(db, *, parent, nanny, starts_at, ends_at, check_in_at=None):
    row = models.Booking(
        nanny_id=nanny.id,
        client_user_id=parent.id,
        day=starts_at.date(),
        status="accepted",
        price_cents=10000,
        starts_at=starts_at,
        ends_at=ends_at,
        check_in_at=check_in_at,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_start_reminder_is_sent_once_across_repeated_sweeps(db):
    parent, nanny_user, nanny, _ = _seed_people(db)
    now = datetime.utcnow().replace(microsecond=0)
    booking = _booking(
        db,
        parent=parent,
        nanny=nanny,
        starts_at=now + timedelta(minutes=60),
        ends_at=now + timedelta(hours=3),
    )

    first = run_duty_notification_sweep(db, now=now)
    second = run_duty_notification_sweep(db, now=now + timedelta(minutes=1))

    assert first["start_reminders"] == 1
    assert second["start_reminders"] == 0
    rows = db.query(models.NotificationLog).filter(
        models.NotificationLog.user_id == nanny_user.id,
        models.NotificationLog.event_type == "booking_start_reminder",
        models.NotificationLog.reference_id == booking.id,
    ).all()
    assert {row.channel for row in rows} == {"whatsapp", "in_app"}
    in_app = db.query(models.InAppNotification).filter(
        models.InAppNotification.user_id == nanny_user.id,
        models.InAppNotification.body.contains(f"booking #{booking.id}"),
    ).one()
    assert in_app.action_url == "/bookings"


@pytest.mark.parametrize("provider_status", ["accepted", "queued", "sending", "delivered", "read"])
def test_start_reminder_stays_deduplicated_after_provider_status_callback(db, provider_status):
    parent, nanny_user, nanny, _ = _seed_people(db)
    now = datetime.utcnow().replace(microsecond=0)
    booking = _booking(
        db,
        parent=parent,
        nanny=nanny,
        starts_at=now + timedelta(minutes=60),
        ends_at=now + timedelta(hours=3),
    )
    existing = models.NotificationLog(
        user_id=nanny_user.id,
        event_type="booking_start_reminder",
        channel="whatsapp",
        status=provider_status,
        reference_id=booking.id,
        message="Existing reminder",
    )
    db.add(existing)
    db.commit()

    result = run_duty_notification_sweep(db, now=now + timedelta(minutes=5))

    assert result["start_reminders"] == 0
    rows = db.query(models.NotificationLog).filter(
        models.NotificationLog.user_id == nanny_user.id,
        models.NotificationLog.event_type == "booking_start_reminder",
        models.NotificationLog.reference_id == booking.id,
    ).all()
    assert len(rows) == 1


def test_missed_checkin_escalates_and_finished_duty_prompts_checkout(db):
    parent, nanny_user, nanny, admin = _seed_people(db)
    now = datetime.utcnow().replace(microsecond=0)
    missed = _booking(
        db,
        parent=parent,
        nanny=nanny,
        starts_at=now - timedelta(minutes=20),
        ends_at=now + timedelta(hours=2),
    )
    checkout = _booking(
        db,
        parent=parent,
        nanny=nanny,
        starts_at=now - timedelta(hours=3),
        ends_at=now - timedelta(minutes=10),
        check_in_at=now - timedelta(hours=3),
    )

    result = run_duty_notification_sweep(db, now=now)

    assert result["missed_check_ins"] == 1
    assert result["checkout_reminders"] == 1
    expected = {
        (nanny_user.id, "missed_check_in", missed.id),
        (parent.id, "nanny_late_alert", missed.id),
        (admin.id, "duty_attention_required", missed.id),
        (nanny_user.id, "checkout_reminder", checkout.id),
    }
    actual = {
        (row.user_id, row.event_type, row.reference_id)
        for row in db.query(models.NotificationLog).filter(models.NotificationLog.status == "sent").all()
    }
    assert expected.issubset(actual)
