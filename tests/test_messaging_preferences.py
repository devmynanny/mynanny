"""
Tests for the self-service messaging channel preference and Telegram
account-linking endpoints, plus the /auth/me extension.
"""

from app import models
from app.db import SessionLocal

from tests.test_booking_flow_api import client, _auth, _seed_parent


def _db():
    return SessionLocal()


def test_auth_me_reports_default_channel_and_unlinked():
    db = _db()
    try:
        user = _seed_parent(db)
        res = client.get("/auth/me", headers=_auth(user))
        assert res.status_code == 200
        body = res.json()
        assert body["preferred_messaging_channel"] == "whatsapp"
        assert body["telegram_linked"] is False
    finally:
        db.close()


def test_telegram_connect_requires_bot_configured(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_USERNAME", raising=False)
    db = _db()
    try:
        user = _seed_parent(db)
        res = client.post("/me/telegram/connect", headers=_auth(user))
        assert res.status_code == 400
    finally:
        db.close()


def test_telegram_connect_returns_deep_link(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_USERNAME", "MyNannyBot")
    db = _db()
    try:
        user = _seed_parent(db)
        res = client.post("/me/telegram/connect", headers=_auth(user))
        assert res.status_code == 200
        body = res.json()
        assert body["deep_link"].startswith("https://t.me/MyNannyBot?start=")

        token_value = body["deep_link"].split("start=", 1)[1]
        row = db.query(models.TelegramLinkToken).filter(models.TelegramLinkToken.token == token_value).first()
        assert row is not None
        assert row.user_id == user.id
    finally:
        db.close()


def test_set_messaging_channel_rejects_unlinked_telegram():
    db = _db()
    try:
        user = _seed_parent(db)
        res = client.post(
            "/me/messaging-channel",
            json={"channel": "telegram"},
            headers=_auth(user),
        )
        assert res.status_code == 400
    finally:
        db.close()


def test_set_messaging_channel_allows_telegram_once_linked():
    db = _db()
    try:
        user = _seed_parent(db)
        user.telegram_chat_id = "555111"
        db.commit()

        res = client.post(
            "/me/messaging-channel",
            json={"channel": "telegram"},
            headers=_auth(user),
        )
        assert res.status_code == 200
        assert res.json()["preferred_messaging_channel"] == "telegram"

        db.expire_all()
        updated = db.query(models.User).filter(models.User.id == user.id).first()
        assert updated.preferred_messaging_channel == "telegram"
    finally:
        db.close()


def test_set_messaging_channel_rejects_invalid_value():
    db = _db()
    try:
        user = _seed_parent(db)
        res = client.post(
            "/me/messaging-channel",
            json={"channel": "carrier_pigeon"},
            headers=_auth(user),
        )
        assert res.status_code == 400
    finally:
        db.close()
