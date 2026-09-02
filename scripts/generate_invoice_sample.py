"""Generate a synthetic invoice PDF for local visual QA only."""

import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from app.services.invoices import build_invoice_pdf


invoice = SimpleNamespace(
    invoice_number="MN-INV-2026-000002",
    receipt_number=None,
    issued_at=datetime(2026, 9, 2, 10, 30),
    paid_at=None,
    permanent_placement_id=1,
    currency="ZAR",
    subtotal_cents=115_000,
    vat_cents=0,
    total_cents=115_000,
    issuer_snapshot_json=json.dumps(
        {
            "legal_name": "My Nanny (Pty) Ltd",
            "trading_name": "My Nanny",
            "email": "sayhi@mynanny.co.za",
            "phone": "0813967980",
            "address": "21 Victoria Cres, Louwlardia, Centurion",
            "registration_number": None,
            "vat_registered": False,
            "vat_number": None,
            "vat_rate_bps": 0,
            "prices_include_vat": False,
        }
    ),
    customer_snapshot_json=json.dumps(
        {
            "name": "UAT Parent Family",
            "email": "uat.parent@mynanny.co.za",
            "phone": "+27810000001",
        }
    ),
    line_items_json=json.dumps(
        [
            {
                "description": "Self-Match interview package top-up",
                "quantity": 1,
                "amount_cents": 115_000,
            }
        ]
    ),
)

destination = Path("output/pdf/permanent-placement-invoice-sample.pdf")
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_bytes(build_invoice_pdf(invoice, document_kind="invoice"))
print(destination.resolve())
