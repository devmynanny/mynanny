
import os
from dotenv import load_dotenv

load_dotenv()

def _normalize_db_url(url: str) -> str:
    # Render/Heroku style URLs use postgres://, which SQLAlchemy 2 rejects.
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://"):]
    return url


class Settings:
    database_url = _normalize_db_url(os.getenv("DATABASE_URL", "sqlite:///./nanny_app.db"))
    admin_api_key = os.getenv("ADMIN_API_KEY", "dev-admin-change-this")
    jwt_secret = os.getenv("JWT_SECRET", "dev-jwt-change-this")
    bootstrap_admin_email = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
    bootstrap_admin_password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")

settings = Settings()
