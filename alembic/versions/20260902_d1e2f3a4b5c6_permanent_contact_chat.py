"""add permanent interview contact terms and chat

Revision ID: d1e2f3a4b5c6
Revises: c0d1e2f3a4b5
Create Date: 2026-09-02
"""

from alembic import op
import sqlalchemy as sa


revision = "d1e2f3a4b5c6"
down_revision = "c0d1e2f3a4b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "permanent_placement_candidates",
        sa.Column("parent_contact_terms_accepted_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "permanent_placement_candidates",
        sa.Column("nanny_contact_terms_accepted_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "permanent_placement_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("placement_id", sa.Integer(), nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.Column("sender_user_id", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["permanent_placement_candidates.id"]),
        sa.ForeignKeyConstraint(["placement_id"], ["permanent_placements.id"]),
        sa.ForeignKeyConstraint(["sender_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_permanent_placement_messages_placement_id",
        "permanent_placement_messages",
        ["placement_id"],
    )
    op.create_index(
        "ix_permanent_placement_messages_candidate_id",
        "permanent_placement_messages",
        ["candidate_id"],
    )
    op.create_index(
        "ix_permanent_placement_messages_sender_user_id",
        "permanent_placement_messages",
        ["sender_user_id"],
    )
    op.create_index(
        "ix_permanent_messages_candidate_created",
        "permanent_placement_messages",
        ["candidate_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_permanent_messages_candidate_created", table_name="permanent_placement_messages")
    op.drop_index("ix_permanent_placement_messages_sender_user_id", table_name="permanent_placement_messages")
    op.drop_index("ix_permanent_placement_messages_candidate_id", table_name="permanent_placement_messages")
    op.drop_index("ix_permanent_placement_messages_placement_id", table_name="permanent_placement_messages")
    op.drop_table("permanent_placement_messages")
    op.drop_column("permanent_placement_candidates", "nanny_contact_terms_accepted_at")
    op.drop_column("permanent_placement_candidates", "parent_contact_terms_accepted_at")
