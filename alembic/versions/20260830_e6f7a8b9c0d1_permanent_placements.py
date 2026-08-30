"""add permanent placement pilot workflow

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-08-30
"""

from alembic import op
import sqlalchemy as sa


revision = "e6f7a8b9c0d1"
down_revision = "d5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column(
            "permanent_placements_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.create_table(
        "permanent_placements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("parent_user_id", sa.Integer(), nullable=False),
        sa.Column("service_tier", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("role_title", sa.String(length=160), nullable=False),
        sa.Column("employment_type", sa.String(length=40), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("schedule_summary", sa.Text(), nullable=False),
        sa.Column("hours_per_week", sa.Integer(), nullable=True),
        sa.Column("children_count", sa.Integer(), nullable=False),
        sa.Column("children_ages_json", sa.Text(), nullable=True),
        sa.Column("duties", sa.Text(), nullable=False),
        sa.Column("special_requirements", sa.Text(), nullable=True),
        sa.Column("salary_min_cents", sa.Integer(), nullable=False),
        sa.Column("salary_max_cents", sa.Integer(), nullable=False),
        sa.Column("location_suburb", sa.String(length=120), nullable=False),
        sa.Column("location_city", sa.String(length=120), nullable=False),
        sa.Column("location_province", sa.String(length=120), nullable=True),
        sa.Column("live_in", sa.Boolean(), nullable=False),
        sa.Column("drivers_license_required", sa.Boolean(), nullable=False),
        sa.Column("own_car_required", sa.Boolean(), nullable=False),
        sa.Column("languages_json", sa.Text(), nullable=True),
        sa.Column("pets", sa.Text(), nullable=True),
        sa.Column("parent_notes", sa.Text(), nullable=True),
        sa.Column("admin_notes", sa.Text(), nullable=True),
        sa.Column("candidate_access_expires_at", sa.DateTime(), nullable=True),
        sa.Column("placed_nanny_id", sa.Integer(), nullable=True),
        sa.Column("hired_at", sa.DateTime(), nullable=True),
        sa.Column("success_fee_due_at", sa.DateTime(), nullable=True),
        sa.Column("guarantee_until", sa.DateTime(), nullable=True),
        sa.Column("replacement_status", sa.String(length=32), nullable=False),
        sa.Column("replacement_requested_at", sa.DateTime(), nullable=True),
        sa.Column("replacement_reason", sa.Text(), nullable=True),
        sa.Column("replacement_resolved_at", sa.DateTime(), nullable=True),
        sa.Column("replacement_resolved_by", sa.Integer(), nullable=True),
        sa.Column("upgraded_from_self_match", sa.Boolean(), nullable=False),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["parent_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["placed_nanny_id"], ["nannies.id"]),
        sa.ForeignKeyConstraint(["replacement_resolved_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_permanent_placements_parent_user_id", "permanent_placements", ["parent_user_id"])
    op.create_index("ix_permanent_placements_status", "permanent_placements", ["status"])
    op.create_index("ix_permanent_placements_parent_status", "permanent_placements", ["parent_user_id", "status"])
    op.create_index("ix_permanent_placements_tier_status", "permanent_placements", ["service_tier", "status"])

    op.create_table(
        "permanent_placement_candidates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("placement_id", sa.Integer(), nullable=False),
        sa.Column("nanny_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("consent_status", sa.String(length=20), nullable=False),
        sa.Column("invited_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("responded_at", sa.DateTime(), nullable=True),
        sa.Column("profile_released_at", sa.DateTime(), nullable=True),
        sa.Column("introduction_expires_at", sa.DateTime(), nullable=True),
        sa.Column("shortlisted_at", sa.DateTime(), nullable=True),
        sa.Column("interview_requested_at", sa.DateTime(), nullable=True),
        sa.Column("interview_scheduled_at", sa.DateTime(), nullable=True),
        sa.Column("interview_format", sa.String(length=40), nullable=True),
        sa.Column("interview_location", sa.Text(), nullable=True),
        sa.Column("trial_scheduled_at", sa.DateTime(), nullable=True),
        sa.Column("trial_notes", sa.Text(), nullable=True),
        sa.Column("client_notes", sa.Text(), nullable=True),
        sa.Column("admin_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["placement_id"], ["permanent_placements.id"]),
        sa.ForeignKeyConstraint(["nanny_id"], ["nannies.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("placement_id", "nanny_id", name="uq_placement_candidate"),
    )
    op.create_index("ix_permanent_placement_candidates_placement_id", "permanent_placement_candidates", ["placement_id"])
    op.create_index("ix_permanent_placement_candidates_nanny_id", "permanent_placement_candidates", ["nanny_id"])
    op.create_index("ix_permanent_placement_candidates_status", "permanent_placement_candidates", ["status"])
    op.create_index("ix_permanent_candidates_placement_status", "permanent_placement_candidates", ["placement_id", "status"])

    op.create_table(
        "permanent_placement_payments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("placement_id", sa.Integer(), nullable=False),
        sa.Column("fee_type", sa.String(length=32), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("paystack_reference", sa.String(length=160), nullable=True),
        sa.Column("paystack_transaction_id", sa.String(length=160), nullable=True),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.Column("payment_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["placement_id"], ["permanent_placements.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("placement_id", "fee_type", name="uq_placement_fee_type"),
        sa.UniqueConstraint("paystack_reference"),
    )
    op.create_index("ix_permanent_placement_payments_placement_id", "permanent_placement_payments", ["placement_id"])
    op.create_index("ix_permanent_placement_payments_status", "permanent_placement_payments", ["status"])
    op.create_index("ix_permanent_placement_payments_paystack_reference", "permanent_placement_payments", ["paystack_reference"])

    op.create_table(
        "permanent_placement_preferences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nanny_id", sa.Integer(), nullable=False),
        sa.Column("opted_in", sa.Boolean(), nullable=False),
        sa.Column("desired_salary_min_cents", sa.Integer(), nullable=True),
        sa.Column("desired_salary_max_cents", sa.Integer(), nullable=True),
        sa.Column("employment_types_json", sa.Text(), nullable=True),
        sa.Column("preferred_locations", sa.Text(), nullable=True),
        sa.Column("available_from", sa.Date(), nullable=True),
        sa.Column("live_in_preference", sa.String(length=24), nullable=True),
        sa.Column("profile_notes", sa.Text(), nullable=True),
        sa.Column("consent_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["nanny_id"], ["nannies.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("nanny_id"),
    )
    op.create_index("ix_permanent_placement_preferences_nanny_id", "permanent_placement_preferences", ["nanny_id"])

    op.create_table(
        "permanent_placement_activities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("placement_id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("details_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["placement_id"], ["permanent_placements.id"]),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_permanent_placement_activities_placement_id", "permanent_placement_activities", ["placement_id"])
    op.create_index("ix_permanent_placement_activities_event_type", "permanent_placement_activities", ["event_type"])
    op.create_index("ix_permanent_activity_placement_created", "permanent_placement_activities", ["placement_id", "created_at"])


def downgrade() -> None:
    op.drop_table("permanent_placement_activities")
    op.drop_table("permanent_placement_preferences")
    op.drop_table("permanent_placement_payments")
    op.drop_table("permanent_placement_candidates")
    op.drop_table("permanent_placements")
    op.drop_column("app_settings", "permanent_placements_enabled")
