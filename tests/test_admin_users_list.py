from datetime import datetime

from app import models
from app.db import SessionLocal
from tests.test_booking_flow_api import _auth, client


def _admin(db) -> models.User:
    stamp = datetime.utcnow().timestamp()
    user = models.User(
        name="Users List Admin",
        role="admin",
        email=f"users_list_admin_{stamp}@example.com",
        password_hash="x",
        is_admin=True,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_admin_users_searches_nanny_identity_without_loading_every_user():
    db = SessionLocal()
    try:
        admin = _admin(db)
        stamp = str(datetime.utcnow().timestamp()).replace(".", "")
        nanny_user = models.User(
            name="Admin Search Nanny",
            role="nanny",
            email=f"admin_search_nanny_{stamp}@example.com",
            password_hash="x",
            is_active=True,
        )
        db.add(nanny_user)
        db.flush()
        nanny = models.Nanny(user_id=nanny_user.id, approved=True)
        db.add(nanny)
        db.flush()
        db.add(
            models.NannyProfile(
                nanny_id=nanny.id,
                sa_id_number=f"900101{stamp[-7:]}",
                passport_number=f"PASS-{stamp[-8:]}",
            )
        )
        db.commit()

        response = client.get(
            f"/admin/users?q=PASS-{stamp[-8:]}",
            headers=_auth(admin),
        )

        assert response.status_code == 200, response.text
        rows = response.json()
        assert [row["id"] for row in rows] == [nanny_user.id]
        assert rows[0]["approved"] is True
        assert rows[0]["passport_number"] == f"PASS-{stamp[-8:]}"
    finally:
        db.close()


def test_admin_users_searches_parent_profile_phone():
    db = SessionLocal()
    try:
        admin = _admin(db)
        stamp = str(datetime.utcnow().timestamp()).replace(".", "")
        parent = models.User(
            name="Admin Search Parent",
            role="parent",
            email=f"admin_search_parent_{stamp}@example.com",
            password_hash="x",
            is_active=True,
        )
        db.add(parent)
        db.flush()
        profile_phone = f"+2782{stamp[-7:]}"
        db.add(models.ParentProfile(user_id=parent.id, phone=profile_phone))
        db.commit()

        response = client.get(
            f"/admin/users?q={profile_phone[-7:]}",
            headers=_auth(admin),
        )

        assert response.status_code == 200, response.text
        rows = response.json()
        assert [row["id"] for row in rows] == [parent.id]
        assert rows[0]["phone"] == profile_phone
    finally:
        db.close()
