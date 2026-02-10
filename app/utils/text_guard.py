import re
from typing import Optional


_EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
_URL_RE = re.compile(r"(https?://|www\.)|(\b\w+\.(com|co\.za|net|org|za|io|biz|info)\b)", re.IGNORECASE)
_SOCIAL_RE = re.compile(r"\b(whatsapp|telegram|instagram|facebook|fb|tiktok|snapchat|wechat|line|signal|viber)\b", re.IGNORECASE)
_HANDLE_RE = re.compile(r"@\w{2,}", re.IGNORECASE)
_PHONE_RE = re.compile(r"\+?\d[\d\s().-]{6,}\d")


def _looks_like_phone(text: str) -> bool:
    for match in _PHONE_RE.finditer(text):
        digits = re.sub(r"\D", "", match.group(0))
        if len(digits) >= 7:
            return True
    return False


def redact_contact_info(text: Optional[str]) -> Optional[str]:
    if text is None:
        return None
    value = str(text)
    redacted = value
    redacted = _EMAIL_RE.sub("[redacted]", redacted)
    redacted = _URL_RE.sub("[redacted]", redacted)
    redacted = _SOCIAL_RE.sub("[redacted]", redacted)
    redacted = _HANDLE_RE.sub("[redacted]", redacted)
    # redact phone-like sequences
    def _phone_sub(match: re.Match) -> str:
        digits = re.sub(r"\D", "", match.group(0))
        return "[redacted]" if len(digits) >= 7 else match.group(0)
    redacted = _PHONE_RE.sub(_phone_sub, redacted)
    return redacted
