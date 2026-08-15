"""
Tests for the admin conversations inbox: list, thread view (mark-read),
and reply (including the WhatsApp 24h window guard).
"""

import json

from datetime import timedelta

from app import models
from app.db import SessionLocal
from app.utils.time import utc_now

from tests.test_booking_flow_api import client, _auth
from tests.test_accounting_reconciliation import _seed_admin


def _db():
    return SessionLocal()


def _seed_conversation(db, *, channel="whatsapp", external_id="+27821230000", last_inbound_at=None):
    conv = models.Conversation(channel=channel, external_id=external_id, last_inbound_at=last_inbound_at)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def _seed_message(db, conv, *, direction="inbound", body="hi", status="received"):
    msg = models.Message(conversation_id=conv.id, direction=direction, channel=conv.channel, body=body, status=status)
    db.add(msg)
    conv.last_message_at = utc_now()
    if direction == "inbound":
        conv.last_inbound_at = utc_now()
        conv.unread_count = (conv.unread_count or 0) + 1
    db.commit()
    db.refresh(msg)
    return msg


def test_list_conversations_requires_admin():
    res = client.get("/admin/conversations")
    assert res.status_code in (401, 403)


def test_open_parent_whatsapp_conversation_from_booking():
    db = _db()
    try:
        admin = _seed_admin(db)
        parent = models.User(
            name="Communicator Parent",
            role="parent",
            email=f"communicator_parent_{utc_now().timestamp()}@example.com",
            password_hash="x",
            is_active=True,
        )
        db.add(parent)
        db.commit()
        db.refresh(parent)
        db.add(models.ParentProfile(user_id=parent.id, phone="+27821239999"))
        db.commit()

        res = client.post(
            "/admin/conversations/open",
            json={"user_id": parent.id, "channel": "whatsapp"},
            headers=_auth(admin),
        )

        assert res.status_code == 200
        assert res.json()["external_id"] == "+27821239999"
        conv = db.query(models.Conversation).filter(models.Conversation.id == res.json()["conversation_id"]).one()
        assert conv.user_id == parent.id
    finally:
        db.close()


def test_list_conversations_returns_preview_and_unread(monkeypatch):
    db = _db()
    try:
        admin = _seed_admin(db)
        conv = _seed_conversation(db, external_id="+27821230001")
        _seed_message(db, conv, body="Hello there")

        res = client.get("/admin/conversations", headers=_auth(admin))
        assert res.status_code == 200
        rows = [r for r in res.json()["results"] if r["id"] == conv.id]
        assert len(rows) == 1
        assert rows[0]["last_message_preview"] == "Hello there"
        assert rows[0]["unread_count"] == 1
    finally:
        db.close()


def test_get_thread_marks_conversation_read():
    db = _db()
    try:
        admin = _seed_admin(db)
        conv = _seed_conversation(db, external_id="+27821230002")
        _seed_message(db, conv, body="First message")
        db.refresh(conv)
        assert conv.unread_count == 1

        res = client.get(f"/admin/conversations/{conv.id}/messages", headers=_auth(admin))
        assert res.status_code == 200
        assert len(res.json()["results"]) == 1

        db.expire_all()
        updated = db.query(models.Conversation).filter(models.Conversation.id == conv.id).first()
        assert updated.unread_count == 0
    finally:
        db.close()


def test_get_thread_returns_message_attachments():
    db = _db()
    try:
        admin = _seed_admin(db)
        conv = _seed_conversation(db, external_id="+27821230012")
        msg = _seed_message(db, conv, body="")
        msg.attachments_json = json.dumps([{
            "url": "/media/communicator/whatsapp/SM1/0.ogg",
            "content_type": "audio/ogg",
            "size": 123,
        }])
        db.commit()

        res = client.get(
            f"/admin/conversations/{conv.id}/messages",
            headers=_auth(admin),
        )
        assert res.status_code == 200
        attachment = res.json()["results"][0]["attachments"][0]
        assert attachment["content_type"] == "audio/ogg"
        assert attachment["url"].startswith("/media/communicator/")
    finally:
        db.close()


def test_reply_rejected_outside_whatsapp_24h_window():
    db = _db()
    try:
        admin = _seed_admin(db)
        conv = _seed_conversation(
            db, external_id="+27821230003", last_inbound_at=utc_now() - timedelta(hours=30)
        )

        res = client.post(
            f"/admin/conversations/{conv.id}/reply",
            json={"body": "We're back!"},
            headers=_auth(admin),
        )
        assert res.status_code == 422
        assert "24-hour" in res.json()["detail"]
    finally:
        db.close()


def test_reply_sends_within_whatsapp_window(monkeypatch):
    db = _db()
    try:
        admin = _seed_admin(db)
        conv = _seed_conversation(db, external_id="+27821230004", last_inbound_at=utc_now())

        monkeypatch.setattr(
            "app.routers.admin.messaging.send_chat_message",
            lambda channel, external_id, body: (True, ""),
        )

        res = client.post(
            f"/admin/conversations/{conv.id}/reply",
            json={"body": "On our way"},
            headers=_auth(admin),
        )
        assert res.status_code == 200
        body = res.json()
        assert body["direction"] == "outbound"
        assert body["status"] == "sent"

        db.expire_all()
        msg = (
            db.query(models.Message)
            .filter(models.Message.conversation_id == conv.id, models.Message.direction == "outbound")
            .first()
        )
        assert msg is not None
        assert msg.sender_user_id == admin.id
    finally:
        db.close()


def test_reply_send_failure_returns_502(monkeypatch):
    db = _db()
    try:
        admin = _seed_admin(db)
        conv = _seed_conversation(db, channel="telegram", external_id="123456")

        monkeypatch.setattr(
            "app.routers.admin.messaging.send_chat_message",
            lambda channel, external_id, body: (False, "bot not configured"),
        )

        res = client.post(
            f"/admin/conversations/{conv.id}/reply",
            json={"body": "hi"},
            headers=_auth(admin),
        )
        assert res.status_code == 502

        db.expire_all()
        msg = (
            db.query(models.Message)
            .filter(models.Message.conversation_id == conv.id, models.Message.direction == "outbound")
            .first()
        )
        assert msg is not None
        assert msg.status == "failed"
    finally:
        db.close()
