"""Pure outbound chat-message transport: WhatsApp (Twilio) and Telegram.

No DB access here by design - app/services/notifications.py owns policy
(which channel, DB logging, retries) and app/services/conversations.py owns
conversation/message persistence. This module only knows how to actually
place an HTTP call to each provider.
"""
from __future__ import annotations

import base64
import os
from typing import Optional
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError
from urllib.parse import quote

import requests


def send_whatsapp_message(to_number: str, body: str, template_name: Optional[str] = None) -> tuple[bool, str]:
    sid = (os.getenv("TWILIO_ACCOUNT_SID") or "").strip()
    token = (os.getenv("TWILIO_AUTH_TOKEN") or "").strip()
    from_number = (os.getenv("TWILIO_WHATSAPP_FROM") or "").strip()
    if not sid or not token or not from_number:
        return False, "Twilio WhatsApp not configured"

    # Twilio requires the whatsapp: prefix on both From and To.
    if not from_number.startswith("whatsapp:"):
        from_number = f"whatsapp:{from_number}"
    to_number = str(to_number).strip()
    if not to_number.startswith("whatsapp:"):
        to_number = f"whatsapp:{to_number}"

    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    payload = {
        "From": from_number,
        "To": to_number,
        "Body": body,
    }
    if template_name:
        payload["Body"] = body
    data = "&".join(f"{k}={quote(str(v))}" for k, v in payload.items()).encode("utf-8")
    auth = base64.b64encode(f"{sid}:{token}".encode("utf-8")).decode("ascii")
    req = urllib_request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urllib_request.urlopen(req, timeout=20) as res:
            res.read()
        return True, ""
    except HTTPError as exc:
        # Read the response body when available - Twilio's error payloads
        # (e.g. code 63016, outside the 24h customer-service window) live
        # here, not in str(exc).
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except Exception:
            detail = str(exc)
        return False, detail
    except URLError as exc:
        return False, str(exc)
    except Exception as exc:
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
