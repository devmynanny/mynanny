"""Fail a deployment before startup if its database target is unsafe."""

from app.utils.database_target import assert_safe_database_target


if __name__ == "__main__":
    database_name = assert_safe_database_target()
    print(f"Database safety check passed for {database_name}")
