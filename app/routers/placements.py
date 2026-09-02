from __future__ import annotations

import json
import os
import uuid
from datetime import date, datetime, time as dt_time, timedelta, timezone
from typing import Literal, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.db import SessionLocal
from app.routers.public import _require_user, require_admin
from app.services.audit import log_audit
from app.services.notifications import notify
from app.services.paystack import initialize_transaction, verify_transaction
from app.services.invoices import (
    billing_settings_payload,
    get_or_create_billing_settings,
    invoice_payload,
    sync_invoice_for_payment,
)
from app.services.permanent_placements import (
    apply_paid_payment,
    consume_interview_credit,
    get_or_create_permanent_settings,
    get_or_create_payment,
    initial_fee_type,
    interview_credit_summary,
    paid_fee,
    placement_feature_enabled,
    pricing_payload,
    restore_interview_credit,
    snapshot_placement_pricing,
)
from app.utils.time import utc_now


router = APIRouter(tags=["permanent placements"])


def _document_ready_message(document_label: str, number: str | None) -> str:
    portal_url = f"{(os.getenv('V2_BASE_URL') or 'http://localhost:3000').rstrip('/')}/placements"
    return (
        f"{document_label} {number or ''} is ready in your Permanent Placements account.\n\n"
        f"Open it securely: {portal_url}"
    )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class PlacementBriefPayload(BaseModel):
    service_tier: Literal["self_match", "concierge"]
    role_title: str = Field(min_length=2, max_length=160)
    employment_type: Literal["full_time", "part_time", "live_in", "live_out"] = "full_time"
    start_date: Optional[date] = None
    schedule_summary: str = Field(min_length=5, max_length=2000)
    hours_per_week: Optional[int] = Field(default=None, ge=1, le=168)
    children_count: int = Field(default=1, ge=1, le=12)
    children_ages: list[str] = Field(default_factory=list, max_length=12)
    duties: str = Field(min_length=5, max_length=4000)
    special_requirements: Optional[str] = Field(default=None, max_length=4000)
    salary_min_cents: int = Field(ge=1)
    salary_max_cents: int = Field(ge=1)
    location_suburb: str = Field(min_length=2, max_length=120)
    location_city: str = Field(min_length=2, max_length=120)
    location_province: Optional[str] = Field(default=None, max_length=120)
    live_in: bool = False
    drivers_license_required: bool = False
    own_car_required: bool = False
    languages: list[str] = Field(default_factory=list, max_length=20)
    pets: Optional[str] = Field(default=None, max_length=1000)
    parent_notes: Optional[str] = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def validate_salary(self):
        if self.salary_max_cents < self.salary_min_cents:
            raise ValueError("Maximum salary must be at least the minimum salary")
        return self


class PlacementBriefUpdatePayload(BaseModel):
    role_title: Optional[str] = Field(default=None, min_length=2, max_length=160)
    employment_type: Optional[Literal["full_time", "part_time", "live_in", "live_out"]] = None
    start_date: Optional[date] = None
    schedule_summary: Optional[str] = Field(default=None, min_length=5, max_length=2000)
    hours_per_week: Optional[int] = Field(default=None, ge=1, le=168)
    children_count: Optional[int] = Field(default=None, ge=1, le=12)
    children_ages: Optional[list[str]] = Field(default=None, max_length=12)
    duties: Optional[str] = Field(default=None, min_length=5, max_length=4000)
    special_requirements: Optional[str] = Field(default=None, max_length=4000)
    salary_min_cents: Optional[int] = Field(default=None, ge=1)
    salary_max_cents: Optional[int] = Field(default=None, ge=1)
    location_suburb: Optional[str] = Field(default=None, min_length=2, max_length=120)
    location_city: Optional[str] = Field(default=None, min_length=2, max_length=120)
    location_province: Optional[str] = Field(default=None, max_length=120)
    live_in: Optional[bool] = None
    drivers_license_required: Optional[bool] = None
    own_car_required: Optional[bool] = None
    languages: Optional[list[str]] = Field(default=None, max_length=20)
    pets: Optional[str] = Field(default=None, max_length=1000)
    parent_notes: Optional[str] = Field(default=None, max_length=4000)


class PaymentInitializePayload(BaseModel):
    callback_url: Optional[str] = None


class PaymentVerifyPayload(BaseModel):
    reference: str = Field(min_length=5, max_length=200)


class NannyPreferencePayload(BaseModel):
    opted_in: bool
    desired_salary_min_cents: Optional[int] = Field(default=None, ge=1)
    desired_salary_max_cents: Optional[int] = Field(default=None, ge=1)
    employment_types: list[Literal["full_time", "part_time", "live_in", "live_out"]] = Field(default_factory=list)
    preferred_locations: Optional[str] = Field(default=None, max_length=2000)
    available_from: Optional[date] = None
    live_in_preference: Optional[Literal["yes", "no", "either"]] = None
    profile_notes: Optional[str] = Field(default=None, max_length=3000)

    @model_validator(mode="after")
    def validate_salary(self):
        if (
            self.desired_salary_min_cents is not None
            and self.desired_salary_max_cents is not None
            and self.desired_salary_max_cents < self.desired_salary_min_cents
        ):
            raise ValueError("Maximum salary must be at least the minimum salary")
        if self.opted_in and not self.employment_types:
            raise ValueError("Choose at least one permanent employment type")
        return self


class CandidateResponsePayload(BaseModel):
    decision: Literal["accepted", "declined"]
    note: Optional[str] = Field(default=None, max_length=2000)


class InterviewResponsePayload(BaseModel):
    decision: Literal["accepted", "declined", "cancelled"]
    note: Optional[str] = Field(default=None, max_length=2000)


class InterviewProgressPayload(BaseModel):
    action: Literal["check_in", "completed"]


class ParentInterviewDecisionPayload(BaseModel):
    decision: Literal["reject", "maybe", "trial", "offer", "admin_support"]
    feedback: str = Field(min_length=3, max_length=4000)


class TrialRequestPayload(BaseModel):
    starts_at: datetime
    ends_at: datetime
    note: Optional[str] = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_window(self):
        if (self.starts_at.tzinfo is None) != (self.ends_at.tzinfo is None):
            raise ValueError("Trial start and end times must use the same timezone format")
        if self.ends_at <= self.starts_at:
            raise ValueError("Trial end time must be after its start time")
        return self


class TrialResponsePayload(BaseModel):
    decision: Literal["accepted", "declined", "change_requested"]
    alternative_at: Optional[datetime] = None
    note: Optional[str] = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_alternative(self):
        if self.decision == "change_requested" and self.alternative_at is None:
            raise ValueError("Suggest a different date and time")
        return self


class OfferPayload(BaseModel):
    salary_cents: int = Field(ge=1)
    start_date: date
    working_days: list[int] = Field(min_length=1, max_length=7)
    start_time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    end_time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    terms: str = Field(min_length=5, max_length=4000)

    @model_validator(mode="after")
    def validate_schedule(self):
        if any(day < 0 or day > 6 for day in self.working_days):
            raise ValueError("Working days must use Monday 0 through Sunday 6")
        if len(set(self.working_days)) != len(self.working_days):
            raise ValueError("Working days cannot contain duplicates")
        if dt_time.fromisoformat(self.end_time) <= dt_time.fromisoformat(self.start_time):
            raise ValueError("Offer end time must be after its start time")
        return self


class OfferResponsePayload(BaseModel):
    decision: Literal["accepted", "declined", "admin_support"]
    note: Optional[str] = Field(default=None, max_length=2000)


class ContactTermsPayload(BaseModel):
    accepted: bool


class PermanentMessagePayload(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class BillingSettingsPayload(BaseModel):
    issuer_legal_name: Optional[str] = Field(default=None, max_length=200)
    issuer_trading_name: Optional[str] = Field(default=None, max_length=200)
    issuer_email: Optional[str] = Field(default=None, max_length=254)
    issuer_phone: Optional[str] = Field(default=None, max_length=80)
    issuer_address: Optional[str] = Field(default=None, max_length=2000)
    issuer_registration_number: Optional[str] = Field(default=None, max_length=100)
    issuer_vat_number: Optional[str] = Field(default=None, max_length=100)
    vat_registered: Optional[bool] = None
    vat_rate_bps: Optional[int] = Field(default=None, ge=0, le=10_000)
    prices_include_vat: Optional[bool] = None
    tax_status_confirmed: Optional[bool] = None
    invoice_prefix: Optional[str] = Field(default=None, min_length=1, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")


class InvoiceIssuePayload(BaseModel):
    send_email: bool = True


class CandidateNotePayload(BaseModel):
    note: Optional[str] = Field(default=None, max_length=2000)


class InterviewSchedulePayload(BaseModel):
    scheduled_at: datetime
    interview_format: Literal["video", "in_person", "telephone"]
    interview_location: Optional[str] = Field(default=None, max_length=1000)
    note: Optional[str] = Field(default=None, max_length=2000)


class AdminInterviewOutcomePayload(BaseModel):
    outcome: Literal["cancelled_by_nanny", "not_held"]
    reason: str = Field(min_length=3, max_length=2000)


class CandidateStagePayload(BaseModel):
    status: Literal["released", "shortlisted", "interview_requested", "interviewed", "trial", "offered", "declined", "withdrawn"]
    trial_scheduled_at: Optional[datetime] = None
    note: Optional[str] = Field(default=None, max_length=2000)


class AdminPlacementSettingsPayload(BaseModel):
    enabled: Optional[bool] = None
    self_match_activation_fee_cents: Optional[int] = Field(default=None, ge=0)
    self_match_interview_package_fee_cents: Optional[int] = Field(default=None, ge=0)
    self_match_placement_fee_cents: Optional[int] = Field(default=None, ge=0)
    activation_fee_credits_toward_package: Optional[bool] = None
    concierge_consultation_fee_cents: Optional[int] = Field(default=None, ge=0)
    concierge_engagement_fee_cents: Optional[int] = Field(default=None, ge=0)
    concierge_success_balance_cents: Optional[int] = Field(default=None, ge=0)
    self_match_profile_limit: Optional[int] = Field(default=None, ge=1)
    self_match_interview_limit: Optional[int] = Field(default=None, ge=1)
    concierge_interview_limit: Optional[int] = Field(default=None, ge=1)
    candidate_access_days: Optional[int] = Field(default=None, ge=1)
    replacement_period_days: Optional[int] = Field(default=None, ge=1)
    replacement_credit_count: Optional[int] = Field(default=None, ge=1)
    replacement_max_count: Optional[int] = Field(default=None, ge=1)
    maybe_period_days: Optional[int] = Field(default=None, ge=1)


class AdminNotesPayload(BaseModel):
    note: Optional[str] = Field(default=None, max_length=4000)


class ReplacementRequestPayload(BaseModel):
    reason: str = Field(min_length=10, max_length=4000)


class ReplacementDecisionPayload(BaseModel):
    decision: Literal["approved", "declined", "completed"]
    note: str = Field(min_length=3, max_length=4000)


class AdminCandidateInvitePayload(BaseModel):
    nanny_id: int = Field(ge=1)
    note: Optional[str] = Field(default=None, max_length=2000)


class ManualPaymentPayload(BaseModel):
    fee_type: Literal["activation", "candidate_access", "application", "engagement", "success"]
    reason: str = Field(min_length=3, max_length=1000)


def _json_load(value, fallback):
    try:
        parsed = json.loads(value or "")
        return parsed if isinstance(parsed, type(fallback)) else fallback
    except (TypeError, ValueError):
        return fallback


def _activity(
    db: Session,
    placement_id: int,
    actor_user_id: Optional[int],
    event_type: str,
    details: Optional[dict] = None,
) -> None:
    db.add(
        models.PermanentPlacementActivity(
            placement_id=placement_id,
            actor_user_id=actor_user_id,
            event_type=event_type,
            details_json=json.dumps(details or {}, default=str),
        )
    )


def _notify_after_commit(
    db: Session,
    user_id: Optional[int],
    event_type: str,
    message: str,
    reference_id: int,
) -> None:
    if user_id is None:
        return
    try:
        notify(
            db,
            user_id,
            event_type,
            message,
            reference_id=reference_id,
            action_url="/placements",
        )
        db.commit()
    except Exception:
        db.rollback()


def _notify_admins(db: Session, event_type: str, message: str, reference_id: int) -> None:
    admin_ids = [
        row.id
        for row in db.query(models.User)
        .filter(models.User.is_admin.is_(True), models.User.is_active.is_(True))
        .all()
    ]
    for user_id in admin_ids:
        _notify_after_commit(db, user_id, event_type, message, reference_id)


def _naive_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _to_utc_z(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=ZoneInfo("Africa/Johannesburg"))
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _block_permanent_working_days(
    db: Session,
    placement: models.PermanentPlacement,
    candidate: models.PermanentPlacementCandidate,
) -> int:
    if (
        candidate.offer_start_date is None
        or not candidate.offer_start_time
        or not candidate.offer_end_time
    ):
        raise ValueError("The accepted offer does not contain a complete working schedule")
    weekdays = set(_json_load(candidate.offer_working_days_json, []))
    # Once a permanent role is accepted, the nanny may publish short-term
    # availability only on days outside that role (for example weekends for a
    # Monday-to-Friday offer). Keep the agreed hours on the offer itself, but
    # block each agreed working day in full to prevent unsafe back-to-back jobs.
    start_time = dt_time.min
    end_time = dt_time(23, 59, 59)
    end_date = candidate.offer_start_date + timedelta(days=363)
    note = f"Permanent placement #{placement.id}"
    existing_dates = {
        row[0]
        for row in (
            db.query(models.NannyAvailability.date)
            .filter(
                models.NannyAvailability.nanny_id == candidate.nanny_id,
                models.NannyAvailability.created_by == "permanent_placement",
                models.NannyAvailability.notes == note,
            )
            .all()
        )
    }
    local_tz = ZoneInfo("Africa/Johannesburg")
    created = 0
    day = candidate.offer_start_date
    while day <= end_date:
        if day.weekday() in weekdays and day not in existing_dates:
            local_start = datetime.combine(day, start_time).replace(tzinfo=local_tz)
            local_end = datetime.combine(day, end_time).replace(tzinfo=local_tz)
            db.add(
                models.NannyAvailability(
                    nanny_id=candidate.nanny_id,
                    date=day,
                    start_time=start_time,
                    end_time=end_time,
                    start_dt=_to_utc_z(local_start),
                    end_dt=_to_utc_z(local_end),
                    type="blocked",
                    is_available=False,
                    created_by="permanent_placement",
                    notes=note,
                )
            )
            created += 1
        day += timedelta(days=1)
    return created


def _contact_window_open(candidate: models.PermanentPlacementCandidate) -> bool:
    return bool(
        candidate.interview_invite_status == "accepted"
        and candidate.interview_credit_restored_at is None
        and candidate.interview_checked_in_at is None
        and candidate.interview_completed_at is None
    )


def _contact_terms_complete(candidate: models.PermanentPlacementCandidate) -> bool:
    return bool(
        candidate.parent_contact_terms_accepted_at
        and candidate.nanny_contact_terms_accepted_at
    )


CONTACT_TERMS_TEXT = (
    "Temporary contact access is only for arranging this interview. After the nanny "
    "checks in or completes the interview, contact details and direct chat are locked. "
    "Questions, trial arrangements, offers and salary discussions must then be managed "
    "through My Nanny. Platform terms apply to attempts to bypass this process."
)


def _communication_parties(
    db: Session,
    candidate_id: int,
    user: models.User,
) -> tuple[models.PermanentPlacementCandidate, models.PermanentPlacement, models.User, models.User, str]:
    candidate = (
        db.query(models.PermanentPlacementCandidate)
        .filter(models.PermanentPlacementCandidate.id == candidate_id)
        .first()
    )
    if candidate is None:
        raise HTTPException(status_code=404, detail="Permanent placement candidate not found")
    placement = (
        db.query(models.PermanentPlacement)
        .filter(models.PermanentPlacement.id == candidate.placement_id)
        .first()
    )
    nanny = db.query(models.Nanny).filter(models.Nanny.id == candidate.nanny_id).first()
    nanny_user = (
        db.query(models.User).filter(models.User.id == nanny.user_id).first()
        if nanny
        else None
    )
    parent_user = (
        db.query(models.User).filter(models.User.id == placement.parent_user_id).first()
        if placement
        else None
    )
    if placement is None or parent_user is None or nanny_user is None:
        raise HTTPException(status_code=404, detail="Permanent placement communication not found")
    if user.id == parent_user.id:
        role = "parent"
    elif user.id == nanny_user.id:
        role = "nanny"
    elif bool(user.is_admin):
        role = "admin"
    else:
        raise HTTPException(status_code=404, detail="Permanent placement communication not found")
    return candidate, placement, parent_user, nanny_user, role


def _communication_dict(
    db: Session,
    candidate: models.PermanentPlacementCandidate,
    placement: models.PermanentPlacement,
    parent_user: models.User,
    nanny_user: models.User,
    viewer_role: str,
) -> dict:
    window_open = _contact_window_open(candidate)
    terms_complete = _contact_terms_complete(candidate)
    messages = (
        db.query(models.PermanentPlacementMessage)
        .filter(models.PermanentPlacementMessage.candidate_id == candidate.id)
        .order_by(models.PermanentPlacementMessage.created_at.asc())
        .all()
    )
    users = {parent_user.id: parent_user, nanny_user.id: nanny_user}
    viewer_accepted = (
        bool(candidate.parent_contact_terms_accepted_at)
        if viewer_role == "parent"
        else bool(candidate.nanny_contact_terms_accepted_at)
        if viewer_role == "nanny"
        else True
    )
    peer = nanny_user if viewer_role == "parent" else parent_user
    contact_visible = bool(window_open and terms_complete and viewer_role in {"parent", "nanny"})
    return {
        "candidate_id": candidate.id,
        "placement_id": placement.id,
        "window_open": window_open,
        "locked_reason": (
            None
            if window_open
            else "Interview communication is closed. My Nanny will mediate all further questions, trials, offers and salary discussions."
        ),
        "terms_text": CONTACT_TERMS_TEXT,
        "viewer_role": viewer_role,
        "viewer_terms_accepted": viewer_accepted,
        "parent_terms_accepted": bool(candidate.parent_contact_terms_accepted_at),
        "nanny_terms_accepted": bool(candidate.nanny_contact_terms_accepted_at),
        "can_message": bool(window_open and terms_complete and viewer_role in {"parent", "nanny"}),
        "contact": (
            {
                "name": peer.name,
                "email": peer.email,
                "phone": peer.phone,
            }
            if contact_visible
            else None
        ),
        "messages": [
            {
                "id": message.id,
                "sender_user_id": message.sender_user_id,
                "sender_role": (
                    "parent"
                    if message.sender_user_id == parent_user.id
                    else "nanny"
                    if message.sender_user_id == nanny_user.id
                    else "admin"
                ),
                "sender_name": getattr(users.get(message.sender_user_id), "name", "My Nanny"),
                "body": message.body,
                "created_at": message.created_at,
            }
            for message in messages
        ],
    }


def _require_parent(authorization: Optional[str], db: Session) -> models.User:
    user = _require_user(authorization, db)
    if user.role != "parent":
        raise HTTPException(status_code=403, detail="A parent account is required")
    return user


def _require_nanny(authorization: Optional[str], db: Session) -> tuple[models.User, models.Nanny]:
    user = _require_user(authorization, db)
    if user.role != "nanny":
        raise HTTPException(status_code=403, detail="A nanny account is required")
    nanny = db.query(models.Nanny).filter(models.Nanny.user_id == user.id).first()
    if nanny is None:
        raise HTTPException(status_code=404, detail="Nanny profile not found")
    return user, nanny


def _parent_placement(db: Session, placement_id: int, parent_id: int) -> models.PermanentPlacement:
    placement = (
        db.query(models.PermanentPlacement)
        .filter(
            models.PermanentPlacement.id == placement_id,
            models.PermanentPlacement.parent_user_id == parent_id,
        )
        .first()
    )
    if placement is None:
        raise HTTPException(status_code=404, detail="Permanent placement not found")
    return placement


def _payment_dict(row: models.PermanentPlacementPayment) -> dict:
    return {
        "id": row.id,
        "fee_type": row.fee_type,
        "amount_cents": row.amount_cents,
        "status": row.status,
        "paid_at": row.paid_at,
        "paystack_reference": row.paystack_reference,
    }


def _preference_dict(row: Optional[models.PermanentPlacementPreference]) -> dict:
    if row is None:
        return {
            "opted_in": False,
            "desired_salary_min_cents": None,
            "desired_salary_max_cents": None,
            "employment_types": [],
            "preferred_locations": None,
            "available_from": None,
            "live_in_preference": None,
            "profile_notes": None,
            "consent_at": None,
        }
    return {
        "id": row.id,
        "opted_in": bool(row.opted_in),
        "desired_salary_min_cents": row.desired_salary_min_cents,
        "desired_salary_max_cents": row.desired_salary_max_cents,
        "employment_types": _json_load(row.employment_types_json, []),
        "preferred_locations": row.preferred_locations,
        "available_from": row.available_from,
        "live_in_preference": row.live_in_preference,
        "profile_notes": row.profile_notes,
        "consent_at": row.consent_at,
    }


def _candidate_profile(
    db: Session,
    candidate: models.PermanentPlacementCandidate,
    *,
    admin: bool = False,
) -> dict:
    nanny = db.query(models.Nanny).filter(models.Nanny.id == candidate.nanny_id).first()
    user = db.query(models.User).filter(models.User.id == nanny.user_id).first() if nanny else None
    profile = (
        db.query(models.NannyProfile)
        .filter(models.NannyProfile.nanny_id == candidate.nanny_id)
        .first()
    )
    preference = (
        db.query(models.PermanentPlacementPreference)
        .filter(models.PermanentPlacementPreference.nanny_id == candidate.nanny_id)
        .first()
    )
    previous_jobs = _json_load(getattr(profile, "previous_jobs_json", None), [])
    qualifications = [row.name for row in getattr(profile, "qualifications", [])]
    languages = [row.name for row in getattr(profile, "languages", [])]
    approvals = _json_load(getattr(profile, "document_approvals_json", None), {})
    first_name = ((getattr(user, "name", "") or "Candidate").split(" ", 1)[0]).strip()
    result = {
        "id": candidate.id,
        "candidate_code": f"MN-P-{candidate.nanny_id:05d}",
        "nanny_id": candidate.nanny_id,
        "status": candidate.status,
        "consent_status": candidate.consent_status,
        "first_name": first_name,
        "profile_photo_url": getattr(user, "profile_photo_url", None),
        "broad_location": ", ".join(
            item for item in [getattr(profile, "suburb", None), getattr(profile, "city", None)] if item
        ) or "Location available on request",
        "bio": getattr(profile, "bio", None),
        "experience": previous_jobs,
        "experience_count": len(previous_jobs),
        "qualifications": qualifications,
        "languages": languages,
        "available_from": getattr(preference, "available_from", None),
        "desired_salary_min_cents": getattr(preference, "desired_salary_min_cents", None),
        "desired_salary_max_cents": getattr(preference, "desired_salary_max_cents", None),
        "employment_types": _json_load(getattr(preference, "employment_types_json", None), []),
        "verification": {
            "profile_approved": bool(getattr(nanny, "approved", False)),
            "identity_document": bool(
                getattr(profile, "sa_id_document_url", None)
                or getattr(profile, "passport_document_url", None)
            ),
            "police_clearance": bool(getattr(profile, "police_clearance_document_url", None)),
            "video_screening": bool(getattr(nanny, "video_screening_complete", False)),
            "documents_approved": sum(
                1 for value in approvals.values() if isinstance(value, dict) and value.get("approved")
            ),
        },
        "interview_scheduled_at": candidate.interview_scheduled_at,
        "interview_checked_in_at": candidate.interview_checked_in_at,
        "interview_completed_at": candidate.interview_completed_at,
        "interview_invite_status": candidate.interview_invite_status,
        "interview_responded_at": candidate.interview_responded_at,
        "interview_credit_cycle": candidate.interview_credit_cycle,
        "interview_credit_consumed_at": candidate.interview_credit_consumed_at,
        "interview_credit_restored_at": candidate.interview_credit_restored_at,
        "interview_format": candidate.interview_format,
        "contact_window_open": _contact_window_open(candidate),
        "parent_contact_terms_accepted_at": candidate.parent_contact_terms_accepted_at,
        "nanny_contact_terms_accepted_at": candidate.nanny_contact_terms_accepted_at,
        "contact_details_visible": bool(
            _contact_window_open(candidate) and _contact_terms_complete(candidate)
        ),
        "trial_scheduled_at": candidate.trial_scheduled_at,
        "trial_ends_at": candidate.trial_ends_at,
        "trial_status": candidate.trial_status,
        "trial_responded_at": candidate.trial_responded_at,
        "trial_alternative_at": candidate.trial_alternative_at,
        "parent_interview_decision": candidate.parent_interview_decision,
        "parent_interview_feedback": candidate.parent_interview_feedback,
        "parent_interview_decided_at": candidate.parent_interview_decided_at,
        "maybe_until": candidate.maybe_until,
        "offer_status": candidate.offer_status,
        "offer_salary_cents": candidate.offer_salary_cents,
        "offer_start_date": candidate.offer_start_date,
        "offer_working_days": _json_load(candidate.offer_working_days_json, []),
        "offer_start_time": candidate.offer_start_time,
        "offer_end_time": candidate.offer_end_time,
        "offer_terms": candidate.offer_terms,
        "offer_sent_at": candidate.offer_sent_at,
        "offer_responded_at": candidate.offer_responded_at,
        "availability_restructured_at": candidate.availability_restructured_at,
        "profile_released_at": candidate.profile_released_at,
        "introduction_expires_at": candidate.introduction_expires_at,
    }
    if not admin and _contact_window_open(candidate) and _contact_terms_complete(candidate):
        result["temporary_contact"] = {
            "name": getattr(user, "name", None),
            "email": getattr(user, "email", None),
            "phone": getattr(user, "phone", None),
        }
    if admin:
        result.update(
            {
                "full_name": getattr(user, "name", None),
                "email": getattr(user, "email", None),
                "phone": getattr(user, "phone", None),
                "exact_address": getattr(profile, "formatted_address", None),
                "admin_notes": candidate.admin_notes,
                "client_notes": candidate.client_notes,
                "interview_location": candidate.interview_location,
                "trial_notes": candidate.trial_notes,
            }
        )
    return result


def _placement_dict(
    db: Session,
    placement: models.PermanentPlacement,
    *,
    include_candidates: bool = False,
    admin: bool = False,
) -> dict:
    payments = (
        db.query(models.PermanentPlacementPayment)
        .filter(models.PermanentPlacementPayment.placement_id == placement.id)
        .order_by(models.PermanentPlacementPayment.id.asc())
        .all()
    )
    invoices = (
        db.query(models.Invoice)
        .filter(models.Invoice.permanent_placement_id == placement.id)
        .order_by(models.Invoice.id.asc())
        .all()
    )
    result = {
        "id": placement.id,
        "service_tier": placement.service_tier,
        "status": placement.status,
        "role_title": placement.role_title,
        "employment_type": placement.employment_type,
        "start_date": placement.start_date,
        "schedule_summary": placement.schedule_summary,
        "hours_per_week": placement.hours_per_week,
        "children_count": placement.children_count,
        "children_ages": _json_load(placement.children_ages_json, []),
        "duties": placement.duties,
        "special_requirements": placement.special_requirements,
        "salary_min_cents": placement.salary_min_cents,
        "salary_max_cents": placement.salary_max_cents,
        "location_suburb": placement.location_suburb,
        "location_city": placement.location_city,
        "location_province": placement.location_province,
        "live_in": bool(placement.live_in),
        "drivers_license_required": bool(placement.drivers_license_required),
        "own_car_required": bool(placement.own_car_required),
        "languages": _json_load(placement.languages_json, []),
        "pets": placement.pets,
        "parent_notes": placement.parent_notes,
        "candidate_access_expires_at": placement.candidate_access_expires_at,
        "placed_nanny_id": placement.placed_nanny_id,
        "hired_at": placement.hired_at,
        "success_fee_due_at": placement.success_fee_due_at,
        "guarantee_until": placement.guarantee_until,
        "replacement_status": placement.replacement_status,
        "replacement_requested_at": placement.replacement_requested_at,
        "replacement_reason": placement.replacement_reason,
        "replacement_count": int(placement.replacement_count or 0),
        "upgraded_from_self_match": bool(placement.upgraded_from_self_match),
        "pricing": pricing_payload(db, placement),
        "interview_credits": interview_credit_summary(db, placement),
        "payments": [_payment_dict(row) for row in payments],
        "invoices": [invoice_payload(row) for row in invoices],
        "created_at": placement.created_at,
        "updated_at": placement.updated_at,
    }
    if admin:
        parent = db.query(models.User).filter(models.User.id == placement.parent_user_id).first()
        result.update(
            {
                "parent_user_id": placement.parent_user_id,
                "parent_name": getattr(parent, "name", None),
                "parent_email": getattr(parent, "email", None),
                "parent_phone": getattr(parent, "phone", None),
                "admin_notes": placement.admin_notes,
            }
        )
    if include_candidates:
        rows = (
            db.query(models.PermanentPlacementCandidate)
            .filter(models.PermanentPlacementCandidate.placement_id == placement.id)
            .order_by(models.PermanentPlacementCandidate.id.asc())
            .all()
        )
        if not admin:
            rows = [
                row
                for row in rows
                if row.consent_status == "accepted" and row.profile_released_at is not None
            ]
        result["candidates"] = [_candidate_profile(db, row, admin=admin) for row in rows]
    return result


def _candidate_for_parent(
    db: Session, placement: models.PermanentPlacement, candidate_id: int
) -> models.PermanentPlacementCandidate:
    candidate = (
        db.query(models.PermanentPlacementCandidate)
        .filter(
            models.PermanentPlacementCandidate.id == candidate_id,
            models.PermanentPlacementCandidate.placement_id == placement.id,
            models.PermanentPlacementCandidate.consent_status == "accepted",
            models.PermanentPlacementCandidate.profile_released_at.isnot(None),
        )
        .first()
    )
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate profile is not available")
    return candidate


@router.get("/permanent-placements/config")
def permanent_placement_config(db: Session = Depends(get_db)):
    return {"enabled": placement_feature_enabled(db), "pricing": pricing_payload(db)}


@router.get("/parents/me/permanent-placements")
def list_parent_placements(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    parent = _require_parent(authorization, db)
    rows = (
        db.query(models.PermanentPlacement)
        .filter(models.PermanentPlacement.parent_user_id == parent.id)
        .order_by(models.PermanentPlacement.created_at.desc())
        .all()
    )
    return {"results": [_placement_dict(db, row) for row in rows]}


@router.post("/parents/me/permanent-placements")
def create_parent_placement(
    payload: PlacementBriefPayload,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    parent = _require_parent(authorization, db)
    if not placement_feature_enabled(db):
        raise HTTPException(status_code=409, detail="The permanent placement pilot is not open yet")
    placement = models.PermanentPlacement(
        parent_user_id=parent.id,
        service_tier=payload.service_tier,
        status="awaiting_initial_payment",
        role_title=payload.role_title.strip(),
        employment_type=payload.employment_type,
        start_date=payload.start_date,
        schedule_summary=payload.schedule_summary.strip(),
        hours_per_week=payload.hours_per_week,
        children_count=payload.children_count,
        children_ages_json=json.dumps(payload.children_ages),
        duties=payload.duties.strip(),
        special_requirements=(payload.special_requirements or "").strip() or None,
        salary_min_cents=payload.salary_min_cents,
        salary_max_cents=payload.salary_max_cents,
        location_suburb=payload.location_suburb.strip(),
        location_city=payload.location_city.strip(),
        location_province=(payload.location_province or "").strip() or None,
        live_in=payload.live_in,
        drivers_license_required=payload.drivers_license_required,
        own_car_required=payload.own_car_required,
        languages_json=json.dumps(payload.languages),
        pets=(payload.pets or "").strip() or None,
        parent_notes=(payload.parent_notes or "").strip() or None,
    )
    db.add(placement)
    db.flush()
    snapshot_placement_pricing(db, placement)
    fee_type = initial_fee_type(placement)
    get_or_create_payment(db, placement, fee_type)
    _activity(db, placement.id, parent.id, "brief_created", {"service_tier": placement.service_tier})
    db.commit()
    db.refresh(placement)
    log_audit(
        db,
        actor_user=parent,
        target_user_id=parent.id,
        entity="permanent_placements",
        entity_id=placement.id,
        action="create",
        after_obj={"service_tier": placement.service_tier, "status": placement.status},
        request=request,
    )
    _notify_admins(
        db,
        "permanent_brief_created",
        f"A new {placement.service_tier.replace('_', ' ')} permanent-placement brief #{placement.id} has been created.",
        placement.id,
    )
    return _placement_dict(db, placement, include_candidates=True)


@router.get("/parents/me/permanent-placements/{placement_id}")
def get_parent_placement(
    placement_id: int,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    parent = _require_parent(authorization, db)
    placement = _parent_placement(db, placement_id, parent.id)
    return _placement_dict(db, placement, include_candidates=True)


@router.patch("/parents/me/permanent-placements/{placement_id}")
def update_parent_placement(
    placement_id: int,
    payload: PlacementBriefUpdatePayload,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    parent = _require_parent(authorization, db)
    placement = _parent_placement(db, placement_id, parent.id)
    if placement.status not in {"awaiting_initial_payment", "brief_submitted", "awaiting_candidate_access"}:
        raise HTTPException(status_code=409, detail="This brief can no longer be edited by the family")
    updates = payload.model_dump(exclude_unset=True)
    if "salary_min_cents" in updates or "salary_max_cents" in updates:
        minimum = updates.get("salary_min_cents", placement.salary_min_cents)
        maximum = updates.get("salary_max_cents", placement.salary_max_cents)
        if maximum < minimum:
            raise HTTPException(status_code=422, detail="Maximum salary must be at least the minimum salary")
    if "children_ages" in updates:
        placement.children_ages_json = json.dumps(updates.pop("children_ages"))
    if "languages" in updates:
        placement.languages_json = json.dumps(updates.pop("languages"))
    for key, value in updates.items():
        setattr(placement, key, value.strip() if isinstance(value, str) else value)
    _activity(db, placement.id, parent.id, "brief_updated", {"fields": sorted(updates)})
    db.commit()
    log_audit(
        db,
        actor_user=parent,
        target_user_id=parent.id,
        entity="permanent_placements",
        entity_id=placement.id,
        action="update",
        after_obj={"fields": sorted(updates)},
        request=request,
    )
    return _placement_dict(db, placement, include_candidates=True)


@router.post("/parents/me/permanent-placements/{placement_id}/upgrade")
def upgrade_parent_placement(
    placement_id: int,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    parent = _require_parent(authorization, db)
    placement = _parent_placement(db, placement_id, parent.id)
    if placement.service_tier != "self_match":
        raise HTTPException(status_code=409, detail="This placement already uses Concierge")
    if placement.status in {"placed", "closed", "cancelled"}:
        raise HTTPException(status_code=409, detail="This placement cannot be upgraded")
    if not paid_fee(db, placement.id, "activation"):
        raise HTTPException(status_code=409, detail="Complete the Self-Match activation fee before upgrading")
    placement.service_tier = "concierge"
    placement.upgraded_from_self_match = True
    placement.status = "awaiting_engagement_payment"
    get_or_create_payment(db, placement, "engagement")
    _activity(
        db,
        placement.id,
        parent.id,
        "upgraded_to_concierge",
        {
            "candidate_access_credit_cents": pricing_payload(db, placement)["upgrade"][
                "candidate_access_credit_cents"
            ]
        },
    )
    db.commit()
    log_audit(
        db,
        actor_user=parent,
        target_user_id=parent.id,
        entity="permanent_placements",
        entity_id=placement.id,
        action="upgrade_to_concierge",
        request=request,
    )
    _notify_admins(
        db,
        "permanent_placement_upgraded",
        f"Permanent placement #{placement.id} has upgraded to Concierge.",
        placement.id,
    )
    return _placement_dict(db, placement, include_candidates=True)


@router.post("/parents/me/permanent-placements/{placement_id}/request-replacement")
def request_placement_replacement(
    placement_id: int,
    payload: ReplacementRequestPayload,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    parent = _require_parent(authorization, db)
    placement = _parent_placement(db, placement_id, parent.id)
    if placement.status != "placed" or not placement.guarantee_until:
        raise HTTPException(status_code=409, detail="This placement does not have an active replacement period")
    if placement.guarantee_until < utc_now():
        raise HTTPException(status_code=409, detail="The replacement period has expired")
    if placement.replacement_status in {"requested", "approved"}:
        raise HTTPException(status_code=409, detail="A replacement request is already open")
    replacement_limit = int(
        pricing_payload(db, placement)["self_match"]["replacement_max_count"]
    )
    if int(placement.replacement_count or 0) >= replacement_limit:
        raise HTTPException(status_code=409, detail="The included replacement has already been used")
    placement.replacement_status = "requested"
    placement.replacement_requested_at = utc_now()
    placement.replacement_reason = payload.reason.strip()
    _activity(db, placement.id, parent.id, "replacement_requested", {"reason": payload.reason.strip()})
    db.commit()
    log_audit(
        db,
        actor_user=parent,
        target_user_id=parent.id,
        entity="permanent_placements",
        entity_id=placement.id,
        action="replacement_requested",
        request=request,
    )
    _notify_admins(
        db,
        "permanent_replacement_requested",
        f"A replacement was requested for permanent placement #{placement.id}.",
        placement.id,
    )
    return _placement_dict(db, placement, include_candidates=True)


@router.post("/parents/me/permanent-placements/{placement_id}/candidates/{candidate_id}/shortlist")
def shortlist_candidate(
    placement_id: int,
    candidate_id: int,
    payload: CandidateNotePayload,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    parent = _require_parent(authorization, db)
    placement = _parent_placement(db, placement_id, parent.id)
    candidate = _candidate_for_parent(db, placement, candidate_id)
    candidate.status = "shortlisted"
    candidate.shortlisted_at = utc_now()
    candidate.client_notes = (payload.note or "").strip() or None
    _activity(db, placement.id, parent.id, "candidate_shortlisted", {"candidate_id": candidate.id})
    db.commit()
    log_audit(
        db,
        actor_user=parent,
        target_user_id=parent.id,
        entity="permanent_placement_candidates",
        entity_id=candidate.id,
        action="shortlist",
        request=request,
    )
    _notify_admins(
        db,
        "permanent_candidate_shortlisted",
        f"The family shortlisted candidate {candidate.id} for placement #{placement.id}.",
        placement.id,
    )
    return _placement_dict(db, placement, include_candidates=True)


@router.post("/parents/me/permanent-placements/{placement_id}/candidates/{candidate_id}/request-interview")
def request_candidate_interview(
    placement_id: int,
    candidate_id: int,
    payload: CandidateNotePayload,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    parent = _require_parent(authorization, db)
    placement = _parent_placement(db, placement_id, parent.id)
    candidate = _candidate_for_parent(db, placement, candidate_id)
    if candidate.interview_invite_status in {"pending", "accepted"}:
        raise HTTPException(status_code=409, detail="This interview invitation is already active")
    candidate.status = "interview_requested"
    candidate.interview_requested_at = utc_now()
    candidate.interview_invite_status = "pending"
    candidate.interview_responded_at = None
    candidate.interview_scheduled_at = None
    candidate.interview_checked_in_at = None
    candidate.interview_completed_at = None
    candidate.parent_contact_terms_accepted_at = None
    candidate.nanny_contact_terms_accepted_at = None
    candidate.client_notes = (payload.note or candidate.client_notes or "").strip() or None
    placement.status = "interviewing"
    _activity(db, placement.id, parent.id, "interview_requested", {"candidate_id": candidate.id})
    db.commit()
    log_audit(
        db,
        actor_user=parent,
        target_user_id=parent.id,
        entity="permanent_placement_candidates",
        entity_id=candidate.id,
        action="interview_requested",
        request=request,
    )
    _notify_admins(
        db,
        "permanent_interview_requested",
        f"An interview was requested for candidate {candidate.id} on placement #{placement.id}.",
        placement.id,
    )
    nanny = db.query(models.Nanny).filter(models.Nanny.id == candidate.nanny_id).first()
    _notify_after_commit(
        db,
        getattr(nanny, "user_id", None),
        "permanent_interview_invited",
        "A family has invited you to a permanent-placement interview. Accepting uses one of the family's included interview credits.",
        candidate.id,
    )
    return _placement_dict(db, placement, include_candidates=True)


@router.post("/parents/me/permanent-placements/{placement_id}/candidates/{candidate_id}/interview-decision")
def record_parent_interview_decision(
    placement_id: int,
    candidate_id: int,
    payload: ParentInterviewDecisionPayload,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    parent = _require_parent(authorization, db)
    placement = _parent_placement(db, placement_id, parent.id)
    candidate = _candidate_for_parent(db, placement, candidate_id)
    if candidate.interview_completed_at is None:
        raise HTTPException(
            status_code=409,
            detail="The nanny must mark the interview completed before feedback is recorded",
        )
    now = utc_now()
    if (
        candidate.parent_interview_decision == "maybe"
        and candidate.maybe_until
        and candidate.maybe_until < now
    ):
        candidate.status = "released"
        candidate.parent_interview_decision = "maybe_expired"
        db.commit()
        raise HTTPException(status_code=409, detail="The four-day Maybe period has expired")

    existing_maybe_until = (
        candidate.maybe_until
        if candidate.parent_interview_decision == "maybe"
        and candidate.maybe_until
        and candidate.maybe_until >= now
        else None
    )
    candidate.parent_interview_decision = payload.decision
    candidate.parent_interview_feedback = payload.feedback.strip()
    candidate.parent_interview_decided_at = now
    candidate.maybe_until = None
    status_by_decision = {
        "reject": "rejected",
        "maybe": "maybe",
        "trial": "trial_requested",
        "offer": "offer_requested",
        "admin_support": "admin_support_requested",
    }
    candidate.status = status_by_decision[payload.decision]
    if payload.decision == "maybe":
        candidate.maybe_until = existing_maybe_until or now + timedelta(
            days=int(pricing_payload(db, placement)["rules"]["maybe_period_days"])
        )
    _activity(
        db,
        placement.id,
        parent.id,
        f"parent_interview_{payload.decision}",
        {
            "candidate_id": candidate.id,
            "feedback": payload.feedback.strip(),
            "maybe_until": candidate.maybe_until,
        },
    )
    db.commit()
    log_audit(
        db,
        actor_user=parent,
        target_user_id=parent.id,
        entity="permanent_placement_candidates",
        entity_id=candidate.id,
        action=f"interview_decision_{payload.decision}",
        after_obj={
            "decision": payload.decision,
            "feedback": payload.feedback.strip(),
            "maybe_until": candidate.maybe_until,
        },
        request=request,
    )
    nanny = db.query(models.Nanny).filter(models.Nanny.id == candidate.nanny_id).first()
    _notify_after_commit(
        db,
        getattr(nanny, "user_id", None),
        "permanent_interview_decision",
        (
            "The family would like My Nanny to arrange the next step after your interview."
            if payload.decision in {"trial", "offer", "admin_support"}
            else "The family has recorded an update after your interview. My Nanny will support the next step."
        ),
        candidate.id,
    )
    _notify_admins(
        db,
        "permanent_interview_decision",
        f"The family selected {payload.decision.replace('_', ' ')} for candidate {candidate.id} on placement #{placement.id}.",
        placement.id,
    )
    return _placement_dict(db, placement, include_candidates=True)


@router.post("/parents/me/permanent-placements/{placement_id}/candidates/{candidate_id}/trial")
def request_permanent_trial(
    placement_id: int,
    candidate_id: int,
    payload: TrialRequestPayload,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    parent = _require_parent(authorization, db)
    placement = _parent_placement(db, placement_id, parent.id)
    candidate = _candidate_for_parent(db, placement, candidate_id)
    if candidate.parent_interview_decision != "trial":
        raise HTTPException(status_code=409, detail="Choose Request trial after the interview first")
    if candidate.trial_status in {"pending", "accepted"}:
        raise HTTPException(status_code=409, detail="A trial request is already active")
    starts_at = _naive_datetime(payload.starts_at)
    ends_at = _naive_datetime(payload.ends_at)
    if starts_at <= utc_now():
        raise HTTPException(status_code=422, detail="Choose a future trial date and time")
    candidate.trial_scheduled_at = starts_at
    candidate.trial_ends_at = ends_at
    candidate.trial_status = "pending"
    candidate.trial_responded_at = None
    candidate.trial_alternative_at = None
    candidate.trial_notes = (payload.note or "").strip() or None
    candidate.status = "trial_requested"
    _activity(
        db,
        placement.id,
        parent.id,
        "trial_requested",
        {"candidate_id": candidate.id, "starts_at": starts_at, "ends_at": ends_at},
    )
    db.commit()
    log_audit(
        db,
        actor_user=parent,
        target_user_id=parent.id,
        entity="permanent_placement_candidates",
        entity_id=candidate.id,
        action="trial_requested",
        after_obj={"starts_at": starts_at, "ends_at": ends_at},
        request=request,
    )
    nanny = db.query(models.Nanny).filter(models.Nanny.id == candidate.nanny_id).first()
    _notify_after_commit(
        db,
        getattr(nanny, "user_id", None),
        "permanent_trial_requested",
        "The family proposed a paid trial date. Accept it, decline it or suggest another time in Permanent Placements.",
        candidate.id,
    )
    _notify_admins(
        db,
        "permanent_trial_requested",
        f"A paid trial was requested for candidate {candidate.id} on placement #{placement.id}.",
        placement.id,
    )
    return _placement_dict(db, placement, include_candidates=True)


@router.post("/parents/me/permanent-placements/{placement_id}/candidates/{candidate_id}/offer")
def make_permanent_offer(
    placement_id: int,
    candidate_id: int,
    payload: OfferPayload,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    parent = _require_parent(authorization, db)
    placement = _parent_placement(db, placement_id, parent.id)
    candidate = _candidate_for_parent(db, placement, candidate_id)
    if candidate.parent_interview_decision != "offer":
        raise HTTPException(status_code=409, detail="Choose Make an offer after the interview first")
    if candidate.offer_status in {"pending", "accepted"}:
        raise HTTPException(status_code=409, detail="An offer is already active")
    if payload.start_date < utc_now().date():
        raise HTTPException(status_code=422, detail="Offer start date cannot be in the past")
    candidate.offer_status = "pending"
    candidate.offer_salary_cents = payload.salary_cents
    candidate.offer_start_date = payload.start_date
    candidate.offer_working_days_json = json.dumps(sorted(payload.working_days))
    candidate.offer_start_time = payload.start_time
    candidate.offer_end_time = payload.end_time
    candidate.offer_terms = payload.terms.strip()
    candidate.offer_sent_at = utc_now()
    candidate.offer_responded_at = None
    candidate.status = "offer_pending"
    _activity(
        db,
        placement.id,
        parent.id,
        "offer_sent",
        {
            "candidate_id": candidate.id,
            "salary_cents": payload.salary_cents,
            "start_date": payload.start_date,
            "working_days": sorted(payload.working_days),
            "start_time": payload.start_time,
            "end_time": payload.end_time,
        },
    )
    db.commit()
    log_audit(
        db,
        actor_user=parent,
        target_user_id=parent.id,
        entity="permanent_placement_candidates",
        entity_id=candidate.id,
        action="offer_sent",
        after_obj={
            "salary_cents": payload.salary_cents,
            "start_date": payload.start_date,
            "working_days": sorted(payload.working_days),
        },
        request=request,
    )
    nanny = db.query(models.Nanny).filter(models.Nanny.id == candidate.nanny_id).first()
    _notify_after_commit(
        db,
        getattr(nanny, "user_id", None),
        "permanent_offer_received",
        "A family sent you a permanent placement offer. Review the salary, start date and working schedule in Permanent Placements.",
        candidate.id,
    )
    _notify_admins(
        db,
        "permanent_offer_received",
        f"A family sent an offer to candidate {candidate.id} for placement #{placement.id}.",
        placement.id,
    )
    return _placement_dict(db, placement, include_candidates=True)


def _validate_fee_due(db: Session, placement: models.PermanentPlacement, fee_type: str) -> None:
    expected = initial_fee_type(placement)
    if fee_type == expected and placement.status == "awaiting_initial_payment":
        return
    if fee_type == "candidate_access" and placement.service_tier == "self_match" and placement.status == "awaiting_candidate_access":
        return
    if fee_type == "engagement" and placement.service_tier == "concierge" and placement.status == "awaiting_engagement_payment":
        return
    if fee_type == "success" and placement.status == "awaiting_success_fee":
        return
    raise HTTPException(status_code=409, detail="This fee is not currently due")


@router.post("/parents/me/permanent-placements/{placement_id}/payments/{fee_type}/initialize")
def initialize_placement_payment(
    placement_id: int,
    fee_type: str,
    payload: PaymentInitializePayload,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    parent = _require_parent(authorization, db)
    placement = _parent_placement(db, placement_id, parent.id)
    _validate_fee_due(db, placement, fee_type)
    payment = get_or_create_payment(db, placement, fee_type)
    if payment.status == "paid":
        raise HTTPException(status_code=409, detail="This fee has already been paid")
    reference = f"MN-PLACE-{placement.id}-{fee_type.upper()}-{uuid.uuid4().hex[:12]}"
    ok, result = initialize_transaction(
        email=parent.email,
        amount_kobo=payment.amount_cents,
        reference=reference,
        callback_url=payload.callback_url,
        metadata={
            "purpose": "permanent_placement_fee",
            "placement_id": placement.id,
            "payment_id": payment.id,
            "fee_type": fee_type,
            "parent_user_id": parent.id,
        },
    )
    if not ok:
        raise HTTPException(status_code=502, detail=result.get("message") or "Paystack could not start the payment")
    data = result.get("data") or result
    payment.paystack_reference = str(data.get("reference") or reference)
    payment.status = "initialized"
    invoice, invoice_created, _ = sync_invoice_for_payment(db, payment)
    if invoice_created:
        invoice.invoice_email_requested_at = utc_now()
    db.commit()
    if invoice_created:
        _notify_after_commit(
            db,
            parent.id,
            "permanent_invoice_issued",
            _document_ready_message("Invoice", invoice.invoice_number),
            invoice.id,
        )
    return {
        "authorization_url": data.get("authorization_url"),
        "access_code": data.get("access_code"),
        "reference": payment.paystack_reference,
        "amount_cents": payment.amount_cents,
        "invoice": invoice_payload(invoice),
    }


@router.post("/parents/me/permanent-placements/{placement_id}/payments/verify")
def verify_placement_payment(
    placement_id: int,
    payload: PaymentVerifyPayload,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    parent = _require_parent(authorization, db)
    placement = _parent_placement(db, placement_id, parent.id)
    payment = (
        db.query(models.PermanentPlacementPayment)
        .filter(
            models.PermanentPlacementPayment.placement_id == placement.id,
            models.PermanentPlacementPayment.paystack_reference == payload.reference,
        )
        .first()
    )
    if payment is None:
        raise HTTPException(status_code=404, detail="Placement payment not found")
    ok, result = verify_transaction(payload.reference)
    if not ok:
        raise HTTPException(status_code=502, detail=result.get("message") or "Paystack verification failed")
    data = result.get("data") or result
    if str(data.get("status") or "").lower() != "success":
        raise HTTPException(status_code=409, detail="Paystack has not confirmed this payment")
    if int(data.get("amount") or 0) < int(payment.amount_cents):
        raise HTTPException(status_code=409, detail="The confirmed payment amount is too low")
    metadata = data.get("metadata") or {}
    if isinstance(metadata, str):
        metadata = _json_load(metadata, {})
    if metadata and str(metadata.get("placement_id")) != str(placement.id):
        raise HTTPException(status_code=409, detail="Payment metadata does not match this placement")
    apply_paid_payment(db, payment, transaction_id=data.get("id"))
    invoice, invoice_created, receipt_created = sync_invoice_for_payment(db, payment)
    if invoice_created:
        invoice.invoice_email_requested_at = utc_now()
    if receipt_created:
        invoice.receipt_email_requested_at = utc_now()
    _activity(db, placement.id, parent.id, "fee_paid", {"fee_type": payment.fee_type, "amount_cents": payment.amount_cents})
    db.commit()
    if invoice_created:
        _notify_after_commit(
            db,
            parent.id,
            "permanent_invoice_issued",
            _document_ready_message("Invoice", invoice.invoice_number),
            invoice.id,
        )
    if receipt_created:
        _notify_after_commit(
            db,
            parent.id,
            "permanent_receipt_ready",
            _document_ready_message("Receipt", invoice.receipt_number),
            invoice.id,
        )
    _notify_admins(
        db,
        "permanent_fee_paid",
        f"The {payment.fee_type.replace('_', ' ')} fee was paid for placement #{placement.id}.",
        placement.id,
    )
    return _placement_dict(db, placement, include_candidates=True)


@router.get("/nannies/me/permanent-placement-profile")
def get_nanny_permanent_profile(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    _, nanny = _require_nanny(authorization, db)
    preference = (
        db.query(models.PermanentPlacementPreference)
        .filter(models.PermanentPlacementPreference.nanny_id == nanny.id)
        .first()
    )
    return _preference_dict(preference)


@router.put("/nannies/me/permanent-placement-profile")
def update_nanny_permanent_profile(
    payload: NannyPreferencePayload,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    user, nanny = _require_nanny(authorization, db)
    preference = (
        db.query(models.PermanentPlacementPreference)
        .filter(models.PermanentPlacementPreference.nanny_id == nanny.id)
        .first()
    )
    if preference is None:
        preference = models.PermanentPlacementPreference(nanny_id=nanny.id)
        db.add(preference)
    previously_opted_in = bool(preference.opted_in)
    preference.opted_in = payload.opted_in
    preference.desired_salary_min_cents = payload.desired_salary_min_cents
    preference.desired_salary_max_cents = payload.desired_salary_max_cents
    preference.employment_types_json = json.dumps(payload.employment_types)
    preference.preferred_locations = (payload.preferred_locations or "").strip() or None
    preference.available_from = payload.available_from
    preference.live_in_preference = payload.live_in_preference
    preference.profile_notes = (payload.profile_notes or "").strip() or None
    if payload.opted_in and (not previously_opted_in or preference.consent_at is None):
        preference.consent_at = utc_now()
    if not payload.opted_in:
        preference.consent_at = None
    db.commit()
    db.refresh(preference)
    log_audit(
        db,
        actor_user=user,
        target_user_id=user.id,
        entity="permanent_placement_preferences",
        entity_id=preference.id,
        action="opt_in" if payload.opted_in else "opt_out",
        after_obj={"opted_in": payload.opted_in},
        request=request,
    )
    return _preference_dict(preference)


@router.get("/nannies/me/permanent-opportunities")
def list_nanny_permanent_opportunities(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    _, nanny = _require_nanny(authorization, db)
    candidates = (
        db.query(models.PermanentPlacementCandidate)
        .filter(models.PermanentPlacementCandidate.nanny_id == nanny.id)
        .order_by(models.PermanentPlacementCandidate.created_at.desc())
        .all()
    )
    results = []
    for candidate in candidates:
        placement = (
            db.query(models.PermanentPlacement)
            .filter(models.PermanentPlacement.id == candidate.placement_id)
            .first()
        )
        if placement is None:
            continue
        parent_user = (
            db.query(models.User)
            .filter(models.User.id == placement.parent_user_id)
            .first()
        )
        contact_visible = bool(
            _contact_window_open(candidate) and _contact_terms_complete(candidate)
        )
        results.append(
            {
                "candidate_id": candidate.id,
                "placement_id": placement.id,
                "status": candidate.status,
                "consent_status": candidate.consent_status,
                "service_tier": placement.service_tier,
                "role_title": placement.role_title,
                "employment_type": placement.employment_type,
                "start_date": placement.start_date,
                "schedule_summary": placement.schedule_summary,
                "children_count": placement.children_count,
                "children_ages": _json_load(placement.children_ages_json, []),
                "duties": placement.duties,
                "special_requirements": placement.special_requirements,
                "salary_min_cents": placement.salary_min_cents,
                "salary_max_cents": placement.salary_max_cents,
                "broad_location": ", ".join(
                    item for item in [placement.location_suburb, placement.location_city] if item
                ),
                "live_in": bool(placement.live_in),
                "drivers_license_required": bool(placement.drivers_license_required),
                "own_car_required": bool(placement.own_car_required),
                "languages": _json_load(placement.languages_json, []),
                "pets": placement.pets,
                "interview_scheduled_at": candidate.interview_scheduled_at,
                "interview_invite_status": candidate.interview_invite_status,
                "interview_responded_at": candidate.interview_responded_at,
                "interview_checked_in_at": candidate.interview_checked_in_at,
                "interview_completed_at": candidate.interview_completed_at,
                "interview_format": candidate.interview_format,
                "interview_location": candidate.interview_location,
                "contact_window_open": _contact_window_open(candidate),
                "parent_contact_terms_accepted_at": candidate.parent_contact_terms_accepted_at,
                "nanny_contact_terms_accepted_at": candidate.nanny_contact_terms_accepted_at,
                "contact_details_visible": contact_visible,
                "temporary_contact": (
                    {
                        "name": getattr(parent_user, "name", None),
                        "email": getattr(parent_user, "email", None),
                        "phone": getattr(parent_user, "phone", None),
                    }
                    if contact_visible
                    else None
                ),
                "trial_scheduled_at": candidate.trial_scheduled_at,
                "trial_ends_at": candidate.trial_ends_at,
                "trial_status": candidate.trial_status,
                "trial_alternative_at": candidate.trial_alternative_at,
                "trial_notes": candidate.trial_notes,
                "offer_status": candidate.offer_status,
                "offer_salary_cents": candidate.offer_salary_cents,
                "offer_start_date": candidate.offer_start_date,
                "offer_working_days": _json_load(candidate.offer_working_days_json, []),
                "offer_start_time": candidate.offer_start_time,
                "offer_end_time": candidate.offer_end_time,
                "offer_terms": candidate.offer_terms,
                "offer_sent_at": candidate.offer_sent_at,
                "offer_responded_at": candidate.offer_responded_at,
                "availability_restructured_at": candidate.availability_restructured_at,
                "invited_at": candidate.invited_at,
            }
        )
    return {"results": results}


@router.post("/nannies/me/permanent-opportunities/{candidate_id}/respond")
def respond_to_permanent_opportunity(
    candidate_id: int,
    payload: CandidateResponsePayload,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    user, nanny = _require_nanny(authorization, db)
    candidate = (
        db.query(models.PermanentPlacementCandidate)
        .filter(
            models.PermanentPlacementCandidate.id == candidate_id,
            models.PermanentPlacementCandidate.nanny_id == nanny.id,
        )
        .first()
    )
    if candidate is None:
        raise HTTPException(status_code=404, detail="Permanent opportunity not found")
    if candidate.consent_status != "pending":
        raise HTTPException(status_code=409, detail="You have already responded to this opportunity")
    candidate.consent_status = payload.decision
    candidate.status = "consented" if payload.decision == "accepted" else "declined"
    candidate.responded_at = utc_now()
    candidate.admin_notes = (payload.note or "").strip() or candidate.admin_notes
    _activity(
        db,
        candidate.placement_id,
        user.id,
        "candidate_consent_accepted" if payload.decision == "accepted" else "candidate_consent_declined",
        {"candidate_id": candidate.id},
    )
    db.commit()
    log_audit(
        db,
        actor_user=user,
        target_user_id=user.id,
        entity="permanent_placement_candidates",
        entity_id=candidate.id,
        action=f"consent_{payload.decision}",
        request=request,
    )
    _notify_admins(
        db,
        "permanent_candidate_response",
        f"A nanny has {payload.decision} permanent placement opportunity #{candidate.placement_id}.",
        candidate.placement_id,
    )
    return {"ok": True, "status": candidate.status, "consent_status": candidate.consent_status}


@router.post("/nannies/me/permanent-opportunities/{candidate_id}/interview-response")
def respond_to_permanent_interview(
    candidate_id: int,
    payload: InterviewResponsePayload,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    user, nanny = _require_nanny(authorization, db)
    candidate = (
        db.query(models.PermanentPlacementCandidate)
        .filter(
            models.PermanentPlacementCandidate.id == candidate_id,
            models.PermanentPlacementCandidate.nanny_id == nanny.id,
        )
        .first()
    )
    if candidate is None:
        raise HTTPException(status_code=404, detail="Permanent interview invitation not found")
    placement = (
        db.query(models.PermanentPlacement)
        .filter(models.PermanentPlacement.id == candidate.placement_id)
        .with_for_update()
        .first()
    )
    if placement is None:
        raise HTTPException(status_code=404, detail="Permanent placement not found")

    note = (payload.note or "").strip() or None
    now = utc_now()
    if payload.decision in {"accepted", "declined"}:
        if candidate.interview_invite_status != "pending":
            raise HTTPException(status_code=409, detail="This interview invitation is not awaiting a response")
        candidate.interview_responded_at = now
        if payload.decision == "accepted":
            try:
                credits = consume_interview_credit(
                    db,
                    placement,
                    candidate,
                    actor_user_id=user.id,
                )
            except ValueError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            candidate.interview_invite_status = "accepted"
            candidate.status = "interview_accepted"
            event_type = "interview_invitation_accepted"
        else:
            credits = interview_credit_summary(db, placement)
            candidate.interview_invite_status = "declined"
            candidate.status = "released"
            event_type = "interview_invitation_declined"
    else:
        if candidate.interview_invite_status != "accepted":
            raise HTTPException(status_code=409, detail="Only an accepted interview can be cancelled")
        if not note:
            raise HTTPException(status_code=422, detail="Please provide a cancellation reason")
        try:
            credits = restore_interview_credit(
                db,
                placement,
                candidate,
                actor_user_id=user.id,
                event_type="cancelled_by_nanny",
                reason=note,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        candidate.interview_invite_status = "cancelled_by_nanny"
        candidate.status = "released"
        placement.status = "search_active"
        event_type = "interview_cancelled_by_nanny"

    candidate.admin_notes = note or candidate.admin_notes
    _activity(
        db,
        placement.id,
        user.id,
        event_type,
        {"candidate_id": candidate.id, "credits": credits, "note": note},
    )
    db.commit()
    log_audit(
        db,
        actor_user=user,
        target_user_id=placement.parent_user_id,
        entity="permanent_placement_candidates",
        entity_id=candidate.id,
        action=event_type,
        after_obj={"interview_invite_status": candidate.interview_invite_status, "credits": credits},
        request=request,
    )
    _notify_after_commit(
        db,
        placement.parent_user_id,
        "permanent_interview_response",
        (
            "A nanny accepted your interview invitation. My Nanny will coordinate the arrangements."
            if payload.decision == "accepted"
            else "A nanny declined or cancelled your interview invitation. Your placement team has been notified."
        ),
        candidate.id,
    )
    _notify_admins(
        db,
        "permanent_interview_response",
        f"Candidate {candidate.id} {payload.decision} the interview invitation for placement #{placement.id}.",
        placement.id,
    )
    return {
        "ok": True,
        "status": candidate.status,
        "interview_invite_status": candidate.interview_invite_status,
        "interview_credits": credits,
    }


@router.post("/nannies/me/permanent-opportunities/{candidate_id}/interview-progress")
def record_permanent_interview_progress(
    candidate_id: int,
    payload: InterviewProgressPayload,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    user, nanny = _require_nanny(authorization, db)
    candidate = (
        db.query(models.PermanentPlacementCandidate)
        .filter(
            models.PermanentPlacementCandidate.id == candidate_id,
            models.PermanentPlacementCandidate.nanny_id == nanny.id,
        )
        .first()
    )
    if candidate is None:
        raise HTTPException(status_code=404, detail="Permanent interview not found")
    placement = (
        db.query(models.PermanentPlacement)
        .filter(models.PermanentPlacement.id == candidate.placement_id)
        .first()
    )
    if placement is None:
        raise HTTPException(status_code=404, detail="Permanent placement not found")
    if (
        candidate.interview_invite_status not in {"accepted", "completed"}
        or candidate.interview_scheduled_at is None
        or candidate.interview_credit_restored_at is not None
    ):
        raise HTTPException(status_code=409, detail="There is no active scheduled interview")

    now = utc_now()
    if payload.action == "check_in":
        candidate.interview_checked_in_at = candidate.interview_checked_in_at or now
        event_type = "interview_checked_in"
        message = "The nanny has arrived for the interview."
    else:
        candidate.interview_completed_at = candidate.interview_completed_at or now
        candidate.interview_invite_status = "completed"
        candidate.status = "interviewed"
        event_type = "interview_completed"
        message = "The nanny marked the interview completed. Please record your feedback and next step."
    _activity(
        db,
        placement.id,
        user.id,
        event_type,
        {"candidate_id": candidate.id, "recorded_at": now},
    )
    db.commit()
    log_audit(
        db,
        actor_user=user,
        target_user_id=placement.parent_user_id,
        entity="permanent_placement_candidates",
        entity_id=candidate.id,
        action=event_type,
        after_obj={"recorded_at": now},
        request=request,
    )
    _notify_after_commit(
        db,
        placement.parent_user_id,
        event_type,
        message,
        candidate.id,
    )
    _notify_admins(
        db,
        event_type,
        f"Candidate {candidate.id} updated interview progress for placement #{placement.id}: {payload.action.replace('_', ' ')}.",
        placement.id,
    )
    return {
        "ok": True,
        "status": candidate.status,
        "interview_checked_in_at": candidate.interview_checked_in_at,
        "interview_completed_at": candidate.interview_completed_at,
    }


@router.post("/nannies/me/permanent-opportunities/{candidate_id}/trial-response")
def respond_to_permanent_trial(
    candidate_id: int,
    payload: TrialResponsePayload,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    user, nanny = _require_nanny(authorization, db)
    candidate = (
        db.query(models.PermanentPlacementCandidate)
        .filter(
            models.PermanentPlacementCandidate.id == candidate_id,
            models.PermanentPlacementCandidate.nanny_id == nanny.id,
        )
        .first()
    )
    if candidate is None:
        raise HTTPException(status_code=404, detail="Permanent trial request not found")
    if candidate.trial_status != "pending":
        raise HTTPException(status_code=409, detail="This trial request is not awaiting a response")
    placement = (
        db.query(models.PermanentPlacement)
        .filter(models.PermanentPlacement.id == candidate.placement_id)
        .first()
    )
    if placement is None:
        raise HTTPException(status_code=404, detail="Permanent placement not found")
    candidate.trial_status = payload.decision
    candidate.trial_responded_at = utc_now()
    candidate.admin_notes = (payload.note or candidate.admin_notes or "").strip() or None
    if payload.decision == "accepted":
        candidate.status = "trial"
        placement.status = "trial"
    elif payload.decision == "declined":
        candidate.status = "interviewed"
    else:
        alternative = _naive_datetime(payload.alternative_at)
        if alternative <= utc_now():
            raise HTTPException(status_code=422, detail="Suggest a future trial date and time")
        candidate.trial_alternative_at = alternative
        candidate.status = "trial_change_requested"
    _activity(
        db,
        placement.id,
        user.id,
        f"trial_{payload.decision}",
        {
            "candidate_id": candidate.id,
            "alternative_at": candidate.trial_alternative_at,
            "note": payload.note,
        },
    )
    db.commit()
    log_audit(
        db,
        actor_user=user,
        target_user_id=placement.parent_user_id,
        entity="permanent_placement_candidates",
        entity_id=candidate.id,
        action=f"trial_{payload.decision}",
        request=request,
    )
    _notify_after_commit(
        db,
        placement.parent_user_id,
        "permanent_trial_response",
        f"The nanny {payload.decision.replace('_', ' ')} the proposed paid trial.",
        candidate.id,
    )
    _notify_admins(
        db,
        "permanent_trial_response",
        f"Candidate {candidate.id} {payload.decision.replace('_', ' ')} the trial for placement #{placement.id}.",
        placement.id,
    )
    return {"ok": True, "status": candidate.status, "trial_status": candidate.trial_status}


@router.post("/nannies/me/permanent-opportunities/{candidate_id}/offer-response")
def respond_to_permanent_offer(
    candidate_id: int,
    payload: OfferResponsePayload,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    user, nanny = _require_nanny(authorization, db)
    candidate = (
        db.query(models.PermanentPlacementCandidate)
        .filter(
            models.PermanentPlacementCandidate.id == candidate_id,
            models.PermanentPlacementCandidate.nanny_id == nanny.id,
        )
        .first()
    )
    if candidate is None:
        raise HTTPException(status_code=404, detail="Permanent offer not found")
    placement = (
        db.query(models.PermanentPlacement)
        .filter(models.PermanentPlacement.id == candidate.placement_id)
        .with_for_update()
        .first()
    )
    if placement is None:
        raise HTTPException(status_code=404, detail="Permanent placement not found")
    if candidate.offer_status != "pending":
        raise HTTPException(status_code=409, detail="This offer is not awaiting a response")
    note = (payload.note or "").strip() or None
    if payload.decision == "admin_support" and not note:
        raise HTTPException(status_code=422, detail="Tell My Nanny what you would like to discuss")

    candidate.offer_status = payload.decision
    candidate.offer_responded_at = utc_now()
    candidate.admin_notes = note or candidate.admin_notes
    blocked_days = 0
    if payload.decision == "accepted":
        try:
            blocked_days = _block_permanent_working_days(db, placement, candidate)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        candidate.availability_restructured_at = utc_now()
        candidate.status = "hired"
        placement.placed_nanny_id = candidate.nanny_id
        placement.hired_at = utc_now()
        replacement_hire = (
            placement.replacement_status == "approved"
            and paid_fee(db, placement.id, "success") is not None
        )
        if replacement_hire:
            placement.status = "placed"
            placement.replacement_status = "completed"
            placement.replacement_resolved_at = utc_now()
        else:
            placement.status = "awaiting_success_fee"
            placement.success_fee_due_at = utc_now()
            get_or_create_payment(db, placement, "success")
        profile = (
            db.query(models.NannyProfile)
            .filter(models.NannyProfile.nanny_id == candidate.nanny_id)
            .first()
        )
        if profile is not None:
            profile.current_job_availability = "piece_and_permanent"
        user.is_active = True
    elif payload.decision == "declined":
        candidate.status = "interviewed"
    else:
        candidate.status = "offer_admin_support"

    _activity(
        db,
        placement.id,
        user.id,
        f"offer_{payload.decision}",
        {"candidate_id": candidate.id, "note": note, "blocked_calendar_days": blocked_days},
    )
    db.commit()
    log_audit(
        db,
        actor_user=user,
        target_user_id=placement.parent_user_id,
        entity="permanent_placement_candidates",
        entity_id=candidate.id,
        action=f"offer_{payload.decision}",
        after_obj={"status": candidate.status, "blocked_calendar_days": blocked_days},
        request=request,
    )
    _notify_after_commit(
        db,
        placement.parent_user_id,
        "permanent_offer_response",
        (
            "The nanny accepted your offer. The successful-placement payment is now ready, and her short-term calendar has been updated around the agreed working schedule."
            if payload.decision == "accepted"
            else f"The nanny selected {payload.decision.replace('_', ' ')} on your permanent offer. My Nanny will support the next step."
        ),
        candidate.id,
    )
    _notify_admins(
        db,
        "permanent_offer_response",
        f"Candidate {candidate.id} selected {payload.decision.replace('_', ' ')} on the offer for placement #{placement.id}.",
        placement.id,
    )
    return {
        "ok": True,
        "status": candidate.status,
        "offer_status": candidate.offer_status,
        "placement_status": placement.status,
        "blocked_calendar_days": blocked_days,
    }


@router.get("/permanent-placements/candidates/{candidate_id}/communication")
def get_permanent_candidate_communication(
    candidate_id: int,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _require_user(authorization, db)
    candidate, placement, parent_user, nanny_user, role = _communication_parties(
        db, candidate_id, user
    )
    return _communication_dict(
        db, candidate, placement, parent_user, nanny_user, role
    )


@router.post("/permanent-placements/candidates/{candidate_id}/contact-terms")
def accept_permanent_candidate_contact_terms(
    candidate_id: int,
    payload: ContactTermsPayload,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _require_user(authorization, db)
    candidate, placement, parent_user, nanny_user, role = _communication_parties(
        db, candidate_id, user
    )
    if role not in {"parent", "nanny"}:
        raise HTTPException(status_code=403, detail="Only the family or nanny may accept these terms")
    if not payload.accepted:
        raise HTTPException(status_code=422, detail="Accept the interview communication terms to continue")
    if not _contact_window_open(candidate):
        raise HTTPException(
            status_code=409,
            detail="Temporary contact access is not available for this interview",
        )
    now = utc_now()
    if role == "parent":
        candidate.parent_contact_terms_accepted_at = (
            candidate.parent_contact_terms_accepted_at or now
        )
        recipient_id = nanny_user.id
    else:
        candidate.nanny_contact_terms_accepted_at = (
            candidate.nanny_contact_terms_accepted_at or now
        )
        recipient_id = parent_user.id
    _activity(
        db,
        placement.id,
        user.id,
        f"{role}_contact_terms_accepted",
        {"candidate_id": candidate.id},
    )
    db.commit()
    log_audit(
        db,
        actor_user=user,
        target_user_id=user.id,
        entity="permanent_placement_candidates",
        entity_id=candidate.id,
        action=f"{role}_contact_terms_accepted",
        request=request,
    )
    _notify_after_commit(
        db,
        recipient_id,
        "permanent_contact_terms",
        (
            "Interview communication is ready. Both parties accepted the temporary contact rules."
            if _contact_terms_complete(candidate)
            else "The other party accepted the temporary interview contact rules. Review and accept them in Permanent Placements when ready."
        ),
        candidate.id,
    )
    return _communication_dict(
        db, candidate, placement, parent_user, nanny_user, role
    )


@router.post("/permanent-placements/candidates/{candidate_id}/messages")
def send_permanent_candidate_message(
    candidate_id: int,
    payload: PermanentMessagePayload,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _require_user(authorization, db)
    candidate, placement, parent_user, nanny_user, role = _communication_parties(
        db, candidate_id, user
    )
    if role not in {"parent", "nanny"}:
        raise HTTPException(status_code=403, detail="Admin supports this conversation through the placement case")
    if not _contact_window_open(candidate):
        raise HTTPException(
            status_code=409,
            detail="Direct chat closed when the interview began. Ask My Nanny for support.",
        )
    if not _contact_terms_complete(candidate):
        raise HTTPException(
            status_code=409,
            detail="Both parties must accept the temporary interview communication terms first",
        )
    body = payload.body.strip()
    if not body:
        raise HTTPException(status_code=422, detail="Message body is required")
    message = models.PermanentPlacementMessage(
        placement_id=placement.id,
        candidate_id=candidate.id,
        sender_user_id=user.id,
        body=body,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    log_audit(
        db,
        actor_user=user,
        target_user_id=(nanny_user.id if role == "parent" else parent_user.id),
        entity="permanent_placement_messages",
        entity_id=message.id,
        action="message_sent",
        after_obj={"placement_id": placement.id, "candidate_id": candidate.id},
        request=request,
    )
    _notify_after_commit(
        db,
        nanny_user.id if role == "parent" else parent_user.id,
        "permanent_interview_message",
        "You have a new interview-arrangement message in Permanent Placements.",
        candidate.id,
    )
    return _communication_dict(
        db, candidate, placement, parent_user, nanny_user, role
    )


@router.get("/admin/permanent-placements/settings")
def get_admin_placement_settings(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    require_admin(authorization, db)
    return {"enabled": placement_feature_enabled(db), "pricing": pricing_payload(db)}


@router.get("/admin/billing/settings")
def get_admin_billing_settings(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    require_admin(authorization, db)
    return billing_settings_payload(db)


@router.put("/admin/billing/settings")
def update_admin_billing_settings(
    payload: BillingSettingsPayload,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    admin = require_admin(authorization, db)
    settings = get_or_create_billing_settings(db)
    updates = payload.model_dump(exclude_unset=True)
    tax_status_confirmed = updates.pop("tax_status_confirmed", None)
    text_fields = {
        "issuer_legal_name",
        "issuer_trading_name",
        "issuer_email",
        "issuer_phone",
        "issuer_address",
        "issuer_registration_number",
        "issuer_vat_number",
        "invoice_prefix",
    }
    for field_name, value in updates.items():
        if field_name in text_fields and isinstance(value, str):
            value = value.strip() or None
        setattr(settings, field_name, value)
    if tax_status_confirmed is not None:
        settings.tax_status_confirmed_at = utc_now() if tax_status_confirmed else None
    settings.updated_by_user_id = admin.id
    if settings.vat_registered and not (settings.issuer_vat_number or "").strip():
        raise HTTPException(status_code=422, detail="Enter the VAT number before confirming VAT registration")
    if settings.vat_registered and settings.prices_include_vat is not True:
        raise HTTPException(status_code=422, detail="Confirm that the configured customer fees include VAT")
    db.commit()
    log_audit(
        db,
        actor_user=admin,
        target_user_id=admin.id,
        entity="billing_settings",
        entity_id=settings.id,
        action="update",
        after_obj={"fields": sorted(payload.model_dump(exclude_unset=True))},
        request=request,
    )
    return billing_settings_payload(db)


@router.post("/admin/invoices/{invoice_id}/issue")
def issue_or_resend_invoice(
    invoice_id: int,
    payload: InvoiceIssuePayload,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    admin = require_admin(authorization, db)
    readiness = billing_settings_payload(db)
    if not readiness["ready_to_issue"]:
        raise HTTPException(
            status_code=409,
            detail="Complete billing setup first: " + ", ".join(readiness["missing"]),
        )
    invoice = db.query(models.Invoice).filter(models.Invoice.id == invoice_id).first()
    if invoice is None or invoice.permanent_payment_id is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    payment = (
        db.query(models.PermanentPlacementPayment)
        .filter(models.PermanentPlacementPayment.id == invoice.permanent_payment_id)
        .first()
    )
    if payment is None:
        raise HTTPException(status_code=404, detail="Invoice payment not found")
    invoice, invoice_created, receipt_created = sync_invoice_for_payment(db, payment)
    if payload.send_email:
        invoice.invoice_email_requested_at = utc_now()
        if invoice.receipt_pdf_url:
            invoice.receipt_email_requested_at = utc_now()
    db.commit()
    log_audit(
        db,
        actor_user=admin,
        target_user_id=invoice.parent_user_id,
        entity="invoices",
        entity_id=invoice.id,
        action="issue" if invoice_created else "resend",
        after_obj={"invoice_created": invoice_created, "receipt_created": receipt_created},
        request=request,
    )
    if payload.send_email:
        _notify_after_commit(
            db,
            invoice.parent_user_id,
            "permanent_invoice_issued",
            _document_ready_message("Invoice", invoice.invoice_number),
            invoice.id,
        )
        if invoice.receipt_pdf_url:
            _notify_after_commit(
                db,
                invoice.parent_user_id,
                "permanent_receipt_ready",
                _document_ready_message("Receipt", invoice.receipt_number),
                invoice.id,
            )
    return invoice_payload(invoice)


@router.put("/admin/permanent-placements/settings")
def update_admin_placement_settings(
    payload: AdminPlacementSettingsPayload,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    admin = require_admin(authorization, db)
    row = db.query(models.AppSettings).filter(models.AppSettings.id == 1).first()
    if row is None:
        row = models.AppSettings(id=1)
        db.add(row)
    settings_row = get_or_create_permanent_settings(db)
    changes = payload.model_dump(exclude_unset=True)
    before = {
        "enabled": bool(getattr(row, "permanent_placements_enabled", False)),
        "pricing": pricing_payload(db),
    }
    if "enabled" in changes:
        row.permanent_placements_enabled = bool(changes.pop("enabled"))

    editable_fields = {
        "self_match_activation_fee_cents",
        "self_match_interview_package_fee_cents",
        "self_match_placement_fee_cents",
        "activation_fee_credits_toward_package",
        "concierge_consultation_fee_cents",
        "concierge_engagement_fee_cents",
        "concierge_success_balance_cents",
        "self_match_profile_limit",
        "self_match_interview_limit",
        "concierge_interview_limit",
        "candidate_access_days",
        "replacement_period_days",
        "replacement_credit_count",
        "replacement_max_count",
        "maybe_period_days",
    }
    for field_name, value in changes.items():
        if field_name in editable_fields:
            setattr(settings_row, field_name, value)

    if (
        settings_row.activation_fee_credits_toward_package
        and settings_row.self_match_interview_package_fee_cents
        < settings_row.self_match_activation_fee_cents
    ):
        raise HTTPException(
            status_code=422,
            detail="The Self-Match interview package cannot be less than the activation fee when the activation fee is credited.",
        )
    settings_row.updated_by_user_id = admin.id
    db.commit()
    result = {
        "enabled": bool(row.permanent_placements_enabled),
        "pricing": pricing_payload(db),
    }
    log_audit(
        db,
        actor_user=admin,
        target_user_id=None,
        entity="app_settings",
        entity_id=1,
        action="permanent_placement_settings_update",
        before_obj=before,
        after_obj=result,
        request=request,
    )
    return result


@router.get("/admin/permanent-placements/overview")
def admin_placement_overview(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    require_admin(authorization, db)
    rows = (
        db.query(models.PermanentPlacement)
        .order_by(models.PermanentPlacement.created_at.desc())
        .all()
    )
    active_statuses = {"brief_submitted", "awaiting_candidate_access", "awaiting_engagement_payment", "search_active", "interviewing", "trial", "awaiting_success_fee"}
    payments = db.query(models.PermanentPlacementPayment).all()
    return {
        "enabled": placement_feature_enabled(db),
        "pricing": pricing_payload(db),
        "metrics": {
            "total": len(rows),
            "active": sum(1 for row in rows if row.status in active_statuses),
            "awaiting_payment": sum(1 for row in rows if row.status in {"awaiting_initial_payment", "awaiting_candidate_access", "awaiting_engagement_payment", "awaiting_success_fee"}),
            "interviewing": sum(1 for row in rows if row.status in {"interviewing", "trial"}),
            "placed": sum(1 for row in rows if row.status == "placed"),
            "revenue_cents": sum(row.amount_cents for row in payments if row.status == "paid"),
        },
        "results": [_placement_dict(db, row, admin=True) for row in rows],
    }


@router.get("/admin/permanent-placements/eligible-nannies")
def admin_eligible_permanent_nannies(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    require_admin(authorization, db)
    preferences = (
        db.query(models.PermanentPlacementPreference)
        .filter(models.PermanentPlacementPreference.opted_in.is_(True))
        .all()
    )
    results = []
    for preference in preferences:
        nanny = db.query(models.Nanny).filter(models.Nanny.id == preference.nanny_id).first()
        if not nanny or not nanny.approved or nanny.is_suspended:
            continue
        user = db.query(models.User).filter(models.User.id == nanny.user_id).first()
        profile = db.query(models.NannyProfile).filter(models.NannyProfile.nanny_id == nanny.id).first()
        results.append(
            {
                "nanny_id": nanny.id,
                "name": getattr(user, "name", None),
                "email": getattr(user, "email", None),
                "phone": getattr(user, "phone", None),
                "location": ", ".join(
                    item for item in [getattr(profile, "suburb", None), getattr(profile, "city", None)] if item
                ),
                **_preference_dict(preference),
            }
        )
    return {"results": results}


@router.get("/admin/permanent-placements/{placement_id}")
def admin_placement_detail(
    placement_id: int,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    require_admin(authorization, db)
    placement = db.query(models.PermanentPlacement).filter(models.PermanentPlacement.id == placement_id).first()
    if placement is None:
        raise HTTPException(status_code=404, detail="Permanent placement not found")
    result = _placement_dict(db, placement, include_candidates=True, admin=True)
    activities = (
        db.query(models.PermanentPlacementActivity)
        .filter(models.PermanentPlacementActivity.placement_id == placement.id)
        .order_by(models.PermanentPlacementActivity.created_at.desc())
        .all()
    )
    result["activities"] = [
        {
            "id": row.id,
            "event_type": row.event_type,
            "details": _json_load(row.details_json, {}),
            "actor_user_id": row.actor_user_id,
            "created_at": row.created_at,
        }
        for row in activities
    ]
    return result


@router.post("/admin/permanent-placements/{placement_id}/qualify")
def admin_qualify_placement(
    placement_id: int,
    payload: AdminNotesPayload,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    admin = require_admin(authorization, db)
    placement = db.query(models.PermanentPlacement).filter(models.PermanentPlacement.id == placement_id).first()
    if placement is None:
        raise HTTPException(status_code=404, detail="Permanent placement not found")
    initial_fee = initial_fee_type(placement)
    if not paid_fee(db, placement.id, initial_fee):
        raise HTTPException(status_code=409, detail="The opening fee must be paid before qualification")
    placement.admin_notes = (payload.note or "").strip() or placement.admin_notes
    placement.status = "awaiting_candidate_access" if placement.service_tier == "self_match" else "awaiting_engagement_payment"
    if placement.service_tier == "self_match":
        get_or_create_payment(db, placement, "candidate_access")
    else:
        get_or_create_payment(db, placement, "engagement")
    _activity(db, placement.id, admin.id, "brief_qualified", {"status": placement.status})
    db.commit()
    log_audit(
        db,
        actor_user=admin,
        target_user_id=placement.parent_user_id,
        entity="permanent_placements",
        entity_id=placement.id,
        action="qualify",
        after_obj={"status": placement.status},
        request=request,
    )
    message = (
        "Your permanent-placement brief is approved. Complete candidate access to begin reviewing profiles."
        if placement.service_tier == "self_match"
        else "Your Concierge brief is approved. Complete the engagement payment so our placement team can begin the managed search."
    )
    _notify_after_commit(db, placement.parent_user_id, "permanent_brief_qualified", message, placement.id)
    return _placement_dict(db, placement, include_candidates=True, admin=True)


@router.post("/admin/permanent-placements/{placement_id}/candidates")
def admin_invite_placement_candidate(
    placement_id: int,
    payload: AdminCandidateInvitePayload,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    admin = require_admin(authorization, db)
    placement = db.query(models.PermanentPlacement).filter(models.PermanentPlacement.id == placement_id).first()
    if placement is None:
        raise HTTPException(status_code=404, detail="Permanent placement not found")
    if placement.status not in {"search_active", "interviewing", "trial"}:
        raise HTTPException(status_code=409, detail="The placement search is not active")
    nanny = db.query(models.Nanny).filter(models.Nanny.id == payload.nanny_id).first()
    preference = (
        db.query(models.PermanentPlacementPreference)
        .filter(
            models.PermanentPlacementPreference.nanny_id == payload.nanny_id,
            models.PermanentPlacementPreference.opted_in.is_(True),
        )
        .first()
    )
    if not nanny or not nanny.approved or nanny.is_suspended or preference is None:
        raise HTTPException(status_code=409, detail="Only approved, opted-in nannies can be invited")
    candidate = models.PermanentPlacementCandidate(
        placement_id=placement.id,
        nanny_id=nanny.id,
        status="invited",
        consent_status="pending",
        admin_notes=(payload.note or "").strip() or None,
    )
    db.add(candidate)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="This nanny has already been invited")
    _activity(db, placement.id, admin.id, "candidate_invited", {"candidate_id": candidate.id, "nanny_id": nanny.id})
    db.commit()
    log_audit(
        db,
        actor_user=admin,
        target_user_id=nanny.user_id,
        entity="permanent_placement_candidates",
        entity_id=candidate.id,
        action="invite",
        request=request,
    )
    _notify_after_commit(
        db,
        nanny.user_id,
        "permanent_opportunity_invitation",
        f"A family in {placement.location_suburb} is interested in your permanent-placement profile. Review the opportunity and choose whether to share your profile.",
        candidate.id,
    )
    return _candidate_profile(db, candidate, admin=True)


@router.post("/admin/permanent-placements/{placement_id}/replacement")
def admin_decide_placement_replacement(
    placement_id: int,
    payload: ReplacementDecisionPayload,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    admin = require_admin(authorization, db)
    placement = db.query(models.PermanentPlacement).filter(models.PermanentPlacement.id == placement_id).first()
    if placement is None:
        raise HTTPException(status_code=404, detail="Permanent placement not found")
    if payload.decision in {"approved", "declined"} and placement.replacement_status != "requested":
        raise HTTPException(status_code=409, detail="There is no replacement request awaiting a decision")
    if payload.decision == "completed" and placement.replacement_status != "approved":
        raise HTTPException(status_code=409, detail="Approve the replacement before completing it")
    placement.replacement_status = payload.decision
    placement.admin_notes = payload.note.strip()
    placement.replacement_resolved_by = admin.id
    if payload.decision == "approved":
        replacement_limit = int(
            pricing_payload(db, placement)["self_match"]["replacement_max_count"]
        )
        if int(placement.replacement_count or 0) >= replacement_limit:
            raise HTTPException(status_code=409, detail="The included replacement has already been used")
        placement.replacement_count = int(placement.replacement_count or 0) + 1
        placement.interview_credit_cycle = int(placement.interview_credit_cycle or 0) + 1
        placement.status = "search_active"
    else:
        placement.replacement_resolved_at = utc_now()
        if payload.decision == "declined":
            placement.status = "placed"
    _activity(
        db,
        placement.id,
        admin.id,
        f"replacement_{payload.decision}",
        {
            "note": payload.note.strip(),
            "replacement_count": int(placement.replacement_count or 0),
            "interview_credits": interview_credit_summary(db, placement),
        },
    )
    db.commit()
    log_audit(
        db,
        actor_user=admin,
        target_user_id=placement.parent_user_id,
        entity="permanent_placements",
        entity_id=placement.id,
        action=f"replacement_{payload.decision}",
        request=request,
    )
    _notify_after_commit(
        db,
        placement.parent_user_id,
        "permanent_replacement_updated",
        f"Your permanent-placement replacement request has been {payload.decision}.",
        placement.id,
    )
    return _placement_dict(db, placement, include_candidates=True, admin=True)


@router.post("/admin/permanent-placements/{placement_id}/candidates/{candidate_id}/release")
def admin_release_candidate_profile(
    placement_id: int,
    candidate_id: int,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    admin = require_admin(authorization, db)
    placement = db.query(models.PermanentPlacement).filter(models.PermanentPlacement.id == placement_id).first()
    candidate = (
        db.query(models.PermanentPlacementCandidate)
        .filter(
            models.PermanentPlacementCandidate.id == candidate_id,
            models.PermanentPlacementCandidate.placement_id == placement_id,
        )
        .first()
    )
    if not placement or not candidate:
        raise HTTPException(status_code=404, detail="Permanent placement candidate not found")
    if candidate.consent_status != "accepted":
        raise HTTPException(status_code=409, detail="The nanny must consent before the profile is released")
    if placement.service_tier == "self_match":
        released_count = (
            db.query(func.count(models.PermanentPlacementCandidate.id))
            .filter(
                models.PermanentPlacementCandidate.placement_id == placement.id,
                models.PermanentPlacementCandidate.profile_released_at.isnot(None),
                models.PermanentPlacementCandidate.id != candidate.id,
            )
            .scalar()
            or 0
        )
        profile_limit = int(pricing_payload(db, placement)["self_match"]["profile_limit"])
        if released_count >= profile_limit:
            raise HTTPException(
                status_code=409,
                detail=f"Self-Match includes up to {profile_limit} released profiles",
            )
    now = utc_now()
    candidate.status = "released"
    candidate.profile_released_at = candidate.profile_released_at or now
    candidate.introduction_expires_at = None
    _activity(db, placement.id, admin.id, "candidate_profile_released", {"candidate_id": candidate.id})
    db.commit()
    log_audit(
        db,
        actor_user=admin,
        target_user_id=placement.parent_user_id,
        entity="permanent_placement_candidates",
        entity_id=candidate.id,
        action="profile_release",
        request=request,
    )
    _notify_after_commit(
        db,
        placement.parent_user_id,
        "permanent_candidate_released",
        f"A new candidate profile is ready to review for permanent placement #{placement.id}.",
        placement.id,
    )
    return _candidate_profile(db, candidate, admin=True)


@router.post("/admin/permanent-placements/{placement_id}/candidates/{candidate_id}/schedule-interview")
def admin_schedule_candidate_interview(
    placement_id: int,
    candidate_id: int,
    payload: InterviewSchedulePayload,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    admin = require_admin(authorization, db)
    placement = db.query(models.PermanentPlacement).filter(models.PermanentPlacement.id == placement_id).first()
    candidate = (
        db.query(models.PermanentPlacementCandidate)
        .filter(
            models.PermanentPlacementCandidate.id == candidate_id,
            models.PermanentPlacementCandidate.placement_id == placement_id,
        )
        .first()
    )
    if not placement or not candidate:
        raise HTTPException(status_code=404, detail="Permanent placement candidate not found")
    if candidate.consent_status != "accepted" or candidate.profile_released_at is None:
        raise HTTPException(status_code=409, detail="Release the consented profile before scheduling an interview")
    if (
        candidate.interview_invite_status != "accepted"
        or candidate.interview_credit_restored_at is not None
        or int(candidate.interview_credit_cycle or 0)
        != int(placement.interview_credit_cycle or 0)
    ):
        raise HTTPException(
            status_code=409,
            detail="The nanny must accept the current interview invitation before it can be scheduled",
        )
    candidate.status = "interview_scheduled"
    candidate.interview_scheduled_at = payload.scheduled_at.replace(tzinfo=None) if payload.scheduled_at.tzinfo else payload.scheduled_at
    candidate.interview_format = payload.interview_format
    candidate.interview_location = (payload.interview_location or "").strip() or None
    candidate.admin_notes = (payload.note or candidate.admin_notes or "").strip() or None
    placement.status = "interviewing"
    _activity(db, placement.id, admin.id, "interview_scheduled", {"candidate_id": candidate.id, "scheduled_at": candidate.interview_scheduled_at})
    db.commit()
    log_audit(
        db,
        actor_user=admin,
        target_user_id=placement.parent_user_id,
        entity="permanent_placement_candidates",
        entity_id=candidate.id,
        action="schedule_interview",
        request=request,
    )
    nanny = db.query(models.Nanny).filter(models.Nanny.id == candidate.nanny_id).first()
    _notify_after_commit(
        db,
        placement.parent_user_id,
        "permanent_interview_scheduled",
        f"Your permanent-placement interview is scheduled for {candidate.interview_scheduled_at.strftime('%d %b %Y at %H:%M')}.",
        candidate.id,
    )
    _notify_after_commit(
        db,
        getattr(nanny, "user_id", None),
        "permanent_interview_scheduled",
        f"Your permanent-placement interview is scheduled for {candidate.interview_scheduled_at.strftime('%d %b %Y at %H:%M')}.",
        candidate.id,
    )
    return _candidate_profile(db, candidate, admin=True)


@router.post("/admin/permanent-placements/{placement_id}/candidates/{candidate_id}/interview-outcome")
def admin_record_interview_outcome(
    placement_id: int,
    candidate_id: int,
    payload: AdminInterviewOutcomePayload,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    admin = require_admin(authorization, db)
    placement = (
        db.query(models.PermanentPlacement)
        .filter(models.PermanentPlacement.id == placement_id)
        .with_for_update()
        .first()
    )
    candidate = (
        db.query(models.PermanentPlacementCandidate)
        .filter(
            models.PermanentPlacementCandidate.id == candidate_id,
            models.PermanentPlacementCandidate.placement_id == placement_id,
        )
        .first()
    )
    if not placement or not candidate:
        raise HTTPException(status_code=404, detail="Permanent placement candidate not found")
    if candidate.interview_invite_status != "accepted":
        raise HTTPException(status_code=409, detail="Only an accepted interview can restore a credit")
    try:
        credits = restore_interview_credit(
            db,
            placement,
            candidate,
            actor_user_id=admin.id,
            event_type=payload.outcome,
            reason=payload.reason.strip(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    candidate.interview_invite_status = payload.outcome
    candidate.status = "released"
    candidate.admin_notes = payload.reason.strip()
    placement.status = "search_active"
    _activity(
        db,
        placement.id,
        admin.id,
        f"interview_{payload.outcome}",
        {"candidate_id": candidate.id, "reason": payload.reason.strip(), "credits": credits},
    )
    db.commit()
    log_audit(
        db,
        actor_user=admin,
        target_user_id=placement.parent_user_id,
        entity="permanent_placement_candidates",
        entity_id=candidate.id,
        action=f"interview_{payload.outcome}",
        after_obj={"credits": credits},
        request=request,
    )
    _notify_after_commit(
        db,
        placement.parent_user_id,
        "permanent_interview_credit_restored",
        "The interview was recorded as cancelled or not held, and the interview credit was restored.",
        candidate.id,
    )
    nanny = db.query(models.Nanny).filter(models.Nanny.id == candidate.nanny_id).first()
    _notify_after_commit(
        db,
        getattr(nanny, "user_id", None),
        "permanent_interview_updated",
        "The placement team recorded that the interview did not take place.",
        candidate.id,
    )
    return _placement_dict(db, placement, include_candidates=True, admin=True)


@router.post("/admin/permanent-placements/{placement_id}/candidates/{candidate_id}/stage")
def admin_update_candidate_stage(
    placement_id: int,
    candidate_id: int,
    payload: CandidateStagePayload,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    admin = require_admin(authorization, db)
    placement = db.query(models.PermanentPlacement).filter(models.PermanentPlacement.id == placement_id).first()
    candidate = (
        db.query(models.PermanentPlacementCandidate)
        .filter(
            models.PermanentPlacementCandidate.id == candidate_id,
            models.PermanentPlacementCandidate.placement_id == placement_id,
        )
        .first()
    )
    if not placement or not candidate:
        raise HTTPException(status_code=404, detail="Permanent placement candidate not found")
    if payload.status == "released" and candidate.consent_status != "accepted":
        raise HTTPException(status_code=409, detail="The nanny must consent before profile release")
    candidate.status = payload.status
    candidate.admin_notes = (payload.note or candidate.admin_notes or "").strip() or None
    if payload.status == "trial":
        candidate.trial_scheduled_at = payload.trial_scheduled_at
        candidate.trial_notes = (payload.note or "").strip() or candidate.trial_notes
        placement.status = "trial"
    _activity(db, placement.id, admin.id, f"candidate_{payload.status}", {"candidate_id": candidate.id})
    db.commit()
    log_audit(
        db,
        actor_user=admin,
        target_user_id=placement.parent_user_id,
        entity="permanent_placement_candidates",
        entity_id=candidate.id,
        action=f"stage_{payload.status}",
        request=request,
    )
    return _candidate_profile(db, candidate, admin=True)


@router.post("/admin/permanent-placements/{placement_id}/candidates/{candidate_id}/hire")
def admin_mark_candidate_hired(
    placement_id: int,
    candidate_id: int,
    payload: AdminNotesPayload,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    admin = require_admin(authorization, db)
    placement = db.query(models.PermanentPlacement).filter(models.PermanentPlacement.id == placement_id).first()
    candidate = (
        db.query(models.PermanentPlacementCandidate)
        .filter(
            models.PermanentPlacementCandidate.id == candidate_id,
            models.PermanentPlacementCandidate.placement_id == placement_id,
        )
        .first()
    )
    if not placement or not candidate:
        raise HTTPException(status_code=404, detail="Permanent placement candidate not found")
    if candidate.consent_status != "accepted" or candidate.profile_released_at is None:
        raise HTTPException(status_code=409, detail="Only a consented, introduced candidate can be hired")
    now = utc_now()
    candidate.status = "hired"
    candidate.admin_notes = (payload.note or candidate.admin_notes or "").strip() or None
    placement.placed_nanny_id = candidate.nanny_id
    placement.hired_at = now
    replacement_hire = placement.replacement_status == "approved" and paid_fee(db, placement.id, "success")
    if replacement_hire:
        placement.status = "placed"
        placement.replacement_status = "completed"
        placement.replacement_resolved_at = now
        placement.replacement_resolved_by = admin.id
    else:
        placement.success_fee_due_at = now
        placement.status = "awaiting_success_fee"
        get_or_create_payment(db, placement, "success")
    other_candidates = (
        db.query(models.PermanentPlacementCandidate)
        .filter(
            models.PermanentPlacementCandidate.placement_id == placement.id,
            models.PermanentPlacementCandidate.id != candidate.id,
            models.PermanentPlacementCandidate.status.notin_(["declined", "withdrawn"]),
        )
        .all()
    )
    for other in other_candidates:
        other.status = "not_selected"
    _activity(db, placement.id, admin.id, "candidate_hired", {"candidate_id": candidate.id, "nanny_id": candidate.nanny_id})
    db.commit()
    log_audit(
        db,
        actor_user=admin,
        target_user_id=placement.parent_user_id,
        entity="permanent_placements",
        entity_id=placement.id,
        action="candidate_hired",
        after_obj={"nanny_id": candidate.nanny_id, "status": placement.status},
        request=request,
    )
    nanny = db.query(models.Nanny).filter(models.Nanny.id == candidate.nanny_id).first()
    _notify_after_commit(
        db,
        placement.parent_user_id,
        "permanent_replacement_updated" if replacement_hire else "permanent_success_fee_due",
        (
            "Your replacement nanny has been recorded and the replacement process is complete."
            if replacement_hire
            else "Your selected nanny has been recorded. Complete the successful-placement fee to activate the onboarding pack and placement support."
        ),
        placement.id,
    )
    _notify_after_commit(
        db,
        getattr(nanny, "user_id", None),
        "permanent_candidate_hired",
        "The family has selected you for their permanent nanny role. My Nanny will contact you about onboarding.",
        placement.id,
    )
    return _placement_dict(db, placement, include_candidates=True, admin=True)


@router.post("/admin/permanent-placements/{placement_id}/payments/mark-paid")
def admin_mark_placement_payment_paid(
    placement_id: int,
    payload: ManualPaymentPayload,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    admin = require_admin(authorization, db)
    placement = db.query(models.PermanentPlacement).filter(models.PermanentPlacement.id == placement_id).first()
    if placement is None:
        raise HTTPException(status_code=404, detail="Permanent placement not found")
    _validate_fee_due(db, placement, payload.fee_type)
    payment = get_or_create_payment(db, placement, payload.fee_type)
    if payment.status == "paid":
        raise HTTPException(status_code=409, detail="This fee has already been recorded as paid")
    apply_paid_payment(db, payment, note=f"Admin recorded payment: {payload.reason}")
    invoice, invoice_created, receipt_created = sync_invoice_for_payment(db, payment)
    if invoice_created:
        invoice.invoice_email_requested_at = utc_now()
    if receipt_created:
        invoice.receipt_email_requested_at = utc_now()
    _activity(db, placement.id, admin.id, "fee_marked_paid", {"fee_type": payment.fee_type, "amount_cents": payment.amount_cents, "reason": payload.reason})
    db.commit()
    log_audit(
        db,
        actor_user=admin,
        target_user_id=placement.parent_user_id,
        entity="permanent_placement_payments",
        entity_id=payment.id,
        action="mark_paid",
        after_obj={"fee_type": payment.fee_type, "amount_cents": payment.amount_cents, "reason": payload.reason},
        request=request,
    )
    if invoice_created:
        _notify_after_commit(
            db,
            placement.parent_user_id,
            "permanent_invoice_issued",
            _document_ready_message("Invoice", invoice.invoice_number),
            invoice.id,
        )
    if receipt_created:
        _notify_after_commit(
            db,
            placement.parent_user_id,
            "permanent_receipt_ready",
            _document_ready_message("Receipt", invoice.receipt_number),
            invoice.id,
        )
    return _placement_dict(db, placement, include_candidates=True, admin=True)
