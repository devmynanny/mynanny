import json
from typing import Optional, Dict, Any

from fastapi import Request
from sqlalchemy.orm import Session

from app import models


def _json_dumps(value: Dict[str, Any]) -> str:
    return json.dumps(value, default=str, separators=(",", ":"))


def log_audit(
    db: Session,
    request: Request,
    event_type: str,
    entity: str,
    entity_id: Optional[int],
    target_user_id: Optional[int],
    before_dict: Optional[Dict[str, Any]],
    after_dict: Optional[Dict[str, Any]],
) -> None:
    before = before_dict or {}
    after = after_dict or {}

    changed_fields = []
    for key in sorted(set(before.keys()) | set(after.keys())):
        if key not in before or key not in after or before.get(key) != after.get(key):
            changed_fields.append(key)

    if not changed_fields:
        return

    actor = getattr(request.state, "user", None)
    actor_user_id = actor.get("id") if isinstance(actor, dict) else None
    if actor_user_id is None:
        return

    impersonated_by = getattr(request.state, "impersonated_by_user_id", None)
    ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    log = models.AuditLog(
        actor_user_id=actor_user_id,
        impersonated_by_user_id=impersonated_by,
        target_user_id=target_user_id,
        event_type=event_type,
        entity=entity,
        entity_id=entity_id,
        before_json=_json_dumps(before) if before else None,
        after_json=_json_dumps(after) if after else None,
        changed_fields_json=_json_dumps(changed_fields),
        ip=ip,
        user_agent=user_agent,
    )

    db.add(log)
    db.commit()
