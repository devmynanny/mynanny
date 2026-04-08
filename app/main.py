# app/main.py
from pathlib import Path
import hmac
import secrets
import os


from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from app.routes import router
from app.db import Base, engine, SessionLocal, ensure_audit_log_schema, ensure_booking_requests_schema, ensure_nanny_availability_schema, ensure_bookings_schema, ensure_nanny_profiles_schema, ensure_parent_profiles_schema, ensure_admin_invites_schema, ensure_users_schema, ensure_languages_seed, ensure_parent_favorites_schema, ensure_pricing_settings_schema, ensure_bootstrap_admin
from app.routers.public import _decode_access_token, ACCESS_COOKIE_NAME, CSRF_COOKIE_NAME, CSRF_HEADER_NAME
from app import models
from app.request_context import auth_token_ctx

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


app = FastAPI()
SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


def _is_prod_like_env() -> bool:
    env = (os.getenv("APP_ENV") or os.getenv("ENV") or "").strip().lower()
    return env in {"prod", "production", "staging"}


@app.middleware("http")
async def attach_request_user(request: Request, call_next):
    request.state.user = None
    request.state.impersonated_by_user_id = None
    auth = request.headers.get("Authorization")
    has_bearer = bool(auth and auth.startswith("Bearer "))
    access_cookie = request.cookies.get(ACCESS_COOKIE_NAME)
    token = None
    if has_bearer:
        token = auth.split(" ", 1)[1].strip()
    if not token:
        token = access_cookie

    if (
        request.method not in SAFE_METHODS
        and access_cookie
        and not has_bearer
        and request.url.path != "/paystack/webhook"
    ):
        csrf_cookie = request.cookies.get(CSRF_COOKIE_NAME)
        csrf_header = request.headers.get(CSRF_HEADER_NAME) or request.headers.get(CSRF_HEADER_NAME.lower())
        if not csrf_cookie or not csrf_header or not hmac.compare_digest(csrf_cookie, csrf_header):
            return JSONResponse(status_code=403, content={"detail": "CSRF validation failed"})

    token_ctx = auth_token_ctx.set(token)
    try:
        if token:
            payload = _decode_access_token(token)
            if payload and payload.get("sub"):
                db = SessionLocal()
                try:
                    user = db.query(models.User).filter(models.User.id == payload["sub"]).first()
                    if user:
                        request.state.user = {"id": user.id, "is_admin": bool(getattr(user, "is_admin", False))}
                        request.state.impersonated_by_user_id = payload.get("impersonated_by")
                finally:
                    db.close()
        response = await call_next(request)
        if token and not request.cookies.get(CSRF_COOKIE_NAME):
            response.set_cookie(
                key=CSRF_COOKIE_NAME,
                value=secrets.token_urlsafe(32),
                httponly=False,
                secure=_is_prod_like_env(),
                samesite="lax",
                max_age=60 * 60 * 24 * 30,
                path="/",
            )
    finally:
        auth_token_ctx.reset(token_ctx)
    return response


# Ensure all models are registered before creating tables
Base.metadata.create_all(bind=engine)
ensure_audit_log_schema()
ensure_booking_requests_schema()
ensure_nanny_availability_schema()
ensure_bookings_schema()
ensure_nanny_profiles_schema()
ensure_parent_profiles_schema()
ensure_admin_invites_schema()
ensure_users_schema()
ensure_languages_seed()
ensure_parent_favorites_schema()
ensure_pricing_settings_schema()
ensure_bootstrap_admin()

app.include_router(router)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def home():
    return RedirectResponse(url="/static/login.html", status_code=307)
