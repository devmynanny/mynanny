from __future__ import annotations

import hashlib
import html
import io
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
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


def _address_lines(value: Any) -> list[str]:
    lines: list[str] = []
    for raw_line in str(value or "").splitlines():
        lines.extend(part.strip() for part in raw_line.split(",") if part.strip())
    return lines


def build_invoice_pdf(invoice: models.Invoice, *, document_kind: str) -> bytes:
    issuer = _json(invoice.issuer_snapshot_json, {})
    customer = _json(invoice.customer_snapshot_json, {})
    line_items = _json(invoice.line_items_json, [])
    number = invoice.invoice_number if document_kind == "invoice" else invoice.receipt_number
    title = "Invoice" if document_kind == "invoice" else "Payment receipt"
    document_date = invoice.issued_at if document_kind == "invoice" else invoice.paid_at
    styles = getSampleStyleSheet()
    ink = colors.HexColor("#18324A")
    muted = colors.HexColor("#667B8D")
    blue = colors.HexColor("#5F9FBE")
    blue_dark = colors.HexColor("#2F6F92")
    blue_pale = colors.HexColor("#E8F5FA")
    cream = colors.HexColor("#FBFAF6")
    line = colors.HexColor("#DBE7EC")
    coral = colors.HexColor("#DC765F")
    green = colors.HexColor("#4C8A72")

    styles.add(ParagraphStyle(
        name="InvoiceBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=10.5,
        leading=15,
        textColor=ink,
        spaceAfter=0,
    ))
    styles.add(ParagraphStyle(
        name="InvoiceBodyRight",
        parent=styles["InvoiceBody"],
        alignment=TA_RIGHT,
    ))
    styles.add(ParagraphStyle(
        name="InvoiceEyebrow",
        parent=styles["InvoiceBody"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=10,
        textColor=blue_dark,
        tracking=2.1,
        uppercase=True,
    ))
    styles.add(ParagraphStyle(
        name="InvoiceTitle",
        parent=styles["InvoiceBodyRight"],
        fontName="Times-Bold",
        fontSize=28,
        leading=29,
        textColor=ink,
    ))
    styles.add(ParagraphStyle(
        name="InvoiceNumber",
        parent=styles["InvoiceBodyRight"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        textColor=blue_dark,
    ))
    styles.add(ParagraphStyle(
        name="InvoiceCardTitle",
        parent=styles["InvoiceBody"],
        fontName="Times-Bold",
        fontSize=15,
        leading=17,
        textColor=ink,
        spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="InvoiceSmallMuted",
        parent=styles["InvoiceBody"],
        fontSize=8.5,
        leading=12,
        textColor=muted,
    ))
    styles.add(ParagraphStyle(
        name="InvoiceWhite",
        parent=styles["InvoiceBody"],
        textColor=colors.white,
    ))
    styles.add(ParagraphStyle(
        name="InvoiceWhiteRight",
        parent=styles["InvoiceWhite"],
        alignment=TA_RIGHT,
    ))
    styles.add(ParagraphStyle(
        name="InvoiceWhiteEyebrow",
        parent=styles["InvoiceEyebrow"],
        textColor=colors.HexColor("#D7F0F8"),
    ))
    styles.add(ParagraphStyle(
        name="InvoiceTotalLabel",
        parent=styles["InvoiceWhite"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
    ))
    styles.add(ParagraphStyle(
        name="InvoiceTotal",
        parent=styles["InvoiceWhiteRight"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=18,
    ))
    styles.add(ParagraphStyle(
        name="InvoiceFooter",
        parent=styles["InvoiceSmallMuted"],
        alignment=TA_CENTER,
        fontSize=7.5,
        leading=10,
    ))

    asset_root = Path(__file__).resolve().parents[1] / "static"
    logo_path = asset_root / "logo.jpg"
    tiqet_logo_path = asset_root / "powered-by-tiqet.png"

    stream = io.BytesIO()
    document = SimpleDocTemplate(
        stream,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=15 * mm,
        bottomMargin=27 * mm,
        title=f"{title} {number}",
        author=str(issuer.get("trading_name") or issuer.get("legal_name") or "My Nanny"),
    )

    def decorate_page(canvas, doc):
        width, height = A4
        canvas.saveState()
        canvas.setFillColor(cream)
        canvas.rect(0, 0, width, height, stroke=0, fill=1)
        canvas.setFillColor(colors.HexColor("#DDF1F8"))
        canvas.circle(-8 * mm, height - 12 * mm, 34 * mm, stroke=0, fill=1)
        canvas.setFillColor(colors.HexColor("#F8DED8"))
        canvas.circle(width + 2 * mm, height + 1 * mm, 23 * mm, stroke=0, fill=1)
        canvas.setFillColor(colors.HexColor("#F6E8BE"))
        canvas.circle(width - 17 * mm, height - 6 * mm, 4 * mm, stroke=0, fill=1)
        canvas.setStrokeColor(line)
        canvas.setLineWidth(0.7)
        canvas.line(16 * mm, 24 * mm, width - 16 * mm, 24 * mm)
        canvas.setFillColor(muted)
        canvas.setFont("Helvetica", 7.5)
        canvas.drawString(16 * mm, 15.5 * mm, "MY NANNY  |  PLACEMENT SUPPORT MADE PERSONAL")
        if tiqet_logo_path.exists():
            canvas.drawImage(
                str(tiqet_logo_path),
                width - 57 * mm,
                7.5 * mm,
                width=41 * mm,
                height=14.8 * mm,
                preserveAspectRatio=True,
                mask="auto",
            )
        canvas.restoreState()

    story: list[Any] = []

    logo = (
        Image(str(logo_path), width=61 * mm, height=23 * mm)
        if logo_path.exists()
        else Paragraph("<b>My Nanny</b>", styles["InvoiceCardTitle"])
    )
    document_heading = Table(
        [
            [Paragraph(title, styles["InvoiceTitle"])],
            [Paragraph(html.escape(str(number or "DRAFT")), styles["InvoiceNumber"])],
        ],
        colWidths=[78 * mm],
        style=TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]),
    )
    header = Table(
        [[logo, document_heading]],
        colWidths=[92 * mm, 86 * mm],
        cornerRadii=[7 * mm] * 4,
        style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.white),
            ("BOX", (0, 0), (-1, -1), 0.7, line),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (0, 0), 7 * mm),
            ("RIGHTPADDING", (-1, 0), (-1, 0), 7 * mm),
            ("TOPPADDING", (0, 0), (-1, -1), 6 * mm),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6 * mm),
        ]),
    )
    story.append(header)
    story.append(Spacer(1, 7 * mm))

    issuer_address = "<br/>".join(
        html.escape(line_value) for line_value in _address_lines(issuer.get("address"))
    )
    issuer_lines = [
        f"<font name='Times-Bold' size='15'>{html.escape(str(issuer.get('legal_name') or 'My Nanny'))}</font>",
        issuer_address,
        html.escape(str(issuer.get("email") or "")),
        html.escape(str(issuer.get("phone") or "")),
    ]
    if issuer.get("registration_number"):
        issuer_lines.append(f"Registration: {html.escape(str(issuer['registration_number']))}")
    if issuer.get("vat_registered"):
        issuer_lines.append(f"VAT: {html.escape(str(issuer.get('vat_number') or ''))}")
    customer_lines = [
        "<font name='Times-Bold' size='15'>Bill to</font>",
        f"<b>{html.escape(str(customer.get('name') or ''))}</b>",
        html.escape(str(customer.get("email") or "")),
        html.escape(str(customer.get("phone") or "")),
    ]

    def info_card(content: Paragraph, width: float, background=colors.white) -> Table:
        return Table(
            [[content]],
            colWidths=[width],
            cornerRadii=[6 * mm] * 4,
            style=TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), background),
                ("BOX", (0, 0), (-1, -1), 0.7, line),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 5 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5 * mm),
            ]),
        )

    issuer_card = info_card(
        Paragraph("<br/>".join(filter(None, issuer_lines)), styles["InvoiceBody"]),
        61 * mm,
    )
    customer_card = info_card(
        Paragraph("<br/>".join(filter(None, customer_lines)), styles["InvoiceBody"]),
        61 * mm,
        blue_pale,
    )
    detail_content = "<br/>".join([
        "<font color='#D7F0F8' size='7'><b>DATE</b></font>",
        f"<b>{document_date.strftime('%d %B %Y') if document_date else '-'}</b>",
        "",
        "<font color='#D7F0F8' size='7'><b>PLACEMENT</b></font>",
        f"<b>PP-{invoice.permanent_placement_id}</b>",
    ])
    details_card = Table(
        [[Paragraph(detail_content, styles["InvoiceWhiteRight"])]],
        colWidths=[50 * mm],
        cornerRadii=[6 * mm] * 4,
        style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), blue_dark),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5 * mm),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5 * mm),
            ("TOPPADDING", (0, 0), (-1, -1), 5 * mm),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5 * mm),
        ]),
    )
    story.append(Table(
        [[issuer_card, "", customer_card, "", details_card]],
        colWidths=[61 * mm, 3 * mm, 61 * mm, 3 * mm, 50 * mm],
        style=TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]),
    ))
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph("YOUR SERVICE", styles["InvoiceEyebrow"]))
    story.append(Spacer(1, 2.5 * mm))

    rows = [[
        Paragraph("<b>Description</b>", styles["InvoiceBody"]),
        Paragraph("<b>Amount</b>", styles["InvoiceBodyRight"]),
    ]]
    for item in line_items:
        rows.append([
            Paragraph(html.escape(str(item.get("description") or "Service")), styles["InvoiceBody"]),
            Paragraph(_money(int(item.get("amount_cents") or 0), invoice.currency), styles["InvoiceBodyRight"]),
        ])
    story.append(
        Table(
            rows,
            colWidths=[128 * mm, 50 * mm],
            repeatRows=1,
            cornerRadii=[5 * mm] * 4,
            style=TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), blue_pale),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ("TEXTCOLOR", (0, 0), (-1, 0), blue_dark),
                ("BOX", (0, 0), (-1, -1), 0.7, line),
                ("LINEBELOW", (0, 0), (-1, 0), 0.7, line),
                ("LINEBEFORE", (1, 0), (1, -1), 0.5, line),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4.5 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5 * mm),
                ("LEFTPADDING", (0, 0), (-1, -1), 5 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5 * mm),
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
    total_flowables = [
        [
            Paragraph(html.escape(str(label)), styles["InvoiceBodyRight"]),
            Paragraph(html.escape(str(amount)), styles["InvoiceBodyRight"]),
        ]
        for label, amount in total_rows[:-1]
    ]
    total_flowables.append([
        Paragraph(html.escape(str(total_rows[-1][0])), styles["InvoiceTotalLabel"]),
        Paragraph(html.escape(str(total_rows[-1][1])), styles["InvoiceTotal"]),
    ])
    totals = Table(
        total_flowables,
        colWidths=[32 * mm, 42 * mm],
        hAlign="RIGHT",
        cornerRadii=[5 * mm] * 4,
    )
    totals.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("BACKGROUND", (0, -1), (-1, -1), blue_dark),
        ("BOX", (0, -1), (-1, -1), 0.7, blue_dark),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5 * mm),
        ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
    ]))
    story.append(totals)
    story.append(Spacer(1, 9 * mm))
    payment_note = (
        "Payment received. Thank you."
        if document_kind == "receipt"
        else "Please use the secure Paystack payment option in your My Nanny placement portal."
    )
    payment_heading = "PAYMENT RECEIVED" if document_kind == "receipt" else "SECURE PAYMENT"
    payment_colour = green if document_kind == "receipt" else coral
    payment_card = Table(
        [[
            Paragraph(payment_heading, ParagraphStyle(
                name=f"InvoicePayment{document_kind}",
                parent=styles["InvoiceEyebrow"],
                textColor=payment_colour,
            )),
            Paragraph(payment_note, styles["InvoiceBody"]),
        ]],
        colWidths=[38 * mm, 140 * mm],
        cornerRadii=[5 * mm] * 4,
        style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.white),
            ("BOX", (0, 0), (-1, -1), 0.7, line),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LINEBEFORE", (1, 0), (1, 0), 3, payment_colour),
            ("LEFTPADDING", (0, 0), (-1, -1), 5 * mm),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5 * mm),
            ("TOPPADDING", (0, 0), (-1, -1), 4 * mm),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * mm),
        ]),
    )
    story.append(payment_card)
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        "This document was generated from the immutable price and customer snapshot stored with the service payment. Contact My Nanny through the app if any detail needs review.",
        styles["InvoiceSmallMuted"],
    ))
    document.build(story, onFirstPage=decorate_page, onLaterPages=decorate_page)
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
