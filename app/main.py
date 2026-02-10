# app/main.py
from pathlib import Path


from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from app.routes import router
from app.db import Base, engine, SessionLocal, ensure_audit_log_schema, ensure_booking_requests_schema, ensure_nanny_availability_schema, ensure_bookings_schema, ensure_nanny_profiles_schema, ensure_admin_invites_schema, ensure_users_schema, ensure_languages_seed, ensure_parent_favorites_schema, ensure_pricing_settings_schema
from app.routers.public import _decode_access_token
from app import models

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


app = FastAPI()


@app.middleware("http")
async def attach_request_user(request: Request, call_next):
    request.state.user = None
    request.state.impersonated_by_user_id = None
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        token = auth.split(" ", 1)[1].strip()
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
    return response


# Ensure all models are registered before creating tables
Base.metadata.create_all(bind=engine)
ensure_audit_log_schema()
ensure_booking_requests_schema()
ensure_nanny_availability_schema()
ensure_bookings_schema()
ensure_nanny_profiles_schema()
ensure_admin_invites_schema()
ensure_users_schema()
ensure_languages_seed()
ensure_parent_favorites_schema()
ensure_pricing_settings_schema()

app.include_router(router)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
def home():
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")
