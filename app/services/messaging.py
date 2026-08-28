"""Pure outbound chat-message transport: WhatsApp (Twilio) and Telegram.

No DB access here by design - app/services/notifications.py owns policy
(which channel, DB logging, retries) and app/services/conversations.py owns
conversation/message persistence. This module only knows how to actually
place an HTTP call to each provider.
"""
from __future__ import annotations

import os
import re
from typing import Optional

import requests
import truststore

from app.services.whatsapp_templates import content_sid_env_key


# Use the operating system trust store so local and hosted runtimes validate
# provider certificates consistently without disabling TLS verification.
truststore.inject_into_ssl()


def normalize_phone_number(value: str, default_country_code: str = "27") -> str:
    """Return an E.164-style number, defaulting local numbers to South Africa."""
    raw = str(value or "").strip()
    has_plus = raw.startswith("+")
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return raw
    if has_plus:
        return f"+{digits}"
    if digits.startswith("0"):
        return f"+{default_country_code}{digits[1:]}"
    if digits.startswith(default_country_code):
        return f"+{digits}"
    return f"+{digits}"


def send_whatsapp_message(to_number: str, body: str, template_name: Optional[str] = None) -> tuple[bool, str]:
    sid = (os.getenv("TWILIO_ACCOUNT_SID") or "").strip()
    token = (os.getenv("TWILIO_AUTH_TOKEN") or "").strip()
    from_number = (os.getenv("TWILIO_WHATSAPP_FROM") or "").strip()
    if not sid or not token or not from_number:
        return False, "Twilio WhatsApp not configured"

    # Twilio requires the whatsapp: prefix on both From and To.
    if not from_number.startswith("whatsapp:"):
        from_number = f"whatsapp:{from_number}"
    to_number = normalize_phone_number(to_number)
    if not to_number.startswith("whatsapp:"):
        to_number = f"whatsapp:{to_number}"

    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    payload = {"From": from_number, "To": to_number}
    status_callback = (os.getenv("TWILIO_STATUS_CALLBACK_URL") or "").strip()
    if status_callback:
        payload["StatusCallback"] = status_callback
    content_sid = (os.getenv(content_sid_env_key(template_name)) or "").strip() if template_name else ""
    if content_sid:
        payload["ContentSid"] = content_sid
    elif template_name and (os.getenv("TWILIO_REQUIRE_TEMPLATES") or "").strip().lower() in ("1", "true", "yes"):
        return False, f"Approved WhatsApp template is not configured for {template_name}"
    else:
        # Free-form bodies are valid only in an open WhatsApp customer-service
        # window. Production should set TWILIO_REQUIRE_TEMPLATES=true.
        payload["Body"] = body
    try:
        response = requests.post(url, data=payload, auth=(sid, token), timeout=20)
        if 200 <= response.status_code < 300:
            try:
                return True, str(response.json().get("sid") or "")
            except (ValueError, AttributeError):
                return True, ""
        return False, response.text or f"Twilio API error (status {response.status_code})"
    except requests.RequestException as exc:
        return False, str(exc)
    except Exception as exc:
        return False, str(exc)


def send_whatsapp_media(to_number: str, media_url: str, body: str = "") -> tuple[bool, str]:
    sid = (os.getenv("TWILIO_ACCOUNT_SID") or "").strip()
    token = (os.getenv("TWILIO_AUTH_TOKEN") or "").strip()
    from_number = (os.getenv("TWILIO_WHATSAPP_FROM") or "").strip()
    if not sid or not token or not from_number:
        return False, "Twilio WhatsApp not configured"
    if not from_number.startswith("whatsapp:"):
        from_number = f"whatsapp:{from_number}"
    to_number = normalize_phone_number(to_number)
    if not to_number.startswith("whatsapp:"):
        to_number = f"whatsapp:{to_number}"
    payload = {"From": from_number, "To": to_number, "MediaUrl": media_url}
    status_callback = (os.getenv("TWILIO_STATUS_CALLBACK_URL") or "").strip()
    if status_callback:
        payload["StatusCallback"] = status_callback
    if body:
        payload["Body"] = body
    try:
        response = requests.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
            data=payload,
            auth=(sid, token),
            timeout=30,
        )
        if 200 <= response.status_code < 300:
            return True, ""
        return False, response.text or f"Twilio API error (status {response.status_code})"
    except requests.RequestException as exc:
        return False, str(exc)


def send_telegram_message(chat_id: str, body: str) -> tuple[bool, str]:
    bot_token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    if not bot_token:
        return False, "Telegram bot not configured"

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        resp = requests.post(url, json={"chat_id": chat_id, "text": body}, timeout=20)
        data = resp.json() if resp.content else {}
        if resp.status_code == 200 and data.get("ok"):
            return True, ""
        return False, data.get("description") or f"Telegram API error (status {resp.status_code})"
    except Exception as exc:
        return False, str(exc)


def send_chat_message(channel: str, external_id: str, body: str) -> tuple[bool, str]:
    """Channel-agnostic dispatch for free-form (non-templated) sends - the
    admin ad hoc reply path uses this directly, bypassing NOTIFICATION_POLICY
    entirely since a manual reply isn't a policy-driven system event."""
    if channel == "whatsapp":
        return send_whatsapp_message(external_id, body)
    if channel == "telegram":
        return send_telegram_message(external_id, body)
    return False, f"unsupported channel: {channel}"
