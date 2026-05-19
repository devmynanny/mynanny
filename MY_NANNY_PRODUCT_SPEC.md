# My Nanny Product and Planning Specification

Last updated: 2026-05-19

## 1. Purpose

My Nanny is a South Africa-first childcare booking platform that connects parents with approved nannies. Parents create one-off or recurring booking requests, broadcast those requests to relevant nannies, and manage confirmed bookings. Nannies maintain profiles and availability, review advertised jobs, see estimated earnings, accept or decline requests, and check in/out when working. Admins oversee nanny approvals, pending bookings, manual assignments, pricing, refunds, reporting, and operational exceptions.

This document is intended for planning, export, QA, and identifying loose ends before production hardening.

## 2. Current Stack

- Backend: FastAPI.
- Frontend: static HTML/CSS/JavaScript, no SPA framework.
- Database: SQLite for local/dev (`nanny_app.db`), with a planned Postgres production path.
- Payments: Paystack first.
- Scheduling timezone: `Africa/Johannesburg` (SAST).
- Hosting config: `render.yaml`.
- Primary app entry: [main.py](/Users/daviddiener/Desktop/nanny_app/app/main.py).
- Public/admin router entry: [public.py](/Users/daviddiener/Desktop/nanny_app/app/routers/public.py), [admin.py](/Users/daviddiener/Desktop/nanny_app/app/routers/admin.py).

## 3. User Roles

### Parent

Parents can:

- Sign up and log in.
- Complete family/profile details.
- Add saved booking locations.
- Search for available nannies by location/time/filters.
- Favorite nannies.
- Create booking requests.
- Broadcast booking requests to selected nannies, favorites, or nearby nannies.
- Confirm booking location and required disclaimers.
- View current, upcoming, in-progress, and past bookings.
- Cancel editable bookings where policy allows.
- Confirm nanny check-in/check-out times.
- Review completed bookings.

### Nanny

Nannies can:

- Sign up and log in.
- Complete profile, documents, location, qualifications, languages, tags, and work history.
- Manage availability.
- View booking requests sent to them.
- See booking details before accepting, including schedule, address, client expectations, and estimated earnings.
- Accept, decline, or mark themselves as deciding on a booking request.
- View confirmed duty bookings.
- Check in/out when physically near the booking location.
- Cancel assigned bookings where policy allows.

### Admin

Admins can:

- Log in and access admin screens.
- Review nanny applications.
- Approve, hold, decline, or update nanny status.
- View users, profiles, booking stats, and revenue.
- View pending booking requests and confirmed bookings.
- Approve, reject, cancel, or manually assign booking requests.
- See available nannies for manual assignment sorted by distance and rating.
- Open nanny profiles and contact nannies by WhatsApp/phone where phone numbers exist.
- Manage pricing settings and nanny tags.
- Review refunds and reports.
- View audit logs and operational history.
- Impersonate users for support/debugging.

## 4. Major Screens

### Parent Screens

- [parent_home.html](/Users/daviddiener/Desktop/nanny_app/app/static/parent_home.html): parent landing and booking setup.
- [parent_profile.html](/Users/daviddiener/Desktop/nanny_app/app/static/parent_profile.html): family profile, saved locations, children, and booking form defaults.
- [parent_candidates.html](/Users/daviddiener/Desktop/nanny_app/app/static/parent_candidates.html): nanny search, preview, selection, broadcast, and booking modal.
- [parent_candidates_results.html](/Users/daviddiener/Desktop/nanny_app/app/static/parent_candidates_results.html): candidate search results.
- [parent_favorites.html](/Users/daviddiener/Desktop/nanny_app/app/static/parent_favorites.html): saved nannies.
- [parent_jobs.html](/Users/daviddiener/Desktop/nanny_app/app/static/parent_jobs.html): current jobs, calendar, booking details, check-in/out confirmation.

### Nanny Screens

- [nanny_home.html](/Users/daviddiener/Desktop/nanny_app/app/static/nanny_home.html): nanny dashboard and calendar.
- [nanny.html](/Users/daviddiener/Desktop/nanny_app/app/static/nanny.html): nanny profile.
- [nanny_availability.html](/Users/daviddiener/Desktop/nanny_app/app/static/nanny_availability.html): availability management.
- [nanny_requests.html](/Users/daviddiener/Desktop/nanny_app/app/static/nanny_requests.html): job adverts/booking requests.
- [nanny_history.html](/Users/daviddiener/Desktop/nanny_app/app/static/nanny_history.html): booking history.

### Admin Screens

- [admin_dashboard.html](/Users/daviddiener/Desktop/nanny_app/app/static/admin_dashboard.html): bookings overview, pending requests, manual assignment, admin calendar.
- [admin_user.html](/Users/daviddiener/Desktop/nanny_app/app/static/admin_user.html): user profile and admin controls.
- [admin_pricing.html](/Users/daviddiener/Desktop/nanny_app/app/static/admin_pricing.html): pricing settings.
- [admin_reports.html](/Users/daviddiener/Desktop/nanny_app/app/static/admin_reports.html): operational reports.
- [admin_audit.html](/Users/daviddiener/Desktop/nanny_app/app/static/admin_audit.html): audit logs.
- [admin_tickets.html](/Users/daviddiener/Desktop/nanny_app/app/static/admin_tickets.html): complaints/tickets.
- [admin_integrations.html](/Users/daviddiener/Desktop/nanny_app/app/static/admin_integrations.html): external integrations.
- [admin_invite.html](/Users/daviddiener/Desktop/nanny_app/app/static/admin_invite.html): admin invite acceptance.

## 5. Core Data Model

Important tables/models:

- `users`: account, role, auth, phone, active/admin flags.
- `nannies`: nanny entity linked to user and approval flag.
- `nanny_profiles`: profile details, documents, location, availability context, qualifications/tags/languages.
- `parent_profiles`: parent/family profile and booking form defaults.
- `parent_locations`: saved parent addresses and coordinates.
- `parent_favorites`: parent-to-nanny favorites.
- `nanny_availability`: available and blocked time windows.
- `booking_requests`: parent request/ad/job sent to one nanny, grouped by `group_id` for broadcasts.
- `booking_request_slots`: multi-slot schedule per request.
- `bookings`: confirmed/approved booking days created from requests.
- `reviews`: parent reviews of nannies.
- `pricing_settings`: booking rates, fee percentages, cancellation settings.
- `audit_logs`: operational change history.
- `admin_invites`, `admin_profiles`, `app_settings`.

## 6. Booking Concepts

### Booking Request

A booking request is the advertised job. It can be sent to one nanny or many nannies as separate request rows under a shared `group_id`.

Current statuses include:

- `tbc`: waiting for nanny/admin outcome.
- `pending_admin`: admin attention required.
- `approved`: accepted/confirmed.
- `rejected`: rejected or filled by someone else.
- `cancelled`: cancelled.

### Booking

A booking is an accepted/confirmed scheduled work item. A request may create one or more booking rows, especially for multi-day or recurring schedules.

Current statuses include:

- `approved`
- `accepted`
- `pending`
- `active`
- `in_progress`
- `completed`
- `cancelled`
- `rejected`

### Broadcast Audience vs Required Nanny Count

Broadcast audience size is not the number of nannies required. A parent can broadcast to 2, 5, or 20 nannies while only needing 1 nanny. The booking UI now separates:

- selected/broadcasted nanny list
- `requested_nannies_count`, default `1`

Pricing should use requested count, not broadcast audience size.

## 7. Scheduling and Time Rules

- South African local time (`Africa/Johannesburg`) is the canonical business timezone for scheduling UX.
- User-facing date/time displays should render in SA time.
- Datetimes are persisted in ISO/UTC-compatible forms where possible.
- Naive timestamps should be treated carefully and normalized consistently.
- Full-day availability must represent a local South African day and not shift accidentally due to browser timezone.

Current categorization:

- Upcoming: not terminal, not in progress, and start time is in the future.
- In progress: nanny checked in but not checked out, or current time is between start/end.
- Past: terminal status (`cancelled`, `rejected`, `completed`) or end time has passed.

## 8. Availability Rules

- Availability rows can be `available` or `blocked`.
- A nanny must have availability overlapping the requested windows.
- Blocked windows override availability.
- Existing active bookings block overlapping jobs.
- A 5-hour pre-booking hold applies before an active booking.
- The 5-hour hold does not apply when the new request is from the same parent.
- A nanny should not be able to accept an advert whose start time has already passed.

## 9. Location Rules

- Parent saved location is required for matching and duty operations.
- Parent must confirm the booking location before submitting a booking.
- Booking and request records should retain location references and booking rows should keep lat/lng/address snapshots.
- Nanny check-in/check-out requires location within 100 meters of the booking location.
- If booking location is missing, nanny duty actions can fail or show warnings.

## 10. Pricing and Earnings

Pricing is computed from:

- weekday/weekend/public holiday day rates
- half/full day duration rules
- over-9-hour surcharge
- after-17:00 surcharge
- sleepover rates and sleepover extensions
- extra child surcharge
- agency booking fee percentages

Parent-facing total includes wage plus booking fee.

Nanny-facing earnings should show approximate wage/earnings before acceptance:

- before acceptance: `Estimated earnings after agency booking fee`
- after acceptance: `Total earnings after agency booking fee`

Current implementation uses `wage_cents`/`daily_wage_cents` from booking requests for nanny display.

## 11. Parent Booking Flow

1. Parent completes profile and location.
2. Parent chooses schedule: single or recurring/multi-slot.
3. Parent searches for nannies by time/location or uses selected/favorite/nearby broadcast.
4. Parent opens booking modal.
5. Parent confirms location and required disclaimers.
6. Parent enters requested nanny count.
7. App estimates price.
8. Parent submits booking/broadcast.
9. Booking requests are created with status `tbc`.
10. Admin sees them in pending requests.
11. Nannies receive/view adverts.
12. First accepted/approved result becomes confirmed booking, with sibling requests rejected/filled as appropriate.

## 12. Nanny Request Flow

1. Nanny opens booking requests.
2. Nanny sees schedule, location, client expectations, estimated earnings, and map links.
3. Nanny can accept, decline with reason, or mark deciding.
4. If accepting:
   - API validates request status.
   - API validates booking window is not in the past.
   - API validates availability.
   - Booking rows are created/updated.
   - Related conflicting pending requests may be marked filled/rejected.
   - Calendar sync may be attempted.
5. Accepted bookings move to nanny calendar/duty context.

## 13. Admin Manual Assignment Flow

1. Admin opens a pending or existing booking request.
2. Admin selects manual assignment.
3. System loads available nannies within 30 km.
4. Candidates are filtered by active/approved status, distance, and availability for all selected slots.
5. Candidates are sorted closest to furthest, then by rating/review count.
6. Admin can view profile, WhatsApp, or call the nanny.
7. Admin selects nanny and supplies reason.
8. System validates availability again.
9. System updates request/booking assignment.
10. System notifies parent/new nanny and previous nanny when relevant.

## 14. Admin Dashboard Booking Buckets

- Pending requests: request rows with `tbc` or `pending_admin`.
- Bookings tomorrow: confirmed live bookings whose earliest local start date is tomorrow.
- Upcoming bookings: confirmed live bookings whose group is future scheduled.
- In-progress bookings: confirmed live bookings currently underway.
- Past bookings: completed/ended bookings.
- Cancelations: cancelled requests/bookings.
- Unsuccessful bookings: rejected/cancelled without successful booking.

## 15. Integrations

### Google Maps

- Used for geocoding/reverse geocoding and map/location UX.
- Config endpoint: `/config/google-maps`.
- Admin integration config exists for Google Maps keys.

### Google Calendar

- Confirmed bookings can sync to Google Calendar.
- Calendar sync stores event ID/status fields on booking rows.

### Paystack

- Paystack service and webhook exist.
- Current production readiness should be reviewed before relying on real payments.

### Email/Notifications

- Utility email functions exist.
- Notifications are used for booking responses, reassignment, overdue unaccepted requests, and admin events.

## 16. Security and Permissions

- Cookie-based auth with CSRF handling in frontend helper.
- Roles: parent, nanny, admin.
- Admin-only endpoints use admin guards.
- Some legacy compatibility paths exist.
- Admin impersonation is available and should be tightly controlled/audited.
- Text fields use contact-info redaction in important booking notes/profile paths.

## 17. Known Current Shortcomings

### Product and UX

- The app has many static HTML pages with duplicated formatting and business logic.
- Some flows require manual page refresh after actions.
- Some admin/nanny/parent screens use different date parsing helpers.
- Booking status labels are not fully normalized across all screens.
- Error handling is functional but not always polished for non-technical users.
- Manual assignment contact actions depend on phone data quality.
- Some nannies may lack complete profiles, phone numbers, documents, or coordinates.

### Booking and Scheduling

- Multi-nanny requested count is partly represented via notes/request payload, but not yet as a dedicated database column.
- Broadcast groups represent multiple request rows, but product policy for needing more than one nanny requires fuller acceptance logic.
- Past adverts are blocked at accept time, but expired adverts may still need UI hiding/cleanup policies.
- Timezone handling has improved, but a full audit is still needed across all static pages and backend datetime comparisons.
- Existing data may contain missing locations or older naive timestamps.

### Data Model

- SQLite schema migrations are handled through custom `ensure_*_schema` functions, which is workable locally but fragile for production.
- There is no Alembic migration system yet.
- Some important operational concepts are encoded in notes rather than structured columns.
- Booking request and booking status values are string-based and spread across many flows.

### Payments and Finance

- Payment status exists, Paystack webhook exists, and refund flows exist, but full payment lifecycle needs end-to-end production QA.
- Nanny earnings display is based on computed wage snapshots; final reconciliation after extra hours/check-out confirmation needs policy review.
- Refund, cancellation, company retained, nanny retained, and paid-at fields need clear accounting documentation.

### Admin Operations

- Admin manual assignment is powerful but needs strong audit review and clear user notifications.
- Admin dashboard grouping logic is complex and should have automated tests.
- Reports likely need reconciliation against payments, refunds, cancellations, and booking states.

### Testing

- Current test coverage is minimal.
- Critical flows needing tests:
  - parent booking creation
  - broadcast to selection/favorites/nearby
  - requested nanny count vs broadcast audience count
  - nanny accept/decline/deciding
  - past booking accept rejection
  - admin manual assignment
  - availability overlap and 5-hour buffer
  - check-in/out geofence
  - payment/refund lifecycle
  - timezone display and local-day availability

## 18. Production Readiness Checklist

- Add real migration tooling, ideally Alembic.
- Move production database to Postgres.
- Define canonical status enum/state machine.
- Add structured `requested_nannies_count` column.
- Add cleanup/archive policy for expired pending adverts.
- Add UI hiding/labeling for expired adverts.
- Complete timezone audit across all pages.
- Add automated tests for booking, assignment, availability, payments, and duty actions.
- Verify Paystack integration in sandbox and production modes.
- Verify Google Maps and Google Calendar failure behavior.
- Strengthen admin impersonation audit visibility.
- Add monitoring/logging for failed notifications and payment webhooks.
- Review POPIA/privacy handling for IDs, documents, family photos, and location data.
- Add backup/restore plan for production database and uploaded documents.
- Decide support process for disputes, late arrivals, extra hours, cancellations, refunds, and no-shows.

## 19. Suggested Milestones

### Milestone 1: Stabilize Booking Core

- Normalize status lifecycle.
- Add tests for booking creation, broadcast, accept/decline, admin assignment.
- Add structured requested nanny count in database.
- Hide or expire stale/past adverts in nanny UI.

### Milestone 2: Production Data and Payments

- Add Alembic migrations.
- Move to Postgres.
- Complete Paystack sandbox test plan.
- Document refund/cancellation accounting.
- Add payment reconciliation report.

### Milestone 3: Operational Trust

- Finalize admin workflows.
- Add notification reliability checks.
- Improve support/audit screens.
- Add document/privacy review.
- Add monitoring and backup plan.

### Milestone 4: UX Consistency

- Consolidate shared frontend date/time helpers.
- Standardize status labels and empty states.
- Polish parent/nanny/admin dashboards.
- Improve mobile layouts for modal-heavy workflows.

## 20. Open Product Questions

- When a parent requests more than one nanny, should the platform allow multiple acceptances up to that count?
- Should admin choose winners manually, or should acceptance automatically fill the first available slot(s)?
- Should parents pay before broadcast, after admin approval, or after nanny acceptance?
- Should nannies see parent phone/address before acceptance, or only after acceptance?
- How long should pending adverts remain visible before expiring?
- Should expired adverts auto-reject or move to an admin attention bucket?
- What is the official policy for late check-out, extra hours, and parent confirmation disputes?
- What is the official cancellation/refund policy by time window?
- Should manual admin reassignment notify all previously broadcasted nannies?
- Which documents are required before a nanny can be searchable/bookable?

## 21. Immediate Loose Ends From Recent Work

- Commit/push the recent code changes when ready:
  - past advert accept guard
  - manual assignment profile/WhatsApp/call actions
  - nanny estimated earnings before accept
- Decide whether fake local nanny phone numbers should remain local-only test data.
- Add a real location to all manually created local test bookings.
- Add UI logic to hide or label expired adverts.
- Add tests for the new accept guard and earnings visibility.

