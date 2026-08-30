from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.services.notification_dispatch import claim_notification_dispatch


def _session():
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_dispatch_claim_allows_only_one_logical_notification():
    db = _session()
    try:
        assert claim_notification_dispatch(
            db,
            user_id=17,
            event_type="missed_check_in",
            reference_id=42,
        )
        assert not claim_notification_dispatch(
            db,
            user_id=17,
            event_type="missed_check_in",
            reference_id=42,
        )
        assert db.query(models.NotificationDispatchClaim).count() == 1
    finally:
        db.close()


def test_failed_legacy_delivery_still_blocks_scheduler_resend():
    db = _session()
    try:
        db.add(
            models.NotificationLog(
                user_id=17,
                event_type="booking_start_reminder",
                channel="whatsapp",
                status="failed",
                reference_id=42,
                message="Existing reminder awaiting the retry worker",
            )
        )
        db.commit()

        assert not claim_notification_dispatch(
            db,
            user_id=17,
            event_type="booking_start_reminder",
            reference_id=42,
        )
        assert db.query(models.NotificationDispatchClaim).count() == 0
    finally:
        db.close()


def test_explicit_keys_keep_base_and_overrun_payouts_distinct():
    db = _session()
    try:
        base_key = "payout:sent:17:42:base"
        overrun_key = "payout:sent:17:42:overrun"

        assert claim_notification_dispatch(
            db,
            user_id=17,
            event_type="payout_sent",
            reference_id=42,
            idempotency_key=base_key,
            legacy_message_marker="Your payment of",
        )
        assert claim_notification_dispatch(
            db,
            user_id=17,
            event_type="payout_sent",
            reference_id=42,
            idempotency_key=overrun_key,
            legacy_message_marker="Your overrun payment of",
        )
        assert not claim_notification_dispatch(
            db,
            user_id=17,
            event_type="payout_sent",
            reference_id=42,
            idempotency_key=base_key,
            legacy_message_marker="Your payment of",
        )
        assert db.query(models.NotificationDispatchClaim).count() == 2
    finally:
        db.close()
