"""
Characterization tests for app.services.booking_status.

These lock in the CURRENT read-side status derivation behavior before any
write-path normalization work touches app/routers/public.py. If a change to
booking_status.py breaks one of these, that is a real behavior change and
needs a conscious decision, not an accident.
"""

from datetime import datetime, timedelta
from types import SimpleNamespace

from app.services.booking_status import (
    CANONICAL_BOOKING_STATUSES,
    LEGACY_STATUS_MAP,
    booking_state_from_booking,
    booking_state_from_request,
    canonical_booking_status,
    get_display_status,
)


# ---------------------------------------------------------------------------
# canonical_booking_status
# ---------------------------------------------------------------------------

def test_canonical_status_none_defaults_to_draft():
    assert canonical_booking_status(None) == "draft"
    assert canonical_booking_status("") == "draft"


def test_canonical_status_normalizes_case_and_whitespace():
    assert canonical_booking_status("  Confirmed  ") == "confirmed"


def test_canonical_status_maps_legacy_values():
    for legacy, expected in LEGACY_STATUS_MAP.items():
        assert canonical_booking_status(legacy) == expected


def test_canonical_status_passes_through_unknown_values():
    assert canonical_booking_status("some_new_status") == "some_new_status"


# ---------------------------------------------------------------------------
# booking_state_from_booking (bookings table)
# ---------------------------------------------------------------------------

def _booking(**overrides):
    base = dict(
        status="confirmed",
        check_in_at=None,
        check_out_at=None,
        starts_at=None,
        start_dt=None,
        ends_at=None,
        end_dt=None,
        overrun_status=None,
        payout_released_at=None,
        payment_status=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_booking_cancelled_status_wins_over_everything():
    b = _booking(status="cancelled", check_in_at=datetime.utcnow())
    assert booking_state_from_booking(b) == "cancelled"


def test_booking_rejected_status_maps_to_cancelled():
    b = _booking(status="rejected")
    assert booking_state_from_booking(b) == "cancelled"


def test_booking_overrun_awaiting_parent_takes_priority():
    b = _booking(overrun_status="awaiting_parent")
    assert booking_state_from_booking(b) == "awaiting_overtime_approval"


def test_booking_overrun_queried_maps_to_admin_review():
    b = _booking(overrun_status="queried")
    assert booking_state_from_booking(b) == "admin_review"


def test_booking_overrun_charged_without_payout_release_is_completed():
    b = _booking(
        overrun_status="charged",
        check_out_at=datetime.utcnow(),
        payout_released_at=None,
    )
    assert booking_state_from_booking(b) == "completed"


def test_booking_checked_out_is_completed():
    b = _booking(check_out_at=datetime.utcnow())
    assert booking_state_from_booking(b) == "completed"


def test_booking_checked_in_not_out_is_in_progress():
    b = _booking(check_in_at=datetime.utcnow(), check_out_at=None)
    assert booking_state_from_booking(b) == "in_progress"


def test_booking_payment_failed():
    b = _booking(payment_status="failed")
    assert booking_state_from_booking(b) == "payment_failed"


def test_booking_pending_payment():
    b = _booking(payment_status="pending_payment")
    assert booking_state_from_booking(b) == "awaiting_payment"


def test_booking_in_time_window_is_in_progress_by_time_alone():
    now = datetime.utcnow()
    b = _booking(
        status="upcoming",
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(hours=1),
    )
    assert booking_state_from_booking(b) == "in_progress"


def test_booking_past_end_time_without_checkout_is_past():
    now = datetime.utcnow()
    b = _booking(
        status="upcoming",
        starts_at=now - timedelta(hours=5),
        ends_at=now - timedelta(hours=1),
    )
    assert booking_state_from_booking(b) == "past"


def test_booking_confirmed_and_accepted_map_to_confirmed():
    assert booking_state_from_booking(_booking(status="confirmed")) == "confirmed"
    assert booking_state_from_booking(_booking(status="accepted")) == "confirmed"


def test_booking_pending_awaiting_broadcast_map_to_awaiting_acceptance():
    for status in ("pending", "awaiting_acceptance", "broadcast_sent"):
        assert booking_state_from_booking(_booking(status=status)) == "awaiting_acceptance"


def test_booking_approved_maps_to_confirmed_via_legacy_map():
    # NOTE: "approved" is legacy-mapped to "confirmed" by canonical_booking_status
    # BEFORE booking_state_from_booking's own "approved -> upcoming" branch can
    # fire; that branch is unreachable for "approved". Locked in as current behavior.
    assert booking_state_from_booking(_booking(status="approved")) == "confirmed"
    assert booking_state_from_booking(_booking(status="upcoming")) == "upcoming"


def test_booking_unknown_status_falls_through_unchanged():
    b = _booking(status="some_new_status")
    assert booking_state_from_booking(b) == "some_new_status"


# ---------------------------------------------------------------------------
# booking_state_from_request (booking_requests table)
# ---------------------------------------------------------------------------

def _request(**overrides):
    base = dict(
        status="tbc",
        payment_status=None,
        nanny_response_status=None,
        requested_starts_at=None,
        start_dt=None,
        requested_ends_at=None,
        end_dt=None,
        paid_at=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_request_cancelled_and_rejected_map_to_cancelled():
    assert booking_state_from_request(_request(status="cancelled")) == "cancelled"
    assert booking_state_from_request(_request(status="rejected")) == "cancelled"


def test_request_payment_failed_overrides_status():
    r = _request(status="approved", payment_status="failed")
    assert booking_state_from_request(r) == "payment_failed"


def test_request_pending_admin_maps_to_broadcast_sent():
    assert booking_state_from_request(_request(status="pending_admin")) == "broadcast_sent"


def test_request_accepted_paid_and_within_window_is_in_progress():
    now = datetime.utcnow()
    r = _request(
        status="approved",
        nanny_response_status="accepted",
        payment_status="paid",
        paid_at=now - timedelta(hours=1),
        requested_starts_at=now - timedelta(minutes=30),
        requested_ends_at=now + timedelta(hours=1),
    )
    assert booking_state_from_request(r) == "in_progress"


def test_request_accepted_paid_but_before_start_is_confirmed():
    now = datetime.utcnow()
    r = _request(
        status="approved",
        nanny_response_status="accepted",
        payment_status="paid",
        paid_at=now,
        requested_starts_at=now + timedelta(hours=2),
        requested_ends_at=now + timedelta(hours=4),
    )
    assert booking_state_from_request(r) == "confirmed"


def test_request_accepted_paid_and_past_end_is_completed():
    now = datetime.utcnow()
    r = _request(
        status="approved",
        nanny_response_status="accepted",
        payment_status="paid",
        paid_at=now - timedelta(hours=5),
        requested_starts_at=now - timedelta(hours=4),
        requested_ends_at=now - timedelta(hours=1),
    )
    assert booking_state_from_request(r) == "completed"


def test_request_accepted_but_not_yet_paid_is_awaiting_payment():
    r = _request(status="approved", nanny_response_status="accepted", payment_status=None)
    assert booking_state_from_request(r) == "awaiting_payment"


def test_request_paid_without_acceptance_flag_still_resolves_by_time():
    now = datetime.utcnow()
    r = _request(
        status="approved",
        payment_status="paid",
        requested_starts_at=now + timedelta(hours=1),
        requested_ends_at=now + timedelta(hours=2),
    )
    assert booking_state_from_request(r) == "upcoming"


def test_request_approved_with_no_payment_or_time_data_is_confirmed():
    r = _request(status="approved")
    assert booking_state_from_request(r) == "confirmed"


def test_request_tbc_is_awaiting_acceptance():
    r = _request(status="tbc")
    assert booking_state_from_request(r) == "awaiting_acceptance"


def test_request_unknown_status_falls_back_to_time_window():
    now = datetime.utcnow()
    r = _request(
        status="some_new_status",
        requested_starts_at=now - timedelta(hours=5),
        requested_ends_at=now - timedelta(hours=1),
    )
    assert booking_state_from_request(r) == "past"


# ---------------------------------------------------------------------------
# get_display_status
# ---------------------------------------------------------------------------

def test_get_display_status_admin_sees_raw_canonical_status_not_derived_state():
    b = _booking(status="confirmed", check_in_at=datetime.utcnow())
    # Non-admin viewers get the fully derived state (in_progress, since checked in).
    assert get_display_status(b, viewer_role="parent") == "in_progress"
    # Admin viewer intentionally sees the raw canonical status, not the derived one.
    assert get_display_status(b, viewer_role="admin") == "confirmed"


def test_all_legacy_map_targets_are_in_canonical_list():
    for target in LEGACY_STATUS_MAP.values():
        assert target in CANONICAL_BOOKING_STATUSES
