"""Add the persisted video screening completion flag.

Revision ID: d9e0f1a2b3c4
Revises: c8d9e0f1a2b3
"""

from alembic import op
import sqlalchemy as sa


revision = "d9e0f1a2b3c4"
down_revision = "c8d9e0f1a2b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("nannies")}
    if "video_screening_complete" not in columns:
        op.add_column(
            "nannies",
            sa.Column(
                "video_screening_complete",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("nannies")}
    if "video_screening_complete" in columns:
        op.drop_column("nannies", "video_screening_complete")
