from datetime import datetime

import pytest

from app import models
from app.db import SessionLocal
from app.main import app  # noqa: F401
from app.services import notifications
from app.services.notification_controls import load_notification_controls
from app.services.notification_dispatch import claim_notification_dispatch
from app.services.scheduler_leases import claim_scheduler_job
from tests.test_booking_flow_api import _auth, client


@pytest.fixture()
def db(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AUTOMATED_NOTIFICATIONS_ENABLED", "true")
    session = SessionLocal()
    row = session.query(models.AppSettings).filter(models.AppSettings.id == 1).first()
    if not row:
        row = models.AppSettings(id=1)
        session.add(row)
    row.automated_notifications_enabled = True
    row.notification_test_mode = False
    row.notification_test_phone = None
    row.notification_volume_alert_threshold = 30
    session.commit()
    yield session
    row = session.query(models.AppSettings).filter(models.AppSettings.id == 1).first()
    if row:
        row.automated_notifications_enabled = True
        row.notification_test_mode = False
        row.notification_test_phone = None
        row.notification_volume_alert_threshold = 30
        session.commit()
    session.close()


def _user(db, suffix: str) -> models.User:
    row = models.User(
        name=f"Notification {suffix}",
        role="nanny",
        email=f"notification_controls_{suffix}_{datetime.utcnow().timestamp()}@example.com",
        phone="+27820000001",
        password_hash="x",
        is_active=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _superadmin(db) -> models.User:
    user = models.User(
        name="Notification Superadmin",
        role="admin",
        email=f"notification_admin_{datetime.utcnow().timestamp()}@example.com",
        password_hash="x",
        is_admin=True,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.add(models.AdminProfile(user_id=user.id, access_level="superadmin", is_superadmin=True))
    db.commit()
    return user


def test_disabled_master_switch_suppresses_external_but_keeps_in_app(db, monkeypatch):
    user = _user(db, "disabled")
    settings = db.query(models.AppSettings).filter(models.AppSettings.id == 1).one()
    settings.automated_notifications_enabled = False
    db.commit()
    monkeypatch.setattr(
        notifications.messaging,
        "send_whatsapp_message",
        lambda *_args, **_kwargs: pytest.fail("disabled delivery reached Twilio"),
    )

    delivered = notifications.notify(
        db,
        user.id,
        "booking_confirmed",
        "Your booking is confirmed.",
        reference_id=91001,
        action_url="/bookings",
    )
    db.commit()

    assert delivered is False
    assert db.query(models.NotificationLog).filter(
        models.NotificationLog.user_id == user.id,
        models.NotificationLog.event_type == "booking_confirmed",
        models.NotificationLog.status == "suppressed",
    ).count() == 2
    assert db.query(models.InAppNotification).filter(
        models.InAppNotification.user_id == user.id,
        models.InAppNotification.body == "Your booking is confirmed.",
    ).count() == 1
    assert db.query(models.NotificationDispatchClaim).filter(
        models.NotificationDispatchClaim.user_id == user.id,
        models.NotificationDispatchClaim.reference_id == 91001,
    ).count() == 0


def test_test_mode_redirects_and_labels_whatsapp(db, monkeypatch):
    user = _user(db, "redirect")
    settings = db.query(models.AppSettings).filter(models.AppSettings.id == 1).one()
    settings.notification_test_mode = True
    settings.notification_test_phone = "+27764024363"
    db.commit()
    sent = []

    def capture(phone, body, template_name=None):
        sent.append((phone, body, template_name))
        return True, "SMtestredirect"

    monkeypatch.setattr(notifications.messaging, "send_whatsapp_message", capture)

    assert notifications.notify(
        db,
        user.id,
        "new_booking_request",
        "A family sent a request.",
        reference_id=91002,
    )
    db.commit()

    assert sent == [
        (
            "+27764024363",
            "[TEST for Notification redirect (+27820000001)]\nA family sent a request.",
            None,
        )
    ]
    log = db.query(models.NotificationLog).filter(
        models.NotificationLog.provider_message_id == "SMtestredirect"
    ).one()
    assert log.destination == "+27764024363"
    assert log.test_redirected is True


def test_system_notification_is_claimed_once_for_recipient_event_and_reference(db, monkeypatch):
    user = _user(db, "dedupe")
    calls = []
    monkeypatch.setattr(
        notifications.messaging,
        "send_whatsapp_message",
        lambda *args, **kwargs: (calls.append((args, kwargs)) or (True, "SMdedupe")),
    )

    first = notifications.notify(db, user.id, "booking_start_reminder", "Starts soon", reference_id=91003)
    db.commit()
    second = notifications.notify(db, user.id, "booking_start_reminder", "Starts soon", reference_id=91003)
    db.commit()

    assert first is True
    assert second is False
    assert len(calls) == 1
    assert db.query(models.NotificationDispatchClaim).filter(
        models.NotificationDispatchClaim.user_id == user.id,
        models.NotificationDispatchClaim.event_type == "booking_start_reminder",
        models.NotificationDispatchClaim.reference_id == 91003,
    ).count() == 1


def test_suppressed_attempt_does_not_consume_delivery_claim(db):
    user = _user(db, "suppressed_claim")
    db.add(
        models.NotificationLog(
            user_id=user.id,
            event_type="booking_start_reminder",
            channel="whatsapp",
            status="suppressed",
            reference_id=91004,
        )
    )
    db.commit()

    assert claim_notification_dispatch(
        db,
        user_id=user.id,
        event_type="booking_start_reminder",
        reference_id=91004,
    ) is True


def test_environment_override_wins_over_database_switch(db, monkeypatch):
    monkeypatch.setenv("AUTOMATED_NOTIFICATIONS_ENABLED", "false")

    controls = load_notification_controls(db)

    assert controls.configured_enabled is True
    assert controls.environment_enabled is False
    assert controls.effective_enabled is False


def test_scheduler_lease_allows_only_one_claim_during_window(db):
    job_name = f"test-job-{datetime.utcnow().timestamp()}"

    assert claim_scheduler_job(db, job_name, lease_seconds=60) is True
    assert claim_scheduler_job(db, job_name, lease_seconds=60) is False


def test_superadmin_can_update_controls_and_read_delivery_activity(db):
    admin = _superadmin(db)

    response = client.put(
        "/admin/notification-controls",
        headers=_auth(admin),
        json={
            "automated_notifications_enabled": False,
            "notification_test_mode": False,
            "notification_test_phone": "+27764024363",
            "notification_volume_alert_threshold": 12,
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["automated_notifications_enabled"] is False
    assert body["effective_enabled"] is False
    assert body["manual_communicator_enabled"] is True
    assert body["notification_volume_alert_threshold"] == 12
    audit = db.query(models.AuditLog).filter(
        models.AuditLog.actor_user_id == admin.id,
        models.AuditLog.action == "notification_controls_updated",
    ).one()
    assert audit.entity == "app_settings"

    log_response = client.get("/admin/notification-log?limit=5", headers=_auth(admin))
    assert log_response.status_code == 200, log_response.text
    assert isinstance(log_response.json()["results"], list)


def test_superadmin_safety_test_respects_switch_test_mode_and_deduplication(db, monkeypatch):
    admin = _superadmin(db)
    settings = db.query(models.AppSettings).filter(models.AppSettings.id == 1).one()
    settings.automated_notifications_enabled = False
    db.commit()
    sent = []
    monkeypatch.setattr(
        notifications.messaging,
        "send_whatsapp_message",
        lambda phone, body, template_name=None: (sent.append((phone, body, template_name)) or (True, "SMsafetytest")),
    )

    disabled = client.post(
        "/admin/notification-controls/test",
        headers=_auth(admin),
        json={"reference_id": 92001},
    )
    assert disabled.status_code == 200, disabled.text
    assert disabled.json()["delivered"] is False
    external_attempts = [
        attempt for attempt in disabled.json()["attempts"] if attempt["channel"] != "in_app"
    ]
    in_app_attempts = [
        attempt for attempt in disabled.json()["attempts"] if attempt["channel"] == "in_app"
    ]
    assert {attempt["status"] for attempt in external_attempts} == {"suppressed"}
    assert {attempt["status"] for attempt in in_app_attempts} == {"sent"}
    assert sent == []

    settings = db.query(models.AppSettings).filter(models.AppSettings.id == 1).one()
    settings.automated_notifications_enabled = True
    settings.notification_test_mode = True
    settings.notification_test_phone = "+27764024363"
    db.commit()

    enabled = client.post(
        "/admin/notification-controls/test",
        headers=_auth(admin),
        json={"reference_id": 92001},
    )
    duplicate = client.post(
        "/admin/notification-controls/test",
        headers=_auth(admin),
        json={"reference_id": 92001},
    )

    assert enabled.status_code == 200, enabled.text
    assert enabled.json()["delivered"] is True
    assert enabled.json()["test_mode"] is True
    assert duplicate.status_code == 200, duplicate.text
    assert duplicate.json()["delivered"] is False
    assert len(sent) == 1
    assert sent[0][0] == "+27764024363"
    assert sent[0][1].startswith("[TEST for Notification Superadmin")
