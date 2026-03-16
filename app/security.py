from passlib.context import CryptContext

# Prefer a stable pure-python scheme for portability across environments.
# Keep bcrypt support for verifying any existing bcrypt hashes.
pwd_context = CryptContext(
    schemes=["pbkdf2_sha256", "bcrypt"],
    deprecated="auto",
)

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)
