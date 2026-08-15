from __future__ import annotations

import re


# Fixed, privacy-safe bodies improve WhatsApp approval reliability and avoid
# exposing family, location, rate, or identity details on a lock screen.
WHATSAPP_UTILITY_TEMPLATES: dict[str, dict[str, str]] = {
    "new_booking_request": {
        "name": "my_nanny_new_booking_request",
        "body": "You have a new My Nanny booking request. Open the app to review the dates, location and earnings.",
    },
    "broadcast_position_filled": {
        "name": "my_nanny_booking_progress",
        "body": "A nanny position for your My Nanny booking has been filled. The request remains open for any remaining positions. Open the app for details.",
    },
    "broadcast_filled": {
        "name": "my_nanny_booking_filled",
        "body": "All required nanny positions for your My Nanny booking are filled. Open the app to review the confirmed booking.",
    },
    "broadcast_closed_nanny": {
        "name": "my_nanny_broadcast_closed",
        "body": "A My Nanny booking request has closed because all required positions were filled. Open the app to view your requests.",
    },
    "booking_confirmed": {
        "name": "my_nanny_booking_confirmed",
        "body": "Your My Nanny booking is confirmed. Open the app to review the booking details.",
    },
    "nanny_accepted": {
        "name": "my_nanny_nanny_accepted",
        "body": "A nanny accepted your My Nanny booking request. Open the app for the latest booking status.",
    },
    "nanny_checked_in": {
        "name": "my_nanny_nanny_checked_in",
        "body": "Your nanny checked in for an active booking. Open My Nanny to review the service status.",
    },
    "booking_start_reminder": {
        "name": "my_nanny_booking_start_reminder",
        "body": "Your My Nanny booking starts in about one hour. Open the app to review the location and check-in instructions.",
    },
    "check_in_confirmation_required": {
        "name": "my_nanny_check_in_confirmation",
        "body": "Your nanny has checked in. Open My Nanny to confirm the arrival time.",
    },
    "check_out_confirmation_required": {
        "name": "my_nanny_check_out_confirmation",
        "body": "Your nanny has checked out. Open My Nanny to confirm the service times.",
    },
    "checkout_reminder": {
        "name": "my_nanny_checkout_reminder",
        "body": "Your booking has reached its scheduled finish time. Open My Nanny and check out when care has ended.",
    },
    "missed_check_in": {
        "name": "my_nanny_missed_check_in",
        "body": "You have not checked in for an active booking. Open My Nanny now or contact operations if you cannot attend.",
    },
    "nanny_late_alert": {
        "name": "my_nanny_late_alert",
        "body": "Your nanny has not checked in for an active booking. My Nanny operations has been alerted. Open the app for details.",
    },
    "overtime_request": {
        "name": "my_nanny_overtime_confirmation",
        "body": "Additional booking time requires your confirmation. Open My Nanny to approve or query it.",
    },
    "service_fee_adjusted": {
        "name": "my_nanny_earnings_adjusted",
        "body": "Your booking earnings were adjusted using the confirmed service time. Open My Nanny for details.",
    },
    "service_refund_requested": {
        "name": "my_nanny_refund_update",
        "body": "A booking adjustment and refund request have been recorded. Open My Nanny for details.",
    },
    "service_time_corrected": {
        "name": "my_nanny_service_time_corrected",
        "body": "A booking service time was corrected. Open My Nanny to review the update.",
    },
    "service_time_disputed": {
        "name": "my_nanny_service_time_disputed",
        "body": "A booking service time has been queried and sent to operations. Open My Nanny for details.",
    },
    "payment_success": {
        "name": "my_nanny_payment_success",
        "body": "Payment for your My Nanny booking was successful. Open the app for the receipt and booking details.",
    },
    "payment_failed": {
        "name": "my_nanny_payment_failed",
        "body": "Payment for your My Nanny booking was unsuccessful. Open the app to update payment or try again.",
    },
    "payment_pending": {
        "name": "my_nanny_payment_pending",
        "body": "Payment for your My Nanny booking is still being processed. Open the app for the latest status.",
    },
    "payment_due": {
        "name": "my_nanny_payment_due",
        "body": "Payment is required to confirm your My Nanny booking. Open the app to continue securely with Paystack.",
    },
    "payout_pending": {
        "name": "my_nanny_payout_pending",
        "body": "Your My Nanny payout is pending a booking confirmation. Open the app for details.",
    },
    "payout_sent": {
        "name": "my_nanny_payout_sent",
        "body": "Your My Nanny payout has been sent. Open the app to review the payment details.",
    },
    "booking_cancelled": {
        "name": "my_nanny_booking_cancelled_parent",
        "body": "Your My Nanny booking was cancelled. Open the app for the cancellation and refund status.",
    },
    "booking_cancelled_nanny": {
        "name": "my_nanny_booking_cancelled_nanny",
        "body": "A confirmed My Nanny booking was cancelled. Open the app for details.",
    },
    "nanny_declined": {
        "name": "my_nanny_request_declined",
        "body": "A nanny declined your booking request. The request remains available to other eligible nannies. Open the app for details.",
    },
    "no_nanny_yet": {
        "name": "my_nanny_request_still_open",
        "body": "Your My Nanny booking request is still open and no nanny has accepted yet. Open the app for options.",
    },
    "request_expired": {
        "name": "my_nanny_request_expired",
        "body": "A My Nanny booking request expired before it was accepted. Open the app to review or create another request.",
    },
    "deciding_reminder": {
        "name": "my_nanny_request_decision_reminder",
        "body": "A My Nanny booking request is waiting for your response. Open the app to accept or decline it.",
    },
    "refund_processed": {
        "name": "my_nanny_refund_processed",
        "body": "Your My Nanny refund has been processed. Open the app for details.",
    },
    "review_request": {
        "name": "my_nanny_review_request",
        "body": "Your booking is complete. Open My Nanny to share a review of your experience.",
    },
    "nanny_approved": {
        "name": "my_nanny_profile_approved",
        "body": "Your My Nanny profile has been approved. Open the app to view your profile and opportunities.",
    },
    "nanny_reactivated": {
        "name": "my_nanny_profile_reactivated",
        "body": "Your My Nanny profile has been reactivated. Open the app for details.",
    },
    "passport_expiry_warning": {
        "name": "my_nanny_passport_expiry_warning",
        "body": "Your passport on My Nanny will expire within three months. Open the app to upload a renewed passport before your profile is suspended.",
    },
    "passport_expired_suspension": {
        "name": "my_nanny_passport_suspension",
        "body": "Your My Nanny profile was suspended because the passport on file expired. Open the app to upload a valid passport.",
    },
    "passport_renewal_approved": {
        "name": "my_nanny_passport_approved",
        "body": "Your renewed passport was approved by My Nanny. Open the app to view your profile status.",
    },
}


def content_sid_env_key(event_type: str) -> str:
    normalized = re.sub(r"[^A-Z0-9]+", "_", event_type.upper()).strip("_")
    return f"TWILIO_CONTENT_SID_{normalized}"
