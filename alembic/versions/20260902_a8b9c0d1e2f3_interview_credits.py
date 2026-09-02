"""add permanent-placement interview credit ledger

Revision ID: a8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-09-02
"""

from alembic import op
import sqlalchemy as sa


revision = "a8b9c0d1e2f3"
down_revision = "f7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "permanent_placements",
        sa.Column("replacement_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "permanent_placements",
        sa.Column("interview_credit_cycle", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "permanent_placement_candidates",
        sa.Column(
            "interview_invite_status",
            sa.String(length=24),
            nullable=False,
            server_default="not_requested",
        ),
    )
    op.add_column(
        "permanent_placement_candidates",
        sa.Column("interview_responded_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "permanent_placement_candidates",
        sa.Column("interview_credit_cycle", sa.Integer(), nullable=True),
    )
    op.add_column(
        "permanent_placement_candidates",
        sa.Column("interview_credit_consumed_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "permanent_placement_candidates",
        sa.Column("interview_credit_restored_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "permanent_placement_interview_credit_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("placement_id", sa.Integer(), nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.Column("cycle", sa.Integer(), nullable=False),
        sa.Column("delta", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("delta IN (-1, 1)", name="ck_perm_interview_credit_delta"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["candidate_id"], ["permanent_placement_candidates.id"]),
        sa.ForeignKeyConstraint(["placement_id"], ["permanent_placements.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_permanent_placement_interview_credit_events_placement_id",
        "permanent_placement_interview_credit_events",
        ["placement_id"],
    )
    op.create_index(
        "ix_permanent_placement_interview_credit_events_candidate_id",
        "permanent_placement_interview_credit_events",
        ["candidate_id"],
    )
    op.create_index(
        "ix_permanent_placement_interview_credit_events_event_type",
        "permanent_placement_interview_credit_events",
        ["event_type"],
    )
    op.create_index(
        "ix_permanent_interview_credit_placement_cycle",
        "permanent_placement_interview_credit_events",
        ["placement_id", "cycle"],
    )

    op.execute(
        sa.text(
            "UPDATE permanent_placement_candidates "
            "SET interview_invite_status = CASE "
            "WHEN status = 'interview_requested' THEN 'pending' "
            "WHEN status IN ('interview_scheduled', 'interviewed', 'trial', 'offered', 'hired') "
            "THEN 'accepted' ELSE 'not_requested' END"
        )
    )
    op.execute(
        sa.text(
            "UPDATE permanent_placement_candidates "
            "SET interview_credit_cycle = 0, "
            "interview_credit_consumed_at = COALESCE(interview_scheduled_at, interview_requested_at, created_at) "
            "WHERE interview_invite_status = 'accepted'"
        )
    )
    op.execute(
        sa.text(
            "INSERT INTO permanent_placement_interview_credit_events "
            "(placement_id, candidate_id, cycle, delta, event_type, created_at) "
            "SELECT placement_id, id, 0, -1, 'migrated_acceptance', "
            "COALESCE(interview_scheduled_at, interview_requested_at, created_at) "
            "FROM permanent_placement_candidates "
            "WHERE interview_invite_status = 'accepted'"
        )
    )


def downgrade() -> None:
    op.drop_index(
        "ix_permanent_interview_credit_placement_cycle",
        table_name="permanent_placement_interview_credit_events",
    )
    op.drop_index(
        "ix_permanent_placement_interview_credit_events_event_type",
        table_name="permanent_placement_interview_credit_events",
    )
    op.drop_index(
        "ix_permanent_placement_interview_credit_events_candidate_id",
        table_name="permanent_placement_interview_credit_events",
    )
    op.drop_index(
        "ix_permanent_placement_interview_credit_events_placement_id",
        table_name="permanent_placement_interview_credit_events",
    )
    op.drop_table("permanent_placement_interview_credit_events")
    op.drop_column("permanent_placement_candidates", "interview_credit_restored_at")
    op.drop_column("permanent_placement_candidates", "interview_credit_consumed_at")
    op.drop_column("permanent_placement_candidates", "interview_credit_cycle")
    op.drop_column("permanent_placement_candidates", "interview_responded_at")
    op.drop_column("permanent_placement_candidates", "interview_invite_status")
    op.drop_column("permanent_placements", "interview_credit_cycle")
    op.drop_column("permanent_placements", "replacement_count")
