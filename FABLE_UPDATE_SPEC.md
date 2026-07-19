# My Nanny Update Spec for Fable

Last updated: 2026-07-19

## Purpose

This document summarizes the current product updates and open work for the My Nanny app so it can be uploaded into Fable as a concise planning/spec artifact.

## Launch Decision (2026-07-19)

- Goal: monetize as soon as possible.
- Decision: full spec must be complete before any live paid booking (no partial/soft launch). This is a deliberate scope-over-speed call, not a default.
- Execution mode: Claude has direct read/write access to this repo (`~/Desktop/nanny_app`) and is making code changes directly in this session/thread, rather than producing Codex-ready briefs. File structure is being left alone (no restructuring of `app/routers/public.py`); only behavior is being changed.
- Working cadence: Claude works through the tracked task list autonomously across turns/sessions and checks in at milestone boundaries (M1/M2/M3/M4/final), not after every small task.
- Audit finding that reset expectations: the app was assumed "stalled/possibly broken" (last commit over a month old, 4 tests failing). Root cause of the failing tests was a sandbox filesystem issue (SQLite over a FUSE-mounted folder), not a code bug — all 17 existing tests pass against a real disk. The app is materially closer to launch-ready than the stale git history suggested. The real blockers are: no live Paystack key configured, SQLite still used as the production datastore, and no automated coverage for the booking status/lifecycle logic.

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

Tracked as 14 work items across four milestones, gating full launch. Status as of 2026-07-19:

### Milestone 1: Stabilize Booking Core
- [in progress] Test coverage for core booking flows — started with full characterization test suite for `app/services/booking_status.py` (the read-side status derivation layer), since it had zero prior coverage and any lifecycle refactor needs a safety net first.
- [not started] Normalize booking status lifecycle — investigation found `app/routers/public.py` (10,251 lines) writes raw status strings at 50+ call sites across two different vocabularies (`bookings.status` vs `booking_requests.status`), reconciled only at read-time by `booking_status.py`. Sequencing changed: tests before refactor, to avoid regressions in a payment-connected file.
- [not started] Add structured `requested_nannies_count` column (currently encoded in notes/request payload).
- [not started] Expire/hide stale adverts (cleanup policy + UI hiding for expired pending adverts).

### Milestone 2: Production Data and Payments
- [not started] Alembic migrations (replacing the custom `ensure_*_schema` functions in `app/db.py`).
- [not started] Migrate production DB to Postgres.
- [not started] Paystack sandbox test plan + live key wiring (`.env` currently has no `PAYSTACK_SECRET_KEY` — this is the single hard blocker to taking real payments).
- [not started] Refund/cancellation accounting documentation + payment reconciliation report.

### Milestone 3: Operational Trust
- [not started] WhatsApp/Twilio notification reliability (policy matrix, delivery logging, retry handling).
- [not started] Admin operational trust: audit visibility, monitoring/logging for failed notifications and payment webhooks, backup/restore plan.
- [not started] POPIA/privacy compliance pass for identity, document, and child data.

### Milestone 4: UX Consistency
- [not started] Consolidate frontend date/time and status helpers (partially started in prior work, per below).
- [not started] Standardize status labels, empty states, and dashboard polish across parent/nanny/admin.

### Final
- [not started] Full walk of the Section 18 Production Readiness Checklist before declaring launch-ready.

## Risks To Keep In Mind

- Auth, document access, and payment flows remain high-risk areas and should keep explicit validation plus audit logging.
- Timezone handling must stay anchored to South African local time for user-facing booking behavior.
- Cancellation and refund rules should stay consistent across backend, admin UI, and user-facing screens.

## Notes For Fable

- This is a compact current-state/spec update, not the full historical product spec.
- If you need the deeper planning reference, use `MY_NANNY_PRODUCT_SPEC.md` as the source of truth for the full system overview.
