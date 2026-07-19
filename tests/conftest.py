import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Hermetic test database.
#
# app/config.py reads DATABASE_URL at import time and app/main.py creates the
# full schema (Base.metadata.create_all + ensure_* migrations) on import, so
# pointing DATABASE_URL at a fresh temp file BEFORE any app import gives every
# test run a clean, fully-migrated database.
#
# Previously tests ran against the real dev DB (nanny_app.db), seeding and
# deleting rows in it. Set MYNANNY_TEST_USE_REAL_DB=1 to restore that behavior
# if you ever need to debug against real data.
if not os.environ.get("MYNANNY_TEST_USE_REAL_DB"):
    _tmpdir = tempfile.mkdtemp(prefix="mynanny_test_")
    os.environ["DATABASE_URL"] = f"sqlite:///{_tmpdir}/test.db"
