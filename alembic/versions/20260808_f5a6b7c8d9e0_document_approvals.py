"""Add document approval metadata to nanny profiles."""

from alembic import op
import sqlalchemy as sa

revision = "f5a6b7c8d9e0"
down_revision = "e4f5a6b7c8d9"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("nanny_profiles", sa.Column("document_approvals_json", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("nanny_profiles", "document_approvals_json")
