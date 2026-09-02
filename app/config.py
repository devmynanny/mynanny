
import os
from dotenv import load_dotenv

from app.utils.database_target import resolve_database_url

load_dotenv()

class Settings:
    database_url = resolve_database_url()
    admin_api_key = os.getenv("ADMIN_API_KEY", "dev-admin-change-this")
    jwt_secret = os.getenv("JWT_SECRET", "dev-jwt-change-this")
    bootstrap_admin_email = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
    bootstrap_admin_password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")

settings = Settings()
