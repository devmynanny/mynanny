import io
import mimetypes
import os
from pathlib import Path, PurePosixPath
from typing import BinaryIO


MEDIA_PREFIX = "/media/"
DEFAULT_LOCAL_UPLOAD_ROOT = Path(__file__).resolve().parents[1] / "static" / "uploads"
LOCAL_UPLOAD_ROOT = DEFAULT_LOCAL_UPLOAD_ROOT


def _local_upload_root() -> Path:
    """Allow automated tests to keep uploaded media outside the app tree."""
    configured = (os.getenv("LOCAL_UPLOAD_ROOT") or "").strip()
    return Path(configured) if configured else Path(LOCAL_UPLOAD_ROOT)


def _backend() -> str:
    return (os.getenv("STORAGE_BACKEND") or "local").strip().lower()


def _safe_key(key: str) -> str:
    normalized = str(PurePosixPath(key.strip().lstrip("/")))
    if not normalized or normalized == "." or normalized.startswith("../") or "/../" in normalized:
        raise ValueError("Invalid media key")
    return normalized


def media_url(key: str) -> str:
    return f"{MEDIA_PREFIX}{_safe_key(key)}"


def key_from_media_url(url: str) -> str | None:
    return _safe_key(url[len(MEDIA_PREFIX):]) if url.startswith(MEDIA_PREFIX) else None


def _s3_client():
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=os.getenv("S3_ENDPOINT_URL") or None,
        region_name=os.getenv("S3_REGION") or None,
        aws_access_key_id=os.getenv("S3_ACCESS_KEY_ID") or None,
        aws_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY") or None,
    )


def _bucket() -> str:
    value = (os.getenv("S3_BUCKET") or "").strip()
    if not value:
        raise RuntimeError("S3_BUCKET is required when STORAGE_BACKEND=s3")
    return value


def store_bytes(key: str, data: bytes, content_type: str | None = None) -> str:
    safe_key = _safe_key(key)
    if _backend() == "s3":
        extra = {"ContentType": content_type} if content_type else {}
        _s3_client().put_object(Bucket=_bucket(), Key=safe_key, Body=data, **extra)
    else:
        destination = _local_upload_root() / safe_key
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    return media_url(safe_key)


def store_file(key: str, source: Path, content_type: str | None = None) -> str:
    safe_key = _safe_key(key)
    if _backend() == "s3":
        extra = {"ContentType": content_type} if content_type else None
        _s3_client().upload_file(str(source), _bucket(), safe_key, ExtraArgs=extra or {})
    else:
        destination = _local_upload_root() / safe_key
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
    return media_url(safe_key)


def open_media(key: str) -> tuple[BinaryIO, str | None, int | None]:
    safe_key = _safe_key(key)
    if _backend() == "s3":
        result = _s3_client().get_object(Bucket=_bucket(), Key=safe_key)
        return result["Body"], result.get("ContentType"), result.get("ContentLength")
    path = _local_upload_root() / safe_key
    data = path.read_bytes()
    return io.BytesIO(data), mimetypes.guess_type(safe_key)[0], len(data)


def temporary_provider_url(key: str, expires_seconds: int = 900) -> str:
    """Create a short-lived URL a messaging provider can fetch server-side."""
    safe_key = _safe_key(key)
    if _backend() != "s3":
        raise RuntimeError("Outbound messaging attachments require STORAGE_BACKEND=s3")
    return _s3_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": _bucket(), "Key": safe_key},
        ExpiresIn=expires_seconds,
    )
