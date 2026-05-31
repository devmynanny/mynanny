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

## 3A. Onboarding Question Inventory

This section lists the questions/fields currently asked during account creation, profile completion, booking setup, and nanny onboarding. Some questions are asked directly during signup; others are asked shortly after signup as part of profile completion or the first booking flow.

### Shared Account Signup Questions

Asked on the create account screen:

- Role: `I'm a parent` or `I'm a nanny`.
- Name: full name.
- Email.
- Password.

### Parent Onboarding Questions

Parent account creation is currently light; most parent onboarding happens on the parent profile, saved-location, and booking setup screens.

Parent profile questions:

- Phone number.
- Kids count.
- Kids ages: years and/or months for each child.
- What matters most in a nanny?
- Home language.
- Special notes.
- Family photo.
- Type of residence:
  Open residential street, gated community, or access required.
- How should the nanny gain access or let you know they have arrived?

Parent saved-location questions:

- Address.
- Use current location? This captures current coordinates and reverse-geocoded address.
- Location label:
  Home, Work, or Other.
- Make this my default?

Parent booking setup questions:

- Is this a booking or another request type?
- Booking date/schedule.
- Repeat booking on which days?
- Repeat until which date?
- Arrival time.
- Finishing time.
- Sleepover required?
- Booking address choice:
  Default home address or different saved address.
- Confirm this is the correct location.
- How many nannies do you need?
- Notes for the nanny.

Parent booking form/questions shown to the nanny and admin:

- What will the nanny be responsible for?
- Will you or another adult be present at the chosen address during the booking?
  Options: I will be present, another adult will be present, no adult will be present.
- What is the reason for your booking?
- How many kids will be present during the booking?
- Should the nanny provide their own meal during the booking?
  Options: we will provide food, we will provide basics like bread/spread/coffee/tea, or nanny must provide her own meals.
- Are there certain foods not allowed in your home?
- Do you have dogs? Specify the breed.
- Basic upkeep disclaimer:
  Parent confirms that the nanny is not expected to do whole-family laundry or full-house cleaning, but basic upkeep related to the child is acceptable.
- Medicine disclaimer:
  Parent confirms nannies cannot be held accountable for medicine administration unless written instructions and consent are provided.
- Additional-hours disclaimer:
  Parent confirms extra hours will be charged if the nanny works longer than stated.
- After-17:00 transport disclaimer:
  Parent agrees to help the nanny get safely home if work ends after 17:00/18:00 according to the stated policy.

Parent search/filter questions:

- Only favourites?
- Rated only?
- Distance range.
- Areas of experience.
- Qualifications.
- Languages.
- Job type.
- Driver's license requirement.
- Transport preference: own car or public transport.
- Dogs in the home:
  small dogs, calm big dogs, pitbull/rottweiler, or no dogs.

### Nanny Onboarding Questions

Nanny signup asks more initial questions than parent signup because approval depends on identity, eligibility, and profile details.

Nanny signup questions:

- Phone number.
- Alternative phone number.
- Gender.
- Nationality.
- Race.
- Passport number, if not South African.
- Passport expiry date.
- Passport copy upload.
- South African ID number, if South African.
- Copy of ID upload.
- Do you have a valid permit?
  Options: yes, waiver, receipt, or no permit.
- Work permit expiry.
- Work permit copy upload.
- Do you have your own car?
- Do you have a driver's license?
- Job type:
  Stay in, stay out, or both.
- Do you have police clearance?
- Do you have your own kids?
- If yes, how old are they and where do they stay?
- Do you have any medical conditions or chronic medications?
- Have you done training with My Nanny?

Nanny profile completion questions:

- Profile photo.
- Full name.
- Phone number.
- Alternative phone number.
- Gender.
- Date of birth.
- Race.
- Do you have your own car?
- Do you have a driver's license?
- Job type:
  Stay in, stay out, or both.
- Have you done training with My Nanny?
- Are you currently available for jobs?
  Options: piece jobs and permanent, unavailable for now, piece jobs only, permanent jobs only.
- Bio, currently present but hidden/temporary.
- Do you have your own kids?
- If yes, how old are they and where do they stay?
- Do you have any medical conditions or chronic medications?
- Nationality.
- Passport number.
- Passport expiry date.
- Passport copy upload.
- South African ID number.
- Copy of ID upload.
- Permit/waiver/receipt status.
- Waiver, if no permit.
- Permit/waiver/receipt copy upload.
- Police clearance/criminal check upload.
- Home address.
- Use current location?
- Languages.
- Driver's license document upload.
- Certificates upload.

Nanny previous-job/reference questions:

- Role.
- Employer/family.
- Period.
- What kind of care did you provide for this family?
  Options include childcare for toddlers, infant care, elderly care, domestic house cleaning, and disability care.
- If childcare/infant care: how old were the kids when you started?
- If disability care: what was the disability?
- Reference name.
- Reference phone.
- Relationship.
- Written reference upload.

Nanny availability questions:

- Ready for bookings / inactive toggle.
- Weekly start date.
- Number of weeks.
- Weekdays available/unavailable.
- Start time.
- End time.
- Availability type:
  available or unavailable/blocked.
- Calendar selection:
  available, unavailable, cancel.

Admin-completed or admin-locked nanny onboarding fields:

- Qualifications.
- Areas of experience.
- Preference with dogs:
  I prefer small dogs, any dog is fine, not pitbulls or rottweilers, or no dogs.
- Studying details, when the `Studying` qualification is selected.
- Application status:
  approved, declined, hold, or pending.
- Admin reason for hold/decline/manual decision.

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

- Utility email functions exist in the backend.
- Current notification delivery is mostly email-based, with some WhatsApp support for check-in notifications.
- Notification sending is trigger-driven inside route handlers rather than managed through a central notification table, queue, or scheduler.

### Current Notification Trigger Matrix

| Event | Trigger in product flow | Recipient(s) | Current behavior |
| --- | --- | --- | --- |
| New booking request created | Parent creates a direct/legacy booking request | Requested nanny and admins | Sends "New booking request" email with booking/request details and admin link. |
| Admin assigns replacement after rejection | Admin rejects original request and assigns another nanny | Parent, replacement nanny, admins | Sends reassignment/update emails and creates/updates the request path. |
| Admin manually reassigns a booking | Admin manually assigns/reassigns a booking request | Parent, previous nanny, new nanny | Parent is told the booking was updated; previous nanny is told it was removed; new nanny is told it was assigned. |
| Nanny accepts, declines, or marks deciding | Nanny responds to a booking request | Parent and admins | Sends nanny response email with request ID, time window, and response note. |
| Pending request not accepted within 6 hours | Admin pending/list/detail/overview checks mark old pending requests | Admins | Sends one overdue email and stamps the request as notified. This is not currently a background job. |
| Nanny cancels a booking | Nanny cancellation endpoint | Admins | Sends admin alert saying admin attention is required before contacting the client. |
| Nanny checks in | Nanny check-in endpoint | Parent | Sends email and/or WhatsApp depending on parent notification preferences, with fallback attempts. |
| Parent denies nanny check-in/check-out time | Parent denies reported arrival/completion time | Admins | Sends admin email requiring manual review. |
| Admin invite created | Admin creates invitation | Invited admin email | Sends invite email with signup path. |

### Notification Gaps

- There is no single notification policy table that defines every trigger, recipient, channel, template, fallback, and retry rule.
- There is no in-app notification center yet.
- There is no durable notification log for delivery status, retries, or failed messages.
- Overdue unaccepted booking alerts are triggered when admin routes are viewed, not by a scheduled worker.
- Parent/admin cancellation, refund approval/denial, payment success/failure, profile approval, document rejection, and booking completion notifications need a formal trigger decision.
- WhatsApp is not yet a fully generalized notification channel across all critical events.

## 15A. Cancellation and Refund Policy in Code

The app already has cancellation and refund behavior in code, but the business policy still needs to be written clearly for parents, nannies, and admins.

### Current Parent Cancellation Behavior

- Parents can cancel their own booking request/group with a required cancellation reason.
- Past jobs cannot be cancelled by the parent cancellation endpoint.
- If a nanny has already accepted the booking and the booking is inside the configured cancellation window, the parent is blocked with a message to contact support.
- If a paid booking is cancelled, the request is marked for refund review.
- Current refund retention calculation:
  - Inside fee window: company retains 100% of the booking fee and nanny retains 40% of wage.
  - Outside fee window: company retains 80% of the booking fee and nanny retains 0% of wage.
  - Refund amount is calculated as total paid minus retained amounts.

### Current Admin Cancellation Behavior

- Admin can cancel a booking request/group with a required reason.
- Related booking rows are cancelled.
- Admin-blocked availability created for the request is cleared.
- Paid cancellations use the same retained/refund calculation as parent cancellation.
- Refunds are placed into `pending_review` before admin approval/denial.

### Current Nanny Cancellation Behavior

- Nannies can cancel their own active/upcoming booking with a required reason unless the booking is already completed, cancelled, or rejected.
- The related booking request is also marked cancelled.
- Admins are notified that admin attention is required before the client is contacted.
- The nanny cancellation path does not yet define a parent refund/credit outcome or nanny penalty policy.

### Current Refund Review Behavior

- Admin can list refund review items.
- Admin can approve a refund, which calls Paystack refund creation when a transaction reference exists.
- Admin can deny a refund with a reason.
- Paystack webhook handling updates refund status for processed/failed refund events.

### Cancellation Policy Gaps

- The user-facing cancellation policy is not documented yet.
- The configured cancellation window is inconsistent in code: database/admin defaults use 12 hours in places, while public cancellation logic enforces a minimum of 15 hours.
- The product needs a clear rule for who may cancel, at what time, what fees apply, what the nanny earns, what the agency retains, and what the parent receives.
- Nanny cancellation consequences are not fully defined.
- No-show, late arrival, parent denial of times, extra hours, illness, emergency, and same-day dispute policies still need operational rules.

## 16. Security and Permissions

- Cookie-based auth with CSRF handling in frontend helper.
- Roles: parent, nanny, admin.
- Admin-only endpoints use admin guards.
- Some legacy compatibility paths exist.
- Admin impersonation is available and should be tightly controlled/audited.
- Text fields use contact-info redaction in important booking notes/profile paths.

## 16A. POPIA and Sensitive Data Position

The app collects high-sensitivity personal information, including SA ID numbers, passport numbers, identity/passport documents, family photos, addresses, location coordinates, child/family details, and medical condition information. POPIA compliance is therefore a launch requirement, not a nice-to-have.

### Current Technical Controls Already Present

- Role-based access exists for parent, nanny, and admin endpoints.
- Admin-only endpoints are guarded.
- Cookie auth and CSRF handling are present in the frontend helper.
- SA ID numbers are validated for format/checksum/date in nanny onboarding/profile flows.
- Contact details are redacted from several free-text booking/profile fields to discourage off-platform contact sharing.
- Approved nanny profile policy locks key identity fields from casual editing.
- Uploaded family photos and nanny identity/passport documents are stored as uploaded file URLs.
- Audit logging exists for important admin/user actions in several flows.

### POPIA Gaps Before Launch

- There is no documented privacy notice and consent flow covering what data is collected, why, how long it is kept, and who receives it.
- There is no retention/deletion policy for ID documents, passport documents, family photos, medical information, old bookings, chat/notes, and audit records.
- There is no documented data subject request process for access, correction, export, deletion, or objection.
- There is no documented breach response process.
- There is no production storage policy for encryption at rest, private document access, backups, and document expiry.
- There is no access minimization policy for which admin roles may view sensitive documents and medical/family information.
- There is no operator/third-party processing register for Paystack, Google, email/SMTP, WhatsApp, hosting, backups, or analytics.
- There is no explicit parental/child data policy, even though child/family details may be stored.
- The current implementation should be treated as partial technical groundwork, not POPIA compliance.

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
- Cancellation rules exist in code but need a signed-off business policy and user-facing wording.

### Admin Operations

- Admin manual assignment is powerful but needs strong audit review and clear user notifications.
- Admin dashboard grouping logic is complex and should have automated tests.
- Reports likely need reconciliation against payments, refunds, cancellations, and booking states.
- Notification triggers exist in code but need a central policy matrix, delivery logging, and retry handling.

### Compliance

- POPIA-related technical controls exist only partially; launch requires a proper privacy, retention, access, and breach-response plan.

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

## 21. Immediate Loose Ends From Recent Work

- Commit/push the recent code changes when ready:
  - past advert accept guard
  - manual assignment profile/WhatsApp/call actions
  - nanny estimated earnings before accept
- Decide whether fake local nanny phone numbers should remain local-only test data.
- Add a real location to all manually created local test bookings.
- Add UI logic to hide or label expired adverts.
- Add tests for the new accept guard and earnings visibility.

## 22. Product Decisions Implemented (May 31, 2026)

- Task 9 completed: suspension and document enforcement in search and booking.
- Search eligibility now requires all of the following:
  - nanny is approved
  - nanny is not suspended
  - nanny profile meets document requirements
- Booking acceptance now blocks:
  - suspended nanny accounts (403)
  - nanny profiles that do not meet document requirements (403)
- Admin approval now blocks approval when document requirements are incomplete and returns missing fields (400).
- Admin reactivation endpoint implemented:
  - `POST /admin/nannies/{nanny_id}/lift-suspension`
  - required body: `{ "reason": "..." }`
  - clears suspension, records lift timestamp/admin user, sends nanny reactivation notice, logs audit + notification events.

### Searchable/Bookable Document Rule (Current)

- South African nanny:
  - `sa_id_number`
  - `sa_id_document_url`
- Non-South African nanny:
  - `passport_number`
  - `passport_expiry`
  - `passport_document_url`
  - and when `permit_status == "permit"`:
    - `work_permit_expiry`
    - `work_permit_document_url`
