import os
import subprocess
import sys


def test_database_guard_script_can_run_from_its_file_path():
    env = os.environ.copy()
    env.update(
        {
            "APP_ENV": "staging",
            "DATABASE_ADMIN_URL": "postgres://owner:secret@internal-host:5432/mynanny",
            "DATABASE_NAME_OVERRIDE": "mynanny_uat",
            "UAT_EXPECTED_DATABASE_NAME": "mynanny_uat",
        }
    )

    result = subprocess.run(
        [sys.executable, "scripts/assert_safe_database_target.py"],
        cwd=os.path.dirname(os.path.dirname(__file__)),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Database safety check passed for mynanny_uat" in result.stdout
