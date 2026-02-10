import os
import smtplib
from dataclasses import dataclass
from email.mime.text import MIMEText
from typing import Iterable, Optional


def _env(name: str) -> Optional[str]:
    v = os.getenv(name)
    if v is None:
        return None
    v = v.strip()
    return v if v else None


def _parse_int(name: str, default: int) -> int:
    v = _env(name)
    if not v:
        return default
    try:
        return int(v)
    except Exception:
        return default


def _split_emails(csv: Optional[str]) -> list[str]:
    if not csv:
        return []
    out: list[str] = []
    for part in csv.split(","):
        e = part.strip()
        if e:
            out.append(e)
    return out


@dataclass
class EmailMessage:
    to: list[str]
    subject: str
    body: str


class EmailClient:
    """
    Modes:
      EMAIL_MODE=log      logs emails to stdout, never raises
      EMAIL_MODE=smtp     sends via SMTP, falls back to log if misconfigured
      EMAIL_MODE=off      no op
    """

    def __init__(self) -> None:
        self.mode = (_env("EMAIL_MODE") or "log").lower()

        self.smtp_host = _env("SMTP_HOST")
        self.smtp_port = _parse_int("SMTP_PORT", 587)
        self.smtp_user = _env("SMTP_USER")
        self.smtp_pass = _env("SMTP_PASS")
        self.from_email = _env("FROM_EMAIL") or self.smtp_user

    def can_smtp(self) -> bool:
        if not self.smtp_host:
            return False
        if not self.from_email:
            return False
        if not self.smtp_user or not self.smtp_pass:
            return False
        return True

    def send(self, msg: EmailMessage) -> None:
        if self.mode == "off":
            return

        if self.mode == "smtp" and self.can_smtp():
            try:
                self._send_smtp(msg)
                return
            except Exception as e:
                print(f"[EMAIL][SMTP_FAIL] {e!r}")

        self._log(msg)

    def _log(self, msg: EmailMessage) -> None:
        print("[EMAIL][LOG]")
        print(f"to: {', '.join(msg.to)}")
        print(f"subject: {msg.subject}")
        print("body:")
        print(msg.body)
        print("[EMAIL][END]")

    def _send_smtp(self, msg: EmailMessage) -> None:
        mime = MIMEText(msg.body, "plain", "utf-8")
        mime["Subject"] = msg.subject
        mime["From"] = self.from_email
        mime["To"] = ", ".join(msg.to)

        with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=15) as server:
            server.starttls()
            server.login(self.smtp_user, self.smtp_pass)
            server.sendmail(self.from_email, msg.to, mime.as_string())


_email_client: Optional[EmailClient] = None


def get_email_client() -> EmailClient:
    global _email_client
    if _email_client is None:
        _email_client = EmailClient()
    return _email_client


def admin_emails() -> list[str]:
    return _split_emails(_env("ADMIN_EMAILS"))


def app_base_url() -> str:
    return _env("APP_BASE_URL") or "http://127.0.0.1:8000"
