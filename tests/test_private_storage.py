from pathlib import Path

from app.services import storage
from app.main import _upload_access_status


def test_local_storage_round_trip(monkeypatch, tmp_path):
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setattr(storage, "LOCAL_UPLOAD_ROOT", tmp_path)

    url = storage.store_bytes("nannies/id_42_test.pdf", b"%PDF-test", "application/pdf")
    stream, content_type, size = storage.open_media("nannies/id_42_test.pdf")

    assert url == "/media/nannies/id_42_test.pdf"
    assert stream.read() == b"%PDF-test"
    assert content_type == "application/pdf"
    assert size == 9


def test_media_key_rejects_path_traversal():
    try:
        storage.store_bytes("../secret.txt", b"no")
    except ValueError:
        pass
    else:
        raise AssertionError("path traversal key should be rejected")


def test_private_media_uses_existing_owner_access_rules():
    path = "/media/nannies/passport_42_test.pdf"
    assert _upload_access_status(path, None) == 401
    assert _upload_access_status(path, {"id": 41, "is_admin": False}) == 403
    assert _upload_access_status(path, {"id": 42, "is_admin": False}) is None
    assert _upload_access_status(path, {"id": 1, "is_admin": True}) is None


def test_signed_in_users_can_view_non_sensitive_profile_media():
    assert _upload_access_status("/media/nannies/42_photo.jpg", None) == 401
    assert _upload_access_status("/media/nannies/42_photo.jpg", {"id": 7, "is_admin": False}) is None
