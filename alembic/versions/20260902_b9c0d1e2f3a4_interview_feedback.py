"""add permanent interview progress and parent feedback

Revision ID: b9c0d1e2f3a4
Revises: a8b9c0d1e2f3
Create Date: 2026-09-02
"""

from alembic import op
import sqlalchemy as sa


revision = "b9c0d1e2f3a4"
down_revision = "a8b9c0d1e2f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "permanent_placement_candidates",
        sa.Column("interview_checked_in_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "permanent_placement_candidates",
        sa.Column("interview_completed_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "permanent_placement_candidates",
        sa.Column("parent_interview_decision", sa.String(length=24), nullable=True),
    )
    op.add_column(
        "permanent_placement_candidates",
        sa.Column("parent_interview_feedback", sa.Text(), nullable=True),
    )
    op.add_column(
        "permanent_placement_candidates",
        sa.Column("parent_interview_decided_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "permanent_placement_candidates",
        sa.Column("maybe_until", sa.DateTime(), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE permanent_placement_candidates "
            "SET interview_completed_at = COALESCE(updated_at, created_at) "
            "WHERE status IN ('interviewed', 'trial', 'offered', 'hired') "
            "AND interview_completed_at IS NULL"
        )
    )


def downgrade() -> None:
    op.drop_column("permanent_placement_candidates", "maybe_until")
    op.drop_column("permanent_placement_candidates", "parent_interview_decided_at")
    op.drop_column("permanent_placement_candidates", "parent_interview_feedback")
    op.drop_column("permanent_placement_candidates", "parent_interview_decision")
    op.drop_column("permanent_placement_candidates", "interview_completed_at")
    op.drop_column("permanent_placement_candidates", "interview_checked_in_at")
