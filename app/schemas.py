from datetime import datetime, date
from typing import List, Optional, Literal
from enum import Enum
from pydantic import BaseModel, ConfigDict, EmailStr, Field, conint, field_validator, model_validator

class ReviewPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    booking_id: int
    stars: int
    comment: Optional[str] = None
    created_at: datetime


# ...existing code...

class NannyReviewsResponse(BaseModel):
    nanny_id: int
    average_rating_12m: Optional[float] = None
    review_count_12m: int = 0
    reviews: List['ReviewOut']


# Schema for /nannies/search result
class NannySearchResult(BaseModel):
    nanny_id: int
    approved: bool
    user_id: int
    name: str
    nickname: Optional[str] = None
    last_initial: Optional[str] = None
    profile_photo_url: Optional[str] = None
    profile_summary: Optional[str] = None
    bio: Optional[str] = None
    date_of_birth: Optional[date] = None
    age: Optional[int] = None
    nationality: Optional[str] = None
    ethnicity: Optional[str] = None
    qualifications: Optional[List[dict]] = None
    tags: Optional[List[dict]] = None
    languages: Optional[List[dict]] = None
    job_type: Optional[str] = None
    has_drivers_license: Optional[bool] = None
    has_own_car: Optional[bool] = None
    dog_preference: Optional[str] = None
    average_rating_12m: Optional[float] = None
    review_count_12m: int = 0
    distance_km: Optional[float] = None
    location_hint: Optional[str] = None
    completed_jobs_count: int = 0
    has_identity_document: bool = False
    has_passport_document: bool = False
    previous_jobs: Optional[List[dict]] = None

class SearchNanniesResponse(BaseModel):
    results: List[NannySearchResult] = []
    code: Optional[str] = None
    message: Optional[str] = None
    parent_profile_complete: Optional[bool] = None

class SearchNanniesRequest(BaseModel):
    lat: Optional[float] = None
    lng: Optional[float] = None
    max_distance_km: Optional[float] = None
    min_rating: Optional[float] = None
    tag_ids: Optional[List[int]] = None
    qualification_ids: Optional[List[int]] = None
    language_ids: Optional[List[int]] = None
    min_age: Optional[int] = None
    max_age: Optional[int] = None
    use_preferences: bool = False

class BookingSlot(BaseModel):
    starts_at: datetime
    ends_at: datetime

class BulkBookingRequest(BaseModel):
    parent_user_id: int
    nanny_id: int
    slots: List[BookingSlot] = Field(min_items=1)
    client_notes: Optional[str] = None

class UpdateNannyProfileRequest(BaseModel):
    bio: Optional[str] = None
    date_of_birth: Optional[date] = None
    nationality: Optional[str] = None
    ethnicity: Optional[str] = None
    qualification_ids: Optional[List[int]] = None
    tag_ids: Optional[List[int]] = None
    language_ids: Optional[List[int]] = None

class SetNannyAreasRequest(BaseModel):
    area_ids: List[int]

class CreateNannyProfileRequest(BaseModel):
    bio: Optional[str] = None
    date_of_birth: Optional[date] = None
    nationality: Optional[str] = None
    ethnicity: Optional[str] = None


class NannyPreviousJob(BaseModel):
    role: Optional[str] = None
    employer: Optional[str] = None
    period: Optional[str] = None
    care_type: Optional[str] = None
    kids_age_when_started: Optional[str] = None
    disability_details: Optional[str] = None
    reference_letter_url: Optional[str] = None
    reference_name: Optional[str] = None
    reference_phone: Optional[str] = None
    reference_relationship: Optional[str] = None


class NannyMeProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    phone_alt: Optional[str] = None
    dob: Optional[date] = None
    bio: Optional[str] = None
    nationality: Optional[str] = None
    gender: Optional[str] = None
    ethnicity: Optional[str] = None
    passport_number: Optional[str] = None
    passport_expiry: Optional[str] = None
    passport_document_url: Optional[str] = None
    permit_status: Optional[str] = None
    work_permit: Optional[bool] = None
    work_permit_expiry: Optional[str] = None
    work_permit_document_url: Optional[str] = None
    waiver: Optional[bool] = None
    sa_id_number: Optional[str] = None
    sa_id_document_url: Optional[str] = None
    has_own_car: Optional[bool] = None
    has_drivers_license: Optional[bool] = None
    job_type: Optional[str] = None
    police_clearance_status: Optional[str] = None
    has_own_kids: Optional[bool] = None
    own_kids_details: Optional[str] = None
    medical_conditions: Optional[str] = None
    my_nanny_training_status: Optional[str] = None
    dog_preference: Optional[str] = None
    studying_details: Optional[str] = None
    police_clearance_document_url: Optional[str] = None
    drivers_license_document_url: Optional[str] = None
    certificate_urls: Optional[List[str]] = None
    previous_jobs: Optional[List[NannyPreviousJob]] = None
    qualification_ids: Optional[List[int]] = None
    tag_ids: Optional[List[int]] = None
    language_ids: Optional[List[int]] = None


class NannyMeProfileResponse(BaseModel):
    nanny_id: int
    user_id: int
    full_name: Optional[str] = None
    phone: Optional[str] = None
    phone_alt: Optional[str] = None
    dob: Optional[date] = None
    bio: Optional[str] = None
    nationality: Optional[str] = None
    gender: Optional[str] = None
    ethnicity: Optional[str] = None
    passport_number: Optional[str] = None
    passport_expiry: Optional[str] = None
    passport_document_url: Optional[str] = None
    permit_status: Optional[str] = None
    work_permit: Optional[bool] = None
    work_permit_expiry: Optional[str] = None
    work_permit_document_url: Optional[str] = None
    waiver: Optional[bool] = None
    sa_id_number: Optional[str] = None
    sa_id_document_url: Optional[str] = None
    has_own_car: Optional[bool] = None
    has_drivers_license: Optional[bool] = None
    job_type: Optional[str] = None
    police_clearance_status: Optional[str] = None
    has_own_kids: Optional[bool] = None
    own_kids_details: Optional[str] = None
    medical_conditions: Optional[str] = None
    my_nanny_training_status: Optional[str] = None
    dog_preference: Optional[str] = None
    studying_details: Optional[str] = None
    police_clearance_document_url: Optional[str] = None
    drivers_license_document_url: Optional[str] = None
    certificate_urls: List[str] = []
    previous_jobs: List[NannyPreviousJob] = []
    qualification_ids: List[int] = []
    tag_ids: List[int] = []
    language_ids: List[int] = []
    is_approved: bool
    approved_at: Optional[str] = None
    profile_photo_url: Optional[str] = None
    formatted_address: Optional[str] = None
    suburb: Optional[str] = None
    city: Optional[str] = None
    location_hint: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None


class NannyAvailabilityCreateRequest(BaseModel):
    start_dt: str
    end_dt: str
    type: Literal["available", "blocked"]


class NannyAvailabilityBulkRequest(BaseModel):
    start_date: str
    end_date: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    type: Literal["available", "blocked"]


class NannyAvailabilityWeeklyRequest(BaseModel):
    start_date: str
    weeks: int
    weekdays: List[int]
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    type: Literal["available", "blocked"]


class NannyAvailabilityOut(BaseModel):
    id: int
    start_dt: Optional[str] = None
    end_dt: Optional[str] = None
    type: Optional[str] = None
    notes: Optional[str] = None

class SetParentAreaRequest(BaseModel):
    user_id: int
    area_id: int


class SetParentDefaultLocationRequest(BaseModel):
    user_id: int
    lat: float
    lng: float
    confirm_version: str = "v1"


class SetLocationRequest(BaseModel):
    lat: float
    lng: float
    place_id: Optional[str] = None
    formatted_address: Optional[str] = None
    street: Optional[str] = None
    suburb: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    label: Optional[str] = None
    location_label: Optional[str] = None


class SetLocationResponse(BaseModel):
    user_id: int
    lat: float
    lng: float


class ParentLocationResponse(BaseModel):
    user_id: int
    lat: float
    lng: float


class NannyLocationResponse(BaseModel):
    nanny_id: int
    lat: float
    lng: float


class LocationMode(str, Enum):
    default = "default"
    current = "current"


class BookingCreateRequest(BaseModel):
    parent_user_id: int
    nanny_id: int
    starts_at: datetime
    ends_at: datetime
    location_id: int


class BookingRequestCreate(BaseModel):
    nanny_id: int
    start_dt: Optional[str] = None
    end_dt: Optional[str] = None
    slots: Optional[List[BookingSlot]] = None
    notes: Optional[str] = None
    location_id: Optional[int] = None
    sleepover: Optional[bool] = None
    kids_count: Optional[int] = 1
    responsibilities: Optional[str] = None
    adult_present: Optional[str] = None
    booking_reason: Optional[str] = None
    meal_option: Optional[str] = None
    food_restrictions: Optional[str] = None
    dogs_info: Optional[str] = None
    disclaimer_basic_upkeep: Optional[bool] = None
    disclaimer_medicine: Optional[bool] = None
    disclaimer_extra_hours: Optional[bool] = None
    disclaimer_transport: Optional[bool] = None


class BookingRequestBulkCreate(BaseModel):
    nanny_ids: List[int]
    start_dt: Optional[str] = None
    end_dt: Optional[str] = None
    slots: Optional[List[BookingSlot]] = None
    notes: Optional[str] = None
    location_id: Optional[int] = None
    sleepover: Optional[bool] = None
    kids_count: Optional[int] = 1
    responsibilities: Optional[str] = None
    adult_present: Optional[str] = None
    booking_reason: Optional[str] = None
    meal_option: Optional[str] = None
    food_restrictions: Optional[str] = None
    dogs_info: Optional[str] = None
    disclaimer_basic_upkeep: Optional[bool] = None
    disclaimer_medicine: Optional[bool] = None
    disclaimer_extra_hours: Optional[bool] = None
    disclaimer_transport: Optional[bool] = None


class BookingEstimateRequest(BaseModel):
    start_dt: Optional[str] = None
    end_dt: Optional[str] = None
    slots: Optional[List[BookingSlot]] = None
    sleepover: Optional[bool] = None
    selected_count: Optional[int] = 1
    kids_count: Optional[int] = 1


class BookingEstimateResponse(BaseModel):
    currency: str = "ZAR"
    per_nanny_total_cents: int
    per_nanny_wage_cents: int
    per_nanny_fee_cents: int
    booking_fee_pct: float
    selected_count: int = 1
    selected_total_cents: int


class NannySearchByTimeRequest(BaseModel):
    lat: Optional[float] = None
    lng: Optional[float] = None
    start_dt: Optional[str] = None
    end_dt: Optional[str] = None
    slots: Optional[List[BookingSlot]] = None
    max_distance_km: Optional[float] = 50


class BookingRequestReject(BaseModel):
    reason: Optional[str] = None
    assign_nanny_id: Optional[int] = None


class BookingCancellationRequest(BaseModel):
    reason: str


class NannyBookingRequestResponse(BaseModel):
    response: Literal["accepted", "declined", "deciding"]
    reason: Optional[str] = None


class ParentBookingRequestUpdate(BaseModel):
    notes: Optional[str] = None
    responsibilities: Optional[str] = None
    adult_present: Optional[str] = None
    booking_reason: Optional[str] = None
    kids_count: Optional[int] = 1
    meal_option: Optional[str] = None
    food_restrictions: Optional[str] = None
    dogs_info: Optional[str] = None
    disclaimer_basic_upkeep: Optional[bool] = None
    disclaimer_medicine: Optional[bool] = None
    disclaimer_extra_hours: Optional[bool] = None
    disclaimer_transport: Optional[bool] = None


class AdminNannyApplicationUpdateRequest(BaseModel):
    status: Literal["approved", "declined", "hold", "pending"]
    reason: Optional[str] = None


class AdminInviteCreateRequest(BaseModel):
    email: EmailStr
    reason: Optional[str] = None


class AdminInviteAcceptRequest(BaseModel):
    token: str
    name: str
    password: str


class BookingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    booking_id: int
    parent_user_id: int
    nanny_id: int
    starts_at: datetime
    ends_at: datetime
    status: str
    location_mode: Optional[str] = None
    location_label: Optional[str] = None
    formatted_address: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None


class AuthUserOut(BaseModel):
    id: int
    name: str
    email: str
    role: str
    nanny_id: Optional[int] = None
    is_admin: bool = False
    is_active: bool = True
    nanny_application_status: Optional[str] = None
    nanny_admin_reason: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    user: AuthUserOut


class AuthResponse(BaseModel):
    user: AuthUserOut


class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: Literal["parent", "nanny"]
    phone: Optional[str] = None
    phone_alt: Optional[str] = None
    nationality: Optional[str] = None
    gender: Optional[str] = None
    ethnicity: Optional[str] = None
    passport_number: Optional[str] = None
    passport_expiry: Optional[str] = None
    permit_status: Optional[str] = None
    work_permit: Optional[bool] = None
    work_permit_expiry: Optional[str] = None
    waiver: Optional[bool] = None
    sa_id_number: Optional[str] = None
    sa_id_document_url: Optional[str] = None
    has_own_car: Optional[bool] = None
    has_drivers_license: Optional[bool] = None
    job_type: Optional[str] = None
    police_clearance_status: Optional[str] = None
    has_own_kids: Optional[bool] = None
    own_kids_details: Optional[str] = None
    medical_conditions: Optional[str] = None
    my_nanny_training_status: Optional[str] = None


class BookingListResponse(BaseModel):
    results: List[BookingOut] = []


class BookingStatus(str, Enum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"
    cancelled = "cancelled"
    completed = "completed"


class BookingStatusUpdateRequest(BaseModel):
    status: BookingStatus


class BookingDutyActionRequest(BaseModel):
    lat: float
    lng: float


class ReviewCreate(BaseModel):
    booking_id: int
    stars: int
    comment: Optional[str] = None


class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    booking_id: int
    parent_user_id: int
    nanny_id: int
    stars: int
    comment: Optional[str] = None
    approved: bool
    created_at: datetime


class ParentProfileDetailsRequest(BaseModel):
    phone: Optional[str] = None
    kids_count: Optional[int] = None
    kids_ages: Optional[List[int]] = None
    desired_tag_ids: Optional[List[int]] = None
    home_language_id: Optional[int] = None
    special_notes: Optional[str] = None
    family_photo_url: Optional[str] = None
    residence_type: Optional[str] = None
    access_flags: Optional[List[str]] = None
    booking_responsibilities: Optional[str] = None
    booking_adult_present: Optional[str] = None
    booking_reason: Optional[str] = None
    booking_children_count: Optional[int] = None
    booking_meal_option: Optional[str] = None
    booking_food_restrictions: Optional[str] = None
    booking_dogs: Optional[str] = None
    booking_disclaimer_basic_upkeep: Optional[bool] = None
    booking_disclaimer_medicine: Optional[bool] = None
    booking_disclaimer_extra_hours: Optional[bool] = None
    booking_disclaimer_transport: Optional[bool] = None


class ParentLocationBase(BaseModel):
    label: Optional[str] = None
    place_id: Optional[str] = None
    formatted_address: Optional[str] = None
    street: Optional[str] = None
    suburb: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    lat: float
    lng: float


class ParentLocationCreateRequest(ParentLocationBase):
    is_default: Optional[bool] = None


class ParentLocationUpdateRequest(ParentLocationBase):
    pass


class ParentLocationOut(ParentLocationBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    parent_user_id: int
    is_default: bool
    created_at: Optional[str] = None

    @field_validator("created_at", mode="before")
    @classmethod
    def normalize_created_at(cls, v):
        if v is None:
            return v
        if isinstance(v, datetime):
            return v.isoformat()
        return str(v)


class SetDefaultLocationRequest(BaseModel):
    make_default: bool = True


class GeoReverseResponse(BaseModel):
    place_id: Optional[str] = None
    formatted_address: Optional[str] = None
    street: Optional[str] = None
    suburb: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    lat: float
    lng: float


class GeoReverseErrorResponse(BaseModel):
    status: Optional[str] = None
    error_message: Optional[str] = None
    raw: Optional[dict] = None


class AdminSetUserAdminRequest(BaseModel):
    is_admin: bool


class AdminSetNannyApprovalRequest(BaseModel):
    approved: bool


class AdminSetBookingRequestStatusRequest(BaseModel):
    status: Literal["accepted", "rejected"]


class AdminImpersonateRequest(BaseModel):
    user_id: int
