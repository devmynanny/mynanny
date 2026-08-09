from __future__ import annotations

import json
from datetime import date, datetime

from sqlalchemy.orm import Session

from app import models
from app.services.notifications import notify
from app.utils.time import utc_now


def _expiry(value: str | None) -> date | None:
    try:
        return date.fromisoformat(str(value or "").strip()[:10])
    except ValueError:
        return None


def _already_notified(db: Session, user_id: int, event_type: str, expiry: date) -> bool:
    marker = expiry.isoformat()
    return db.query(models.NotificationLog).filter(
        models.NotificationLog.user_id == user_id,
        models.NotificationLog.event_type == event_type,
        models.NotificationLog.message.contains(marker),
    ).first() is not None


def run_passport_compliance(db: Session) -> dict[str, int]:
    today = date.today()
    warned = 0
    suspended = 0
    rows = (
        db.query(models.Nanny, models.NannyProfile)
        .join(models.NannyProfile, models.NannyProfile.nanny_id == models.Nanny.id)
        .all()
    )
    for nanny, profile in rows:
        if str(profile.nationality or "").strip().lower() == "south african":
            continue
        try:
            approvals = json.loads(profile.document_approvals_json or "{}")
        except Exception:
            approvals = {}
        approval = approvals.get("passport_document_url") or {}
        approved_expiry = _expiry(approval.get("approved_expiry"))
        previous_expiry = _expiry(approval.get("previous_approved_expiry"))
        expiry = approved_expiry if approval.get("approved") else previous_expiry or _expiry(profile.passport_expiry)
        if not expiry:
            continue
        days = (expiry - today).days
        if 0 < days <= 90 and not _already_notified(
            db, nanny.user_id, "passport_expiry_warning", expiry
        ):
            notify(
                db,
                nanny.user_id,
                "passport_expiry_warning",
                f"Your passport expires on {expiry.isoformat()}. Upload a renewed passport and expiry date before then. Your account will be suspended if no valid, admin-approved passport is on file.",
                reference_id=profile.id,
            )
            warned += 1
        if days <= 0:
            valid = (
                bool(approval.get("approved"))
                and approved_expiry == _expiry(profile.passport_expiry)
                and approved_expiry > today
            )
            if not valid and not nanny.is_suspended:
                nanny.is_suspended = True
                nanny.suspended_at = utc_now()
                nanny.suspension_reason = "Passport expired or renewed passport awaiting admin approval"
                notify(
                    db,
                    nanny.user_id,
                    "passport_expired_suspension",
                    f"Your My Nanny account has been suspended because your passport expired on {expiry.isoformat()}. Upload a valid passport and expiry date for admin approval.",
                    reference_id=profile.id,
                )
                suspended += 1
    db.commit()
    return {"warned": warned, "suspended": suspended}
