"""add configurable permanent-placement pricing

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-09-01
"""

import json

from alembic import op
import sqlalchemy as sa


revision = "f7a8b9c0d1e2"
down_revision = "e6f7a8b9c0d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "permanent_placement_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("self_match_activation_fee_cents", sa.Integer(), nullable=False),
        sa.Column("self_match_interview_package_fee_cents", sa.Integer(), nullable=False),
        sa.Column("self_match_placement_fee_cents", sa.Integer(), nullable=False),
        sa.Column("activation_fee_credits_toward_package", sa.Boolean(), nullable=False),
        sa.Column("concierge_consultation_fee_cents", sa.Integer(), nullable=False),
        sa.Column("concierge_engagement_fee_cents", sa.Integer(), nullable=False),
        sa.Column("concierge_success_balance_cents", sa.Integer(), nullable=False),
        sa.Column("self_match_profile_limit", sa.Integer(), nullable=False),
        sa.Column("self_match_interview_limit", sa.Integer(), nullable=False),
        sa.Column("concierge_interview_limit", sa.Integer(), nullable=False),
        sa.Column("candidate_access_days", sa.Integer(), nullable=False),
        sa.Column("replacement_period_days", sa.Integer(), nullable=False),
        sa.Column("replacement_credit_count", sa.Integer(), nullable=False),
        sa.Column("replacement_max_count", sa.Integer(), nullable=False),
        sa.Column("maybe_period_days", sa.Integer(), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("self_match_activation_fee_cents >= 0", name="ck_perm_activation_fee_nonnegative"),
        sa.CheckConstraint("self_match_interview_package_fee_cents >= 0", name="ck_perm_package_fee_nonnegative"),
        sa.CheckConstraint("self_match_placement_fee_cents >= 0", name="ck_perm_placement_fee_nonnegative"),
        sa.CheckConstraint("concierge_consultation_fee_cents >= 0", name="ck_perm_consultation_fee_nonnegative"),
        sa.CheckConstraint("concierge_engagement_fee_cents >= 0", name="ck_perm_engagement_fee_nonnegative"),
        sa.CheckConstraint("concierge_success_balance_cents >= 0", name="ck_perm_success_balance_nonnegative"),
        sa.CheckConstraint("self_match_profile_limit > 0", name="ck_perm_profile_limit_positive"),
        sa.CheckConstraint("self_match_interview_limit > 0", name="ck_perm_self_interview_limit_positive"),
        sa.CheckConstraint("concierge_interview_limit > 0", name="ck_perm_concierge_interview_limit_positive"),
        sa.CheckConstraint("candidate_access_days > 0", name="ck_perm_access_days_positive"),
        sa.CheckConstraint("replacement_period_days > 0", name="ck_perm_replacement_days_positive"),
        sa.CheckConstraint("replacement_credit_count > 0", name="ck_perm_replacement_credits_positive"),
        sa.CheckConstraint("replacement_max_count > 0", name="ck_perm_replacement_count_positive"),
        sa.CheckConstraint("maybe_period_days > 0", name="ck_perm_maybe_days_positive"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.add_column("permanent_placements", sa.Column("pricing_snapshot_json", sa.Text(), nullable=True))

    settings_table = sa.table(
        "permanent_placement_settings",
        sa.column("id", sa.Integer()),
        sa.column("currency", sa.String()),
        sa.column("self_match_activation_fee_cents", sa.Integer()),
        sa.column("self_match_interview_package_fee_cents", sa.Integer()),
        sa.column("self_match_placement_fee_cents", sa.Integer()),
        sa.column("activation_fee_credits_toward_package", sa.Boolean()),
        sa.column("concierge_consultation_fee_cents", sa.Integer()),
        sa.column("concierge_engagement_fee_cents", sa.Integer()),
        sa.column("concierge_success_balance_cents", sa.Integer()),
        sa.column("self_match_profile_limit", sa.Integer()),
        sa.column("self_match_interview_limit", sa.Integer()),
        sa.column("concierge_interview_limit", sa.Integer()),
        sa.column("candidate_access_days", sa.Integer()),
        sa.column("replacement_period_days", sa.Integer()),
        sa.column("replacement_credit_count", sa.Integer()),
        sa.column("replacement_max_count", sa.Integer()),
        sa.column("maybe_period_days", sa.Integer()),
    )
    op.bulk_insert(
        settings_table,
        [
            {
                "id": 1,
                "currency": "ZAR",
                "self_match_activation_fee_cents": 35_000,
                "self_match_interview_package_fee_cents": 150_000,
                "self_match_placement_fee_cents": 150_000,
                "activation_fee_credits_toward_package": True,
                "concierge_consultation_fee_cents": 55_000,
                "concierge_engagement_fee_cents": 250_000,
                "concierge_success_balance_cents": 700_000,
                "self_match_profile_limit": 10,
                "self_match_interview_limit": 5,
                "concierge_interview_limit": 5,
                "candidate_access_days": 30,
                "replacement_period_days": 40,
                "replacement_credit_count": 3,
                "replacement_max_count": 1,
                "maybe_period_days": 4,
            }
        ],
    )

    # Preserve the commercial terms that any case created before this migration
    # may already have shown to the family.
    legacy_snapshot = json.dumps(
        {
            "currency": "ZAR",
            "self_match": {
                "activation_fee_cents": 35_000,
                "interview_package_fee_cents": 185_000,
                "candidate_access_fee_cents": 150_000,
                "success_fee_cents": 150_000,
                "total_if_placed_cents": 335_000,
                "profile_limit": 10,
                "interview_limit": 3,
                "candidate_access_days": 30,
                "replacement_days": 30,
                "replacement_credit_count": 3,
                "replacement_max_count": 1,
            },
            "concierge": {
                "consultation_fee_cents": 50_000,
                "application_fee_cents": 50_000,
                "engagement_fee_cents": 0,
                "success_balance_cents": 500_000,
                "success_fee_cents": 500_000,
                "total_if_placed_cents": 550_000,
                "interview_limit": 5,
                "replacement_days": 90,
            },
            "rules": {"maybe_period_days": 4},
            "upgrade": {"candidate_access_credit_cents": 150_000, "remaining_success_fee_cents": 350_000},
        }
    )
    escaped_snapshot = legacy_snapshot.replace("'", "''")
    op.execute(
        sa.text(
            "UPDATE permanent_placements "
            f"SET pricing_snapshot_json = '{escaped_snapshot}' "
            "WHERE pricing_snapshot_json IS NULL"
        )
    )
    op.execute(
        sa.text(
            "UPDATE permanent_placement_candidates "
            "SET introduction_expires_at = NULL "
            "WHERE introduction_expires_at IS NOT NULL"
        )
    )


def downgrade() -> None:
    op.drop_column("permanent_placements", "pricing_snapshot_json")
    op.drop_table("permanent_placement_settings")
