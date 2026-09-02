"""add shared billing settings and invoice core

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-09-02
"""

from alembic import op
import sqlalchemy as sa


revision = "e2f3a4b5c6d7"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "billing_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("issuer_legal_name", sa.String(length=200), nullable=True),
        sa.Column("issuer_trading_name", sa.String(length=200), nullable=False, server_default="My Nanny"),
        sa.Column("issuer_email", sa.String(length=254), nullable=True),
        sa.Column("issuer_phone", sa.String(length=80), nullable=True),
        sa.Column("issuer_address", sa.Text(), nullable=True),
        sa.Column("issuer_registration_number", sa.String(length=100), nullable=True),
        sa.Column("issuer_vat_number", sa.String(length=100), nullable=True),
        sa.Column("vat_registered", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("vat_rate_bps", sa.Integer(), nullable=False, server_default="1500"),
        sa.Column("prices_include_vat", sa.Boolean(), nullable=True),
        sa.Column("tax_status_confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("invoice_prefix", sa.String(length=20), nullable=False, server_default="MN"),
        sa.Column("next_invoice_sequence", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("next_receipt_sequence", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "invoices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("service_type", sa.String(length=40), nullable=False),
        sa.Column("parent_user_id", sa.Integer(), nullable=False),
        sa.Column("permanent_placement_id", sa.Integer(), nullable=True),
        sa.Column("permanent_payment_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="draft"),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="ZAR"),
        sa.Column("subtotal_cents", sa.Integer(), nullable=False),
        sa.Column("vat_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_cents", sa.Integer(), nullable=False),
        sa.Column("line_items_json", sa.Text(), nullable=False),
        sa.Column("issuer_snapshot_json", sa.Text(), nullable=True),
        sa.Column("customer_snapshot_json", sa.Text(), nullable=False),
        sa.Column("invoice_number", sa.String(length=80), nullable=True),
        sa.Column("receipt_number", sa.String(length=80), nullable=True),
        sa.Column("invoice_pdf_url", sa.Text(), nullable=True),
        sa.Column("invoice_pdf_sha256", sa.String(length=64), nullable=True),
        sa.Column("receipt_pdf_url", sa.Text(), nullable=True),
        sa.Column("receipt_pdf_sha256", sa.String(length=64), nullable=True),
        sa.Column("paystack_reference", sa.String(length=160), nullable=True),
        sa.Column("paystack_transaction_id", sa.String(length=160), nullable=True),
        sa.Column("issued_at", sa.DateTime(), nullable=True),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.Column("voided_at", sa.DateTime(), nullable=True),
        sa.Column("void_reason", sa.Text(), nullable=True),
        sa.Column("invoice_email_requested_at", sa.DateTime(), nullable=True),
        sa.Column("receipt_email_requested_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["parent_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["permanent_placement_id"], ["permanent_placements.id"]),
        sa.ForeignKeyConstraint(["permanent_payment_id"], ["permanent_placement_payments.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invoice_number"),
        sa.UniqueConstraint("receipt_number"),
        sa.UniqueConstraint("permanent_payment_id", name="uq_invoice_permanent_payment"),
    )
    op.create_index("ix_invoices_service_type", "invoices", ["service_type"])
    op.create_index("ix_invoices_parent_user_id", "invoices", ["parent_user_id"])
    op.create_index("ix_invoices_permanent_placement_id", "invoices", ["permanent_placement_id"])
    op.create_index("ix_invoices_status", "invoices", ["status"])
    op.create_index("ix_invoices_invoice_number", "invoices", ["invoice_number"], unique=True)
    op.create_index("ix_invoices_receipt_number", "invoices", ["receipt_number"], unique=True)
    op.create_index("ix_invoices_parent_created", "invoices", ["parent_user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_invoices_parent_created", table_name="invoices")
    op.drop_index("ix_invoices_receipt_number", table_name="invoices")
    op.drop_index("ix_invoices_invoice_number", table_name="invoices")
    op.drop_index("ix_invoices_status", table_name="invoices")
    op.drop_index("ix_invoices_permanent_placement_id", table_name="invoices")
    op.drop_index("ix_invoices_parent_user_id", table_name="invoices")
    op.drop_index("ix_invoices_service_type", table_name="invoices")
    op.drop_table("invoices")
    op.drop_table("billing_settings")
