# Permanent-placement UAT testing

## Purpose

The permanent-placement smoke test validates the integrated parent, nanny and
administrator workflow against the isolated Render UAT database. It is
destructive by design: every run creates a new clearly labelled Self-Match
placement and completes it using simulated administrator-recorded payments.

The runner refuses any hostname that does not contain `uat` and explicitly
refuses the My Nanny production domains.

## UAT accounts

- Administrator: `uat.admin@mynanny.co.za`
- Parent: `uat.parent@mynanny.co.za`
- Nanny: `uat.nanny@mynanny.co.za`

Passwords are UAT secrets. Supply them only as local environment variables;
never add them to source control, Render logs or this document.

## Prerequisites

- `https://mynanny-uat.onrender.com/health` reports a healthy, isolated UAT
  database.
- Permanent placements are enabled in the UAT administrator screen.
- Billing is invoice-ready. The current UAT configuration is:
  - Legal name: My Nanny (Pty) Ltd
  - Trading name: My Nanny
  - Address: 21 Victoria Cres, Louwlardia, Centurion
  - Billing email: `sayhi@mynanny.co.za`
  - Billing phone: `0813967980`
  - VAT registered: No
- Automated external notifications remain disabled.
- Paystack remains in test mode.

## Running the smoke test

From the repository root, set the three password variables in the current
shell and run:

```bash
python3 scripts/run_uat_permanent_placement_smoke.py
```

Required variables:

- `MYNANNY_UAT_ADMIN_PASSWORD`
- `MYNANNY_UAT_PARENT_PASSWORD`
- `MYNANNY_UAT_NANNY_PASSWORD`

Optional overrides are `MYNANNY_UAT_API`, `MYNANNY_UAT_ADMIN_EMAIL`,
`MYNANNY_UAT_PARENT_EMAIL` and `MYNANNY_UAT_NANNY_EMAIL`.

## What it verifies

1. The UAT health and database isolation gate pass.
2. The three test users can authenticate.
3. The nanny receives a synthetic UAT-only prerequisite profile, is approved,
   and opts into permanent placements.
4. The parent creates a Self-Match brief using the current admin-controlled
   pricing snapshot.
5. The activation, candidate-access and successful-placement fees move through
   their expected states using simulated administrator payment records. The
   script never initializes or verifies a Paystack charge.
6. Admin qualification, nanny consent, protected profile release, shortlist
   and interview invitation all succeed.
7. Candidate identity, contact and address details remain hidden before the
   permitted interview contact window.
8. Both parties accept the contact terms, can message during the interview
   window, and lose direct contact access when the nanny checks in.
9. Interview completion, paid-trial request and acceptance, formal offer and
   nanny acceptance all succeed.
10. A Monday-to-Friday accepted offer blocks the nanny's weekday short-term
    calendar while leaving weekends outside the permanent schedule.
11. The success fee completes the placement and activates the configured
    40-day replacement period.
12. All three Self-Match invoices and receipts receive sequential document
    numbers and download as valid PDF files.

## First recorded UAT result

On 2 September 2026, placement `#1` completed successfully:

- Status: Placed
- Candidate status: Hired
- Offer status: Accepted
- Interview credits: 1 used, 4 available
- Permanent calendar blocks: 260 weekdays
- Replacement cover through: 12 October 2026
- Invoices: `MN-INV-2026-000001` to `MN-INV-2026-000003`
- Receipts: `MN-RCT-2026-000001` to `MN-RCT-2026-000003`
- Candidate privacy check: Passed
- Interview contact lock check: Passed
