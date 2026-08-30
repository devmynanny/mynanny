from __future__ import annotations

import os
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app import models


FALSE_VALUES = {"0", "false", "no", "off"}


@dataclass(frozen=True)
class NotificationControls:
    configured_enabled: bool
    environment_enabled: bool
    effective_enabled: bool
    test_mode: bool
    test_phone: str | None
    volume_alert_threshold: int


def environment_notifications_enabled() -> bool:
    default = "false" if os.getenv("APP_ENV", "").strip().lower() == "production" else "true"
    return os.getenv("AUTOMATED_NOTIFICATIONS_ENABLED", default).strip().lower() not in FALSE_VALUES


def load_notification_controls(db: Session) -> NotificationControls:
    row = db.query(models.AppSettings).filter(models.AppSettings.id == 1).first()
    is_production = os.getenv("APP_ENV", "").strip().lower() == "production"
    configured_enabled = (
        bool(row.automated_notifications_enabled)
        if row is not None
        else not is_production
    )
    environment_enabled = environment_notifications_enabled()
    test_mode = bool(getattr(row, "notification_test_mode", False)) if row else False
    test_phone = (
        (getattr(row, "notification_test_phone", None) or "").strip() or None
        if row
        else None
    )
    threshold = int(getattr(row, "notification_volume_alert_threshold", 30) or 30) if row else 30
    return NotificationControls(
        configured_enabled=configured_enabled,
        environment_enabled=environment_enabled,
        effective_enabled=configured_enabled and environment_enabled,
        test_mode=test_mode,
        test_phone=test_phone,
        volume_alert_threshold=max(1, threshold),
    )
