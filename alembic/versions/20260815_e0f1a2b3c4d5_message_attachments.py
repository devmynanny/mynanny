"""Add private attachment metadata to communicator messages.

Revision ID: e0f1a2b3c4d5
Revises: d9e0f1a2b3c4
"""

from alembic import op
import sqlalchemy as sa

revision = "e0f1a2b3c4d5"
down_revision = "d9e0f1a2b3c4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("attachments_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("messages", "attachments_json")
