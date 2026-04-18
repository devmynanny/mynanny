
import math
import os
import json
import hmac
import hashlib
import secrets
import uuid
from functools import cmp_to_key
from urllib.request import urlopen, Request as UrlRequest
from urllib.parse import urlencode
from pathlib import Path
from typing import Optional, List, Union
from datetime import date, datetime, timedelta, timezone, time as dt_time
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, Request, Query, Header, File, UploadFile, Response
from jose import jwt, JWTError
from sqlalchemy.orm import Session, aliased
from sqlalchemy import func, text, distinct, or_
from sqlalchemy.exc import IntegrityError
from app.db import SessionLocal
from app import models, schemas
from app.request_context import auth_token_ctx
from app.schemas import NannyReviewsResponse, SetParentAreaRequest, SetParentDefaultLocationRequest, ParentLocationResponse, NannyLocationResponse, ReviewOut, ReviewCreate, SetNannyAreasRequest, CreateNannyProfileRequest, UpdateNannyProfileRequest, BulkBookingRequest, SearchNanniesResponse, NannyMeProfileUpdate, NannyMeProfileResponse, BookingRequestCreate, BookingRequestReject, BookingRequestBulkCreate
from app.utils.email import EmailMessage, admin_emails, app_base_url, get_email_client
from app import security
from app.services.audit import log_audit, log_profile_update, log_booking_request_status_change, log_booking_status_change
from app.services.google_calendar import sync_booking_to_google_calendar
from app.utils.text_guard import redact_contact_info

router = APIRouter()

DEFAULT_NANNY_TAGS = [
    "Baby care (0-12 months)",
    "Newborn care",
    "Toddler care",
    "Domestic nanny",
    "Mostly domestic",
    "Elderly care",
    "Disability care",
    "Twin infant care",
    "Nursing",
    "Hospital NICU (baby ICU)",
    "Pre-mature infant care",
]

def _normalize_previous_jobs(raw: object) -> List[dict]:
    if raw is None:
        return []
    parsed = raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except Exception:
            return []
    if not isinstance(parsed, list):
        return []
    cleaned: List[dict] = []
    for row in parsed[:5]:
        if not isinstance(row, dict):
            continue
        item = {
            "role": (row.get("role") or "").strip(),
            "employer": (row.get("employer") or "").strip(),
            "period": (row.get("period") or "").strip(),
            "care_type": (row.get("care_type") or "").strip(),
            "kids_age_when_started": (row.get("kids_age_when_started") or "").strip(),
            "disability_details": (row.get("disability_details") or "").strip(),
            "reference_letter_url": (row.get("reference_letter_url") or "").strip(),
            "reference_name": (row.get("reference_name") or "").strip(),
            "reference_phone": (row.get("reference_phone") or "").strip(),
            "reference_relationship": (row.get("reference_relationship") or "").strip(),
        }
        if any(item.values()):
            cleaned.append(item)
    return cleaned

def _build_nanny_profile_summary(
    *,
    age: Optional[int],
    nationality: Optional[str],
    qualifications: Optional[list],
    tags: Optional[list],
    previous_jobs: Optional[List[dict]],
    bio: Optional[str],
) -> Optional[str]:
    parts: List[str] = []

    intro_bits: List[str] = []
    if nationality:
        intro_bits.append(f"from {nationality}")
    if age:
        intro_bits.append(f"{age} years old")
    if intro_bits:
        parts.append("She is " + ", ".join(intro_bits) + ".")

    qual_names: List[str] = []
    for item in (qualifications or []):
        if isinstance(item, dict):
            name = str(item.get("name") or "").strip()
        else:
            name = str(getattr(item, "name", "") or "").strip()
        if name:
            qual_names.append(name)
    if qual_names:
        displayed = ", ".join(qual_names[:3])
        if len(qual_names) > 3:
            displayed += f", and {len(qual_names) - 3} more"
        parts.append(f"Qualifications include {displayed}.")

    tag_names: List[str] = []
    for item in (tags or []):
        if isinstance(item, dict):
            name = str(item.get("name") or "").strip()
        else:
            name = str(getattr(item, "name", "") or "").strip()
        if name:
            tag_names.append(name)
    if tag_names:
        displayed = ", ".join(tag_names[:4])
        if len(tag_names) > 4:
            displayed += f", and {len(tag_names) - 4} more"
        parts.append(f"Her profile highlights {displayed}.")

    jobs = [job for job in (previous_jobs or []) if isinstance(job, dict)]
    if jobs:
        first_job = jobs[0]
        role = (first_job.get("role") or "").strip()
        employer = (first_job.get("employer") or "").strip()
        period = (first_job.get("period") or "").strip()
        summary = "She has previous childcare experience"
        if role:
            summary = f"She has worked as {role}"
        if employer:
            summary += f" for {employer}"
        if period:
            summary += f" during {period}"
        summary += "."
        parts.append(summary)
        if len(jobs) > 1:
            parts.append(f"She has listed {len(jobs)} previous childcare roles on her profile.")

    if not parts:
        cleaned_bio = (bio or "").strip()
        if not cleaned_bio:
            return None
        return cleaned_bio if len(cleaned_bio) <= 220 else cleaned_bio[:217].rstrip() + "..."
    return " ".join(parts)


def _public_nanny_name(full_name: Optional[str]) -> str:
    parts = [p for p in str(full_name or "").strip().split() if p]
    if not parts:
        return "Nanny"
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]} {parts[-1][0]}."


def _ensure_default_nanny_tags(db: Session) -> List[models.NannyTag]:
    rows = db.query(models.NannyTag).all()
    by_lower = {((row.name or "").strip().lower()): row for row in rows}
    desired_lowers = {name.lower() for name in DEFAULT_NANNY_TAGS}

    for name in DEFAULT_NANNY_TAGS:
        existing = by_lower.get(name.lower())
        if existing:
            if existing.name != name:
                existing.name = name
        else:
            row = models.NannyTag(name=name)
            db.add(row)
            db.flush()
            by_lower[name.lower()] = row

    extra_rows = [row for row in rows if ((row.name or "").strip().lower()) not in desired_lowers]
    extra_ids = [row.id for row in extra_rows]
    if extra_ids:
        db.execute(
            models.nanny_profile_tags.delete().where(models.nanny_profile_tags.c.tag_id.in_(extra_ids))
        )
        for row in extra_rows:
            db.delete(row)

    db.commit()

    synced_rows = db.query(models.NannyTag).all()
    synced_by_lower = {((row.name or "").strip().lower()): row for row in synced_rows}
    return [synced_by_lower[name.lower()] for name in DEFAULT_NANNY_TAGS if name.lower() in synced_by_lower]

def get_google_maps_browser_api_key() -> tuple[Optional[str], Optional[str]]:
    db = SessionLocal()
    try:
        row = db.query(models.AppSettings).filter(models.AppSettings.id == 1).first()
        db_key = (getattr(row, "google_maps_api_key", None) or "").strip() if row else ""
    finally:
        db.close()

    if db_key:
        return db_key, "database"

    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        env_path = Path(__file__).resolve().parents[2] / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
        api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    api_key = (api_key or "").strip()
    return (api_key or None), ("env" if api_key else None)


def get_google_maps_server_api_key() -> tuple[Optional[str], Optional[str]]:
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        env_path = Path(__file__).resolve().parents[2] / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
        api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    api_key = (api_key or "").strip()
    return (api_key or None), ("env" if api_key else None)


def google_reverse_geocode(lat: float, lng: float) -> dict:
    api_key, _ = get_google_maps_server_api_key()
    if not api_key:
        return {"status": "NO_KEY", "error_message": "GOOGLE_MAPS_API_KEY not set"}

    qs = urlencode({"latlng": f"{lat},{lng}", "key": api_key})
    url = f"https://maps.googleapis.com/maps/api/geocode/json?{qs}"

    try:
        req = UrlRequest(url, headers={"User-Agent": "nanny-app/1.0"})
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Reverse geocode failed: {e}")

    return data


@router.get("/config/google-maps")
def public_google_maps_config():
    api_key, source = get_google_maps_browser_api_key()
    return {
        "configured": bool(api_key),
        "google_maps_api_key": api_key,
        "source": source,
    }


def _extract_reverse_fields(lat: float, lng: float) -> Optional[dict]:
    data = google_reverse_geocode(lat, lng)
    status = data.get("status")
    if status != "OK":
        return None

    results = data.get("results") or []
    if not results:
        return None

    r0 = results[0]
    comps = r0.get("address_components", []) or []

    def get_long(t):
        for c in comps:
            if t in (c.get("types") or []):
                return c.get("long_name")
        return None

    street_number = get_long("street_number")
    route = get_long("route")
    street = None
    if street_number and route:
        street = f"{street_number} {route}"
    elif route:
        street = route

    city = get_long("locality")
    suburb = (
        get_long("sublocality")
        or get_long("sublocality_level_1")
        or get_long("neighborhood")
    )
    province = get_long("administrative_area_level_1")
    postal_code = get_long("postal_code")
    country = get_long("country")

    return {
        "place_id": r0.get("place_id"),
        "formatted_address": r0.get("formatted_address"),
        "street": street,
        "suburb": suburb,
        "city": city,
        "province": province,
        "postal_code": postal_code,
        "country": country,
        "lat": lat,
        "lng": lng,
    }


@router.get("/geo/reverse", response_model=Union[schemas.GeoReverseResponse, schemas.GeoReverseErrorResponse])
def geo_reverse(lat: float, lng: float):
    data = google_reverse_geocode(lat, lng)
    status = data.get("status")
    error_message = data.get("error_message")
    first_result = (data.get("results") or [None])[0]
    print(f"[GEO_REVERSE] status={status} error_message={error_message} first_result={first_result}")

    if status != "OK":
        return {
            "status": status,
            "error_message": error_message,
            "raw": data,
        }

    results = data.get("results") or []
    if not results:
        return {
            "status": "NO_RESULTS",
            "error_message": "No results in response",
            "raw": data,
        }

    r0 = results[0]
    comps = r0.get("address_components", []) or []

    def get_long(t):
        for c in comps:
            if t in (c.get("types") or []):
                return c.get("long_name")
        return None

    street_number = get_long("street_number")
    route = get_long("route")
    street = None
    if street_number and route:
        street = f"{street_number} {route}"
    elif route:
        street = route

    city = get_long("locality")
    suburb = (
        get_long("sublocality")
        or get_long("sublocality_level_1")
        or get_long("neighborhood")
    )
    province = get_long("administrative_area_level_1")
    postal_code = get_long("postal_code")
    country = get_long("country")

    return schemas.GeoReverseResponse(
        place_id=r0.get("place_id"),
        formatted_address=r0.get("formatted_address"),
        street=street,
        suburb=suburb,
        city=city,
        province=province,
        postal_code=postal_code,
        country=country,
        lat=lat,
        lng=lng,
    )

def get_rating_12m_for_nanny(db: Session, nanny_id: int):
    """
    Returns (average_rating_12m, review_count_12m) for a nanny over the last 12 months, using only approved reviews.
    """
    window_start = datetime.utcnow() - timedelta(days=365)
    q = (
        db.query(
            func.avg(models.Review.stars).label("avg_stars"),
            func.count(models.Review.id).label("count")
        )
        .filter(
            models.Review.nanny_id == nanny_id,
            models.Review.approved == True,
            models.Review.created_at >= window_start
        )
    )
    result = q.one()
    avg = float(result.avg_stars) if result.avg_stars is not None else None
    count = int(result.count)
    return avg, count

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _auth_secret() -> str:
    secret = (os.getenv("AUTH_SECRET") or "").strip()
    app_env = (os.getenv("APP_ENV") or os.getenv("ENV") or "").strip().lower()
    is_prod_like = app_env in {"prod", "production", "staging"}
    if secret:
        if is_prod_like and len(secret) < 32:
            raise RuntimeError("AUTH_SECRET must be at least 32 characters in production/staging")
        return secret
    if is_prod_like:
        raise RuntimeError("AUTH_SECRET is required in production/staging")
    return "dev-auth-secret"

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_TTL = timedelta(days=30)
IMPERSONATION_TOKEN_TTL = timedelta(minutes=10)
ACCESS_COOKIE_NAME = "access_token"
CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"


def _is_prod_like_env() -> bool:
    app_env = (os.getenv("APP_ENV") or os.getenv("ENV") or "").strip().lower()
    return app_env in {"prod", "production", "staging"}


def _set_access_cookie(response: Response, token: str) -> None:
    secure = _is_prod_like_env()
    response.set_cookie(
        key=ACCESS_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=int(ACCESS_TOKEN_TTL.total_seconds()),
        path="/",
    )


def _set_csrf_cookie(response: Response, token: Optional[str] = None) -> None:
    secure = _is_prod_like_env()
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=token or secrets.token_urlsafe(32),
        httponly=False,
        secure=secure,
        samesite="lax",
        max_age=int(ACCESS_TOKEN_TTL.total_seconds()),
        path="/",
    )


def _clear_access_cookie(response: Response) -> None:
    response.delete_cookie(
        key=ACCESS_COOKIE_NAME,
        path="/",
    )


def _clear_csrf_cookie(response: Response) -> None:
    response.delete_cookie(
        key=CSRF_COOKIE_NAME,
        path="/",
    )


def _extract_bearer_token(authorization: Optional[str]) -> Optional[str]:
    if authorization and authorization.startswith("Bearer "):
        return authorization.split(" ", 1)[1].strip()
    return None


def _resolve_auth_token(authorization: Optional[str]) -> Optional[str]:
    token = _extract_bearer_token(authorization)
    if token:
        return token
    return auth_token_ctx.get()


def _create_access_token(user: models.User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
        "name": user.name,
        "iat": now,
        "exp": now + ACCESS_TOKEN_TTL,
    }
    return jwt.encode(payload, _auth_secret(), algorithm=JWT_ALGORITHM)


def _create_impersonation_token(target_user: models.User, admin_user_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(target_user.id),
        "email": target_user.email,
        "role": target_user.role,
        "name": target_user.name,
        "impersonated_by": admin_user_id,
        "iat": now,
        "exp": now + IMPERSONATION_TOKEN_TTL,
    }
    return jwt.encode(payload, _auth_secret(), algorithm=JWT_ALGORITHM)


def hash_password(pw: str) -> str:
    return security.hash_password(pw)


def _decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(
            token,
            _auth_secret(),
            algorithms=[JWT_ALGORITHM],
            options={"verify_aud": False},
        )
        sub = payload.get("sub")
        if sub is None:
            return None
        try:
            payload["sub"] = int(sub)
        except (TypeError, ValueError):
            return None
        return payload
    except JWTError:
        return None


def _verify_password(raw_password: str, stored_hash: str) -> bool:
    if not stored_hash:
        return False
    try:
        if security.verify_password(raw_password, stored_hash):
            return True
    except Exception:
        pass

    # Legacy compatibility for older local/dev hashes so accounts can migrate
    if stored_hash == "test_hash":
        return raw_password == "password123"
    if stored_hash.startswith("sha256$"):
        legacy = "sha256$" + hashlib.sha256(raw_password.encode("utf-8")).hexdigest()
        return hmac.compare_digest(stored_hash, legacy)
    if stored_hash == raw_password:
        return True
    return False


def _password_needs_rehash(stored_hash: Optional[str]) -> bool:
    if not stored_hash:
        return True
    # Current secure formats in this app:
    # - bcrypt: $2a$, $2b$, $2y$
    # - pbkdf2_sha256 (passlib): $pbkdf2-sha256$
    if stored_hash.startswith("$2"):
        return False
    if stored_hash.startswith("$pbkdf2-sha256$"):
        return False
    return True


def _parse_iso_dt(value: Union[str, datetime]) -> datetime:
    if isinstance(value, datetime):
        return value
    if value is None:
        raise ValueError("missing datetime")
    s = str(value).strip()
    if not s:
        raise ValueError("empty datetime")
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    if " " in s and "T" not in s:
        s = s.replace(" ", "T")
    return datetime.fromisoformat(s)


def _to_iso_z(dt: datetime) -> str:
    if dt.tzinfo is None:
        return dt.isoformat()
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _existing_availability_dates(
    db: Session,
    nanny_id: int,
    start_date: date,
    end_date: date,
    expected_windows: dict[date, tuple[datetime, datetime]],
    availability_type: str,
) -> set[date]:
    rows = (
        db.query(models.NannyAvailability)
        .filter(
            models.NannyAvailability.nanny_id == nanny_id,
            models.NannyAvailability.date >= start_date,
            models.NannyAvailability.date <= end_date,
            models.NannyAvailability.type == availability_type,
        )
        .all()
    )
    existing: set[date] = set()
    for row in rows:
        row_date = getattr(row, "date", None)
        expected = expected_windows.get(row_date)
        if not row_date or not expected:
            continue
        window = _availability_window(row)
        if not window:
            continue
        row_start, row_end = window
        expected_start, expected_end = expected
        if _naive_utc(row_start) == _naive_utc(expected_start) and _naive_utc(row_end) == _naive_utc(expected_end):
            existing.add(row_date)
    return existing


def _build_availability_range(day: date, start_time_text: str, end_time_text: str) -> tuple[datetime, datetime]:
    start_dt = _parse_iso_dt(f"{day.isoformat()}T{start_time_text}")
    end_dt = _parse_iso_dt(f"{day.isoformat()}T{end_time_text}")
    if end_dt <= start_dt:
        end_dt = end_dt + timedelta(days=1)
    return start_dt, end_dt


def _availability_legacy_end_time(start_dt: datetime, end_dt: datetime):
    if end_dt.date() > start_dt.date() or end_dt.time() <= start_dt.time():
        return dt_time(23, 59, 59)
    return end_dt.time()


def _naive_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _overlaps(start_dt: datetime, end_dt: datetime, other_start: datetime, other_end: datetime) -> bool:
    a_start = _naive_utc(start_dt)
    a_end = _naive_utc(end_dt)
    b_start = _naive_utc(other_start)
    b_end = _naive_utc(other_end)
    return not (a_end <= b_start or a_start >= b_end)


def _next_booking_request_id(db: Session) -> int:
    max_id = db.query(func.max(models.BookingRequest.id)).scalar()
    return int(max_id or 0) + 1


def _next_booking_request_slot_id(db: Session) -> int:
    max_id = db.query(func.max(models.BookingRequestSlot.id)).scalar()
    return int(max_id or 0) + 1


def _get_pricing_settings(db: Session) -> dict:
    row = db.query(models.PricingSettings).first()
    if not row:
        return {
            "weekday_half_day": 250,
            "weekday_full_day": 300,
            "weekend_half_day": 300,
            "weekend_full_day": 350,
            "sleepover_add": 150,
            "sleepover_only_weekday": 400,
            "sleepover_only_weekend": 450,
            "sleepover_extra_hour_over14": 50,
            "after17_weekday": 30,
            "after17_weekend": 35,
            "over9_weekday": 45,
            "over9_weekend": 50,
            "sleepover_start_hour": 14,
            "sleepover_end_hour": 7,
            "sleepover_after7_hourly": 45,
            "booking_fee_pct_1_5": 0.30,
            "booking_fee_pct_6_10": 0.27,
            "booking_fee_pct_10_plus": 0.25,
            "cancellation_fee_window_hours": 15,
        }
    return {
        "weekday_half_day": row.weekday_half_day,
        "weekday_full_day": row.weekday_full_day,
        "weekend_half_day": row.weekend_half_day,
        "weekend_full_day": row.weekend_full_day,
        "sleepover_add": row.sleepover_add,
        "sleepover_only_weekday": row.sleepover_only_weekday,
        "sleepover_only_weekend": row.sleepover_only_weekend,
        "sleepover_extra_hour_over14": row.sleepover_extra_hour_over14,
        "after17_weekday": row.after17_weekday,
        "after17_weekend": row.after17_weekend,
        "over9_weekday": row.over9_weekday,
        "over9_weekend": row.over9_weekend,
        "sleepover_start_hour": row.sleepover_start_hour,
        "sleepover_end_hour": row.sleepover_end_hour,
        "sleepover_after7_hourly": row.sleepover_after7_hourly,
        "booking_fee_pct_1_5": float(row.booking_fee_pct_1_5),
        "booking_fee_pct_6_10": float(row.booking_fee_pct_6_10),
        "booking_fee_pct_10_plus": float(row.booking_fee_pct_10_plus),
        "cancellation_fee_window_hours": int(getattr(row, "cancellation_fee_window_hours", 15) or 15),
    }


@router.get("/settings/cancellation-window-hours")
def get_cancellation_window_hours(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    _ = _require_user(authorization, db)
    settings = _get_pricing_settings(db)
    return {"cancellation_fee_window_hours": max(15, int(settings.get("cancellation_fee_window_hours") or 15))}


def _sa_public_holidays(year: int) -> set:
    # South Africa public holidays (basic list). Substitute next Monday if holiday falls on Sunday.
    base = {
        date(year, 1, 1),   # New Year's Day
        date(year, 3, 21),  # Human Rights Day
        date(year, 4, 27),  # Freedom Day
        date(year, 5, 1),   # Workers' Day
        date(year, 6, 16),  # Youth Day
        date(year, 8, 9),   # National Women's Day
        date(year, 9, 24),  # Heritage Day
        date(year, 12, 16), # Day of Reconciliation
        date(year, 12, 25), # Christmas Day
        date(year, 12, 26), # Day of Goodwill
    }
    # Good Friday / Family Day (approximate 2026 dates)
    if year == 2026:
        base.add(date(2026, 4, 3))  # Good Friday
        base.add(date(2026, 4, 6))  # Family Day
    # Substitute if Sunday
    subs = set()
    for d in base:
        if d.weekday() == 6:
            subs.add(d + timedelta(days=1))
    return base | subs


def _is_weekend_or_holiday(d: date) -> bool:
    if d.weekday() >= 5:
        return True
    return d in _sa_public_holidays(d.year)


def _hours_between(start_dt: datetime, end_dt: datetime) -> float:
    delta = end_dt - start_dt
    return max(0.0, delta.total_seconds() / 3600.0)


def _normalize_booking_slots(
    *,
    start_dt_value: Optional[str] = None,
    end_dt_value: Optional[str] = None,
    slot_items: Optional[List[schemas.BookingSlot]] = None,
) -> List[tuple]:
    windows: List[tuple] = []

    if slot_items:
        for idx, slot in enumerate(slot_items):
            start_dt = getattr(slot, "starts_at", None)
            end_dt = getattr(slot, "ends_at", None)
            if not start_dt or not end_dt:
                raise HTTPException(status_code=400, detail=f"Invalid slot at index {idx}")
            if end_dt <= start_dt:
                raise HTTPException(status_code=400, detail=f"Slot {idx + 1} end time must be after start time")
            windows.append((start_dt, end_dt))
    else:
        if not start_dt_value or not end_dt_value:
            raise HTTPException(status_code=400, detail="Select at least one date and time")
        try:
            start_dt = _parse_iso_dt(start_dt_value)
            end_dt = _parse_iso_dt(end_dt_value)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid start_dt or end_dt")
        if end_dt <= start_dt:
            raise HTTPException(status_code=400, detail="start_dt must be before end_dt")
        windows.append((start_dt, end_dt))

    windows.sort(key=lambda item: item[0])
    for idx in range(1, len(windows)):
        if windows[idx][0] < windows[idx - 1][1]:
            raise HTTPException(status_code=400, detail="Selected date slots cannot overlap")
    return windows


EXTRA_CHILD_SURCHARGE_CENTS = 5000


def _sanitize_booking_kids_count(value: Optional[int]) -> int:
    try:
        kids_count = int(value or 1)
    except Exception:
        kids_count = 1
    return max(1, kids_count)


def _compute_booking_slots_pricing(windows: List[tuple], sleepover: bool, settings: dict, kids_count: int = 1) -> dict:
    total_wage_cents = 0
    total_fee_cents = 0
    total_cents = 0
    booking_fee_pct = 0.0
    for start_dt, end_dt in windows:
        pricing = _compute_booking_pricing(start_dt, end_dt, sleepover, settings)
        total_wage_cents += int(pricing.get("wage_cents") or 0)
        total_fee_cents += int(pricing.get("booking_fee_cents") or 0)
        total_cents += int(pricing.get("total_cents") or 0)
        booking_fee_pct = float(pricing.get("booking_fee_pct") or booking_fee_pct or 0.0)
    extra_children = max(0, _sanitize_booking_kids_count(kids_count) - 1)
    if extra_children > 0 and windows:
        surcharge_wage_cents = extra_children * EXTRA_CHILD_SURCHARGE_CENTS * len(windows)
        surcharge_fee_cents = int(round(surcharge_wage_cents * booking_fee_pct))
        total_wage_cents += surcharge_wage_cents
        total_fee_cents += surcharge_fee_cents
        total_cents += surcharge_wage_cents + surcharge_fee_cents
    return {
        "wage_cents": total_wage_cents,
        "booking_fee_pct": booking_fee_pct,
        "booking_fee_cents": total_fee_cents,
        "total_cents": total_cents,
    }


def _sanitize_booking_questionnaire_payload(payload) -> dict:
    return {
        "responsibilities": redact_contact_info(getattr(payload, "responsibilities", None) or "").strip() or None,
        "adult_present": redact_contact_info(getattr(payload, "adult_present", None) or "").strip() or None,
        "booking_reason": redact_contact_info(getattr(payload, "booking_reason", None) or "").strip() or None,
        "kids_count": _sanitize_booking_kids_count(getattr(payload, "kids_count", 1)),
        "meal_option": redact_contact_info(getattr(payload, "meal_option", None) or "").strip() or None,
        "food_restrictions": redact_contact_info(getattr(payload, "food_restrictions", None) or "").strip() or None,
        "dogs_info": redact_contact_info(getattr(payload, "dogs_info", None) or "").strip() or None,
        "disclaimer_basic_upkeep": bool(getattr(payload, "disclaimer_basic_upkeep", False)),
        "disclaimer_medicine": bool(getattr(payload, "disclaimer_medicine", False)),
        "disclaimer_extra_hours": bool(getattr(payload, "disclaimer_extra_hours", False)),
        "disclaimer_transport": bool(getattr(payload, "disclaimer_transport", False)),
    }


def _validate_booking_questionnaire(data: dict) -> None:
    if not data.get("responsibilities"):
        raise HTTPException(status_code=400, detail="Please describe what the nanny will be responsible for")
    if not data.get("adult_present"):
        raise HTTPException(status_code=400, detail="Please confirm whether an adult will be present")
    if not data.get("booking_reason"):
        raise HTTPException(status_code=400, detail="Please share the reason for the booking")
    if not data.get("meal_option"):
        raise HTTPException(status_code=400, detail="Please select the meal arrangement")
    if not data.get("disclaimer_basic_upkeep"):
        raise HTTPException(status_code=400, detail="Please confirm the house upkeep disclaimer")
    if not data.get("disclaimer_medicine"):
        raise HTTPException(status_code=400, detail="Please confirm the medicine disclaimer")
    if not data.get("disclaimer_extra_hours"):
        raise HTTPException(status_code=400, detail="Please confirm the additional-hours disclaimer")
    if not data.get("disclaimer_transport"):
        raise HTTPException(status_code=400, detail="Please confirm the after-17:00 transport disclaimer")


def _build_booking_questionnaire_notes(base_notes: Optional[str], questionnaire: dict) -> Optional[str]:
    sections = []
    if base_notes:
        sections.append(f"Additional notes: {base_notes}")
    sections.extend([
        f"Nanny responsibilities: {questionnaire.get('responsibilities') or '-'}",
        f"Adult present at address: {questionnaire.get('adult_present') or '-'}",
        f"Reason for booking: {questionnaire.get('booking_reason') or '-'}",
        f"Children present: {questionnaire.get('kids_count') or 1}",
        f"Meal arrangement: {questionnaire.get('meal_option') or '-'}",
        f"Foods not allowed in home: {questionnaire.get('food_restrictions') or 'None provided'}",
        f"Dogs at home: {questionnaire.get('dogs_info') or 'None provided'}",
        f"House upkeep disclaimer understood: {'Yes' if questionnaire.get('disclaimer_basic_upkeep') else 'No'}",
        f"Medicine disclaimer understood: {'Yes' if questionnaire.get('disclaimer_medicine') else 'No'}",
        f"Additional hours disclaimer understood: {'Yes' if questionnaire.get('disclaimer_extra_hours') else 'No'}",
        f"After-17:00 transport disclaimer understood: {'Yes' if questionnaire.get('disclaimer_transport') else 'No'}",
    ])
    notes = "\n".join(sections).strip()
    return notes or None


def _attach_booking_request_slots(db: Session, req_id: int, windows: List[tuple]) -> None:
    next_id = _next_booking_request_slot_id(db)
    for start_dt, end_dt in windows:
        db.add(
            models.BookingRequestSlot(
                id=next_id,
                booking_request_id=req_id,
                starts_at=start_dt,
                ends_at=end_dt,
            )
        )
        next_id += 1


def _compute_day_rate(hours: float, is_weekend: bool, settings: dict) -> int:
    half_day = settings["weekend_half_day"] if is_weekend else settings["weekday_half_day"]
    full_day = settings["weekend_full_day"] if is_weekend else settings["weekday_full_day"]
    over9_rate = settings["over9_weekend"] if is_weekend else settings["over9_weekday"]
    if hours <= 6:
        return half_day
    if hours <= 9:
        return full_day
    extra = hours - 9
    return full_day + int(round(extra * over9_rate))


def _compute_booking_pricing(start_dt: datetime, end_dt: datetime, sleepover: bool, settings: dict) -> dict:
    start_local = _naive_utc(start_dt)
    end_local = _naive_utc(end_dt)
    start_date = start_local.date()
    is_weekend = _is_weekend_or_holiday(start_date)

    full_day = settings["weekend_full_day"] if is_weekend else settings["weekday_full_day"]
    half_day = settings["weekend_half_day"] if is_weekend else settings["weekday_half_day"]
    sleepover_add = settings["sleepover_add"]
    after17_rate = settings["after17_weekend"] if is_weekend else settings["after17_weekday"]
    over9_rate = settings["over9_weekend"] if is_weekend else settings["over9_weekday"]

    wage = 0
    if sleepover:
        # Base day rate + sleepover
        wage += full_day + sleepover_add

        # Sleepover covers until 07:00 next day
        next_morning = datetime.combine(start_date + timedelta(days=1), datetime.min.time()).replace(hour=settings["sleepover_end_hour"])
        if end_local > next_morning:
            extra_hours = _hours_between(next_morning, end_local)
            # Apply weekday/weekend for next day
            is_weekend_next = _is_weekend_or_holiday((start_date + timedelta(days=1)))
            if extra_hours < 3:
                wage += int(round(extra_hours * settings["sleepover_after7_hourly"]))
            elif extra_hours <= 6:
                wage += (settings["weekend_half_day"] if is_weekend_next else settings["weekday_half_day"])
            elif extra_hours <= 9:
                wage += (settings["weekend_full_day"] if is_weekend_next else settings["weekday_full_day"])
            else:
                wage += (settings["weekend_full_day"] if is_weekend_next else settings["weekday_full_day"]) + int(round((extra_hours - 9) * (settings["over9_weekend"] if is_weekend_next else settings["over9_weekday"])))
    else:
        hours = _hours_between(start_local, end_local)
        wage += _compute_day_rate(hours, is_weekend, settings)
        # after-hours top-up if end after 17:00
        after17 = datetime.combine(start_date, datetime.min.time()).replace(hour=17)
        if end_local > after17:
            after_hours = _hours_between(after17, end_local)
            wage += int(round(after_hours * after17_rate))
        # over 9 hours top-up handled in _compute_day_rate

    # Booking fee based on days booked (single day assumed here)
    days = 1
    if days <= 5:
        fee_pct = settings["booking_fee_pct_1_5"]
    elif days <= 10:
        fee_pct = settings["booking_fee_pct_6_10"]
    else:
        fee_pct = settings["booking_fee_pct_10_plus"]
    fee = int(round(wage * fee_pct))
    total = wage + fee
    return {
        "wage_cents": wage * 100,
        "booking_fee_pct": fee_pct,
        "booking_fee_cents": fee * 100,
        "total_cents": total * 100,
    }


def _validate_sa_id(id_number: str, dob_value: Optional[date] = None) -> Optional[str]:
    s = (id_number or "").strip()
    if not s.isdigit() or len(s) != 13:
        return "ID number must be 13 digits"

    yy = int(s[0:2])
    mm = int(s[2:4])
    dd = int(s[4:6])
    # infer century
    today = datetime.utcnow().date()
    century = 2000 if yy <= (today.year % 100) else 1900
    try:
        dob = date(century + yy, mm, dd)
    except Exception:
        return "ID number has invalid date of birth"

    if dob_value:
        if (dob_value.year % 100) != yy or dob_value.month != mm or dob_value.day != dd:
            return "ID number does not match date of birth"

    citizen = s[10]
    if citizen not in ("0", "1"):
        return "ID number has invalid citizenship digit"

    # Luhn checksum
    total = 0
    reverse_digits = list(map(int, reversed(s)))
    for i, d in enumerate(reverse_digits):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    if total % 10 != 0:
        return "ID number failed checksum"

    return None


def _availability_window(row) -> Optional[tuple]:
    if getattr(row, "start_dt", None) and getattr(row, "end_dt", None):
        try:
            return _parse_iso_dt(row.start_dt), _parse_iso_dt(row.end_dt)
        except Exception:
            return None
    if getattr(row, "date", None) and getattr(row, "start_time", None) and getattr(row, "end_time", None):
        try:
            start = datetime.combine(row.date, row.start_time)
            end = datetime.combine(row.date, row.end_time)
            return start, end
        except Exception:
            return None
    return None


def _booking_window(row) -> Optional[tuple]:
    if getattr(row, "start_dt", None) and getattr(row, "end_dt", None):
        try:
            return _parse_iso_dt(row.start_dt), _parse_iso_dt(row.end_dt)
        except Exception:
            return None
    if getattr(row, "starts_at", None) and getattr(row, "ends_at", None):
        try:
            return row.starts_at, row.ends_at
        except Exception:
            return None
    return None


def _booking_request_windows(db: Session, req: models.BookingRequest) -> List[tuple]:
    slots = (
        db.query(models.BookingRequestSlot)
        .filter(models.BookingRequestSlot.booking_request_id == req.id)
        .order_by(models.BookingRequestSlot.starts_at.asc())
        .all()
    )
    windows: List[tuple] = []
    for slot in slots:
        start = getattr(slot, "starts_at", None)
        end = getattr(slot, "ends_at", None)
        if not start or not end or end <= start:
            continue
        windows.append((start, end))
    if windows:
        return windows

    try:
        start = _parse_iso_dt(req.start_dt or req.requested_starts_at)
        end = _parse_iso_dt(req.end_dt or req.requested_ends_at)
    except Exception:
        return []
    if end <= start:
        return []
    return [(start, end)]


def _is_nanny_available(db: Session, nanny_id: int, start_dt: datetime, end_dt: datetime) -> bool:
    available_rows = (
        db.query(models.NannyAvailability)
        .filter(
            models.NannyAvailability.nanny_id == nanny_id,
            models.NannyAvailability.type != "blocked",
            models.NannyAvailability.is_available == True,
        )
        .all()
    )
    if not available_rows:
        return False
    has_available_window = False
    for row in available_rows:
        window = _availability_window(row)
        if not window:
            continue
        if _overlaps(start_dt, end_dt, window[0], window[1]):
            has_available_window = True
            break
    if not has_available_window:
        return False

    blocked_rows = (
        db.query(models.NannyAvailability)
        .filter(
            models.NannyAvailability.nanny_id == nanny_id,
            or_(models.NannyAvailability.type == "blocked", models.NannyAvailability.is_available == False),
        )
        .all()
    )
    for row in blocked_rows:
        window = _availability_window(row)
        if not window:
            continue
        if _overlaps(start_dt, end_dt, window[0], window[1]):
            return False

    active_statuses = ["approved", "active", "pending"]
    bookings = (
        db.query(models.Booking)
        .filter(models.Booking.nanny_id == nanny_id, models.Booking.status.in_(active_statuses))
        .all()
    )
    for row in bookings:
        window = _booking_window(row)
        if not window:
            continue
        if _overlaps(start_dt, end_dt, window[0], window[1]):
            return False

    return True


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def _fmt_booking_lines(b):
    return "\n".join(
        [
            f"Booking ID: {b.id}",
            f"Parent user_id: {b.client_user_id}",
            f"Nanny ID: {b.nanny_id}",
            f"Starts: {b.starts_at}",
            f"Ends: {b.ends_at}",
            f"Status: {b.status}",
            f"Location mode: {getattr(b, 'location_mode', None)}",
            f"Location label: {getattr(b, 'location_label', None)}",
            f"Lat: {getattr(b, 'lat', None)}",
            f"Lng: {getattr(b, 'lng', None)}",
        ]
    )


def _safe_send(to_email: str, subject: str, body: str):
    if not to_email:
        return
    msg = EmailMessage(to=[to_email], subject=subject, body=body)
    get_email_client().send(msg)


def notify_booking_created(parent_user_id: int, nanny_id: int, booking_id: int, starts_at, ends_at, location_label: Optional[str]):
    client = get_email_client()
    base = app_base_url()

    subject = f"New booking request #{booking_id}"
    label = location_label or "Unlabeled"
    body = "\n".join(
        [
            "A new booking has been created.",
            f"booking_id: {booking_id}",
            f"parent_user_id: {parent_user_id}",
            f"nanny_id: {nanny_id}",
            f"starts_at: {starts_at}",
            f"ends_at: {ends_at}",
            f"location_label: {label}",
            f"admin_link: {base}/admin",
        ]
    )

    db = SessionLocal()
    try:
        nanny_email = None
        try:
            nanny = db.query(models.Nanny).filter(models.Nanny.id == nanny_id).first()
            if nanny and nanny.user:
                nanny_email = getattr(nanny.user, "email", None)
        except Exception:
            nanny_email = None

        if nanny_email:
            client.send(EmailMessage(to=[nanny_email], subject=subject, body=body))

        admins = admin_emails()
        if admins:
            client.send(EmailMessage(to=admins, subject=subject, body=body))

    except Exception as e:
        print(f"[EMAIL][NOTIFY_FAIL] {e!r}")
        return
    finally:
        db.close()


def notify_booking_reassigned(parent_user_id: int, nanny_id: int, request_id: int, starts_at, ends_at):
    client = get_email_client()
    base = app_base_url()
    db = SessionLocal()
    try:
        parent = db.query(models.User).filter(models.User.id == parent_user_id).first()
        nanny = db.query(models.Nanny).filter(models.Nanny.id == nanny_id).first()
        nanny_user = db.query(models.User).filter(models.User.id == nanny.user_id).first() if nanny else None

        if not parent or not parent.email:
            return

        subject = f"Booking request #{request_id} updated"
        nanny_name = nanny_user.name if nanny_user else f"Nanny #{nanny_id}"
        body = "\n".join(
            [
                "Your booking request was not approved for the original nanny.",
                f"We have assigned {nanny_name} instead.",
                f"starts_at: {starts_at}",
                f"ends_at: {ends_at}",
                f"portal: {base}",
            ]
        )
        client.send(EmailMessage(to=[parent.email], subject=subject, body=body))
    finally:
        db.close()


def notify_booking_nanny_response(
    req: models.BookingRequest,
    nanny_user: Optional[models.User],
    response: str,
) -> None:
    client = get_email_client()
    db = SessionLocal()
    try:
        parent = db.query(models.User).filter(models.User.id == req.parent_user_id).first()
        admins = admin_emails()
        nanny_name = getattr(nanny_user, "name", None) or f"Nanny #{req.nanny_id}"
        response_label = {
            "accepted": "accepted",
            "declined": "declined",
            "deciding": "marked the booking as still deciding",
        }.get(response, response)
        subject = f"Nanny response for booking request #{req.id}"
        body = "\n".join(
            [
                f"{nanny_name} has {response_label}.",
                f"booking_request_id: {req.id}",
                f"start: {req.start_dt or (req.requested_starts_at.isoformat() if req.requested_starts_at else '-')}",
                f"end: {req.end_dt or (req.requested_ends_at.isoformat() if req.requested_ends_at else '-')}",
                f"response_note: {getattr(req, 'nanny_response_note', None) or '-'}",
                f"admin_link: {app_base_url()}/static/admin_dashboard.html",
            ]
        )
        recipients = []
        if parent and getattr(parent, "email", None):
            recipients.append(parent.email)
        recipients.extend(admins or [])
        sent = set()
        for recipient in recipients:
            if not recipient or recipient in sent:
                continue
            sent.add(recipient)
            client.send(EmailMessage(to=[recipient], subject=subject, body=body))
    except Exception as e:
        print(f"[EMAIL][BOOKING_NANNY_RESPONSE_FAIL] {e!r}")
    finally:
        db.close()


def notify_admin_unaccepted_booking_request(
    req: models.BookingRequest,
    parent_user: Optional[models.User],
    nanny_user: Optional[models.User],
) -> None:
    admins = admin_emails()
    if not admins:
        return
    client = get_email_client()
    subject = f"Booking request #{req.id} still unaccepted after 6 hours"
    body = "\n".join(
        [
            "A booking request has not been accepted within 6 hours and may need manual admin intervention.",
            f"booking_request_id: {req.id}",
            f"parent: {getattr(parent_user, 'name', None) or '-'} ({getattr(parent_user, 'email', None) or '-'})",
            f"requested_nanny: {getattr(nanny_user, 'name', None) or '-'}",
            f"start: {req.start_dt or (req.requested_starts_at.isoformat() if req.requested_starts_at else '-')}",
            f"end: {req.end_dt or (req.requested_ends_at.isoformat() if req.requested_ends_at else '-')}",
            f"admin_link: {app_base_url()}/static/admin_dashboard.html",
        ]
    )
    try:
        client.send(EmailMessage(to=admins, subject=subject, body=body))
    except Exception as e:
        print(f"[EMAIL][UNACCEPTED_BOOKING_NOTIFY_FAIL] {e!r}")


def notify_admin_nanny_cancelled_booking(
    booking: models.Booking,
    nanny_user: Optional[models.User],
    reason: Optional[str],
) -> None:
    client = get_email_client()
    admins = admin_emails()
    if not admins:
        return

    subject = f"Nanny cancelled booking #{booking.id}"
    body = "\n".join(
        [
            "A nanny cancelled a booking and admin attention is required before the client is contacted.",
            f"booking_id: {booking.id}",
            f"nanny: {getattr(nanny_user, 'name', None) or 'Unknown nanny'}",
            f"parent_user_id: {booking.client_user_id}",
            f"starts_at: {booking.start_dt or (booking.starts_at.isoformat() if booking.starts_at else '-')}",
            f"ends_at: {booking.end_dt or (booking.ends_at.isoformat() if booking.ends_at else '-')}",
            f"reason: {reason or '-'}",
            f"admin_link: {app_base_url()}/static/admin_dashboard.html",
        ]
    )
    try:
        client.send(EmailMessage(to=admins, subject=subject, body=body))
    except Exception as e:
        print(f"[EMAIL][ADMIN_CANCEL_NOTIFY_FAIL] {e!r}")


def _booking_request_reason_label(reason: Optional[str]) -> Optional[str]:
    raw = (reason or "").strip()
    if not raw:
        return None
    labels = {
        "accepted_by_nanny": "Accepted by nanny",
        "filled": "Filled by another nanny",
        "filled_higher_rating": "Filled by another nanny with a higher rating",
        "cancelled_by_parent": "Cancelled by parent",
    }
    return labels.get(raw, raw.replace("_", " ").strip().capitalize())


def _parse_booking_questionnaire_notes(notes: Optional[str]) -> dict:
    parsed = {"additional_notes": None, "items": []}
    text = (notes or "").strip()
    if not text:
        return parsed
    for line in [line.strip() for line in text.splitlines() if line.strip()]:
        if ":" in line:
            label, value = line.split(":", 1)
            clean_label = label.strip()
            clean_value = value.strip() or "-"
            if clean_label.lower() == "additional notes":
                parsed["additional_notes"] = clean_value
            parsed["items"].append({"label": clean_label, "value": clean_value})
        else:
            parsed["items"].append({"label": "Notes", "value": line})
    return parsed


def _booking_questionnaire_from_notes(notes: Optional[str]) -> dict:
    parsed = _parse_booking_questionnaire_notes(notes)
    values = {
        "notes": parsed.get("additional_notes"),
        "responsibilities": None,
        "adult_present": None,
        "booking_reason": None,
        "sleepover_expectations": None,
        "sleepover_reason": None,
        "kids_count": 1,
        "meal_option": None,
        "food_restrictions": None,
        "dogs_info": None,
        "disclaimer_basic_upkeep": False,
        "disclaimer_medicine": False,
        "disclaimer_extra_hours": False,
        "disclaimer_transport": False,
    }
    bool_map = {"yes": True, "true": True, "no": False, "false": False}
    label_map = {
        "nanny responsibilities": "responsibilities",
        "adult present at address": "adult_present",
        "reason for booking": "booking_reason",
        "sleepover expectations": "sleepover_expectations",
        "sleepover reason": "sleepover_reason",
        "children present": "kids_count",
        "meal arrangement": "meal_option",
        "foods not allowed in home": "food_restrictions",
        "dogs at home": "dogs_info",
        "house upkeep disclaimer understood": "disclaimer_basic_upkeep",
        "medicine disclaimer understood": "disclaimer_medicine",
        "additional hours disclaimer understood": "disclaimer_extra_hours",
        "after-17:00 transport disclaimer understood": "disclaimer_transport",
    }
    for item in parsed.get("items", []):
        label = str(item.get("label") or "").strip().lower()
        target = label_map.get(label)
        if not target:
            continue
        raw_value = item.get("value")
        if target == "kids_count":
            try:
                values[target] = _sanitize_booking_kids_count(raw_value)
            except Exception:
                values[target] = 1
        elif target.startswith("disclaimer_"):
            values[target] = bool_map.get(str(raw_value or "").strip().lower(), False)
        else:
            values[target] = raw_value
    return values


def _booking_elapsed_minutes(booking: models.Booking) -> Optional[int]:
    if not getattr(booking, "check_in_at", None) or not getattr(booking, "check_out_at", None):
        return None
    delta = booking.check_out_at - booking.check_in_at
    return max(0, int(delta.total_seconds() // 60))


def _booking_scheduled_minutes(booking: models.Booking) -> Optional[int]:
    if not getattr(booking, "starts_at", None) or not getattr(booking, "ends_at", None):
        return None
    delta = booking.ends_at - booking.starts_at
    return max(0, int(delta.total_seconds() // 60))


def _find_related_bookings_for_request(db: Session, req: models.BookingRequest) -> List[models.Booking]:
    rows = (
        db.query(models.Booking)
        .filter(models.Booking.booking_request_id == req.id)
        .order_by(models.Booking.starts_at.asc(), models.Booking.id.asc())
        .all()
    )
    if rows:
        return rows

    windows = _booking_request_windows(db, req)
    if not windows:
        try:
            start_dt = _parse_iso_dt(req.start_dt or req.requested_starts_at)
            end_dt = _parse_iso_dt(req.end_dt or req.requested_ends_at)
            windows = [(start_dt, end_dt)]
        except Exception:
            return []

    start_floor = min(w[0] for w in windows)
    end_ceiling = max(w[1] for w in windows)
    return (
        db.query(models.Booking)
        .filter(
            models.Booking.client_user_id == req.parent_user_id,
            models.Booking.nanny_id == req.nanny_id,
            models.Booking.starts_at <= end_ceiling,
            models.Booking.ends_at >= start_floor,
        )
        .order_by(models.Booking.starts_at.asc(), models.Booking.id.asc())
        .all()
    )


def _sync_confirmed_booking_request_to_google_calendar(db: Session, req: models.BookingRequest) -> None:
    if req.status != "approved" or (getattr(req, "nanny_response_status", None) or "") != "accepted":
        return
    bookings = [
        b for b in _find_related_bookings_for_request(db, req)
        if b.status in ("approved", "accepted") and not getattr(b, "google_calendar_event_id", None)
    ]
    for booking in bookings:
        try:
            sync_booking_to_google_calendar(db, booking)
        except Exception as exc:
            booking.google_calendar_sync_error = str(exc)[:500]
            db.commit()


def _cancel_related_bookings_for_request(
    db: Session,
    req: models.BookingRequest,
    *,
    actor_role: str,
    actor_user_id: Optional[int],
    reason: str,
) -> List[models.Booking]:
    cancelled: List[models.Booking] = []
    now = datetime.utcnow()
    for booking in _find_related_bookings_for_request(db, req):
        if booking.status in ("completed", "cancelled", "rejected"):
            continue
        booking.status = "cancelled"
        booking.cancelled_at = now
        booking.cancellation_reason = reason
        booking.cancellation_actor_role = actor_role
        booking.cancellation_actor_user_id = actor_user_id
        cancelled.append(booking)
    return cancelled


def _send_whatsapp_message(phone: Optional[str], message: str) -> bool:
    to = (phone or "").strip()
    if not to:
        return False

    webhook = (os.getenv("WHATSAPP_WEBHOOK_URL") or "").strip()
    token = (os.getenv("WHATSAPP_WEBHOOK_TOKEN") or "").strip()
    if not webhook:
        print("[WHATSAPP][LOG]")
        print(f"to: {to}")
        print("message:")
        print(message)
        print("[WHATSAPP][END]")
        return True

    payload = json.dumps({"to": to, "message": message}).encode("utf-8")
    headers = {"Content-Type": "application/json", "User-Agent": "nanny-app/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = UrlRequest(webhook, data=payload, headers=headers, method="POST")
    try:
        with urlopen(req, timeout=10) as resp:
            _ = resp.read()
        return True
    except Exception as e:
        print(f"[WHATSAPP][SEND_FAIL] {e!r}")
        return False


def _resolve_parent_notification_channels(parent_profile: Optional[models.ParentProfile]) -> set:
    channels = set()
    flags = []
    if parent_profile and getattr(parent_profile, "access_flags_json", None):
        try:
            parsed = json.loads(parent_profile.access_flags_json) or []
            if isinstance(parsed, list):
                flags = [str(x).strip().lower() for x in parsed if str(x).strip()]
        except Exception:
            flags = []

    for flag in flags:
        if "email" in flag:
            channels.add("email")
        if "whatsapp" in flag:
            channels.add("whatsapp")

    # Fallback when no explicit channel is configured.
    if not channels:
        channels.add("email")
    return channels


def notify_parent_nanny_checked_in(db: Session, booking: models.Booking, nanny_user: Optional[models.User]) -> dict:
    parent_user = db.query(models.User).filter(models.User.id == booking.client_user_id).first()
    if not parent_user:
        return {"email": False, "whatsapp": False}
    parent_profile = db.query(models.ParentProfile).filter(models.ParentProfile.user_id == parent_user.id).first()
    channels = _resolve_parent_notification_channels(parent_profile)

    start_str = booking.start_dt or (booking.starts_at.isoformat() if booking.starts_at else "-")
    end_str = booking.end_dt or (booking.ends_at.isoformat() if booking.ends_at else "-")
    location = getattr(booking, "formatted_address", None) or getattr(booking, "location_label", None) or "your booking location"
    nanny_name = getattr(nanny_user, "name", None) or "Your nanny"

    email_sent = False
    if "email" in channels and getattr(parent_user, "email", None):
        subject = f"Nanny checked in for booking #{booking.id}"
        body = "\n".join(
            [
                f"{nanny_name} has checked in and started the booking.",
                f"Booking ID: {booking.id}",
                f"Scheduled time: {start_str} to {end_str}",
                f"Location: {location}",
            ]
        )
        try:
            get_email_client().send(EmailMessage(to=[parent_user.email], subject=subject, body=body))
            email_sent = True
        except Exception as e:
            print(f"[EMAIL][CHECKIN_NOTIFY_FAIL] {e!r}")

    whatsapp_sent = False
    whatsapp_phone = None
    if parent_profile and getattr(parent_profile, "phone", None):
        whatsapp_phone = parent_profile.phone
    elif getattr(parent_user, "phone", None):
        whatsapp_phone = parent_user.phone
    if "whatsapp" in channels and whatsapp_phone:
        msg = (
            f"{nanny_name} checked in for booking #{booking.id}. "
            f"Time: {start_str} to {end_str}. "
            f"Location: {location}."
        )
        whatsapp_sent = _send_whatsapp_message(whatsapp_phone, msg)

    return {"email": email_sent, "whatsapp": whatsapp_sent}


@router.get("/qualifications")
def list_qualifications(db: Session = Depends(get_db)):
    rows = db.query(models.Qualification).order_by(models.Qualification.name.asc()).all()
    return [{"id": r.id, "name": r.name} for r in rows]


@router.get("/nanny-tags")
def list_nanny_tags(db: Session = Depends(get_db)):
    rows = _ensure_default_nanny_tags(db)
    return [{"id": r.id, "name": r.name} for r in rows]


@router.get("/languages")
def list_languages(db: Session = Depends(get_db)):
    rows = db.query(models.Language).order_by(models.Language.name.asc()).all()
    return [{"id": r.id, "name": r.name} for r in rows]


@router.get("/health")
def health(request: Request, db: Session = Depends(get_db)):
    # auth enabled if any route starts with /auth
    auth_enabled = any(getattr(r, "path", "").startswith("/auth") for r in request.app.routes)

    # db ping
    db_ok = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    # basic counts
    counts = {
        "users": db.query(models.User).count(),
        "nannies": db.query(models.NannyProfile).count(),
        "reviews": db.query(models.Review).count(),
    }

    return {
        "ok": bool(db_ok),
        "auth_enabled": auth_enabled,
        "db_ok": db_ok,
        "counts": counts,
    }


@router.post("/auth/login", response_model=schemas.LoginResponse)
def auth_login(payload: schemas.LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = (
        db.query(models.User)
        .filter(func.lower(models.User.email) == payload.email.lower())
        .first()
    )
    if not user or not _verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if _password_needs_rehash(user.password_hash):
        try:
            user.password_hash = hash_password(payload.password)
            db.commit()
        except Exception:
            # Never block successful auth due to best-effort hash migration.
            db.rollback()

    nanny_id = None
    if user.role == "nanny":
        nanny = db.query(models.Nanny).filter(models.Nanny.user_id == user.id).first()
        if nanny:
            nanny_id = nanny.id

    token = _create_access_token(user)
    _set_access_cookie(response, token)
    _set_csrf_cookie(response)
    return {
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "nanny_id": nanny_id,
            "is_admin": bool(getattr(user, "is_admin", False)),
            "is_active": bool(getattr(user, "is_active", True)),
        },
    }


@router.post("/auth/signup", response_model=schemas.AuthResponse)
def auth_signup(payload: schemas.SignupRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()

    existing = db.query(models.User).filter(func.lower(models.User.email) == email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already exists")

    if len(payload.password) < 6:
        raise HTTPException(status_code=400, detail="Password too short")

    user = models.User(
        name=payload.name.strip(),
        email=email,
        password_hash=hash_password(payload.password),
        role=payload.role,
        phone=payload.phone,
        phone_alt=payload.phone_alt,
        is_active=False if payload.role == "nanny" else True,
    )
    db.add(user)
    db.flush()

    nanny_id = None

    if payload.role == "parent":
        db.add(models.ParentProfile(user_id=user.id))
    elif payload.role == "nanny":
        def _norm_text(value: Optional[str]) -> Optional[str]:
            if value is None:
                return None
            value = value.strip()
            return value or None

        nat = payload.nationality.strip().lower() if payload.nationality else ""
        permit_status = _norm_text(payload.permit_status)
        has_own_car = payload.has_own_car if payload.has_own_car is not None else None
        has_drivers_license = payload.has_drivers_license if payload.has_drivers_license is not None else None
        has_own_kids = payload.has_own_kids if payload.has_own_kids is not None else None
        own_kids_details = _norm_text(payload.own_kids_details)

        if not _norm_text(payload.gender):
            raise HTTPException(status_code=400, detail="Gender is required")
        if not _norm_text(payload.ethnicity):
            raise HTTPException(status_code=400, detail="Race is required")
        if not _norm_text(payload.job_type):
            raise HTTPException(status_code=400, detail="Job type is required")
        if not _norm_text(payload.police_clearance_status):
            raise HTTPException(status_code=400, detail="Police clearance status is required")
        if not _norm_text(payload.my_nanny_training_status):
            raise HTTPException(status_code=400, detail="Training status is required")
        if has_own_car is True and has_drivers_license is None:
            raise HTTPException(status_code=400, detail="Driver's license status is required")
        if has_own_kids is True and not own_kids_details:
            raise HTTPException(status_code=400, detail="Please share how old your children are and where they stay")

        if nat == "south african":
            if not payload.sa_id_number:
                raise HTTPException(status_code=400, detail="South African ID number is required")
            err = _validate_sa_id(payload.sa_id_number)
            if err:
                raise HTTPException(status_code=400, detail=err)
        elif nat:
            if not payload.passport_number:
                raise HTTPException(status_code=400, detail="Passport number is required")
            if permit_status not in {"permit", "waiver", "receipt"}:
                raise HTTPException(
                    status_code=400,
                    detail="You need a waiver/receipt or permit for approval. Once you obtain this, please email it to nannies.info@gmail.com",
                )
        nanny = models.Nanny(user_id=user.id, approved=False)
        db.add(nanny)
        db.flush()
        profile = models.NannyProfile(
            nanny_id=nanny.id,
            nationality=_norm_text(payload.nationality),
            gender=_norm_text(payload.gender),
            ethnicity=_norm_text(payload.ethnicity),
            passport_number=_norm_text(payload.passport_number),
            passport_expiry=_norm_text(payload.passport_expiry),
            permit_status=permit_status,
            work_permit=True if permit_status == "permit" else (False if permit_status in {"waiver", "receipt"} else payload.work_permit if payload.work_permit is not None else None),
            work_permit_expiry=_norm_text(payload.work_permit_expiry),
            waiver=True if permit_status == "waiver" else (False if permit_status in {"permit", "receipt"} else payload.waiver if payload.waiver is not None else None),
            sa_id_number=_norm_text(payload.sa_id_number),
            sa_id_document_url=_norm_text(payload.sa_id_document_url),
            has_own_car=has_own_car,
            has_drivers_license=has_drivers_license,
            job_type=_norm_text(payload.job_type),
            police_clearance_status=_norm_text(payload.police_clearance_status),
            has_own_kids=has_own_kids,
            own_kids_details=own_kids_details,
            medical_conditions=_norm_text(payload.medical_conditions),
            my_nanny_training_status=_norm_text(payload.my_nanny_training_status),
        )
        db.add(profile)
        nanny_id = nanny.id
    else:
        raise HTTPException(status_code=400, detail="Invalid role")

    db.commit()

    if payload.role == "parent":
        prof = db.query(models.ParentProfile).filter(models.ParentProfile.user_id == user.id).first()
        if prof:
            after = _parent_profile_snapshot(prof)
            log_profile_update(
                db,
                actor_user=user,
                target_user_id=user.id,
                entity="parent_profiles",
                entity_id=prof.id,
                before_obj={},
                after_obj=after,
                request=request,
                action="create",
            )
    elif payload.role == "nanny":
        nanny = db.query(models.Nanny).filter(models.Nanny.user_id == user.id).first()
        if nanny:
            profile = db.query(models.NannyProfile).filter(models.NannyProfile.nanny_id == nanny.id).first()
            if profile:
                after = {
                    "bio": profile.bio,
                    "date_of_birth": profile.date_of_birth,
                    "nationality": profile.nationality,
                    "ethnicity": profile.ethnicity,
                    "qualification_ids": [q.id for q in (profile.qualifications or [])],
                    "tag_ids": [t.id for t in (profile.tags or [])],
                    "language_ids": [l.id for l in (profile.languages or [])],
                }
                log_profile_update(
                    db,
                    actor_user=user,
                    target_user_id=user.id,
                    entity="nanny_profiles",
                    entity_id=profile.id,
                    before_obj={},
                    after_obj=after,
                    request=request,
                    action="create",
                )

    token = _create_access_token(user)
    _set_access_cookie(response, token)
    _set_csrf_cookie(response)
    return {
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "nanny_id": nanny_id,
            "is_admin": bool(getattr(user, "is_admin", False)),
        },
    }


@router.get("/auth/me", response_model=schemas.AuthUserOut)
def auth_me(authorization: Optional[str] = Header(default=None), db: Session = Depends(get_db)):
    token = _resolve_auth_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = _decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = db.query(models.User).filter(models.User.id == payload["sub"]).first()
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    nanny_id = None
    nanny_application_status = None
    nanny_admin_reason = None
    if user.role == "nanny":
        nanny = db.query(models.Nanny).filter(models.Nanny.user_id == user.id).first()
        if nanny:
            nanny_id = nanny.id
            profile = db.query(models.NannyProfile).filter(models.NannyProfile.nanny_id == nanny.id).first()
            if profile:
                nanny_application_status = getattr(profile, "application_status", None)
                nanny_admin_reason = getattr(profile, "admin_reason", None)
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "nanny_id": nanny_id,
        "is_admin": bool(getattr(user, "is_admin", False)),
        "is_active": bool(getattr(user, "is_active", True)),
        "nanny_application_status": nanny_application_status,
        "nanny_admin_reason": nanny_admin_reason,
    }


@router.get("/me", response_model=schemas.AuthUserOut)
def me_alias(authorization: Optional[str] = Header(default=None), db: Session = Depends(get_db)):
    return auth_me(authorization=authorization, db=db)


@router.post("/auth/logout")
def auth_logout(response: Response):
    _clear_access_cookie(response)
    _clear_csrf_cookie(response)
    return {"ok": True}


@router.get("/admin/me")
def admin_me(authorization: Optional[str] = Header(default=None), db: Session = Depends(get_db)):
    user = _require_user(authorization, db)
    if not getattr(user, "is_admin", False):
        raise HTTPException(status_code=403, detail="Forbidden")
    return {"ok": True, "email": user.email, "id": user.id}


@router.post("/admin/impersonate")
def admin_impersonate(
    payload: schemas.AdminImpersonateRequest,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    admin = require_admin(authorization, db)
    target = db.query(models.User).filter(models.User.id == payload.user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    token = _create_impersonation_token(target, admin.id)
    return {"access_token": token}


def _require_user(authorization: Optional[str], db: Session) -> models.User:
    token = _resolve_auth_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = _decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = db.query(models.User).filter(models.User.id == payload["sub"]).first()
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def require_admin(authorization: Optional[str], db: Session) -> models.User:
    user = _require_user(authorization, db)
    if not getattr(user, "is_admin", False):
        raise HTTPException(status_code=403, detail="Forbidden")
    return user


def _require_admin_user(authorization: Optional[str], db: Session) -> models.User:
    return require_admin(authorization, db)


def _require_nanny_user_not_on_hold(authorization: Optional[str], db: Session) -> tuple[models.User, models.Nanny, Optional[models.NannyProfile]]:
    user = _require_user(authorization, db)
    if user.role != "nanny":
        raise HTTPException(status_code=403, detail="Forbidden")
    nanny = db.query(models.Nanny).filter(models.Nanny.user_id == user.id).first()
    if not nanny:
        raise HTTPException(status_code=404, detail="Nanny not found")
    profile = db.query(models.NannyProfile).filter(models.NannyProfile.nanny_id == nanny.id).first()
    if profile and getattr(profile, "application_status", None) == "hold":
        raise HTTPException(
            status_code=423,
            detail="Your profile is on hold due to outstanding information. Please update your profile to continue.",
        )
    return user, nanny, profile


def _nanny_profile_snapshot(user: models.User, profile: models.NannyProfile) -> dict:
    tag_ids = [t.id for t in (profile.tags or [])]
    language_ids = [l.id for l in (profile.languages or [])]
    previous_jobs = []
    raw_jobs = getattr(profile, "previous_jobs_json", None)
    if raw_jobs:
        try:
            parsed = json.loads(raw_jobs)
            if isinstance(parsed, list):
                previous_jobs = parsed
        except Exception:
            previous_jobs = []
    certificate_urls = []
    raw_certs = getattr(profile, "certificates_json", None)
    if raw_certs:
        try:
            parsed_certs = json.loads(raw_certs)
            if isinstance(parsed_certs, list):
                certificate_urls = [str(url).strip() for url in parsed_certs if str(url).strip()]
        except Exception:
            certificate_urls = []
    return {
        "full_name": user.name,
        "gender": getattr(profile, "gender", None),
        "dob": getattr(profile, "date_of_birth", None),
        "bio": getattr(profile, "bio", None),
        "nationality": getattr(profile, "nationality", None),
        "race": getattr(profile, "ethnicity", None),
        "permit_status": getattr(profile, "permit_status", None),
        "has_own_car": getattr(profile, "has_own_car", None),
        "has_drivers_license": getattr(profile, "has_drivers_license", None),
        "job_type": getattr(profile, "job_type", None),
        "current_job_availability": getattr(profile, "current_job_availability", None),
        "police_clearance_status": getattr(profile, "police_clearance_status", None),
        "has_own_kids": getattr(profile, "has_own_kids", None),
        "own_kids_details": getattr(profile, "own_kids_details", None),
        "medical_conditions": getattr(profile, "medical_conditions", None),
        "my_nanny_training_status": getattr(profile, "my_nanny_training_status", None),
        "dog_preference": getattr(profile, "dog_preference", None),
        "studying_details": getattr(profile, "studying_details", None),
        "police_clearance_document_url": getattr(profile, "police_clearance_document_url", None),
        "drivers_license_document_url": getattr(profile, "drivers_license_document_url", None),
        "certificate_urls": certificate_urls,
        "previous_jobs": previous_jobs,
        "qualification_ids": sorted([q.id for q in (profile.qualifications or [])]),
        "tag_ids": sorted(tag_ids),
        "language_ids": sorted(language_ids),
    }


def _nanny_location_snapshot(profile: models.NannyProfile) -> dict:
    return {
        "lat": getattr(profile, "lat", None),
        "lng": getattr(profile, "lng", None),
        "formatted_address": getattr(profile, "formatted_address", None),
        "suburb": getattr(profile, "suburb", None),
        "city": getattr(profile, "city", None),
        "province": getattr(profile, "province", None),
        "postal_code": getattr(profile, "postal_code", None),
        "country": getattr(profile, "country", None),
        "place_id": getattr(profile, "place_id", None),
    }


def _parent_profile_snapshot(prof: models.ParentProfile) -> dict:
    kids_ages = []
    if prof.kids_ages_json:
        try:
            kids_ages = json.loads(prof.kids_ages_json) or []
        except Exception:
            kids_ages = []

    desired_tag_ids = []
    if prof.desired_tag_ids_json:
        try:
            desired_tag_ids = json.loads(prof.desired_tag_ids_json) or []
        except Exception:
            desired_tag_ids = []

    access_flags = []
    if prof.access_flags_json:
        try:
            access_flags = json.loads(prof.access_flags_json) or []
        except Exception:
            access_flags = []

    return {
        "phone": prof.phone,
        "kids_count": prof.kids_count,
        "kids_ages": kids_ages,
        "desired_tag_ids": desired_tag_ids,
        "home_language_id": prof.home_language_id,
        "residence_type": prof.residence_type,
        "special_notes": prof.special_notes,
        "family_photo_url": prof.family_photo_url,
        "access_flags": access_flags,
    }


def _parent_location_snapshot(loc: models.ParentLocation) -> dict:
    return {
        "id": loc.id,
        "label": loc.label,
        "place_id": loc.place_id,
        "formatted_address": loc.formatted_address,
        "street": loc.street,
        "suburb": loc.suburb,
        "city": loc.city,
        "province": loc.province,
        "postal_code": loc.postal_code,
        "country": loc.country,
        "lat": loc.lat,
        "lng": loc.lng,
        "is_default": bool(loc.is_default),
    }


@router.post("/nannies/me/photo")
def upload_nanny_photo(
    request: Request,
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _require_user(authorization, db)
    if user.role != "nanny":
        raise HTTPException(status_code=403, detail="Forbidden")

    allowed = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }
    ext = allowed.get(file.content_type or "")
    if not ext:
        raise HTTPException(status_code=400, detail="Unsupported image type")

    upload_dir = Path(__file__).resolve().parents[1] / "static" / "uploads" / "nannies"
    upload_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{user.id}_{uuid.uuid4().hex}{ext}"
    dest = upload_dir / filename

    try:
        data = file.file.read()
        dest.write_bytes(data)
    finally:
        try:
            file.file.close()
        except Exception:
            pass

    before = {"profile_photo_url": getattr(user, "profile_photo_url", None)}
    user.profile_photo_url = f"/static/uploads/nannies/{filename}"
    db.add(user)
    db.commit()
    db.refresh(user)

    after = {"profile_photo_url": getattr(user, "profile_photo_url", None)}
    log_audit(
        db,
        actor_user=user,
        target_user_id=user.id,
        entity="users",
        entity_id=user.id,
        action="update",
        before_obj=before,
        after_obj=after,
        changed_fields=None,
        request=request,
    )

    return {"url": user.profile_photo_url}


@router.post("/parents/me/family-photo")
def upload_parent_family_photo(
    request: Request,
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _require_user(authorization, db)
    if user.role != "parent":
        raise HTTPException(status_code=403, detail="Forbidden")

    allowed = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }
    ext = allowed.get(file.content_type or "")
    if not ext:
        raise HTTPException(status_code=400, detail="Unsupported image type")

    upload_dir = Path(__file__).resolve().parents[1] / "static" / "uploads" / "parents"
    upload_dir.mkdir(parents=True, exist_ok=True)

    filename = f"family_{user.id}_{uuid.uuid4().hex}{ext}"
    dest = upload_dir / filename

    try:
        data = file.file.read()
        dest.write_bytes(data)
    finally:
        try:
            file.file.close()
        except Exception:
            pass

    prof = db.query(models.ParentProfile).filter(models.ParentProfile.user_id == user.id).first()
    if not prof:
        prof = models.ParentProfile(user_id=user.id)
        db.add(prof)

    before = _parent_profile_snapshot(prof)
    prof.family_photo_url = f"/static/uploads/parents/{filename}"
    db.add(prof)
    db.commit()
    db.refresh(prof)

    after = _parent_profile_snapshot(prof)
    log_audit(
        db,
        actor_user=user,
        target_user_id=user.id,
        entity="parent_profiles",
        entity_id=prof.id,
        action="update",
        before_obj=before,
        after_obj=after,
        changed_fields=["family_photo_url"],
        request=request,
    )

    return {"url": prof.family_photo_url}


@router.post("/nannies/me/id-document")
def upload_nanny_id_document(
    request: Request,
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _require_user(authorization, db)
    if user.role != "nanny":
        raise HTTPException(status_code=403, detail="Forbidden")

    allowed = {
        "application/pdf": ".pdf",
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }
    ext = allowed.get(file.content_type or "")
    if not ext:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    upload_dir = Path(__file__).resolve().parents[1] / "static" / "uploads" / "nannies"
    upload_dir.mkdir(parents=True, exist_ok=True)

    filename = f"id_{user.id}_{uuid.uuid4().hex}{ext}"
    dest = upload_dir / filename

    try:
        data = file.file.read()
        dest.write_bytes(data)
    finally:
        try:
            file.file.close()
        except Exception:
            pass

    nanny = db.query(models.Nanny).filter(models.Nanny.user_id == user.id).first()
    if not nanny:
        raise HTTPException(status_code=404, detail="Nanny not found")
    profile = db.query(models.NannyProfile).filter(models.NannyProfile.nanny_id == nanny.id).first()
    if not profile:
        profile = models.NannyProfile(nanny_id=nanny.id)
        db.add(profile)
        db.commit()
        db.refresh(profile)

    before = {"sa_id_document_url": getattr(profile, "sa_id_document_url", None)}
    profile.sa_id_document_url = f"/static/uploads/nannies/{filename}"
    db.add(profile)
    db.commit()
    db.refresh(profile)

    after = {"sa_id_document_url": getattr(profile, "sa_id_document_url", None)}
    log_audit(
        db,
        actor_user=user,
        target_user_id=user.id,
        entity="nanny_profiles",
        entity_id=profile.id,
        action="update",
        before_obj=before,
        after_obj=after,
        changed_fields=None,
        request=request,
    )

    return {"url": profile.sa_id_document_url}


@router.post("/nannies/me/passport-document")
def upload_nanny_passport_document(
    request: Request,
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _require_user(authorization, db)
    if user.role != "nanny":
        raise HTTPException(status_code=403, detail="Forbidden")

    allowed = {
        "application/pdf": ".pdf",
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }
    ext = allowed.get(file.content_type or "")
    if not ext:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    upload_dir = Path(__file__).resolve().parents[1] / "static" / "uploads" / "nannies"
    upload_dir.mkdir(parents=True, exist_ok=True)

    filename = f"passport_{user.id}_{uuid.uuid4().hex}{ext}"
    dest = upload_dir / filename

    try:
        data = file.file.read()
        dest.write_bytes(data)
    finally:
        try:
            file.file.close()
        except Exception:
            pass

    nanny = db.query(models.Nanny).filter(models.Nanny.user_id == user.id).first()
    if not nanny:
        raise HTTPException(status_code=404, detail="Nanny not found")
    profile = db.query(models.NannyProfile).filter(models.NannyProfile.nanny_id == nanny.id).first()
    if not profile:
        profile = models.NannyProfile(nanny_id=nanny.id)
        db.add(profile)
        db.commit()
        db.refresh(profile)

    before = {"passport_document_url": getattr(profile, "passport_document_url", None)}
    profile.passport_document_url = f"/static/uploads/nannies/{filename}"
    db.add(profile)
    db.commit()
    db.refresh(profile)

    after = {"passport_document_url": getattr(profile, "passport_document_url", None)}
    log_audit(
        db,
        actor_user=user,
        target_user_id=user.id,
        entity="nanny_profiles",
        entity_id=profile.id,
        action="update",
        before_obj=before,
        after_obj=after,
        changed_fields=None,
        request=request,
    )

    return {"url": profile.passport_document_url}


@router.post("/nannies/me/work-permit-document")
def upload_nanny_work_permit_document(
    request: Request,
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _require_user(authorization, db)
    if user.role != "nanny":
        raise HTTPException(status_code=403, detail="Forbidden")

    allowed = {
        "application/pdf": ".pdf",
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }
    ext = allowed.get(file.content_type or "")
    if not ext:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    upload_dir = Path(__file__).resolve().parents[1] / "static" / "uploads" / "nannies"
    upload_dir.mkdir(parents=True, exist_ok=True)

    filename = f"permit_{user.id}_{uuid.uuid4().hex}{ext}"
    dest = upload_dir / filename

    try:
        data = file.file.read()
        dest.write_bytes(data)
    finally:
        try:
            file.file.close()
        except Exception:
            pass

    nanny = db.query(models.Nanny).filter(models.Nanny.user_id == user.id).first()
    if not nanny:
        raise HTTPException(status_code=404, detail="Nanny not found")
    profile = db.query(models.NannyProfile).filter(models.NannyProfile.nanny_id == nanny.id).first()
    if not profile:
        profile = models.NannyProfile(nanny_id=nanny.id)
        db.add(profile)
        db.commit()
        db.refresh(profile)

    before = {"work_permit_document_url": getattr(profile, "work_permit_document_url", None)}
    profile.work_permit_document_url = f"/static/uploads/nannies/{filename}"
    db.add(profile)
    db.commit()
    db.refresh(profile)

    after = {"work_permit_document_url": getattr(profile, "work_permit_document_url", None)}
    log_audit(
        db,
        actor_user=user,
        target_user_id=user.id,
        entity="nanny_profiles",
        entity_id=profile.id,
        action="update",
        before_obj=before,
        after_obj=after,
        changed_fields=None,
        request=request,
    )

    return {"url": profile.work_permit_document_url}


def _upload_nanny_optional_document(
    *,
    user: models.User,
    request: Request,
    db: Session,
    file: UploadFile,
    filename_prefix: str,
    profile_attr: str,
    append_json_list: bool = False,
):
    allowed = {
        "application/pdf": ".pdf",
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }
    ext = allowed.get(file.content_type or "")
    if not ext:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    upload_dir = Path(__file__).resolve().parents[1] / "static" / "uploads" / "nannies"
    upload_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{filename_prefix}_{user.id}_{uuid.uuid4().hex}{ext}"
    dest = upload_dir / filename

    try:
        data = file.file.read()
        dest.write_bytes(data)
    finally:
        try:
            file.file.close()
        except Exception:
            pass

    nanny = db.query(models.Nanny).filter(models.Nanny.user_id == user.id).first()
    if not nanny:
        raise HTTPException(status_code=404, detail="Nanny not found")
    profile = db.query(models.NannyProfile).filter(models.NannyProfile.nanny_id == nanny.id).first()
    if not profile:
        profile = models.NannyProfile(nanny_id=nanny.id)
        db.add(profile)
        db.commit()
        db.refresh(profile)

    url = f"/static/uploads/nannies/{filename}"
    before = {profile_attr: getattr(profile, profile_attr, None)}
    if append_json_list:
        raw = getattr(profile, profile_attr, None)
        items = []
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    items = [str(item).strip() for item in parsed if str(item).strip()]
            except Exception:
                items = []
        items.append(url)
        setattr(profile, profile_attr, json.dumps(items))
    else:
        setattr(profile, profile_attr, url)
    db.add(profile)
    db.commit()
    db.refresh(profile)

    after = {profile_attr: getattr(profile, profile_attr, None)}
    log_audit(
        db,
        actor_user=user,
        target_user_id=user.id,
        entity="nanny_profiles",
        entity_id=profile.id,
        action="update",
        before_obj=before,
        after_obj=after,
        changed_fields=None,
        request=request,
    )
    return {"url": url}


@router.post("/nannies/me/police-clearance-document")
def upload_nanny_police_clearance_document(
    request: Request,
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _require_user(authorization, db)
    if user.role != "nanny":
        raise HTTPException(status_code=403, detail="Forbidden")
    return _upload_nanny_optional_document(
        user=user,
        request=request,
        db=db,
        file=file,
        filename_prefix="police",
        profile_attr="police_clearance_document_url",
    )


@router.post("/nannies/me/drivers-license-document")
def upload_nanny_drivers_license_document(
    request: Request,
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _require_user(authorization, db)
    if user.role != "nanny":
        raise HTTPException(status_code=403, detail="Forbidden")
    return _upload_nanny_optional_document(
        user=user,
        request=request,
        db=db,
        file=file,
        filename_prefix="drivers_license",
        profile_attr="drivers_license_document_url",
    )


@router.post("/nannies/me/certificates")
def upload_nanny_certificate_document(
    request: Request,
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _require_user(authorization, db)
    if user.role != "nanny":
        raise HTTPException(status_code=403, detail="Forbidden")
    return _upload_nanny_optional_document(
        user=user,
        request=request,
        db=db,
        file=file,
        filename_prefix="certificate",
        profile_attr="certificates_json",
        append_json_list=True,
    )


@router.post("/nannies/me/reference-document")
def upload_nanny_reference_document(
    request: Request,
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _require_user(authorization, db)
    if user.role != "nanny":
        raise HTTPException(status_code=403, detail="Forbidden")
    allowed = {
        "application/pdf": ".pdf",
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }
    ext = allowed.get(file.content_type or "")
    if not ext:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    upload_dir = Path(__file__).resolve().parents[1] / "static" / "uploads" / "nannies"
    upload_dir.mkdir(parents=True, exist_ok=True)
    filename = f"reference_{user.id}_{uuid.uuid4().hex}{ext}"
    dest = upload_dir / filename
    try:
        dest.write_bytes(file.file.read())
    finally:
        try:
            file.file.close()
        except Exception:
            pass

    url = f"/static/uploads/nannies/{filename}"
    log_audit(
        db,
        actor_user=user,
        target_user_id=user.id,
        entity="nanny_profiles",
        entity_id=None,
        action="upload_reference_document",
        before_obj={},
        after_obj={"reference_letter_url": url},
        changed_fields=None,
        request=request,
    )
    return {"url": url}


@router.get("/nannies/me/profile", response_model=NannyMeProfileResponse)
def get_nanny_me_profile(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _require_user(authorization, db)
    if user.role != "nanny":
        raise HTTPException(status_code=403, detail="Forbidden")

    nanny = db.query(models.Nanny).filter(models.Nanny.user_id == user.id).first()
    if not nanny:
        raise HTTPException(status_code=404, detail="Nanny not found")

    profile = db.query(models.NannyProfile).filter(models.NannyProfile.nanny_id == nanny.id).first()
    if not profile:
        profile = models.NannyProfile(nanny_id=nanny.id)
        db.add(profile)
        db.commit()
        db.refresh(profile)

    qualification_ids = [q.id for q in (profile.qualifications or [])]
    tag_ids = [t.id for t in (profile.tags or [])]
    language_ids = [l.id for l in (profile.languages or [])]

    location_hint = None
    if getattr(profile, "suburb", None) and getattr(profile, "city", None):
        location_hint = f"{profile.suburb}, {profile.city}"
    elif getattr(profile, "city", None):
        location_hint = profile.city
    previous_jobs = []
    raw_jobs = getattr(profile, "previous_jobs_json", None)
    if raw_jobs:
        try:
            parsed = json.loads(raw_jobs)
            if isinstance(parsed, list):
                previous_jobs = parsed
        except Exception:
            previous_jobs = []
    certificate_urls = []
    raw_certs = getattr(profile, "certificates_json", None)
    if raw_certs:
        try:
            parsed_certs = json.loads(raw_certs)
            if isinstance(parsed_certs, list):
                certificate_urls = [str(url).strip() for url in parsed_certs if str(url).strip()]
        except Exception:
            certificate_urls = []

    return {
        "nanny_id": nanny.id,
        "user_id": user.id,
        "full_name": user.name,
        "phone": getattr(user, "phone", None),
        "phone_alt": getattr(user, "phone_alt", None),
        "dob": getattr(profile, "date_of_birth", None),
        "bio": getattr(profile, "bio", None),
        "nationality": getattr(profile, "nationality", None),
        "gender": getattr(profile, "gender", None),
        "ethnicity": getattr(profile, "ethnicity", None),
        "passport_number": getattr(profile, "passport_number", None),
        "passport_expiry": getattr(profile, "passport_expiry", None),
        "passport_document_url": getattr(profile, "passport_document_url", None),
        "permit_status": getattr(profile, "permit_status", None),
        "work_permit": getattr(profile, "work_permit", None),
        "work_permit_expiry": getattr(profile, "work_permit_expiry", None),
        "work_permit_document_url": getattr(profile, "work_permit_document_url", None),
        "waiver": getattr(profile, "waiver", None),
        "sa_id_number": getattr(profile, "sa_id_number", None),
        "sa_id_document_url": getattr(profile, "sa_id_document_url", None),
        "has_own_car": getattr(profile, "has_own_car", None),
        "has_drivers_license": getattr(profile, "has_drivers_license", None),
        "job_type": getattr(profile, "job_type", None),
        "current_job_availability": getattr(profile, "current_job_availability", None),
        "police_clearance_status": getattr(profile, "police_clearance_status", None),
        "has_own_kids": getattr(profile, "has_own_kids", None),
        "own_kids_details": getattr(profile, "own_kids_details", None),
        "medical_conditions": getattr(profile, "medical_conditions", None),
        "my_nanny_training_status": getattr(profile, "my_nanny_training_status", None),
        "dog_preference": getattr(profile, "dog_preference", None),
        "studying_details": getattr(profile, "studying_details", None),
        "police_clearance_document_url": getattr(profile, "police_clearance_document_url", None),
        "drivers_license_document_url": getattr(profile, "drivers_license_document_url", None),
        "certificate_urls": certificate_urls,
        "previous_jobs": previous_jobs,
        "qualification_ids": qualification_ids,
        "tag_ids": tag_ids,
        "language_ids": language_ids,
        "is_approved": bool(getattr(profile, "is_approved", 0)),
        "approved_at": getattr(profile, "approved_at", None),
        "profile_photo_url": getattr(user, "profile_photo_url", None),
        "formatted_address": getattr(profile, "formatted_address", None),
        "suburb": getattr(profile, "suburb", None),
        "city": getattr(profile, "city", None),
        "location_hint": location_hint,
        "lat": getattr(profile, "lat", None),
        "lng": getattr(profile, "lng", None),
    }


@router.patch("/nannies/me/profile")
def update_nanny_me_profile(
    payload: NannyMeProfileUpdate,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _require_user(authorization, db)
    if user.role != "nanny":
        raise HTTPException(status_code=403, detail="Forbidden")

    nanny = db.query(models.Nanny).filter(models.Nanny.user_id == user.id).first()
    if not nanny:
        raise HTTPException(status_code=404, detail="Nanny not found")

    profile = db.query(models.NannyProfile).filter(models.NannyProfile.nanny_id == nanny.id).first()
    if not profile:
        profile = models.NannyProfile(nanny_id=nanny.id)
        db.add(profile)
        db.commit()
        db.refresh(profile)

    before = _nanny_profile_snapshot(user, profile)
    is_approved = bool(getattr(profile, "is_approved", 0))

    def _norm_text(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        v = value.strip()
        return v or None

    if payload.full_name is not None:
        user.name = payload.full_name.strip() if payload.full_name else ""

    if payload.phone is not None:
        user.phone = payload.phone.strip() if payload.phone else None

    if payload.phone_alt is not None:
        user.phone_alt = payload.phone_alt.strip() if payload.phone_alt else None

    if payload.dob is not None:
        if is_approved and payload.dob != profile.date_of_birth:
            raise HTTPException(status_code=400, detail="Date of birth cannot be changed after approval")
        profile.date_of_birth = payload.dob

    if payload.bio is not None:
        cleaned = redact_contact_info(payload.bio)
        profile.bio = cleaned.strip() if cleaned else None

    if payload.nationality is not None:
        profile.nationality = payload.nationality.strip() if payload.nationality else None

    if payload.gender is not None:
        profile.gender = payload.gender.strip() if payload.gender else None

    if payload.ethnicity is not None:
        profile.ethnicity = payload.ethnicity.strip() if payload.ethnicity else None

    if payload.passport_number is not None:
        new_passport_number = _norm_text(payload.passport_number)
        current_passport_number = _norm_text(getattr(profile, "passport_number", None))
        if is_approved and new_passport_number != current_passport_number:
            raise HTTPException(status_code=400, detail="Passport number cannot be changed after approval")
        profile.passport_number = new_passport_number

    if payload.passport_expiry is not None:
        profile.passport_expiry = payload.passport_expiry.strip() if payload.passport_expiry else None

    if payload.passport_document_url is not None:
        new_passport_doc = _norm_text(payload.passport_document_url)
        current_passport_doc = _norm_text(getattr(profile, "passport_document_url", None))
        if is_approved and current_passport_doc and not new_passport_doc:
            raise HTTPException(status_code=400, detail="Approved nannies cannot remove uploaded passport documents")
        profile.passport_document_url = new_passport_doc

    if payload.permit_status is not None:
        profile.permit_status = _norm_text(payload.permit_status)

    if payload.work_permit is not None:
        profile.work_permit = bool(payload.work_permit)

    if payload.work_permit_expiry is not None:
        profile.work_permit_expiry = payload.work_permit_expiry.strip() if payload.work_permit_expiry else None

    if payload.work_permit_document_url is not None:
        new_permit_doc = _norm_text(payload.work_permit_document_url)
        current_permit_doc = _norm_text(getattr(profile, "work_permit_document_url", None))
        if is_approved and current_permit_doc and not new_permit_doc:
            raise HTTPException(status_code=400, detail="Approved nannies cannot remove uploaded permit documents")
        profile.work_permit_document_url = new_permit_doc

    if payload.waiver is not None:
        profile.waiver = bool(payload.waiver)
    if payload.sa_id_number is not None:
        new_sa_id = _norm_text(payload.sa_id_number)
        current_sa_id = _norm_text(getattr(profile, "sa_id_number", None))
        if is_approved and new_sa_id != current_sa_id:
            raise HTTPException(status_code=400, detail="South African ID number cannot be changed after approval")
        profile.sa_id_number = new_sa_id
    if payload.sa_id_document_url is not None:
        new_sa_doc = _norm_text(payload.sa_id_document_url)
        current_sa_doc = _norm_text(getattr(profile, "sa_id_document_url", None))
        if is_approved and current_sa_doc and not new_sa_doc:
            raise HTTPException(status_code=400, detail="Approved nannies cannot remove uploaded ID documents")
        profile.sa_id_document_url = new_sa_doc
    if payload.has_own_car is not None:
        profile.has_own_car = bool(payload.has_own_car)
    if payload.has_drivers_license is not None:
        profile.has_drivers_license = bool(payload.has_drivers_license)
    if payload.job_type is not None:
        profile.job_type = _norm_text(payload.job_type)
    if payload.current_job_availability is not None:
        profile.current_job_availability = _norm_text(payload.current_job_availability)
    if payload.police_clearance_status is not None:
        profile.police_clearance_status = _norm_text(payload.police_clearance_status)
    if payload.has_own_kids is not None:
        profile.has_own_kids = bool(payload.has_own_kids)
    if payload.own_kids_details is not None:
        profile.own_kids_details = _norm_text(payload.own_kids_details)
    if payload.medical_conditions is not None:
        profile.medical_conditions = _norm_text(payload.medical_conditions)
    if payload.my_nanny_training_status is not None:
        profile.my_nanny_training_status = _norm_text(payload.my_nanny_training_status)
    if payload.dog_preference is not None:
        profile.dog_preference = _norm_text(payload.dog_preference)
    if payload.studying_details is not None:
        profile.studying_details = _norm_text(payload.studying_details)
    if payload.police_clearance_document_url is not None:
        profile.police_clearance_document_url = _norm_text(payload.police_clearance_document_url)
    if payload.drivers_license_document_url is not None:
        profile.drivers_license_document_url = _norm_text(payload.drivers_license_document_url)
    if payload.certificate_urls is not None:
        cleaned_urls = [_norm_text(url) for url in payload.certificate_urls]
        profile.certificates_json = json.dumps([url for url in cleaned_urls if url])
    if payload.previous_jobs is not None:
        cleaned_jobs = []
        for item in payload.previous_jobs:
            job = item.dict() if hasattr(item, "dict") else dict(item or {})
            cleaned = {
                "role": _norm_text(job.get("role")),
                "employer": _norm_text(job.get("employer")),
                "period": _norm_text(job.get("period")),
                "care_type": _norm_text(job.get("care_type")),
                "kids_age_when_started": _norm_text(job.get("kids_age_when_started")),
                "disability_details": _norm_text(job.get("disability_details")),
                "reference_letter_url": _norm_text(job.get("reference_letter_url")),
                "reference_name": _norm_text(job.get("reference_name")),
                "reference_phone": _norm_text(job.get("reference_phone")),
                "reference_relationship": _norm_text(job.get("reference_relationship")),
            }
            if any(cleaned.values()):
                cleaned_jobs.append(cleaned)
        profile.previous_jobs_json = json.dumps(cleaned_jobs)

    if payload.qualification_ids is not None:
        profile.qualifications = (
            db.query(models.Qualification)
            .filter(models.Qualification.id.in_(payload.qualification_ids))
            .all()
        )

    if payload.tag_ids is not None:
        profile.tags = (
            db.query(models.NannyTag)
            .filter(models.NannyTag.id.in_(payload.tag_ids))
            .all()
        )

    if payload.language_ids is not None:
        profile.languages = (
            db.query(models.Language)
            .filter(models.Language.id.in_(payload.language_ids))
            .all()
        )

    if not getattr(profile, "is_approved", 0):
        profile.application_status = "pending"
        profile.admin_reason = None
        profile.reviewed_at = None
        profile.reviewed_by_user_id = None

    if not profile.nationality:
        raise HTTPException(status_code=400, detail="Nationality is required")
    nat = profile.nationality.strip().lower()
    if not profile.gender:
        raise HTTPException(status_code=400, detail="Gender is required")
    if not profile.ethnicity:
        raise HTTPException(status_code=400, detail="Race is required")
    if not profile.job_type:
        raise HTTPException(status_code=400, detail="Job type is required")
    if not profile.police_clearance_status:
        raise HTTPException(status_code=400, detail="Police clearance status is required")
    if not profile.my_nanny_training_status:
        raise HTTPException(status_code=400, detail="Training status is required")
    qualification_names = {str(getattr(q, "name", "") or "").strip().lower() for q in (profile.qualifications or [])}
    if "studying" in qualification_names and not _norm_text(getattr(profile, "studying_details", None)):
        raise HTTPException(status_code=400, detail="Please tell us what you are studying")
    if profile.has_own_car is True and profile.has_drivers_license is None:
        raise HTTPException(status_code=400, detail="Driver's license status is required")
    if profile.has_own_kids is True and not _norm_text(getattr(profile, "own_kids_details", None)):
        raise HTTPException(status_code=400, detail="Please share how old your children are and where they stay")
    if nat == "south african":
        if not profile.sa_id_number:
            raise HTTPException(status_code=400, detail="South African ID number is required")
        err = _validate_sa_id(profile.sa_id_number, profile.date_of_birth)
        if err:
            raise HTTPException(status_code=400, detail=err)
        needs_sa = not profile.sa_id_number or not profile.sa_id_document_url
        if needs_sa:
            user.is_active = False
        else:
            if user.is_active is False:
                user.is_active = True
    else:
        if not profile.passport_number:
            raise HTTPException(status_code=400, detail="Passport number is required")
        permit_status = _norm_text(getattr(profile, "permit_status", None))
        if permit_status == "permit":
            profile.work_permit = True
            profile.waiver = False
        elif permit_status == "waiver":
            profile.work_permit = False
            profile.waiver = True
        elif permit_status == "receipt":
            profile.work_permit = False
            profile.waiver = False
        else:
            raise HTTPException(
                status_code=400,
                detail="You need a waiver/receipt or permit for approval. Once you obtain this, please email it to nannies.info@gmail.com",
            )
        needs_docs = False
        if not profile.passport_number or not profile.passport_expiry or not profile.passport_document_url:
            needs_docs = True
        if permit_status == "permit":
            if not profile.work_permit_expiry or not profile.work_permit_document_url:
                needs_docs = True
        if needs_docs:
            user.is_active = False
        else:
            if user.is_active is False:
                user.is_active = True

    db.commit()
    db.refresh(user)
    db.refresh(profile)

    after = _nanny_profile_snapshot(user, profile)
    log_profile_update(
        db,
        actor_user=user,
        target_user_id=user.id,
        entity="nanny_profiles",
        entity_id=profile.id,
        before_obj=before,
        after_obj=after,
        request=request,
        action="update",
    )
    return {"ok": True, "nanny_id": nanny.id}


@router.patch("/nannies/me/location", response_model=NannyLocationResponse)
def set_nanny_me_location(
    payload: schemas.SetLocationRequest,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _require_user(authorization, db)
    if user.role != "nanny":
        raise HTTPException(status_code=403, detail="Forbidden")

    nanny = db.query(models.Nanny).filter(models.Nanny.user_id == user.id).first()
    if not nanny:
        raise HTTPException(status_code=404, detail="Nanny not found")

    profile = db.query(models.NannyProfile).filter(models.NannyProfile.nanny_id == nanny.id).first()
    if not profile:
        profile = models.NannyProfile(nanny_id=nanny.id)
        db.add(profile)
        db.commit()
        db.refresh(profile)

    before = _nanny_location_snapshot(profile)

    profile.lat = payload.lat
    profile.lng = payload.lng

    reverse = _extract_reverse_fields(payload.lat, payload.lng)
    if reverse:
        profile.formatted_address = reverse.get("formatted_address")
        profile.suburb = reverse.get("suburb")
        profile.city = reverse.get("city")
        profile.province = reverse.get("province")
        profile.postal_code = reverse.get("postal_code")
        profile.country = reverse.get("country")
        profile.place_id = reverse.get("place_id")
    else:
        if payload.formatted_address is not None:
            profile.formatted_address = payload.formatted_address
        if payload.suburb is not None:
            profile.suburb = payload.suburb
        if payload.city is not None:
            profile.city = payload.city
        if payload.province is not None:
            profile.province = payload.province
        if payload.postal_code is not None:
            profile.postal_code = payload.postal_code
        if payload.country is not None:
            profile.country = payload.country
        if payload.place_id is not None:
            profile.place_id = payload.place_id

    db.commit()
    db.refresh(profile)

    after = _nanny_location_snapshot(profile)
    log_profile_update(
        db,
        actor_user=user,
        target_user_id=user.id,
        entity="nanny_profiles",
        entity_id=profile.id,
        before_obj=before,
        after_obj=after,
        request=request,
        action="update",
    )
    return {"nanny_id": profile.nanny_id, "lat": profile.lat, "lng": profile.lng}


@router.get("/nannies/me/availability")
def get_nanny_me_availability(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    _, nanny, _ = _require_nanny_user_not_on_hold(authorization, db)
    rows = (
        db.query(models.NannyAvailability)
        .filter(models.NannyAvailability.nanny_id == nanny.id)
        .order_by(models.NannyAvailability.date.asc(), models.NannyAvailability.start_time.asc())
        .all()
    )
    out = []
    for r in rows:
        out.append({
            "id": r.id,
            "start_dt": r.start_dt,
            "end_dt": r.end_dt,
            "type": getattr(r, "type", None) or ("available" if getattr(r, "is_available", True) else "blocked"),
            "notes": r.notes,
        })
    return {"results": out}


@router.post("/nannies/me/availability")
def create_nanny_me_availability(
    payload: schemas.NannyAvailabilityCreateRequest,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    _, nanny, _ = _require_nanny_user_not_on_hold(authorization, db)
    try:
        start_dt = _parse_iso_dt(payload.start_dt)
        end_dt = _parse_iso_dt(payload.end_dt)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid start_dt or end_dt")
    if end_dt <= start_dt:
        raise HTTPException(status_code=400, detail="start_dt must be before end_dt")
    if payload.type not in ("available", "blocked"):
        raise HTTPException(status_code=400, detail="Invalid type")

    row = models.NannyAvailability(
        nanny_id=nanny.id,
        date=start_dt.date(),
        start_time=start_dt.time(),
        end_time=_availability_legacy_end_time(start_dt, end_dt),
        is_available=True if payload.type == "available" else False,
        created_by="nanny",
        type=payload.type,
        start_dt=_to_iso_z(start_dt),
        end_dt=_to_iso_z(end_dt),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id}


@router.post("/nannies/me/availability/bulk")
def create_nanny_me_availability_bulk(
    payload: schemas.NannyAvailabilityBulkRequest,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    _, nanny, _ = _require_nanny_user_not_on_hold(authorization, db)
    if payload.type not in ("available", "blocked"):
        raise HTTPException(status_code=400, detail="Invalid type")

    def parse_date(s):
        return datetime.fromisoformat(s).date()

    try:
        start_date = parse_date(payload.start_date)
        end_date = parse_date(payload.end_date)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid start_date or end_date")
    if end_date < start_date:
        raise HTTPException(status_code=400, detail="end_date must be after start_date")

    start_time = payload.start_time or "00:00"
    end_time = payload.end_time or "23:59"

    try:
        sample_start_dt, sample_end_dt = _build_availability_range(start_date, start_time, end_time)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid start_time or end_time")

    slot_start_time = sample_start_dt.time()
    slot_end_time = _availability_legacy_end_time(sample_start_dt, sample_end_dt)
    expected_windows = {}
    day = start_date
    while day <= end_date:
        expected_windows[day] = _build_availability_range(day, start_time, end_time)
        day = day + timedelta(days=1)
    existing_dates = _existing_availability_dates(
        db, nanny.id, start_date, end_date, expected_windows, payload.type
    )

    created = 0
    skipped = 0
    day = start_date
    while day <= end_date:
        if day in existing_dates:
            skipped += 1
            day = day + timedelta(days=1)
            continue
        start_dt, end_dt = expected_windows[day]
        row = models.NannyAvailability(
            nanny_id=nanny.id,
            date=start_dt.date(),
            start_time=slot_start_time,
            end_time=slot_end_time,
            is_available=True if payload.type == "available" else False,
            created_by="nanny",
            type=payload.type,
            start_dt=_to_iso_z(start_dt),
            end_dt=_to_iso_z(end_dt),
        )
        db.add(row)
        created += 1
        day = day + timedelta(days=1)
    db.commit()
    return {"created": created, "skipped": skipped}


@router.post("/nannies/me/availability/weekly")
def create_nanny_me_availability_weekly(
    payload: schemas.NannyAvailabilityWeeklyRequest,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    _, nanny, _ = _require_nanny_user_not_on_hold(authorization, db)
    if payload.type not in ("available", "blocked"):
        raise HTTPException(status_code=400, detail="Invalid type")
    if payload.weeks <= 0 or payload.weeks > 52:
        raise HTTPException(status_code=400, detail="weeks must be 1-52")
    if not payload.weekdays:
        raise HTTPException(status_code=400, detail="Select at least one weekday")

    try:
        start_date = datetime.fromisoformat(payload.start_date).date()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid start_date")

    start_time = payload.start_time or "00:00"
    end_time = payload.end_time or "23:59"

    weekdays = set(int(d) for d in payload.weekdays if 0 <= int(d) <= 6)
    if not weekdays:
        raise HTTPException(status_code=400, detail="Invalid weekdays")

    end_date = start_date + timedelta(days=(payload.weeks * 7) - 1)
    try:
        sample_start_dt, sample_end_dt = _build_availability_range(start_date, start_time, end_time)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid start_time or end_time")

    slot_start_time = sample_start_dt.time()
    slot_end_time = _availability_legacy_end_time(sample_start_dt, sample_end_dt)
    expected_windows: dict[date, tuple[datetime, datetime]] = {}
    day = start_date
    while day <= end_date:
        if day.weekday() in weekdays:
            expected_windows[day] = _build_availability_range(day, start_time, end_time)
        day = day + timedelta(days=1)
    existing_dates = _existing_availability_dates(
        db, nanny.id, start_date, end_date, expected_windows, payload.type
    )

    created = 0
    skipped = 0
    day = start_date
    while day <= end_date:
        if day.weekday() in weekdays:
            if day in existing_dates:
                skipped += 1
            else:
                start_dt, end_dt = expected_windows[day]
                row = models.NannyAvailability(
                    nanny_id=nanny.id,
                    date=start_dt.date(),
                    start_time=slot_start_time,
                    end_time=slot_end_time,
                    is_available=True if payload.type == "available" else False,
                    created_by="nanny",
                    type=payload.type,
                    start_dt=_to_iso_z(start_dt),
                    end_dt=_to_iso_z(end_dt),
                )
                db.add(row)
                created += 1
        day = day + timedelta(days=1)
    db.commit()
    return {"created": created, "skipped": skipped}


@router.delete("/nannies/me/availability/{availability_id}")
def delete_nanny_me_availability(
    availability_id: int,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    _, nanny, _ = _require_nanny_user_not_on_hold(authorization, db)
    row = (
        db.query(models.NannyAvailability)
        .filter(models.NannyAvailability.id == availability_id, models.NannyAvailability.nanny_id == nanny.id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Availability not found")
    db.delete(row)
    db.commit()
    return {"ok": True}


@router.delete("/nannies/me/availability")
def clear_nanny_me_availability(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    _, nanny, _ = _require_nanny_user_not_on_hold(authorization, db)

    deleted = (
        db.query(models.NannyAvailability)
        .filter(models.NannyAvailability.nanny_id == nanny.id)
        .delete(synchronize_session=False)
    )
    db.commit()
    return {"ok": True, "deleted": deleted}


@router.patch("/nannies/me/availability/{availability_id}")
def update_nanny_me_availability(
    availability_id: int,
    payload: dict,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    _, nanny, _ = _require_nanny_user_not_on_hold(authorization, db)
    row = (
        db.query(models.NannyAvailability)
        .filter(models.NannyAvailability.id == availability_id, models.NannyAvailability.nanny_id == nanny.id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Availability not found")
    next_start_dt = None
    next_end_dt = None
    if "start_dt" in payload:
        next_start_dt = _parse_iso_dt(payload["start_dt"])
        row.start_dt = _to_iso_z(next_start_dt)
    if "end_dt" in payload:
        next_end_dt = _parse_iso_dt(payload["end_dt"])
        row.end_dt = _to_iso_z(next_end_dt)
    if "type" in payload:
        row.type = payload["type"]
    if next_start_dt or next_end_dt:
        if not next_start_dt:
            next_start_dt = _parse_iso_dt(row.start_dt)
        if not next_end_dt:
            next_end_dt = _parse_iso_dt(row.end_dt)
        if next_end_dt <= next_start_dt:
            raise HTTPException(status_code=400, detail="end_dt must be after start_dt")
        row.date = next_start_dt.date()
        row.start_time = next_start_dt.time()
        row.end_time = _availability_legacy_end_time(next_start_dt, next_end_dt)
    db.commit()
    return {"ok": True}


@router.patch("/nannies/me/inactive")
def set_nanny_inactive(
    payload: dict,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    user, _, _ = _require_nanny_user_not_on_hold(authorization, db)
    inactive = bool(payload.get("inactive"))
    user.is_active = not inactive
    db.commit()
    return {"ok": True, "is_active": bool(user.is_active)}


@router.get("/nannies/me/booking-requests")
def list_nanny_me_booking_requests(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    user, nanny, _ = _require_nanny_user_not_on_hold(authorization, db)
    nanny_profile = db.query(models.NannyProfile).filter(models.NannyProfile.nanny_id == nanny.id).first()
    nanny_lat = getattr(nanny_profile, "lat", None) if nanny_profile else None
    nanny_lng = getattr(nanny_profile, "lng", None) if nanny_profile else None
    parent_user = aliased(models.User)
    location = aliased(models.ParentLocation)
    parent_profile = aliased(models.ParentProfile)
    rows = (
        db.query(models.BookingRequest, parent_user, location, parent_profile)
        .join(parent_user, parent_user.id == models.BookingRequest.parent_user_id)
        .outerjoin(location, location.id == models.BookingRequest.location_id)
        .outerjoin(parent_profile, parent_profile.user_id == models.BookingRequest.parent_user_id)
        .filter(
            models.BookingRequest.nanny_id == nanny.id,
            models.BookingRequest.status.in_(["tbc", "pending_admin", "approved"]),
        )
        .order_by(models.BookingRequest.created_at.desc())
        .all()
    )
    results = []
    for req, parent, loc, prof in rows:
        instructions = None
        access_flags = []
        if not loc:
            loc = (
                db.query(models.ParentLocation)
                .filter(models.ParentLocation.parent_user_id == parent.id)
                .order_by(models.ParentLocation.is_default.desc(), models.ParentLocation.id.desc())
                .first()
            )
        windows = _booking_request_windows(db, req)
        slots = [
            {
                "start_dt": _to_iso_z(w[0]),
                "end_dt": _to_iso_z(w[1]),
                "date": w[0].date().isoformat(),
            }
            for w in windows
        ]
        day_count = len({w[0].date().isoformat() for w in windows}) if windows else 1
        location_lat = (getattr(loc, "lat", None) if loc else None) if (loc and getattr(loc, "lat", None) is not None) else getattr(prof, "lat", None)
        location_lng = (getattr(loc, "lng", None) if loc else None) if (loc and getattr(loc, "lng", None) is not None) else getattr(prof, "lng", None)
        distance_km = None
        if nanny_lat is not None and nanny_lng is not None and location_lat is not None and location_lng is not None:
            try:
                distance_km = round(haversine_km(float(nanny_lat), float(nanny_lng), float(location_lat), float(location_lng)), 1)
            except Exception:
                distance_km = None
        results.append({
            "id": req.id,
            "group_id": req.group_id or req.id,
            "status": req.status,
            "nanny_response_status": getattr(req, "nanny_response_status", None) or "pending",
            "nanny_responded_at": req.nanny_responded_at.isoformat() if getattr(req, "nanny_responded_at", None) else None,
            "nanny_response_note": getattr(req, "nanny_response_note", None),
            "parent_name": parent.name,
            "parent_email": parent.email,
            "parent_phone": (
                (getattr(prof, "phone", None) or getattr(parent, "phone", None))
                if (req.status == "approved" or (getattr(req, "nanny_response_status", None) or "").lower() == "accepted")
                else None
            ),
            "start_dt": req.start_dt or (req.requested_starts_at.isoformat() if req.requested_starts_at else None),
            "end_dt": req.end_dt or (req.requested_ends_at.isoformat() if req.requested_ends_at else None),
            "notes": req.client_notes,
            "location_label": loc.label if loc else None,
            "location_address": (getattr(loc, "formatted_address", None) if loc else None) or getattr(prof, "formatted_address", None),
            "location_lat": location_lat,
            "location_lng": location_lng,
            "distance_km": distance_km,
            "slots": slots,
            "days_required": day_count,
            "created_at": req.created_at.isoformat() if getattr(req, "created_at", None) else None,
        })
    return {"results": results}


@router.get("/nannies/me/bookings")
def list_nanny_me_bookings(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    user, nanny, _ = _require_nanny_user_not_on_hold(authorization, db)
    parent_user = aliased(models.User)
    location = aliased(models.ParentLocation)
    parent_profile = aliased(models.ParentProfile)
    rows = (
        db.query(models.BookingRequest, parent_user, location, parent_profile)
        .join(parent_user, parent_user.id == models.BookingRequest.parent_user_id)
        .outerjoin(location, location.id == models.BookingRequest.location_id)
        .outerjoin(parent_profile, parent_profile.user_id == models.BookingRequest.parent_user_id)
        .filter(
            models.BookingRequest.nanny_id == nanny.id,
            models.BookingRequest.status.in_(["approved", "rejected", "cancelled"]),
        )
        .order_by(models.BookingRequest.created_at.desc())
        .all()
    )
    results = []
    for req, parent, loc, prof in rows:
        if not loc:
            loc = (
                db.query(models.ParentLocation)
                .filter(models.ParentLocation.parent_user_id == parent.id)
                .order_by(models.ParentLocation.is_default.desc(), models.ParentLocation.id.desc())
                .first()
            )
        windows = _booking_request_windows(db, req)
        slots = [
            {
                "start_dt": _to_iso_z(w[0]),
                "end_dt": _to_iso_z(w[1]),
                "date": w[0].date().isoformat(),
            }
            for w in windows
        ]
        day_count = len({w[0].date().isoformat() for w in windows}) if windows else 1
        results.append({
            "id": req.id,
            "group_id": req.group_id or req.id,
            "status": req.status,
            "parent_name": parent.name,
            "parent_email": parent.email,
            "start_dt": req.start_dt or (req.requested_starts_at.isoformat() if req.requested_starts_at else None),
            "end_dt": req.end_dt or (req.requested_ends_at.isoformat() if req.requested_ends_at else None),
            "notes": req.client_notes,
            "location_label": loc.label if loc else None,
            "location_address": (getattr(loc, "formatted_address", None) if loc else None) or getattr(prof, "formatted_address", None),
            "location_lat": (getattr(loc, "lat", None) if loc else None) if (loc and getattr(loc, "lat", None) is not None) else getattr(prof, "lat", None),
            "location_lng": (getattr(loc, "lng", None) if loc else None) if (loc and getattr(loc, "lng", None) is not None) else getattr(prof, "lng", None),
            "slots": slots,
            "days_required": day_count,
            "created_at": req.created_at.isoformat() if getattr(req, "created_at", None) else None,
        })
    return {"results": results}


def _ensure_booking_geo(booking: models.Booking) -> tuple:
    if booking.lat is None or booking.lng is None:
        raise HTTPException(status_code=400, detail="Booking location is missing")
    return float(booking.lat), float(booking.lng)


def _distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    return float(haversine_km(lat1, lng1, lat2, lng2) * 1000.0)


def _nanny_owned_booking_or_404(db: Session, booking_id: int, user_id: int) -> models.Booking:
    nanny = db.query(models.Nanny).filter(models.Nanny.user_id == user_id).first()
    if not nanny:
        raise HTTPException(status_code=404, detail="Nanny not found")
    booking = (
        db.query(models.Booking)
        .filter(models.Booking.id == booking_id, models.Booking.nanny_id == nanny.id)
        .first()
    )
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking


@router.get("/nannies/me/duty-bookings")
def list_nanny_me_duty_bookings(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    user, nanny, _ = _require_nanny_user_not_on_hold(authorization, db)

    parent_user = aliased(models.User)
    rows = (
        db.query(models.Booking, parent_user)
        .join(parent_user, parent_user.id == models.Booking.client_user_id)
        .filter(models.Booking.nanny_id == nanny.id)
        .order_by(models.Booking.starts_at.desc())
        .all()
    )
    return {
        "results": [
            {
                "booking_id": b.id,
                "booking_request_id": getattr(b, "booking_request_id", None),
                "parent_name": p.name,
                "parent_email": p.email,
                "start_dt": b.start_dt or (b.starts_at.isoformat() if b.starts_at else None),
                "end_dt": b.end_dt or (b.ends_at.isoformat() if b.ends_at else None),
                "status": b.status,
                "location_label": getattr(b, "location_label", None),
                "location_address": getattr(b, "formatted_address", None),
                "location_lat": getattr(b, "lat", None),
                "location_lng": getattr(b, "lng", None),
                "check_in_at": b.check_in_at.isoformat() if getattr(b, "check_in_at", None) else None,
                "check_in_lat": getattr(b, "check_in_lat", None),
                "check_in_lng": getattr(b, "check_in_lng", None),
                "check_in_distance_m": getattr(b, "check_in_distance_m", None),
                "check_out_at": b.check_out_at.isoformat() if getattr(b, "check_out_at", None) else None,
                "check_out_lat": getattr(b, "check_out_lat", None),
                "check_out_lng": getattr(b, "check_out_lng", None),
                "check_out_distance_m": getattr(b, "check_out_distance_m", None),
            }
            for b, p in rows
        ]
    }


@router.post("/nannies/me/bookings/{booking_id}/check-in")
def nanny_check_in_booking(
    booking_id: int,
    payload: schemas.BookingDutyActionRequest,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    user, _, _ = _require_nanny_user_not_on_hold(authorization, db)
    booking = _nanny_owned_booking_or_404(db, booking_id, user.id)
    target_lat, target_lng = _ensure_booking_geo(booking)
    distance_m = _distance_m(payload.lat, payload.lng, target_lat, target_lng)
    if distance_m > 100:
        raise HTTPException(status_code=409, detail=f"You must be within 100m to check in (current distance: {distance_m:.1f}m)")
    if booking.check_in_at:
        return {
            "ok": True,
            "booking_id": booking.id,
            "check_in_at": booking.check_in_at.isoformat(),
            "check_in_distance_m": booking.check_in_distance_m,
        }

    before_status = booking.status
    booking.check_in_at = datetime.utcnow()
    booking.check_in_lat = float(payload.lat)
    booking.check_in_lng = float(payload.lng)
    booking.check_in_distance_m = float(round(distance_m, 2))
    if booking.status in ("approved", "pending"):
        booking.status = "accepted"
    db.commit()
    db.refresh(booking)
    log_booking_status_change(
        db,
        actor_user=user,
        target_user_id=booking.client_user_id,
        booking_id=booking.id,
        before_status=before_status,
        after_status=booking.status,
        request=request,
    )
    notifications = notify_parent_nanny_checked_in(db, booking, user)
    return {
        "ok": True,
        "booking_id": booking.id,
        "check_in_at": booking.check_in_at.isoformat() if booking.check_in_at else None,
        "check_in_distance_m": booking.check_in_distance_m,
        "notifications": notifications,
    }


@router.post("/nannies/me/bookings/{booking_id}/check-out")
def nanny_check_out_booking(
    booking_id: int,
    payload: schemas.BookingDutyActionRequest,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    user, _, _ = _require_nanny_user_not_on_hold(authorization, db)
    booking = _nanny_owned_booking_or_404(db, booking_id, user.id)
    if not booking.check_in_at:
        raise HTTPException(status_code=400, detail="Check in first before checking out")
    target_lat, target_lng = _ensure_booking_geo(booking)
    distance_m = _distance_m(payload.lat, payload.lng, target_lat, target_lng)
    if distance_m > 100:
        raise HTTPException(status_code=409, detail=f"You must be within 100m to check out (current distance: {distance_m:.1f}m)")
    if booking.check_out_at:
        return {
            "ok": True,
            "booking_id": booking.id,
            "check_out_at": booking.check_out_at.isoformat(),
            "check_out_distance_m": booking.check_out_distance_m,
        }

    before_status = booking.status
    booking.check_out_at = datetime.utcnow()
    booking.check_out_lat = float(payload.lat)
    booking.check_out_lng = float(payload.lng)
    booking.check_out_distance_m = float(round(distance_m, 2))
    booking.status = "completed"
    db.commit()
    db.refresh(booking)
    log_booking_status_change(
        db,
        actor_user=user,
        target_user_id=booking.client_user_id,
        booking_id=booking.id,
        before_status=before_status,
        after_status=booking.status,
        request=request,
    )
    return {
        "ok": True,
        "booking_id": booking.id,
        "check_out_at": booking.check_out_at.isoformat() if booking.check_out_at else None,
        "check_out_distance_m": booking.check_out_distance_m,
    }


@router.post("/nannies/me/bookings/{booking_id}/cancel")
def nanny_cancel_booking(
    booking_id: int,
    payload: schemas.BookingCancellationRequest,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    user, _, _ = _require_nanny_user_not_on_hold(authorization, db)
    reason = (payload.reason or "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="Please provide a reason for cancelling this booking")

    booking = _nanny_owned_booking_or_404(db, booking_id, user.id)
    if booking.status in ("completed", "cancelled", "rejected"):
        raise HTTPException(status_code=400, detail="This booking can no longer be cancelled")

    before_status = booking.status
    booking.status = "cancelled"
    booking.cancelled_at = datetime.utcnow()
    booking.cancellation_reason = reason
    booking.cancellation_actor_role = "nanny"
    booking.cancellation_actor_user_id = user.id

    related_request = None
    if getattr(booking, "booking_request_id", None):
        related_request = db.query(models.BookingRequest).filter(models.BookingRequest.id == booking.booking_request_id).first()
    if related_request:
        related_request.status = "cancelled"
        related_request.admin_reason = reason
        related_request.admin_decided_at = datetime.utcnow()
        related_request.cancelled_at = datetime.utcnow()

    db.commit()
    db.refresh(booking)

    log_booking_status_change(
        db,
        actor_user=user,
        target_user_id=booking.client_user_id,
        booking_id=booking.id,
        before_status=before_status,
        after_status=booking.status,
        request=request,
    )
    log_audit(
        db,
        actor_user=user,
        target_user_id=booking.client_user_id,
        entity="bookings",
        entity_id=booking.id,
        action="cancel",
        before_obj={"status": before_status},
        after_obj={"status": booking.status, "reason": reason},
        changed_fields=["status", "cancellation_reason"],
        request=request,
    )
    notify_admin_nanny_cancelled_booking(booking, user, reason)
    return {"ok": True, "booking_id": booking.id, "status": booking.status, "reason": reason}


@router.post("/nannies/me/booking-requests/{request_id}/accept")
def accept_nanny_booking_request(
    request_id: int,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    user, nanny, _ = _require_nanny_user_not_on_hold(authorization, db)

    req = db.query(models.BookingRequest).filter(models.BookingRequest.id == request_id).first()
    if not req or req.nanny_id != nanny.id:
        raise HTTPException(status_code=404, detail="Booking request not found")
    if req.status not in ("tbc", "pending_admin", "approved"):
        raise HTTPException(status_code=400, detail="Booking request is not available")

    existing_bookings = _find_related_bookings_for_request(db, req) if req.status == "approved" else []
    windows = _booking_request_windows(db, req)
    if not windows:
        raise HTTPException(status_code=400, detail="Invalid booking window")
    if not existing_bookings:
        for start_dt, end_dt in windows:
            if not _is_nanny_available(db, req.nanny_id, start_dt, end_dt):
                raise HTTPException(status_code=409, detail="Requested time is not available")
    start_dt = min(w[0] for w in windows)
    end_dt = max(w[1] for w in windows)

    if not req.group_id:
        req.group_id = req.id
    group_id = req.group_id

    def _resolve_group_acceptance(group_id_value: int):
        accepted_reqs = (
            db.query(models.BookingRequest)
            .filter(
                models.BookingRequest.group_id == group_id_value,
                models.BookingRequest.status == "approved",
            )
            .all()
        )
        if len(accepted_reqs) <= 1:
            return accepted_reqs[0] if accepted_reqs else None

        def rating_key(r):
            avg, cnt = get_rating_12m_for_nanny(db, r.nanny_id)
            return (avg or 0.0, cnt or 0, -r.id)

        winner = max(accepted_reqs, key=rating_key)
        for other_req in accepted_reqs:
            if other_req.id == winner.id:
                continue
            other_req.status = "rejected"
            other_req.admin_reason = "filled_higher_rating"
            other_req.admin_decided_at = datetime.utcnow()
        return winner

    location = None
    if req.location_id:
        location = db.query(models.ParentLocation).filter(models.ParentLocation.id == req.location_id).first()

    before_status = req.status
    before_response = getattr(req, "nanny_response_status", None) or "pending"
    req.status = "approved"
    req.start_dt = req.start_dt or _to_iso_z(start_dt)
    req.end_dt = req.end_dt or _to_iso_z(end_dt)
    req.admin_decided_at = datetime.utcnow()
    req.admin_reason = "accepted_by_nanny"
    req.nanny_response_status = "accepted"
    req.nanny_responded_at = datetime.utcnow()
    req.nanny_response_note = None

    created_bookings = existing_bookings or _find_related_bookings_for_request(db, req)
    if not created_bookings:
        db.flush()
        winner = _resolve_group_acceptance(group_id)
        if winner and winner.id != req.id:
            db.commit()
            raise HTTPException(status_code=409, detail="Another nanny has already been selected for this job")

        created_bookings = []
        for slot_start, slot_end in windows:
            booking = models.Booking(
                booking_request_id=req.id,
                nanny_id=req.nanny_id,
                client_user_id=req.parent_user_id,
                day=slot_start.date(),
                status="approved",
                price_cents=0,
                starts_at=slot_start,
                ends_at=slot_end,
                start_dt=_to_iso_z(slot_start),
                end_dt=_to_iso_z(slot_end),
                lat=location.lat if location else None,
                lng=location.lng if location else None,
                location_mode="saved" if location else None,
                location_label=(location.label or "Location").strip() if location else None,
                formatted_address=getattr(location, "formatted_address", None) if location else None,
            )
            db.add(booking)
            created_bookings.append(booking)

        others = (
            db.query(models.BookingRequest)
            .filter(
                models.BookingRequest.parent_user_id == req.parent_user_id,
                models.BookingRequest.id != req.id,
                models.BookingRequest.status.in_(["tbc", "pending_admin"]),
            )
            .all()
        )
        for other in others:
            try:
                other_start = _parse_iso_dt(other.start_dt or other.requested_starts_at)
                other_end = _parse_iso_dt(other.end_dt or other.requested_ends_at)
            except Exception:
                continue
            if any(_overlaps(slot_start, slot_end, other_start, other_end) for slot_start, slot_end in windows):
                other.status = "rejected"
                other.admin_reason = "filled"
                other.admin_decided_at = datetime.utcnow()

        for slot_start, slot_end in windows:
            block_row = models.NannyAvailability(
                nanny_id=req.nanny_id,
                date=slot_start.date(),
                start_time=slot_start.time(),
                end_time=slot_end.time(),
                is_available=False,
                created_by="nanny",
                type="blocked",
                start_dt=_to_iso_z(slot_start),
                end_dt=_to_iso_z(slot_end),
            )
            db.add(block_row)

    db.commit()
    _sync_confirmed_booking_request_to_google_calendar(db, req)
    log_booking_request_status_change(
        db,
        actor_user=user,
        target_user_id=req.parent_user_id,
        booking_request_id=req.id,
        before_status=before_status,
        after_status=req.status,
        request=request,
    )
    log_audit(
        db,
        actor_user=user,
        target_user_id=req.parent_user_id,
        entity="booking_requests",
        entity_id=req.id,
        action="nanny_response",
        before_obj={"status": before_status, "nanny_response_status": before_response},
        after_obj={"status": req.status, "nanny_response_status": "accepted"},
        changed_fields=["nanny_response_status", "nanny_responded_at"],
        request=request,
    )
    notify_booking_nanny_response(req, user, "accepted")
    primary_booking_id = created_bookings[0].id if created_bookings else None
    return {
        "ok": True,
        "booking_id": primary_booking_id,
        "booking_ids": [b.id for b in created_bookings],
        "booking_request_id": req.id,
    }


@router.post("/nannies/me/booking-requests/{request_id}/respond")
def respond_nanny_booking_request(
    request_id: int,
    payload: schemas.NannyBookingRequestResponse,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    user, nanny, _ = _require_nanny_user_not_on_hold(authorization, db)

    req = db.query(models.BookingRequest).filter(models.BookingRequest.id == request_id).first()
    if not req or req.nanny_id != nanny.id:
        raise HTTPException(status_code=404, detail="Booking request not found")
    if req.status not in ("tbc", "pending_admin", "approved"):
        raise HTTPException(status_code=400, detail="Booking request can no longer be updated")

    response_value = (payload.response or "").strip().lower()
    reason = (payload.reason or "").strip() or None
    if response_value == "accepted":
        raise HTTPException(status_code=400, detail="Use the accept action to confirm this booking")
    if response_value == "declined" and not reason:
        raise HTTPException(status_code=400, detail="Please provide a reason for declining this booking")

    before_status = req.status
    before_response = getattr(req, "nanny_response_status", None) or "pending"
    req.nanny_response_status = response_value
    req.nanny_responded_at = datetime.utcnow()
    req.nanny_response_note = reason

    changed_fields = ["nanny_response_status", "nanny_responded_at", "nanny_response_note"]
    if response_value == "declined":
        req.status = "rejected"
        req.admin_reason = reason or "declined_by_nanny"
        req.admin_decided_at = datetime.utcnow()
        changed_fields.append("status")
        _cancel_related_bookings_for_request(
            db,
            req,
            actor_role="nanny",
            actor_user_id=user.id,
            reason=reason or "Declined by nanny",
        )

    db.commit()
    log_audit(
        db,
        actor_user=user,
        target_user_id=req.parent_user_id,
        entity="booking_requests",
        entity_id=req.id,
        action="nanny_response",
        before_obj={"status": before_status, "nanny_response_status": before_response},
        after_obj={"status": req.status, "nanny_response_status": req.nanny_response_status, "reason": req.nanny_response_note},
        changed_fields=changed_fields,
        request=request,
    )
    notify_booking_nanny_response(req, user, response_value)
    return {"ok": True, "booking_request_id": req.id, "status": req.status, "nanny_response_status": req.nanny_response_status}


# ...existing code...

from datetime import datetime, timedelta

@router.get("/nannies/{nanny_id}/reviews", response_model=NannyReviewsResponse)
def get_nanny_reviews(nanny_id: int, db: Session = Depends(get_db)):
    nanny = db.query(models.Nanny).filter(models.Nanny.id == nanny_id).first()
    if not nanny:
        raise HTTPException(status_code=404, detail="Nanny not found")

    window_start = datetime.utcnow() - timedelta(days=365)
    reviews_query = (
        db.query(models.Review)
        .filter(
            models.Review.nanny_id == nanny_id,
            models.Review.approved == True,
            models.Review.created_at >= window_start
        )
        .order_by(models.Review.created_at.desc())
    )
    reviews = reviews_query.all()

    review_count_12m = len(reviews)
    if review_count_12m == 0:
        average_rating_12m = None
    else:
        average_rating_12m = float(sum(r.stars for r in reviews) / review_count_12m)

    return {
        "nanny_id": nanny_id,
        "average_rating_12m": average_rating_12m,
        "review_count_12m": review_count_12m,
        "reviews": [ReviewOut.model_validate(r, from_attributes=True) for r in reviews],
    }

def compute_age(dob: Optional[date]) -> Optional[int]:
    if dob is None:
        return None
    today = date.today()
    years = today.year - dob.year
    if (today.month, today.day) < (dob.month, dob.day):
        years -= 1
    return years

def _search_nannies_by_area(
    db: Session,
    parent_area_id: Optional[int],
    parent_lat: Optional[float],
    parent_lng: Optional[float],
    max_distance_km: Optional[float],
    min_rating: Optional[float],
    tag_ids: Optional[List[int]],
    qualification_ids: Optional[List[int]],
    language_ids: Optional[List[int]],
    min_age: Optional[int] = None,
    max_age: Optional[int] = None,
):
    q = (
        db.query(models.NannyProfile)
        .join(models.Nanny, models.Nanny.id == models.NannyProfile.nanny_id)
        .join(models.User, models.User.id == models.Nanny.user_id)
        .filter(models.Nanny.approved == True)
        .filter(models.User.is_active == True)
    )

    if parent_area_id is not None:
        q = (
            q.join(models.NannyArea, models.NannyArea.nanny_id == models.NannyProfile.nanny_id)
             .filter(models.NannyArea.area_id == parent_area_id)
        )

    if qualification_ids:
        q = (
            q.join(models.nanny_profile_qualifications)
             .filter(models.nanny_profile_qualifications.c.qualification_id.in_(qualification_ids))
             .group_by(models.NannyProfile.id)
             .having(
                 func.count(distinct(models.nanny_profile_qualifications.c.qualification_id))
                 == len(set(qualification_ids))
             )
        )

    if tag_ids:
        q = (
            q.join(models.nanny_profile_tags)
             .filter(models.nanny_profile_tags.c.tag_id.in_(tag_ids))
             .group_by(models.NannyProfile.id)
             .having(
                 func.count(distinct(models.nanny_profile_tags.c.tag_id))
                 == len(set(tag_ids))
             )
        )

    if language_ids:
        q = (
            q.join(models.nanny_profile_languages)
             .filter(models.nanny_profile_languages.c.language_id.in_(language_ids))
             .group_by(models.NannyProfile.id)
             .having(
                 func.count(distinct(models.nanny_profile_languages.c.language_id))
                 == len(set(language_ids))
             )
        )

    profiles = q.all()

    def simple_list(items):
        return [{"id": x.id, "name": x.name} for x in (items or [])]

    nanny_ids = [p.nanny_id for p in profiles]
    completed_jobs_map = {}
    if nanny_ids:
        completed_rows = (
            db.query(models.BookingRequest.nanny_id, func.count(models.BookingRequest.id))
            .filter(
                models.BookingRequest.nanny_id.in_(nanny_ids),
                models.BookingRequest.status == "approved",
            )
            .group_by(models.BookingRequest.nanny_id)
            .all()
        )
        completed_jobs_map = {int(nanny_id): int(count or 0) for nanny_id, count in completed_rows}

    results = []
    for p in profiles:
        nanny = db.query(models.Nanny).filter(models.Nanny.id == p.nanny_id).first()
        if not nanny:
            continue
        nanny_user = db.query(models.User).filter(models.User.id == nanny.user_id).first()
        if not nanny_user:
            continue

        avg, cnt = get_rating_12m_for_nanny(db, p.nanny_id)
        distance_km = None
        if parent_lat is not None and parent_lng is not None and p.lat is not None and p.lng is not None:
            distance_km = round(haversine_km(parent_lat, parent_lng, p.lat, p.lng), 2)

        if min_age is not None or max_age is not None:
            age = compute_age(getattr(p, "date_of_birth", None))
            if age is None:
                continue
            if min_age is not None and age < min_age:
                continue
            if max_age is not None and age > max_age:
                continue

        if min_rating is not None:
            if avg is None or avg < min_rating:
                continue

        if max_distance_km is not None:
            if distance_km is None or distance_km > max_distance_km:
                continue

        location_hint = None
        if getattr(p, "suburb", None) and getattr(p, "city", None):
            location_hint = f"{p.suburb}, {p.city}"
        elif getattr(p, "city", None):
            location_hint = p.city
        qualifications = simple_list(getattr(p, "qualifications", None))
        tags = simple_list(getattr(p, "tags", None))
        previous_jobs = _normalize_previous_jobs(getattr(p, "previous_jobs_json", None))
        public_jobs = [
            {
                "role": job.get("role"),
                "employer": job.get("employer"),
                "period": job.get("period"),
                "care_type": job.get("care_type"),
                "kids_age_when_started": job.get("kids_age_when_started"),
                "disability_details": job.get("disability_details"),
            }
            for job in previous_jobs
        ]
        age = compute_age(getattr(p, "date_of_birth", None))

        results.append(
            {
                "nanny_id": p.nanny_id,
                "approved": nanny.approved,
                "user_id": nanny_user.id,
                "name": _public_nanny_name(nanny_user.name),
                "nickname": getattr(nanny_user, "nickname", None),
                "last_initial": getattr(nanny_user, "last_initial", None),
                "profile_photo_url": getattr(nanny_user, "profile_photo_url", None),
                "profile_summary": _build_nanny_profile_summary(
                    age=age,
                    nationality=getattr(p, "nationality", None),
                    qualifications=qualifications,
                    tags=tags,
                    previous_jobs=previous_jobs,
                    bio=None,
                ),
                "bio": None,
                "date_of_birth": getattr(p, "date_of_birth", None),
                "age": age,
                "nationality": getattr(p, "nationality", None),
                "ethnicity": getattr(p, "ethnicity", None),
                "qualifications": qualifications,
                "tags": tags,
                "languages": simple_list(getattr(p, "languages", None)),
                "job_type": getattr(p, "job_type", None),
                "has_drivers_license": getattr(p, "has_drivers_license", None),
                "has_own_car": getattr(p, "has_own_car", None),
                "dog_preference": getattr(p, "dog_preference", None),
                "average_rating_12m": avg,
                "review_count_12m": cnt or 0,
                "distance_km": distance_km,
                "location_hint": location_hint,
                "completed_jobs_count": completed_jobs_map.get(int(p.nanny_id), 0),
                "has_identity_document": False,
                "has_passport_document": False,
                "previous_jobs": public_jobs,
            }
        )

    def compare_rating(a: dict, b: dict) -> int:
        ra = a.get("average_rating_12m")
        rb = b.get("average_rating_12m")
        rated_a = ra is not None
        rated_b = rb is not None
        if rated_a != rated_b:
            return -1 if rated_a else 1
        if rated_a and rated_b:
            if ra != rb:
                return -1 if ra > rb else 1
            rca = a.get("review_count_12m") or 0
            rcb = b.get("review_count_12m") or 0
            if rca != rcb:
                return -1 if rca > rcb else 1
        return 0

    def compare(a: dict, b: dict) -> int:
        da = a.get("distance_km")
        db = b.get("distance_km")

        if da is None and db is None:
            rated_cmp = compare_rating(a, b)
            if rated_cmp != 0:
                return rated_cmp
            return (a.get("nanny_id", 0) > b.get("nanny_id", 0)) - (a.get("nanny_id", 0) < b.get("nanny_id", 0))
        if da is None:
            return 1
        if db is None:
            return -1

        if abs(da - db) < 1.0:
            rated_cmp = compare_rating(a, b)
            if rated_cmp != 0:
                return rated_cmp

        if da != db:
            return -1 if da < db else 1

        return (a.get("nanny_id", 0) > b.get("nanny_id", 0)) - (a.get("nanny_id", 0) < b.get("nanny_id", 0))

    results.sort(key=cmp_to_key(compare))
    return results

# /nannies/search route must be defined immediately after router = APIRouter()
@router.get("/nannies/search", response_model=SearchNanniesResponse)
def search_nannies(
    parent_user_id: int,
    max_distance_km: Optional[float] = Query(default=None),
    min_rating: Optional[float] = Query(default=None),
    tag_ids: Optional[List[int]] = Query(default=None),
    qualification_ids: Optional[List[int]] = Query(default=None),
    language_ids: Optional[List[int]] = Query(default=None),
    db: Session = Depends(get_db),
):

    parent = (
        db.query(models.ParentProfile)
        .filter(models.ParentProfile.user_id == parent_user_id)
        .first()
    )
    if not parent:
        raise HTTPException(status_code=404, detail="Parent profile not found")

    default_loc = (
        db.query(models.ParentLocation)
        .filter(models.ParentLocation.parent_user_id == parent_user_id, models.ParentLocation.is_default == True)
        .first()
    )
    if not default_loc or default_loc.lat is None or default_loc.lng is None:
        return {
            "results": [],
            "code": "PARENT_LOCATION_REQUIRED",
            "message": "Set your default location first",
        }

    parent_area_id = parent.area_id
    parent_lat = getattr(default_loc, "lat", None)
    parent_lng = getattr(default_loc, "lng", None)

    results = _search_nannies_by_area(
        db=db,
        parent_area_id=parent_area_id,
        parent_lat=parent_lat,
        parent_lng=parent_lng,
        max_distance_km=max_distance_km,
        min_rating=min_rating,
        tag_ids=tag_ids,
        qualification_ids=qualification_ids,
        language_ids=language_ids,
        min_age=None,
        max_age=None,
    )

    return {
        "results": results,
        "code": None,
        "message": None,
        "parent_profile_complete": _is_profile_complete(db, parent_user_id),
    }


@router.post("/nannies/search", response_model=SearchNanniesResponse)
def search_nannies_post(
    payload: schemas.SearchNanniesRequest,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _require_user(authorization, db)
    if user.role != "parent":
        raise HTTPException(status_code=403, detail="Parent access required")

    parent = (
        db.query(models.ParentProfile)
        .filter(models.ParentProfile.user_id == user.id)
        .first()
    )
    if not parent:
        raise HTTPException(status_code=404, detail="Parent profile not found")

    search_lat = payload.lat
    search_lng = payload.lng
    if search_lat is None or search_lng is None:
        default_loc = (
            db.query(models.ParentLocation)
            .filter(models.ParentLocation.parent_user_id == user.id, models.ParentLocation.is_default == True)
            .first()
        )
        if not default_loc or default_loc.lat is None or default_loc.lng is None:
            raise HTTPException(status_code=422, detail="Location required")
        search_lat = default_loc.lat
        search_lng = default_loc.lng

    # Filtering intentionally disabled – show all nannies
    tag_ids = None
    language_ids = None
    min_age = payload.min_age
    max_age = payload.max_age

    applied_filters = {
        "max_distance_km": payload.max_distance_km is not None,
        "min_rating": payload.min_rating is not None,
        "tag_ids": bool(tag_ids),
        "language_ids": bool(language_ids),
        "qualification_ids": bool(payload.qualification_ids),
        "min_age": min_age is not None,
        "max_age": max_age is not None,
    }
    print("/nannies/search filters", {k: v for k, v in applied_filters.items() if v})

    results = _search_nannies_by_area(
        db=db,
        parent_area_id=None,
        parent_lat=search_lat,
        parent_lng=search_lng,
        max_distance_km=payload.max_distance_km,
        min_rating=payload.min_rating,
        tag_ids=tag_ids,
        qualification_ids=payload.qualification_ids,
        language_ids=language_ids,
        min_age=min_age,
        max_age=max_age,
    )

    return {
        "results": results,
        "code": None,
        "message": None,
        "parent_profile_complete": _is_profile_complete(db, user.id),
    }


@router.post("/nannies/search-by-time", response_model=SearchNanniesResponse)
def search_nannies_by_time(
    payload: schemas.NannySearchByTimeRequest,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _require_user(authorization, db)
    if user.role != "parent":
        raise HTTPException(status_code=403, detail="Parent access required")

    windows = _normalize_booking_slots(
        start_dt_value=payload.start_dt,
        end_dt_value=payload.end_dt,
        slot_items=payload.slots,
    )

    search_lat = payload.lat
    search_lng = payload.lng
    if search_lat is None or search_lng is None:
        default_loc = (
            db.query(models.ParentLocation)
            .filter(models.ParentLocation.parent_user_id == user.id, models.ParentLocation.is_default == True)
            .first()
        )
        if default_loc and default_loc.lat is not None and default_loc.lng is not None:
            search_lat = default_loc.lat
            search_lng = default_loc.lng

    results = _search_nannies_by_area(
        db=db,
        parent_area_id=None,
        parent_lat=search_lat,
        parent_lng=search_lng,
        max_distance_km=payload.max_distance_km,
        min_rating=None,
        tag_ids=None,
        qualification_ids=None,
        language_ids=None,
        min_age=None,
        max_age=None,
    )

    available = []
    for n in results:
        if all(_is_nanny_available(db, n.get("nanny_id"), start_dt, end_dt) for start_dt, end_dt in windows):
            available.append(n)

    return {
        "results": available,
        "code": None,
        "message": None,
        "parent_profile_complete": _is_profile_complete(db, user.id),
    }


@router.post("/parents/default-location")
def set_parent_default_location(payload: SetParentDefaultLocationRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter_by(id=payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    existing = db.query(models.ParentProfile).filter_by(user_id=payload.user_id).first()
    if not existing:
        existing = models.ParentProfile(user_id=payload.user_id)
        db.add(existing)
    existing.lat = payload.lat
    existing.lng = payload.lng
    existing.location_confirmed_at = datetime.utcnow().isoformat()
    existing.location_confirm_version = payload.confirm_version
    db.commit()
    return {"ok": True}


@router.get("/parents/location-status")
def get_parent_location_status(user_id: int, db: Session = Depends(get_db)):
    loc = (
        db.query(models.ParentLocation)
        .filter(models.ParentLocation.parent_user_id == user_id, models.ParentLocation.is_default == True)
        .first()
    )
    lat = getattr(loc, "lat", None) if loc else None
    lng = getattr(loc, "lng", None) if loc else None
    return {
        "has_default_location": lat is not None and lng is not None,
        "lat": lat,
        "lng": lng,
    }


@router.patch("/parents/{user_id}/location", response_model=schemas.SetLocationResponse)
def set_parent_location(user_id: int, payload: schemas.SetLocationRequest, db: Session = Depends(get_db)):
    parent = db.query(models.ParentProfile).filter(models.ParentProfile.user_id == user_id).first()
    if not parent:
        parent = models.ParentProfile(user_id=user_id)
        db.add(parent)
    parent.lat = payload.lat
    parent.lng = payload.lng
    parent.place_id = payload.place_id
    parent.formatted_address = payload.formatted_address
    parent.street = payload.street
    parent.suburb = payload.suburb
    parent.city = payload.city
    parent.province = payload.province
    parent.postal_code = payload.postal_code
    parent.country = payload.country
    parent.location_label = payload.location_label or payload.label
    db.commit()
    db.refresh(parent)
    return {"user_id": parent.user_id, "lat": parent.lat, "lng": parent.lng}


@router.get("/parents/me/locations", response_model=List[schemas.ParentLocationOut])
def list_parent_locations(authorization: Optional[str] = Header(default=None), db: Session = Depends(get_db)):
    user = _require_user(authorization, db)
    if user.role != "parent":
        raise HTTPException(status_code=403, detail="Forbidden")
    rows = (
        db.query(models.ParentLocation)
        .filter(models.ParentLocation.parent_user_id == user.id)
        .order_by(models.ParentLocation.is_default.desc(), models.ParentLocation.created_at.desc())
        .all()
    )
    return rows


def _is_profile_complete(db: Session, user_id: int) -> bool:
    prof = db.query(models.ParentProfile).filter(models.ParentProfile.user_id == user_id).first()
    if not prof:
        return False

    phone = (prof.phone or "").strip()
    if not phone or len(phone) < 7:
        return False

    if prof.kids_count is None:
        return False
    try:
        kids_count = int(prof.kids_count)
    except Exception:
        return False

    kids_ages = []
    if prof.kids_ages_json:
        try:
            kids_ages = json.loads(prof.kids_ages_json) or []
        except Exception:
            return False
    if len(kids_ages) != kids_count:
        return False
    for a in kids_ages:
        try:
            ai = int(a)
        except Exception:
            return False
        if ai < 0 or ai > 18:
            return False

    if not prof.desired_tag_ids_json:
        return False
    try:
        tags = json.loads(prof.desired_tag_ids_json) or []
    except Exception:
        return False
    if len(tags) < 1:
        return False

    if prof.home_language_id is None:
        return False
    if not prof.residence_type:
        return False

    any_location = (
        db.query(models.ParentLocation)
        .filter(models.ParentLocation.parent_user_id == user_id)
        .first()
    )
    if not any_location:
        return False

    default_location = (
        db.query(models.ParentLocation)
        .filter(
            models.ParentLocation.parent_user_id == user_id,
            models.ParentLocation.is_default == True,
        )
        .first()
    )
    if not default_location:
        return False

    return True


@router.get("/parents/me/profile-status")
def parent_profile_status(authorization: Optional[str] = Header(default=None), db: Session = Depends(get_db)):
    user = _require_user(authorization, db)
    if user.role != "parent":
        raise HTTPException(status_code=403, detail="Forbidden")
    return {"is_profile_complete": _is_profile_complete(db, user.id)}


@router.get("/parents/me/profile")
def get_parent_profile(authorization: Optional[str] = Header(default=None), db: Session = Depends(get_db)):
    user = _require_user(authorization, db)
    if user.role != "parent":
        raise HTTPException(status_code=403, detail="Forbidden")
    prof = db.query(models.ParentProfile).filter(models.ParentProfile.user_id == user.id).first()
    if not prof:
        return {"exists": False}

    kids_ages = []
    if prof.kids_ages_json:
        try:
            kids_ages = json.loads(prof.kids_ages_json) or []
        except Exception:
            kids_ages = []

    desired_tag_ids = []
    if prof.desired_tag_ids_json:
        try:
            desired_tag_ids = json.loads(prof.desired_tag_ids_json) or []
        except Exception:
            desired_tag_ids = []

    access_flags = []
    if prof.access_flags_json:
        try:
            access_flags = json.loads(prof.access_flags_json) or []
        except Exception:
            access_flags = []

    return {
        "exists": True,
        "full_name": user.name,
        "email": user.email,
        "phone": prof.phone,
        "kids_count": prof.kids_count,
        "kids_ages": kids_ages,
        "desired_tag_ids": desired_tag_ids,
        "home_language_id": prof.home_language_id,
        "residence_type": prof.residence_type,
        "special_notes": prof.special_notes,
        "family_photo_url": prof.family_photo_url,
        "access_flags": access_flags,
        "booking_responsibilities": getattr(prof, "booking_responsibilities", None),
        "booking_adult_present": getattr(prof, "booking_adult_present", None),
        "booking_reason": getattr(prof, "booking_reason", None),
        "booking_children_count": getattr(prof, "booking_children_count", None),
        "booking_meal_option": getattr(prof, "booking_meal_option", None),
        "booking_food_restrictions": getattr(prof, "booking_food_restrictions", None),
        "booking_dogs": getattr(prof, "booking_dogs", None),
        "booking_disclaimer_basic_upkeep": bool(getattr(prof, "booking_disclaimer_basic_upkeep", False)),
        "booking_disclaimer_medicine": bool(getattr(prof, "booking_disclaimer_medicine", False)),
        "booking_disclaimer_extra_hours": bool(getattr(prof, "booking_disclaimer_extra_hours", False)),
        "booking_disclaimer_transport": bool(getattr(prof, "booking_disclaimer_transport", False)),
    }


@router.get("/parents/me/booking-requests")
def list_parent_booking_requests(authorization: Optional[str] = Header(default=None), db: Session = Depends(get_db)):
    user = _require_user(authorization, db)
    if user.role != "parent":
        raise HTTPException(status_code=403, detail="Forbidden")
    def _resolve_group_acceptance(group_id_value: int) -> bool:
        accepted_reqs = (
            db.query(models.BookingRequest)
            .filter(
                models.BookingRequest.group_id == group_id_value,
                models.BookingRequest.status == "approved",
            )
            .all()
        )
        if len(accepted_reqs) <= 1:
            return False

        def rating_key(r):
            avg, cnt = get_rating_12m_for_nanny(db, r.nanny_id)
            return (avg or 0.0, cnt or 0, -r.id)

        winner = max(accepted_reqs, key=rating_key)
        changed = False
        for other_req in accepted_reqs:
            if other_req.id == winner.id:
                continue
            other_req.status = "rejected"
            other_req.admin_reason = "filled_higher_rating"
            other_req.admin_decided_at = datetime.utcnow()
            changed = True
        return changed

    nanny_user = aliased(models.User)
    rows = (
        db.query(models.BookingRequest, nanny_user)
        .join(models.Nanny, models.Nanny.id == models.BookingRequest.nanny_id)
        .join(nanny_user, nanny_user.id == models.Nanny.user_id)
        .filter(models.BookingRequest.parent_user_id == user.id)
        .order_by(models.BookingRequest.created_at.desc())
        .all()
    )
    group_ids = {req.group_id or req.id for req, _ in rows}
    any_changes = False
    for gid in group_ids:
        if _resolve_group_acceptance(gid):
            any_changes = True
    if any_changes:
        db.commit()
    grouped = {}
    for req, nanny_u in rows:
        gid = req.group_id or req.id
        entry = grouped.get(gid)
        status = req.status
        start_dt = req.start_dt or (req.requested_starts_at.isoformat() if req.requested_starts_at else None)
        end_dt = req.end_dt or (req.requested_ends_at.isoformat() if req.requested_ends_at else None)
        if not entry:
            booking_form = _booking_questionnaire_from_notes(req.client_notes)
            related_bookings = _find_related_bookings_for_request(db, req)
            booking_category = "upcoming"
            if related_bookings:
                if any(getattr(b, "check_in_at", None) and not getattr(b, "check_out_at", None) for b in related_bookings):
                    booking_category = "in_progress"
                elif all(
                    getattr(b, "status", None) in ("completed", "cancelled", "rejected")
                    or (getattr(b, "ends_at", None) and getattr(b, "ends_at", None) < datetime.utcnow())
                    for b in related_bookings
                ):
                    booking_category = "past"
            elif status in ("cancelled", "rejected", "completed"):
                booking_category = "past"
            windows = _booking_request_windows(db, req)
            any_accepted = any(
                (candidate.status == "approved" or (getattr(candidate, "nanny_response_status", None) or "").lower() == "accepted")
                for candidate, _ in rows
                if (candidate.group_id or candidate.id) == gid
            )
            any_editable = any(
                candidate.status in ("tbc", "pending_admin")
                for candidate, _ in rows
                if (candidate.group_id or candidate.id) == gid
            )
            can_edit_details = bool(not any_accepted and any_editable)
            grouped[gid] = {
                "job_id": gid,
                "status": status,
                "booking_category": booking_category,
                "start_dt": start_dt,
                "end_dt": end_dt,
                "slots": [
                    {"start_dt": _to_iso_z(slot_start), "end_dt": _to_iso_z(slot_end)}
                    for slot_start, slot_end in windows
                ],
                "sleepover": bool(getattr(req, "sleepover", False)),
                "created_at": req.created_at.isoformat() if getattr(req, "created_at", None) else None,
                "can_edit_details": can_edit_details,
                "can_edit_form": can_edit_details,
                "edit_locked_reason": None if can_edit_details else "Booking details can no longer be edited once a nanny has accepted, or after the job is cancelled.",
                "accepted_nanny_id": None,
                "accepted_nanny_user_id": None,
                "accepted_nanny_name": None,
                "accepted_nanny_phone": None,
                "accepted_nanny_phone_alt": None,
                "requested_nannies": [],
                "booking_form": booking_form,
            }
            entry = grouped[gid]
        entry["requested_nannies"].append({"id": req.nanny_id, "name": nanny_u.name})
        if status == "approved":
            entry["status"] = "approved"
            entry["booking_category"] = entry.get("booking_category") or "upcoming"
            entry["accepted_nanny_id"] = req.nanny_id
            entry["accepted_nanny_user_id"] = nanny_u.id
            entry["accepted_nanny_name"] = nanny_u.name
            if entry.get("booking_category") != "past":
                entry["accepted_nanny_phone"] = getattr(nanny_u, "phone", None)
                entry["accepted_nanny_phone_alt"] = getattr(nanny_u, "phone_alt", None)
        elif entry["status"] != "approved" and status in ("tbc", "pending_admin"):
            entry["status"] = "tbc"
        elif entry["status"] not in ("approved", "tbc", "pending_admin"):
            entry["status"] = status

    results = list(grouped.values())
    results.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return {"results": results}


@router.get("/parents/me/nannies/{nanny_id}/profile")
def get_parent_nanny_profile_preview(
    nanny_id: int,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _require_user(authorization, db)
    if user.role != "parent":
        raise HTTPException(status_code=403, detail="Forbidden")

    results = _search_nannies_by_area(
        db=db,
        parent_area_id=None,
        parent_lat=None,
        parent_lng=None,
        max_distance_km=None,
        min_rating=None,
        tag_ids=None,
        qualification_ids=None,
        language_ids=None,
        min_age=None,
        max_age=None,
    )
    match = next((item for item in results if int(item.get("nanny_id") or 0) == nanny_id), None)
    if not match:
        raise HTTPException(status_code=404, detail="Nanny profile not found")
    return match


@router.patch("/parents/me/booking-requests/{job_id}/cancel")
def cancel_parent_booking_request(
    job_id: int,
    payload: schemas.BookingCancellationRequest,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _require_user(authorization, db)
    if user.role != "parent":
        raise HTTPException(status_code=403, detail="Forbidden")
    reason = (payload.reason or "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="Please provide a reason for cancelling this booking")

    rows = (
        db.query(models.BookingRequest)
        .filter(
            models.BookingRequest.parent_user_id == user.id,
            or_(models.BookingRequest.group_id == job_id, models.BookingRequest.id == job_id),
        )
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Job not found")

    settings = _get_pricing_settings(db)
    cancellation_window_hours = max(15, int(settings.get("cancellation_fee_window_hours") or 15))

    # Fee window applies only after a nanny has accepted
    any_accepted = any(r.status == "approved" for r in rows)
    if any_accepted:
        start_times = []
        for req in rows:
            try:
                start_times.append(_parse_iso_dt(req.start_dt or req.requested_starts_at))
            except Exception:
                continue
        if start_times:
            earliest = min(start_times)
            if (earliest - datetime.utcnow()) < timedelta(hours=cancellation_window_hours):
                raise HTTPException(
                    status_code=400,
                    detail=f"Cancellation within {cancellation_window_hours} hours will incur a fee. Please contact support.",
                )

    for req in rows:
        if req.status == "cancelled":
            continue
        req.status = "cancelled"
        req.admin_reason = reason
        req.admin_decided_at = datetime.utcnow()
        req.cancelled_at = datetime.utcnow()
        _cancel_related_bookings_for_request(
            db,
            req,
            actor_role="parent",
            actor_user_id=user.id,
            reason=reason,
        )

        # If paid and accepted, compute retention/refund
        if req.payment_status == "paid":
            wage = req.wage_cents or 0
            fee = req.booking_fee_cents or 0
            within_fee_window = False
            try:
                start_dt = _parse_iso_dt(req.start_dt or req.requested_starts_at)
                within_fee_window = (start_dt - datetime.utcnow()) < timedelta(hours=cancellation_window_hours)
            except Exception:
                within_fee_window = False
            if within_fee_window:
                company_retained = int(round(fee * 1.0))
                nanny_retained = int(round(wage * 0.40))
            else:
                company_retained = int(round(fee * 0.80))
                nanny_retained = 0
            refund = max(0, (wage + fee) - (company_retained + nanny_retained))
            req.company_retained_cents = company_retained
            req.nanny_retained_cents = nanny_retained
            req.refund_cents = refund
            req.refund_status = "pending_review"

    db.commit()
    log_audit(
        db,
        actor_user=user,
        target_user_id=user.id,
        entity="booking_requests",
        entity_id=job_id,
        action="cancel",
        before_obj={},
        after_obj={"status": "cancelled", "reason": reason},
        changed_fields=None,
        request=request,
    )
    return {"ok": True, "job_id": job_id, "reason": reason}


@router.patch("/parents/me/booking-requests/{job_id}/schedule")
def update_parent_booking_request_schedule(
    job_id: int,
    payload: schemas.ParentBookingRequestScheduleUpdate,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _require_user(authorization, db)
    if user.role != "parent":
        raise HTTPException(status_code=403, detail="Forbidden")

    rows = (
        db.query(models.BookingRequest)
        .filter(
            models.BookingRequest.parent_user_id == user.id,
            or_(models.BookingRequest.group_id == job_id, models.BookingRequest.id == job_id),
        )
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Job not found")
    if any(r.status == "approved" or (getattr(r, "nanny_response_status", None) or "").lower() == "accepted" for r in rows):
        raise HTTPException(status_code=409, detail="Booking details can no longer be edited after a nanny has accepted")
    editable_rows = [r for r in rows if r.status in ("tbc", "pending_admin")]
    if not editable_rows:
        raise HTTPException(status_code=400, detail="This booking can no longer be edited")

    windows = _normalize_booking_slots(
        start_dt_value=payload.start_dt,
        end_dt_value=payload.end_dt,
        slot_items=payload.slots,
    )
    settings = _get_pricing_settings(db)
    questionnaire = _booking_questionnaire_from_notes(editable_rows[0].client_notes)
    pricing = _compute_booking_slots_pricing(
        windows,
        bool(payload.sleepover),
        settings,
        kids_count=_sanitize_booking_kids_count(questionnaire.get("kids_count")),
    )
    start_dt = min(w[0] for w in windows)
    end_dt = max(w[1] for w in windows)

    for req in editable_rows:
        for slot_start, slot_end in windows:
            if not _is_nanny_available(db, req.nanny_id, slot_start, slot_end):
                raise HTTPException(status_code=409, detail="One or more requested nannies are not available for the new time")

    before_obj = {
        "start_dt": editable_rows[0].start_dt,
        "end_dt": editable_rows[0].end_dt,
        "sleepover": editable_rows[0].sleepover,
    }
    for req in editable_rows:
        req.start_dt = _to_iso_z(start_dt)
        req.end_dt = _to_iso_z(end_dt)
        req.requested_starts_at = start_dt
        req.requested_ends_at = end_dt
        req.sleepover = bool(payload.sleepover) if payload.sleepover is not None else None
        req.wage_cents = pricing["wage_cents"]
        req.booking_fee_pct = pricing["booking_fee_pct"]
        req.booking_fee_cents = pricing["booking_fee_cents"]
        req.total_cents = pricing["total_cents"]
        db.query(models.BookingRequestSlot).filter(models.BookingRequestSlot.booking_request_id == req.id).delete()
        db.flush()
        _attach_booking_request_slots(db, req.id, windows)

    db.commit()
    log_audit(
        db,
        actor_user=user,
        target_user_id=user.id,
        entity="booking_requests",
        entity_id=job_id,
        action="update_schedule",
        before_obj=before_obj,
        after_obj={
            "start_dt": _to_iso_z(start_dt),
            "end_dt": _to_iso_z(end_dt),
            "sleepover": bool(payload.sleepover),
            "slots": [{"start_dt": _to_iso_z(s), "end_dt": _to_iso_z(e)} for s, e in windows],
        },
        changed_fields=["start_dt", "end_dt", "sleepover", "slots"],
        request=request,
    )
    return {
        "ok": True,
        "job_id": job_id,
        "start_dt": _to_iso_z(start_dt),
        "end_dt": _to_iso_z(end_dt),
        "sleepover": bool(payload.sleepover),
    }


@router.patch("/parents/me/booking-requests/{job_id}/form")
def update_parent_booking_request_form(
    job_id: int,
    payload: schemas.ParentBookingRequestUpdate,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _require_user(authorization, db)
    if user.role != "parent":
        raise HTTPException(status_code=403, detail="Forbidden")

    rows = (
        db.query(models.BookingRequest)
        .filter(
            models.BookingRequest.parent_user_id == user.id,
            or_(models.BookingRequest.group_id == job_id, models.BookingRequest.id == job_id),
        )
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Job not found")
    if any(r.status == "approved" or (getattr(r, "nanny_response_status", None) or "").lower() == "accepted" for r in rows):
        raise HTTPException(status_code=409, detail="Booking details can no longer be edited after a nanny has accepted")
    editable_rows = [r for r in rows if r.status in ("tbc", "pending_admin")]
    if not editable_rows:
        raise HTTPException(status_code=400, detail="This booking can no longer be edited")

    questionnaire = _sanitize_booking_questionnaire_payload(payload)
    _validate_booking_questionnaire(questionnaire)
    notes = redact_contact_info((payload.notes or "").strip() or "")
    rebuilt_notes = _build_booking_questionnaire_notes(notes or None, questionnaire)

    for req in editable_rows:
        req.client_notes = rebuilt_notes

    db.commit()
    log_audit(
        db,
        actor_user=user,
        target_user_id=user.id,
        entity="booking_requests",
        entity_id=job_id,
        action="update_form",
        before_obj=None,
        after_obj={"client_notes": rebuilt_notes},
        changed_fields=["client_notes"],
        request=request,
    )
    return {"ok": True, "job_id": job_id, "client_notes": rebuilt_notes}


@router.get("/parents/me/favorites")
def list_parent_favorites(authorization: Optional[str] = Header(default=None), db: Session = Depends(get_db)):
    user = _require_user(authorization, db)
    if user.role != "parent":
        raise HTTPException(status_code=403, detail="Forbidden")
    rows = (
        db.query(models.ParentFavorite)
        .filter(models.ParentFavorite.parent_user_id == user.id)
        .all()
    )
    return {"nanny_ids": [r.nanny_id for r in rows]}


@router.get("/parents/me/favorites/details", response_model=SearchNanniesResponse)
def list_parent_favorite_nannies(authorization: Optional[str] = Header(default=None), db: Session = Depends(get_db)):
    user = _require_user(authorization, db)
    if user.role != "parent":
        raise HTTPException(status_code=403, detail="Forbidden")

    favorite_ids = [
        int(row.nanny_id)
        for row in (
            db.query(models.ParentFavorite)
            .filter(models.ParentFavorite.parent_user_id == user.id)
            .all()
        )
    ]

    if not favorite_ids:
        return {
            "results": [],
            "code": None,
            "message": None,
            "parent_profile_complete": _is_profile_complete(db, user.id),
        }

    default_loc = (
        db.query(models.ParentLocation)
        .filter(models.ParentLocation.parent_user_id == user.id, models.ParentLocation.is_default == True)
        .first()
    )
    search_lat = getattr(default_loc, "lat", None) if default_loc else None
    search_lng = getattr(default_loc, "lng", None) if default_loc else None

    results = _search_nannies_by_area(
        db=db,
        parent_area_id=None,
        parent_lat=search_lat,
        parent_lng=search_lng,
        max_distance_km=None,
        min_rating=None,
        tag_ids=None,
        qualification_ids=None,
        language_ids=None,
        min_age=None,
        max_age=None,
    )
    filtered = [item for item in results if int(item.get("nanny_id") or 0) in favorite_ids]

    return {
        "results": filtered,
        "code": None,
        "message": None,
        "parent_profile_complete": _is_profile_complete(db, user.id),
    }


@router.post("/parents/me/favorites/{nanny_id}")
def add_parent_favorite(nanny_id: int, authorization: Optional[str] = Header(default=None), db: Session = Depends(get_db)):
    user = _require_user(authorization, db)
    if user.role != "parent":
        raise HTTPException(status_code=403, detail="Forbidden")
    nanny = db.query(models.Nanny).filter(models.Nanny.id == nanny_id).first()
    if not nanny:
        raise HTTPException(status_code=404, detail="Nanny not found")
    exists = (
        db.query(models.ParentFavorite)
        .filter(models.ParentFavorite.parent_user_id == user.id, models.ParentFavorite.nanny_id == nanny_id)
        .first()
    )
    if not exists:
        db.add(models.ParentFavorite(parent_user_id=user.id, nanny_id=nanny_id))
        db.commit()
    return {"ok": True}


@router.delete("/parents/me/favorites/{nanny_id}")
def remove_parent_favorite(nanny_id: int, authorization: Optional[str] = Header(default=None), db: Session = Depends(get_db)):
    user = _require_user(authorization, db)
    if user.role != "parent":
        raise HTTPException(status_code=403, detail="Forbidden")
    db.query(models.ParentFavorite).filter(
        models.ParentFavorite.parent_user_id == user.id,
        models.ParentFavorite.nanny_id == nanny_id,
    ).delete()
    db.commit()
    return {"ok": True}


@router.post("/parents/me/locations", response_model=schemas.ParentLocationOut)
def create_parent_location(
    payload: schemas.ParentLocationCreateRequest,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _require_user(authorization, db)
    if user.role != "parent":
        raise HTTPException(status_code=403, detail="Forbidden")
    lat_round = round(payload.lat, 5)
    lng_round = round(payload.lng, 5)

    existing = (
        db.query(models.ParentLocation)
        .filter(
            models.ParentLocation.parent_user_id == user.id,
            models.ParentLocation.lat_round == lat_round,
            models.ParentLocation.lng_round == lng_round,
        )
        .first()
    )
    if existing:
        return existing

    existing_count = (
        db.query(models.ParentLocation)
        .filter(models.ParentLocation.parent_user_id == user.id)
        .count()
    )
    is_default = payload.is_default is True or existing_count == 0

    loc = models.ParentLocation(
        parent_user_id=user.id,
        label=payload.label,
        place_id=payload.place_id,
        formatted_address=payload.formatted_address,
        street=payload.street,
        suburb=payload.suburb,
        city=payload.city,
        province=payload.province,
        postal_code=payload.postal_code,
        country=payload.country,
        lat=payload.lat,
        lng=payload.lng,
        lat_round=lat_round,
        lng_round=lng_round,
        is_default=is_default,
    )
    db.add(loc)

    if is_default:
        db.query(models.ParentLocation).filter(
            models.ParentLocation.parent_user_id == user.id
        ).update({models.ParentLocation.is_default: False})
        loc.is_default = True
        parent = db.query(models.ParentProfile).filter(models.ParentProfile.user_id == user.id).first()
        if parent:
            parent.lat = payload.lat
            parent.lng = payload.lng
            parent.place_id = payload.place_id
            parent.formatted_address = payload.formatted_address
            parent.street = payload.street
            parent.suburb = payload.suburb
            parent.city = payload.city
            parent.province = payload.province
            parent.postal_code = payload.postal_code
            parent.country = payload.country
            parent.location_label = payload.label

    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        if "ux_parent_locations_unique_latlng" in str(e):
            raise HTTPException(status_code=409, detail="Location already exists")
        raise
    db.refresh(loc)

    after = _parent_location_snapshot(loc)
    log_audit(
        db,
        actor_user=user,
        target_user_id=user.id,
        entity="parent_locations",
        entity_id=loc.id,
        action="create",
        before_obj={},
        after_obj=after,
        changed_fields=None,
        request=request,
    )
    return loc


@router.delete("/parents/me/locations/{location_id}")
def delete_parent_location(
    location_id: int,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _require_user(authorization, db)
    if user.role != "parent":
        raise HTTPException(status_code=403, detail="Forbidden")

    loc = (
        db.query(models.ParentLocation)
        .filter(models.ParentLocation.id == location_id, models.ParentLocation.parent_user_id == user.id)
        .first()
    )
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")

    before = _parent_location_snapshot(loc)
    was_default = bool(loc.is_default)
    db.delete(loc)
    db.commit()

    if was_default:
        next_loc = (
            db.query(models.ParentLocation)
            .filter(models.ParentLocation.parent_user_id == user.id)
            .order_by(models.ParentLocation.created_at.desc())
            .first()
        )
        if next_loc:
            next_loc.is_default = True
            parent = db.query(models.ParentProfile).filter(models.ParentProfile.user_id == user.id).first()
            if parent:
                parent.lat = next_loc.lat
                parent.lng = next_loc.lng
                parent.place_id = next_loc.place_id
                parent.formatted_address = next_loc.formatted_address
                parent.street = next_loc.street
                parent.suburb = next_loc.suburb
                parent.city = next_loc.city
                parent.province = next_loc.province
                parent.postal_code = next_loc.postal_code
                parent.country = next_loc.country
                parent.location_label = next_loc.label
            db.commit()

    log_audit(
        db,
        actor_user=user,
        target_user_id=user.id,
        entity="parent_locations",
        entity_id=loc.id,
        action="delete",
        before_obj=before,
        after_obj={},
        changed_fields=None,
        request=request,
    )

    return {"ok": True}


@router.patch("/parents/me/locations/{location_id}/default", response_model=schemas.ParentLocationOut)
def set_parent_location_default(
    location_id: int,
    payload: schemas.SetDefaultLocationRequest,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _require_user(authorization, db)
    if user.role != "parent":
        raise HTTPException(status_code=403, detail="Forbidden")

    loc = (
        db.query(models.ParentLocation)
        .filter(models.ParentLocation.id == location_id, models.ParentLocation.parent_user_id == user.id)
        .first()
    )
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")

    before = _parent_location_snapshot(loc)

    if payload.make_default:
        db.query(models.ParentLocation).filter(models.ParentLocation.parent_user_id == user.id).update(
            {models.ParentLocation.is_default: False}
        )
        loc.is_default = True

    parent = db.query(models.ParentProfile).filter(models.ParentProfile.user_id == user.id).first()
    if parent:
        parent.lat = loc.lat
        parent.lng = loc.lng
        parent.place_id = loc.place_id
        parent.formatted_address = loc.formatted_address
        parent.street = loc.street
        parent.suburb = loc.suburb
        parent.city = loc.city
        parent.province = loc.province
        parent.postal_code = loc.postal_code
        parent.country = loc.country
        parent.location_label = loc.label

    db.commit()
    db.refresh(loc)

    after = _parent_location_snapshot(loc)
    log_audit(
        db,
        actor_user=user,
        target_user_id=user.id,
        entity="parent_locations",
        entity_id=loc.id,
        action="update",
        before_obj=before,
        after_obj=after,
        changed_fields=None,
        request=request,
    )
    return loc


@router.patch("/parents/{user_id}/profile-details")
def update_parent_profile_details(
    user_id: int,
    payload: schemas.ParentProfileDetailsRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    prof = db.query(models.ParentProfile).filter(models.ParentProfile.user_id == user_id).first()
    if not prof:
        prof = models.ParentProfile(user_id=user_id)
        db.add(prof)

    before = _parent_profile_snapshot(prof)

    if payload.phone is not None:
        prof.phone = payload.phone

    if payload.kids_count is not None:
        prof.kids_count = payload.kids_count

    if payload.kids_ages is not None:
        prof.kids_ages_json = json.dumps(payload.kids_ages)

    if payload.desired_tag_ids is not None:
        prof.desired_tag_ids_json = json.dumps(payload.desired_tag_ids)

    if payload.home_language_id is not None:
        prof.home_language_id = payload.home_language_id

    if payload.special_notes is not None:
        prof.special_notes = redact_contact_info(payload.special_notes)

    if payload.family_photo_url is not None:
        prof.family_photo_url = payload.family_photo_url

    if payload.residence_type is not None:
        prof.residence_type = payload.residence_type

    if payload.access_flags is not None:
        cleaned_flags = []
        for item in payload.access_flags:
            cleaned_flags.append(redact_contact_info(item))
        prof.access_flags_json = json.dumps(cleaned_flags)

    if payload.booking_responsibilities is not None:
        prof.booking_responsibilities = redact_contact_info(payload.booking_responsibilities)

    if payload.booking_adult_present is not None:
        prof.booking_adult_present = redact_contact_info(payload.booking_adult_present)

    if payload.booking_reason is not None:
        prof.booking_reason = redact_contact_info(payload.booking_reason)

    if payload.booking_children_count is not None:
        prof.booking_children_count = _sanitize_booking_kids_count(payload.booking_children_count)

    if payload.booking_meal_option is not None:
        prof.booking_meal_option = redact_contact_info(payload.booking_meal_option)

    if payload.booking_food_restrictions is not None:
        prof.booking_food_restrictions = redact_contact_info(payload.booking_food_restrictions)

    if payload.booking_dogs is not None:
        prof.booking_dogs = redact_contact_info(payload.booking_dogs)

    if payload.booking_disclaimer_basic_upkeep is not None:
        prof.booking_disclaimer_basic_upkeep = bool(payload.booking_disclaimer_basic_upkeep)

    if payload.booking_disclaimer_medicine is not None:
        prof.booking_disclaimer_medicine = bool(payload.booking_disclaimer_medicine)

    if payload.booking_disclaimer_extra_hours is not None:
        prof.booking_disclaimer_extra_hours = bool(payload.booking_disclaimer_extra_hours)

    if payload.booking_disclaimer_transport is not None:
        prof.booking_disclaimer_transport = bool(payload.booking_disclaimer_transport)

    db.add(prof)
    db.commit()

    db.refresh(prof)
    after = _parent_profile_snapshot(prof)
    log_profile_update(
        db,
        actor_user=None,
        target_user_id=user_id,
        entity="parent_profiles",
        entity_id=prof.id,
        before_obj=before,
        after_obj=after,
        request=request,
        action="update",
    )

    return {"ok": True, "user_id": user_id}


@router.patch("/nannies/{nanny_id}/location", response_model=NannyLocationResponse)
def set_nanny_location(nanny_id: int, payload: schemas.SetLocationRequest, request: Request, db: Session = Depends(get_db)):
    profile = db.query(models.NannyProfile).filter(models.NannyProfile.nanny_id == nanny_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Nanny profile not found")
    before = _nanny_location_snapshot(profile)
    profile.lat = payload.lat
    profile.lng = payload.lng
    reverse = _extract_reverse_fields(payload.lat, payload.lng)
    if reverse:
        profile.formatted_address = reverse.get("formatted_address")
        profile.suburb = reverse.get("suburb")
        profile.city = reverse.get("city")
        profile.province = reverse.get("province")
        profile.postal_code = reverse.get("postal_code")
        profile.country = reverse.get("country")
        profile.place_id = reverse.get("place_id")
    else:
        if payload.formatted_address is not None:
            profile.formatted_address = payload.formatted_address
        if payload.suburb is not None:
            profile.suburb = payload.suburb
        if payload.city is not None:
            profile.city = payload.city
        if payload.province is not None:
            profile.province = payload.province
        if payload.postal_code is not None:
            profile.postal_code = payload.postal_code
        if payload.country is not None:
            profile.country = payload.country
        if payload.place_id is not None:
            profile.place_id = payload.place_id
    db.commit()
    db.refresh(profile)

    after = _nanny_location_snapshot(profile)
    nanny = db.query(models.Nanny).filter(models.Nanny.id == profile.nanny_id).first()
    target_user_id = nanny.user_id if nanny else None
    log_profile_update(
        db,
        actor_user=None,
        target_user_id=target_user_id,
        entity="nanny_profiles",
        entity_id=profile.id,
        before_obj=before,
        after_obj=after,
        request=request,
        action="update",
    )
    return {"nanny_id": profile.nanny_id, "lat": profile.lat, "lng": profile.lng}

@router.post("/parents/area")
def set_parent_area(payload: SetParentAreaRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter_by(id=payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    existing = db.query(models.ParentProfile).filter_by(user_id=payload.user_id).first()
    if existing:
        existing.area_id = payload.area_id
    else:
        db.add(models.ParentProfile(user_id=payload.user_id, area_id=payload.area_id))
    db.commit()
    return {"user_id": payload.user_id, "area_id": payload.area_id}

@router.post("/reviews", response_model=ReviewOut)
def create_review(payload: ReviewCreate, db: Session = Depends(get_db)):
    booking = db.query(models.Booking).filter_by(id=payload.booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking.status != "completed":
        raise HTTPException(status_code=400, detail="Booking is not completed")

    existing = db.query(models.Review).filter_by(booking_id=payload.booking_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="Review already exists for this booking")

    if payload.comment:
        payload.comment = redact_contact_info(payload.comment)
    review = models.Review(
        booking_id=payload.booking_id,
        parent_user_id=booking.client_user_id,
        nanny_id=booking.nanny_id,
        stars=payload.stars,
        comment=payload.comment,
        approved=False,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review

@router.post("/nannies/{nanny_id}/areas")
def set_nanny_areas(nanny_id: int, payload: SetNannyAreasRequest, db: Session = Depends(get_db)):
    nanny = db.query(models.Nanny).filter_by(id=nanny_id).first()
    if not nanny:
        raise HTTPException(status_code=404, detail="Nanny not found")
    db.query(models.NannyArea).filter_by(nanny_id=nanny_id).delete()
    for area_id in payload.area_ids:
        db.add(models.NannyArea(nanny_id=nanny_id, area_id=area_id))
    db.commit()
    return {"nanny_id": nanny_id, "area_ids": payload.area_ids}

@router.post("/nanny-profiles")
def create_nanny_profile(
    nanny_id: int,
    request: Request,
    payload: Optional[CreateNannyProfileRequest] = None,
    db: Session = Depends(get_db),
):
    nanny = db.query(models.Nanny).filter_by(id=nanny_id).first()
    if not nanny:
        raise HTTPException(status_code=404, detail="Nanny not found")
    existing = db.query(models.NannyProfile).filter_by(nanny_id=nanny_id).first()
    if existing:
        return {
            "id": existing.id,
            "nanny_id": existing.nanny_id,
            "bio": existing.bio,
            "date_of_birth": existing.date_of_birth,
            "age": compute_age(existing.date_of_birth),
            "nationality": existing.nationality,
            "ethnicity": existing.ethnicity,
            "qualifications": [{"id": q.id, "name": q.name} for q in existing.qualifications],
            "tags": [{"id": t.id, "name": t.name} for t in existing.tags],
            "languages": [{"id": l.id, "name": l.name} for l in existing.languages],
        }
    if payload is None:
        payload = CreateNannyProfileRequest()
    if payload.bio:
        payload.bio = redact_contact_info(payload.bio)
    profile = models.NannyProfile(
        nanny_id=nanny_id,
        bio=payload.bio.strip() if payload.bio else None,
        date_of_birth=payload.date_of_birth,
        nationality=payload.nationality.strip() if payload.nationality else None,
        ethnicity=payload.ethnicity.strip() if payload.ethnicity else None,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)

    after = {
        "bio": profile.bio,
        "date_of_birth": profile.date_of_birth,
        "nationality": profile.nationality,
        "ethnicity": profile.ethnicity,
        "qualification_ids": [q.id for q in (profile.qualifications or [])],
        "tag_ids": [t.id for t in (profile.tags or [])],
        "language_ids": [l.id for l in (profile.languages or [])],
    }
    target_user_id = nanny.user_id if nanny else None
    log_profile_update(
        db,
        actor_user=None,
        target_user_id=target_user_id,
        entity="nanny_profiles",
        entity_id=profile.id,
        before_obj={},
        after_obj=after,
        request=request,
        action="create",
    )
    return {
        "id": profile.id,
        "nanny_id": profile.nanny_id,
        "bio": profile.bio,
        "date_of_birth": profile.date_of_birth,
        "age": compute_age(profile.date_of_birth),
        "nationality": profile.nationality,
        "ethnicity": profile.ethnicity,
        "qualifications": [],
        "tags": [],
        "languages": [],
    }

@router.put("/nanny-profiles/{nanny_id}")
def update_nanny_profile(nanny_id: int, payload: UpdateNannyProfileRequest, request: Request, db: Session = Depends(get_db)):
    profile = db.query(models.NannyProfile).filter_by(nanny_id=nanny_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Nanny profile not found")
    before = {
        "bio": profile.bio,
        "date_of_birth": profile.date_of_birth,
        "nationality": profile.nationality,
        "ethnicity": profile.ethnicity,
        "qualification_ids": [q.id for q in (profile.qualifications or [])],
        "tag_ids": [t.id for t in (profile.tags or [])],
        "language_ids": [l.id for l in (profile.languages or [])],
    }
    if payload.bio is not None:
        cleaned = redact_contact_info(payload.bio)
        profile.bio = cleaned.strip() if cleaned else None
    if payload.date_of_birth is not None:
        profile.date_of_birth = payload.date_of_birth
    if payload.nationality is not None:
        profile.nationality = payload.nationality.strip() if payload.nationality else None
    if payload.ethnicity is not None:
        profile.ethnicity = payload.ethnicity.strip() if payload.ethnicity else None
    if payload.qualification_ids is not None:
        profile.qualifications = (
            db.query(models.Qualification)
            .filter(models.Qualification.id.in_(payload.qualification_ids))
            .all()
        )
    if payload.tag_ids is not None:
        profile.tags = (
            db.query(models.NannyTag)
            .filter(models.NannyTag.id.in_(payload.tag_ids))
            .all()
        )
    if payload.language_ids is not None:
        profile.languages = (
            db.query(models.Language)
            .filter(models.Language.id.in_(payload.language_ids))
            .all()
        )
    db.commit()
    db.refresh(profile)

    after = {
        "bio": profile.bio,
        "date_of_birth": profile.date_of_birth,
        "nationality": profile.nationality,
        "ethnicity": profile.ethnicity,
        "qualification_ids": [q.id for q in (profile.qualifications or [])],
        "tag_ids": [t.id for t in (profile.tags or [])],
        "language_ids": [l.id for l in (profile.languages or [])],
    }
    nanny = db.query(models.Nanny).filter(models.Nanny.id == nanny_id).first()
    target_user_id = nanny.user_id if nanny else None
    log_profile_update(
        db,
        actor_user=None,
        target_user_id=target_user_id,
        entity="nanny_profiles",
        entity_id=profile.id,
        before_obj=before,
        after_obj=after,
        request=request,
        action="update",
    )
    return {"ok": True, "nanny_id": nanny_id}


@router.post("/bookings", response_model=schemas.BookingOut)
def create_booking(payload: schemas.BookingCreateRequest, request: Request, db: Session = Depends(get_db)):
    attempted = payload.dict() if hasattr(payload, "dict") else {}
    try:
        if not _is_profile_complete(db, payload.parent_user_id):
            raise HTTPException(status_code=403, detail="Complete your profile before booking")
        location = (
            db.query(models.ParentLocation)
            .filter(
                models.ParentLocation.id == payload.location_id,
                models.ParentLocation.parent_user_id == payload.parent_user_id,
            )
            .first()
        )
        if not location:
            raise HTTPException(status_code=400, detail="Location not found")

        lat = location.lat
        lng = location.lng
        location_label = (location.label or "Location").strip()
        formatted_address = location.formatted_address

        booking = models.Booking(
            nanny_id=payload.nanny_id,
            client_user_id=payload.parent_user_id,
            day=payload.starts_at.date(),
            status="pending",
            price_cents=0,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            lat=lat,
            lng=lng,
            location_mode="saved",
            location_label=location_label,
            formatted_address=formatted_address,
        )
        db.add(booking)
        db.commit()
        db.refresh(booking)
        notify_booking_created(
            booking.client_user_id,
            booking.nanny_id,
            booking.id,
            booking.starts_at,
            booking.ends_at,
            booking.location_label,
        )
    except HTTPException as e:
        log_audit(
            db,
            actor_user=None,
            target_user_id=payload.parent_user_id,
            entity="bookings",
            entity_id=None,
            action="create_failed",
            before_obj=None,
            after_obj={"error": e.detail, "payload": attempted},
            changed_fields=None,
            request=request,
        )
        raise

    log_audit(
        db,
        actor_user=None,
        target_user_id=booking.client_user_id,
        entity="bookings",
        entity_id=booking.id,
        action="create",
        before_obj={},
        after_obj={
            "status": booking.status,
            "parent_user_id": booking.client_user_id,
            "nanny_id": booking.nanny_id,
            "starts_at": booking.starts_at,
            "ends_at": booking.ends_at,
            "location_label": booking.location_label,
        },
        changed_fields=None,
        request=request,
    )

    return {
        "booking_id": booking.id,
        "parent_user_id": booking.client_user_id,
        "nanny_id": booking.nanny_id,
        "starts_at": booking.starts_at,
        "ends_at": booking.ends_at,
        "status": booking.status,
        "location_mode": booking.location_mode,
        "location_label": booking.location_label,
        "formatted_address": booking.formatted_address,
        "lat": booking.lat,
        "lng": booking.lng,
    }


_ALLOWED = {
    schemas.BookingStatus.pending: {schemas.BookingStatus.accepted, schemas.BookingStatus.rejected},
    schemas.BookingStatus.accepted: {schemas.BookingStatus.completed, schemas.BookingStatus.cancelled},
    schemas.BookingStatus.rejected: set(),
    schemas.BookingStatus.cancelled: set(),
    schemas.BookingStatus.completed: set(),
}


@router.patch("/bookings/{booking_id}/status")
def update_booking_status(booking_id: int, payload: schemas.BookingStatusUpdateRequest, request: Request, db: Session = Depends(get_db)):
    b = db.query(models.Booking).filter(models.Booking.id == booking_id).first()
    if not b:
        raise HTTPException(status_code=404, detail="Booking not found")

    current = schemas.BookingStatus(b.status)
    target = payload.status

    if current == schemas.BookingStatus.pending and target == schemas.BookingStatus.accepted:
        if b.starts_at is None or b.ends_at is None:
            raise HTTPException(status_code=400, detail="Booking time window is missing")
        overlap = (
            db.query(models.Booking.id)
            .filter(
                models.Booking.nanny_id == b.nanny_id,
                models.Booking.status == schemas.BookingStatus.accepted.value,
                models.Booking.id != b.id,
                models.Booking.starts_at < b.ends_at,
                models.Booking.ends_at > b.starts_at,
            )
            .first()
        )
        if overlap:
            raise HTTPException(
                status_code=409,
                detail="Nanny already has an accepted booking that overlaps this time window",
            )

    if target not in _ALLOWED[current]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid transition: {current.value} -> {target.value}"
        )

    before_status = b.status
    b.status = target.value
    db.commit()
    db.refresh(b)

    log_booking_status_change(
        db,
        actor_user=None,
        target_user_id=b.client_user_id,
        booking_id=b.id,
        before_status=before_status,
        after_status=b.status,
        request=request,
    )

    return {
        "booking_id": b.id,
        "status": b.status
    }


@router.get("/parents/{user_id}/bookings", response_model=schemas.BookingListResponse)
def list_parent_bookings(
    user_id: int,
    status: Optional[schemas.BookingStatus] = None,
    from_: Optional[datetime] = Query(default=None, alias="from"),
    to: Optional[datetime] = None,
    nanny_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    q = db.query(models.Booking).filter(models.Booking.client_user_id == user_id)

    if status is not None:
        q = q.filter(models.Booking.status == status.value)
    if nanny_id is not None:
        q = q.filter(models.Booking.nanny_id == nanny_id)
    if from_ is not None:
        q = q.filter(models.Booking.ends_at >= from_)
    if to is not None:
        q = q.filter(models.Booking.starts_at <= to)

    rows = q.order_by(models.Booking.starts_at.desc()).all()

    return {
        "results": [
            {
                "booking_id": b.id,
                "parent_user_id": b.client_user_id,
                "nanny_id": b.nanny_id,
                "starts_at": b.starts_at,
                "ends_at": b.ends_at,
                "status": b.status,
                "lat": b.lat,
                "lng": b.lng,
                "location_label": getattr(b, "location_label", None),
                "check_in_at": b.check_in_at.isoformat() if getattr(b, "check_in_at", None) else None,
                "check_in_distance_m": getattr(b, "check_in_distance_m", None),
                "check_out_at": b.check_out_at.isoformat() if getattr(b, "check_out_at", None) else None,
                "check_out_distance_m": getattr(b, "check_out_distance_m", None),
            }
            for b in rows
        ]
    }


@router.get("/nannies/{nanny_id}/bookings")
def list_nanny_bookings(
    nanny_id: int,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(models.Booking).filter(models.Booking.nanny_id == nanny_id)

    if status:
        q = q.filter(models.Booking.status == status)

    rows = q.order_by(models.Booking.starts_at.desc()).all()

    return {
        "results": [
            {
                "booking_id": b.id,
                "parent_user_id": b.client_user_id,
                "nanny_id": b.nanny_id,
                "starts_at": b.starts_at.isoformat() if b.starts_at else None,
                "ends_at": b.ends_at.isoformat() if b.ends_at else None,
                "status": b.status,
                "lat": b.lat,
                "lng": b.lng,
                "location_mode": getattr(b, "location_mode", None),
                "location_label": getattr(b, "location_label", None),
                "check_in_at": b.check_in_at.isoformat() if getattr(b, "check_in_at", None) else None,
                "check_in_distance_m": getattr(b, "check_in_distance_m", None),
                "check_out_at": b.check_out_at.isoformat() if getattr(b, "check_out_at", None) else None,
                "check_out_distance_m": getattr(b, "check_out_distance_m", None),
            }
            for b in rows
        ]
    }

@router.post("/bookings/bulk")
def create_bulk_booking_request(payload: BulkBookingRequest, request: Request, db: Session = Depends(get_db)):
    created_slots = []
    errors = []
    next_slot_id = _next_booking_request_slot_id(db)
    req = models.BookingRequest(
        id=_next_booking_request_id(db),
        parent_user_id=payload.parent_user_id,
        nanny_id=payload.nanny_id,
        status="tbc",
        payment_status="pending_payment",
        client_notes=payload.client_notes,
    )
    db.add(req)
    db.flush()
    for i, slot in enumerate(payload.slots):
        if slot.ends_at <= slot.starts_at:
            errors.append({"index": i, "error": "ends_at must be after starts_at"})
            continue
        existing = (
            db.query(models.BookingRequestSlot)
            .join(models.BookingRequest)
            .filter(
                models.BookingRequest.nanny_id == payload.nanny_id,
                models.BookingRequest.status.in_(["tbc", "pending_admin", "approved"]),
                models.BookingRequestSlot.starts_at < slot.ends_at,
                slot.starts_at < models.BookingRequestSlot.ends_at,
            )
            .first()
        )
        if existing:
            errors.append({"index": i, "error": "overlaps an existing booking or hold"})
            continue
        s = models.BookingRequestSlot(
            id=next_slot_id,
            booking_request_id=req.id,
            starts_at=slot.starts_at,
            ends_at=slot.ends_at,
        )
        next_slot_id += 1
        db.add(s)
        db.flush()
        created_slots.append({"id": s.id, "starts_at": s.starts_at, "ends_at": s.ends_at})
    req.status = "approved" if created_slots else "rejected"
    if created_slots:
        req.payment_status = "paid"
        req.requested_starts_at = created_slots[0]["starts_at"]
        req.requested_ends_at = created_slots[-1]["ends_at"]
        try:
            req.start_dt = _to_iso_z(req.requested_starts_at)
            req.end_dt = _to_iso_z(req.requested_ends_at)
        except Exception:
            pass
    else:
        now = datetime.utcnow()
        req.requested_starts_at = now
        req.requested_ends_at = now
    db.commit()

    log_audit(
        db,
        actor_user=None,
        target_user_id=payload.parent_user_id,
        entity="booking_requests",
        entity_id=req.id,
        action="create",
        before_obj={},
        after_obj={
            "status": req.status,
            "payment_status": getattr(req, "payment_status", None),
            "nanny_id": req.nanny_id,
            "requested_starts_at": req.requested_starts_at,
            "requested_ends_at": req.requested_ends_at,
            "errors": errors,
        },
        changed_fields=None,
        request=request,
    )
    return {
        "booking_request_id": req.id,
        "status": req.status,
        "payment_status": getattr(req, "payment_status", None),
        "created_slots": created_slots,
        "errors": errors,
    }


@router.post("/booking-requests")
def create_booking_request(
    payload: BookingRequestCreate,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    attempted = payload.dict() if hasattr(payload, "dict") else {}
    user = None
    try:
        user = _require_user(authorization, db)
        if user.role != "parent":
            raise HTTPException(status_code=403, detail="Forbidden")

        windows = _normalize_booking_slots(
            start_dt_value=payload.start_dt,
            end_dt_value=payload.end_dt,
            slot_items=payload.slots,
        )
        start_dt = windows[0][0]
        end_dt = windows[-1][1]

        nanny = db.query(models.Nanny).filter(models.Nanny.id == payload.nanny_id).first()
        if not nanny:
            raise HTTPException(status_code=404, detail="Nanny not found")
        if not getattr(nanny, "approved", False):
            raise HTTPException(status_code=400, detail="Nanny not approved")
        nanny_user = db.query(models.User).filter(models.User.id == nanny.user_id).first()
        if nanny_user and not bool(getattr(nanny_user, "is_active", True)):
            raise HTTPException(status_code=409, detail="Nanny is inactive")

        if not all(_is_nanny_available(db, nanny.id, slot_start, slot_end) for slot_start, slot_end in windows):
            raise HTTPException(status_code=409, detail="Requested time is not available")

        if payload.notes:
            payload.notes = redact_contact_info(payload.notes)
        questionnaire = _sanitize_booking_questionnaire_payload(payload)
        _validate_booking_questionnaire(questionnaire)
        pricing = _compute_booking_slots_pricing(
            windows,
            bool(payload.sleepover),
            _get_pricing_settings(db),
            questionnaire.get("kids_count", 1),
        )
        req = models.BookingRequest(
            id=_next_booking_request_id(db),
            parent_user_id=user.id,
            nanny_id=payload.nanny_id,
            status="tbc",
            group_id=None,
            start_dt=_to_iso_z(start_dt),
            end_dt=_to_iso_z(end_dt),
            requested_starts_at=start_dt,
            requested_ends_at=end_dt,
            location_id=payload.location_id,
            sleepover=bool(payload.sleepover) if payload.sleepover is not None else None,
            wage_cents=pricing.get("wage_cents"),
            booking_fee_pct=pricing.get("booking_fee_pct"),
            booking_fee_cents=pricing.get("booking_fee_cents"),
            total_cents=pricing.get("total_cents"),
            client_notes=_build_booking_questionnaire_notes((payload.notes or "").strip() or None, questionnaire),
        )
        req.group_id = req.id
        db.add(req)
        db.flush()
        if payload.slots:
            _attach_booking_request_slots(db, req.id, windows)
        db.commit()
        db.refresh(req)
    except HTTPException as e:
        log_audit(
            db,
            actor_user=user,
            target_user_id=user.id if user else None,
            entity="booking_requests",
            entity_id=None,
            action="create_failed",
            before_obj=None,
            after_obj={"error": e.detail, "payload": attempted},
            changed_fields=None,
            request=request,
        )
        raise

    log_audit(
        db,
        actor_user=user,
        target_user_id=user.id,
        entity="booking_requests",
        entity_id=req.id,
        action="create",
        before_obj={},
        after_obj={
            "status": req.status,
            "nanny_id": req.nanny_id,
            "start_dt": req.start_dt,
            "end_dt": req.end_dt,
        },
        changed_fields=None,
        request=request,
    )
    return {"booking_request_id": req.id, "group_id": req.group_id, "status": req.status}


@router.post("/booking-requests/estimate", response_model=schemas.BookingEstimateResponse)
def estimate_booking_request(
    payload: schemas.BookingEstimateRequest,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _require_user(authorization, db)
    if user.role != "parent":
        raise HTTPException(status_code=403, detail="Forbidden")

    windows = _normalize_booking_slots(
        start_dt_value=payload.start_dt,
        end_dt_value=payload.end_dt,
        slot_items=payload.slots,
    )

    selected_count = int(payload.selected_count or 1)
    if selected_count < 1:
        selected_count = 1

    pricing = _compute_booking_slots_pricing(
        windows,
        bool(payload.sleepover),
        _get_pricing_settings(db),
        _sanitize_booking_kids_count(payload.kids_count),
    )
    per_nanny_total = int(pricing.get("total_cents") or 0)
    per_nanny_wage = int(pricing.get("wage_cents") or 0)
    per_nanny_fee = int(pricing.get("booking_fee_cents") or 0)
    booking_fee_pct = float(pricing.get("booking_fee_pct") or 0.0)

    return {
        "currency": "ZAR",
        "per_nanny_total_cents": per_nanny_total,
        "per_nanny_wage_cents": per_nanny_wage,
        "per_nanny_fee_cents": per_nanny_fee,
        "booking_fee_pct": booking_fee_pct,
        "selected_count": selected_count,
        "selected_total_cents": per_nanny_total * selected_count,
    }


@router.post("/booking-requests/bulk")
def create_booking_request_bulk(
    payload: BookingRequestBulkCreate,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _require_user(authorization, db)
    if user.role != "parent":
        raise HTTPException(status_code=403, detail="Forbidden")

    windows = _normalize_booking_slots(
        start_dt_value=payload.start_dt,
        end_dt_value=payload.end_dt,
        slot_items=payload.slots,
    )
    start_dt = windows[0][0]
    end_dt = windows[-1][1]

    nanny_ids = list(dict.fromkeys([int(n) for n in (payload.nanny_ids or []) if n is not None]))
    if not nanny_ids:
        raise HTTPException(status_code=400, detail="No nannies selected")

    created = []
    errors = []
    next_id = _next_booking_request_id(db)
    group_id = next_id
    if payload.location_id:
        loc = db.query(models.ParentLocation).filter(
            models.ParentLocation.id == payload.location_id,
            models.ParentLocation.parent_user_id == user.id,
        ).first()
        if not loc:
            raise HTTPException(status_code=400, detail="Invalid location")

    if payload.notes:
        payload.notes = redact_contact_info(payload.notes)
    questionnaire = _sanitize_booking_questionnaire_payload(payload)
    _validate_booking_questionnaire(questionnaire)

    for nanny_id in nanny_ids:
        nanny = db.query(models.Nanny).filter(models.Nanny.id == nanny_id).first()
        if not nanny:
            errors.append({"nanny_id": nanny_id, "error": "Nanny not found"})
            continue
        if not getattr(nanny, "approved", False):
            errors.append({"nanny_id": nanny_id, "error": "Nanny not approved"})
            continue
        nanny_user = db.query(models.User).filter(models.User.id == nanny.user_id).first()
        if nanny_user and not bool(getattr(nanny_user, "is_active", True)):
            errors.append({"nanny_id": nanny_id, "error": "Nanny is inactive"})
            continue
        if not all(_is_nanny_available(db, nanny.id, slot_start, slot_end) for slot_start, slot_end in windows):
            errors.append({"nanny_id": nanny_id, "error": "Requested time is not available"})
            continue

        pricing = _compute_booking_slots_pricing(
            windows,
            bool(payload.sleepover),
            _get_pricing_settings(db),
            questionnaire.get("kids_count", 1),
        )
        req = models.BookingRequest(
            id=next_id,
            parent_user_id=user.id,
            nanny_id=nanny_id,
            status="tbc",
            group_id=group_id,
            start_dt=_to_iso_z(start_dt),
            end_dt=_to_iso_z(end_dt),
            requested_starts_at=start_dt,
            requested_ends_at=end_dt,
            location_id=payload.location_id,
            sleepover=bool(payload.sleepover) if payload.sleepover is not None else None,
            wage_cents=pricing.get("wage_cents"),
            booking_fee_pct=pricing.get("booking_fee_pct"),
            booking_fee_cents=pricing.get("booking_fee_cents"),
            total_cents=pricing.get("total_cents"),
            client_notes=_build_booking_questionnaire_notes((payload.notes or "").strip() or None, questionnaire),
        )
        next_id += 1
        db.add(req)
        db.flush()
        if payload.slots:
            _attach_booking_request_slots(db, req.id, windows)
        created.append(req.id)
        log_audit(
            db,
            actor_user=user,
            target_user_id=user.id,
            entity="booking_requests",
            entity_id=req.id,
            action="create",
            before_obj={},
            after_obj={
                "status": req.status,
                "nanny_id": req.nanny_id,
                "start_dt": req.start_dt,
                "end_dt": req.end_dt,
            },
            changed_fields=None,
            request=request,
        )

    db.commit()
    return {"ok": True, "group_id": group_id, "created_ids": created, "errors": errors}


@router.get("/admin/booking-requests")
def list_booking_requests(
    status: Optional[str] = Query(default="tbc"),
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    _require_admin_user(authorization, db)

    parent_user = aliased(models.User)
    nanny_user = aliased(models.User)

    q = (
        db.query(models.BookingRequest, models.ParentLocation, parent_user, nanny_user)
        .join(parent_user, parent_user.id == models.BookingRequest.parent_user_id)
        .join(models.Nanny, models.Nanny.id == models.BookingRequest.nanny_id)
        .join(nanny_user, nanny_user.id == models.Nanny.user_id)
        .outerjoin(models.ParentLocation, models.ParentLocation.id == models.BookingRequest.location_id)
    )
    if status:
        q = q.filter(models.BookingRequest.status == status)

    rows = q.order_by(models.BookingRequest.created_at.desc()).all()
    out = []
    for req, loc, parent, nanny in rows:
        out.append({
            "id": req.id,
            "status": req.status,
            "parent_user_id": req.parent_user_id,
            "parent_name": parent.name,
            "parent_email": parent.email,
            "nanny_id": req.nanny_id,
            "nanny_name": nanny.name,
            "start_dt": req.start_dt or (req.requested_starts_at.isoformat() if req.requested_starts_at else None),
            "end_dt": req.end_dt or (req.requested_ends_at.isoformat() if req.requested_ends_at else None),
            "location_label": getattr(loc, "label", None) if loc else None,
            "suburb": getattr(loc, "suburb", None) if loc else None,
            "city": getattr(loc, "city", None) if loc else None,
        })
    return {"results": out}


@router.patch("/admin/booking-requests/{request_id}/approve")
def approve_booking_request(
    request_id: int,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    admin = _require_admin_user(authorization, db)
    req = db.query(models.BookingRequest).filter(models.BookingRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Booking request not found")
    if req.status not in ("pending_admin", "tbc"):
        raise HTTPException(status_code=400, detail="Booking request is not pending")

    windows = _booking_request_windows(db, req)
    if not windows:
        raise HTTPException(status_code=400, detail="Invalid booking window")
    for start_dt, end_dt in windows:
        if not _is_nanny_available(db, req.nanny_id, start_dt, end_dt):
            raise HTTPException(status_code=409, detail="Requested time is not available")
    start_dt = min(w[0] for w in windows)
    end_dt = max(w[1] for w in windows)

    location = None
    if req.location_id:
        location = db.query(models.ParentLocation).filter(models.ParentLocation.id == req.location_id).first()

    before_status = req.status
    created_bookings = []
    for slot_start, slot_end in windows:
        booking = models.Booking(
            booking_request_id=req.id,
            nanny_id=req.nanny_id,
            client_user_id=req.parent_user_id,
            day=slot_start.date(),
            status="approved",
            price_cents=0,
            starts_at=slot_start,
            ends_at=slot_end,
            start_dt=_to_iso_z(slot_start),
            end_dt=_to_iso_z(slot_end),
            lat=location.lat if location else None,
            lng=location.lng if location else None,
            location_mode="saved" if location else None,
            location_label=(location.label or "Location").strip() if location else None,
            formatted_address=getattr(location, "formatted_address", None) if location else None,
        )
        db.add(booking)
        created_bookings.append(booking)

    req.status = "approved"
    req.start_dt = req.start_dt or _to_iso_z(start_dt)
    req.end_dt = req.end_dt or _to_iso_z(end_dt)
    req.admin_user_id = admin.id
    req.admin_decided_at = datetime.utcnow()

    db.commit()
    for slot_start, slot_end in windows:
        block_row = models.NannyAvailability(
            nanny_id=req.nanny_id,
            date=slot_start.date(),
            start_time=slot_start.time(),
            end_time=slot_end.time(),
            is_available=False,
            created_by="admin",
            type="blocked",
            start_dt=_to_iso_z(slot_start),
            end_dt=_to_iso_z(slot_end),
        )
        db.add(block_row)
    db.commit()
    _sync_confirmed_booking_request_to_google_calendar(db, req)
    log_booking_request_status_change(
        db,
        actor_user=admin,
        target_user_id=req.parent_user_id,
        booking_request_id=req.id,
        before_status=before_status,
        after_status=req.status,
        request=request,
    )
    log_audit(
        db,
        actor_user=admin,
        target_user_id=booking.client_user_id,
        entity="bookings",
        entity_id=created_bookings[0].id if created_bookings else None,
        action="create",
        before_obj={},
        after_obj={
            "status": "approved",
            "parent_user_id": req.parent_user_id,
            "nanny_id": req.nanny_id,
            "start_dt": _to_iso_z(start_dt),
            "end_dt": _to_iso_z(end_dt),
            "location_label": (location.label if location else None),
            "booking_count": len(created_bookings),
        },
        changed_fields=None,
        request=request,
    )
    primary_booking_id = created_bookings[0].id if created_bookings else None
    return {
        "ok": True,
        "booking_id": primary_booking_id,
        "booking_ids": [b.id for b in created_bookings],
        "booking_request_id": req.id,
    }


@router.post("/admin/booking-requests/{request_id}/approve")
def approve_booking_request_post(
    request_id: int,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    return approve_booking_request(
        request_id=request_id,
        request=request,
        authorization=authorization,
        db=db,
    )


@router.patch("/admin/booking-requests/{request_id}/reject")
def reject_booking_request(
    request_id: int,
    request: Request,
    payload: Optional[BookingRequestReject] = None,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    admin = _require_admin_user(authorization, db)
    if payload is None:
        payload = BookingRequestReject()
    req = db.query(models.BookingRequest).filter(models.BookingRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Booking request not found")
    if req.status not in ("pending_admin", "tbc"):
        raise HTTPException(status_code=400, detail="Booking request is not pending")
    reason = (payload.reason or "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="Please provide a reason for rejecting this booking request")

    before_status = req.status
    req.status = "rejected"
    req.admin_reason = reason
    req.admin_user_id = admin.id
    req.admin_decided_at = datetime.utcnow()

    booking_id = None
    if payload.assign_nanny_id:
        nanny = db.query(models.Nanny).filter(models.Nanny.id == payload.assign_nanny_id).first()
        if not nanny:
            raise HTTPException(status_code=404, detail="Assigned nanny not found")

        location = None
        if req.location_id:
            location = db.query(models.ParentLocation).filter(models.ParentLocation.id == req.location_id).first()
        if not location:
            raise HTTPException(status_code=400, detail="Location not found")

        booking = models.Booking(
            booking_request_id=req.id,
            nanny_id=payload.assign_nanny_id,
            client_user_id=req.parent_user_id,
            day=req.requested_starts_at.date() if req.requested_starts_at else datetime.utcnow().date(),
            status="pending",
            price_cents=0,
            starts_at=req.requested_starts_at,
            ends_at=req.requested_ends_at,
            lat=location.lat,
            lng=location.lng,
            location_mode="saved",
            location_label=(location.label or "Location").strip() if location else None,
            formatted_address=getattr(location, "formatted_address", None),
        )
        db.add(booking)
        db.flush()
        booking_id = booking.id

    db.commit()
    if booking_id:
        notify_booking_created(req.parent_user_id, payload.assign_nanny_id, booking_id, req.requested_starts_at, req.requested_ends_at, None)
        notify_booking_reassigned(req.parent_user_id, payload.assign_nanny_id, req.id, req.requested_starts_at, req.requested_ends_at)
        booking = db.query(models.Booking).filter(models.Booking.id == booking_id).first()
        if booking:
            log_audit(
                db,
                actor_user=admin,
                target_user_id=booking.client_user_id,
                entity="bookings",
                entity_id=booking.id,
                action="create",
                before_obj={},
                after_obj={
                    "status": booking.status,
                    "parent_user_id": booking.client_user_id,
                    "nanny_id": booking.nanny_id,
                    "starts_at": booking.starts_at,
                    "ends_at": booking.ends_at,
                    "location_label": booking.location_label,
                },
                changed_fields=None,
                request=request,
            )
    log_booking_request_status_change(
        db,
        actor_user=admin,
        target_user_id=req.parent_user_id,
        booking_request_id=req.id,
        before_status=before_status,
        after_status=req.status,
        request=request,
        extra_after={"admin_reason": req.admin_reason},
    )
    return {"ok": True, "booking_request_id": req.id, "booking_id": booking_id}


@router.post("/admin/booking-requests/{request_id}/reject")
def reject_booking_request_post(
    request_id: int,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    return reject_booking_request(
        request_id=request_id,
        payload=None,
        request=request,
        authorization=authorization,
        db=db,
    )


@router.get("/admin/nannies/pending")
def list_pending_nanny_approvals(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    _require_admin_user(authorization, db)

    rows = (
        db.query(models.Nanny, models.User, models.NannyProfile)
        .join(models.User, models.User.id == models.Nanny.user_id)
        .outerjoin(models.NannyProfile, models.NannyProfile.nanny_id == models.Nanny.id)
        .filter(
            (models.NannyProfile.is_approved == 0) | (models.NannyProfile.is_approved == None)
        )
        .filter(
            (models.NannyProfile.application_status == None)
            | (models.NannyProfile.application_status == "pending")
            | (models.NannyProfile.application_status == "hold")
        )
        .all()
    )
    out = []
    for nanny, user, profile in rows:
        out.append({
            "nanny_id": nanny.id,
            "user_id": user.id,
            "name": user.name,
            "email": user.email,
            "profile_photo_url": user.profile_photo_url,
            "suburb": getattr(profile, "suburb", None),
            "city": getattr(profile, "city", None),
            "application_status": getattr(profile, "application_status", None),
            "admin_reason": getattr(profile, "admin_reason", None),
        })
    return {"results": out}


@router.get("/admin/nannies/applications")
def list_nanny_applications(
    status: Optional[str] = Query(default="pending"),
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    _require_admin_user(authorization, db)

    normalized = (status or "pending").strip().lower()
    allowed = {"all", "pending", "hold", "approved", "declined"}
    if normalized not in allowed:
        raise HTTPException(status_code=400, detail="Invalid application status filter")

    q = (
        db.query(models.Nanny, models.User, models.NannyProfile)
        .join(models.User, models.User.id == models.Nanny.user_id)
        .outerjoin(models.NannyProfile, models.NannyProfile.nanny_id == models.Nanny.id)
    )

    if normalized == "pending":
        q = q.filter(
            (models.NannyProfile.application_status == None)
            | (models.NannyProfile.application_status == "pending")
        )
    elif normalized != "all":
        q = q.filter(models.NannyProfile.application_status == normalized)

    rows = q.order_by(models.User.name.asc()).all()
    out = []
    for nanny, user, profile in rows:
        out.append({
            "nanny_id": nanny.id,
            "user_id": user.id,
            "name": user.name,
            "email": user.email,
            "profile_photo_url": user.profile_photo_url,
            "suburb": getattr(profile, "suburb", None),
            "city": getattr(profile, "city", None),
            "application_status": getattr(profile, "application_status", None) or "pending",
            "admin_reason": getattr(profile, "admin_reason", None),
            "approved": bool(getattr(nanny, "approved", False)),
        })
    return {"results": out}


@router.get("/admin/booking-requests/pending")
def list_pending_booking_requests(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    require_admin(authorization, db)

    parent_user = aliased(models.User)
    nanny_user = aliased(models.User)
    rows = (
        db.query(models.BookingRequest, parent_user, nanny_user)
        .join(parent_user, parent_user.id == models.BookingRequest.parent_user_id)
        .join(models.Nanny, models.Nanny.id == models.BookingRequest.nanny_id)
        .join(nanny_user, nanny_user.id == models.Nanny.user_id)
        .filter(models.BookingRequest.status == "tbc")
        .order_by(models.BookingRequest.created_at.desc())
        .all()
    )
    _mark_overdue_booking_requests_notified(db, rows)

    results = []
    for req, parent, nanny in rows:
        is_overdue = bool(getattr(req, "created_at", None) and (datetime.utcnow() - req.created_at) >= timedelta(hours=6))
        results.append({
            "id": req.id,
            "parent_name": parent.name,
            "parent_email": parent.email,
            "nanny_name": nanny.name,
            "start_dt": req.start_dt or (req.requested_starts_at.isoformat() if req.requested_starts_at else None),
            "end_dt": req.end_dt or (req.requested_ends_at.isoformat() if req.requested_ends_at else None),
            "is_overdue": is_overdue,
        })

    return {"results": results}


def _mark_overdue_booking_requests_notified(db: Session, request_rows: List[tuple]) -> None:
    now = datetime.utcnow()
    changed = False
    for req, parent, nanny in request_rows:
        if req.status not in ("tbc", "pending_admin"):
            continue
        created_at = getattr(req, "created_at", None)
        if not created_at or (now - created_at) < timedelta(hours=6):
            continue
        if getattr(req, "unaccepted_admin_notified_at", None):
            continue
        notify_admin_unaccepted_booking_request(req, parent, nanny)
        req.unaccepted_admin_notified_at = now
        changed = True
    if changed:
        db.commit()


@router.get("/admin/booking-requests/{request_id}/detail")
def get_admin_booking_request_detail(
    request_id: int,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    require_admin(authorization, db)

    parent_user = aliased(models.User)
    nanny_user = aliased(models.User)
    profile = aliased(models.ParentProfile)
    loc = aliased(models.ParentLocation)

    row = (
        db.query(models.BookingRequest, parent_user, nanny_user, profile, loc)
        .join(parent_user, parent_user.id == models.BookingRequest.parent_user_id)
        .join(models.Nanny, models.Nanny.id == models.BookingRequest.nanny_id)
        .join(nanny_user, nanny_user.id == models.Nanny.user_id)
        .outerjoin(profile, profile.user_id == models.BookingRequest.parent_user_id)
        .outerjoin(loc, loc.id == models.BookingRequest.location_id)
        .filter(models.BookingRequest.id == request_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Booking request not found")

    req, parent, nanny, parent_profile, location = row
    _mark_overdue_booking_requests_notified(db, [(req, parent, nanny)])
    slots = _booking_request_windows(db, req)
    related_bookings = _find_related_bookings_for_request(db, req)
    questionnaire = _parse_booking_questionnaire_notes(getattr(req, "client_notes", None))
    created_at = getattr(req, "created_at", None)
    is_overdue = bool(created_at and (datetime.utcnow() - created_at) >= timedelta(hours=6) and req.status in ("tbc", "pending_admin"))

    return {
        "request_id": req.id,
        "group_id": req.group_id or req.id,
        "status": req.status,
        "admin_reason": req.admin_reason,
        "payment_status": getattr(req, "payment_status", None),
        "is_overdue": is_overdue,
        "unaccepted_admin_notified_at": req.unaccepted_admin_notified_at.isoformat() if getattr(req, "unaccepted_admin_notified_at", None) else None,
        "created_at": created_at.isoformat() if created_at else None,
        "parent": {
            "user_id": parent.id,
            "name": parent.name,
            "email": parent.email,
            "phone": getattr(parent_profile, "phone", None) if parent_profile else None,
        },
        "nanny": {
            "nanny_id": req.nanny_id,
            "name": nanny.name,
            "email": nanny.email,
        },
        "location": {
            "label": getattr(location, "label", None) if location else None,
            "address": getattr(location, "formatted_address", None) if location else None,
            "suburb": getattr(location, "suburb", None) if location else None,
            "city": getattr(location, "city", None) if location else None,
            "province": getattr(location, "province", None) if location else None,
        },
        "pricing": {
            "wage_cents": getattr(req, "wage_cents", None),
            "booking_fee_cents": getattr(req, "booking_fee_cents", None),
            "total_cents": getattr(req, "total_cents", None),
        },
        "schedule": [
            {
                "start_dt": _to_iso_z(slot_start),
                "end_dt": _to_iso_z(slot_end),
            }
            for slot_start, slot_end in slots
        ] or [
            {
                "start_dt": req.start_dt or (req.requested_starts_at.isoformat() if req.requested_starts_at else None),
                "end_dt": req.end_dt or (req.requested_ends_at.isoformat() if req.requested_ends_at else None),
            }
        ],
        "booking_form": {
            "additional_notes": questionnaire.get("additional_notes"),
            "items": questionnaire.get("items", []),
            "fallback_profile": {
                "booking_responsibilities": getattr(parent_profile, "booking_responsibilities", None) if parent_profile else None,
                "booking_adult_present": getattr(parent_profile, "booking_adult_present", None) if parent_profile else None,
                "booking_reason": getattr(parent_profile, "booking_reason", None) if parent_profile else None,
                "booking_children_count": getattr(parent_profile, "booking_children_count", None) if parent_profile else None,
                "booking_meal_option": getattr(parent_profile, "booking_meal_option", None) if parent_profile else None,
                "booking_food_restrictions": getattr(parent_profile, "booking_food_restrictions", None) if parent_profile else None,
                "booking_dogs": getattr(parent_profile, "booking_dogs", None) if parent_profile else None,
                "special_notes": getattr(parent_profile, "special_notes", None) if parent_profile else None,
            },
        },
        "booking_days": [
            {
                "booking_id": booking.id,
                "status": booking.status,
                "start_dt": booking.start_dt or (booking.starts_at.isoformat() if booking.starts_at else None),
                "end_dt": booking.end_dt or (booking.ends_at.isoformat() if booking.ends_at else None),
                "check_in_at": booking.check_in_at.isoformat() if getattr(booking, "check_in_at", None) else None,
                "check_out_at": booking.check_out_at.isoformat() if getattr(booking, "check_out_at", None) else None,
                "scheduled_minutes": _booking_scheduled_minutes(booking),
                "worked_minutes": _booking_elapsed_minutes(booking),
                "extra_minutes": (
                    max(0, (_booking_elapsed_minutes(booking) or 0) - (_booking_scheduled_minutes(booking) or 0))
                    if _booking_elapsed_minutes(booking) is not None and _booking_scheduled_minutes(booking) is not None
                    else None
                ),
                "location_label": getattr(booking, "location_label", None),
                "location_address": getattr(booking, "formatted_address", None),
            }
            for booking in related_bookings
        ],
    }


@router.get("/admin/booking-requests/{request_id}/available-nannies")
def get_admin_booking_request_available_nannies(
    request_id: int,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    require_admin(authorization, db)

    req = db.query(models.BookingRequest).filter(models.BookingRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Booking request not found")

    parent_profile = db.query(models.ParentProfile).filter(models.ParentProfile.user_id == req.parent_user_id).first()
    location = None
    if req.location_id:
        location = db.query(models.ParentLocation).filter(models.ParentLocation.id == req.location_id).first()

    parent_lat = None
    parent_lng = None
    if location and getattr(location, "lat", None) is not None and getattr(location, "lng", None) is not None:
        parent_lat = float(location.lat)
        parent_lng = float(location.lng)
    elif parent_profile and getattr(parent_profile, "lat", None) is not None and getattr(parent_profile, "lng", None) is not None:
        parent_lat = float(parent_profile.lat)
        parent_lng = float(parent_profile.lng)

    if parent_lat is None or parent_lng is None:
        raise HTTPException(status_code=400, detail="Client location is missing coordinates")

    windows = _booking_request_windows(db, req)
    if not windows:
        start_dt = _parse_iso_dt(req.start_dt or req.requested_starts_at)
        end_dt = _parse_iso_dt(req.end_dt or req.requested_ends_at)
        windows = [(start_dt, end_dt)]

    candidates = _search_nannies_by_area(
        db=db,
        parent_area_id=None,
        parent_lat=parent_lat,
        parent_lng=parent_lng,
        max_distance_km=30.0,
        min_rating=None,
        tag_ids=None,
        qualification_ids=None,
        language_ids=None,
    )

    available = []
    for item in candidates:
        nanny_id = int(item.get("nanny_id") or 0)
        if nanny_id <= 0:
            continue
        if all(_is_nanny_available(db, nanny_id, slot_start, slot_end) for slot_start, slot_end in windows):
            available.append(
                {
                    "nanny_id": nanny_id,
                    "user_id": item.get("user_id"),
                    "name": item.get("name"),
                    "distance_km": item.get("distance_km"),
                    "location_hint": item.get("location_hint"),
                    "average_rating_12m": item.get("average_rating_12m"),
                    "review_count_12m": item.get("review_count_12m"),
                    "completed_jobs_count": item.get("completed_jobs_count"),
                    "job_type": item.get("job_type"),
                    "has_own_car": item.get("has_own_car"),
                    "has_drivers_license": item.get("has_drivers_license"),
                }
            )

    return {
        "request_id": req.id,
        "group_id": req.group_id or req.id,
        "radius_km": 30,
        "location": {
            "label": getattr(location, "label", None) if location else None,
            "address": getattr(location, "formatted_address", None) if location else getattr(parent_profile, "formatted_address", None) if parent_profile else None,
        },
        "schedule": [
            {
                "start_dt": _to_iso_z(slot_start),
                "end_dt": _to_iso_z(slot_end),
            }
            for slot_start, slot_end in windows
        ],
        "results": available,
    }


@router.get("/admin/bookings/overview")
def list_admin_bookings_overview(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    require_admin(authorization, db)

    now = datetime.utcnow()
    local_tz = ZoneInfo("Africa/Johannesburg")
    local_today = datetime.now(local_tz).date()
    tomorrow = local_today + timedelta(days=1)
    month_start = local_today.replace(day=1)
    next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    month_end = next_month - timedelta(days=1)
    parent_user = aliased(models.User)
    nanny_user = aliased(models.User)

    request_rows = (
        db.query(models.BookingRequest, parent_user, nanny_user)
        .join(parent_user, parent_user.id == models.BookingRequest.parent_user_id)
        .join(models.Nanny, models.Nanny.id == models.BookingRequest.nanny_id)
        .join(nanny_user, nanny_user.id == models.Nanny.user_id)
        .order_by(models.BookingRequest.created_at.desc())
        .all()
    )
    _mark_overdue_booking_requests_notified(db, request_rows)
    booking_rows = (
        db.query(models.Booking, parent_user, nanny_user)
        .join(parent_user, parent_user.id == models.Booking.client_user_id)
        .join(models.Nanny, models.Nanny.id == models.Booking.nanny_id)
        .join(nanny_user, nanny_user.id == models.Nanny.user_id)
        .order_by(models.Booking.starts_at.desc(), models.Booking.id.desc())
        .all()
    )
    request_by_id = {req.id: req for req, _, _ in request_rows}
    booking_request_ids = {
        getattr(booking, "booking_request_id", None)
        for booking, _, _ in booking_rows
        if getattr(booking, "booking_request_id", None) is not None
    }

    pending_requests = []
    unsuccessful_bookings = []
    upcoming_bookings = []
    bookings_in_progress = []
    past_bookings = []
    bookings_tomorrow = []
    month_confirmed_bookings = []

    for req, parent, nanny in request_rows:
        item = {
            "source": "request",
            "request_id": req.id,
            "booking_id": None,
            "status": req.status,
            "parent_name": parent.name,
            "parent_email": parent.email,
            "nanny_name": nanny.name,
            "start_dt": req.start_dt or (req.requested_starts_at.isoformat() if req.requested_starts_at else None),
            "end_dt": req.end_dt or (req.requested_ends_at.isoformat() if req.requested_ends_at else None),
            "location_label": None,
            "reason": _booking_request_reason_label(req.admin_reason),
            "created_at": req.created_at.isoformat() if getattr(req, "created_at", None) else None,
            "updated_at": req.updated_at.isoformat() if getattr(req, "updated_at", None) else None,
            "is_overdue": bool(getattr(req, "created_at", None) and (now - req.created_at) >= timedelta(hours=6)),
        }
        if req.status in ("tbc", "pending_admin"):
            pending_requests.append(item)
        elif req.status in ("rejected", "cancelled") and req.id not in booking_request_ids:
            unsuccessful_bookings.append(item)

    for booking, parent, nanny in booking_rows:
        start_dt = booking.starts_at
        end_dt = booking.ends_at
        related_request = request_by_id.get(getattr(booking, "booking_request_id", None))
        nanny_response_status = (getattr(related_request, "nanny_response_status", None) or "").lower() if related_request else ""
        is_confirmed = booking.status in ("approved", "accepted") and nanny_response_status == "accepted"
        item = {
            "source": "booking",
            "request_id": getattr(booking, "booking_request_id", None),
            "booking_id": booking.id,
            "status": booking.status,
            "nanny_response_status": nanny_response_status or None,
            "confirmed": bool(is_confirmed),
            "parent_name": parent.name,
            "parent_email": parent.email,
            "nanny_name": nanny.name,
            "start_dt": booking.start_dt or (start_dt.isoformat() if start_dt else None),
            "end_dt": booking.end_dt or (end_dt.isoformat() if end_dt else None),
            "location_label": getattr(booking, "location_label", None) or getattr(booking, "formatted_address", None),
            "reason": getattr(booking, "cancellation_reason", None),
            "created_at": None,
            "updated_at": getattr(booking, "cancelled_at", None).isoformat() if getattr(booking, "cancelled_at", None) else None,
            "check_in_at": booking.check_in_at.isoformat() if getattr(booking, "check_in_at", None) else None,
            "check_out_at": booking.check_out_at.isoformat() if getattr(booking, "check_out_at", None) else None,
            "google_calendar_event_id": getattr(booking, "google_calendar_event_id", None),
            "google_calendar_synced_at": booking.google_calendar_synced_at.isoformat() if getattr(booking, "google_calendar_synced_at", None) else None,
            "google_calendar_sync_error": getattr(booking, "google_calendar_sync_error", None),
        }
        if is_confirmed and start_dt:
            local_start = start_dt.replace(tzinfo=timezone.utc).astimezone(local_tz) if start_dt.tzinfo is None else start_dt.astimezone(local_tz)
            if local_start.date() == tomorrow:
                bookings_tomorrow.append(item)
            if month_start <= local_start.date() <= month_end:
                month_confirmed_bookings.append(item)
        if booking.status in ("cancelled", "rejected"):
            unsuccessful_bookings.append(item)
            continue
        if booking.status == "completed" or (end_dt and end_dt < now):
            past_bookings.append(item)
            continue
        if booking.check_in_at and not booking.check_out_at:
            bookings_in_progress.append(item)
            continue
        if booking.status in ("approved", "accepted", "pending"):
            upcoming_bookings.append(item)
            continue
        past_bookings.append(item)

    def _sort_desc(items: List[dict]) -> List[dict]:
        return sorted(items, key=lambda row: row.get("start_dt") or row.get("created_at") or "", reverse=True)

    def _sort_asc(items: List[dict]) -> List[dict]:
        return sorted(items, key=lambda row: row.get("start_dt") or row.get("created_at") or "")

    month_days = []
    day_cursor = month_start
    while day_cursor <= month_end:
        iso_day = day_cursor.isoformat()
        day_bookings = []
        for item in month_confirmed_bookings:
            item_start = item.get("start_dt")
            if not item_start:
                continue
            try:
                parsed_start = _parse_iso_dt(item_start)
                local_start = parsed_start.replace(tzinfo=timezone.utc).astimezone(local_tz) if parsed_start.tzinfo is None else parsed_start.astimezone(local_tz)
            except Exception:
                continue
            if local_start.date().isoformat() == iso_day:
                day_bookings.append(item)
        month_days.append({
            "date": iso_day,
            "day": day_cursor.day,
            "bookings": _sort_asc(day_bookings),
        })
        day_cursor += timedelta(days=1)

    return {
        "pending_requests": _sort_desc(pending_requests),
        "bookings_tomorrow": _sort_asc(bookings_tomorrow),
        "upcoming_bookings": _sort_desc(upcoming_bookings),
        "bookings_in_progress": _sort_desc(bookings_in_progress),
        "past_bookings": _sort_desc(past_bookings),
        "unsuccessful_bookings": _sort_desc(unsuccessful_bookings),
        "month_calendar": {
            "year": month_start.year,
            "month": month_start.month,
            "month_label": month_start.strftime("%B %Y"),
            "days": month_days,
        },
    }


@router.post("/admin/bookings/sync-google-calendar")
def sync_admin_confirmed_bookings_to_google_calendar(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    require_admin(authorization, db)
    confirmed_requests = (
        db.query(models.BookingRequest)
        .filter(
            models.BookingRequest.status == "approved",
            models.BookingRequest.nanny_response_status == "accepted",
        )
        .order_by(models.BookingRequest.id.asc())
        .all()
    )
    before_synced = (
        db.query(models.Booking)
        .filter(models.Booking.google_calendar_event_id.isnot(None))
        .count()
    )
    for req in confirmed_requests:
        _sync_confirmed_booking_request_to_google_calendar(db, req)
    after_synced = (
        db.query(models.Booking)
        .filter(models.Booking.google_calendar_event_id.isnot(None))
        .count()
    )
    errors = (
        db.query(models.Booking)
        .filter(models.Booking.google_calendar_sync_error.isnot(None))
        .count()
    )
    return {
        "ok": True,
        "checked_requests": len(confirmed_requests),
        "newly_synced": max(after_synced - before_synced, 0),
        "synced_total": after_synced,
        "error_total": errors,
    }


@router.get("/admin/users/{user_id}")
def admin_get_user(
    user_id: int,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    require_admin(authorization, db)
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "is_admin": bool(getattr(user, "is_admin", False)),
        "created_at": None,
    }


@router.get("/admin/parents/{user_id}/profile")
def admin_get_parent_profile(
    user_id: int,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    require_admin(authorization, db)
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    profile = db.query(models.ParentProfile).filter(models.ParentProfile.user_id == user_id).first()
    default_loc = (
        db.query(models.ParentLocation)
        .filter(models.ParentLocation.parent_user_id == user_id, models.ParentLocation.is_default == True)
        .first()
    )
    kids_ages = []
    if profile and getattr(profile, "kids_ages_json", None):
        try:
            kids_ages = json.loads(getattr(profile, "kids_ages_json", None)) or []
        except Exception:
            kids_ages = []
    access_flags = []
    if profile and getattr(profile, "access_flags_json", None):
        try:
            access_flags = json.loads(getattr(profile, "access_flags_json", None)) or []
        except Exception:
            access_flags = []
    return {
        "name": user.name,
        "phone": getattr(profile, "phone", None) if profile else None,
        "phone_alt": getattr(user, "phone_alt", None),
        "kids_count": getattr(profile, "kids_count", None) if profile else None,
        "kids_ages": kids_ages,
        "suburb": (default_loc.suburb if default_loc else None) or (getattr(profile, "suburb", None) if profile else None),
        "city": (default_loc.city if default_loc else None) or (getattr(profile, "city", None) if profile else None),
        "province": (default_loc.province if default_loc else None) or (getattr(profile, "province", None) if profile else None),
        "formatted_address": getattr(default_loc, "formatted_address", None) if default_loc else getattr(profile, "formatted_address", None) if profile else None,
        "location_label": getattr(default_loc, "label", None) if default_loc else getattr(profile, "location_label", None) if profile else None,
        "residence_type": getattr(profile, "residence_type", None) if profile else None,
        "special_notes": getattr(profile, "special_notes", None) if profile else None,
        "family_photo_url": getattr(profile, "family_photo_url", None) if profile else None,
        "access_flags": access_flags,
        "booking_responsibilities": getattr(profile, "booking_responsibilities", None) if profile else None,
        "booking_adult_present": getattr(profile, "booking_adult_present", None) if profile else None,
        "booking_reason": getattr(profile, "booking_reason", None) if profile else None,
        "booking_children_count": getattr(profile, "booking_children_count", None) if profile else None,
        "booking_meal_option": getattr(profile, "booking_meal_option", None) if profile else None,
        "booking_food_restrictions": getattr(profile, "booking_food_restrictions", None) if profile else None,
        "booking_dogs": getattr(profile, "booking_dogs", None) if profile else None,
    }


@router.get("/admin/nannies/{user_id}/profile")
def admin_get_nanny_profile(
    user_id: int,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    require_admin(authorization, db)
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    nanny = db.query(models.Nanny).filter(models.Nanny.user_id == user_id).first()
    profile = None
    if nanny:
        profile = db.query(models.NannyProfile).filter(models.NannyProfile.nanny_id == nanny.id).first()
    def simple_list(items):
        return [{"id": x.id, "name": x.name} for x in (items or [])]
    qualifications = simple_list(getattr(profile, "qualifications", None)) if profile else []
    tags = simple_list(getattr(profile, "tags", None)) if profile else []
    previous_jobs = _normalize_previous_jobs(getattr(profile, "previous_jobs_json", None)) if profile else []
    certificate_urls = []
    if profile and getattr(profile, "certificates_json", None):
        try:
            parsed_certs = json.loads(getattr(profile, "certificates_json", None))
            if isinstance(parsed_certs, list):
                certificate_urls = [str(url).strip() for url in parsed_certs if str(url).strip()]
        except Exception:
            certificate_urls = []
    age = compute_age(getattr(profile, "date_of_birth", None)) if profile else None
    return {
        "name": user.name,
        "phone": getattr(user, "phone", None),
        "phone_alt": getattr(user, "phone_alt", None),
        "nanny_id": nanny.id if nanny else None,
        "suburb": getattr(profile, "suburb", None) if profile else None,
        "city": getattr(profile, "city", None) if profile else None,
        "province": getattr(profile, "province", None) if profile else None,
        "approved": bool(getattr(nanny, "approved", False)) if nanny else False,
        "application_status": getattr(profile, "application_status", None) if profile else None,
        "admin_reason": getattr(profile, "admin_reason", None) if profile else None,
        "reviewed_at": getattr(profile, "reviewed_at", None) if profile else None,
        "reviewed_by_user_id": getattr(profile, "reviewed_by_user_id", None) if profile else None,
        "profile_summary": _build_nanny_profile_summary(
            age=age,
            nationality=getattr(profile, "nationality", None) if profile else None,
            qualifications=qualifications,
            tags=tags,
            previous_jobs=previous_jobs,
            bio=getattr(profile, "bio", None) if profile else None,
        ),
        "bio": getattr(profile, "bio", None) if profile else None,
        "date_of_birth": getattr(profile, "date_of_birth", None) if profile else None,
        "age": age,
        "nationality": getattr(profile, "nationality", None) if profile else None,
        "gender": getattr(profile, "gender", None) if profile else None,
        "ethnicity": getattr(profile, "ethnicity", None) if profile else None,
        "passport_number": getattr(profile, "passport_number", None) if profile else None,
        "passport_expiry": getattr(profile, "passport_expiry", None) if profile else None,
        "passport_document_url": getattr(profile, "passport_document_url", None) if profile else None,
        "permit_status": getattr(profile, "permit_status", None) if profile else None,
        "work_permit": getattr(profile, "work_permit", None) if profile else None,
        "work_permit_expiry": getattr(profile, "work_permit_expiry", None) if profile else None,
        "work_permit_document_url": getattr(profile, "work_permit_document_url", None) if profile else None,
        "waiver": getattr(profile, "waiver", None) if profile else None,
        "sa_id_number": getattr(profile, "sa_id_number", None) if profile else None,
        "sa_id_document_url": getattr(profile, "sa_id_document_url", None) if profile else None,
        "police_clearance_status": getattr(profile, "police_clearance_status", None) if profile else None,
        "police_clearance_document_url": getattr(profile, "police_clearance_document_url", None) if profile else None,
        "drivers_license_document_url": getattr(profile, "drivers_license_document_url", None) if profile else None,
        "certificate_urls": certificate_urls,
        "dog_preference": getattr(profile, "dog_preference", None) if profile else None,
        "job_type": getattr(profile, "job_type", None) if profile else None,
        "current_job_availability": getattr(profile, "current_job_availability", None) if profile else None,
        "has_drivers_license": getattr(profile, "has_drivers_license", None) if profile else None,
        "has_own_car": getattr(profile, "has_own_car", None) if profile else None,
        "has_own_kids": getattr(profile, "has_own_kids", None) if profile else None,
        "own_kids_details": getattr(profile, "own_kids_details", None) if profile else None,
        "medical_conditions": getattr(profile, "medical_conditions", None) if profile else None,
        "my_nanny_training_status": getattr(profile, "my_nanny_training_status", None) if profile else None,
        "studying_details": getattr(profile, "studying_details", None) if profile else None,
        "tags": tags,
        "languages": simple_list(getattr(profile, "languages", None)) if profile else [],
        "qualifications": qualifications,
        "previous_jobs": previous_jobs,
        "formatted_address": getattr(profile, "formatted_address", None) if profile else None,
        "postal_code": getattr(profile, "postal_code", None) if profile else None,
        "country": getattr(profile, "country", None) if profile else None,
        "lat": getattr(profile, "lat", None) if profile else None,
        "lng": getattr(profile, "lng", None) if profile else None,
    }


@router.get("/admin/users/{user_id}/booking-stats")
def admin_user_booking_stats(
    user_id: int,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    require_admin(authorization, db)
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    parent_count = db.query(models.Booking).filter(models.Booking.client_user_id == user_id).count()
    nanny_count = 0
    if user.role == "nanny":
        nanny = db.query(models.Nanny).filter(models.Nanny.user_id == user_id).first()
        if nanny:
            nanny_count = db.query(models.Booking).filter(models.Booking.nanny_id == nanny.id).count()

    return {
        "bookings_made_count": parent_count if user.role == "parent" else 0,
        "bookings_attended_count": nanny_count if user.role == "nanny" else 0,
        "total_bookings_count": parent_count + nanny_count,
    }


@router.get("/admin/users/{user_id}/revenue")
def admin_user_revenue(
    user_id: int,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    require_admin(authorization, db)
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    total = 0
    if user.role == "parent":
        total = db.query(func.coalesce(func.sum(models.Booking.price_cents), 0)).filter(
            models.Booking.client_user_id == user_id
        ).scalar() or 0
    elif user.role == "nanny":
        nanny = db.query(models.Nanny).filter(models.Nanny.user_id == user_id).first()
        if nanny:
            total = db.query(func.coalesce(func.sum(models.Booking.price_cents), 0)).filter(
                models.Booking.nanny_id == nanny.id
            ).scalar() or 0

    return {"total_revenue": total}


@router.patch("/admin/users/{user_id}")
def admin_update_user(
    user_id: int,
    payload: schemas.AdminSetUserAdminRequest,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    admin = require_admin(authorization, db)
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    before = {"is_admin": bool(getattr(user, "is_admin", False))}

    if not payload.is_admin and getattr(user, "is_admin", False):
        admin_count = db.query(models.User).filter(models.User.is_admin == True).count()
        if admin_count <= 1:
            raise HTTPException(status_code=409, detail="Cannot remove last admin")

    user.is_admin = bool(payload.is_admin)
    db.commit()
    db.refresh(user)

    after = {"is_admin": bool(getattr(user, "is_admin", False))}
    log_audit(
        db,
        actor_user=admin,
        target_user_id=user.id,
        entity="users",
        entity_id=user.id,
        action="admin_toggle",
        before_obj=before,
        after_obj=after,
        changed_fields=None,
        request=request,
    )
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "is_admin": bool(user.is_admin),
    }


@router.patch("/admin/nannies/{nanny_id}/approve")
def approve_nanny(
    nanny_id: int,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    _require_admin_user(authorization, db)
    nanny = db.query(models.Nanny).filter_by(id=nanny_id).first()
    if not nanny:
        raise HTTPException(status_code=404, detail="Nanny not found")

    profile = db.query(models.NannyProfile).filter_by(nanny_id=nanny_id).first()
    if not profile:
        profile = models.NannyProfile(nanny_id=nanny_id)
        db.add(profile)

    profile.is_approved = 1
    profile.approved_at = datetime.utcnow().isoformat()
    nanny.approved = True

    db.commit()
    return {"ok": True, "nanny_id": nanny_id}


@router.get("/admin/users")
def admin_list_users(
    authorization: Optional[str] = Header(default=None),
    q: Optional[str] = Query(default=None),
    role: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    require_admin(authorization, db)
    query = db.query(models.User)
    if q:
        like = f"%{q.lower()}%"
        query = query.filter(
            or_(
                func.lower(models.User.name).like(like),
                func.lower(models.User.email).like(like),
            )
        )
    if role:
        query = query.filter(models.User.role == role)
    users = query.order_by(models.User.id.asc()).all()

    user_ids = [u.id for u in users]
    audit_map = {}
    if user_ids:
        rows = (
            db.query(
                models.AuditLog.target_user_id,
                func.min(models.AuditLog.created_at),
                func.max(models.AuditLog.created_at),
            )
            .filter(models.AuditLog.target_user_id.in_(user_ids))
            .group_by(models.AuditLog.target_user_id)
            .all()
        )
        for uid, first_at, last_at in rows:
            audit_map[uid] = {"joined_at": first_at, "last_activity_at": last_at}

    parent_profiles = {}
    parent_locations = {}
    parent_ids = [u.id for u in users if u.role == "parent"]
    if parent_ids:
        for p in db.query(models.ParentProfile).filter(models.ParentProfile.user_id.in_(parent_ids)).all():
            parent_profiles[p.user_id] = p
        for loc in (
            db.query(models.ParentLocation)
            .filter(models.ParentLocation.parent_user_id.in_(parent_ids), models.ParentLocation.is_default == True)
            .all()
        ):
            parent_locations[loc.parent_user_id] = loc

    nanny_profiles = {}
    nanny_ids = {}
    nanny_approved_map = {}
    nanny_user_ids = [u.id for u in users if u.role == "nanny"]
    if nanny_user_ids:
        nannies = (
            db.query(models.Nanny, models.NannyProfile)
            .outerjoin(models.NannyProfile, models.NannyProfile.nanny_id == models.Nanny.id)
            .filter(models.Nanny.user_id.in_(nanny_user_ids))
            .all()
        )
        for nanny, profile in nannies:
            nanny_profiles[nanny.user_id] = profile
            nanny_ids[nanny.user_id] = nanny.id
            nanny_approved_map[nanny.user_id] = bool(getattr(nanny, "approved", False)) or bool(getattr(profile, "is_approved", 0) if profile else 0)

    users = [
        u for u in users
        if u.role != "nanny" or nanny_approved_map.get(u.id, False)
    ]

    rating_map = {}
    for nanny_id in set(nanny_ids.values()):
        try:
            avg, cnt = get_rating_12m_for_nanny(db, nanny_id)
            rating_map[nanny_id] = {"rating": avg, "review_count": cnt or 0}
        except Exception:
            rating_map[nanny_id] = {"rating": None, "review_count": 0}

    def location_for_user(u):
        if u.role == "parent":
            loc = parent_locations.get(u.id)
            prof = parent_profiles.get(u.id)
            suburb = (loc.suburb if loc else None) or (prof.suburb if prof else None)
            city = (loc.city if loc else None) or (prof.city if prof else None)
            province = (loc.province if loc else None) or (prof.province if prof else None)
        elif u.role == "nanny":
            prof = nanny_profiles.get(u.id)
            suburb = prof.suburb if prof else None
            city = prof.city if prof else None
            province = prof.province if prof else None
        else:
            suburb = city = province = None
        parts = [p for p in [suburb, city, province] if p]
        return {
            "suburb": suburb,
            "city": city,
            "province": province,
            "label": ", ".join(parts) if parts else None,
        }

    return [
        {
            "id": u.id,
            "name": u.name,
            "email": u.email,
            "role": u.role,
            "is_admin": bool(getattr(u, "is_admin", False)),
            "nanny_id": nanny_ids.get(u.id),
            "joined_at": audit_map.get(u.id, {}).get("joined_at").isoformat() if audit_map.get(u.id, {}).get("joined_at") else None,
            "last_activity_at": audit_map.get(u.id, {}).get("last_activity_at").isoformat() if audit_map.get(u.id, {}).get("last_activity_at") else None,
            "location": location_for_user(u),
            "rating": rating_map.get(nanny_ids.get(u.id), {}).get("rating") if u.role == "nanny" else None,
            "review_count": rating_map.get(nanny_ids.get(u.id), {}).get("review_count") if u.role == "nanny" else 0,
        }
        for u in users
    ]


@router.patch("/admin/users/{user_id}/admin")
def admin_set_user_admin(
    user_id: int,
    payload: schemas.AdminSetUserAdminRequest,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    admin = require_admin(authorization, db)
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    before = {"is_admin": bool(getattr(user, "is_admin", False))}

    if not payload.is_admin and getattr(user, "is_admin", False):
        admin_count = db.query(models.User).filter(models.User.is_admin == True).count()
        if admin_count <= 1:
            raise HTTPException(status_code=409, detail="Cannot remove last admin")

    user.is_admin = bool(payload.is_admin)
    db.commit()
    db.refresh(user)

    after = {"is_admin": bool(getattr(user, "is_admin", False))}
    log_audit(
        db,
        actor_user=admin,
        target_user_id=user.id,
        entity="users",
        entity_id=user.id,
        action="admin_toggle",
        before_obj=before,
        after_obj=after,
        changed_fields=None,
        request=request,
    )
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "is_admin": bool(user.is_admin),
    }


@router.patch("/admin/nannies/{nanny_id}/approval")
def admin_set_nanny_approval(
    nanny_id: int,
    payload: schemas.AdminSetNannyApprovalRequest,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    require_admin(authorization, db)
    nanny = db.query(models.Nanny).filter(models.Nanny.id == nanny_id).first()
    if not nanny:
        raise HTTPException(status_code=404, detail="Nanny not found")
    nanny.approved = bool(payload.approved)
    profile = db.query(models.NannyProfile).filter(models.NannyProfile.nanny_id == nanny.id).first()
    if profile:
        profile.application_status = "approved" if nanny.approved else "pending"
        profile.admin_reason = None
        profile.reviewed_at = datetime.utcnow().isoformat()
        profile.reviewed_by_user_id = None
        profile.is_approved = 1 if nanny.approved else 0
        profile.approved_at = datetime.utcnow().isoformat() if nanny.approved else None
    db.commit()
    db.refresh(nanny)
    return {"nanny_id": nanny.id, "approved": nanny.approved}


@router.patch("/admin/nannies/{nanny_id}/application")
def admin_set_nanny_application_status(
    nanny_id: int,
    payload: schemas.AdminNannyApplicationUpdateRequest,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    admin = require_admin(authorization, db)
    nanny = db.query(models.Nanny).filter(models.Nanny.id == nanny_id).first()
    if not nanny:
        raise HTTPException(status_code=404, detail="Nanny not found")
    profile = db.query(models.NannyProfile).filter(models.NannyProfile.nanny_id == nanny.id).first()
    if not profile:
        profile = models.NannyProfile(nanny_id=nanny.id)
        db.add(profile)
        db.commit()
        db.refresh(profile)

    before = {
        "application_status": getattr(profile, "application_status", None),
        "admin_reason": getattr(profile, "admin_reason", None),
        "is_approved": bool(getattr(profile, "is_approved", 0)),
        "approved_at": getattr(profile, "approved_at", None),
    }

    if payload.status == "hold" and not (payload.reason or "").strip():
        raise HTTPException(status_code=400, detail="Please provide a note explaining what information is still outstanding")

    profile.application_status = payload.status
    profile.admin_reason = (payload.reason or "").strip() or None
    profile.reviewed_at = datetime.utcnow().isoformat()
    profile.reviewed_by_user_id = admin.id

    if payload.status == "approved":
        nanny.approved = True
        profile.is_approved = 1
        profile.approved_at = datetime.utcnow().isoformat()
    else:
        nanny.approved = False
        profile.is_approved = 0
        if payload.status != "approved":
            profile.approved_at = None

    db.commit()
    db.refresh(profile)

    after = {
        "application_status": getattr(profile, "application_status", None),
        "admin_reason": getattr(profile, "admin_reason", None),
        "is_approved": bool(getattr(profile, "is_approved", 0)),
        "approved_at": getattr(profile, "approved_at", None),
    }
    log_audit(
        db,
        actor_user=admin,
        target_user_id=nanny.user_id,
        entity="nanny_profiles",
        entity_id=profile.id,
        action="application_status_update",
        before_obj=before,
        after_obj=after,
        changed_fields=None,
        request=request,
    )

    return {
        "nanny_id": nanny.id,
        "application_status": profile.application_status,
        "admin_reason": profile.admin_reason,
        "approved": bool(nanny.approved),
    }


@router.get("/admin/dashboard")
def admin_dashboard(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    require_admin(authorization, db)
    pending_nannies = (
        db.query(models.Nanny, models.User)
        .join(models.User, models.User.id == models.Nanny.user_id)
        .filter(models.Nanny.approved == False)
        .all()
    )

    parent_user = aliased(models.User)
    nanny_user = aliased(models.User)
    location = aliased(models.ParentLocation)
    pending_requests = (
        db.query(models.BookingRequest, parent_user, nanny_user, location)
        .join(parent_user, parent_user.id == models.BookingRequest.parent_user_id)
        .join(models.Nanny, models.Nanny.id == models.BookingRequest.nanny_id)
        .join(nanny_user, nanny_user.id == models.Nanny.user_id)
        .outerjoin(location, location.id == models.BookingRequest.location_id)
        .filter(models.BookingRequest.status == "tbc")
        .all()
    )
    return {
        "pending_nannies": [
            {
                "nanny_id": n.id,
                "user_id": u.id,
                "name": u.name,
                "email": u.email,
                "approved": n.approved,
            }
            for n, u in pending_nannies
        ],
        "pending_booking_requests": [
            {
                "id": r.id,
                "parent_user_id": r.parent_user_id,
                "parent_name": pu.name,
                "parent_email": pu.email,
                "nanny_id": r.nanny_id,
                "nanny_name": nu.name,
                "status": r.status,
                "start_dt": r.start_dt or (r.requested_starts_at.isoformat() if r.requested_starts_at else None),
                "end_dt": r.end_dt or (r.requested_ends_at.isoformat() if r.requested_ends_at else None),
                "location_label": (loc.label if loc else None) or (loc.formatted_address if loc else None),
            }
            for r, pu, nu, loc in pending_requests
        ],
    }


@router.post("/admin/invites")
def admin_create_invite(
    payload: schemas.AdminInviteCreateRequest,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    admin = require_admin(authorization, db)
    email = payload.email.strip().lower()

    existing = db.query(models.User).filter(func.lower(models.User.email) == email).first()
    if existing and bool(getattr(existing, "is_admin", False)):
        raise HTTPException(status_code=409, detail="User is already an admin")

    now = datetime.utcnow()
    db.query(models.AdminInvite).filter(
        models.AdminInvite.email == email,
        models.AdminInvite.status == "pending",
    ).update({"status": "cancelled"})

    token = uuid.uuid4().hex
    expires_at = now + timedelta(days=7)
    invite = models.AdminInvite(
        email=email,
        token=token,
        status="pending",
        created_at=now,
        expires_at=expires_at,
        invited_by_user_id=admin.id,
        reason=(payload.reason or "").strip() or None,
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)

    link = f"{app_base_url()}/static/admin_invite.html?token={token}"
    body = "\n".join([
        "You have been invited to become an admin.",
        "",
        f"Accept invite: {link}",
        "",
        "If you did not expect this, you can ignore this email.",
    ])
    get_email_client().send(EmailMessage(to=[email], subject="Admin invite", body=body))

    log_audit(
        db,
        actor_user=admin,
        target_user_id=existing.id if existing else None,
        entity="admin_invites",
        entity_id=invite.id,
        action="create",
        before_obj={},
        after_obj={"email": email, "status": invite.status, "expires_at": invite.expires_at},
        changed_fields=None,
        request=request,
    )
    return {"ok": True, "invite_id": invite.id}


@router.get("/auth/admin-invite/{token}")
def get_admin_invite(token: str, db: Session = Depends(get_db)):
    invite = db.query(models.AdminInvite).filter(models.AdminInvite.token == token).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    now = datetime.utcnow()
    if invite.status == "pending" and invite.expires_at < now:
        invite.status = "expired"
        db.commit()
    return {
        "email": invite.email,
        "status": invite.status,
        "expires_at": invite.expires_at.isoformat() if invite.expires_at else None,
    }


@router.post("/auth/admin-invite/accept")
def accept_admin_invite(
    payload: schemas.AdminInviteAcceptRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    invite = db.query(models.AdminInvite).filter(models.AdminInvite.token == payload.token).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    now = datetime.utcnow()
    if invite.status != "pending":
        raise HTTPException(status_code=400, detail="Invite is not pending")
    if invite.expires_at and invite.expires_at < now:
        invite.status = "expired"
        db.commit()
        raise HTTPException(status_code=400, detail="Invite expired")

    email = invite.email
    existing = db.query(models.User).filter(func.lower(models.User.email) == email.lower()).first()
    if existing:
        raise HTTPException(status_code=409, detail="User already exists")

    if len(payload.password) < 6:
        raise HTTPException(status_code=400, detail="Password too short")

    user = models.User(
        name=payload.name.strip(),
        email=email.lower(),
        password_hash=hash_password(payload.password),
        role="admin",
        is_admin=True,
    )
    db.add(user)
    db.flush()

    invite.status = "accepted"
    invite.accepted_at = now
    invite.accepted_user_id = user.id
    db.commit()

    log_audit(
        db,
        actor_user=user,
        target_user_id=user.id,
        entity="admin_invites",
        entity_id=invite.id,
        action="accept",
        before_obj={"status": "pending"},
        after_obj={"status": "accepted"},
        changed_fields=None,
        request=request,
    )

    token = _create_access_token(user)
    _set_access_cookie(response, token)
    _set_csrf_cookie(response)
    return {
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "nanny_id": None,
            "is_admin": True,
        },
    }


@router.patch("/admin/booking-requests/{request_id}/status")
def admin_set_booking_request_status(
    request_id: int,
    payload: schemas.AdminSetBookingRequestStatusRequest,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    if payload.status == "accepted":
        return approve_booking_request(request_id, request, authorization, db)
    if payload.status == "rejected":
        return reject_booking_request(request_id, None, request, authorization, db)
    raise HTTPException(status_code=400, detail="Invalid status")


@router.post("/paystack/webhook")
async def paystack_webhook(request: Request, db: Session = Depends(get_db)):
    secret = os.getenv("PAYSTACK_SECRET_KEY")
    body = await request.body()
    signature = request.headers.get("x-paystack-signature") or request.headers.get("X-Paystack-Signature")
    if not secret or not signature:
        raise HTTPException(status_code=400, detail="Invalid signature")
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha512).hexdigest()
    if expected != signature:
        raise HTTPException(status_code=400, detail="Invalid signature")

    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid payload")

    event = payload.get("event")
    data = payload.get("data") or {}

    if event not in ("refund.processed", "refund.failed"):
        return {"ok": True}

    tx_id = None
    tx_ref = None
    refund_ref = data.get("reference") or data.get("refund_reference")
    transaction = data.get("transaction")
    if isinstance(transaction, dict):
        tx_id = transaction.get("id")
        tx_ref = transaction.get("reference")
    elif transaction is not None:
        tx_id = transaction
    tx_ref = tx_ref or data.get("transaction_reference") or data.get("reference")

    q = db.query(models.BookingRequest)
    if tx_id is not None:
        q = q.filter(models.BookingRequest.paystack_transaction_id == str(tx_id))
    elif tx_ref:
        q = q.filter(models.BookingRequest.paystack_reference == str(tx_ref))
    else:
        return {"ok": True}

    req = q.first()
    if not req:
        return {"ok": True}

    if refund_ref:
        req.paystack_refund_reference = str(refund_ref)
    if event == "refund.processed":
        req.refund_status = "processed"
        req.refund_processed_at = datetime.utcnow()
    elif event == "refund.failed":
        req.refund_status = "failed"
        req.refund_failed_at = datetime.utcnow()
        req.refund_failure_reason = data.get("message") or data.get("gateway_response")

    db.commit()
    return {"ok": True}
