# My Nanny Update Spec for Fable

Last updated: 2026-06-13

## Purpose

This document summarizes the current product updates and open work for the My Nanny app so it can be uploaded into Fable as a concise planning/spec artifact.

## Product Snapshot

My Nanny is a South Africa-first childcare booking platform built with:

- Backend: FastAPI
- Frontend: static HTML/CSS/JavaScript
- Database: SQLite locally today, with a planned Postgres production path
- Payments: Paystack first
- Primary timezone: `Africa/Johannesburg`

## Recent Implemented Updates

### Booking and request enforcement

- Past advert acceptance is blocked.
- Booking quantity is now treated separately from broadcast audience size.
- Booking request and booking state handling has been tightened to reduce inconsistent transitions.

### Suspension and document enforcement

- Nanny search eligibility now requires:
  - approved status
  - no active suspension
  - required document completeness
- Booking acceptance blocks suspended nannies.
- Booking acceptance blocks nannies whose required documents are incomplete.
- Admin approval now rejects incomplete document submissions and returns the missing fields.
- Admin can lift a suspension through a dedicated reactivation flow with audit logging and a nanny notification.

### Cancellation and refund behavior

- Parent cancellation now applies policy-based restrictions.
- Admin cancellation uses the same retained/refund calculation path as parent cancellation.
- Nanny cancellations notify admins that manual attention is needed.
- Refund review is supported through admin approval/denial flow.

### Payout and demerit support

- The codebase now includes service-level support for cancellation handling, demerit tracking, payout logic, and Paystack-related refund behavior.
- Tests have been added for cancellation and demerit service behavior.

### Frontend helper consolidation

- Shared frontend helper logic has started moving into a safer common path to reduce duplicated date/time and state-handling behavior.

## Current Product Areas

### Parent

- Sign up, profile setup, saved locations, search, favorites, booking requests, booking management, cancellations, and confirmations.

### Nanny

- Sign up, profile completion, documents, availability, request review, accept/decline/deciding actions, and duty booking management.

### Admin

- Approvals, holds, declines, manual assignments, pricing, refunds, reports, audit logs, and impersonation/support tools.

## Open Work / Next Updates

- Finish the frontend helper consolidation and remove remaining duplicated logic.
- Add broader automated coverage for booking, assignment, availability, refund, and timezone flows.
- Complete the production migration path from SQLite to Postgres.
- Finalize a clear cancellation/refund policy for parents, nannies, and admins.
- Tighten POPIA/privacy handling for sensitive identity, document, and child data.

## Risks To Keep In Mind

- Auth, document access, and payment flows remain high-risk areas and should keep explicit validation plus audit logging.
- Timezone handling must stay anchored to South African local time for user-facing booking behavior.
- Cancellation and refund rules should stay consistent across backend, admin UI, and user-facing screens.

## Notes For Fable

- This is a compact current-state/spec update, not the full historical product spec.
- If you need the deeper planning reference, use `MY_NANNY_PRODUCT_SPEC.md` as the source of truth for the full system overview.
