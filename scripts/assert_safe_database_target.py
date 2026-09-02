"""Fail a deployment before startup if its database target is unsafe."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.utils.database_target import assert_safe_database_target


if __name__ == "__main__":
    database_name = assert_safe_database_target()
    print(f"Database safety check passed for {database_name}")
