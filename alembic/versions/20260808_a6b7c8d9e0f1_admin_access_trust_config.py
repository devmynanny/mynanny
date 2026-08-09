"""admin access levels and trust configuration

Revision ID: a6b7c8d9e0f1
Revises: f5a6b7c8d9e0
"""

from alembic import op
import sqlalchemy as sa

revision = "a6b7c8d9e0f1"
down_revision = "f5a6b7c8d9e0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("admin_profiles", sa.Column("access_level", sa.String(), nullable=False, server_default="operations"))
    op.add_column("admin_invites", sa.Column("access_level", sa.String(), nullable=False, server_default="operations"))
    op.add_column("app_settings", sa.Column("trust_config_json", sa.Text(), nullable=True))
    op.add_column("nanny_tags", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("qualifications", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade():
    op.drop_column("qualifications", "is_active")
    op.drop_column("nanny_tags", "is_active")
    op.drop_column("app_settings", "trust_config_json")
    op.drop_column("admin_invites", "access_level")
    op.drop_column("admin_profiles", "access_level")
