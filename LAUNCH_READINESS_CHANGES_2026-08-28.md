# My Nanny V2 Launch-Readiness Changes - 28 August 2026

This file records changes and verification performed during the final admin and launch-readiness pass. No paid provider actions are permitted during this pass.

## Changes

- Replaced the admin overview's hardcoded booking count and three demo booking rows with live data from `/admin/bookings/overview`.
- Admin overview dates and times are interpreted in the `Africa/Johannesburg` timezone.
- Clicking a live booking row opens its booking-details drawer directly.
- Added loading, empty, and API-error states so the overview does not display invented operational data.
- Replaced the hardcoded interview-review count with the number of pending applications that have completed video screening.
- Corrected duplicate primary-content landmarks on Trust configuration and Team access so every admin destination uses the application shell's single `main` region.

## Verification Log

- Frontend lint: passed.
- V2 production build: passed.
- Backend regression suite: `182 passed`.
- Isolated Chromium suite: `3 passed`, covering the complete nanny onboarding/video flow, the incomplete-profile approval safeguard, and every admin menu destination.
- Admin menu coverage is read-only and runs with Twilio, Paystack, and S3 disabled.
- Pending: production deployment smoke test.

## Admin Menu Coverage

- Overview
- Candidate review
- Users & records
- Bookings
- Finance
- Refunds
- Safety centre
- Communicator
- Audit logs
- Trust configuration
- Team access
- Settings

## Known Constraints

- Provider integrations that can incur charges must be mocked or inspected without sending messages, taking payments, or creating paid resources.
- Production authentication must use an existing authenticated session or be completed by the account owner; credentials are not recorded in this file.
