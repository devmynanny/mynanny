"""
Seed demo nannies near Louwlardia, Centurion for end-to-end testing.

Creates fully search-eligible nannies (approved, documents complete, located
near Louwlardia) with availability for the next 7 days, 06:00-20:00 SA time.

Usage:
    # Against production (get External Database URL from Render dashboard):
    DATABASE_URL="postgres://..." python scripts/seed_demo_nannies.py

    # Against local SQLite (default):
    python scripts/seed_demo_nannies.py

Idempotent: skips any demo nanny whose email already exists.
Cleanup: python scripts/seed_demo_nannies.py --delete
"""
import os
import sys
from datetime import date, datetime, time, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# app.db reads DATABASE_URL at import time, so env must be set before import.
from app.db import SessionLocal, engine  # noqa: E402
from app import models  # noqa: E402
from app.security import hash_password  # noqa: E402

DEMO_PASSWORD = "Demo1234!"

# Louwlardia, Centurion (approx). Small offsets so distances differ.
DEMO_NANNIES = [
    {
        "name": "Thandi Demo Mokoena",
        "nickname": "Thandi",
        "last_initial": "M",
        "email": "demo.nanny1@mynanny.test",
        "phone": "+27820000001",
        "lat": -25.9020, "lng": 28.1870,
        "dob": date(1992, 3, 14),
        "bio": "Warm, energetic nanny with 8 years of experience caring for toddlers and school-age children.",
        "languages": ["English", "Zulu", "Sotho"],
        "qualifications": ["First aid and CPR certificate", "Childcare / Nanny certificate"],
        "has_drivers_license": True,
        "has_own_car": True,
        "dog_preference": "loves_dogs",
    },
    {
        "name": "Lerato Demo Nkosi",
        "nickname": "Lerato",
        "last_initial": "N",
        "email": "demo.nanny2@mynanny.test",
        "phone": "+27820000002",
        "lat": -25.8960, "lng": 28.1930,
        "dob": date(1988, 11, 2),
        "bio": "Experienced night nanny and newborn specialist. Calm, reliable, and great with routines.",
        "languages": ["English", "Tswana"],
        "qualifications": ["Night Nurse / night nanny certificate", "Pediatric CPR/First aid"],
        "has_drivers_license": True,
        "has_own_car": False,
        "dog_preference": "fine_with_dogs",
    },
    {
        "name": "Naledi Demo Dlamini",
        "nickname": "Naledi",
        "last_initial": "D",
        "email": "demo.nanny3@mynanny.test",
        "phone": "+27820000003",
        "lat": -25.9080, "lng": 28.1810,
        "dob": date(1997, 6, 25),
        "bio": "ECD-qualified nanny who loves educational play. Currently studying part time.",
        "languages": ["English", "Afrikaans", "Xhosa"],
        "qualifications": ["ECD Certificate", "First aid and CPR certificate"],
        "has_drivers_license": False,
        "has_own_car": False,
        "dog_preference": "fine_with_dogs",
    },
]

AVAILABILITY_DAYS = 7
AVAIL_START = time(6, 0)   # SA local
AVAIL_END = time(20, 0)    # SA local
SA_UTC_OFFSET = timedelta(hours=2)


def _iso_z(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def seed(db):
    created = []
    for spec in DEMO_NANNIES:
        existing = db.query(models.User).filter(models.User.email == spec["email"]).first()
        if existing:
            print(f"skip: {spec['email']} already exists (user id {existing.id})")
            continue

        user = models.User(
            name=spec["name"],
            role="nanny",
            email=spec["email"],
            password_hash=hash_password(DEMO_PASSWORD),
            is_admin=False,
            is_active=True,
            phone=spec["phone"],
            nickname=spec["nickname"],
            last_initial=spec["last_initial"],
        )
        db.add(user)
        db.flush()

        nanny = models.Nanny(
            user_id=user.id,
            approved=True,
            is_suspended=False,
            profile_complete=True,
            availability_complete=True,
            banking_complete=True,
        )
        db.add(nanny)
        db.flush()

        profile = models.NannyProfile(
            nanny_id=nanny.id,
            bio=spec["bio"],
            date_of_birth=spec["dob"],
            nationality="South African",
            gender="Female",
            sa_id_number=f"920314{user.id:07d}",
            sa_id_document_url="/static/uploads/id_demo_placeholder.pdf",
            police_clearance_status="yes",
            has_drivers_license=spec["has_drivers_license"],
            has_own_car=spec["has_own_car"],
            dog_preference=spec["dog_preference"],
            job_type="both",
            lat=spec["lat"],
            lng=spec["lng"],
            is_approved=1,
            application_status="approved",
            approved_at=datetime.utcnow().isoformat(),
            formatted_address="Louwlardia, Centurion, Gauteng, South Africa",
            suburb="Louwlardia",
            city="Centurion",
            province="Gauteng",
            country="South Africa",
        )
        langs = db.query(models.Language).filter(models.Language.name.in_(spec["languages"])).all()
        quals = db.query(models.Qualification).filter(models.Qualification.name.in_(spec["qualifications"])).all()
        profile.languages = langs
        profile.qualifications = quals
        db.add(profile)
        db.flush()

        start_day = date.today() + timedelta(days=1)
        for offset in range(AVAILABILITY_DAYS):
            d = start_day + timedelta(days=offset)
            local_start = datetime.combine(d, AVAIL_START)
            local_end = datetime.combine(d, AVAIL_END)
            db.add(models.NannyAvailability(
                nanny_id=nanny.id,
                date=d,
                start_time=AVAIL_START,
                end_time=AVAIL_END,
                start_dt=_iso_z(local_start - SA_UTC_OFFSET),
                end_dt=_iso_z(local_end - SA_UTC_OFFSET),
                type="available",
                is_available=True,
                created_by="admin",
                notes="demo seed",
            ))

        created.append((spec["email"], user.id, nanny.id))

    db.commit()
    return created


def delete(db):
    emails = [s["email"] for s in DEMO_NANNIES]
    users = db.query(models.User).filter(models.User.email.in_(emails)).all()
    for user in users:
        nanny = db.query(models.Nanny).filter(models.Nanny.user_id == user.id).first()
        if nanny:
            profile = db.query(models.NannyProfile).filter(models.NannyProfile.nanny_id == nanny.id).first()
            if profile:
                profile.languages = []
                profile.qualifications = []
                profile.tags = []
                db.flush()
                db.delete(profile)
            db.query(models.NannyAvailability).filter(models.NannyAvailability.nanny_id == nanny.id).delete()
            db.delete(nanny)
        db.delete(user)
        print(f"deleted: {user.email}")
    db.commit()


def main():
    print(f"database: {engine.url.render_as_string(hide_password=True)} ({engine.dialect.name})")
    db = SessionLocal()
    try:
        if "--delete" in sys.argv:
            delete(db)
            return
        created = seed(db)
        if created:
            print(f"\ncreated {len(created)} demo nannies (password for all: {DEMO_PASSWORD}):")
            for email, user_id, nanny_id in created:
                print(f"  {email}  user_id={user_id} nanny_id={nanny_id}")
            print("\navailability: next 7 days, 06:00-20:00 SA time, near Louwlardia, Centurion")
            print("cleanup before real launch: python scripts/seed_demo_nannies.py --delete")
    finally:
        db.close()


if __name__ == "__main__":
    main()
