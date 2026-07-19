# Paystack Test Plan (Sandbox → Live)

## Key wiring (do this yourself, never share keys in chat)

Sandbox first:

1. Paystack Dashboard → Settings → API Keys & Webhooks.
2. Copy the TEST secret key (`sk_test_...`).
3. Local: add to `.env`: `PAYSTACK_SECRET_KEY=sk_test_...`
4. Render (staging): Environment → add `PAYSTACK_SECRET_KEY` with the test key.
5. Webhook URL in Paystack dashboard (test mode): `https://<your-render-url>/paystack/webhook`

Go-live swap (after this plan passes end to end in sandbox):

1. Complete Paystack business verification (required for ZAR live mode + transfers).
2. Replace `PAYSTACK_SECRET_KEY` on Render with the LIVE secret key (`sk_live_...`).
3. Set the live-mode webhook URL to the same endpoint.
4. Re-run smoke tests 1, 2 and 6 below with a real card and small amounts, then refund yourself.

## Paystack test cards (test mode)

| Card | Number | Behavior |
|---|---|---|
| Success | 4084 0840 8408 4081 | Charges succeed |
| Insufficient funds | 5060 6666 6666 6666 666 | charge_authorization fails |
| Declined | 4084 0800 0000 5408 | Charge declined |

CVV 408, any future expiry, PIN 0000, OTP 123456.

## Test sequence (run in order, staging environment)

### 1. Card capture (parent payment method)
- As a parent: add payment method → `/parent/payment-method/initialize` → complete Paystack checkout with the success card → `/parent/payment-method/verify`.
- PASS: parent has `card_last4`, `card_brand` set; `paystack_auth_code` stored; card shows in parent profile UI.

### 2. Charge on nanny acceptance (core revenue path)
- Parent (with saved card) sends a booking request; nanny accepts.
- PASS: request `payment_status = paid`, `paid_at` set, `paystack_reference` set; booking rows created; nanny availability blocked; parent receives payment_success notification; charge visible in Paystack dashboard with metadata `purpose=booking_acceptance_charge` and correct `booking_request_id`.

### 3. Failed charge on acceptance
- Repeat with a parent whose saved card is the insufficient-funds card.
- PASS: API returns 402; request has `admin_reason = payment_failed`; NO booking rows; parent notified to update card; nothing marked paid.

### 4. Webhook reconciliation
- In Paystack dashboard → resend the charge.success event for test 2's transaction.
- PASS: 200 response; request still `paid` (idempotent). Also send an event with a tampered body: PASS = 400 invalid signature. (Covered by automated tests too.)

### 5. Refund via cancellation
- Parent cancels a paid booking in each policy window (>24h, 15-24h, <15h).
- PASS: retained/refund split matches policy; `create_refund` called with correct amount; refund appears in Paystack dashboard; `refund_status` transitions; admin refund review flow works for the manual-review cases.

### 6. Nanny payout (transfer)
- Nanny adds bank details (`/nanny/banking` with a real bank + test account) → recipient created.
- Complete a booking (check-in/check-out within geofence), wait for payout hold (24h; shorten `payout_hold_hours` in pricing_settings for testing).
- PASS: `run_scheduled_payouts` creates a transfer for wage minus any debt deduction; `payout_released_at` set; transfer visible in dashboard.
  NOTE: test-mode transfers to real banks do not settle; verify via dashboard status only. Transfers in live mode require Paystack balance + business verification.

### 7. Overtime supplementary charge
- Check out late so overrun minutes accrue → parent approves overtime.
- PASS: supplementary charge on saved card for the overrun amount; `overrun_status = charged`.

## Automated coverage already in repo

- Charge on acceptance (success, failure, idempotency, guard rails): tests/test_booking_flow_api.py
- Webhook signature + charge.success reconciliation: tests/test_paystack_webhook.py
- Cancellation outcome calculation: tests/test_cancellation_service.py

## Known gaps to watch in sandbox

- Payout reconciliation report does not exist yet (M2 task, in progress).
- Transfer webhook events (transfer.success / transfer.failed) are not yet
  handled; payout status relies on the scheduled job's synchronous response.
