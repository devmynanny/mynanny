"""add permanent trial, offer and calendar fields

Revision ID: c0d1e2f3a4b5
Revises: b9c0d1e2f3a4
Create Date: 2026-09-02
"""

from alembic import op
import sqlalchemy as sa


revision = "c0d1e2f3a4b5"
down_revision = "b9c0d1e2f3a4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = [
        sa.Column("trial_ends_at", sa.DateTime(), nullable=True),
        sa.Column("trial_status", sa.String(length=24), nullable=False, server_default="not_requested"),
        sa.Column("trial_responded_at", sa.DateTime(), nullable=True),
        sa.Column("trial_alternative_at", sa.DateTime(), nullable=True),
        sa.Column("offer_status", sa.String(length=24), nullable=False, server_default="not_requested"),
        sa.Column("offer_salary_cents", sa.Integer(), nullable=True),
        sa.Column("offer_start_date", sa.Date(), nullable=True),
        sa.Column("offer_working_days_json", sa.Text(), nullable=True),
        sa.Column("offer_start_time", sa.String(length=5), nullable=True),
        sa.Column("offer_end_time", sa.String(length=5), nullable=True),
        sa.Column("offer_terms", sa.Text(), nullable=True),
        sa.Column("offer_sent_at", sa.DateTime(), nullable=True),
        sa.Column("offer_responded_at", sa.DateTime(), nullable=True),
        sa.Column("availability_restructured_at", sa.DateTime(), nullable=True),
    ]
    for column in columns:
        op.add_column("permanent_placement_candidates", column)

    op.execute(
        sa.text(
            "UPDATE permanent_placement_candidates SET trial_status = 'accepted' "
            "WHERE status = 'trial' AND trial_scheduled_at IS NOT NULL"
        )
    )
    op.execute(
        sa.text(
            "UPDATE permanent_placement_candidates SET offer_status = 'accepted', "
            "offer_responded_at = COALESCE(updated_at, created_at) "
            "WHERE status = 'hired'"
        )
    )


def downgrade() -> None:
    for column_name in [
        "availability_restructured_at",
        "offer_responded_at",
        "offer_sent_at",
        "offer_terms",
        "offer_end_time",
        "offer_start_time",
        "offer_working_days_json",
        "offer_start_date",
        "offer_salary_cents",
        "offer_status",
        "trial_alternative_at",
        "trial_responded_at",
        "trial_status",
        "trial_ends_at",
    ]:
        op.drop_column("permanent_placement_candidates", column_name)
