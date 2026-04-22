from .availability import NannyAvailability as Availability
from .availability import NannyAvailability
from .bookings import BookingRequest, BookingRequestSlot, BookingPricingSnapshot
from app.db import Base

from sqlalchemy import (
    Column,
    BigInteger,
    Integer,
    String,
    Boolean,
    ForeignKey,
    Date,
    Table,
    Text,
    Float,
    UniqueConstraint,
    DateTime,
    CheckConstraint,
    Index,
    Numeric,
)
from sqlalchemy.orm import relationship
from app.db import Base
from sqlalchemy import UniqueConstraint
from sqlalchemy.sql import func

# ---------------- USERS ----------------

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    role = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True)
    password_hash = Column(String, nullable=False)

    is_admin = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)

    phone = Column(String, nullable=True)
    phone_alt = Column(String, nullable=True)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)

    nickname = Column(String, nullable=True)
    last_initial = Column(String, nullable=True)
    profile_photo_url = Column(String, nullable=True)

    admin_profile = relationship("AdminProfile", back_populates="user", uselist=False)


# ---------------- CORE ENTITIES ----------------

class Nanny(Base):
    __tablename__ = "nannies"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    approved = Column(Boolean, nullable=False, default=False)

    profile = relationship("NannyProfile", back_populates="nanny", uselist=False)





class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True)
    booking_request_id = Column(BigInteger, ForeignKey("booking_requests.id"), nullable=True)
    nanny_id = Column(Integer, ForeignKey("nannies.id"), nullable=False)
    client_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    day = Column(Date, nullable=False)
    status = Column(String, nullable=False, default="pending")
    price_cents = Column(Integer, nullable=False)
    starts_at = Column(DateTime, nullable=True)
    ends_at = Column(DateTime, nullable=True)
    start_dt = Column(String, nullable=True)
    end_dt = Column(String, nullable=True)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    location_mode = Column(String, nullable=True)
    location_label = Column(String, nullable=True)
    formatted_address = Column(String, nullable=True)
    check_in_at = Column(DateTime, nullable=True)
    check_in_lat = Column(Float, nullable=True)
    check_in_lng = Column(Float, nullable=True)
    check_in_distance_m = Column(Float, nullable=True)
    check_in_confirmed_at = Column(DateTime, nullable=True)
    check_in_confirmed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    check_out_at = Column(DateTime, nullable=True)
    check_out_lat = Column(Float, nullable=True)
    check_out_lng = Column(Float, nullable=True)
    check_out_distance_m = Column(Float, nullable=True)
    check_out_confirmed_at = Column(DateTime, nullable=True)
    check_out_confirmed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    cancellation_reason = Column(Text, nullable=True)
    cancellation_actor_role = Column(String, nullable=True)
    cancellation_actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    google_calendar_event_id = Column(String, nullable=True)
    google_calendar_synced_at = Column(DateTime, nullable=True)
    google_calendar_sync_error = Column(Text, nullable=True)


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=False, unique=True)
    parent_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    nanny_id = Column(Integer, ForeignKey("nannies.id"), nullable=False)
    stars = Column(Integer, nullable=False)
    comment = Column(Text, nullable=True)
    approved = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("stars >= 1 AND stars <= 5", name="reviews_stars_check"),
        Index("reviews_nanny_id_idx", "nanny_id"),
        Index("reviews_parent_user_id_idx", "parent_user_id"),
        Index("reviews_approved_idx", "approved"),
        Index("reviews_created_at_idx", "created_at"),
    )


# ---------------- LOOKUP TABLES ----------------

class Qualification(Base):
    __tablename__ = "qualifications"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)


class NannyTag(Base):
    __tablename__ = "nanny_tags"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)


class Language(Base):
    __tablename__ = "languages"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)


class Area(Base):
    __tablename__ = "areas"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)


class NannyArea(Base):
    __tablename__ = "nanny_areas"

    id = Column(Integer, primary_key=True)
    nanny_id = Column(Integer, ForeignKey("nannies.id"), nullable=False)
    area_id = Column(Integer, ForeignKey("areas.id"), nullable=False)

    __table_args__ = (
        UniqueConstraint("nanny_id", "area_id", name="uq_nanny_area"),
    )


class ParentProfile(Base):
    __tablename__ = "parent_profiles"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    area_id = Column(Integer, ForeignKey("areas.id"), nullable=True)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    location_confirmed_at = Column(DateTime, nullable=True)
    location_confirm_version = Column(String, nullable=True)
    place_id = Column(String, nullable=True)
    formatted_address = Column(String, nullable=True)
    street = Column(String, nullable=True)
    suburb = Column(String, nullable=True)
    city = Column(String, nullable=True)
    province = Column(String, nullable=True)
    postal_code = Column(String, nullable=True)
    country = Column(String, nullable=True)
    location_label = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    kids_count = Column(Integer, nullable=True)
    kids_ages_json = Column(Text, nullable=True)
    desired_tag_ids_json = Column(Text, nullable=True)
    home_language_id = Column(Integer, nullable=True)
    special_notes = Column(Text, nullable=True)
    family_photo_url = Column(String, nullable=True)
    residence_type = Column(String, nullable=True)
    access_flags_json = Column(Text, nullable=True)
    booking_responsibilities = Column(Text, nullable=True)
    booking_adult_present = Column(Text, nullable=True)
    booking_reason = Column(Text, nullable=True)
    booking_children_count = Column(Integer, nullable=True)
    booking_meal_option = Column(Text, nullable=True)
    booking_food_restrictions = Column(Text, nullable=True)
    booking_dogs = Column(Text, nullable=True)
    booking_disclaimer_basic_upkeep = Column(Boolean, nullable=True)
    booking_disclaimer_medicine = Column(Boolean, nullable=True)
    booking_disclaimer_extra_hours = Column(Boolean, nullable=True)
    booking_disclaimer_transport = Column(Boolean, nullable=True)


class ParentFavorite(Base):
    __tablename__ = "parent_favorites"

    id = Column(Integer, primary_key=True)
    parent_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    nanny_id = Column(Integer, ForeignKey("nannies.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("parent_user_id", "nanny_id", name="uq_parent_favorite"),
        Index("ix_parent_favorites_parent_user_id", "parent_user_id"),
        Index("ix_parent_favorites_nanny_id", "nanny_id"),
    )


class PricingSettings(Base):
    __tablename__ = "pricing_settings"

    id = Column(Integer, primary_key=True)
    weekday_half_day = Column(Integer, nullable=False, default=250)
    weekday_full_day = Column(Integer, nullable=False, default=300)
    weekend_half_day = Column(Integer, nullable=False, default=300)
    weekend_full_day = Column(Integer, nullable=False, default=350)
    sleepover_add = Column(Integer, nullable=False, default=150)
    sleepover_only_weekday = Column(Integer, nullable=False, default=400)
    sleepover_only_weekend = Column(Integer, nullable=False, default=450)
    sleepover_extra_hour_over14 = Column(Integer, nullable=False, default=50)
    after17_weekday = Column(Integer, nullable=False, default=30)
    after17_weekend = Column(Integer, nullable=False, default=35)
    over9_weekday = Column(Integer, nullable=False, default=45)
    over9_weekend = Column(Integer, nullable=False, default=50)
    sleepover_start_hour = Column(Integer, nullable=False, default=14)
    sleepover_end_hour = Column(Integer, nullable=False, default=7)
    sleepover_after7_hourly = Column(Integer, nullable=False, default=45)
    booking_fee_pct_1_5 = Column(Numeric(5, 4), nullable=False, default=0.30)
    booking_fee_pct_6_10 = Column(Numeric(5, 4), nullable=False, default=0.27)
    booking_fee_pct_10_plus = Column(Numeric(5, 4), nullable=False, default=0.25)
    cancellation_fee_window_hours = Column(Integer, nullable=False, default=15)


class AppSettings(Base):
    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True)
    google_maps_api_key = Column(Text, nullable=True)
    google_calendar_id = Column(Text, nullable=True)


class ParentLocation(Base):
    __tablename__ = "parent_locations"

    id = Column(Integer, primary_key=True)
    parent_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    label = Column(String, nullable=True)
    place_id = Column(String, nullable=True)
    formatted_address = Column(String, nullable=True)
    street = Column(String, nullable=True)
    suburb = Column(String, nullable=True)
    city = Column(String, nullable=True)
    province = Column(String, nullable=True)
    postal_code = Column(String, nullable=True)
    country = Column(String, nullable=True)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    lat_round = Column(Float, nullable=True)
    lng_round = Column(Float, nullable=True)
    is_default = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


# ---------------- MANY TO MANY ----------------

nanny_profile_qualifications = Table(
    "nanny_profile_qualifications",
    Base.metadata,
    Column("nanny_profile_id", Integer, ForeignKey("nanny_profiles.id"), primary_key=True),
    Column("qualification_id", Integer, ForeignKey("qualifications.id"), primary_key=True),
)

nanny_profile_tags = Table(
    "nanny_profile_tags",
    Base.metadata,
    Column("nanny_profile_id", Integer, ForeignKey("nanny_profiles.id"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("nanny_tags.id"), primary_key=True),
)

nanny_profile_languages = Table(
    "nanny_profile_languages",
    Base.metadata,
    Column("nanny_profile_id", Integer, ForeignKey("nanny_profiles.id"), primary_key=True),
    Column("language_id", Integer, ForeignKey("languages.id"), primary_key=True),
)


# ---------------- MAIN PROFILE ----------------

class NannyProfile(Base):
    __tablename__ = "nanny_profiles"

    id = Column(Integer, primary_key=True)
    nanny_id = Column(Integer, ForeignKey("nannies.id"), nullable=False, unique=True)

    bio = Column(Text, nullable=True)
    date_of_birth = Column(Date, nullable=True)
    nationality = Column(String, nullable=True)

    gender = Column(String, nullable=True)
    ethnicity = Column(String, nullable=True)
    passport_number = Column(String, nullable=True)
    passport_expiry = Column(String, nullable=True)
    passport_document_url = Column(String, nullable=True)
    permit_status = Column(String, nullable=True)
    work_permit = Column(Boolean, nullable=True)
    work_permit_expiry = Column(String, nullable=True)
    work_permit_document_url = Column(String, nullable=True)
    waiver = Column(Boolean, nullable=True)
    sa_id_number = Column(String, nullable=True)
    sa_id_document_url = Column(String, nullable=True)
    has_own_car = Column(Boolean, nullable=True)
    has_drivers_license = Column(Boolean, nullable=True)
    job_type = Column(String, nullable=True)
    current_job_availability = Column(String, nullable=True)
    police_clearance_status = Column(String, nullable=True)
    has_own_kids = Column(Boolean, nullable=True)
    own_kids_details = Column(Text, nullable=True)
    medical_conditions = Column(Text, nullable=True)
    my_nanny_training_status = Column(String, nullable=True)
    dog_preference = Column(String, nullable=True)
    studying_details = Column(Text, nullable=True)
    police_clearance_document_url = Column(String, nullable=True)
    drivers_license_document_url = Column(String, nullable=True)
    certificates_json = Column(Text, nullable=True)
    previous_jobs_json = Column(Text, nullable=True)

    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)

    is_approved = Column(Integer, nullable=False, default=0)
    approved_at = Column(String, nullable=True)
    application_status = Column(String, nullable=True, default="pending")
    admin_reason = Column(Text, nullable=True)
    reviewed_at = Column(String, nullable=True)
    reviewed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    formatted_address = Column(String, nullable=True)
    suburb = Column(String, nullable=True)
    city = Column(String, nullable=True)
    province = Column(String, nullable=True)
    postal_code = Column(String, nullable=True)
    country = Column(String, nullable=True)
    place_id = Column(String, nullable=True)

    nanny = relationship("Nanny", back_populates="profile")

    qualifications = relationship("Qualification", secondary=nanny_profile_qualifications)
    tags = relationship("NannyTag", secondary=nanny_profile_tags)
    languages = relationship("Language", secondary=nanny_profile_languages)


from app.models.admin_profile import AdminProfile
from app.models.admin_invite import AdminInvite
from app.models.audit_log import AuditLog
from . import availability
