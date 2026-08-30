from __future__ import annotations

from datetime import timedelta
from typing import Any, Optional

from sqlalchemy.orm import Session

from app import models
from app.utils.time import utc_now


SELF_MATCH_ACTIVATION_CENTS = 35_000
SELF_MATCH_ACCESS_CENTS = 150_000
SELF_MATCH_SUCCESS_CENTS = 150_000
CONCIERGE_APPLICATION_CENTS = 50_000
CONCIERGE_SUCCESS_CENTS = 500_000
SELF_MATCH_PROFILE_LIMIT = 10
SELF_MATCH_INTERVIEW_LIMIT = 3
CONCIERGE_INTERVIEW_LIMIT = 5
CANDIDATE_ACCESS_DAYS = 30
SELF_MATCH_REMATCH_DAYS = 30
CONCIERGE_REPLACEMENT_DAYS = 90
INTRODUCTION_PROTECTION_DAYS = 365


def pricing_payload() -> dict[str, Any]:
    return {
        "self_match": {
            "activation_fee_cents": SELF_MATCH_ACTIVATION_CENTS,
            "candidate_access_fee_cents": SELF_MATCH_ACCESS_CENTS,
            "success_fee_cents": SELF_MATCH_SUCCESS_CENTS,
            "total_if_placed_cents": (
                SELF_MATCH_ACTIVATION_CENTS
                + SELF_MATCH_ACCESS_CENTS
                + SELF_MATCH_SUCCESS_CENTS
            ),
            "profile_limit": SELF_MATCH_PROFILE_LIMIT,
            "interview_limit": SELF_MATCH_INTERVIEW_LIMIT,
            "candidate_access_days": CANDIDATE_ACCESS_DAYS,
            "rematch_days": SELF_MATCH_REMATCH_DAYS,
        },
        "concierge": {
            "application_fee_cents": CONCIERGE_APPLICATION_CENTS,
            "success_fee_cents": CONCIERGE_SUCCESS_CENTS,
            "total_if_placed_cents": (
                CONCIERGE_APPLICATION_CENTS + CONCIERGE_SUCCESS_CENTS
            ),
            "interview_limit": CONCIERGE_INTERVIEW_LIMIT,
            "replacement_days": CONCIERGE_REPLACEMENT_DAYS,
        },
        "upgrade": {
            "candidate_access_credit_cents": SELF_MATCH_ACCESS_CENTS,
            "remaining_success_fee_cents": (
                CONCIERGE_SUCCESS_CENTS - SELF_MATCH_ACCESS_CENTS
            ),
        },
    }


def placement_feature_enabled(db: Session) -> bool:
    row = db.query(models.AppSettings).filter(models.AppSettings.id == 1).first()
    return bool(getattr(row, "permanent_placements_enabled", False))


def paid_fee(db: Session, placement_id: int, fee_type: str) -> Optional[models.PermanentPlacementPayment]:
    return (
        db.query(models.PermanentPlacementPayment)
        .filter(
            models.PermanentPlacementPayment.placement_id == placement_id,
            models.PermanentPlacementPayment.fee_type == fee_type,
            models.PermanentPlacementPayment.status == "paid",
        )
        .first()
    )


def initial_fee_type(placement: models.PermanentPlacement) -> str:
    return "activation" if placement.service_tier == "self_match" else "application"


def fee_amount_cents(db: Session, placement: models.PermanentPlacement, fee_type: str) -> int:
    if fee_type == "activation" and placement.service_tier == "self_match":
        return SELF_MATCH_ACTIVATION_CENTS
    if fee_type == "candidate_access" and placement.service_tier == "self_match":
        return SELF_MATCH_ACCESS_CENTS
    if fee_type == "application" and placement.service_tier == "concierge":
        return CONCIERGE_APPLICATION_CENTS
    if fee_type == "success":
        if placement.service_tier == "self_match":
            return SELF_MATCH_SUCCESS_CENTS
        if placement.upgraded_from_self_match and paid_fee(db, placement.id, "candidate_access"):
            return CONCIERGE_SUCCESS_CENTS - SELF_MATCH_ACCESS_CENTS
        return CONCIERGE_SUCCESS_CENTS
    raise ValueError("This fee is not available for the selected placement service")


def get_or_create_payment(
    db: Session,
    placement: models.PermanentPlacement,
    fee_type: str,
) -> models.PermanentPlacementPayment:
    amount = fee_amount_cents(db, placement, fee_type)
    payment = (
        db.query(models.PermanentPlacementPayment)
        .filter(
            models.PermanentPlacementPayment.placement_id == placement.id,
            models.PermanentPlacementPayment.fee_type == fee_type,
        )
        .first()
    )
    if payment is None:
        payment = models.PermanentPlacementPayment(
            placement_id=placement.id,
            fee_type=fee_type,
            amount_cents=amount,
            status="pending",
        )
        db.add(payment)
        db.flush()
    elif payment.status != "paid":
        payment.amount_cents = amount
    return payment


def apply_paid_payment(
    db: Session,
    payment: models.PermanentPlacementPayment,
    *,
    transaction_id: Optional[str] = None,
    note: Optional[str] = None,
) -> models.PermanentPlacement:
    placement = (
        db.query(models.PermanentPlacement)
        .filter(models.PermanentPlacement.id == payment.placement_id)
        .first()
    )
    if placement is None:
        raise ValueError("Permanent placement not found")

    payment.status = "paid"
    payment.paid_at = payment.paid_at or utc_now()
    payment.payment_note = note or payment.payment_note
    if transaction_id:
        payment.paystack_transaction_id = str(transaction_id)

    if payment.fee_type in {"activation", "application"}:
        if placement.status == "awaiting_initial_payment":
            placement.status = "brief_submitted"
    elif payment.fee_type == "candidate_access":
        placement.status = "search_active"
        placement.candidate_access_expires_at = utc_now() + timedelta(
            days=CANDIDATE_ACCESS_DAYS
        )
    elif payment.fee_type == "success":
        placement.status = "placed"
        guarantee_days = (
            SELF_MATCH_REMATCH_DAYS
            if placement.service_tier == "self_match"
            else CONCIERGE_REPLACEMENT_DAYS
        )
        placement.guarantee_until = utc_now() + timedelta(days=guarantee_days)

    db.add(payment)
    db.add(placement)
    return placement


def record_paystack_success(
    db: Session,
    *,
    reference: str,
    transaction_id: Optional[str] = None,
) -> Optional[models.PermanentPlacementPayment]:
    payment = (
        db.query(models.PermanentPlacementPayment)
        .filter(models.PermanentPlacementPayment.paystack_reference == reference)
        .first()
    )
    if payment is None:
        return None
    apply_paid_payment(db, payment, transaction_id=transaction_id)
    db.commit()
    return payment
