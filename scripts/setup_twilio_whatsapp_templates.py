#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path

import requests
import truststore
from dotenv import load_dotenv

from app.services.whatsapp_templates import WHATSAPP_UTILITY_TEMPLATES, content_sid_env_key


truststore.inject_into_ssl()


def _request(method: str, url: str, sid: str, token: str, **kwargs):
    response = requests.request(method, url, auth=(sid, token), timeout=30, **kwargs)
    data = response.json() if response.content else {}
    if not 200 <= response.status_code < 300:
        message = data.get("message") if isinstance(data, dict) else None
        raise RuntimeError(message or response.text or f"Twilio returned {response.status_code}")
    return data


def _existing_templates(sid: str, token: str) -> dict[str, str]:
    data = _request("GET", "https://content.twilio.com/v1/Content?PageSize=1000", sid, token)
    return {
        item["friendly_name"]: item["sid"]
        for item in data.get("contents", [])
        if item.get("friendly_name") and item.get("sid")
    }


def _update_env(path: Path, values: dict[str, str]) -> None:
    lines = path.read_text().splitlines() if path.exists() else []
    keys = set(values)
    output = [line for line in lines if not any(line.startswith(f"{key}=") for key in keys)]
    if output and output[-1].strip():
        output.append("")
    output.extend(f"{key}={value}" for key, value in sorted(values.items()))
    path.write_text("\n".join(output) + "\n")
    path.chmod(0o600)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create My Nanny Twilio Content Templates")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--submit", action="store_true", help="Request WhatsApp Utility approval")
    parser.add_argument("--status", action="store_true", help="Only report current WhatsApp approval states")
    args = parser.parse_args()

    env_path = Path(args.env_file).resolve()
    load_dotenv(env_path)
    sid = (os.getenv("TWILIO_ACCOUNT_SID") or "").strip()
    token = (os.getenv("TWILIO_AUTH_TOKEN") or "").strip()
    if not sid or not token:
        raise SystemExit("TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN are required")

    existing = _existing_templates(sid, token)
    if args.status:
        counts: dict[str, int] = {}
        for event_type, template in WHATSAPP_UTILITY_TEMPLATES.items():
            content_sid = (os.getenv(content_sid_env_key(event_type)) or existing.get(template["name"]) or "").strip()
            if not content_sid:
                status = "missing"
            else:
                data = _request(
                    "GET",
                    f"https://content.twilio.com/v1/Content/{content_sid}/ApprovalRequests",
                    sid,
                    token,
                )
                status = str((data.get("whatsapp") or {}).get("status") or "unsubmitted").lower()
            counts[status] = counts.get(status, 0) + 1
        print("approval status: " + ", ".join(f"{key}={value}" for key, value in sorted(counts.items())))
        return 0

    env_values: dict[str, str] = {}
    failures: list[str] = []
    for event_type, template in WHATSAPP_UTILITY_TEMPLATES.items():
        content_sid = existing.get(template["name"])
        if not content_sid:
            created = _request(
                "POST",
                "https://content.twilio.com/v1/Content",
                sid,
                token,
                json={
                    "friendly_name": template["name"],
                    "language": "en",
                    "variables": {},
                    "types": {"twilio/text": {"body": template["body"]}},
                },
            )
            content_sid = created["sid"]
            print(f"created  {event_type}")
        else:
            print(f"existing {event_type}")
        env_values[content_sid_env_key(event_type)] = content_sid

        if args.submit:
            try:
                approval = _request(
                    "POST",
                    f"https://content.twilio.com/v1/Content/{content_sid}/ApprovalRequests/whatsapp",
                    sid,
                    token,
                    json={"name": template["name"], "category": "UTILITY"},
                )
                print(f"approval {event_type}: {approval.get('status', 'submitted')}")
            except RuntimeError as exc:
                if "already" in str(exc).lower():
                    print(f"approval {event_type}: already submitted")
                else:
                    failures.append(f"{event_type}: {exc}")

    env_values["TWILIO_REQUIRE_TEMPLATES"] = "true"
    _update_env(env_path, env_values)
    print(f"saved {len(env_values) - 1} Content SIDs to {env_path}")
    if failures:
        print("Approval requests requiring attention:")
        for failure in failures:
            print(f"- {failure}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
