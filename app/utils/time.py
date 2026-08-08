from datetime import datetime, timezone


def utc_now() -> datetime:
    """Naive UTC now. Drop-in replacement for the deprecated datetime.utcnow()."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
