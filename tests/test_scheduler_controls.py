import pytest

from app import main


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, True),
        ("true", True),
        ("1", True),
        ("false", False),
        ("0", False),
        ("off", False),
        ("no", False),
    ],
)
def test_automated_notifications_enabled(monkeypatch, value, expected):
    monkeypatch.setenv("APP_ENV", "development")
    if value is None:
        monkeypatch.delenv("AUTOMATED_NOTIFICATIONS_ENABLED", raising=False)
    else:
        monkeypatch.setenv("AUTOMATED_NOTIFICATIONS_ENABLED", value)

    assert main._automated_notifications_enabled() is expected


def test_automated_notifications_default_off_in_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("AUTOMATED_NOTIFICATIONS_ENABLED", raising=False)

    assert main._automated_notifications_enabled() is False


@pytest.mark.parametrize(
    "wrapper_name",
    [
        "retry_failed_notifications_wrapper",
        "passport_compliance_wrapper",
        "duty_notification_sweep_wrapper",
    ],
)
def test_disabled_notification_wrappers_do_not_open_database(monkeypatch, wrapper_name):
    monkeypatch.setenv("AUTOMATED_NOTIFICATIONS_ENABLED", "false")

    def fail_if_called():
        pytest.fail("Disabled notification wrapper opened a database session")

    monkeypatch.setattr(main, "SessionLocal", fail_if_called)

    getattr(main, wrapper_name)()
