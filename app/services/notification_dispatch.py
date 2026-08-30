from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models


def claim_notification_dispatch(
    db: Session,
    *,
    user_id: int | None,
    event_type: str,
    reference_id: int | None,
    idempotency_key: str | None = None,
    legacy_message_marker: str | None = None,
) -> bool:
    """Atomically claim a logical notification before attempting delivery."""
    if user_id is None:
        return False

    legacy = db.query(models.NotificationLog.id).filter(
        models.NotificationLog.user_id == user_id,
        models.NotificationLog.event_type == event_type,
        models.NotificationLog.reference_id == reference_id,
        models.NotificationLog.status != "suppressed",
        models.NotificationLog.channel != "in_app",
    )
    if legacy_message_marker:
        legacy = legacy.filter(
            models.NotificationLog.message.contains(legacy_message_marker)
        )
    if legacy.first() is not None:
        return False

    key = idempotency_key or (
        f"notification:{event_type}:{user_id}:"
        f"{reference_id if reference_id is not None else 'none'}"
    )
    values = {
        "idempotency_key": key,
        "user_id": user_id,
        "event_type": event_type,
        "reference_id": reference_id,
    }
    dialect_name = db.get_bind().dialect.name
    if dialect_name == "postgresql":
        statement = (
            postgresql_insert(models.NotificationDispatchClaim)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["idempotency_key"])
        )
        return db.execute(statement).rowcount == 1
    if dialect_name == "sqlite":
        statement = (
            sqlite_insert(models.NotificationDispatchClaim)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["idempotency_key"])
        )
        return db.execute(statement).rowcount == 1

    try:
        with db.begin_nested():
            db.add(models.NotificationDispatchClaim(**values))
            db.flush()
        return True
    except IntegrityError:
        return False
