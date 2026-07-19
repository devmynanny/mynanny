
from sqlalchemy import (
	Column, BigInteger, Integer, String, Text, Boolean, ForeignKey, DateTime, Numeric,
	CheckConstraint, UniqueConstraint, Index, and_
)
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import func


from app.db import Base
from app.services.booking_status import (
	BOOKING_WRITE_STATUSES,
	PAYMENT_WRITE_STATUSES,
	REQUEST_WRITE_STATUSES,
	RESPONSE_WRITE_STATUSES,
)


class BookingRequest(Base):
	__tablename__ = "booking_requests"
	id = Column(BigInteger, primary_key=True)
	parent_user_id = Column(BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
	nanny_id = Column(BigInteger, ForeignKey("nannies.id", ondelete="RESTRICT"), nullable=False)
	status = Column(Text, nullable=False, default="tbc")
	group_id = Column(BigInteger, nullable=True)
	start_dt = Column(Text, nullable=True)
	end_dt = Column(Text, nullable=True)
	sleepover = Column(Boolean, nullable=True)
	wage_cents = Column(Integer, nullable=True)
	booking_fee_pct = Column(Numeric(5, 4), nullable=True)
	booking_fee_cents = Column(Integer, nullable=True)
	total_cents = Column(Integer, nullable=True)
	paid_at = Column(DateTime(timezone=True), nullable=True)
	company_retained_cents = Column(Integer, nullable=True)
	nanny_retained_cents = Column(Integer, nullable=True)
	refund_cents = Column(Integer, nullable=True)
	refund_status = Column(Text, nullable=True)
	refund_requested_at = Column(DateTime(timezone=True), nullable=True)
	refund_processed_at = Column(DateTime(timezone=True), nullable=True)
	refund_failed_at = Column(DateTime(timezone=True), nullable=True)
	refund_failure_reason = Column(Text, nullable=True)
	refund_reviewed_at = Column(DateTime(timezone=True), nullable=True)
	refund_reviewed_by = Column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
	refund_review_reason = Column(Text, nullable=True)
	paystack_reference = Column(Text, nullable=True)
	paystack_transaction_id = Column(Text, nullable=True)
	paystack_refund_reference = Column(Text, nullable=True)
	cancelled_at = Column(DateTime(timezone=True), nullable=True)
	hold_expires_at = Column(DateTime(timezone=True), nullable=True)
	payment_status = Column(Text, nullable=False, default="pending_payment")
	admin_notes = Column(Text)
	client_notes = Column(Text)
	# Structured count of nannies the parent wants for this job. Historically
	# this was only encoded as a "Nannies requested: N" prefix inside
	# client_notes; the column is now the source of truth (notes prefix kept
	# for human readability / backward compatibility).
	requested_nannies_count = Column(Integer, nullable=True, default=1)
	created_by_admin_user_id = Column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
	requested_starts_at = Column(DateTime(timezone=True), nullable=False)
	requested_ends_at = Column(DateTime(timezone=True), nullable=False)
	location_id = Column(BigInteger, ForeignKey("parent_locations.id", ondelete="SET NULL"))
	admin_user_id = Column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
	admin_decided_at = Column(DateTime(timezone=True), nullable=True)
	admin_reason = Column(Text, nullable=True)
	replacement_required = Column(Boolean, nullable=False, default=False)
	unaccepted_admin_notified_at = Column(DateTime(timezone=True), nullable=True)
	nanny_response_status = Column(Text, nullable=True, default="pending")
	nanny_responded_at = Column(DateTime(timezone=True), nullable=True)
	nanny_response_note = Column(Text, nullable=True)
	created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
	updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

	@validates("status")
	def _validate_status(self, key, value):
		if value is not None and value not in REQUEST_WRITE_STATUSES:
			raise ValueError(
				f"Invalid booking_request status {value!r}; allowed: {sorted(REQUEST_WRITE_STATUSES)}"
			)
		return value

	@validates("nanny_response_status")
	def _validate_response_status(self, key, value):
		if value is not None and value not in RESPONSE_WRITE_STATUSES:
			raise ValueError(
				f"Invalid nanny_response_status {value!r}; allowed: {sorted(RESPONSE_WRITE_STATUSES)}"
			)
		return value

	@validates("payment_status")
	def _validate_payment_status(self, key, value):
		if value is not None and value not in PAYMENT_WRITE_STATUSES:
			raise ValueError(
				f"Invalid payment_status {value!r}; allowed: {sorted(PAYMENT_WRITE_STATUSES)}"
			)
		return value

	__table_args__ = (
		CheckConstraint("status IN ('tbc','pending_admin','approved','rejected','cancelled')", name="booking_requests_status_check"),
		CheckConstraint(
			"nanny_response_status IS NULL OR nanny_response_status IN ('pending','accepted','declined','deciding')",
			name="booking_requests_nanny_response_status_check",
		),
		CheckConstraint(
			"payment_status IN ('pending_payment','paid','cancelled')",
			name="booking_requests_payment_status_check",
		),
	)

class BookingRequestSlot(Base):
	__tablename__ = "booking_request_slots"
	id = Column(BigInteger, primary_key=True)
	booking_request_id = Column(BigInteger, ForeignKey("booking_requests.id", ondelete="CASCADE"), nullable=False)
	starts_at = Column(DateTime(timezone=True), nullable=False)
	ends_at = Column(DateTime(timezone=True), nullable=False)
	__table_args__ = (
		CheckConstraint("ends_at > starts_at", name="booking_request_slots_time_check"),
		Index("brs_request_id_idx", "booking_request_id"),
		Index("brs_starts_at_idx", "starts_at"),
	)

class BookingPricingSnapshot(Base):
	__tablename__ = "booking_pricing_snapshot"
	booking_request_id = Column(BigInteger, ForeignKey("booking_requests.id", ondelete="CASCADE"), primary_key=True)
	currency = Column(Text, nullable=False, default="ZAR")
	hourly_rate_cents = Column(Integer, nullable=False)
	fee_pct = Column(Numeric(5,4), nullable=False)
	total_minutes = Column(Integer, nullable=False)
	base_amount_cents = Column(Integer, nullable=False)
	fee_amount_cents = Column(Integer, nullable=False)
	total_amount_cents = Column(Integer, nullable=False)
	created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
	__table_args__ = (
		CheckConstraint("hourly_rate_cents >= 0", name="bps_hourly_rate_check"),
		CheckConstraint("fee_pct >= 0 AND fee_pct <= 1", name="bps_fee_pct_check"),
		CheckConstraint("total_minutes >= 0", name="bps_total_minutes_check"),
		CheckConstraint("base_amount_cents >= 0", name="bps_base_amount_check"),
		CheckConstraint("fee_amount_cents >= 0", name="bps_fee_amount_check"),
		CheckConstraint("total_amount_cents >= 0", name="bps_total_amount_check"),
	)
