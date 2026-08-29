"""add charge disputes and payout hold

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
"""

from alembic import op
import sqlalchemy as sa


revision = "b3c4d5e6f7a8"
down_revision = "a2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "bookings",
        sa.Column("charge_dispute_hold", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "charge_disputes",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("booking_request_id", sa.Integer(), sa.ForeignKey("booking_requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("booking_id", sa.Integer(), sa.ForeignKey("bookings.id", ondelete="SET NULL"), nullable=True),
        sa.Column("parent_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("line_item", sa.String(length=40), nullable=False),
        sa.Column("charge_amount_cents", sa.Integer(), nullable=False),
        sa.Column("disputed_amount_cents", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=200), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="open"),
        sa.Column("approved_refund_cents", sa.Integer(), nullable=True),
        sa.Column("resolution_reason", sa.Text(), nullable=True),
        sa.Column("paystack_refund_reference", sa.String(length=255), nullable=True),
        sa.Column("reviewed_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("line_item in ('nanny_wage','booking_fee','overtime','other')", name="ck_charge_disputes_line_item"),
        sa.CheckConstraint("status in ('open','refund_requested','refunded','denied','failed')", name="ck_charge_disputes_status"),
        sa.CheckConstraint("charge_amount_cents > 0", name="ck_charge_disputes_charge_positive"),
        sa.CheckConstraint("disputed_amount_cents > 0", name="ck_charge_disputes_amount_positive"),
    )
    op.create_index("ix_charge_disputes_booking_request_id", "charge_disputes", ["booking_request_id"])
    op.create_index("ix_charge_disputes_parent_user_id", "charge_disputes", ["parent_user_id"])
    op.create_index("ix_charge_disputes_status", "charge_disputes", ["status"])


def downgrade():
    op.drop_index("ix_charge_disputes_status", table_name="charge_disputes")
    op.drop_index("ix_charge_disputes_parent_user_id", table_name="charge_disputes")
    op.drop_index("ix_charge_disputes_booking_request_id", table_name="charge_disputes")
    op.drop_table("charge_disputes")
    op.drop_column("bookings", "charge_dispute_hold")
