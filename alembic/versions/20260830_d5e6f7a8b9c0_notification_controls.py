"""add notification controls, delivery destinations and scheduler leases

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-08-30
"""

from alembic import op
import sqlalchemy as sa


revision = "d5e6f7a8b9c0"
down_revision = "c4d5e6f7a8b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column(
            "automated_notifications_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "app_settings",
        sa.Column(
            "notification_test_mode",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "app_settings",
        sa.Column("notification_test_phone", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "app_settings",
        sa.Column(
            "notification_volume_alert_threshold",
            sa.Integer(),
            nullable=False,
            server_default="30",
        ),
    )
    op.add_column(
        "notification_log",
        sa.Column("destination", sa.String(), nullable=True),
    )
    op.add_column(
        "notification_log",
        sa.Column(
            "test_redirected",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.create_table(
        "scheduler_job_leases",
        sa.Column("job_name", sa.String(length=100), nullable=False),
        sa.Column("locked_until", sa.DateTime(), nullable=False),
        sa.Column("last_started_at", sa.DateTime(), nullable=False),
        sa.Column("owner", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("job_name"),
    )


def downgrade() -> None:
    op.drop_table("scheduler_job_leases")
    op.drop_column("notification_log", "test_redirected")
    op.drop_column("notification_log", "destination")
    op.drop_column("app_settings", "notification_volume_alert_threshold")
    op.drop_column("app_settings", "notification_test_phone")
    op.drop_column("app_settings", "notification_test_mode")
    op.drop_column("app_settings", "automated_notifications_enabled")
