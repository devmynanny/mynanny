"""
Tests for the WhatsApp (Twilio) and Telegram inbound webhooks: signature/secret
enforcement and conversation/message ingestion.
"""

import base64
import hashlib
import hmac

from app import models
from app.db import SessionLocal

from tests.test_booking_flow_api import client


TWILIO_AUTH_TOKEN = "test_twilio_auth_token"
TELEGRAM_SECRET = "test_telegram_webhook_secret"


def _db():
    return SessionLocal()


def _twilio_signature(url: str, params: dict, auth_token: str) -> str:
    base = url
    for key in sorted(params.keys()):
        base += key + str(params[key])
    return base64.b64encode(hmac.new(auth_token.encode("utf-8"), base.encode("utf-8"), hashlib.sha1).digest()).decode("ascii")


def _signed_whatsapp_post(params: dict, auth_token: str = TWILIO_AUTH_TOKEN):
    url = "http://testserver/whatsapp/webhook"
    signature = _twilio_signature(url, params, auth_token)
    return client.post(
        "/whatsapp/webhook",
        data=params,
        headers={"x-twilio-signature": signature},
    )


def _signed_whatsapp_status_post(params: dict, auth_token: str = TWILIO_AUTH_TOKEN):
    url = "http://testserver/whatsapp/status"
    signature = _twilio_signature(url, params, auth_token)
    return client.post(
        "/whatsapp/status",
        data=params,
        headers={"x-twilio-signature": signature},
    )


def test_whatsapp_webhook_rejects_missing_signature(monkeypatch):
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", TWILIO_AUTH_TOKEN)
    res = client.post("/whatsapp/webhook", data={"From": "whatsapp:+27821112222", "Body": "hi"})
    assert res.status_code == 400


def test_whatsapp_webhook_rejects_bad_signature(monkeypatch):
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", TWILIO_AUTH_TOKEN)
    res = client.post(
        "/whatsapp/webhook",
        data={"From": "whatsapp:+27821112222", "Body": "hi"},
        headers={"x-twilio-signature": "deadbeef" * 5},
    )
    assert res.status_code == 400


def test_whatsapp_status_callback_is_verified_and_reconciled(monkeypatch):
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", TWILIO_AUTH_TOKEN)
    captured = {}

    def fake_reconcile(db, message_sid, status, error):
        captured.update(message_sid=message_sid, status=status, error=error)
        return True

    monkeypatch.setattr("app.routers.public.record_twilio_delivery_status", fake_reconcile)
    res = _signed_whatsapp_status_post({
        "MessageSid": "SM_status_001",
        "MessageStatus": "undelivered",
        "ErrorCode": "63112",
        "ErrorMessage": "Meta disabled the WABA",
    })

    assert res.status_code == 204
    assert captured == {
        "message_sid": "SM_status_001",
        "status": "undelivered",
        "error": "63112: Meta disabled the WABA",
    }


def test_whatsapp_status_callback_rejects_bad_signature(monkeypatch):
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", TWILIO_AUTH_TOKEN)
    res = client.post(
        "/whatsapp/status",
        data={"MessageSid": "SM_status_002", "MessageStatus": "failed"},
        headers={"x-twilio-signature": "invalid"},
    )
    assert res.status_code == 400


def test_whatsapp_webhook_ingests_matched_user_message(monkeypatch):
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", TWILIO_AUTH_TOKEN)
    db = _db()
    try:
        user = models.User(
            name="WA Test Parent",
            role="parent",
            email="wa_webhook_test@example.com",
            password_hash="x",
            phone="+27821119999",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        res = _signed_whatsapp_post({
            "From": "whatsapp:+27821119999",
            "Body": "Is the nanny still available?",
            "MessageSid": "SM_test_001",
        })
        assert res.status_code == 200
        assert "<Response></Response>" in res.text

        conv = (
            db.query(models.Conversation)
            .filter(models.Conversation.channel == "whatsapp", models.Conversation.external_id == "+27821119999")
            .first()
        )
        assert conv is not None
        assert conv.user_id == user.id
        assert conv.unread_count == 1

        msg = db.query(models.Message).filter(models.Message.conversation_id == conv.id).first()
        assert msg.direction == "inbound"
        assert msg.body == "Is the nanny still available?"
        assert msg.external_message_id == "SM_test_001"

        # Twilio retry with the same MessageSid must not double-count.
        _signed_whatsapp_post({
            "From": "whatsapp:+27821119999",
            "Body": "Is the nanny still available?",
            "MessageSid": "SM_test_001",
        })
        db.expire_all()
        conv2 = db.query(models.Conversation).filter(models.Conversation.id == conv.id).first()
        assert conv2.unread_count == 1
    finally:
        db.close()


def test_whatsapp_webhook_ingests_private_media_attachment(monkeypatch):
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", TWILIO_AUTH_TOKEN)
    monkeypatch.setattr(
        "app.routers.public.import_twilio_media",
        lambda sid, media: [{
            "url": f"/media/communicator/whatsapp/{sid}/0.jpg",
            "content_type": "image/jpeg",
            "size": 4,
        }],
    )
    db = _db()
    try:
        res = _signed_whatsapp_post({
            "From": "whatsapp:+27821117777",
            "Body": "",
            "MessageSid": "SM_media_001",
            "NumMedia": "1",
            "MediaUrl0": "https://api.twilio.com/media/ME1",
            "MediaContentType0": "image/jpeg",
        })
        assert res.status_code == 200

        msg = db.query(models.Message).filter(
            models.Message.external_message_id == "SM_media_001"
        ).one()
        assert '"content_type": "image/jpeg"' in msg.attachments_json
        assert "/media/communicator/whatsapp/SM_media_001/0.jpg" in msg.attachments_json
    finally:
        db.close()


def test_telegram_webhook_rejects_wrong_secret(monkeypatch):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", TELEGRAM_SECRET)
    res = client.post(
        "/telegram/webhook/wrong-secret",
        json={"message": {"chat": {"id": 555}, "text": "hi", "message_id": 1}},
    )
    assert res.status_code == 404


def test_telegram_webhook_ingests_message(monkeypatch):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", TELEGRAM_SECRET)
    db = _db()
    try:
        res = client.post(
            f"/telegram/webhook/{TELEGRAM_SECRET}",
            json={"message": {"chat": {"id": 777888}, "text": "Hello from Telegram", "message_id": 42}},
        )
        assert res.status_code == 200

        conv = (
            db.query(models.Conversation)
            .filter(models.Conversation.channel == "telegram", models.Conversation.external_id == "777888")
            .first()
        )
        assert conv is not None
        msg = db.query(models.Message).filter(models.Message.conversation_id == conv.id).first()
        assert msg.body == "Hello from Telegram"
        assert msg.external_message_id == "42"
    finally:
        db.close()


def test_telegram_webhook_start_token_links_account(monkeypatch):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", TELEGRAM_SECRET)
    db = _db()
    try:
        user = models.User(
            name="TG Test Nanny",
            role="nanny",
            email="tg_webhook_test@example.com",
            password_hash="x",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        from app.services import conversations as conv_service

        token = conv_service.create_telegram_link_token(db, user)

        res = client.post(
            f"/telegram/webhook/{TELEGRAM_SECRET}",
            json={"message": {"chat": {"id": 333444}, "text": f"/start {token.token}", "message_id": 1}},
        )
        assert res.status_code == 200

        db.expire_all()
        updated = db.query(models.User).filter(models.User.id == user.id).first()
        assert updated.telegram_chat_id == "333444"

        # The /start payload itself must not be persisted as a browsable message.
        conv = (
            db.query(models.Conversation)
            .filter(models.Conversation.channel == "telegram", models.Conversation.external_id == "333444")
            .first()
        )
        assert conv is None
    finally:
        db.close()
