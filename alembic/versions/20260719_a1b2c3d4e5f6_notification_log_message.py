"""Add notification_log.message for retryable notifications

Revision ID: a1b2c3d4e5f6
Revises: 6b5e6b603b3a
Create Date: 2026-07-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "6b5e6b603b3a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("notification_log") as batch_op:
        batch_op.add_column(sa.Column("message", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("notification_log") as batch_op:
        batch_op.drop_column("message")
