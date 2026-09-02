"""Generate a synthetic invoice PDF for local visual QA only."""

import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from app.services.invoices import build_invoice_pdf


invoice = SimpleNamespace(
    invoice_number="MN-UAT-INV-2026-000001",
    receipt_number=None,
    issued_at=datetime(2026, 9, 2, 10, 30),
    paid_at=None,
    permanent_placement_id=1042,
    currency="ZAR",
    subtotal_cents=217_391,
    vat_cents=32_609,
    total_cents=250_000,
    issuer_snapshot_json=json.dumps(
        {
            "legal_name": "My Nanny Sample Entity (UAT only)",
            "trading_name": "My Nanny",
            "email": "billing@example.com",
            "phone": "+27 11 000 0000",
            "address": "1 Sample Avenue\nJohannesburg\nGauteng",
            "registration_number": "SAMPLE-REG-001",
            "vat_registered": True,
            "vat_number": "SAMPLE-VAT-001",
            "vat_rate_bps": 1500,
            "prices_include_vat": True,
        }
    ),
    customer_snapshot_json=json.dumps(
        {
            "name": "UAT Family",
            "email": "family@example.com",
            "phone": "+27 82 000 0000",
        }
    ),
    line_items_json=json.dumps(
        [
            {
                "description": "Concierge placement engagement",
                "quantity": 1,
                "amount_cents": 250_000,
            }
        ]
    ),
)

destination = Path("output/pdf/permanent-placement-invoice-sample.pdf")
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_bytes(build_invoice_pdf(invoice, document_kind="invoice"))
print(destination.resolve())
