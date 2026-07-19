"""
Tests for policy-driven notify(), message persistence, and the retry sweep.

External channels are stubbed at the service level (_twilio_whatsapp_send,
email client) so no network calls happen.
"""

from datetime import datetime, timedelta

import pytest

from app.main import app  # noqa: F401  (import creates the test DB schema)
from app import models
from app.db import SessionLocal
from app.services import notifications as notif


def _db():
    return SessionLocal()


def _seed_user(db, *, phone="+27820000000") -> models.User:
    user = models.User(
        name="Notify User",
        role="parent",
        email=f"notify_{datetime.utcnow().timestamp()}@example.com",
        password_hash="x",
        is_admin=False,
        is_active=True,
        phone=phone,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


class _FakeEmailClient:
    def __init__(self, fail=False):
        self.fail = fail
        self.sent = []

    def send(self, msg):
        if self.fail:
            raise RuntimeError("smtp down")
        self.sent.append(msg)


@pytest.fixture()
def db():
    session = SessionLocal()
    yield session
    session.close()


def _log_rows(db, user_id):
    return (
        db.query(models.NotificationLog)
        .filter(models.NotificationLog.user_id == user_id)
        .order_by(models.NotificationLog.id.asc())
        .all()
    )


def test_notify_falls_back_to_email_when_whatsapp_fails(db, monkeypatch):
    user = _seed_user(db)
    email_client = _FakeEmailClient()
    monkeypatch.setattr(notif, "_twilio_whatsapp_send", lambda *a, **k: (False, "not configured"))
    monkeypatch.setattr(notif, "get_email_client", lambda: email_client)

    ok = notif.notify(db, user.id, "payment_success", "Payment received", reference_id=1)
    db.commit()

    assert ok is True
    assert len(email_client.sent) == 1
    rows = _log_rows(db, user.id)
    statuses = [(r.channel, r.status) for r in rows]
    assert ("whatsapp", "failed") in statuses
    assert ("email", "sent") in statuses
    # Message body persisted on every attempt row.
    assert all(r.message == "Payment received" for r in rows)


def test_notify_stops_at_first_successful_channel(db, monkeypatch):
    user = _seed_user(db)
    email_client = _FakeEmailClient()
    monkeypatch.setattr(notif, "_twilio_whatsapp_send", lambda *a, **k: (True, ""))
    monkeypatch.setattr(notif, "get_email_client", lambda: email_client)

    ok = notif.notify(db, user.id, "payment_success", "Paid", reference_id=2)
    db.commit()

    assert ok is True
    assert email_client.sent == []  # email never attempted
    rows = _log_rows(db, user.id)
    assert [(r.channel, r.status) for r in rows] == [("whatsapp", "sent")]


def test_notify_writes_in_app_for_action_required_events(db, monkeypatch):
    user = _seed_user(db)
    monkeypatch.setattr(notif, "_twilio_whatsapp_send", lambda *a, **k: (True, ""))

    notif.notify(db, user.id, "overtime_request", "Please confirm overtime", reference_id=3)
    db.commit()

    in_app = (
        db.query(models.InAppNotification)
        .filter(models.InAppNotification.user_id == user.id)
        .all()
    )
    assert len(in_app) == 1
    assert "overtime" in in_app[0].body.lower()


def test_retry_sweep_resends_failed_and_respects_success(db, monkeypatch):
    user = _seed_user(db)
    email_client = _FakeEmailClient(fail=True)
    monkeypatch.setattr(notif, "_twilio_whatsapp_send", lambda *a, **k: (False, "down"))
    monkeypatch.setattr(notif, "get_email_client", lambda: email_client)

    # First attempt: both channels fail.
    ok = notif.notify(db, user.id, "booking_confirmed", "Confirmed!", reference_id=77)
    db.commit()
    assert ok is False

    # Channels recover; sweep should re-deliver.
    monkeypatch.setattr(notif, "_twilio_whatsapp_send", lambda *a, **k: (True, ""))
    retried = notif.retry_failed_notifications(db)
    assert retried == 1

    rows = _log_rows(db, user.id)
    assert ("whatsapp", "sent") in [(r.channel, r.status) for r in rows]

    # Second sweep: tuple now has a sent row -> nothing to retry.
    assert notif.retry_failed_notifications(db) == 0


def test_retry_sweep_caps_attempts(db, monkeypatch):
    user = _seed_user(db)
    email_client = _FakeEmailClient(fail=True)
    monkeypatch.setattr(notif, "_twilio_whatsapp_send", lambda *a, **k: (False, "down"))
    monkeypatch.setattr(notif, "get_email_client", lambda: email_client)

    notif.notify(db, user.id, "booking_confirmed", "Confirmed!", reference_id=88)
    db.commit()

    # Sweeps while channels stay down: each retry adds failed attempts until
    # the cap stops further retries.
    total_retries = 0
    for _ in range(6):
        total_retries += notif.retry_failed_notifications(db)
    assert total_retries <= notif.RETRY_MAX_ATTEMPTS

    final_failed = len([
        r for r in _log_rows(db, user.id) if r.status == "failed" and r.channel == "whatsapp"
    ])
    # Initial attempt + capped retries, never unbounded.
    assert final_failed <= notif.RETRY_MAX_ATTEMPTS + 1


def test_send_critical_is_policy_driven_alias(db, monkeypatch):
    user = _seed_user(db)
    monkeypatch.setattr(notif, "_twilio_whatsapp_send", lambda *a, **k: (True, ""))
    ok = notif.send_critical(db, user.id, "payout_sent", "Money on the way", reference_id=9)
    db.commit()
    assert ok is True
    rows = _log_rows(db, user.id)
    assert [(r.channel, r.status) for r in rows] == [("whatsapp", "sent")]
