import json
from typing import Any

from sqlalchemy.orm import Session

from app import models


DEFAULT_TRUST_BADGES = [
    {"key": "profile_ready", "label": "Profile ready", "required": True, "parent_visible": True},
    {"key": "identity", "label": "Identity verified", "required": True, "parent_visible": True},
    {"key": "video", "label": "Video introduced", "required": True, "parent_visible": True},
    {"key": "police", "label": "Police cleared", "required": True, "parent_visible": True},
    {"key": "training", "label": "My Nanny trained", "required": False, "parent_visible": True},
    {"key": "driver", "label": "Driver ready", "required": False, "parent_visible": True},
    {"key": "approved", "label": "My Nanny approved", "required": True, "parent_visible": True},
]


def get_trust_config(db: Session) -> list[dict[str, Any]]:
    row = db.query(models.AppSettings).filter(models.AppSettings.id == 1).first()
    if not row or not getattr(row, "trust_config_json", None):
        return [dict(item) for item in DEFAULT_TRUST_BADGES]
    try:
        badges = json.loads(row.trust_config_json).get("badges", [])
    except (TypeError, ValueError, AttributeError):
        return [dict(item) for item in DEFAULT_TRUST_BADGES]
    if not isinstance(badges, list) or not badges:
        return [dict(item) for item in DEFAULT_TRUST_BADGES]
    return badges


def _approved_document(profile: models.NannyProfile, attribute: str) -> bool:
    try:
        approvals = json.loads(getattr(profile, "document_approvals_json", None) or "{}")
    except (TypeError, ValueError):
        approvals = {}
    return bool((approvals.get(attribute) or {}).get("approved"))


def build_nanny_trust_badges(
    db: Session,
    nanny: models.Nanny,
    profile: models.NannyProfile,
    user: models.User,
) -> list[dict[str, Any]]:
    nationality = str(getattr(profile, "nationality", None) or "").strip().lower()
    identity_attr = "sa_id_document_url" if nationality == "south african" else "passport_document_url"
    identity_uploaded = bool(getattr(profile, identity_attr, None))
    identity_approved = identity_uploaded and _approved_document(profile, identity_attr)
    police_uploaded = bool(getattr(profile, "police_clearance_document_url", None))
    police_approved = police_uploaded and _approved_document(profile, "police_clearance_document_url")
    driver_uploaded = bool(getattr(profile, "drivers_license_document_url", None))
    driver_approved = driver_uploaded and _approved_document(profile, "drivers_license_document_url")
    application_approved = bool(
        getattr(nanny, "approved", False)
        and getattr(profile, "is_approved", 0)
        and getattr(profile, "application_status", None) == "approved"
    )
    facts = {
        "profile_ready": {
            "ready": bool(user.profile_photo_url and user.name and user.phone and profile.date_of_birth),
            "approved": application_approved,
            "detail": "Photo and core details",
            "href": "/profile",
        },
        "identity": {
            "ready": identity_uploaded,
            "approved": identity_approved,
            "detail": "SA ID document" if nationality == "south african" else "Passport document",
            "href": "/profile",
        },
        "video": {
            "ready": bool(getattr(nanny, "video_screening_complete", False)),
            "approved": application_approved,
            "detail": "Four interview answers",
            "href": "/interview",
        },
        "police": {
            "ready": police_uploaded,
            "approved": police_approved,
            "detail": "Clearance document",
            "href": "/profile",
        },
        "training": {
            "ready": str(getattr(profile, "my_nanny_training_status", None) or "").lower() == "yes",
            "approved": application_approved,
            "detail": "Training completed",
            "href": "/profile",
        },
        "driver": {
            "ready": driver_uploaded,
            "approved": driver_approved,
            "detail": "Licence document",
            "href": "/profile",
        },
        "approved": {
            "ready": application_approved,
            "approved": application_approved,
            "detail": "Final team review",
            "href": "/profile",
        },
    }
    results = []
    for configured in get_trust_config(db):
        key = str(configured.get("key") or "").strip()
        fact = facts.get(key, {"ready": False, "approved": False, "detail": "Admin verification", "href": "/profile"})
        results.append({
            "key": key,
            "label": str(configured.get("label") or key.replace("_", " ").title()),
            "required": bool(configured.get("required")),
            "parent_visible": bool(configured.get("parent_visible", True)),
            "ready": bool(fact["ready"]),
            "earned": bool(fact["ready"] and fact["approved"]),
            "detail": fact["detail"],
            "href": fact["href"],
        })
    return results


def nanny_meets_required_trust(badges: list[dict[str, Any]]) -> bool:
    return all(bool(item.get("earned")) for item in badges if item.get("required"))
