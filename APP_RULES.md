# My Nanny App Rules

This document captures the current business and behavior rules in the app.
It is intended as an operational source of truth for product, support, and engineering.

## 1. Core Context

- Country focus: South Africa.
- Local timezone for scheduling and display: `Africa/Johannesburg` (SAST).
- Backend: FastAPI.
- Frontend: static HTML/CSS/JavaScript.
- Database: SQLite (local/dev), with planned Postgres path for production.

## 2. User Roles

- Parent:
  - Creates and manages booking requests.
  - Chooses booking location.
  - Confirms location and booking disclaimers.
  - Can view/edit own profile and locations.
- Nanny:
  - Manages profile and availability.
  - Accepts/declines booking requests.
  - Sees duty bookings, checks in/out.
- Admin:
  - Reviews users and nannies.
  - Approves/rejects/assigns booking requests.
  - Oversees dashboards and booking operations.

## 3. Scheduling and Time Rules

- App uses South African local time for user-facing scheduling.
- Datetimes are persisted in UTC-compatible form (ISO timestamps) and rendered in SA local time.
- Full-day availability is treated as local-day coverage (not shifted by browser timezone).

## 4. Nanny Availability Rules

- Availability types:
  - `available`
  - `blocked` (unavailable)
- A nanny cannot create duplicate availability entries for the same day and same type.
  - Single create returns conflict if same day/type exists.
  - Weekly/bulk create skips days already containing same day/type.
- Existing blocked windows override availability.
- Booking overlap always makes nanny unavailable for that overlap window.

## 5. Booking Buffer Rule (Pre-Booking Hold)

- If a nanny has an active booking, they are unavailable for the **5 hours before** that booking starts.
- Exception:
  - The 5-hour pre-booking hold does **not** apply when the new booking is from the **same parent/client**.
- This rule is enforced server-side in availability checks used by booking and search flows.

## 6. Booking Request and Booking Rules

- Booking requests use one or more windows (slots).
- A nanny must be available for all requested windows to be bookable.
- Once a nanny accepts/booking is approved, certain edits become locked.
- Booking states used across flows include values like:
  - `tbc`, `pending_admin`, `approved`, `accepted`, `pending`, `active`, `in_progress`, `cancelled`, `rejected`, `completed`.
- Overlap checks prevent conflicting assignments.

## 7. Location Rules

- Parent location is required for matching and booking operations.
- Parent must confirm booking location in booking UI before submission.
- Location confirmation validation appears in UI and blocks submit until confirmed.
- Nanny duty geofence:
  - Nanny check-in is allowed only when within **100 meters** of the booking location.
  - Nanny check-out is allowed only when within **100 meters** of the booking location.
  - If outside the 100m radius, API returns a conflict error and does not record the duty action.

## 8. Profile and Validation Rules

- Input validation is strict on API layer (dates, times, required fields, state transitions).
- Explicit HTTP errors are returned on invalid payloads or business-rule violations.
- Nanny and parent profile completion affects booking/search behavior in parts of the app.

## 9. Calendar and Dashboard Rules

- Nanny home calendar shows current work schedule (upcoming/in-progress context).
- Calendar rendering uses cached API data and can require refresh after state changes.
- Admin overview groups/labels bookings and requests by operational status and time state.

## 10. Operational Safety Rules

- Preserve backward-compatible request/response shapes unless intentionally changed.
- Prefer small safe changes over broad rewrites.
- Auth/security/payment behavior changes should include risk review.

## 11. Known Current Policy Decisions

- One availability entry per day per type per nanny.
- 5-hour pre-booking hold before existing bookings for different parents.
- Same-parent exception for the 5-hour hold.
- South Africa local time is the canonical business time for scheduling UX.

## 12. Change Control

When a rule changes:

- Update this document in the same PR as code changes.
- Add/update tests that enforce the rule.
- Mention migration/cleanup steps if existing data may violate the new rule.
