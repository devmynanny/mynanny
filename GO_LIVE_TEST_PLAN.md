# My Nanny V2 Go-Live Test Plan

This plan translates `APP_RULES.md` into release tests for My Nanny V2. A release may proceed only when every P0 test passes in staging, all automated suites are green, and the production smoke test is complete.

## 1. Release Decision Rules

### Severity

| Level | Meaning | Launch decision |
|---|---|---|
| P0 | Security, privacy, money, approval, booking, location, suspension, or data-loss risk | Any failure blocks launch |
| P1 | Core workflow is broken or seriously misleading but no immediate security or money loss | Any unresolved failure blocks launch |
| P2 | Usability, accessibility, layout, wording, or non-critical browser issue | Launch only with an owner and dated fix |

### Required evidence

For every P0 and P1 test, retain:

- Test date, environment, app commit, and tester.
- Account and booking reference used, without passwords or full identity numbers.
- Pass/fail result and screenshots or provider log references.
- Defect link and retest evidence for every failure.

Use synthetic identities and documents in staging. Never upload a real ID, passport, bank statement, or child medical record for testing.

## 2. Automated Release Gate

Run from `/Users/daviddiener/Desktop/nanny_app` against a clean checkout:

```bash
.venv/bin/python -m pytest -q
cd v2
npm ci
npm run lint
npm run build
npm test
```

Required result: all commands exit successfully with no skipped P0 tests. `npm test` is not currently an effective gate because no Playwright specifications exist yet. The P0 browser journeys in section 4 must be automated before production launch.

Also run against a clean staging Postgres database:

```bash
alembic upgrade head
alembic current
```

Required result: migration succeeds, the database is at the latest revision, and the app starts without startup or schema errors.

## 3. Test Accounts and Data

Prepare these isolated staging accounts:

| Account | Purpose |
|---|---|
| Superadmin | Settings, role correction, approval override, audit, suspension |
| Restricted operations admin | Verify scoped admin access |
| Complete South African nanny | Approval, booking, check-in/out, payout |
| Incomplete South African nanny | Approval and visibility blocking |
| Foreign nanny | Passport expiry and replacement workflow |
| Parent with Paystack authorization | Successful booking journey |
| Parent without Paystack authorization | Payment readiness blocking |
| Unrelated parent | Privacy and object-access tests |

Create bookings for single-nanny, multi-nanny, same-parent adjacent shifts, different-parent adjacent shifts, late arrival, early departure, overtime, cancellation, dispute, and failed payment scenarios.

## 4. P0 Browser Journeys to Automate with Playwright

### Authentication and roles

| ID | Scenario | Expected result |
|---|---|---|
| AUTH-01 | Parent, nanny, admin, and superadmin sign in | Each reaches only their role-appropriate home and menu |
| AUTH-02 | Anonymous user opens authenticated routes | Redirected to sign-in; no private content is rendered |
| AUTH-03 | Parent attempts admin/nanny API and UI routes | Access denied without leaking data |
| AUTH-04 | Admin changes an incorrectly selected parent role to nanny | Role changes, original user history remains, and action is audited |
| AUTH-05 | Disabled or suspended account signs in and attempts protected actions | Access/action is blocked according to the suspension rule |

### Nanny onboarding, profile, and approval

| ID | Scenario | Expected result |
|---|---|---|
| NAN-01 | New nanny creates an account | Only basic account fields appear before sign-up; detailed eligibility questions appear after sign-up |
| NAN-02 | Nanny completes profile without verified location | Interview submission/approval remains blocked and the missing location is explicit |
| NAN-03 | Nanny enters an address through Google Places | Address components and coordinates are stored and survive refresh |
| NAN-04 | Nanny uploads a profile photo and admin replaces it | Correct photo is shown; private documents are never substituted as profile photos |
| NAN-05 | Nanny completes required fields, documents, video, location, and payout setup | Candidate becomes approval-ready but is not parent-visible before admin approval |
| NAN-06 | Admin tries to approve an incomplete candidate | Warning lists outstanding fields and requires explicit acknowledgement; hard rules remain non-overridable |
| NAN-07 | Admin approves a fully eligible nanny | Status changes consistently, audit entry is created, and nanny becomes parent-visible |
| NAN-08 | Admin declines a candidate | Candidate becomes non-visible and cannot receive/accept bookings; reason and audit entry are retained |
| NAN-09 | New approved nanny has no reviews | Parent sees `New`, not a zero rating or misleading score |

### Documents, badges, and private storage

| ID | Scenario | Expected result |
|---|---|---|
| DOC-01 | Nanny uploads ID, passport, clearance, licence, and certificate | Each shows uploaded/pending state and remains private |
| DOC-02 | Unrelated parent or anonymous user requests document URL/media route | Request is denied; no S3 URL or object key grants public access |
| DOC-03 | Admin opens an uploaded document | Authorized streaming works through `/media/*`; bucket remains private |
| DOC-04 | Admin approves a document | Approval metadata is recorded and the corresponding gold/verified badge is earned |
| DOC-05 | Nanny replaces an approved document | Previous approval and badge are invalidated until the replacement is approved |
| DOC-06 | Nanny uploads a document but admin has not approved it | No trust badge is earned merely from upload |
| DOC-07 | Upload wrong type, oversized file, malformed file, and path-traversal name | Upload is rejected safely without creating an accessible object |

### Video introductions

| ID | Scenario | Expected result |
|---|---|---|
| VID-01 | Record, stop, and record again before submission | Camera restarts and replacement recording works |
| VID-02 | Recording reaches 60 seconds | Recording stops automatically and upload remains within configured storage limits |
| VID-03 | Submit with fewer than four valid answers | Submission is blocked with a clear missing-answer message |
| VID-04 | Submit four valid videos | Interview locks; nanny can replay but cannot record or resubmit |
| VID-05 | Reopen a submitted interview | Browser does not request camera/microphone permission |
| VID-06 | Nanny requests a new attempt and admin authorizes it | Recording unlocks only after admin authorization and action is audited |
| VID-07 | Parent searches nannies | Only approved candidates with completed approved video content are returned |

### Parent onboarding and privacy

| ID | Scenario | Expected result |
|---|---|---|
| PAR-01 | Parent completes profile | Progress reaches 100%, completion notice displays, then home actions are emphasized |
| PAR-02 | Parent saves profile again | Saved/completion notice displays briefly and returns to parent home |
| PAR-03 | Parent leaves required data incomplete | Progress and next-best-step identify the missing fields |
| PAR-04 | Parent searches and opens nanny profile | Sees permitted full profile with first-name/last-initial presentation and no nanny contact, ID, passport, bank, or private document details |
| PAR-05 | Parent location is missing or unverified | Distance search and booking submission are blocked with a corrective action |

### Availability, search, and booking setup

| ID | Scenario | Expected result |
|---|---|---|
| AVL-01 | Nanny adds/removes dates and creates a weekly pattern | Dates and hours persist; duplicate availability is not created |
| AVL-02 | Nanny blocks a date containing a booking | Existing booking remains protected and cannot be silently invalidated |
| AVL-03 | Parent selects multiple dates | Every selected date appears in booking summary and survives the available-nanny transition and edit-return flow |
| AVL-04 | Search with parent and nanny coordinates | Results are distance ordered and radius filtering is correct |
| AVL-05 | Nanny has no matching availability or overlapping booking | Nanny is excluded from available results |
| AVL-06 | Different parent requests within five-hour buffer | Nanny is unavailable |
| AVL-07 | Same parent requests within five-hour buffer | Allowed when all other rules pass |

### Paystack readiness and payments

| ID | Scenario | Expected result |
|---|---|---|
| PAY-01 | Parent without Paystack authorization views estimate/search | Estimate may display, but booking submission is blocked with setup guidance |
| PAY-02 | Parent completes Paystack authorization | Profile completion tile updates; app stores only provider references, never full card data |
| PAY-03 | Nanny without Paystack recipient setup reaches admin approval | Approval is blocked because payout readiness is mandatory |
| PAY-04 | Nanny completes payout setup | Provider recipient reference is stored; full account details are not displayed or logged |
| PAY-05 | Successful charge webhook is delivered twice | Booking/payment transition happens once; duplicate event is idempotent |
| PAY-06 | Invalid webhook signature or unknown event | Invalid signature is rejected and audited; unknown valid event causes no unsafe state change |
| PAY-07 | Charge fails during acceptance | No confirmed booking or filled slot is created; parent sees payment failure |

### Broadcast and multi-nanny booking

| ID | Scenario | Expected result |
|---|---|---|
| BRC-01 | Broadcast mode disabled | Parent follows single-nanny flow; bulk selection is rejected |
| BRC-02 | Broadcast mode enabled and one nanny needed | Job is sent only to selected eligible nannies and remains open until one paid acceptance |
| BRC-03 | Parent requests more positions than selected nannies | Submission is blocked |
| BRC-04 | Parent requests two nannies and selects three | First paid acceptance fills one slot; request remains open; second fills final slot; remaining invitations close |
| BRC-05 | Two nannies accept the final available slot concurrently | Exactly one succeeds; capacity cannot be overfilled or double charged |
| BRC-06 | Advert start time passes without fill | Advert expires and disappears from nanny listings |
| BRC-07 | Suspended, unapproved, incomplete, unavailable, or document-invalid nanny accepts | Acceptance is rejected at action time, even if invitation was previously delivered |

### Duty, geofence, billing, and payout

| ID | Scenario | Expected result |
|---|---|---|
| DUT-01 | Nanny checks in within 100 m and from 30 minutes before start | Check-in succeeds once and booking becomes in progress |
| DUT-02 | Nanny checks in outside radius or before time window | Check-in is blocked and no duty timestamp is written |
| DUT-03 | Nanny checks out outside radius | Checkout is blocked unless the defined admin process resolves it |
| DUT-04 | Nanny arrives late | Payable wage and client total decrease for unworked time; full fee is not charged |
| DUT-05 | Nanny leaves early | Payable wage and client total decrease according to actual confirmed duty time |
| DUT-06 | Nanny works beyond scheduled finish | Overtime starts from scheduled finish and requires parent confirmation before charging/releasing payout |
| DUT-07 | Parent confirms actual times | Correct total and payout are finalized exactly once |
| DUT-08 | Parent corrects times | Totals recalculate and adjusted payout hold is released correctly |
| DUT-09 | Parent disputes times | Payout freezes and case is routed to admin review |
| DUT-10 | Check-in/out request is repeated | Endpoint is idempotent; timestamps, charges, and notifications are not duplicated |

### Cancellation, pause, and suspension

| ID | Scenario | Expected result |
|---|---|---|
| OPS-01 | Cancel at exact policy boundaries and either party cancels | Correct cancellation scenario, refund, fee, and payout split are applied |
| OPS-02 | Admin pauses nanny during an active booking | Current booking continues; pause takes effect only after scheduled/actual completion |
| OPS-03 | Nanny reaches demerit/suspension threshold | Suspension triggers at exact threshold and blocks new work |
| OPS-04 | Suspended nanny has an existing current booking | Current duty follows the defined safety rule; future invitations/acceptances are blocked |

### Foreign passport compliance

| ID | Scenario | Expected result |
|---|---|---|
| PAS-01 | Approved passport reaches 90 days before expiry | Nanny receives warning and admin queue flags it once according to notification policy |
| PAS-02 | Nanny uploads replacement passport | Replacement is pending; old approved expiry remains controlling until admin approval |
| PAS-03 | Admin approves replacement image without expiry or expiry without image | Approval is blocked; image and expiry must be approved together |
| PAS-04 | Old passport expires while replacement is pending | Account is suspended and hidden from parents |
| PAS-05 | Admin approves valid replacement | Passport-specific suspension clears, badge returns, and other suspension reasons remain intact |
| PAS-06 | Daily compliance sweep runs repeatedly | Alerts and suspension transitions are idempotent and audited |

### Notifications and communicator

| ID | Scenario | Expected result |
|---|---|---|
| NOT-01 | Booking event triggers preferred WhatsApp notification | Approved utility template is used and provider/message status is logged |
| NOT-02 | WhatsApp send fails | Email fallback sends once and in-app action item is created where required |
| NOT-03 | All channels fail | Retry process attempts at most three times within 48 hours and then flags operations |
| NOT-04 | Inbound WhatsApp message has valid signature | Message appears in the correct communicator thread |
| NOT-05 | Inbound WhatsApp message has invalid signature | Rejected and audited |
| NOT-06 | Admin replies inside and outside WhatsApp 24-hour window | Free-form works only inside window; approved template is required outside it |
| NOT-07 | Booking approaches start, misses check-in, and reaches finish without checkout | Required reminders/escalations send once and appear in operations health |
| NOT-08 | User selects Telegram without linking it | Selection is blocked; linked Telegram flow sends and receives in the communicator |

### Audit, settings, and operational safety

| ID | Scenario | Expected result |
|---|---|---|
| ADM-01 | Superadmin opens platform settings and audit log | Access succeeds; restricted admin sees only authorized settings/actions |
| ADM-02 | Broadcast setting is changed | New bookings follow new mode; change is audited with actor and timestamp |
| ADM-03 | Approval, decline, role change, document approval, override, suspension, and impersonation occur | Every action creates an immutable audit entry |
| ADM-04 | Admin edits nanny personal, legal, work, documents, photo, location, and payout readiness | Changes persist, validation runs, and sensitive changes are audited |
| ADM-05 | Operations health contains failed notifications, rejected webhooks, disputed payout, or refund mismatch | Correct alert/count and drill-down are shown |

## 5. Security and Privacy Tests

These are P0 and should include automated authorization tests plus a focused manual review:

- Verify S3 Block Public Access remains fully enabled and anonymous object URLs return access denied.
- Verify all private media is served only after application authorization and cannot be accessed using another user's identifier.
- Verify IDs, passports, police clearances, medical details, access instructions, phone numbers, full addresses, Paystack secrets, bank details, JWTs, Twilio tokens, and AWS keys never appear in browser logs, API errors, audit payloads, or analytics.
- Verify login/session cookies use secure production attributes and logout invalidates access.
- Verify API input validation covers file names, content types, sizes, dates, phone formats, counts, status values, and coordinates.
- Verify rate limiting or equivalent abuse protection on login, signup, uploads, video submission, booking acceptance, webhook, and messaging endpoints.
- Run dependency and secret scans before launch. High/critical exploitable findings block release.
- Confirm production errors do not display stack traces or internal provider responses to users.

## 6. Provider and Infrastructure Tests

### Render and Postgres

- Deploy from a release commit and confirm backend `/health` and V2 `/` health checks remain green through migration and startup.
- Verify frontend uses the production backend and `app.mynanny.co.za` serves HTTPS with no mixed content.
- Create, read, update, and complete a booking in staging Postgres, then restart both services and confirm persistence.
- Confirm automated backups are enabled and perform a restore rehearsal into a separate database before launch.
- Confirm rollback to the previous Render deploy is documented and tested without running an unsafe schema downgrade.

### AWS S3

- Upload/download each supported media type through the app.
- Confirm object metadata and paths do not expose sensitive personal information.
- Confirm failed uploads do not leave database records claiming success.
- Confirm missing/deleted objects produce a safe user error and operations signal.
- Confirm CORS is no broader than required and bucket listing/public ACLs are disabled.

### Paystack

- Use Paystack test mode for authorization, successful charge, failed charge, duplicate webhook, delayed webhook, refund/cancellation, and payout recipient tests.
- Reconcile app totals, Paystack references, nanny wage, platform fee, refunds, and payout holds.
- Verify switching from test to live keys cannot mix test customers/authorizations with production records.

### Twilio, email, and Telegram

- Confirm every required WhatsApp Content SID is approved before setting `TWILIO_REQUIRE_TEMPLATES=true` in production.
- Test sender, inbound webhook URL, signature verification behind Render proxy headers, delivery callback, failure callback, email fallback, and communicator ingestion.
- Confirm notification text contains no unnecessary child, medical, document, banking, or access-instruction data.

### Google Maps

- Test autocomplete and geocoding for Johannesburg, Midrand, Pretoria, Cape Town, informal/partial addresses, and a deliberately invalid address.
- Verify restricted API key configuration, allowed domains, quota alerts, and graceful failure when Maps is unavailable.

## 7. Compatibility, Accessibility, and Quality

These are P1 unless they prevent a P0 workflow:

- Desktop: latest Chrome, Safari, Firefox, and Edge.
- Mobile: current iOS Safari and Android Chrome, including camera permissions and geolocation.
- Slow network and interrupted upload for photos, documents, and each video answer.
- Responsive checks at 320 px, 375 px, 768 px, 1024 px, and large desktop widths.
- Keyboard-only operation, visible focus, meaningful labels, error announcements, modal focus trap/escape, sufficient contrast, and 200% zoom.
- South African date, time, currency, telephone, SAST/UTC conversion, and daylight-independent behavior.
- Empty, loading, error, retry, duplicate-click, back-button, refresh, and expired-session states.

## 8. Existing Automated Coverage

The current Python suite already provides valuable coverage for:

- Booking broadcasts, requested nanny count, availability, overlap, five-hour buffer, advert expiry, payment acceptance, and idempotency.
- Geofence, check-in window, late-arrival reduction, overtime, parent correction, dispute, and payout hold behavior.
- Paystack webhook signatures and payment transitions.
- Video completion and approval gates.
- Candidate/parent completeness, badges, scoped admin access, and audit events.
- Private uploads and S3-compatible media authorization rules.
- Notification fallback, retries, WhatsApp templates, inbound webhooks, communicator windows, Telegram linking, and duty reminders.
- Cancellation boundaries, demerits, suspension thresholds, reconciliation, booking statuses, and operations health.

Coverage still required before launch:

- Playwright tests for the P0 browser journeys in section 4.
- Full foreign-passport lifecycle tests, including 90-day warning, expiry suspension, replacement coupling, and suspension lifting.
- Concurrency tests for the final broadcast slot and duplicate provider callbacks.
- End-to-end Paystack test-mode authorization, charge, refund, and payout tests.
- End-to-end S3 tests against a private staging bucket.
- Mobile camera, geolocation, and interrupted-upload tests.
- Parent-visible privacy snapshots proving sensitive fields never render.
- Backup restore and Render rollback rehearsal.

## 9. Production Smoke Test

After deployment, use designated production test accounts and a low-value controlled booking:

1. Open `https://app.mynanny.co.za`, sign in as parent, nanny, and admin.
2. Confirm role menus, settings access, and audit log.
3. Confirm parent search returns only approved, video-complete, location-valid nannies.
4. Create one controlled booking, confirm notification delivery, accept it, and verify Paystack reference and booking status.
5. Open booking details from both dashboard and calendar.
6. Verify private photo/video access works and private identity documents remain inaccessible to the parent.
7. Confirm operations health, notification logs, audit log, Render logs, S3 metrics, and Paystack/Twilio logs show no unexplained failures.
8. Cancel or complete the controlled booking and reconcile all amounts.

Do not test a real check-in at a fake location or upload real personal documents in production.

## 10. Final Go/No-Go Checklist

- [ ] All Python tests pass.
- [ ] Frontend lint and production build pass.
- [ ] Required Playwright P0 journeys pass on desktop and mobile.
- [ ] Staging Postgres migration and persistence pass.
- [ ] Paystack end-to-end and reconciliation pass.
- [ ] S3 privacy and authenticated media tests pass.
- [ ] Twilio templates, webhooks, fallback, retries, and communicator pass.
- [ ] Google Maps autocomplete, coordinates, distance, and geofence pass.
- [ ] Passport warning, replacement, expiry, and suspension lifecycle pass.
- [ ] Broadcast single/multi-slot and concurrency tests pass.
- [ ] Late/early/overtime/dispute billing and payout tests pass.
- [ ] Role, approval, visibility, document, and privacy tests pass.
- [ ] Backup restore and rollback rehearsal pass.
- [ ] No open P0 or P1 defects.
- [ ] Production environment variables are present, scoped, and not committed.
- [ ] Release commit, migration revision, test evidence, owner, and rollback decision are recorded.
- [ ] Product owner gives written go-live approval.
