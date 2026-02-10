import json
from typing import Any, Dict, Optional, Iterable

from fastapi import Request
from sqlalchemy.orm import Session

from app import models


_SENSITIVE_KEYS = {"password", "password_hash", "token", "access_token", "auth", "authorization", "secret", "card"}


def _sanitize(obj: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not obj:
        return {}
    clean = {}
    for k, v in obj.items():
        if any(s in str(k).lower() for s in _SENSITIVE_KEYS):
            continue
        clean[k] = v
    return clean


def _json_dumps(value: Any) -> str:
    return json.dumps(value, default=str, separators=(",", ":"))


def _diff_keys(before: Dict[str, Any], after: Dict[str, Any]) -> Iterable[str]:
    keys = set(before.keys()) | set(after.keys())
    for key in sorted(keys):
        if key not in before or key not in after or before.get(key) != after.get(key):
            yield key


def log_audit(
    db: Session,
    actor_user: Optional[models.User],
    target_user_id: Optional[int],
    entity: str,
    entity_id: Optional[Any],
    action: str,
    before_obj: Optional[Dict[str, Any]] = None,
    after_obj: Optional[Dict[str, Any]] = None,
    changed_fields: Optional[Iterable[str]] = None,
    request: Optional[Request] = None,
) -> None:
    before = _sanitize(before_obj)
    after = _sanitize(after_obj)

    if changed_fields is None:
        changed_fields = list(_diff_keys(before, after))
    else:
        changed_fields = list(changed_fields)

    actor_user_id = getattr(actor_user, "id", None) if actor_user is not None else None
    if actor_user is not None and bool(getattr(actor_user, "is_admin", False)):
        actor_role = "admin"
    else:
        actor_role = getattr(actor_user, "role", None) if actor_user is not None else None

    if request is not None:
        impersonated_by = getattr(request.state, "impersonated_by_user_id", None)
        if impersonated_by:
            actor_user_id = impersonated_by
            actor_role = "admin"
        if actor_user is None:
            state_user = getattr(request.state, "user", None)
            if isinstance(state_user, dict):
                actor_user_id = actor_user_id or state_user.get("id")

    if actor_role is None:
        actor_role = "system" if actor_user_id is None else "user"

    ip = request.client.host if request and request.client else None
    user_agent = request.headers.get("user-agent") if request else None

    if actor_user_id is None and target_user_id is not None:
        actor_user_id = target_user_id
        if actor_role == "system":
            actor_role = "user"

    entity_type = entity or "unknown"
    event_type = action or "update"

    log = models.AuditLog(
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        target_user_id=target_user_id,
        entity=entity,
        entity_type=entity_type,
        event_type=event_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        action=action,
        before_json=_json_dumps(before) if before else None,
        after_json=_json_dumps(after) if after else None,
        changed_fields=_json_dumps(changed_fields) if changed_fields else None,
        ip=ip,
        user_agent=user_agent,
    )

    db.add(log)
    db.commit()


def log_profile_update(
    db: Session,
    actor_user: Optional[models.User],
    target_user_id: int,
    entity: str,
    entity_id: Optional[Any],
    before_obj: Dict[str, Any],
    after_obj: Dict[str, Any],
    request: Optional[Request] = None,
    action: str = "update",
) -> None:
    log_audit(
        db,
        actor_user,
        target_user_id,
        entity,
        entity_id,
        action,
        before_obj=before_obj,
        after_obj=after_obj,
        changed_fields=None,
        request=request,
    )


def log_booking_request_status_change(
    db: Session,
    actor_user: Optional[models.User],
    target_user_id: Optional[int],
    booking_request_id: Any,
    before_status: str,
    after_status: str,
    request: Optional[Request] = None,
    extra_after: Optional[Dict[str, Any]] = None,
) -> None:
    before = {"status": before_status}
    after = {"status": after_status}
    if extra_after:
        after.update(extra_after)
    log_audit(
        db,
        actor_user,
        target_user_id,
        entity="booking_requests",
        entity_id=booking_request_id,
        action="status_change",
        before_obj=before,
        after_obj=after,
        changed_fields=None,
        request=request,
    )


def log_booking_status_change(
    db: Session,
    actor_user: Optional[models.User],
    target_user_id: Optional[int],
    booking_id: Any,
    before_status: str,
    after_status: str,
    request: Optional[Request] = None,
    extra_after: Optional[Dict[str, Any]] = None,
) -> None:
    before = {"status": before_status}
    after = {"status": after_status}
    if extra_after:
        after.update(extra_after)
    log_audit(
        db,
        actor_user,
        target_user_id,
        entity="bookings",
        entity_id=booking_id,
        action="status_change",
        before_obj=before,
        after_obj=after,
        changed_fields=None,
        request=request,
    )
