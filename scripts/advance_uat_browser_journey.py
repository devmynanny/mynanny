"""Advance an existing permanent-placement browser test through admin-only UAT gates.

This helper exists for controlled UAT journeys where the parent and nanny steps
are exercised in the website, but no reusable administrator password is stored
in the test environment. It refuses to run outside an explicitly named UAT
environment and UAT database.

It never calls Paystack. Candidate-access payments recorded here are clearly
labelled simulated UAT payments, matching the existing administrator test tool.
"""

from __future__ import annotations

import argparse
import os

from sqlalchemy import func

from app import models
from app.db import SessionLocal
from app.routers.placements import _activity, _notify_after_commit
from app.services.invoices import sync_invoice_for_payment
from app.services.permanent_placements import (
    apply_paid_payment,
    get_or_create_payment,
    pricing_payload,
)
from app.utils.database_target import assert_safe_database_target
from app.utils.time import utc_now


DEMO_NANNY_EMAILS = (
    "demo.nanny1@mynanny.test",
    "demo.nanny2@mynanny.test",
    "demo.nanny3@mynanny.test",
)


def refuse_unsafe_target() -> None:
    environment = os.getenv("APP_ENV", "").strip().lower()
    database_name = assert_safe_database_target().lower()
    if environment not in {"uat", "staging"} or "uat" not in database_name:
        raise SystemExit(
            "Refusing to change data outside an APP_ENV=uat/staging database whose name contains 'uat'"
        )


def placement_or_exit(db, placement_id: int):
    placement = (
        db.query(models.PermanentPlacement)
        .filter(models.PermanentPlacement.id == placement_id)
        .first()
    )
    if placement is None:
        raise SystemExit(f"Permanent placement #{placement_id} was not found")
    return placement


def activate_and_invite(db, placement_id: int) -> None:
    placement = placement_or_exit(db, placement_id)
    if placement.service_tier != "self_match":
        raise SystemExit("This UAT helper only supports the Self-Match journey")

    if placement.status == "brief_submitted":
        placement.status = "awaiting_candidate_access"
        placement.admin_notes = "UAT browser journey: family brief qualified"
        get_or_create_payment(db, placement, "candidate_access")
        _activity(
            db,
            placement.id,
            None,
            "brief_qualified",
            {"status": placement.status, "source": "uat_browser_journey"},
        )
        db.commit()
        _notify_after_commit(
            db,
            placement.parent_user_id,
            "permanent_brief_qualified",
            "Your permanent-placement brief is approved. Candidate access is ready for the controlled UAT journey.",
            placement.id,
        )

    if placement.status == "awaiting_candidate_access":
        payment = get_or_create_payment(db, placement, "candidate_access")
        if payment.status != "paid":
            apply_paid_payment(
                db,
                payment,
                note="Simulated UAT candidate-access payment — no Paystack charge",
            )
            invoice, invoice_created, receipt_created = sync_invoice_for_payment(db, payment)
            if invoice_created:
                invoice.invoice_email_requested_at = utc_now()
            if receipt_created:
                invoice.receipt_email_requested_at = utc_now()
            _activity(
                db,
                placement.id,
                None,
                "fee_marked_paid",
                {
                    "fee_type": "candidate_access",
                    "amount_cents": payment.amount_cents,
                    "reason": "controlled UAT browser journey",
                    "source": "uat_browser_journey",
                },
            )
            db.commit()
            if invoice_created:
                _notify_after_commit(
                    db,
                    placement.parent_user_id,
                    "permanent_invoice_issued",
                    f"Invoice {invoice.invoice_number or ''} is ready in your Permanent Placements account.",
                    invoice.id,
                )
            if receipt_created:
                _notify_after_commit(
                    db,
                    placement.parent_user_id,
                    "permanent_receipt_ready",
                    f"Receipt {invoice.receipt_number or ''} is ready in your Permanent Placements account.",
                    invoice.id,
                )

    db.refresh(placement)
    if placement.status not in {"search_active", "interviewing", "trial"}:
        raise SystemExit(
            f"Placement #{placement.id} is not ready for candidates: {placement.status}"
        )

    invited = 0
    existing = 0
    for email in DEMO_NANNY_EMAILS:
        nanny = (
            db.query(models.Nanny)
            .join(models.User, models.User.id == models.Nanny.user_id)
            .filter(func.lower(models.User.email) == email.lower())
            .first()
        )
        if nanny is None:
            raise SystemExit(f"Required synthetic UAT nanny is missing: {email}")
        preference = (
            db.query(models.PermanentPlacementPreference)
            .filter(
                models.PermanentPlacementPreference.nanny_id == nanny.id,
                models.PermanentPlacementPreference.opted_in.is_(True),
            )
            .first()
        )
        if not nanny.approved or nanny.is_suspended or preference is None:
            raise SystemExit(f"Synthetic UAT nanny is not qualified and opted in: {email}")
        candidate = (
            db.query(models.PermanentPlacementCandidate)
            .filter(
                models.PermanentPlacementCandidate.placement_id == placement.id,
                models.PermanentPlacementCandidate.nanny_id == nanny.id,
            )
            .first()
        )
        if candidate is not None:
            existing += 1
            continue
        candidate = models.PermanentPlacementCandidate(
            placement_id=placement.id,
            nanny_id=nanny.id,
            status="invited",
            consent_status="pending",
            admin_notes="Synthetic UAT candidate invited for browser testing",
        )
        db.add(candidate)
        db.flush()
        _activity(
            db,
            placement.id,
            None,
            "candidate_invited",
            {
                "candidate_id": candidate.id,
                "nanny_id": nanny.id,
                "source": "uat_browser_journey",
            },
        )
        db.commit()
        _notify_after_commit(
            db,
            nanny.user_id,
            "permanent_opportunity_invitation",
            f"A family in {placement.location_suburb} is interested in your permanent-placement profile. Review the opportunity and choose whether to share your profile.",
            candidate.id,
        )
        invited += 1

    print(
        f"Placement #{placement.id}: status={placement.status}; invited={invited}; already_present={existing}"
    )


def release_consented(db, placement_id: int) -> None:
    placement = placement_or_exit(db, placement_id)
    candidates = (
        db.query(models.PermanentPlacementCandidate)
        .filter(
            models.PermanentPlacementCandidate.placement_id == placement.id,
            models.PermanentPlacementCandidate.consent_status == "accepted",
        )
        .order_by(models.PermanentPlacementCandidate.id.asc())
        .all()
    )
    released_count = (
        db.query(func.count(models.PermanentPlacementCandidate.id))
        .filter(
            models.PermanentPlacementCandidate.placement_id == placement.id,
            models.PermanentPlacementCandidate.profile_released_at.isnot(None),
        )
        .scalar()
        or 0
    )
    profile_limit = int(pricing_payload(db, placement)["self_match"]["profile_limit"])
    changed = 0
    for candidate in candidates:
        if candidate.profile_released_at is not None:
            continue
        if released_count >= profile_limit:
            raise SystemExit(f"Self-Match profile limit of {profile_limit} would be exceeded")
        candidate.status = "released"
        candidate.profile_released_at = utc_now()
        candidate.introduction_expires_at = None
        _activity(
            db,
            placement.id,
            None,
            "candidate_profile_released",
            {"candidate_id": candidate.id, "source": "uat_browser_journey"},
        )
        db.commit()
        _notify_after_commit(
            db,
            placement.parent_user_id,
            "permanent_candidate_released",
            f"A new candidate profile is ready to review for permanent placement #{placement.id}.",
            placement.id,
        )
        changed += 1
        released_count += 1
    print(f"Placement #{placement.id}: newly_released={changed}; total_released={released_count}")


def print_summary(db, placement_id: int) -> None:
    placement = placement_or_exit(db, placement_id)
    candidates = (
        db.query(models.PermanentPlacementCandidate)
        .filter(models.PermanentPlacementCandidate.placement_id == placement.id)
        .order_by(models.PermanentPlacementCandidate.id.asc())
        .all()
    )
    print(f"Placement #{placement.id}: {placement.status}")
    for candidate in candidates:
        print(
            f"candidate={candidate.id} nanny={candidate.nanny_id} status={candidate.status} "
            f"consent={candidate.consent_status} released={candidate.profile_released_at is not None}"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action",
        choices=("activate-and-invite", "release-consented", "summary"),
    )
    parser.add_argument("--placement-id", type=int, required=True)
    args = parser.parse_args()

    refuse_unsafe_target()
    db = SessionLocal()
    try:
        if args.action == "activate-and-invite":
            activate_and_invite(db, args.placement_id)
        elif args.action == "release-consented":
            release_consented(db, args.placement_id)
        else:
            print_summary(db, args.placement_id)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
