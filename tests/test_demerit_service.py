from datetime import datetime, timedelta

import pytest

from app import models
from app.db import SessionLocal
from app.services.demerit import apply_cancellation_weight, apply_demerit, apply_no_show


def _db_session():
    return SessionLocal()


def _seed_nanny(db):
    user = models.User(
        name="Nanny User",
        role="nanny",
        email=f"nanny_{datetime.utcnow().timestamp()}@example.com",
        password_hash="x",
        is_admin=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    nanny = models.Nanny(user_id=user.id, approved=True)
    db.add(nanny)
    db.commit()
    db.refresh(nanny)
    return nanny


def _cleanup_nanny(db, nanny_id: int, user_id: int):
    db.query(models.NannyDemeritLog).filter(models.NannyDemeritLog.nanny_id == nanny_id).delete()
    db.query(models.Nanny).filter(models.Nanny.id == nanny_id).delete()
    db.query(models.User).filter(models.User.id == user_id).delete()
    db.commit()


def test_demerit_stacking_across_events():
    db = _db_session()
    nanny = _seed_nanny(db)
    try:
        apply_demerit(db, nanny.id, "scenario_b_cancel", 0.05, 0.75, booking_id=1)
        apply_demerit(db, nanny.id, "scenario_c_cancel", 0.10, 1.0, booking_id=2)

        updated = db.query(models.Nanny).filter(models.Nanny.id == nanny.id).first()
        assert float(updated.rating_demerit_pct) == pytest.approx(0.15)

        logs = (
            db.query(models.NannyDemeritLog)
            .filter(models.NannyDemeritLog.nanny_id == nanny.id)
            .order_by(models.NannyDemeritLog.id.asc())
            .all()
        )
        assert len(logs) == 2
        assert float(logs[0].cumulative_demerit_pct) == pytest.approx(0.05)
        assert float(logs[1].cumulative_demerit_pct) == pytest.approx(0.15)
    finally:
        _cleanup_nanny(db, nanny.id, nanny.user_id)
        db.close()


def test_suspension_trigger_at_exactly_2_5_boundary():
    db = _db_session()
    nanny = _seed_nanny(db)
    try:
        # base rating defaults to 5.0 when no reviews; demerit 0.5 -> displayed 2.5, no suspension
        apply_demerit(db, nanny.id, "scenario_c_cancel", 0.50, 1.0, booking_id=11)
        updated = db.query(models.Nanny).filter(models.Nanny.id == nanny.id).first()
        assert bool(updated.is_suspended) is False

        # any additional demerit pushes below 2.5 and should suspend
        apply_demerit(db, nanny.id, "scenario_b_cancel", 0.01, 0.75, booking_id=12)
        updated = db.query(models.Nanny).filter(models.Nanny.id == nanny.id).first()
        assert bool(updated.is_suspended) is True
        assert updated.suspension_reason == "rating_below_threshold"
        assert updated.suspended_at is not None
    finally:
        _cleanup_nanny(db, nanny.id, nanny.user_id)
        db.close()


def test_cancellation_rate_threshold_at_exactly_5_0():
    db = _db_session()
    nanny = _seed_nanny(db)
    try:
        now = datetime.utcnow()
        weights = [1.0, 1.0, 1.0, 1.0, 1.0]
        running = 0.0
        for idx, w in enumerate(weights, start=1):
            running += w
            db.add(
                models.NannyDemeritLog(
                    nanny_id=nanny.id,
                    booking_id=idx,
                    reason="scenario_c_cancel",
                    demerit_pct=0.0,
                    weight=w,
                    cumulative_demerit_pct=running,
                    applied_at=now - timedelta(days=1),
                    applied_by="system",
                )
            )
        db.commit()

        apply_cancellation_weight(db, nanny.id, weight=0.5)
        updated = db.query(models.Nanny).filter(models.Nanny.id == nanny.id).first()
        assert bool(updated.admin_review_flagged) is True
        assert int(updated.cancellation_count) == 1
    finally:
        _cleanup_nanny(db, nanny.id, nanny.user_id)
        db.close()


def test_no_show_count_triggers_fitness_review_at_2():
    db = _db_session()
    nanny = _seed_nanny(db)
    try:
        apply_no_show(db, nanny.id, booking_id=101)
        first = db.query(models.Nanny).filter(models.Nanny.id == nanny.id).first()
        assert int(first.no_show_count) == 1
        assert bool(first.admin_review_flagged) is False

        apply_no_show(db, nanny.id, booking_id=102)
        second = db.query(models.Nanny).filter(models.Nanny.id == nanny.id).first()
        assert int(second.no_show_count) == 2
        assert bool(second.admin_review_flagged) is True
    finally:
        _cleanup_nanny(db, nanny.id, nanny.user_id)
        db.close()
