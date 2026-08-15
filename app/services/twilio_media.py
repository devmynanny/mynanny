"""Securely import inbound Twilio media into My Nanny's private storage."""

from __future__ import annotations

import mimetypes
import os
from pathlib import PurePosixPath
from typing import Iterable

import requests

from app.services.storage import store_bytes

MAX_ATTACHMENTS = 10
MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024


def _extension(content_type: str, source_url: str) -> str:
    clean_type = content_type.split(";", 1)[0].strip().lower()
    known = {
        "audio/ogg": ".ogg",
        "audio/mpeg": ".mp3",
        "audio/mp4": ".m4a",
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }
    if clean_type in known:
        return known[clean_type]
    guessed = mimetypes.guess_extension(clean_type)
    if guessed:
        return guessed
    suffix = PurePosixPath(source_url.split("?", 1)[0]).suffix
    return suffix[:10] if suffix else ".bin"


def import_twilio_media(
    message_sid: str,
    media: Iterable[tuple[str, str]],
) -> list[dict[str, str | int]]:
    """Download signed Twilio media and return private attachment records."""
    account_sid = (os.getenv("TWILIO_ACCOUNT_SID") or "").strip()
    auth_token = (os.getenv("TWILIO_AUTH_TOKEN") or "").strip()
    if not account_sid or not auth_token:
        raise RuntimeError("Twilio credentials are not configured")

    attachments: list[dict[str, str | int]] = []
    for index, (source_url, declared_type) in enumerate(list(media)[:MAX_ATTACHMENTS]):
        response = requests.get(
            source_url,
            auth=(account_sid, auth_token),
            timeout=30,
        )
        response.raise_for_status()
        content = response.content
        if len(content) > MAX_ATTACHMENT_BYTES:
            raise ValueError("Twilio media attachment exceeds the 25 MB limit")
        content_type = (
            declared_type
            or response.headers.get("Content-Type")
            or "application/octet-stream"
        ).split(";", 1)[0].strip().lower()
        key = f"communicator/whatsapp/{message_sid}/{index}{_extension(content_type, source_url)}"
        attachments.append({
            "url": store_bytes(key, content, content_type),
            "content_type": content_type,
            "size": len(content),
        })
    return attachments
