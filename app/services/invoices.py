from __future__ import annotations

import hashlib
import html
import io
import json
from datetime import datetime
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session

from app import models
from app.services import storage
from app.utils.time import utc_now


FEE_LABELS = {
    "activation": "Self-Match search activation",
    "candidate_access": "Self-Match interview package top-up",
    "application": "Concierge consultation",
    "engagement": "Concierge placement engagement",
    "success": "Successful placement balance",
}


def get_or_create_billing_settings(db: Session) -> models.BillingSettings:
    row = db.query(models.BillingSettings).filter(models.BillingSettings.id == 1).first()
    if row is None:
        row = models.BillingSettings(id=1)
        db.add(row)
        db.flush()
    return row


def billing_settings_payload(db: Session) -> dict[str, Any]:
    row = get_or_create_billing_settings(db)
    missing: list[str] = []
    if not (row.issuer_legal_name or "").strip():
        missing.append("legal business name")
    if not (row.issuer_address or "").strip():
        missing.append("business address")
    if not (row.issuer_email or "").strip():
        missing.append("billing email")
    if row.tax_status_confirmed_at is None:
        missing.append("VAT status confirmation")
    if row.vat_registered and not (row.issuer_vat_number or "").strip():
        missing.append("VAT number")
    if row.vat_registered and row.prices_include_vat is not True:
        missing.append("confirmation that configured fees include VAT")
    return {
        "issuer_legal_name": row.issuer_legal_name,
        "issuer_trading_name": row.issuer_trading_name,
        "issuer_email": row.issuer_email,
        "issuer_phone": row.issuer_phone,
        "issuer_address": row.issuer_address,
        "issuer_registration_number": row.issuer_registration_number,
        "issuer_vat_number": row.issuer_vat_number,
        "vat_registered": bool(row.vat_registered),
        "vat_rate_bps": int(row.vat_rate_bps or 0),
        "prices_include_vat": row.prices_include_vat,
        "tax_status_confirmed": row.tax_status_confirmed_at is not None,
        "invoice_prefix": row.invoice_prefix,
        "ready_to_issue": not missing,
        "missing": missing,
    }


def _json(value: str | None, fallback: Any) -> Any:
    try:
        parsed = json.loads(value or "")
        return parsed
    except (TypeError, ValueError):
        return fallback


def _issuer_snapshot(settings: models.BillingSettings) -> dict[str, Any]:
    return {
        "legal_name": settings.issuer_legal_name,
        "trading_name": settings.issuer_trading_name,
        "email": settings.issuer_email,
        "phone": settings.issuer_phone,
        "address": settings.issuer_address,
        "registration_number": settings.issuer_registration_number,
        "vat_registered": bool(settings.vat_registered),
        "vat_number": settings.issuer_vat_number,
        "vat_rate_bps": int(settings.vat_rate_bps or 0),
        "prices_include_vat": settings.prices_include_vat,
    }


def get_or_create_invoice_for_payment(
    db: Session,
    payment: models.PermanentPlacementPayment,
) -> models.Invoice:
    invoice = (
        db.query(models.Invoice)
        .filter(models.Invoice.permanent_payment_id == payment.id)
        .first()
    )
    if invoice is not None:
        return invoice
    placement = (
        db.query(models.PermanentPlacement)
        .filter(models.PermanentPlacement.id == payment.placement_id)
        .first()
    )
    if placement is None:
        raise ValueError("Permanent placement not found for invoice")
    parent = db.query(models.User).filter(models.User.id == placement.parent_user_id).first()
    if parent is None:
        raise ValueError("Parent not found for invoice")
    invoice = models.Invoice(
        service_type="permanent_placement",
        parent_user_id=parent.id,
        permanent_placement_id=placement.id,
        permanent_payment_id=payment.id,
        status="draft",
        currency="ZAR",
        subtotal_cents=payment.amount_cents,
        vat_cents=0,
        total_cents=payment.amount_cents,
        line_items_json=json.dumps(
            [
                {
                    "description": FEE_LABELS.get(payment.fee_type, payment.fee_type.replace("_", " ").title()),
                    "quantity": 1,
                    "amount_cents": payment.amount_cents,
                    "fee_type": payment.fee_type,
                    "placement_id": placement.id,
                }
            ],
            separators=(",", ":"),
        ),
        customer_snapshot_json=json.dumps(
            {
                "name": parent.name,
                "email": parent.email,
                "phone": parent.phone,
            },
            separators=(",", ":"),
        ),
        paystack_reference=payment.paystack_reference,
        paystack_transaction_id=payment.paystack_transaction_id,
    )
    db.add(invoice)
    db.flush()
    return invoice


def _next_number(settings: models.BillingSettings, kind: str, now: datetime) -> str:
    prefix = (settings.invoice_prefix or "MN").strip().upper()
    if kind == "invoice":
        sequence = int(settings.next_invoice_sequence or 1)
        settings.next_invoice_sequence = sequence + 1
        code = "INV"
    else:
        sequence = int(settings.next_receipt_sequence or 1)
        settings.next_receipt_sequence = sequence + 1
        code = "RCT"
    return f"{prefix}-{code}-{now.year}-{sequence:06d}"


def _money(cents: int, currency: str = "ZAR") -> str:
    return f"R {cents / 100:,.2f}" if currency == "ZAR" else f"{currency} {cents / 100:,.2f}"


def build_invoice_pdf(invoice: models.Invoice, *, document_kind: str) -> bytes:
    issuer = _json(invoice.issuer_snapshot_json, {})
    customer = _json(invoice.customer_snapshot_json, {})
    line_items = _json(invoice.line_items_json, [])
    number = invoice.invoice_number if document_kind == "invoice" else invoice.receipt_number
    title = "Invoice" if document_kind == "invoice" else "Payment receipt"
    document_date = invoice.issued_at if document_kind == "invoice" else invoice.paid_at
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Right", parent=styles["BodyText"], alignment=TA_RIGHT))
    styles.add(ParagraphStyle(name="SmallMuted", parent=styles["BodyText"], fontSize=8.5, leading=12, textColor=colors.HexColor("#64748B")))
    stream = io.BytesIO()
    document = SimpleDocTemplate(
        stream,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"{title} {number}",
        author=str(issuer.get("trading_name") or issuer.get("legal_name") or "My Nanny"),
    )
    brand = colors.HexColor("#1F607D")
    pale = colors.HexColor("#EAF4F7")
    story: list[Any] = []
    story.append(
        Table(
            [[
                Paragraph(f"<font size='23'><b>{html.escape(str(issuer.get('trading_name') or 'My Nanny'))}</b></font>", styles["BodyText"]),
                Paragraph(f"<font size='22'><b>{title.upper()}</b></font><br/><font size='10'>{html.escape(str(number or 'DRAFT'))}</font>", styles["Right"]),
            ]],
            colWidths=[95 * mm, 75 * mm],
            style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("TEXTCOLOR", (0, 0), (-1, -1), brand)]),
        )
    )
    story.append(Spacer(1, 9 * mm))
    issuer_lines = [
        f"<b>{html.escape(str(issuer.get('legal_name') or ''))}</b>",
        html.escape(str(issuer.get("address") or "")).replace("\n", "<br/>"),
        html.escape(str(issuer.get("email") or "")),
        html.escape(str(issuer.get("phone") or "")),
    ]
    if issuer.get("registration_number"):
        issuer_lines.append(f"Registration: {html.escape(str(issuer['registration_number']))}")
    if issuer.get("vat_registered"):
        issuer_lines.append(f"VAT: {html.escape(str(issuer.get('vat_number') or ''))}")
    customer_lines = [
        "<b>Bill to</b>",
        html.escape(str(customer.get("name") or "")),
        html.escape(str(customer.get("email") or "")),
        html.escape(str(customer.get("phone") or "")),
    ]
    details_lines = [
        f"<b>Date</b><br/>{document_date.strftime('%d %B %Y') if document_date else '-'}",
        f"<b>Placement reference</b><br/>PP-{invoice.permanent_placement_id}",
    ]
    story.append(
        Table(
            [[Paragraph("<br/>".join(filter(None, issuer_lines)), styles["BodyText"]), Paragraph("<br/>".join(filter(None, customer_lines)), styles["BodyText"]), Paragraph("<br/><br/>".join(details_lines), styles["Right"])]],
            colWidths=[66 * mm, 55 * mm, 49 * mm],
            style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.6, colors.HexColor("#CBD5E1")), ("BOTTOMPADDING", (0, 0), (-1, -1), 8 * mm)]),
        )
    )
    story.append(Spacer(1, 7 * mm))
    rows = [[Paragraph("<b>Description</b>", styles["BodyText"]), Paragraph("<b>Amount</b>", styles["Right"])]]
    for item in line_items:
        rows.append([
            Paragraph(html.escape(str(item.get("description") or "Service")), styles["BodyText"]),
            Paragraph(_money(int(item.get("amount_cents") or 0), invoice.currency), styles["Right"]),
        ])
    story.append(
        Table(
            rows,
            colWidths=[130 * mm, 40 * mm],
            repeatRows=1,
            style=TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), pale),
                ("TEXTCOLOR", (0, 0), (-1, 0), brand),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#CBD5E1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#E2E8F0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * mm),
                ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
            ]),
        )
    )
    story.append(Spacer(1, 6 * mm))
    total_rows = []
    if issuer.get("vat_registered"):
        total_rows.extend([
            ["Subtotal", _money(invoice.subtotal_cents, invoice.currency)],
            [f"VAT ({int(issuer.get('vat_rate_bps') or 0) / 100:g}%)", _money(invoice.vat_cents, invoice.currency)],
        ])
    total_rows.append(["Total", _money(invoice.total_cents, invoice.currency)])
    if document_kind == "receipt":
        total_rows.append(["Paid", _money(invoice.total_cents, invoice.currency)])
    totals = Table(total_rows, colWidths=[35 * mm, 38 * mm], hAlign="RIGHT")
    totals.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, -1), (-1, -1), 12),
        ("TEXTCOLOR", (0, -1), (-1, -1), brand),
        ("TOPPADDING", (0, 0), (-1, -1), 2 * mm),
    ]))
    story.append(totals)
    story.append(Spacer(1, 12 * mm))
    payment_note = (
        "Payment received. Thank you."
        if document_kind == "receipt"
        else "Please use the secure Paystack payment option in your My Nanny placement portal."
    )
    story.append(Paragraph(payment_note, styles["BodyText"]))
    story.append(Spacer(1, 5 * mm))
    story.append(Paragraph("This document was generated from the immutable price and customer snapshot stored with the service payment. Contact My Nanny through the app if any detail needs review.", styles["SmallMuted"]))
    document.build(story)
    return stream.getvalue()


def _issue_pdf(db: Session, invoice: models.Invoice, settings: models.BillingSettings, kind: str) -> bool:
    now = utc_now()
    if invoice.issuer_snapshot_json is None:
        invoice.issuer_snapshot_json = json.dumps(_issuer_snapshot(settings), separators=(",", ":"))
        if settings.vat_registered:
            rate = int(settings.vat_rate_bps or 0)
            invoice.subtotal_cents = round(invoice.total_cents * 10_000 / (10_000 + rate))
            invoice.vat_cents = invoice.total_cents - invoice.subtotal_cents
        else:
            invoice.subtotal_cents = invoice.total_cents
            invoice.vat_cents = 0
    if kind == "invoice":
        if invoice.invoice_pdf_url:
            return False
        invoice.invoice_number = invoice.invoice_number or _next_number(settings, "invoice", now)
        invoice.issued_at = invoice.issued_at or now
        data = build_invoice_pdf(invoice, document_kind="invoice")
        key = f"invoices/{invoice.parent_user_id}/{invoice.invoice_number}.pdf"
        invoice.invoice_pdf_url = storage.store_bytes(key, data, "application/pdf")
        invoice.invoice_pdf_sha256 = hashlib.sha256(data).hexdigest()
        invoice.status = "paid" if invoice.paid_at else "issued"
    else:
        if invoice.receipt_pdf_url:
            return False
        if invoice.paid_at is None:
            raise ValueError("A receipt cannot be issued before payment")
        invoice.receipt_number = invoice.receipt_number or _next_number(settings, "receipt", now)
        data = build_invoice_pdf(invoice, document_kind="receipt")
        key = f"invoices/{invoice.parent_user_id}/{invoice.receipt_number}.pdf"
        invoice.receipt_pdf_url = storage.store_bytes(key, data, "application/pdf")
        invoice.receipt_pdf_sha256 = hashlib.sha256(data).hexdigest()
        invoice.status = "paid"
    db.add(invoice)
    db.add(settings)
    return True


def sync_invoice_for_payment(
    db: Session,
    payment: models.PermanentPlacementPayment,
) -> tuple[models.Invoice, bool, bool]:
    invoice = get_or_create_invoice_for_payment(db, payment)
    invoice.paystack_reference = payment.paystack_reference
    invoice.paystack_transaction_id = payment.paystack_transaction_id
    if payment.status == "paid":
        invoice.paid_at = payment.paid_at or utc_now()
    readiness = billing_settings_payload(db)
    if not readiness["ready_to_issue"]:
        return invoice, False, False
    settings = (
        db.query(models.BillingSettings)
        .filter(models.BillingSettings.id == 1)
        .with_for_update()
        .one()
    )
    invoice_created = _issue_pdf(db, invoice, settings, "invoice")
    receipt_created = False
    if payment.status == "paid":
        receipt_created = _issue_pdf(db, invoice, settings, "receipt")
    return invoice, invoice_created, receipt_created


def invoice_payload(invoice: models.Invoice) -> dict[str, Any]:
    return {
        "id": invoice.id,
        "service_type": invoice.service_type,
        "permanent_placement_id": invoice.permanent_placement_id,
        "permanent_payment_id": invoice.permanent_payment_id,
        "status": invoice.status,
        "currency": invoice.currency,
        "subtotal_cents": invoice.subtotal_cents,
        "vat_cents": invoice.vat_cents,
        "total_cents": invoice.total_cents,
        "line_items": _json(invoice.line_items_json, []),
        "invoice_number": invoice.invoice_number,
        "receipt_number": invoice.receipt_number,
        "invoice_pdf_url": invoice.invoice_pdf_url,
        "receipt_pdf_url": invoice.receipt_pdf_url,
        "paystack_reference": invoice.paystack_reference,
        "issued_at": invoice.issued_at,
        "paid_at": invoice.paid_at,
        "invoice_email_requested_at": invoice.invoice_email_requested_at,
        "receipt_email_requested_at": invoice.receipt_email_requested_at,
        "created_at": invoice.created_at,
    }
