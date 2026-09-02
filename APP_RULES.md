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
  - Check-in opens 30 minutes before the scheduled start and closes at the scheduled finish.
  - Check-in and check-out are available only for an active, assigned booking in the appropriate state.
  - Check-out is not available before the scheduled start and requires a recorded check-in.
  - Repeated check-in or check-out requests are idempotent and do not replace the original timestamp.

## 7A. Duty Time, Billing and Confirmation Rules

- The client pays only for scheduled service actually delivered.
- A late arrival reduces the nanny wage and percentage-based booking fee in proportion to the scheduled minutes not delivered.
- An early departure reduces the nanny wage and percentage-based booking fee in the same way.
- Arriving before the scheduled start does not increase billable service time.
- Overtime is measured from the scheduled finish time, not from total elapsed time since check-in, and remains subject to parent approval.
- The nanny's base payout uses the adjusted service wage rather than the original full scheduled wage.
- Client refunds for undelivered time are finalized through Paystack only after the parent confirms both arrival and finish times.
- A parent may confirm, correct, or dispute either timestamp.
- A correction recalculates late time, early departure, billable service, refund, overtime and payout before settlement.
- A disputed timestamp moves the booking to admin review and freezes payout until resolved.
- Browser GPS coordinates are treated as operational evidence but do not replace parent confirmation or admin dispute review.

## 8. Profile and Validation Rules

- Input validation is strict on API layer (dates, times, required fields, state transitions).
- Explicit HTTP errors are returned on invalid payloads or business-rule violations.
- Nanny and parent profile completion affects booking/search behavior in parts of the app.
- Nanny profile completeness includes a clear, recent profile photo and all mandatory personal, identity, eligibility, location, work, and document information applicable to that nanny.
- Nannies may upload or replace their own profile photo.
- Admin may upload or replace a nanny's profile photo on the nanny's behalf.
- A nanny who has not yet received reviews is displayed as `New`; an absent rating must not be displayed or interpreted as a zero rating.

## 8A. Candidate Approval and Parent Visibility Rules

- Video screening completion, verified nanny coordinates, and completed Paystack payout details are hard requirements for profile approval.
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
  - A Paystack payout recipient has been created and banking setup is complete.
- Parents may only see approved, video-screened candidates who meet all parent-visibility eligibility rules.
- Parent-facing nanny profiles use the nanny's real first name and only the initial of the last name.
- Parent-facing profiles contain no direct contact details by default.
- Parents must never receive access to a nanny's ID or passport number, identity/legal documents, permit details, medical information, exact home address, or private operational notes.
- A nanny's phone number and email address remain hidden except for the narrowly controlled Permanent Placement interview-arrangement window described in section 9D.
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

## 8E. Uploaded Media Retention Rules

- Retention applies to profile photos, family photos, identity and legal documents, certificates, references, and video interview recordings stored by the platform.
- The database reference to an uploaded file identifies the active version. Replacing a file creates a new storage object and makes the previous object superseded; replacement must not silently overwrite the previous object under the same storage key.
- Superseded photos, documents, and video answers are retained for a **30-day recovery period** and then permanently deleted from private object storage, unless a legal or operational hold applies.
- Uploaded objects that are never linked to a valid database record, or that become orphaned because an upload flow fails, are permanently deleted after **7 days**.
- Active profile photos, family photos, approved documents, and submitted interview videos are retained while the related account remains active and the material remains necessary for screening, trust, bookings, compliance, or dispute handling.
- After account deactivation:
  - Identity, passport, permit, police-clearance, licence, certificate, reference, and other screening documents are deleted after **12 months**.
  - Submitted video interviews are deleted after **12 months**.
  - Parent family photos are deleted within **30 days**.
  - Nanny profile photos are deleted after **12 months**, unless earlier deletion is approved through a verified data-subject request.
- Financial, payout, booking, refund, tax, and dispute records remain subject to their separate **5-year** retention rule. Deleting uploaded media must not delete required financial or booking records.
- A documented legal, safety, fraud, chargeback, safeguarding, or active-dispute hold pauses scheduled deletion only for the affected records. The reason, owner, start date, and release date of the hold must be auditable.
- Deletion must remove the storage object, not only clear its database URL. Deletion actions and failures must be logged without recording sensitive document contents.
- Retention enforcement must use an automated scheduled cleanup job. S3 lifecycle rules should provide a secondary safeguard where appropriate, but may not replace database-aware checks for active references and legal holds.
- Cleanup must be idempotent and must never delete the currently active file referenced by an account, candidate profile, document approval, or submitted interview record.
- Backups follow the hosting provider's backup-expiry schedule; deleted media must not be restored into active use after its retention period without an authorized recovery or legal-hold process.

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
- A duty-monitoring sweep runs every 5 minutes and sends each reminder or escalation only once per user, event, and booking.
- Nannies receive a booking reminder approximately one hour before the scheduled start.
- If no check-in is recorded 15 minutes after the scheduled start, the nanny is prompted to check in, the parent is warned, and active administrators receive an operations alert.
- A checked-in nanny who has not checked out by the scheduled finish receives a checkout reminder.
- Parent check-in and checkout confirmations are action-required notifications linked to the booking screen.
- Confirmed late arrival or early departure notifies the parent of the recorded refund and the nanny of the adjusted service earnings.
- Parent time corrections notify the nanny and administrators. A time dispute creates an operations alert and keeps payout frozen for review.
- Multi-position broadcasts notify the parent after every filled position, remain open while positions are outstanding, and notify remaining invited nannies when the broadcast closes.
- Business-initiated WhatsApp notifications use approved, privacy-safe Utility templates. Detailed names, addresses, rates, and service times remain inside the authenticated application.
- Every templated event resolves its Twilio Content SID from `TWILIO_CONTENT_SID_<EVENT_TYPE>`.
- Production sets `TWILIO_REQUIRE_TEMPLATES=true`; a missing template must fail safely to email rather than attempt an out-of-session free-form WhatsApp message.
- Free-form WhatsApp content is reserved for manual replies during an open 24-hour customer-service window.
- Twilio requires env vars `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`. Until configured, WhatsApp attempts fail fast and email delivers.

## 9B. Parent Payment Readiness Rules

- A parent may browse nannies and prepare booking details before payment authorisation is complete.
- A parent may not submit a booking request until Paystack authorisation has been completed successfully.
- Paystack authorisation is a required parent-profile completion item and is shown in the parent's profile progress tiles.
- My Nanny does not collect or store full card details. Card entry and sensitive payment information are handled by Paystack.
- My Nanny may retain the Paystack customer/authorisation references and limited display metadata returned by Paystack, such as card brand and last four digits, so future booking charges can be initiated securely without storing card details.
- Parent-facing wording must clearly explain the booking restriction and direct incomplete parents to complete authorisation through Paystack.

## 9C. Nanny Payout Readiness Rules

- A nanny must link a valid South African bank account through Paystack before admin can approve the candidate profile.
- Banking readiness is a hard approval prerequisite and cannot be bypassed by the incomplete-profile acknowledgement flow.
- Admin review and candidate-completion interfaces must clearly show whether payout setup is complete.
- My Nanny sends the submitted banking details to Paystack to create a transfer recipient, then retains the Paystack recipient reference and masked account information required for payout operations and display.
- Full nanny account numbers must not be displayed after setup or stored as reusable plaintext banking details.
- An approved nanny without valid payout readiness must not be shown in parent discovery results.

## 9D. Permanent Placement Rules

- Permanent Placement and short-term Nanny on Call use the same V2 landing page, accounts and admin application, but remain distinct products with separate profile visibility and workflow rules.
- Every Permanent Placement amount, profile limit, interview-credit limit, decision period and replacement rule is configurable by an administrator. A new case freezes a pricing-and-rules snapshot so later admin changes do not silently alter an existing client's agreement.
- Self-Match uses an activation payment, an interview-package top-up and a successful-placement payment. Five interview credits are consumed only when invited nannies accept; a credit is restored when the interview is cancelled or did not take place.
- Concierge includes the consultation, managed matching, ongoing client consultation, interview and transport coordination, salary negotiation, offer support and placement administration. Its engagement and successful-placement balance are separate payment milestones.
- One admin-approved replacement is included within the configured replacement period. The replacement releases the configured number of interview credits; a second replacement is not included.
- Limited Permanent Placement profiles never expose identity documents, sensitive checks, exact home addresses, parent addresses, phone numbers or email addresses.
- After a nanny accepts an interview, the parent and nanny must each accept the interview contact rules before either can see the other's phone number or email address or use direct candidate chat.
- Temporary phone, email and direct-chat access exists only to arrange that interview. It is automatically hidden and locked when the nanny checks in or records the interview as completed. Existing chat history remains auditable, and My Nanny mediates all later questions, trials, offers and salary negotiations.
- Exact residential addresses are never revealed through Permanent Placement contact access.
- The parent records an outcome for each completed interview: reject, maybe, request a paid trial, make an offer or request admin support. A maybe decision expires after the configured period.
- A formal offer records salary, start date, working days, working hours and terms. Once accepted, those working days are blocked in the nanny's short-term calendar while the nanny remains free to configure availability on non-working days.
- Permanent Placement payments create an immutable invoice snapshot and, once paid, a receipt. Documents remain private to the parent and authorized administrators.
- Invoice issue is blocked until an administrator has confirmed the legal billing identity, address, billing email and VAT treatment. Payment processing itself does not wait for missing billing data; the document remains a draft until the setup is complete.

## 10. Operational Safety Rules

- Preserve backward-compatible request/response shapes unless intentionally changed.

## 10C. Booking Broadcast Rules

- Superadmins may activate or deactivate the multi-nanny broadcast workflow in Platform Settings.
- When active, a parent defines the dates, times, location, care requirements and payment authorisation before selecting one or more eligible available nannies.
- One grouped booking request is created with an individual response record for every selected nanny.
- Every selected nanny is notified and may accept, decline, or indicate that they are still deciding.
- The parent must specify how many nanny positions the job requires before viewing available nannies.
- The broadcast audience and the number of positions required are separate: a parent may send the job to more nannies than are needed.
- Every valid acceptance that successfully completes the parent payment fills one position.
- A grouped job remains open until the number of paid, accepted nannies equals the number of positions requested.
- Only after all positions are filled are the remaining competing requests in that broadcast closed.
- The API must reject a broadcast when fewer eligible nannies are selected than the number of positions required.
- When broadcast mode is inactive, parents may request only one nanny for a job and the bulk API must reject multi-nanny submissions.
- Parents can track each selected nanny's response without seeing private nanny contact details before confirmation.
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

## Client charge queries and partial refunds

- A parent may query a specific charge only after the related booking payment has been recorded as paid.
- A query must identify the affected line item: nanny wage, booking fee, overtime, or another booking charge. Overtime queries must identify the specific booking day.
- The parent must provide the amount being queried and a reason. The queried amount may not exceed the recorded amount of that charge.
- Only one active query may exist for the same booking charge at a time.
- An open, failed, or Paystack-processing query places the related nanny payout on hold so disputed funds are not paid out before the matter is resolved.
- Finance administrators may decline the query or approve a full or partial refund. Every decision requires a reason for the audit trail and client notification.
- A partial refund may not exceed the amount queried, the original line-item charge, or the remaining refundable amount on the paid transaction.
- Finance approval starts a refund request with Paystack. Approval does not mean the refund has completed; completion is recorded only after a valid Paystack webhook confirms it.
- A failed refund remains visible for finance action and keeps the payout hold in place. A declined query or confirmed refund releases the payout hold when no other active query remains.
- Confirmed charge refunds are included in accounting and refund reporting, and the parent is notified of the final outcome.
- My Nanny never stores card details. Payment and refund processing is handled by Paystack using provider references and authorization tokens only.
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
- Parents only see eligible approved nannies with submitted video interviews and no direct contact or sensitive identity information, except for the controlled Permanent Placement interview contact window in section 9D.

## 12. Change Control

When a rule changes:

- Update this document in the same PR as code changes.
- Add/update tests that enforce the rule.
- Mention migration/cleanup steps if existing data may violate the new rule.
