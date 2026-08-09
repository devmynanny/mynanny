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
- A user selects either `parent` or `nanny` when creating an account.
- Admin may correct a user who selected the wrong account type.
- Changing a user between parent and nanny must retain the existing account and historical records. Role-incompatible information may be hidden but must not be silently deleted.

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
- Nannies may set availability as individual calendar dates or as a recurring weekly pattern.
- Availability changes may not remove, shorten, or invalidate an existing confirmed or in-progress booking.
- Existing bookings remain protected even when the nanny clears availability or changes a weekly pattern.
- Calendar interfaces must visually distinguish today's date from availability and booking indicators.

## 5. Booking Buffer Rule (Pre-Booking Hold)

- If a nanny has an active booking, they are unavailable for the **5 hours before** that booking starts.
- Exception:
  - The 5-hour pre-booking hold does **not** apply when the new booking is from the **same parent/client**.
- This rule is enforced server-side in availability checks used by booking and search flows.

## 6. Booking Request and Booking Rules

- Booking requests use one or more windows (slots).
- A nanny must be available for all requested windows to be bookable.
- Once a nanny accepts/booking is approved, certain edits become locked.
- Status vocabularies are centrally defined in `app/services/booking_status.py` and enforced on every write by model-level validators (rogue values raise immediately):
  - `booking_requests.status`: `tbc`, `pending_admin`, `approved`, `rejected`, `cancelled` (mirrors DB CHECK).
  - `bookings.status`: `pending`, `approved`, `accepted`, `active`, `in_progress`, `admin_review`, `awaiting_overtime_approval`, `completed`, `cancelled`.
  - `booking_requests.nanny_response_status`: `pending`, `accepted`, `declined`, `deciding`.
  - `booking_requests.payment_status`: `pending_payment`, `paid`, `cancelled`. Payment failure is expressed via `admin_reason = "payment_failed"`, never via `payment_status`.
- Display states are derived read-side by `booking_state_from_booking` / `booking_state_from_request` (canonical states like `awaiting_acceptance`, `awaiting_payment`, `confirmed`, `in_progress`, `completed`, `past`, `cancelled`).
- Overlap checks prevent conflicting assignments.

## 6A. Advert Expiry Rules

- An open booking-request advert (status `tbc` or `pending_admin`, not accepted by a nanny) expires once its requested start time has passed.
- Expired adverts:
  - Are hidden from the nanny requests list immediately (filtered at read time).
  - Are marked `status = rejected` with `admin_reason = "expired"` by a scheduled sweep (every 30 minutes), so reporting can distinguish expiry from human rejection.
  - Can never be accepted (server blocks acceptance of past windows independently).
- Requests already accepted by a nanny are never auto-expired.

## 7. Location Rules

- Parent location is required for matching and booking operations.
- Parent must confirm booking location in booking UI before submission.
- Location confirmation validation appears in UI and blocks submit until confirmed.
- A nanny must provide a home location after account creation as part of profile completion.
- Nanny location must include usable geographic coordinates, obtained through the configured Google location/geocoding flow.
- A nanny may not submit a completed screening application or receive profile approval without verified coordinates on file.
- Parent matching and nanny discovery are ordered primarily by location/distance. Trust badges and ratings are supporting signals, not replacements for proximity.
- Nanny duty geofence:
  - Nanny check-in is allowed only when within **100 meters** of the booking location.
  - Nanny check-out is allowed only when within **100 meters** of the booking location.
  - If outside the 100m radius, API returns a conflict error and does not record the duty action.

## 8. Profile and Validation Rules

- Input validation is strict on API layer (dates, times, required fields, state transitions).
- Explicit HTTP errors are returned on invalid payloads or business-rule violations.
- Nanny and parent profile completion affects booking/search behavior in parts of the app.
- Nanny profile completeness includes a clear, recent profile photo and all mandatory personal, identity, eligibility, location, work, and document information applicable to that nanny.
- Nannies may upload or replace their own profile photo.
- Admin may upload or replace a nanny's profile photo on the nanny's behalf.
- A nanny who has not yet received reviews is displayed as `New`; an absent rating must not be displayed or interpreted as a zero rating.

## 8A. Candidate Approval and Parent Visibility Rules

- Video screening completion and verified nanny coordinates are hard requirements for profile approval.
- Before approval, the system checks the complete candidate record and identifies outstanding mandatory information.
- If information remains outstanding, admin must see a warning that lists the incomplete items and explains that approval may not make the profile visible to parents.
- Admin may override profile incompleteness only after explicitly acknowledging that the profile is incomplete.
- An approval override is recorded as a deliberate admin action; it does not bypass separate search, document, suspension, or parent-visibility eligibility rules.
- A nanny becomes eligible for parent discovery only when all of the following are true:
  - The nanny profile is approved.
  - The video interview is complete and submitted.
  - The nanny account is active and not suspended.
  - Required identity, eligibility, and document requirements are satisfied.
  - A verified location is on file.
- Parents may only see approved, video-screened candidates who meet all parent-visibility eligibility rules.
- Parent-facing nanny profiles use the nanny's real first name and only the initial of the last name.
- Parent-facing profiles contain no direct contact details.
- Parents must never receive access to a nanny's ID or passport number, identity/legal documents, permit details, medical information, exact home address, phone number, email address, or private operational notes.
- Admin access to sensitive candidate information is limited to legitimate screening and operational needs and remains subject to audit and POPIA controls.

## 8B. Document and Trust Badge Rules

- Uploading a document means `uploaded - awaiting approval`; an upload alone is not verification.
- Replacing a document invalidates and removes the approval attached to the previous file.
- Admin may upload documents on a nanny's behalf.
- Admin must be able to open, review, approve, or remove approval from candidate documents.
- Document approval records the approving admin and approval timestamp.
- Trust badges are earned only when the underlying requirement has been reviewed and approved by admin.
- Uploading a document, completing a field, or submitting a video does not by itself award an approved trust badge.
- Pending requirements may be shown to the nanny as progress or improvement opportunities, but may not be represented as earned badges.
- Parent-facing trust badges must reflect current approved evidence. A revoked, replaced, expired, or rejected supporting document removes or suspends the related badge.
- Uploaded photos, documents, and video interviews must use the configured private storage provider in deployed environments; deployment-local disk is development-only.
- Storage buckets must not be public. Media is delivered through authenticated application routes so access rules remain consistent across storage providers.
- Sensitive nanny documents are accessible only to the document owner and authorized administrators. Parents cannot access identity, passport, permit, police-clearance, licence, reference, or certificate files.
- Existing local upload references remain readable during migration, but all new deployed uploads must use private object storage.

## 8C. Video Interview Rules

- The standard nanny video interview contains four required questions.
- Every required question must have a recorded answer before the interview can be submitted.
- Each answer has a maximum recording duration of **60 seconds**.
- Recordings should use storage-conscious capture settings while maintaining sufficient quality for screening and parent trust.
- If submission is attempted with unanswered questions, the nanny receives a clear warning identifying that all questions must be completed.
- Video answers remain private until the interview is submitted, reviewed, and the profile is approved for parent visibility.
- Once submitted:
  - The nanny may replay and view the submitted answers.
  - Recording and `record again` controls are removed.
  - The nanny may not resubmit or replace answers directly.
- A nanny who wants to replace submitted videos must request resubmission from admin.
- Recording controls return only after admin authorizes the resubmission request.
- Parents never see candidates whose required video interview has not been completed and submitted.

## 8D. Foreign Passport Compliance Rules

- These rules apply to nannies whose nationality is not South African and who are therefore required to keep a valid passport on file.
- Passport validity consists of both:
  - An uploaded passport document or image.
  - A future passport expiry date that belongs to that uploaded passport.
- The nanny is notified when the active passport is within **90 days of expiry**.
  - The warning states the expiry date.
  - The warning explains that a renewed passport and expiry date must be submitted before expiry.
  - The warning explains that the account will be suspended if no valid, admin-approved passport is on file by the deadline.
  - Delivery follows the configured preferred messaging channel with email fallback and also creates an in-app notification.
- A nanny replacing a passport must enter the new expiry date before uploading the replacement document.
- A replacement passport expiry date must be a valid future date.
- Uploading a new passport immediately changes the passport document and expiry date to **awaiting admin approval**.
- Uploading a new passport, changing its image, or changing its expiry date invalidates the previous approval. An old approval may never carry over to a replacement passport or edited expiry date.
- During an early renewal, the previously approved passport expiry remains the active compliance deadline until admin approves the replacement. Entering an unapproved future date may not postpone suspension.
- Admin must review and approve the replacement passport image and its submitted expiry date together.
- Passport approval records the exact expiry date approved, the approving admin, and the approval timestamp.
- A passport is considered valid only when the approved expiry date matches the current passport expiry date and remains in the future.
- If the active passport reaches its expiry date without a valid admin-approved replacement:
  - The nanny account is automatically suspended.
  - The suspension reason identifies passport expiry or a replacement awaiting approval.
  - The nanny is notified through the configured messaging flow and in-app notification.
- When admin approves a valid replacement passport:
  - The nanny is notified that the passport and expiry date were approved.
  - A suspension caused specifically by passport expiry is automatically lifted.
  - Suspensions imposed for unrelated reasons are not automatically lifted.
- Passport compliance is checked when the backend starts and by a scheduled sweep every 24 hours.

## 9. Calendar and Dashboard Rules

- Nanny home calendar shows current work schedule (upcoming/in-progress context).
- Calendar rendering uses cached API data and can require refresh after state changes.
- Admin overview groups/labels bookings and requests by operational status and time state.
- Booking counts shown on overview tiles must be derived from the same booking data represented by the related list or calendar; summary and detail counts must not conflict.
- Selecting an operational booking row may open its complete booking details directly without requiring an intermediate calendar navigation.

## 9A. Notification Rules

- Central policy matrix lives in `app/services/notifications.py::NOTIFICATION_POLICY`.
- Channel priority per event: WhatsApp (Twilio) first, email fallback. Delivery stops at the first successful channel.
- Action-required events, including passport expiry warnings and passport-related suspensions, additionally write an in-app notification.
- Every delivery attempt is logged to `notification_log` with the message body.
- A scheduled sweep (every 15 minutes) retries failed notifications: max 3 attempts per (user, event, reference) tuple within a 48-hour window; stops permanently once any channel delivers.
- Twilio requires env vars `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`. Until configured, WhatsApp attempts fail fast and email delivers - behavior is unchanged from email-only.

## 9B. Parent Payment Readiness Rules

- A parent may browse nannies and prepare booking details before payment authorisation is complete.
- A parent may not submit a booking request until Paystack authorisation has been completed successfully.
- Paystack authorisation is a required parent-profile completion item and is shown in the parent's profile progress tiles.
- My Nanny does not collect or store full card details. Card entry and sensitive payment information are handled by Paystack.
- My Nanny may retain the Paystack customer/authorisation references and limited display metadata returned by Paystack, such as card brand and last four digits, so future booking charges can be initiated securely without storing card details.
- Parent-facing wording must clearly explain the booking restriction and direct incomplete parents to complete authorisation through Paystack.

## 10. Operational Safety Rules

- Preserve backward-compatible request/response shapes unless intentionally changed.
- Prefer small safe changes over broad rewrites.
- Auth/security/payment behavior changes should include risk review.

## 10A. Manual Pause and Suspension Timing Rules

- Manually pausing or suspending a nanny must not terminate work already in progress.
- If a nanny is currently working, the pause takes effect immediately after the current booking's scheduled completion time.
- The current booking continues to follow its normal check-in, check-out, billing, payout, and support rules.
- The parent continues to be billed according to the active booking and payment rules.
- Once the pause becomes effective, the nanny is excluded from new parent searches, new booking requests, and new assignments until reactivated.
- Automatic compliance suspensions, including passport-expiry suspension, follow their specific compliance rules and must preserve required operational and audit history.

## 10B. Trust Configuration and Team Access Rules

- Trust badges are evidence-based and may only be earned after the relevant evidence has been approved by an administrator.
- Superadmins configure whether each trust badge is required or optional and whether parents may see it.
- Nanny tags, qualifications, and specialties may be retired without deleting historical assignments or records.
- Administrator access is scoped as `operations`, `finance`, or `superadmin`; server-side permissions are authoritative even when navigation is hidden.
- Operations administrators manage bookings, candidates, users, and customer communication.
- Finance administrators manage finance, payouts, refunds, and customer communication.
- Superadmins have full access, including pricing, integrations, trust configuration, audit history, and team access.
- Only superadmins may invite administrators, change administrator access levels, or cancel pending invitations.
- An administrator invitation records its intended access level, expires after seven days, and applies that level when accepted.
- Existing administrators created before scoped access was introduced retain superadmin access until explicitly assigned a narrower role.

## 11. Known Current Policy Decisions

- One availability entry per day per type per nanny.
- 5-hour pre-booking hold before existing bookings for different parents.
- Same-parent exception for the 5-hour hold.
- South Africa local time is the canonical business time for scheduling UX.
- Distance/location is the primary nanny discovery ordering signal.
- New nannies with no reviews display as `New`, not zero-rated.
- Parents only see eligible approved nannies with submitted video interviews and no direct contact or sensitive identity information.

## 12. Change Control

When a rule changes:

- Update this document in the same PR as code changes.
- Add/update tests that enforce the rule.
- Mention migration/cleanup steps if existing data may violate the new rule.
