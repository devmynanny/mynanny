"""
Expiry sweep for stale booking-request adverts.

Policy (documented in APP_RULES.md):
- A booking request still awaiting a nanny response (status 'tbc' or
  'pending_admin', response not 'accepted') whose requested start time has
  passed can no longer be fulfilled - acceptance is already blocked at
  accept-time by _validate_booking_windows_not_in_past.
- The sweep marks such requests status='rejected' with admin_reason='expired'
  so dashboards stop showing them as live work, and reporting can distinguish
  expiry from human rejection via admin_reason.
- Requests a nanny has already accepted are never touched by the sweep.
"""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from app import models

EXPIRED_ADMIN_REASON = "expired"


def _naive_utc(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    try:
        text = str(value).strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        if " " in text and "T" not in text:
            text = text.replace(" ", "T")
        parsed = datetime.fromisoformat(text)
        return parsed.replace(tzinfo=None) if parsed.tzinfo else parsed
    except Exception:
        return None


def _request_start(req: models.BookingRequest) -> Optional[datetime]:
    return _naive_utc(getattr(req, "requested_starts_at", None)) or _naive_utc(
        getattr(req, "start_dt", None)
    )


def is_request_expired(req: models.BookingRequest, now: Optional[datetime] = None) -> bool:
    """An open advert is expired once its start time has passed."""
    if req.status not in ("tbc", "pending_admin"):
        return False
    if (getattr(req, "nanny_response_status", None) or "").lower() == "accepted":
        return False
    start = _request_start(req)
    if start is None:
        return False
    return start <= (now or datetime.utcnow())


def expire_stale_booking_requests(db: Session, now: Optional[datetime] = None) -> int:
    """Mark all expired open adverts as rejected/expired. Returns count."""
    current = now or datetime.utcnow()
    candidates = (
        db.query(models.BookingRequest)
        .filter(models.BookingRequest.status.in_(["tbc", "pending_admin"]))
        .all()
    )
    expired_count = 0
    for req in candidates:
        if not is_request_expired(req, current):
            continue
        req.status = "rejected"
        req.admin_reason = EXPIRED_ADMIN_REASON
        req.admin_decided_at = current
        expired_count += 1
    if expired_count:
        db.commit()
    return expired_count
