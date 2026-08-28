"""
Seed clearly labelled demo nannies in the live test-parent areas.

Creates fully search-eligible nannies (approved, documents complete, located
near Sandhurst or Centurion) with availability for the next 30 days,
06:00-22:00 SA time.

Usage:
    # Against production (get External Database URL from Render dashboard):
    DATABASE_URL="postgres://..." python scripts/seed_demo_nannies.py

    # Against local SQLite (default):
    python scripts/seed_demo_nannies.py

Idempotent: creates or refreshes only the three fixed @mynanny.test accounts.
Cleanup: python scripts/seed_demo_nannies.py --delete
"""
import json
import os
import sys
from datetime import date, datetime, time, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# app.db reads DATABASE_URL at import time, so env must be set before import.
from app.db import SessionLocal, engine  # noqa: E402
from app import models  # noqa: E402
from app.security import hash_password  # noqa: E402

DEMO_PASSWORD = "Demo1234!"
DEMO_PROFILE_PHOTO_URL = "https://mynanny-v2.onrender.com/hero-nanny-feeding-v2.png"
DEMO_DOCUMENT_URL = "https://mynanny-v2.onrender.com/logo.jpg"

DEMO_NANNIES = [
    {
        "name": "Thandi Demo Mokoena",
        "nickname": "Thandi",
        "last_initial": "M",
        "email": "demo.nanny1@mynanny.test",
        "phone": "+27820000001",
        "lat": -26.1070, "lng": 28.0520,
        "formatted_address": "Sandhurst, Sandton, Gauteng, South Africa",
        "suburb": "Sandhurst",
        "city": "Sandton",
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
        "lat": -26.1150, "lng": 28.0420,
        "formatted_address": "Sandton, Gauteng, South Africa",
        "suburb": "Sandton",
        "city": "Sandton",
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
        "formatted_address": "Louwlardia, Centurion, Gauteng, South Africa",
        "suburb": "Louwlardia",
        "city": "Centurion",
        "dob": date(1997, 6, 25),
        "bio": "ECD-qualified nanny who loves educational play. Currently studying part time.",
        "languages": ["English", "Afrikaans", "Xhosa"],
        "qualifications": ["ECD Certificate", "First aid and CPR certificate"],
        "has_drivers_license": False,
        "has_own_car": False,
        "dog_preference": "fine_with_dogs",
    },
]

AVAILABILITY_DAYS = 30
AVAIL_START = time(6, 0)   # SA local
AVAIL_END = time(22, 0)    # SA local
SA_UTC_OFFSET = timedelta(hours=2)


def _iso_z(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def seed(db):
    seeded = []
    for index, spec in enumerate(DEMO_NANNIES, start=1):
        user = db.query(models.User).filter(models.User.email == spec["email"]).first()
        action = "refreshed"
        if not user:
            action = "created"
            user = models.User(email=spec["email"], password_hash=hash_password(DEMO_PASSWORD))
            db.add(user)

        user.name = spec["name"]
        user.role = "nanny"
        user.is_admin = False
        user.is_active = True
        user.phone = spec["phone"]
        user.nickname = spec["nickname"]
        user.last_initial = spec["last_initial"]
        user.profile_photo_url = DEMO_PROFILE_PHOTO_URL
        db.flush()

        nanny = db.query(models.Nanny).filter(models.Nanny.user_id == user.id).first()
        if not nanny:
            nanny = models.Nanny(user_id=user.id)
            db.add(nanny)
        nanny.approved = True
        nanny.is_suspended = False
        nanny.profile_complete = True
        nanny.availability_complete = True
        nanny.banking_complete = True
        nanny.video_screening_complete = True
        nanny.video_screening_json = json.dumps([])
        nanny.video_screening_submitted_at = datetime.utcnow()
        db.flush()

        profile = db.query(models.NannyProfile).filter(models.NannyProfile.nanny_id == nanny.id).first()
        if not profile:
            profile = models.NannyProfile(nanny_id=nanny.id)
            db.add(profile)

        approvals = {
            "sa_id_document_url": {"approved": True, "demo": True},
            "police_clearance_document_url": {"approved": True, "demo": True},
        }
        if spec["has_drivers_license"]:
            approvals["drivers_license_document_url"] = {"approved": True, "demo": True}

        profile.bio = f"TEST PROFILE: {spec['bio']}"
        profile.date_of_birth = spec["dob"]
        profile.nationality = "South African"
        profile.gender = "Female"
        profile.ethnicity = "Black"
        profile.sa_id_number = f"{spec['dob']:%y%m%d}{index:07d}"
        profile.sa_id_document_url = DEMO_DOCUMENT_URL
        profile.police_clearance_status = "yes"
        profile.police_clearance_document_url = DEMO_DOCUMENT_URL
        profile.document_approvals_json = json.dumps(approvals)
        profile.has_drivers_license = spec["has_drivers_license"]
        profile.drivers_license_document_url = DEMO_DOCUMENT_URL if spec["has_drivers_license"] else None
        profile.has_own_car = spec["has_own_car"]
        profile.has_own_kids = False
        profile.medical_conditions = "None"
        profile.dog_preference = spec["dog_preference"]
        profile.job_type = "both"
        profile.current_job_availability = "piece_and_permanent"
        profile.my_nanny_training_status = "yes"
        profile.lat = spec["lat"]
        profile.lng = spec["lng"]
        profile.is_approved = 1
        profile.application_status = "approved"
        profile.approved_at = datetime.utcnow().isoformat()
        profile.formatted_address = spec["formatted_address"]
        profile.suburb = spec["suburb"]
        profile.city = spec["city"]
        profile.province = "Gauteng"
        profile.country = "South Africa"
        langs = db.query(models.Language).filter(models.Language.name.in_(spec["languages"])).all()
        quals = db.query(models.Qualification).filter(models.Qualification.name.in_(spec["qualifications"])).all()
        profile.languages = langs
        profile.qualifications = quals
        db.add(profile)
        db.flush()

        db.query(models.NannyAvailability).filter(
            models.NannyAvailability.nanny_id == nanny.id,
            models.NannyAvailability.notes == "demo seed",
        ).delete(synchronize_session=False)

        start_day = date.today()
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

        seeded.append((action, spec["email"], user.id, nanny.id))

    db.commit()
    return seeded


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
        seeded = seed(db)
        if seeded:
            print(f"\nseeded {len(seeded)} demo nannies (password for all: {DEMO_PASSWORD}):")
            for action, email, user_id, nanny_id in seeded:
                print(f"  {action}: {email}  user_id={user_id} nanny_id={nanny_id}")
            print("\navailability: today plus 29 days, 06:00-22:00 SA time, in Sandhurst/Sandton and Centurion")
            print("cleanup before real launch: python scripts/seed_demo_nannies.py --delete")
    finally:
        db.close()


if __name__ == "__main__":
    main()
