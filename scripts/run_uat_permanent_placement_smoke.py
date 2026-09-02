"""Run a destructive happy-path smoke test against an isolated My Nanny UAT.

This script creates a new Self-Match placement for existing UAT test accounts,
records simulated admin payments (never Paystack charges), and exercises the
parent, nanny and administrator workflow through placement completion.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse


BASE_URL = os.environ.get("MYNANNY_UAT_API", "https://mynanny-uat.onrender.com").rstrip("/")
ADMIN_EMAIL = os.environ.get("MYNANNY_UAT_ADMIN_EMAIL", "uat.admin@mynanny.co.za")
PARENT_EMAIL = os.environ.get("MYNANNY_UAT_PARENT_EMAIL", "uat.parent@mynanny.co.za")
NANNY_EMAIL = os.environ.get("MYNANNY_UAT_NANNY_EMAIL", "uat.nanny@mynanny.co.za")
ADMIN_PASSWORD = os.environ.get("MYNANNY_UAT_ADMIN_PASSWORD", "")
PARENT_PASSWORD = os.environ.get("MYNANNY_UAT_PARENT_PASSWORD", "")
NANNY_PASSWORD = os.environ.get("MYNANNY_UAT_NANNY_PASSWORD", "")
PLACEHOLDER_DOCUMENT = Path(__file__).resolve().parents[1] / "app" / "static" / "logo.jpg"


def refuse_unsafe_target() -> None:
    host = (urlparse(BASE_URL).hostname or "").lower()
    if "uat" not in host or host in {"mynanny.co.za", "www.mynanny.co.za"}:
        raise SystemExit(f"Refusing to run against non-UAT target: {BASE_URL}")
    missing = [
        name
        for name, value in {
            "MYNANNY_UAT_ADMIN_PASSWORD": ADMIN_PASSWORD,
            "MYNANNY_UAT_PARENT_PASSWORD": PARENT_PASSWORD,
            "MYNANNY_UAT_NANNY_PASSWORD": NANNY_PASSWORD,
        }.items()
        if not value
    ]
    if missing:
        raise SystemExit("Missing required environment variables: " + ", ".join(missing))


class Actor:
    def __init__(self, email: str, password: str):
        self.email = email
        with tempfile.NamedTemporaryFile(prefix="mynanny-uat-cookies-", delete=False) as handle:
            cookie_path = Path(handle.name)
        try:
            _, status = curl(
                "POST",
                "/auth/login",
                json_body={"email": email, "password": password},
                cookie_path=cookie_path,
            )
            if status != 200:
                raise AssertionError(f"{email}: login returned {status}")
            token = cookie_value(cookie_path, "access_token")
            if not token:
                raise AssertionError(f"{email}: login did not set an access token")
            self.authorization = f"Bearer {token}"
        finally:
            cookie_path.unlink(missing_ok=True)

    def request(
        self,
        method: str,
        path: str,
        *,
        expected: set[int] | None = None,
        **kwargs: Any,
    ) -> bytes:
        body, status = curl(
            method,
            path,
            authorization=self.authorization,
            json_body=kwargs.get("json"),
            params=kwargs.get("params"),
            file=kwargs.get("file"),
        )
        wanted = expected or {200}
        if status not in wanted:
            try:
                detail = json.loads(body)
            except (ValueError, TypeError):
                detail = body.decode("utf-8", errors="replace")[:500]
            raise AssertionError(f"{self.email}: {method} {path} returned {status}: {detail}")
        return body

    def json(self, method: str, path: str, **kwargs: Any) -> Any:
        return json.loads(self.request(method, path, **kwargs))


def cookie_value(path: Path, name: str) -> str | None:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#HttpOnly_"):
            line = line.removeprefix("#HttpOnly_")
        elif not line or line.startswith("#"):
            continue
        columns = line.split("\t")
        if len(columns) >= 7 and columns[5] == name:
            return columns[6]
    return None


def curl(
    method: str,
    path: str,
    *,
    authorization: str | None = None,
    json_body: Any = None,
    params: dict[str, Any] | None = None,
    file: tuple[str, Path, str] | None = None,
    cookie_path: Path | None = None,
) -> tuple[bytes, int]:
    query = f"?{urlencode(params)}" if params else ""
    command = [
        "curl",
        "--silent",
        "--show-error",
        "--max-time",
        "45",
        "--request",
        method,
        f"{BASE_URL}{path}{query}",
        "--write-out",
        "\n__HTTP_STATUS__:%{http_code}",
    ]
    authorization_file: Path | None = None
    if authorization:
        with tempfile.NamedTemporaryFile(
            prefix="mynanny-uat-auth-", mode="w", encoding="utf-8", delete=False
        ) as handle:
            handle.write(f"Authorization: {authorization}\n")
            authorization_file = Path(handle.name)
        command.extend(["--header", f"@{authorization_file}"])
    if cookie_path:
        command.extend(["--cookie-jar", str(cookie_path), "--cookie", str(cookie_path)])
    request_body: bytes | None = None
    if file:
        field_name, file_path, mime_type = file
        command.extend(["--form", f"{field_name}=@{file_path};type={mime_type}"])
    elif json_body is not None:
        request_body = json.dumps(json_body).encode("utf-8")
        command.extend(
            [
                "--header",
                "Content-Type: application/json",
                "--data-binary",
                "@-",
            ]
        )
    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            input=request_body,
        )
    finally:
        if authorization_file:
            authorization_file.unlink(missing_ok=True)
    marker = b"\n__HTTP_STATUS__:"
    body, raw_status = completed.stdout.rsplit(marker, 1)
    return body, int(raw_status.strip())


def one_user(admin: Actor, email: str) -> dict[str, Any]:
    rows = admin.json("GET", "/admin/users", params={"q": email})
    matches = [row for row in rows if row.get("email", "").lower() == email.lower()]
    if len(matches) != 1:
        raise AssertionError(f"Expected one UAT user for {email}, found {len(matches)}")
    return matches[0]


def mark_paid(admin: Actor, placement_id: int, fee_type: str) -> dict[str, Any]:
    return admin.json(
        "POST",
        f"/admin/permanent-placements/{placement_id}/payments/mark-paid",
        json={"fee_type": fee_type, "reason": "UAT smoke test — simulated payment only"},
    )


def main() -> None:
    refuse_unsafe_target()
    health_body, health_status = curl("GET", "/health")
    if health_status != 200 or not json.loads(health_body).get("db_ok"):
        raise AssertionError("UAT health or database safety check failed")

    admin = Actor(ADMIN_EMAIL, ADMIN_PASSWORD)
    parent = Actor(PARENT_EMAIL, PARENT_PASSWORD)
    nanny = Actor(NANNY_EMAIL, NANNY_PASSWORD)

    parent_user = one_user(admin, PARENT_EMAIL)
    nanny_user = one_user(admin, NANNY_EMAIL)
    nanny_id = int(nanny_user["nanny_id"])

    admin.json(
        "PATCH",
        f"/admin/nannies/{nanny_user['id']}/profile",
        json={
            "full_name": "Nomsa UAT Test",
            "phone": "+27810000002",
            "dob": "1990-01-01",
            "bio": "Synthetic UAT caregiver profile for permanent-placement testing.",
            "nationality": "South African",
            "gender": "female",
            "ethnicity": "black",
            "has_own_kids": False,
            "medical_conditions": "None — synthetic UAT profile",
            "formatted_address": "UAT TEST PROFILE — Louwlardia, Centurion",
            "suburb": "Louwlardia",
            "city": "Centurion",
            "province": "Gauteng",
            "postal_code": "0157",
            "country": "South Africa",
            "lat": -25.9,
            "lng": 28.17,
            "sa_id_number": "9001010000080",
            "police_clearance_status": "yes",
            "has_own_car": False,
            "has_drivers_license": False,
            "job_type": "both",
            "current_job_availability": "available",
            "my_nanny_training_status": "yes",
        },
    )
    admin.json(
        "POST",
        f"/admin/nannies/{nanny_user['id']}/documents/sa_id",
        file=("file", PLACEHOLDER_DOCUMENT, "image/jpeg"),
    )
    admin.json(
        "PATCH",
        f"/admin/nannies/{nanny_user['id']}/documents/sa_id/approval",
        params={"approved": "true"},
    )
    admin.json(
        "PATCH",
        f"/admin/nannies/{nanny_id}/approval",
        json={"approved": True},
    )

    nanny.json(
        "PUT",
        "/nannies/me/permanent-placement-profile",
        json={
            "opted_in": True,
            "desired_salary_min_cents": 700_000,
            "desired_salary_max_cents": 900_000,
            "employment_types": ["full_time", "live_out"],
            "preferred_locations": "Centurion and Midrand",
            "available_from": (date.today() + timedelta(days=12)).isoformat(),
            "live_in_preference": "no",
            "profile_notes": "Synthetic UAT candidate; do not contact outside this test.",
        },
    )

    config = parent.json("GET", "/permanent-placements/config")
    if not config.get("enabled"):
        raise AssertionError("Permanent-placement pilot is not enabled")

    today = date.today()
    interview_day = today + timedelta(days=3)
    trial_day = today + timedelta(days=5)
    start_day = today + timedelta(days=12)
    unique_label = datetime.now().strftime("%Y-%m-%d %H:%M")
    placement = parent.json(
        "POST",
        "/parents/me/permanent-placements",
        json={
            "service_tier": "self_match",
            "role_title": f"UAT permanent nanny — {unique_label}",
            "employment_type": "full_time",
            "start_date": start_day.isoformat(),
            "schedule_summary": "Monday to Friday, 07:00 to 17:00",
            "hours_per_week": 45,
            "children_count": 2,
            "children_ages": ["2 years", "5 years"],
            "duties": "Childcare, school runs and children's meals",
            "special_requirements": "UAT TEST ONLY — no real family or employment offer",
            "salary_min_cents": 700_000,
            "salary_max_cents": 900_000,
            "location_suburb": "Louwlardia",
            "location_city": "Centurion",
            "location_province": "Gauteng",
            "live_in": False,
            "drivers_license_required": False,
            "own_car_required": False,
            "languages": ["English"],
            "pets": "None",
        },
    )
    placement_id = int(placement["id"])

    mark_paid(admin, placement_id, "activation")
    admin.json(
        "POST",
        f"/admin/permanent-placements/{placement_id}/qualify",
        json={"note": "UAT family brief checked and qualified"},
    )
    active = mark_paid(admin, placement_id, "candidate_access")
    if active.get("status") != "search_active":
        raise AssertionError("Candidate-access payment did not activate the search")

    candidate = admin.json(
        "POST",
        f"/admin/permanent-placements/{placement_id}/candidates",
        json={"nanny_id": nanny_id, "note": "Synthetic UAT candidate"},
    )
    candidate_id = int(candidate["id"])
    nanny.json(
        "POST",
        f"/nannies/me/permanent-opportunities/{candidate_id}/respond",
        json={"decision": "accepted", "note": "UAT consent"},
    )
    admin.json(
        "POST",
        f"/admin/permanent-placements/{placement_id}/candidates/{candidate_id}/release",
    )

    parent_detail = parent.json("GET", f"/parents/me/permanent-placements/{placement_id}")
    released = parent_detail["candidates"][0]
    forbidden_keys = {"phone", "email", "full_name", "exact_address", "sa_id_number"}
    leaked = forbidden_keys.intersection(released)
    if leaked:
        raise AssertionError(f"Protected candidate fields leaked to the parent: {sorted(leaked)}")

    parent.json(
        "POST",
        f"/parents/me/permanent-placements/{placement_id}/candidates/{candidate_id}/shortlist",
        json={"note": "UAT shortlist"},
    )
    parent.json(
        "POST",
        f"/parents/me/permanent-placements/{placement_id}/candidates/{candidate_id}/request-interview",
        json={"note": "Please arrange the UAT interview"},
    )
    interview_acceptance = nanny.json(
        "POST",
        f"/nannies/me/permanent-opportunities/{candidate_id}/interview-response",
        json={"decision": "accepted", "note": "UAT interview accepted"},
    )
    if interview_acceptance["interview_credits"]["available"] != 4:
        raise AssertionError("Interview acceptance did not consume one credit")

    parent.json(
        "POST",
        f"/permanent-placements/candidates/{candidate_id}/contact-terms",
        json={"accepted": True},
    )
    nanny.json(
        "POST",
        f"/permanent-placements/candidates/{candidate_id}/contact-terms",
        json={"accepted": True},
    )
    communication = parent.json(
        "POST",
        f"/permanent-placements/candidates/{candidate_id}/messages",
        json={"body": "UAT interview confirmed for the arranged time."},
    )
    if not communication.get("can_message"):
        raise AssertionError("Interview communication did not open after both terms were accepted")

    scheduled_at = datetime.combine(interview_day, time(10, 0)).isoformat()
    admin.json(
        "POST",
        f"/admin/permanent-placements/{placement_id}/candidates/{candidate_id}/schedule-interview",
        json={
            "scheduled_at": scheduled_at,
            "interview_format": "in_person",
            "interview_location": "My Nanny UAT test meeting",
            "note": "No real transport required",
        },
    )
    nanny.json(
        "POST",
        f"/nannies/me/permanent-opportunities/{candidate_id}/interview-progress",
        json={"action": "check_in"},
    )
    locked = parent.json(
        "GET",
        f"/permanent-placements/candidates/{candidate_id}/communication",
    )
    if locked.get("window_open") or locked.get("can_message") or locked.get("contact"):
        raise AssertionError("Contact details or direct messaging remained available after check-in")
    nanny.json(
        "POST",
        f"/nannies/me/permanent-opportunities/{candidate_id}/interview-progress",
        json={"action": "completed"},
    )

    parent.json(
        "POST",
        f"/parents/me/permanent-placements/{placement_id}/candidates/{candidate_id}/interview-decision",
        json={"decision": "trial", "feedback": "UAT interview passed; proceed to test trial."},
    )
    trial_start = datetime.combine(trial_day, time(8, 0)).isoformat()
    trial_end = datetime.combine(trial_day, time(16, 0)).isoformat()
    parent.json(
        "POST",
        f"/parents/me/permanent-placements/{placement_id}/candidates/{candidate_id}/trial",
        json={"starts_at": trial_start, "ends_at": trial_end, "note": "UAT test trial"},
    )
    nanny.json(
        "POST",
        f"/nannies/me/permanent-opportunities/{candidate_id}/trial-response",
        json={"decision": "accepted", "note": "UAT trial accepted"},
    )

    parent.json(
        "POST",
        f"/parents/me/permanent-placements/{placement_id}/candidates/{candidate_id}/interview-decision",
        json={"decision": "offer", "feedback": "UAT trial passed; create a test offer."},
    )
    parent.json(
        "POST",
        f"/parents/me/permanent-placements/{placement_id}/candidates/{candidate_id}/offer",
        json={
            "salary_cents": 850_000,
            "start_date": start_day.isoformat(),
            "working_days": [0, 1, 2, 3, 4],
            "start_time": "07:00",
            "end_time": "17:00",
            "terms": "UAT TEST ONLY — Monday to Friday synthetic permanent nanny offer.",
        },
    )
    offer_acceptance = nanny.json(
        "POST",
        f"/nannies/me/permanent-opportunities/{candidate_id}/offer-response",
        json={"decision": "accepted", "note": "UAT offer accepted"},
    )
    if offer_acceptance.get("placement_status") != "awaiting_success_fee":
        raise AssertionError("Accepted offer did not create the success-fee stage")
    if int(offer_acceptance.get("blocked_calendar_days") or 0) < 250:
        raise AssertionError("Accepted offer did not restructure weekday availability")

    placed = mark_paid(admin, placement_id, "success")
    if placed.get("status") != "placed" or not placed.get("guarantee_until"):
        raise AssertionError("Success payment did not complete the placement and replacement period")

    invoices = placed.get("invoices") or []
    if len(invoices) != 3:
        raise AssertionError(f"Expected three Self-Match invoices, found {len(invoices)}")
    for invoice in invoices:
        if invoice.get("status") != "paid":
            raise AssertionError(f"Invoice {invoice.get('id')} was not marked paid")
        if not invoice.get("invoice_number") or not invoice.get("receipt_number"):
            raise AssertionError(f"Invoice {invoice.get('id')} is missing its issued documents")
        for field in ("invoice_pdf_url", "receipt_pdf_url"):
            document = parent.request("GET", invoice[field])
            if not document.startswith(b"%PDF"):
                raise AssertionError(f"{field} for invoice {invoice.get('id')} is not a PDF")

    final_parent = parent.json("GET", f"/parents/me/permanent-placements/{placement_id}")
    final_candidate = final_parent["candidates"][0]
    summary = {
        "ok": True,
        "placement_id": placement_id,
        "candidate_id": candidate_id,
        "parent_user_id": parent_user["id"],
        "nanny_user_id": nanny_user["id"],
        "nanny_id": nanny_id,
        "status": final_parent["status"],
        "candidate_status": final_candidate["status"],
        "offer_status": final_candidate["offer_status"],
        "guarantee_until": final_parent["guarantee_until"],
        "interview_credits": final_parent["interview_credits"],
        "calendar_days_blocked": offer_acceptance["blocked_calendar_days"],
        "invoice_numbers": [row["invoice_number"] for row in invoices],
        "receipt_numbers": [row["receipt_number"] for row in invoices],
        "privacy_check": "passed",
        "contact_lock_check": "passed",
        "payment_mode": "admin-simulated UAT payments; Paystack was not charged",
    }
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
