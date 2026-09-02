from __future__ import annotations

import json
from datetime import timedelta
from typing import Any, Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from app import models
from app.utils.time import utc_now


def get_or_create_permanent_settings(db: Session) -> models.PermanentPlacementSettings:
    row = (
        db.query(models.PermanentPlacementSettings)
        .filter(models.PermanentPlacementSettings.id == 1)
        .first()
    )
    if row is None:
        row = models.PermanentPlacementSettings(id=1)
        db.add(row)
        db.flush()
    return row


def _settings_payload(row: models.PermanentPlacementSettings) -> dict[str, Any]:
    activation = int(row.self_match_activation_fee_cents)
    package_total = int(row.self_match_interview_package_fee_cents)
    package_top_up = package_total
    if row.activation_fee_credits_toward_package:
        package_top_up = max(0, package_total - activation)

    concierge_service = int(row.concierge_engagement_fee_cents) + int(
        row.concierge_success_balance_cents
    )
    return {
        "currency": row.currency,
        "self_match": {
            "activation_fee_cents": activation,
            "interview_package_fee_cents": package_total,
            "candidate_access_fee_cents": package_top_up,
            "success_fee_cents": int(row.self_match_placement_fee_cents),
            "total_if_placed_cents": package_total
            + int(row.self_match_placement_fee_cents),
            "profile_limit": int(row.self_match_profile_limit),
            "interview_limit": int(row.self_match_interview_limit),
            "candidate_access_days": int(row.candidate_access_days),
            "replacement_days": int(row.replacement_period_days),
            "replacement_credit_count": int(row.replacement_credit_count),
            "replacement_max_count": int(row.replacement_max_count),
            "activation_fee_credits_toward_package": bool(
                row.activation_fee_credits_toward_package
            ),
        },
        "concierge": {
            "consultation_fee_cents": int(row.concierge_consultation_fee_cents),
            "application_fee_cents": int(row.concierge_consultation_fee_cents),
            "engagement_fee_cents": int(row.concierge_engagement_fee_cents),
            "success_balance_cents": int(row.concierge_success_balance_cents),
            "success_fee_cents": concierge_service,
            "total_if_placed_cents": int(row.concierge_consultation_fee_cents)
            + concierge_service,
            "interview_limit": int(row.concierge_interview_limit),
            "replacement_days": int(row.replacement_period_days),
        },
        "rules": {
            "maybe_period_days": int(row.maybe_period_days),
        },
        "upgrade": {
            "candidate_access_credit_cents": package_total,
            "remaining_success_fee_cents": max(0, concierge_service - package_total),
        },
    }


def pricing_payload(
    db: Session,
    placement: Optional[models.PermanentPlacement] = None,
) -> dict[str, Any]:
    if placement is not None and placement.pricing_snapshot_json:
        try:
            value = json.loads(placement.pricing_snapshot_json)
            if isinstance(value, dict) and value.get("self_match") and value.get("concierge"):
                return value
        except (TypeError, ValueError):
            pass
    return _settings_payload(get_or_create_permanent_settings(db))


def snapshot_placement_pricing(
    db: Session,
    placement: models.PermanentPlacement,
) -> dict[str, Any]:
    snapshot = pricing_payload(db, placement)
    if not placement.pricing_snapshot_json:
        placement.pricing_snapshot_json = json.dumps(snapshot, separators=(",", ":"))
        db.add(placement)
    return snapshot


def placement_feature_enabled(db: Session) -> bool:
    row = db.query(models.AppSettings).filter(models.AppSettings.id == 1).first()
    return bool(getattr(row, "permanent_placements_enabled", False))


def interview_credit_summary(
    db: Session, placement: models.PermanentPlacement
) -> dict[str, int]:
    pricing = pricing_payload(db, placement)
    cycle = int(placement.interview_credit_cycle or 0)
    if cycle > 0:
        included = int(pricing["self_match"]["replacement_credit_count"])
    else:
        tier = "self_match" if placement.service_tier == "self_match" else "concierge"
        included = int(pricing[tier]["interview_limit"])
    net_change = (
        db.query(func.coalesce(func.sum(models.PermanentPlacementInterviewCreditEvent.delta), 0))
        .filter(
            models.PermanentPlacementInterviewCreditEvent.placement_id == placement.id,
            models.PermanentPlacementInterviewCreditEvent.cycle == cycle,
        )
        .scalar()
        or 0
    )
    available = max(0, included + int(net_change))
    return {
        "cycle": cycle,
        "included": included,
        "used": max(0, included - available),
        "available": available,
    }


def consume_interview_credit(
    db: Session,
    placement: models.PermanentPlacement,
    candidate: models.PermanentPlacementCandidate,
    *,
    actor_user_id: Optional[int],
) -> dict[str, int]:
    summary = interview_credit_summary(db, placement)
    if summary["available"] <= 0:
        raise ValueError("All included interview credits have already been accepted")
    now = utc_now()
    candidate.interview_credit_cycle = summary["cycle"]
    candidate.interview_credit_consumed_at = now
    candidate.interview_credit_restored_at = None
    db.add(
        models.PermanentPlacementInterviewCreditEvent(
            placement_id=placement.id,
            candidate_id=candidate.id,
            cycle=summary["cycle"],
            delta=-1,
            event_type="interview_accepted",
            actor_user_id=actor_user_id,
        )
    )
    db.flush()
    return interview_credit_summary(db, placement)


def restore_interview_credit(
    db: Session,
    placement: models.PermanentPlacement,
    candidate: models.PermanentPlacementCandidate,
    *,
    actor_user_id: Optional[int],
    event_type: str,
    reason: str,
) -> dict[str, int]:
    if candidate.interview_credit_consumed_at is None:
        raise ValueError("This interview did not consume a credit")
    if candidate.interview_credit_restored_at is not None:
        return interview_credit_summary(db, placement)
    cycle = int(candidate.interview_credit_cycle or 0)
    candidate.interview_credit_restored_at = utc_now()
    db.add(
        models.PermanentPlacementInterviewCreditEvent(
            placement_id=placement.id,
            candidate_id=candidate.id,
            cycle=cycle,
            delta=1,
            event_type=event_type,
            actor_user_id=actor_user_id,
            reason=reason,
        )
    )
    db.flush()
    return interview_credit_summary(db, placement)


def paid_fee(
    db: Session, placement_id: int, fee_type: str
) -> Optional[models.PermanentPlacementPayment]:
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


def fee_amount_cents(
    db: Session, placement: models.PermanentPlacement, fee_type: str
) -> int:
    pricing = snapshot_placement_pricing(db, placement)
    if fee_type == "activation" and placement.service_tier == "self_match":
        return int(pricing["self_match"]["activation_fee_cents"])
    if fee_type == "candidate_access" and placement.service_tier == "self_match":
        return int(pricing["self_match"]["candidate_access_fee_cents"])
    if fee_type == "application" and placement.service_tier == "concierge":
        return int(pricing["concierge"]["consultation_fee_cents"])
    if fee_type == "engagement" and placement.service_tier == "concierge":
        engagement = int(pricing["concierge"]["engagement_fee_cents"])
        if placement.upgraded_from_self_match and paid_fee(
            db, placement.id, "candidate_access"
        ):
            engagement -= int(pricing["upgrade"]["candidate_access_credit_cents"])
        return max(0, engagement)
    if fee_type == "success":
        if placement.service_tier == "self_match":
            return int(pricing["self_match"]["success_fee_cents"])
        success_balance = int(pricing["concierge"]["success_balance_cents"])
        if placement.upgraded_from_self_match and paid_fee(
            db, placement.id, "candidate_access"
        ):
            unused_credit = max(
                0,
                int(pricing["upgrade"]["candidate_access_credit_cents"])
                - int(pricing["concierge"]["engagement_fee_cents"]),
            )
            return max(0, success_balance - unused_credit)
        return success_balance
    raise ValueError("This fee is not available for the selected placement service")


def get_or_create_payment(
    db: Session,
    placement: models.PermanentPlacement,
    fee_type: str,
) -> models.PermanentPlacementPayment:
    payment = (
        db.query(models.PermanentPlacementPayment)
        .filter(
            models.PermanentPlacementPayment.placement_id == placement.id,
            models.PermanentPlacementPayment.fee_type == fee_type,
        )
        .first()
    )
    if payment is None:
        amount_cents = fee_amount_cents(db, placement, fee_type)
        payment = models.PermanentPlacementPayment(
            placement_id=placement.id,
            fee_type=fee_type,
            amount_cents=amount_cents,
            status="pending",
        )
        db.add(payment)
        db.flush()
        if amount_cents == 0:
            apply_paid_payment(
                db,
                payment,
                note="Automatically recorded as a configured R0 fee",
            )
        from app.services.invoices import get_or_create_invoice_for_payment

        get_or_create_invoice_for_payment(db, payment)
    # Never reprice an existing payment: it is the auditable amount the client saw.
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
    pricing = snapshot_placement_pricing(db, placement)

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
            days=int(pricing["self_match"]["candidate_access_days"])
        )
    elif payment.fee_type == "engagement":
        placement.status = "search_active"
    elif payment.fee_type == "success":
        placement.status = "placed"
        tier_pricing = pricing[
            "self_match" if placement.service_tier == "self_match" else "concierge"
        ]
        placement.guarantee_until = utc_now() + timedelta(
            days=int(tier_pricing["replacement_days"])
        )

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
