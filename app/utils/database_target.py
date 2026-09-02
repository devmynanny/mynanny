"""Resolve and validate database targets before the application connects.

UAT can share the production Postgres *instance* to reduce hosting cost, but it
must use a different logical database.  These helpers make the database-name
override explicit and fail closed if staging ever resolves to the instance's
production database.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping

from sqlalchemy.engine import make_url


_SAFE_DATABASE_NAME = re.compile(r"^[a-z][a-z0-9_]{2,62}$")
_UAT_ENVIRONMENTS = {"staging", "uat"}


def normalize_database_url(url: str) -> str:
    value = (url or "").strip()
    if value.startswith("postgres://"):
        return "postgresql://" + value[len("postgres://") :]
    return value


def database_name_from_url(url: str) -> str:
    return (make_url(normalize_database_url(url)).database or "").strip()


def replace_database_name(url: str, database_name: str) -> str:
    name = (database_name or "").strip()
    if not _SAFE_DATABASE_NAME.fullmatch(name):
        raise RuntimeError("DATABASE_NAME_OVERRIDE is missing or unsafe")
    parsed = make_url(normalize_database_url(url)).set(database=name)
    return parsed.render_as_string(hide_password=False)


def resolve_database_url(environ: Mapping[str, str] | None = None) -> str:
    values = environ or os.environ
    base_url = (
        values.get("DATABASE_URL")
        or values.get("DATABASE_ADMIN_URL")
        or "sqlite:///./nanny_app.db"
    )
    override = (values.get("DATABASE_NAME_OVERRIDE") or "").strip()
    normalized = normalize_database_url(base_url)
    return replace_database_name(normalized, override) if override else normalized


def assert_safe_database_target(environ: Mapping[str, str] | None = None) -> str:
    values = environ or os.environ
    resolved_url = resolve_database_url(values)
    app_env = (values.get("APP_ENV") or "").strip().lower()
    if app_env not in _UAT_ENVIRONMENTS:
        return database_name_from_url(resolved_url)

    expected = (values.get("UAT_EXPECTED_DATABASE_NAME") or "").strip()
    override = (values.get("DATABASE_NAME_OVERRIDE") or "").strip()
    if not expected or expected != override:
        raise RuntimeError(
            "UAT database guard failed: the expected database and override must match"
        )

    actual = database_name_from_url(resolved_url)
    if actual != expected:
        raise RuntimeError(
            f"UAT database guard failed: resolved {actual!r}, expected {expected!r}"
        )

    admin_url = (values.get("DATABASE_ADMIN_URL") or "").strip()
    if admin_url and database_name_from_url(admin_url) == actual:
        raise RuntimeError(
            "UAT database guard failed: UAT resolved to the shared instance's "
            "production database"
        )
    return actual
