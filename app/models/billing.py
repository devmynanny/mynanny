from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from app.db import Base


class BillingSettings(Base):
    __tablename__ = "billing_settings"

    id = Column(Integer, primary_key=True, default=1)
    issuer_legal_name = Column(String(200), nullable=True)
    issuer_trading_name = Column(String(200), nullable=False, default="My Nanny")
    issuer_email = Column(String(254), nullable=True)
    issuer_phone = Column(String(80), nullable=True)
    issuer_address = Column(Text, nullable=True)
    issuer_registration_number = Column(String(100), nullable=True)
    issuer_vat_number = Column(String(100), nullable=True)
    vat_registered = Column(Boolean, nullable=False, default=False)
    vat_rate_bps = Column(Integer, nullable=False, default=1500)
    prices_include_vat = Column(Boolean, nullable=True)
    tax_status_confirmed_at = Column(DateTime, nullable=True)
    invoice_prefix = Column(String(20), nullable=False, default="MN")
    next_invoice_sequence = Column(Integer, nullable=False, default=1)
    next_receipt_sequence = Column(Integer, nullable=False, default=1)
    updated_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True)
    service_type = Column(String(40), nullable=False, index=True)
    parent_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    permanent_placement_id = Column(Integer, ForeignKey("permanent_placements.id"), nullable=True, index=True)
    permanent_payment_id = Column(Integer, ForeignKey("permanent_placement_payments.id"), nullable=True)
    status = Column(String(24), nullable=False, default="draft", index=True)
    currency = Column(String(3), nullable=False, default="ZAR")
    subtotal_cents = Column(Integer, nullable=False)
    vat_cents = Column(Integer, nullable=False, default=0)
    total_cents = Column(Integer, nullable=False)
    line_items_json = Column(Text, nullable=False)
    issuer_snapshot_json = Column(Text, nullable=True)
    customer_snapshot_json = Column(Text, nullable=False)
    invoice_number = Column(String(80), nullable=True, unique=True, index=True)
    receipt_number = Column(String(80), nullable=True, unique=True, index=True)
    invoice_pdf_url = Column(Text, nullable=True)
    invoice_pdf_sha256 = Column(String(64), nullable=True)
    receipt_pdf_url = Column(Text, nullable=True)
    receipt_pdf_sha256 = Column(String(64), nullable=True)
    paystack_reference = Column(String(160), nullable=True)
    paystack_transaction_id = Column(String(160), nullable=True)
    issued_at = Column(DateTime, nullable=True)
    paid_at = Column(DateTime, nullable=True)
    voided_at = Column(DateTime, nullable=True)
    void_reason = Column(Text, nullable=True)
    invoice_email_requested_at = Column(DateTime, nullable=True)
    receipt_email_requested_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("permanent_payment_id", name="uq_invoice_permanent_payment"),
        Index("ix_invoices_parent_created", "parent_user_id", "created_at"),
    )
