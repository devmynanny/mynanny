import os
import sqlite3
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.routers.public import hash_password  # uses same hashing as auth

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "nanny_app.db"))


def main() -> None:
    email = os.getenv("ADMIN_EMAIL")
    password = os.getenv("ADMIN_PASSWORD")

    if not email or not password:
        raise SystemExit("ADMIN_EMAIL and ADMIN_PASSWORD must be set")

    email = email.strip().lower()
    name = email.split("@")[0]

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("DELETE FROM users WHERE email = ?", (email,))

    pwd_hash = hash_password(password)
    cur.execute(
        "INSERT INTO users (name, role, email, password_hash, is_admin, is_active) VALUES (?,?,?,?,?,?)",
        (name, "admin", email, pwd_hash, 1, 1),
    )
    conn.commit()
    print(cur.lastrowid)
    conn.close()


if __name__ == "__main__":
    main()
