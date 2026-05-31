from decimal import Decimal, ROUND_HALF_UP


def _round_to_int(value: float) -> int:
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def calculate_cancellation_outcome(
    total_paid_cents: int,
    wage_cents: int,
    booking_fee_cents: int,
    cancelled_by: str,
    hours_until_start: float,
) -> dict:
    if cancelled_by not in {"parent", "nanny"}:
        raise ValueError("cancelled_by must be 'parent' or 'nanny'")

    total_paid_cents = int(total_paid_cents)
    wage_cents = int(wage_cents)
    booking_fee_cents = int(booking_fee_cents)
    hours_until_start = float(hours_until_start)

    if hours_until_start > 24.0:
        scenario = "A"
        company_retained_cents = 0
        nanny_retained_cents = 0
    elif hours_until_start >= 15.0:
        scenario = "B"
        company_retained_cents = _round_to_int(booking_fee_cents * 0.50)
        nanny_retained_cents = 0
    else:
        scenario = "C"
        company_retained_cents = _round_to_int(booking_fee_cents * 0.75)
        nanny_retained_cents = _round_to_int(wage_cents * 0.30)

    parent_refund_cents = total_paid_cents - company_retained_cents - nanny_retained_cents

    return {
        "parent_refund_cents": parent_refund_cents,
        "nanny_retained_cents": nanny_retained_cents,
        "company_retained_cents": company_retained_cents,
        "scenario": scenario,
        "cancelled_by": cancelled_by,
    }

