from __future__ import annotations

import os
import socket
from datetime import timedelta

from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app import models
from app.utils.time import utc_now


def claim_scheduler_job(db: Session, job_name: str, *, lease_seconds: int) -> bool:
    """Allow only one app instance to start a scheduled job per lease window."""
    now = utc_now().replace(tzinfo=None)
    values = {
        "job_name": job_name,
        "locked_until": now + timedelta(seconds=max(1, lease_seconds)),
        "last_started_at": now,
        "owner": f"{socket.gethostname()}:{os.getpid()}",
    }
    dialect_name = db.get_bind().dialect.name
    insert = postgresql_insert if dialect_name == "postgresql" else sqlite_insert if dialect_name == "sqlite" else None
    if insert is None:
        existing = db.query(models.SchedulerJobLease).filter(models.SchedulerJobLease.job_name == job_name).first()
        if existing and existing.locked_until > now:
            return False
        if existing:
            existing.locked_until = values["locked_until"]
            existing.last_started_at = now
            existing.owner = values["owner"]
        else:
            db.add(models.SchedulerJobLease(**values))
        db.commit()
        return True

    statement = insert(models.SchedulerJobLease).values(**values).on_conflict_do_update(
        index_elements=["job_name"],
        set_={
            "locked_until": values["locked_until"],
            "last_started_at": now,
            "owner": values["owner"],
        },
        where=models.SchedulerJobLease.locked_until <= now,
    )
    claimed = db.execute(statement).rowcount == 1
    db.commit()
    return claimed
