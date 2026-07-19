# MyNanny Payment & Refund Accounting

Source of truth for what each money field means, how cancellation splits are
calculated, and how to reconcile the books. All amounts are integer cents (ZAR).

## Money fields on booking_requests

| Field | Meaning | Set when |
|---|---|---|
| wage_cents | Nanny's wage portion for all slots (incl. extra-child surcharge share) | Request creation (pricing snapshot) |
| booking_fee_pct | Company fee percentage applied (0.30 / 0.27 / 0.25 by volume tier) | Request creation |
| booking_fee_cents | Company fee portion | Request creation |
| total_cents | wage_cents + booking_fee_cents = amount charged to parent | Request creation |
| paid_at | When the parent's card was successfully charged | Nanny acceptance (charge_authorization) or webhook |
| paystack_reference / paystack_transaction_id | Paystack charge identifiers | Charge time |
| company_retained_cents | Company's share kept on cancellation | Cancellation |
| nanny_retained_cents | Nanny's compensation kept on cancellation | Cancellation |
| refund_cents | Amount refunded to parent | Refund processing |
| refund_status | requested / processed / denied / failed | Refund lifecycle |
| paystack_refund_reference | Paystack refund identifier | Refund creation |

## Money fields on bookings (per slot/day)

| Field | Meaning |
|---|---|
| payout_amount_cents | Amount released to nanny for this booking |
| payout_debt_deducted_cents | Debt withheld from the payout before release |
| payout_hold_until | Payout released only after this time (default 24h post-completion) |
| payout_released_at | When the transfer to the nanny was executed |
| overrun_amount_cents | Overtime charged to parent after confirmation |
| overrun_status | awaiting_parent / queried / charged / released |

## Cancellation windows and splits

Calculated by `app/services/cancellation.py::calculate_cancellation_outcome`,
symmetric for parents and nannies, keyed on hours until booking start:

| Scenario | Window | Company keeps | Nanny keeps | Parent refund |
|---|---|---|---|---|
| A | > 24h | 0 | 0 | 100% of total |
| B | 15-24h | 50% of booking fee | 0 | remainder |
| C | < 15h | 75% of booking fee | 30% of wage | remainder |

Invariant for every cancelled+refunded request:
company_retained_cents + nanny_retained_cents + refund_cents == total_cents

## Payment failure

Payment failure is NEVER a payment_status value (DB constraint forbids it).
A failed acceptance charge leaves payment_status = pending_payment and sets
admin_reason = "payment_failed". The write guards in the models enforce this.

## Payout invariant

For a completed, non-cancelled booking request:
sum(payout_amount_cents) + sum(payout_debt_deducted_cents) <= wage_cents

Debt deductions are logged in debt_deduction_log and reduce nanny_debt.balance_cents.

## Reconciliation

Admin endpoint: `GET /accounting/reconciliation?range=month[&only_mismatches=true]`

Per paid booking request it emits the full ledger row and a `problems` list:

| Problem code | Meaning |
|---|---|
| paid_with_zero_total | Marked paid but total_cents is 0 - investigate immediately |
| fee_plus_wage_mismatch | booking_fee_cents + wage_cents != total_cents |
| cancel_split_mismatch | Cancellation split + refund does not equal total paid |
| cancelled_paid_but_no_split_recorded | Cancelled after payment but no retention/refund recorded |
| payout_exceeds_wage | Released payout + debt deduction exceeds the wage portion |

Monthly close process:
1. Run the reconciliation report for the month; resolve every problem row.
2. Cross-check payments_processed_cents and refunds_processed_cents in
   `/accounting/summary` against the Paystack dashboard totals for the
   same period.
3. Check payouts_pending_cents for stuck payouts (hold elapsed, not released).
4. Export and archive both reports.

## Related docs

- PAYSTACK_TEST_PLAN.md - sandbox/live verification sequence
- APP_RULES.md section 6 - status vocabularies and enforcement
