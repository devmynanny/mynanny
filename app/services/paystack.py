import json
import logging
import os
import urllib.request
import urllib.error
from urllib.parse import urlencode
from typing import Optional, Tuple, Dict, Any

logger = logging.getLogger(__name__)


PAYSTACK_BASE_URL = "https://api.paystack.co"


def _paystack_secret() -> Optional[str]:
    return os.getenv("PAYSTACK_SECRET_KEY")


def _paystack_request(method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Tuple[bool, Dict[str, Any]]:
    secret = _paystack_secret()
    if not secret:
        return False, {"message": "Paystack not configured"}
    data = None if method.upper() == "GET" else json.dumps(payload or {}).encode("utf-8")
    req = urllib.request.Request(
        PAYSTACK_BASE_URL + path,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {secret}",
            "Content-Type": "application/json",
            "User-Agent": "python-requests/2.31.0",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            body = res.read().decode("utf-8")
            return True, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8")
            logger.error("Paystack HTTP %s | path=%s | body=%s", e.code, path, body[:500])
            parsed = json.loads(body) if body else {}
            msg = parsed.get("message") or f"Paystack HTTP {e.code}"
            return False, {"message": msg, "status_code": e.code, "raw": body}
        except Exception as inner:
            logger.error("Paystack HTTP %s | path=%s | failed to read body: %s", e.code, path, inner)
            return False, {"message": f"Paystack HTTP {e.code}"}
    except Exception as e:
        logger.error("Paystack request failed | path=%s | %s", path, e)
        return False, {"message": str(e)}


def initialize_transaction(
    *,
    email: str,
    amount_kobo: int,
    reference: Optional[str] = None,
    callback_url: Optional[str] = None,
    currency: str = "ZAR",
    metadata: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, Dict[str, Any]]:
    payload: Dict[str, Any] = {
        "email": email,
        "amount": int(amount_kobo),
        "currency": currency,
    }
    if reference:
        payload["reference"] = reference
    if callback_url:
        payload["callback_url"] = callback_url
    if metadata:
        payload["metadata"] = metadata
    return _paystack_request("POST", "/transaction/initialize", payload)


def verify_transaction(reference: str) -> Tuple[bool, Dict[str, Any]]:
    return _paystack_request("GET", f"/transaction/verify/{reference}")


def create_refund(transaction: str, amount_kobo: Optional[int] = None) -> Tuple[bool, Dict[str, Any]]:
    payload: Dict[str, Any] = {"transaction": transaction}
    if amount_kobo is not None:
        payload["amount"] = amount_kobo
    return _paystack_request("POST", "/refund", payload)


def create_supplementary_charge(
    authorization_code: str,
    amount_kobo: int,
    email: Optional[str] = None,
    reference: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, Dict[str, Any]]:
    payload: Dict[str, Any] = {
        "authorization_code": authorization_code,
        "amount": int(amount_kobo),
    }
    if email:
        payload["email"] = email
    if reference:
        payload["reference"] = reference
    if metadata:
        payload["metadata"] = metadata
    return _paystack_request("POST", "/transaction/charge_authorization", payload)


def create_transfer_recipient(
    *,
    account_name: str,
    account_number: str,
    bank_code: str,
    currency: str = "ZAR",
) -> Tuple[bool, Dict[str, Any]]:
    payload: Dict[str, Any] = {
        "type": "nuban",
        "name": account_name,
        "account_number": account_number,
        "bank_code": bank_code,
        "currency": currency,
    }
    return _paystack_request("POST", "/transferrecipient", payload)


def list_banks(
    *,
    country: str = "south africa",
    currency: str = "ZAR",
    enabled_for_verification: bool = True,
) -> Tuple[bool, Dict[str, Any]]:
    params = {
        "country": country,
        "currency": currency,
    }
    if enabled_for_verification:
        params["enabled_for_verification"] = "true"
    return _paystack_request("GET", f"/bank?{urlencode(params)}")


def create_transfer(
    *,
    amount_kobo: int,
    recipient_code: str,
    reason: Optional[str] = None,
) -> Tuple[bool, Dict[str, Any]]:
    payload: Dict[str, Any] = {
        "source": "balance",
        "amount": int(amount_kobo),
        "recipient": recipient_code,
    }
    if reason:
        payload["reason"] = reason
    return _paystack_request("POST", "/transfer", payload)
