from datetime import timedelta
from sqlalchemy import func

from app import models
from app.db import SessionLocal
from app.utils.time import utc_now
from tests.test_accounting_reconciliation import _seed_admin
from tests.test_booking_flow_api import _auth, _seed_nanny, _seed_parent, client


def test_admin_parent_profile_returns_latest_completed_booking_questionnaire():
    db = SessionLocal()
    try:
        admin = _seed_admin(db)
        parent = _seed_parent(db)
        nanny = _seed_nanny(db)
        start = utc_now() + timedelta(days=5)
        notes = "\n".join(
            [
                "Additional notes: Please use the side gate",
                "Nanny responsibilities: Homework and dinner",
                "Adult present at address: No adult will be present",
                "Reason for booking: Work function",
                "Children present: 2",
                "Meal arrangement: We will provide food",
                "Foods not allowed in home: Peanuts",
                "Dogs at home: One calm Labrador",
                "House upkeep disclaimer understood: Yes",
                "Medicine disclaimer understood: Yes",
                "Additional hours disclaimer understood: Yes",
                "After-17:00 transport disclaimer understood: Yes",
            ]
        )
        request = models.BookingRequest(
            id=int(db.query(func.coalesce(func.max(models.BookingRequest.id), 0)).scalar() or 0) + 1,
            parent_user_id=parent.id,
            nanny_id=nanny.id,
            status="tbc",
            payment_status="pending_payment",
            requested_starts_at=start,
            requested_ends_at=start + timedelta(hours=4),
            start_dt=start.isoformat(),
            end_dt=(start + timedelta(hours=4)).isoformat(),
            client_notes=notes,
            requested_nannies_count=2,
        )
        db.add(request)
        db.commit()
        db.refresh(request)

        response = client.get(f"/admin/parents/{parent.id}/profile", headers=_auth(admin))

        assert response.status_code == 200
        latest = response.json()["latest_booking_form"]
        assert latest["request_id"] == request.id
        assert latest["responsibilities"] == "Homework and dinner"
        assert latest["kids_count"] == 2
        assert latest["food_restrictions"] == "Peanuts"
        assert latest["disclaimer_transport"] is True
        assert latest["requested_nannies_count"] == 2
    finally:
        db.close()
