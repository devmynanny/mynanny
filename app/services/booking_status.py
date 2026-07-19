from __future__ import annotations

from datetime import datetime
from typing import Any, Optional


CANONICAL_BOOKING_STATUSES = (
    "draft",
    "broadcast_sent",
    "awaiting_acceptance",
    "awaiting_payment",
    "payment_failed",
    "confirmed",
    "upcoming",
    "in_progress",
    "awaiting_time_confirmation",
    "awaiting_overtime_approval",
    "completed",
    "past",
    "admin_review",
    "cancelled",
)

LEGACY_STATUS_MAP = {
    "pending": "awaiting_acceptance",
    "accepted": "confirmed",
    "approved": "confirmed",
    "rejected": "cancelled",
}

# ---------------------------------------------------------------------------
# Write-side vocabularies (single source of truth).
#
# These are the ONLY values allowed to be written to the corresponding
# columns. Model-level validators (app/models) enforce them on every
# assignment, so no code path can introduce a rogue status string.
# The read-side derivation above maps these raw values to the canonical
# display states.
# ---------------------------------------------------------------------------

# booking_requests.status - mirrors the DB CHECK constraint exactly.
REQUEST_WRITE_STATUSES = frozenset(
    {"tbc", "pending_admin", "approved", "rejected", "cancelled"}
)

# bookings.status - observed vocabulary across all write sites plus default.
BOOKING_WRITE_STATUSES = frozenset(
    {
        "pending",
        "approved",
        "accepted",
        "active",
        "in_progress",
        "admin_review",
        "awaiting_overtime_approval",
        "completed",
        "cancelled",
    }
)

# booking_requests.nanny_response_status - mirrors the DB CHECK constraint.
RESPONSE_WRITE_STATUSES = frozenset({"pending", "accepted", "declined", "deciding"})

# booking_requests.payment_status - mirrors the DB CHECK constraint exactly.
# NOTE: payment failure is expressed via admin_reason="payment_failed", never
# via payment_status (the DB CHECK forbids a "failed" value); the read-side
# "failed" branch above only exists for defensive display handling.
PAYMENT_WRITE_STATUSES = frozenset({"pending_payment", "paid", "cancelled"})


def canonical_booking_status(status: str | None) -> str:
    if not status:
        return "draft"
    normalized = str(status).strip().lower()
    return LEGACY_STATUS_MAP.get(normalized, normalized)


def _as_dt(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    try:
        text = str(value).strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        if " " in text and "T" not in text:
            text = text.replace(" ", "T")
        return datetime.fromisoformat(text)
    except Exception:
        return None


def booking_state_from_booking(booking: Any, now: Optional[datetime] = None) -> str:
    status = canonical_booking_status(getattr(booking, "status", None))
    current = now or datetime.utcnow()
    check_in_at = _as_dt(getattr(booking, "check_in_at", None))
    check_out_at = _as_dt(getattr(booking, "check_out_at", None))
    start_dt = _as_dt(getattr(booking, "starts_at", None) or getattr(booking, "start_dt", None))
    end_dt = _as_dt(getattr(booking, "ends_at", None) or getattr(booking, "end_dt", None))

    if status in {"cancelled"}:
        return "cancelled"
    if status in {"rejected"}:
        return "cancelled"
    if getattr(booking, "overrun_status", None) == "awaiting_parent":
        return "awaiting_overtime_approval"
    if getattr(booking, "overrun_status", None) == "queried":
        return "admin_review"
    if getattr(booking, "overrun_status", None) == "charged" and check_out_at and not getattr(booking, "payout_released_at", None):
        return "completed"
    if check_out_at:
        return "completed"
    if check_in_at and not check_out_at:
        return "in_progress"
    if getattr(booking, "payment_status", None) == "failed":
        return "payment_failed"
    if getattr(booking, "payment_status", None) == "pending_payment":
        return "awaiting_payment"
    if start_dt and end_dt and start_dt <= current < end_dt:
        return "in_progress"
    if end_dt and end_dt <= current:
        return "past"
    if status in {"confirmed", "accepted"}:
        return "confirmed"
    if status in {"pending", "awaiting_acceptance", "broadcast_sent"}:
        return "awaiting_acceptance"
    if status in {"approved", "upcoming"}:
        return "upcoming"
    if status in {"completed", "past"}:
        return "completed"
    if status in {"admin_review"}:
        return "admin_review"
    return status


def booking_state_from_request(request: Any, now: Optional[datetime] = None) -> str:
    status = canonical_booking_status(getattr(request, "status", None))
    payment_status = str(getattr(request, "payment_status", None) or "").strip().lower()
    response_status = str(getattr(request, "nanny_response_status", None) or "").strip().lower()
    current = now or datetime.utcnow()
    start_dt = _as_dt(getattr(request, "requested_starts_at", None) or getattr(request, "start_dt", None))
    end_dt = _as_dt(getattr(request, "requested_ends_at", None) or getattr(request, "end_dt", None))
    paid_at = _as_dt(getattr(request, "paid_at", None))

    if status in {"cancelled"}:
        return "cancelled"
    if status in {"rejected"}:
        return "cancelled"
    if payment_status == "failed":
        return "payment_failed"
    if status in {"pending_admin"}:
        return "broadcast_sent"
    if response_status == "accepted" and payment_status == "paid" and paid_at:
        if start_dt and end_dt and start_dt <= current < end_dt:
            return "in_progress"
        if end_dt and end_dt <= current:
            return "completed"
        return "confirmed"
    if response_status == "accepted":
        return "awaiting_payment"
    if payment_status == "paid":
        if start_dt and end_dt and start_dt <= current < end_dt:
            return "in_progress"
        if end_dt and end_dt <= current:
            return "completed"
        return "upcoming"
    if status in {"approved"}:
        return "confirmed"
    if status in {"tbc"}:
        return "awaiting_acceptance"
    if start_dt and end_dt and start_dt <= current < end_dt:
        return "in_progress"
    if end_dt and end_dt <= current:
        return "past"
    return status


def get_display_status(booking, viewer_role: str = "parent") -> str:
    status = booking_state_from_booking(booking) if viewer_role != "admin" else canonical_booking_status(getattr(booking, "status", None))
    return status
