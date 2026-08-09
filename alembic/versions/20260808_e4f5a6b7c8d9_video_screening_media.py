"""Store nanny video screening clips and submission time.

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e4f5a6b7c8d9"
down_revision: Union[str, None] = "d3e4f5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("nannies", sa.Column("video_screening_json", sa.Text(), nullable=True))
    op.add_column("nannies", sa.Column("video_screening_submitted_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("nannies", "video_screening_submitted_at")
    op.drop_column("nannies", "video_screening_json")
