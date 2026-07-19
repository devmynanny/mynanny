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

### Milestone 1: Stabilize Booking Core — COMPLETE (2026-07-19)
- [done] Test coverage for core booking flows — 87 tests passing: characterization suite for status derivation, end-to-end API tests (request → accept → charge → booking), 5-hour buffer, 100m geofence, guard rails (suspended/missing docs/failed charge/decline/overlap/idempotency). Test suite now hermetic (temp DB per run, no longer writes into dev DB).
- [done] Normalize booking status lifecycle — central write vocabularies in `booking_status.py`, model-level validators reject rogue status writes on all four status columns. Removed dead legacy routers (`routes_public.py`/`routes_admin.py`) that contained a CHECK-violating status write and marked requests paid without charging.
- [done] Structured `requested_nannies_count` column with legacy notes backfill; exposed in admin API.
- [done] Stale advert expiry — sweep service (30-min scheduler) marks past open adverts rejected/expired; nanny listing hides them between sweeps. Policy documented in APP_RULES.md 6A.
- [done, bonus] Fixed fresh-database bootstrap (duplicate audit index creation broke any clean deploy — would have blocked Postgres).

### Milestone 2: Production Data and Payments — COMPLETE (2026-07-19)
- [done] Alembic migrations — baseline covers all 32 tables; env reads DATABASE_URL; verified on fresh SQLite and rendered as valid Postgres DDL. Day-to-day workflow in DEPLOYMENT.md.
- [done] Postgres production path — engine args dialect-aware, all SQLite-only `ensure_*` gated, 6 runtime `sqlite_master` probes replaced (would have crashed Postgres), render.yaml provisions managed Postgres + runs `alembic upgrade head` preDeploy, FK-safe data-copy script for cutover. Remaining manual step: David deploys and (optionally) copies staging data — runbook in DEPLOYMENT.md.
- [done] Paystack — webhook signature check hardened (constant-time), webhook tests added, PAYSTACK_TEST_PLAN.md gives key-wiring steps and a 7-step sandbox sequence. Remaining manual step: David adds PAYSTACK_SECRET_KEY and runs the sandbox plan.
- [done] Accounting — ACCOUNTING.md (field semantics, A/B/C cancellation splits, invariants, monthly close) + `/admin/accounting/reconciliation` per-booking ledger with integrity problem codes.

### Milestone 3: Operational Trust — COMPLETE (2026-07-19)
- [done] Notification reliability — central NOTIFICATION_POLICY matrix (WhatsApp first, email fallback, mandatory in-app for action-required events), message bodies persisted to notification_log, 15-min retry sweep (3-attempt cap, 48h window), Twilio whatsapp: prefix bug fixed. Remaining manual step: David configures Twilio env vars + WhatsApp Business sender approval (Meta lead time).
- [done] Admin operational trust — impersonation now audit-logged (was completely unaudited) with /admin/ops/impersonations listing; rejected Paystack webhooks audit-logged; /admin/ops/health failure-queue snapshot; BACKUPS.md with restore drill and RPO/RTO.
- [done] POPIA — critical fix: uploaded identity documents were publicly retrievable by URL; now owner/admin-only with middleware enforcement (photos require login). POPIA.md documents data inventory, controls, retention, data subject requests, breach response, and open company-side obligations (Information Officer registration, privacy policy page, express consent checkbox).

### Milestone 4: UX Consistency — COMPLETE (2026-07-19)
- [done] Frontend helpers — date/time consolidation was already complete from prior work (app.js shared ZA helpers on 25/26 pages); added shared `bookingStatusLabel()` map mirroring backend vocabularies and switched parent_jobs/nanny_history/nanny_requests/admin_dashboard to it (raw enum strings no longer shown to users).
- [done, with caveat] Empty states verified present on all main dashboards; viewport meta fixed on nanny.html (live post-signup mobile page). Subjective visual polish needs a browser walkthrough by David — punch-list item in LAUNCH_READINESS.md.

### Final — checklist walked (2026-07-19)
- [done] LAUNCH_READINESS.md: full Section 18 walk. Everything code-side is done; launch now gates on 4 David actions (deploy, Paystack test key + sandbox run, live key swap, production secrets) with 7 non-blocking follow-ups (Twilio/WhatsApp sender approval, POPIA company obligations, support policy wording, restore drill, mobile walkthrough, Maps/Calendar failure verification, staging timezone pass).

## Risks To Keep In Mind

- Auth, document access, and payment flows remain high-risk areas and should keep explicit validation plus audit logging.
- Timezone handling must stay anchored to South African local time for user-facing booking behavior.
- Cancellation and refund rules should stay consistent across backend, admin UI, and user-facing screens.

## Notes For Fable

- This is a compact current-state/spec update, not the full historical product spec.
- If you need the deeper planning reference, use `MY_NANNY_PRODUCT_SPEC.md` as the source of truth for the full system overview.
