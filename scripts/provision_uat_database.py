"""Idempotently create the isolated UAT database on the shared Render instance."""

from __future__ import annotations

import os
import re

from sqlalchemy import create_engine, text

from app.utils.database_target import database_name_from_url, normalize_database_url


SAFE_NAME = re.compile(r"^[a-z][a-z0-9_]{2,62}$")


def main() -> None:
    if (os.getenv("APP_ENV") or "").strip().lower() not in {"staging", "uat"}:
        raise RuntimeError("UAT provisioning is allowed only when APP_ENV is staging or uat")

    admin_url = (os.getenv("DATABASE_ADMIN_URL") or "").strip()
    target = (os.getenv("UAT_EXPECTED_DATABASE_NAME") or "").strip()
    override = (os.getenv("DATABASE_NAME_OVERRIDE") or "").strip()
    if not admin_url:
        raise RuntimeError("DATABASE_ADMIN_URL is required")
    if not SAFE_NAME.fullmatch(target) or target != override:
        raise RuntimeError("UAT database name is missing, unsafe, or does not match override")
    if target == database_name_from_url(admin_url):
        raise RuntimeError("Refusing to use the production database as the UAT database")

    engine = create_engine(
        normalize_database_url(admin_url),
        isolation_level="AUTOCOMMIT",
        pool_pre_ping=True,
    )
    with engine.connect() as connection:
        exists = connection.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": target}
        ).scalar()
        if exists:
            print(f"UAT database {target} already exists")
            return
        connection.exec_driver_sql(f'CREATE DATABASE "{target}"')
        print(f"Created isolated UAT database {target}")


if __name__ == "__main__":
    main()
