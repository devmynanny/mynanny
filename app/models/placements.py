from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from app.db import Base


class PermanentPlacement(Base):
    __tablename__ = "permanent_placements"

    id = Column(Integer, primary_key=True)
    parent_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    service_tier = Column(String(32), nullable=False)
    status = Column(String(40), nullable=False, default="awaiting_initial_payment", index=True)
    role_title = Column(String(160), nullable=False)
    employment_type = Column(String(40), nullable=False, default="full_time")
    start_date = Column(Date, nullable=True)
    schedule_summary = Column(Text, nullable=False)
    hours_per_week = Column(Integer, nullable=True)
    children_count = Column(Integer, nullable=False, default=1)
    children_ages_json = Column(Text, nullable=True)
    duties = Column(Text, nullable=False)
    special_requirements = Column(Text, nullable=True)
    salary_min_cents = Column(Integer, nullable=False)
    salary_max_cents = Column(Integer, nullable=False)
    location_suburb = Column(String(120), nullable=False)
    location_city = Column(String(120), nullable=False)
    location_province = Column(String(120), nullable=True)
    live_in = Column(Boolean, nullable=False, default=False)
    drivers_license_required = Column(Boolean, nullable=False, default=False)
    own_car_required = Column(Boolean, nullable=False, default=False)
    languages_json = Column(Text, nullable=True)
    pets = Column(Text, nullable=True)
    parent_notes = Column(Text, nullable=True)
    admin_notes = Column(Text, nullable=True)
    pricing_snapshot_json = Column(Text, nullable=True)
    candidate_access_expires_at = Column(DateTime, nullable=True)
    placed_nanny_id = Column(Integer, ForeignKey("nannies.id"), nullable=True)
    hired_at = Column(DateTime, nullable=True)
    success_fee_due_at = Column(DateTime, nullable=True)
    guarantee_until = Column(DateTime, nullable=True)
    replacement_status = Column(String(32), nullable=False, default="not_requested")
    replacement_requested_at = Column(DateTime, nullable=True)
    replacement_reason = Column(Text, nullable=True)
    replacement_resolved_at = Column(DateTime, nullable=True)
    replacement_resolved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    replacement_count = Column(Integer, nullable=False, default=0)
    interview_credit_cycle = Column(Integer, nullable=False, default=0)
    upgraded_from_self_match = Column(Boolean, nullable=False, default=False)
    closed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_permanent_placements_parent_status", "parent_user_id", "status"),
        Index("ix_permanent_placements_tier_status", "service_tier", "status"),
    )


class PermanentPlacementSettings(Base):
    """Current commercial terms for new permanent-placement cases.

    A case receives its own JSON snapshot when it is created, so editing these
    settings never changes a fee or entitlement already shown to a family.
    """

    __tablename__ = "permanent_placement_settings"

    id = Column(Integer, primary_key=True, default=1)
    currency = Column(String(3), nullable=False, default="ZAR")
    self_match_activation_fee_cents = Column(Integer, nullable=False, default=35_000)
    self_match_interview_package_fee_cents = Column(Integer, nullable=False, default=150_000)
    self_match_placement_fee_cents = Column(Integer, nullable=False, default=150_000)
    activation_fee_credits_toward_package = Column(Boolean, nullable=False, default=True)
    concierge_consultation_fee_cents = Column(Integer, nullable=False, default=55_000)
    concierge_engagement_fee_cents = Column(Integer, nullable=False, default=250_000)
    concierge_success_balance_cents = Column(Integer, nullable=False, default=700_000)
    self_match_profile_limit = Column(Integer, nullable=False, default=10)
    self_match_interview_limit = Column(Integer, nullable=False, default=5)
    concierge_interview_limit = Column(Integer, nullable=False, default=5)
    candidate_access_days = Column(Integer, nullable=False, default=30)
    replacement_period_days = Column(Integer, nullable=False, default=40)
    replacement_credit_count = Column(Integer, nullable=False, default=3)
    replacement_max_count = Column(Integer, nullable=False, default=1)
    maybe_period_days = Column(Integer, nullable=False, default=4)
    updated_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("self_match_activation_fee_cents >= 0", name="ck_perm_activation_fee_nonnegative"),
        CheckConstraint("self_match_interview_package_fee_cents >= 0", name="ck_perm_package_fee_nonnegative"),
        CheckConstraint("self_match_placement_fee_cents >= 0", name="ck_perm_placement_fee_nonnegative"),
        CheckConstraint("concierge_consultation_fee_cents >= 0", name="ck_perm_consultation_fee_nonnegative"),
        CheckConstraint("concierge_engagement_fee_cents >= 0", name="ck_perm_engagement_fee_nonnegative"),
        CheckConstraint("concierge_success_balance_cents >= 0", name="ck_perm_success_balance_nonnegative"),
        CheckConstraint("self_match_profile_limit > 0", name="ck_perm_profile_limit_positive"),
        CheckConstraint("self_match_interview_limit > 0", name="ck_perm_self_interview_limit_positive"),
        CheckConstraint("concierge_interview_limit > 0", name="ck_perm_concierge_interview_limit_positive"),
        CheckConstraint("candidate_access_days > 0", name="ck_perm_access_days_positive"),
        CheckConstraint("replacement_period_days > 0", name="ck_perm_replacement_days_positive"),
        CheckConstraint("replacement_credit_count > 0", name="ck_perm_replacement_credits_positive"),
        CheckConstraint("replacement_max_count > 0", name="ck_perm_replacement_count_positive"),
        CheckConstraint("maybe_period_days > 0", name="ck_perm_maybe_days_positive"),
    )


class PermanentPlacementCandidate(Base):
    __tablename__ = "permanent_placement_candidates"

    id = Column(Integer, primary_key=True)
    placement_id = Column(Integer, ForeignKey("permanent_placements.id"), nullable=False, index=True)
    nanny_id = Column(Integer, ForeignKey("nannies.id"), nullable=False, index=True)
    status = Column(String(40), nullable=False, default="invited", index=True)
    consent_status = Column(String(20), nullable=False, default="pending")
    invited_at = Column(DateTime, nullable=False, server_default=func.now())
    responded_at = Column(DateTime, nullable=True)
    profile_released_at = Column(DateTime, nullable=True)
    introduction_expires_at = Column(DateTime, nullable=True)
    shortlisted_at = Column(DateTime, nullable=True)
    interview_requested_at = Column(DateTime, nullable=True)
    interview_invite_status = Column(String(24), nullable=False, default="not_requested")
    interview_responded_at = Column(DateTime, nullable=True)
    interview_credit_cycle = Column(Integer, nullable=True)
    interview_credit_consumed_at = Column(DateTime, nullable=True)
    interview_credit_restored_at = Column(DateTime, nullable=True)
    interview_scheduled_at = Column(DateTime, nullable=True)
    interview_checked_in_at = Column(DateTime, nullable=True)
    interview_completed_at = Column(DateTime, nullable=True)
    interview_format = Column(String(40), nullable=True)
    interview_location = Column(Text, nullable=True)
    parent_contact_terms_accepted_at = Column(DateTime, nullable=True)
    nanny_contact_terms_accepted_at = Column(DateTime, nullable=True)
    trial_scheduled_at = Column(DateTime, nullable=True)
    trial_ends_at = Column(DateTime, nullable=True)
    trial_status = Column(String(24), nullable=False, default="not_requested")
    trial_responded_at = Column(DateTime, nullable=True)
    trial_alternative_at = Column(DateTime, nullable=True)
    trial_notes = Column(Text, nullable=True)
    offer_status = Column(String(24), nullable=False, default="not_requested")
    offer_salary_cents = Column(Integer, nullable=True)
    offer_start_date = Column(Date, nullable=True)
    offer_working_days_json = Column(Text, nullable=True)
    offer_start_time = Column(String(5), nullable=True)
    offer_end_time = Column(String(5), nullable=True)
    offer_terms = Column(Text, nullable=True)
    offer_sent_at = Column(DateTime, nullable=True)
    offer_responded_at = Column(DateTime, nullable=True)
    availability_restructured_at = Column(DateTime, nullable=True)
    client_notes = Column(Text, nullable=True)
    parent_interview_decision = Column(String(24), nullable=True)
    parent_interview_feedback = Column(Text, nullable=True)
    parent_interview_decided_at = Column(DateTime, nullable=True)
    maybe_until = Column(DateTime, nullable=True)
    admin_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("placement_id", "nanny_id", name="uq_placement_candidate"),
        Index("ix_permanent_candidates_placement_status", "placement_id", "status"),
    )


class PermanentPlacementPayment(Base):
    __tablename__ = "permanent_placement_payments"

    id = Column(Integer, primary_key=True)
    placement_id = Column(Integer, ForeignKey("permanent_placements.id"), nullable=False, index=True)
    fee_type = Column(String(32), nullable=False)
    amount_cents = Column(Integer, nullable=False)
    status = Column(String(24), nullable=False, default="pending", index=True)
    paystack_reference = Column(String(160), nullable=True, unique=True, index=True)
    paystack_transaction_id = Column(String(160), nullable=True)
    paid_at = Column(DateTime, nullable=True)
    payment_note = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("placement_id", "fee_type", name="uq_placement_fee_type"),
    )


class PermanentPlacementPreference(Base):
    __tablename__ = "permanent_placement_preferences"

    id = Column(Integer, primary_key=True)
    nanny_id = Column(Integer, ForeignKey("nannies.id"), nullable=False, unique=True, index=True)
    opted_in = Column(Boolean, nullable=False, default=False)
    desired_salary_min_cents = Column(Integer, nullable=True)
    desired_salary_max_cents = Column(Integer, nullable=True)
    employment_types_json = Column(Text, nullable=True)
    preferred_locations = Column(Text, nullable=True)
    available_from = Column(Date, nullable=True)
    live_in_preference = Column(String(24), nullable=True)
    profile_notes = Column(Text, nullable=True)
    consent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class PermanentPlacementActivity(Base):
    __tablename__ = "permanent_placement_activities"

    id = Column(Integer, primary_key=True)
    placement_id = Column(Integer, ForeignKey("permanent_placements.id"), nullable=False, index=True)
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    event_type = Column(String(64), nullable=False, index=True)
    details_json = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_permanent_activity_placement_created", "placement_id", "created_at"),
    )


class PermanentPlacementInterviewCreditEvent(Base):
    __tablename__ = "permanent_placement_interview_credit_events"

    id = Column(Integer, primary_key=True)
    placement_id = Column(Integer, ForeignKey("permanent_placements.id"), nullable=False, index=True)
    candidate_id = Column(Integer, ForeignKey("permanent_placement_candidates.id"), nullable=False, index=True)
    cycle = Column(Integer, nullable=False, default=0)
    delta = Column(Integer, nullable=False)
    event_type = Column(String(32), nullable=False, index=True)
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("delta IN (-1, 1)", name="ck_perm_interview_credit_delta"),
        Index(
            "ix_permanent_interview_credit_placement_cycle",
            "placement_id",
            "cycle",
        ),
    )


class PermanentPlacementMessage(Base):
    __tablename__ = "permanent_placement_messages"

    id = Column(Integer, primary_key=True)
    placement_id = Column(Integer, ForeignKey("permanent_placements.id"), nullable=False, index=True)
    candidate_id = Column(Integer, ForeignKey("permanent_placement_candidates.id"), nullable=False, index=True)
    sender_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        Index(
            "ix_permanent_messages_candidate_created",
            "candidate_id",
            "created_at",
        ),
    )
