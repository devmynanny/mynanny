import json
import os
import urllib.request
import urllib.error
from typing import Optional, Tuple, Dict, Any


PAYSTACK_BASE_URL = "https://api.paystack.co"


def _paystack_secret() -> Optional[str]:
    return os.getenv("PAYSTACK_SECRET_KEY")


def _paystack_request(method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Tuple[bool, Dict[str, Any]]:
    secret = _paystack_secret()
    if not secret:
        return False, {"message": "Paystack not configured"}
    data = json.dumps(payload or {}).encode("utf-8")
    req = urllib.request.Request(
        PAYSTACK_BASE_URL + path,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {secret}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            body = res.read().decode("utf-8")
            return True, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8")
            return False, json.loads(body) if body else {"message": "Paystack error"}
        except Exception:
            return False, {"message": "Paystack error"}
    except Exception as e:
        return False, {"message": str(e)}


def create_refund(transaction: str, amount_kobo: Optional[int] = None) -> Tuple[bool, Dict[str, Any]]:
    payload: Dict[str, Any] = {"transaction": transaction}
    if amount_kobo is not None:
        payload["amount"] = amount_kobo
    return _paystack_request("POST", "/refund", payload)


def create_supplementary_charge(
    authorization_code: str,
    amount_kobo: int,
    email: Optional[str] = None,
) -> Tuple[bool, Dict[str, Any]]:
    payload: Dict[str, Any] = {
        "authorization_code": authorization_code,
        "amount": int(amount_kobo),
    }
    if email:
        payload["email"] = email
    return _paystack_request("POST", "/transaction/charge_authorization", payload)


def create_transfer_recipient(
    *,
    account_name: str,
    account_number: str,
    bank_code: str,
) -> Tuple[bool, Dict[str, Any]]:
    payload: Dict[str, Any] = {
        "type": "nuban",
        "name": account_name,
        "account_number": account_number,
        "bank_code": bank_code,
        "currency": "ZAR",
    }
    return _paystack_request("POST", "/transferrecipient", payload)


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
