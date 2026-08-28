"""Create or refresh the live booking-flow demo parent.

The profile is complete apart from Paystack authorisation so the real test
payment setup can be exercised. The default address is close to the two
Sandhurst/Sandton demo nannies.

Usage:
    python scripts/seed_demo_parent.py

The fixed account is safe to refresh repeatedly. Remove it after testing with:
    python scripts/seed_demo_parent.py --delete
"""
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import SessionLocal  # noqa: E402
from app import models  # noqa: E402
from app.security import hash_password  # noqa: E402


DEMO_EMAIL = "demo.parent813967980@mynanny.test"
DEMO_PHONE = "+27813967980"
DEMO_PASSWORD = "Demo1234!"
DEMO_NAME = "My Nanny Test Parent"


def seed(db):
    user = db.query(models.User).filter(models.User.email == DEMO_EMAIL).first()
    action = "refreshed"
    if not user:
        action = "created"
        user = models.User(
            name=DEMO_NAME,
            role="parent",
            email=DEMO_EMAIL,
            password_hash=hash_password(DEMO_PASSWORD),
        )
        db.add(user)

    user.name = DEMO_NAME
    user.role = "parent"
    user.is_admin = False
    user.is_active = True
    user.phone = DEMO_PHONE
    user.preferred_messaging_channel = "whatsapp"
    # Deliberately leave Paystack blank so the real R1 test setup is exercised.
    user.paystack_customer_code = None
    user.paystack_auth_code = None
    user.card_last4 = None
    user.card_brand = None
    user.card_saved_at = None
    user.lat = -26.1100
    user.lng = 28.0489
    db.flush()

    language = db.query(models.Language).filter(models.Language.name == "English").first()
    if not language:
        language = db.query(models.Language).order_by(models.Language.id.asc()).first()
    tag = (
        db.query(models.NannyTag)
        .filter(models.NannyTag.is_active == True)
        .order_by(models.NannyTag.id.asc())
        .first()
    )

    profile = db.query(models.ParentProfile).filter(models.ParentProfile.user_id == user.id).first()
    if not profile:
        profile = models.ParentProfile(user_id=user.id)
        db.add(profile)
    profile.phone = DEMO_PHONE
    profile.kids_count = 2
    profile.kids_ages_json = json.dumps([
        {"years": 2, "months": 0},
        {"years": 6, "months": 0},
    ])
    profile.desired_tag_ids_json = json.dumps([tag.id] if tag else [1])
    profile.home_language_id = language.id if language else 1
    profile.special_notes = "TEST PROFILE: Used for end-to-end booking and notification checks."
    profile.residence_type = "house"
    profile.access_flags_json = json.dumps(["access_required"])
    profile.booking_responsibilities = "Childcare, play, meals and the normal evening routine."
    profile.booking_adult_present = "No"
    profile.booking_reason = "End-to-end My Nanny booking test."
    profile.booking_children_count = 2
    profile.booking_meal_option = "Prepare a simple meal"
    profile.booking_food_restrictions = "None"
    profile.booking_dogs = "No dogs"
    profile.booking_disclaimer_basic_upkeep = True
    profile.booking_disclaimer_medicine = True
    profile.booking_disclaimer_extra_hours = True
    profile.booking_disclaimer_transport = True
    profile.lat = -26.1100
    profile.lng = 28.0489
    profile.location_confirmed_at = datetime.utcnow()
    profile.location_confirm_version = "demo-seed-v1"
    profile.formatted_address = "1 Sandton Drive, Sandhurst, Sandton, 2196, South Africa"
    profile.street = "1 Sandton Drive"
    profile.suburb = "Sandhurst"
    profile.city = "Sandton"
    profile.province = "Gauteng"
    profile.postal_code = "2196"
    profile.country = "South Africa"
    profile.location_label = "Home"
    db.flush()

    locations = db.query(models.ParentLocation).filter(models.ParentLocation.parent_user_id == user.id).all()
    location = next((row for row in locations if row.label == "Home"), None)
    if not location:
        location = models.ParentLocation(parent_user_id=user.id, label="Home")
        db.add(location)
    for row in locations:
        row.is_default = False
    location.place_id = "demo-sandhurst-parent"
    location.formatted_address = "1 Sandton Drive, Sandhurst, Sandton, 2196, South Africa"
    location.street = "1 Sandton Drive"
    location.suburb = "Sandhurst"
    location.city = "Sandton"
    location.province = "Gauteng"
    location.postal_code = "2196"
    location.country = "South Africa"
    location.lat = -26.1100
    location.lng = 28.0489
    location.lat_round = -26.11
    location.lng_round = 28.05
    location.is_default = True

    db.commit()
    return action, user.id


def delete(db):
    user = db.query(models.User).filter(models.User.email == DEMO_EMAIL).first()
    if not user:
        print("demo parent not found")
        return
    db.query(models.ParentLocation).filter(models.ParentLocation.parent_user_id == user.id).delete()
    db.query(models.ParentProfile).filter(models.ParentProfile.user_id == user.id).delete()
    db.delete(user)
    db.commit()
    print(f"deleted: {DEMO_EMAIL}")


if __name__ == "__main__":
    db = SessionLocal()
    try:
        if "--delete" in sys.argv:
            delete(db)
        else:
            action, user_id = seed(db)
            print(f"{action}: {DEMO_EMAIL} user_id={user_id}")
            print(f"phone: {DEMO_PHONE}")
            print(f"password: {DEMO_PASSWORD}")
            print("profile: complete except Paystack authorisation")
            print("default location: Sandhurst, Sandton")
            print("cleanup: python scripts/seed_demo_parent.py --delete")
    finally:
        db.close()
