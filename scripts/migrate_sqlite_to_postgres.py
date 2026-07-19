"""
One-off data migration: copy all rows from the SQLite database into Postgres.

Usage:
    python scripts/migrate_sqlite_to_postgres.py \
        --sqlite sqlite:///./nanny_app.db \
        --postgres postgresql://user:pass@host:5432/mynanny

Prerequisites:
- The Postgres schema must already exist: DATABASE_URL=<postgres> alembic upgrade head
- The target tables should be empty (the script aborts if users has rows,
  unless --force is passed).

The copy runs table-by-table in foreign-key-safe order derived from the
SQLAlchemy metadata, inside a single Postgres transaction: it either all
lands or nothing does. Sequences are resynced afterwards so new inserts
don't collide with copied primary keys.
"""

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Import models with a throwaway sqlite URL so app.db doesn't try to
# connect anywhere real at import time.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from sqlalchemy import create_engine, text  # noqa: E402

from app.db import Base  # noqa: E402
from app import models  # noqa: E402,F401
from app.models import audit_log, admin_invite, admin_profile  # noqa: E402,F401


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqlite", required=True, help="SQLite URL (source)")
    parser.add_argument("--postgres", required=True, help="Postgres URL (target)")
    parser.add_argument("--force", action="store_true",
                        help="Copy even if target users table is not empty")
    args = parser.parse_args()

    src_engine = create_engine(args.sqlite)
    dst_engine = create_engine(args.postgres)

    tables = list(Base.metadata.sorted_tables)  # FK-safe order

    with src_engine.connect() as src, dst_engine.begin() as dst:
        if not args.force:
            existing = dst.execute(text("SELECT COUNT(*) FROM users")).scalar()
            if existing:
                print(f"ABORT: target users table already has {existing} rows. "
                      f"Use --force to override.")
                return 1

        total = 0
        for table in tables:
            rows = src.execute(table.select()).mappings().all()
            if not rows:
                print(f"{table.name}: 0 rows")
                continue
            dst.execute(table.insert(), [dict(r) for r in rows])
            print(f"{table.name}: {len(rows)} rows copied")
            total += len(rows)

        # Resync Postgres sequences for integer primary keys.
        for table in tables:
            pk_cols = [c for c in table.primary_key.columns]
            if len(pk_cols) != 1:
                continue
            col = pk_cols[0]
            if not col.autoincrement or str(col.type) not in ("INTEGER", "BIGINT"):
                continue
            dst.execute(text(
                "SELECT setval(pg_get_serial_sequence(:t, :c), "
                "COALESCE((SELECT MAX(" + col.name + ") FROM " + table.name + "), 0) + 1, false)"
            ), {"t": table.name, "c": col.name})

        print(f"DONE: {total} rows copied across {len(tables)} tables.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
