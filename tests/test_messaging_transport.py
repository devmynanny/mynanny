from app.services import messaging
from app.services.messaging import normalize_phone_number


def test_normalize_phone_number_supports_south_african_local_format():
    assert normalize_phone_number("076 202 7746") == "+27762027746"


def test_normalize_phone_number_preserves_international_format():
    assert normalize_phone_number("+1 (415) 555-0123") == "+14155550123"


class _Response:
    status_code = 201
    text = ""

    def json(self):
        return {"sid": "SMtest123"}


def _twilio_env(monkeypatch):
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "ACtest")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "secret")
    monkeypatch.setenv("TWILIO_WHATSAPP_FROM", "+14155238886")


def test_whatsapp_uses_content_sid_for_configured_template(monkeypatch):
    _twilio_env(monkeypatch)
    monkeypatch.setenv("TWILIO_CONTENT_SID_NEW_BOOKING_REQUEST", "HXapproved")
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(kwargs)
        return _Response()

    monkeypatch.setattr(messaging.requests, "post", fake_post)

    ok, error = messaging.send_whatsapp_message(
        "0762027746",
        "Private dynamic details",
        template_name="new_booking_request",
    )

    assert ok is True
    assert error == "SMtest123"
    assert captured["data"]["ContentSid"] == "HXapproved"
    assert "Body" not in captured["data"]
    assert captured["data"]["To"] == "whatsapp:+27762027746"


def test_whatsapp_registers_delivery_status_callback(monkeypatch):
    _twilio_env(monkeypatch)
    monkeypatch.setenv("TWILIO_STATUS_CALLBACK_URL", "https://api.example.com/whatsapp/status")
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(kwargs)
        return _Response()

    monkeypatch.setattr(messaging.requests, "post", fake_post)
    ok, provider_id = messaging.send_whatsapp_message("0762027746", "Hello")

    assert ok is True
    assert provider_id == "SMtest123"
    assert captured["data"]["StatusCallback"] == "https://api.example.com/whatsapp/status"


def test_production_mode_rejects_missing_template(monkeypatch):
    _twilio_env(monkeypatch)
    monkeypatch.setenv("TWILIO_REQUIRE_TEMPLATES", "true")
    monkeypatch.delenv("TWILIO_CONTENT_SID_BOOKING_START_REMINDER", raising=False)

    ok, error = messaging.send_whatsapp_message(
        "+27764024363",
        "Reminder body",
        template_name="booking_start_reminder",
    )

    assert ok is False
    assert "not configured" in error
