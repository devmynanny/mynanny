"""
Tests for POPIA upload access control: identity documents restricted to
owner/admin, photos to any authenticated user, anonymous access denied.
"""

from pathlib import Path

from app import models  # noqa: F401
from app.db import SessionLocal
from app.main import _upload_access_status

from tests.test_booking_flow_api import client, _auth, _seed_parent, _seed_nanny
from tests.test_accounting_reconciliation import _seed_admin

UPLOADS = Path(__file__).resolve().parents[1] / "app" / "static" / "uploads" / "nannies"


def _db():
    return SessionLocal()


# ---------------------------------------------------------------------------
# Unit tests on the policy function
# ---------------------------------------------------------------------------

def test_non_upload_paths_unaffected():
    assert _upload_access_status("/static/login.html", None) is None
    assert _upload_access_status("/health", None) is None


def test_anonymous_denied_on_any_upload():
    assert _upload_access_status("/static/uploads/nannies/5_ab.jpg", None) == 401
    assert _upload_access_status("/static/uploads/nannies/id_5_ab.pdf", None) == 401


def test_sensitive_document_owner_and_admin_only():
    owner = {"id": 5, "is_admin": False}
    stranger = {"id": 9, "is_admin": False}
    admin = {"id": 1, "is_admin": True}
    path = "/static/uploads/nannies/id_5_abcdef.pdf"
    assert _upload_access_status(path, owner) is None
    assert _upload_access_status(path, admin) is None
    assert _upload_access_status(path, stranger) == 403


def test_all_sensitive_prefixes_guarded():
    stranger = {"id": 9, "is_admin": False}
    for prefix in ("id", "passport", "permit", "police", "drivers_license",
                   "reference", "certificate"):
        path = f"/static/uploads/nannies/{prefix}_5_abcdef.pdf"
        assert _upload_access_status(path, stranger) == 403, prefix


def test_photos_visible_to_any_authenticated_user():
    stranger = {"id": 9, "is_admin": False}
    assert _upload_access_status("/static/uploads/nannies/5_ab.jpg", stranger) is None
    assert _upload_access_status("/static/uploads/parents/family_5_ab.jpg", stranger) is None


def test_family_photo_is_not_treated_as_sensitive_doc():
    # family_ is a photo prefix, deliberately not in the sensitive list;
    # visible to logged-in users (nannies see the family they work for).
    stranger = {"id": 9, "is_admin": False}
    assert _upload_access_status("/static/uploads/parents/family_5_ab.jpg", stranger) is None


# ---------------------------------------------------------------------------
# Integration: real requests through the middleware
# ---------------------------------------------------------------------------

def test_middleware_blocks_anonymous_and_stranger_on_real_file():
    db = _db()
    try:
        nanny = _seed_nanny(db)
        stranger = _seed_parent(db)
        admin = _seed_admin(db)

        UPLOADS.mkdir(parents=True, exist_ok=True)
        test_file = UPLOADS / f"id_{nanny.user_id}_testpopia.pdf"
        test_file.write_bytes(b"%PDF-1.4 test")
        try:
            url = f"/static/uploads/nannies/{test_file.name}"

            anon = client.get(url)
            assert anon.status_code == 401

            wrong = client.get(url, headers=_auth(stranger))
            assert wrong.status_code == 403

            ok = client.get(url, headers=_auth(admin))
            assert ok.status_code == 200
        finally:
            test_file.unlink(missing_ok=True)
    finally:
        db.close()
