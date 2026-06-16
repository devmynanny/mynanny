from __future__ import annotations

from datetime import datetime
from sqlalchemy import asc
from sqlalchemy.orm import Session

from app import models


def deduct_debt_from_payout(db: Session, nanny_id: int, payout_cents: int, booking_id: int | None = None) -> dict:
    remaining = max(0, int(payout_cents))
    total_deducted = 0
    deductions = []

    debts = (
        db.query(models.NannyDebt)
        .filter(
            models.NannyDebt.nanny_id == nanny_id,
            models.NannyDebt.status.in_(["active", "partially_paid"]),
            models.NannyDebt.balance_cents > 0,
        )
        .order_by(asc(models.NannyDebt.created_at), asc(models.NannyDebt.id))
        .all()
    )

    for debt in debts:
        if remaining <= 0:
            break
        balance = int(debt.balance_cents or 0)
        if balance <= 0:
            debt.status = "settled"
            continue
        deducted = min(remaining, balance)
        debt.balance_cents = balance - deducted
        debt.status = "settled" if debt.balance_cents <= 0 else "partially_paid"
        debt.updated_at = datetime.utcnow()
        total_deducted += deducted
        remaining -= deducted
        deduction = models.DebtDeductionLog(
            debt_id=debt.id,
            booking_id=booking_id,
            amount_deducted_cents=deducted,
            balance_after_cents=max(0, debt.balance_cents),
        )
        db.add(deduction)
        deductions.append(
            {
                "debt_id": debt.id,
                "amount_deducted_cents": deducted,
                "balance_after_cents": max(0, debt.balance_cents),
            }
        )

    return {
        "net_payout_cents": max(0, int(payout_cents) - total_deducted),
        "total_deducted_cents": total_deducted,
        "deductions": deductions,
    }
