from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timedelta
from typing import Literal, Optional

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
from app.services.permanent_placements import (
    CANDIDATE_ACCESS_DAYS,
    CONCIERGE_INTERVIEW_LIMIT,
    INTRODUCTION_PROTECTION_DAYS,
    SELF_MATCH_INTERVIEW_LIMIT,
    SELF_MATCH_PROFILE_LIMIT,
    apply_paid_payment,
    fee_amount_cents,
    get_or_create_payment,
    initial_fee_type,
    paid_fee,
    placement_feature_enabled,
    pricing_payload,
)
from app.utils.time import utc_now


router = APIRouter(tags=["permanent placements"])


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


class CandidateNotePayload(BaseModel):
    note: Optional[str] = Field(default=None, max_length=2000)


class InterviewSchedulePayload(BaseModel):
    scheduled_at: datetime
    interview_format: Literal["video", "in_person", "telephone"]
    interview_location: Optional[str] = Field(default=None, max_length=1000)
    note: Optional[str] = Field(default=None, max_length=2000)


class CandidateStagePayload(BaseModel):
    status: Literal["released", "shortlisted", "interview_requested", "interviewed", "trial", "offered", "declined", "withdrawn"]
    trial_scheduled_at: Optional[datetime] = None
    note: Optional[str] = Field(default=None, max_length=2000)


class AdminPlacementSettingsPayload(BaseModel):
    enabled: bool


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
    fee_type: Literal["activation", "candidate_access", "application", "success"]
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
        "interview_format": candidate.interview_format,
        "trial_scheduled_at": candidate.trial_scheduled_at,
        "profile_released_at": candidate.profile_released_at,
        "introduction_expires_at": candidate.introduction_expires_at,
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
        "upgraded_from_self_match": bool(placement.upgraded_from_self_match),
        "payments": [_payment_dict(row) for row in payments],
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
    if candidate.introduction_expires_at and candidate.introduction_expires_at < utc_now():
        raise HTTPException(status_code=410, detail="Candidate introduction access has expired")
    return candidate


@router.get("/permanent-placements/config")
def permanent_placement_config(db: Session = Depends(get_db)):
    return {"enabled": placement_feature_enabled(db), "pricing": pricing_payload()}


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
    if paid_fee(db, placement.id, "activation") and placement.status in {
        "brief_submitted",
        "awaiting_candidate_access",
    }:
        placement.status = "search_active"
    _activity(db, placement.id, parent.id, "upgraded_to_concierge", {"candidate_access_credit_cents": 150000})
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
        raise HTTPException(status_code=409, detail="This placement does not have an active replacement or rematch period")
    if placement.guarantee_until < utc_now():
        raise HTTPException(status_code=409, detail="The replacement or rematch period has expired")
    if placement.replacement_status in {"requested", "approved"}:
        raise HTTPException(status_code=409, detail="A replacement request is already open")
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
        f"A replacement or rematch was requested for permanent placement #{placement.id}.",
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
    limit = SELF_MATCH_INTERVIEW_LIMIT if placement.service_tier == "self_match" else CONCIERGE_INTERVIEW_LIMIT
    shortlisted = (
        db.query(func.count(models.PermanentPlacementCandidate.id))
        .filter(
            models.PermanentPlacementCandidate.placement_id == placement.id,
            models.PermanentPlacementCandidate.status.in_(
                ["shortlisted", "interview_requested", "interview_scheduled", "interviewed", "trial", "offered", "hired"]
            ),
            models.PermanentPlacementCandidate.id != candidate.id,
        )
        .scalar()
        or 0
    )
    if shortlisted >= limit:
        raise HTTPException(status_code=409, detail=f"This service includes a shortlist of up to {limit} candidates")
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
    limit = SELF_MATCH_INTERVIEW_LIMIT if placement.service_tier == "self_match" else CONCIERGE_INTERVIEW_LIMIT
    interview_count = (
        db.query(func.count(models.PermanentPlacementCandidate.id))
        .filter(
            models.PermanentPlacementCandidate.placement_id == placement.id,
            models.PermanentPlacementCandidate.status.in_(
                ["interview_requested", "interview_scheduled", "interviewed", "trial", "offered", "hired"]
            ),
            models.PermanentPlacementCandidate.id != candidate.id,
        )
        .scalar()
        or 0
    )
    if interview_count >= limit:
        raise HTTPException(status_code=409, detail=f"This service includes up to {limit} interviews")
    candidate.status = "interview_requested"
    candidate.interview_requested_at = utc_now()
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
    return _placement_dict(db, placement, include_candidates=True)


def _validate_fee_due(db: Session, placement: models.PermanentPlacement, fee_type: str) -> None:
    expected = initial_fee_type(placement)
    if fee_type == expected and placement.status == "awaiting_initial_payment":
        return
    if fee_type == "candidate_access" and placement.service_tier == "self_match" and placement.status == "awaiting_candidate_access":
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
    db.commit()
    return {
        "authorization_url": data.get("authorization_url"),
        "access_code": data.get("access_code"),
        "reference": payment.paystack_reference,
        "amount_cents": payment.amount_cents,
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
    _activity(db, placement.id, parent.id, "fee_paid", {"fee_type": payment.fee_type, "amount_cents": payment.amount_cents})
    db.commit()
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
                "interview_format": candidate.interview_format,
                "interview_location": candidate.interview_location,
                "trial_scheduled_at": candidate.trial_scheduled_at,
                "trial_notes": candidate.trial_notes,
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


@router.get("/admin/permanent-placements/settings")
def get_admin_placement_settings(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    require_admin(authorization, db)
    return {"enabled": placement_feature_enabled(db), "pricing": pricing_payload()}


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
    before = bool(getattr(row, "permanent_placements_enabled", False))
    row.permanent_placements_enabled = payload.enabled
    db.commit()
    log_audit(
        db,
        actor_user=admin,
        target_user_id=None,
        entity="app_settings",
        entity_id=1,
        action="permanent_placements_toggle",
        before_obj={"enabled": before},
        after_obj={"enabled": payload.enabled},
        request=request,
    )
    return {"enabled": payload.enabled}


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
    active_statuses = {"brief_submitted", "awaiting_candidate_access", "search_active", "interviewing", "trial", "awaiting_success_fee"}
    payments = db.query(models.PermanentPlacementPayment).all()
    return {
        "enabled": placement_feature_enabled(db),
        "pricing": pricing_payload(),
        "metrics": {
            "total": len(rows),
            "active": sum(1 for row in rows if row.status in active_statuses),
            "awaiting_payment": sum(1 for row in rows if row.status in {"awaiting_initial_payment", "awaiting_candidate_access", "awaiting_success_fee"}),
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
    placement.status = "awaiting_candidate_access" if placement.service_tier == "self_match" else "search_active"
    if placement.service_tier == "self_match":
        get_or_create_payment(db, placement, "candidate_access")
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
        else "Your Concierge permanent-placement search is active. Our placement team will begin curating candidates."
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
        placement.status = "search_active"
    else:
        placement.replacement_resolved_at = utc_now()
        if payload.decision == "declined":
            placement.status = "placed"
    _activity(db, placement.id, admin.id, f"replacement_{payload.decision}", {"note": payload.note.strip()})
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
        if released_count >= SELF_MATCH_PROFILE_LIMIT:
            raise HTTPException(status_code=409, detail="Self-Match includes up to 10 released profiles")
    now = utc_now()
    candidate.status = "released"
    candidate.profile_released_at = candidate.profile_released_at or now
    candidate.introduction_expires_at = candidate.introduction_expires_at or now + timedelta(days=INTRODUCTION_PROTECTION_DAYS)
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
    if candidate.introduction_expires_at and candidate.introduction_expires_at < utc_now():
        raise HTTPException(status_code=409, detail="The protected introduction period has expired")
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
            "Your replacement nanny has been recorded and the rematch is complete."
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
    return _placement_dict(db, placement, include_candidates=True, admin=True)
