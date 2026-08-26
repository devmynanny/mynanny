from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


V2_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = V2_ROOT.parent
STATE_ROOT = V2_ROOT / ".e2e-state"


def prepare_environment() -> None:
    shutil.rmtree(STATE_ROOT, ignore_errors=True)
    STATE_ROOT.mkdir(parents=True, exist_ok=True)

    isolated = {
        "APP_ENV": "test",
        "DATABASE_URL": f"sqlite:///{STATE_ROOT / 'mynanny-e2e.sqlite3'}",
        "JWT_SECRET": "local-e2e-jwt-secret-not-for-production",
        "ADMIN_API_KEY": "local-e2e-admin-key",
        "BOOTSTRAP_ADMIN_EMAIL": "admin.e2e@example.test",
        "BOOTSTRAP_ADMIN_PASSWORD": "AdminE2E!234",
        "STORAGE_BACKEND": "local",
        "LOCAL_UPLOAD_ROOT": str(STATE_ROOT / "uploads"),
        "TWILIO_ACCOUNT_SID": "",
        "TWILIO_AUTH_TOKEN": "",
        "TWILIO_WHATSAPP_FROM": "",
        "PAYSTACK_SECRET_KEY": "",
        "S3_ENDPOINT_URL": "",
        "S3_REGION": "",
        "S3_ACCESS_KEY_ID": "",
        "S3_SECRET_ACCESS_KEY": "",
        "S3_BUCKET": "",
    }
    os.environ.update(isolated)
    sys.path.insert(0, str(PROJECT_ROOT))


if __name__ == "__main__":
    prepare_environment()

    import uvicorn

    uvicorn.run(
        "app.main:app",
        app_dir=str(PROJECT_ROOT),
        host="127.0.0.1",
        port=8011,
        reload=False,
        log_level="warning",
    )
