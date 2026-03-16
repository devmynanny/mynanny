from app.config import settings
from datetime import date
from fastapi import Depends, HTTPException, Header, Query
from jose import jwt
from sqlalchemy.orm import Session
from app.db import SessionLocal

ADMIN_API_KEY = settings.admin_api_key
JWT_SECRET = settings.jwt_secret
JWT_ALG = "HS256"

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def compute_age(dob: date | None) -> int | None:
    if dob is None:
        return None
    today = date.today()
    years = today.year - dob.year
    if (today.month, today.day) < (dob.month, dob.day):
        years -= 1
    return years

def require_admin(
    x_admin_key: str | None = Header(default=None),
    admin_key: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
) -> None:
    key = x_admin_key or admin_key
    if key == ADMIN_API_KEY:
        return
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        except Exception:
            raise HTTPException(status_code=401, detail="Unauthorized")
        if payload.get("role") == "admin":
            return
    raise HTTPException(status_code=401, detail="Unauthorized")
