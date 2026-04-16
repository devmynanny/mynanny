import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import requests

from app import models

CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.events"
DEFAULT_CALENDAR_ID = "sayhi@mynanny.co.za"


class GoogleCalendarConfigError(RuntimeError):
    pass


def _load_service_account_info() -> dict:
    raw_json = (os.getenv("GOOGLE_CALENDAR_SERVICE_ACCOUNT_JSON") or "").strip()
    if raw_json:
        return json.loads(raw_json)

    path = (os.getenv("GOOGLE_CALENDAR_SERVICE_ACCOUNT_FILE") or "").strip()
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8"))

    raise GoogleCalendarConfigError("Google Calendar service account is not configured")


def _access_token() -> str:
    try:
        from google.auth.transport.requests import Request as GoogleAuthRequest
        from google.oauth2 import service_account
    except ImportError as exc:
        raise GoogleCalendarConfigError("google-auth is not installed") from exc

    info = _load_service_account_info()
    credentials = service_account.Credentials.from_service_account_info(
        info,
        scopes=[CALENDAR_SCOPE],
    )
    delegated_user = (os.getenv("GOOGLE_CALENDAR_DELEGATED_USER") or "").strip()
    if delegated_user:
        credentials = credentials.with_subject(delegated_user)
    credentials.refresh(GoogleAuthRequest())
    return credentials.token


def configured_calendar_id(db) -> str:
    row = db.query(models.AppSettings).filter(models.AppSettings.id == 1).first()
    db_calendar_id = (getattr(row, "google_calendar_id", None) or "").strip() if row else ""
    return db_calendar_id or (os.getenv("GOOGLE_CALENDAR_ID") or "").strip() or DEFAULT_CALENDAR_ID


def is_configured() -> bool:
    return bool(
        (os.getenv("GOOGLE_CALENDAR_SERVICE_ACCOUNT_JSON") or "").strip()
        or (os.getenv("GOOGLE_CALENDAR_SERVICE_ACCOUNT_FILE") or "").strip()
    )


def _event_payload(booking, parent_user, nanny_user) -> dict:
    start_dt = getattr(booking, "starts_at", None)
    end_dt = getattr(booking, "ends_at", None)
    if not start_dt or not end_dt:
        raise ValueError("Booking has no start or end time")

    location = (getattr(booking, "formatted_address", None) or getattr(booking, "location_label", None) or "").strip()
    parent_name = getattr(parent_user, "name", None) or getattr(parent_user, "email", None) or "Client"
    nanny_name = getattr(nanny_user, "name", None) or "Nanny"
    summary = f"My Nanny booking: {nanny_name} with {parent_name}"
    description_lines = [
        f"Booking ID: {booking.id}",
        f"Booking request ID: {getattr(booking, 'booking_request_id', None) or '-'}",
        f"Client: {parent_name} ({getattr(parent_user, 'email', None) or '-'})",
        f"Nanny: {nanny_name} ({getattr(nanny_user, 'email', None) or '-'})",
    ]

    return {
        "summary": summary,
        "location": location,
        "description": "\n".join(description_lines),
        "start": {"dateTime": start_dt.isoformat(), "timeZone": "Africa/Johannesburg"},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": "Africa/Johannesburg"},
        "extendedProperties": {
            "private": {
                "booking_id": str(booking.id),
                "booking_request_id": str(getattr(booking, "booking_request_id", "") or ""),
            }
        },
    }


def sync_booking_to_google_calendar(db, booking) -> Optional[str]:
    if not is_configured():
        return None
    if getattr(booking, "google_calendar_event_id", None):
        return booking.google_calendar_event_id

    parent_user = db.query(models.User).filter(models.User.id == booking.client_user_id).first()
    nanny = db.query(models.Nanny).filter(models.Nanny.id == booking.nanny_id).first()
    nanny_user = db.query(models.User).filter(models.User.id == nanny.user_id).first() if nanny else None
    if not parent_user or not nanny_user:
        raise ValueError("Booking parent or nanny user was not found")

    calendar_id = configured_calendar_id(db)
    token = _access_token()
    url = f"https://www.googleapis.com/calendar/v3/calendars/{quote(calendar_id, safe='')}/events"
    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        params={"sendUpdates": "none"},
        json=_event_payload(booking, parent_user, nanny_user),
        timeout=10,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Google Calendar sync failed: {response.status_code} {response.text[:300]}")

    event_id = response.json().get("id")
    if not event_id:
        raise RuntimeError("Google Calendar sync did not return an event ID")
    booking.google_calendar_event_id = event_id
    booking.google_calendar_synced_at = datetime.utcnow()
    booking.google_calendar_sync_error = None
    db.commit()
    return event_id
