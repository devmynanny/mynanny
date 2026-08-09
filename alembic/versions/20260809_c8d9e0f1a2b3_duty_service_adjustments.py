"""add duty service adjustment fields

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2
"""

from alembic import op
import sqlalchemy as sa

revision = "c8d9e0f1a2b3"
down_revision = "b7c8d9e0f1a2"
branch_labels = None
depends_on = None


def upgrade():
    columns = (
        sa.Column("late_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("early_departure_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("billable_minutes", sa.Integer(), nullable=True),
        sa.Column("scheduled_minutes", sa.Integer(), nullable=True),
        sa.Column("service_wage_cents", sa.Integer(), nullable=True),
        sa.Column("service_fee_cents", sa.Integer(), nullable=True),
        sa.Column("service_refund_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("service_adjustment_status", sa.String(), nullable=True),
        sa.Column("service_refund_reference", sa.Text(), nullable=True),
        sa.Column("service_adjusted_at", sa.DateTime(timezone=True), nullable=True),
    )
    for column in columns:
        op.add_column("bookings", column)


def downgrade():
    for name in (
        "service_adjusted_at", "service_refund_reference", "service_adjustment_status",
        "service_refund_cents", "service_fee_cents", "service_wage_cents",
        "scheduled_minutes", "billable_minutes", "early_departure_minutes", "late_minutes",
    ):
        op.drop_column("bookings", name)
