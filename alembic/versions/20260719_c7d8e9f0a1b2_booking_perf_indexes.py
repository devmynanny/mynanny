"""Performance indexes for booking list/calendar queries

Revision ID: c7d8e9f0a1b2
Revises: a1b2c3d4e5f6
Create Date: 2026-07-19

The parent/nanny/admin calendars filter booking_requests by parent_user_id,
group_id and nanny_id, and bookings by booking_request_id and client_user_id.
None of these had indexes, so every calendar load did sequential scans.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c7d8e9f0a1b2"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEXES = [
    ("br_parent_user_id_idx", "booking_requests", ["parent_user_id"]),
    ("br_group_id_idx", "booking_requests", ["group_id"]),
    ("br_nanny_id_status_idx", "booking_requests", ["nanny_id", "status"]),
    ("bookings_request_id_idx", "bookings", ["booking_request_id"]),
    ("bookings_client_user_id_idx", "bookings", ["client_user_id"]),
    ("bookings_nanny_id_starts_at_idx", "bookings", ["nanny_id", "starts_at"]),
]


def upgrade() -> None:
    for name, table, cols in INDEXES:
        op.create_index(name, table, cols, if_not_exists=True)


def downgrade() -> None:
    for name, table, _ in INDEXES:
        op.drop_index(name, table_name=table, if_exists=True)
