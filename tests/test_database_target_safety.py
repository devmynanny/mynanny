import pytest

from app.utils.database_target import (
    assert_safe_database_target,
    database_name_from_url,
    resolve_database_url,
)


ADMIN_URL = "postgres://owner:secret@internal-host:5432/mynanny"


def test_uat_database_override_rewrites_only_database_name():
    values = {
        "APP_ENV": "staging",
        "DATABASE_ADMIN_URL": ADMIN_URL,
        "DATABASE_NAME_OVERRIDE": "mynanny_uat",
        "UAT_EXPECTED_DATABASE_NAME": "mynanny_uat",
    }

    resolved = resolve_database_url(values)

    assert database_name_from_url(resolved) == "mynanny_uat"
    assert "owner:secret@internal-host:5432" in resolved
    assert assert_safe_database_target(values) == "mynanny_uat"


def test_uat_guard_rejects_production_database():
    values = {
        "APP_ENV": "staging",
        "DATABASE_ADMIN_URL": ADMIN_URL,
        "DATABASE_NAME_OVERRIDE": "mynanny",
        "UAT_EXPECTED_DATABASE_NAME": "mynanny",
    }

    with pytest.raises(RuntimeError, match="production database"):
        assert_safe_database_target(values)


def test_uat_guard_rejects_mismatched_expected_name():
    values = {
        "APP_ENV": "staging",
        "DATABASE_ADMIN_URL": ADMIN_URL,
        "DATABASE_NAME_OVERRIDE": "mynanny_uat",
        "UAT_EXPECTED_DATABASE_NAME": "something_else",
    }

    with pytest.raises(RuntimeError, match="must match"):
        assert_safe_database_target(values)
