# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

My Nanny — a marketplace connecting parents with nannies in South Africa (nanny booking, scheduling, payments, payouts). See `MY_NANNY_PRODUCT_SPEC.md` for the full product spec and `APP_RULES.md` for the authoritative business/behavior rules (statuses, availability, buffers, notifications, geofencing).

- Backend: FastAPI + SQLAlchemy 2.0
- Frontend: static HTML/CSS/JS served from `app/static/` (no SPA framework, no build step)
- Database: SQLite locally (`nanny_app.db`), managed Postgres in production (Render)
- Payments: Paystack (South Africa first)
- Local timezone for business logic: `Africa/Johannesburg` (SAST) — see `app/utils/time.py`

## Commands

```bash
# Install deps
pip install -r requirements.txt

# Run the app (auto-reload)
uvicorn app.main:app --reload

# Run all tests
pytest

# Run a single test file / test
pytest tests/test_booking_flow_api.py
pytest tests/test_booking_flow_api.py::test_name -q

# Alembic migrations (Postgres/production schema)
alembic upgrade head
alembic revision -m "description"
```

Tests are hermetic: `tests/conftest.py` points `DATABASE_URL` at a fresh temp SQLite file before any app import, so `pytest` never touches the dev `nanny_app.db`. Set `MYNANNY_TEST_USE_REAL_DB=1` to opt back into running against the real dev DB.

There is no lint/format command configured in this repo.

## Architecture

### Two schema-management paths — know which one applies

- **SQLite (local/dev)**: `app/main.py` runs `Base.metadata.create_all()` plus a long list of `ensure_*_schema()` functions from `app/db.py` on every startup. These are hand-written, idempotent, in-place migrations (add column if missing, etc.) — the legacy way this project evolved its schema.
- **Postgres (production/staging)**: schema is managed exclusively by Alembic (`alembic upgrade head`, run by `render.yaml`'s `preDeployCommand`). All the `ensure_*_schema()` functions no-op on non-SQLite dialects (see `_is_sqlite()` guards in `app/db.py`).
- Seed functions (languages, qualifications, pricing defaults, bootstrap admin) run on every dialect, every startup.

When adding a new column/table: add it to the SQLAlchemy model AND write/extend an `ensure_*_schema()` function in `app/db.py` for SQLite AND an Alembic migration for Postgres. Missing either path causes drift between local dev and production.

### Router layout

- `app/routes.py` aggregates `app/routers/public.py` (no prefix — parent, nanny, and shared auth endpoints) and `app/routers/admin.py` (`/admin` prefix). `app/routers/public.py` is very large (~10k lines) and covers most non-admin surface area: auth, parent flows, nanny flows, bookings, payments, notifications.
- Auth is cookie-based (JWT access token in an httpOnly cookie) with CSRF double-submit protection enforced in `app/main.py`'s `attach_request_user` middleware for any unsafe method carrying the access cookie (bearer-token requests are exempt, as is the Paystack webhook). The middleware also authorizes access to `/static/uploads/*`: sensitive document prefixes (`id_`, `passport_`, `permit_`, `police_`, `drivers_license_`, `reference_`, `certificate_`) are restricted to their owner or an admin.
- Admin-only endpoints additionally use `require_admin` (`app/deps.py`), which accepts either the static `ADMIN_API_KEY` (header/query) or a JWT with `role: admin`.

### Status vocabularies are centrally defined and enforced at the model layer

`app/services/booking_status.py` is the single source of truth for every status enum in the booking lifecycle (`booking_requests.status`, `bookings.status`, `nanny_response_status`, `payment_status`). SQLAlchemy `@validates` hooks on the models (`app/models/__init__.py`, `app/models/bookings.py`) enforce these vocabularies on every write — an invalid status raises immediately rather than silently persisting. Read-side display state (what the UI actually shows) is a separate derivation (`booking_state_from_booking` / `booking_state_from_request`) layered on top of the raw write-side status. When touching booking status logic, changes usually need to happen in both places: the write-side vocabulary/validator and the read-side derivation.

### Models package

`app/models/__init__.py` holds most models; a few live in their own files (`app/models/availability.py`, `app/models/bookings.py` for `BookingRequest`/`BookingRequestSlot`/`BookingPricingSnapshot`, `app/models/admin_profile.py`, `app/models/admin_invite.py`, `app/models/audit_log.py`) and are re-imported at the bottom of `__init__.py` so `app.models.X` works uniformly. `AdminProfile` only carries admin-specific fields (`is_superadmin`); authentication (`password_hash`, `is_admin`, `is_active`) lives solely on `User`.

### Domain services (`app/services/`)

Business logic is factored out of routers into services — routers stay thin and call these:
- `booking_status.py` — status vocabularies + read-side state derivation (see above)
- `notifications.py` — `NOTIFICATION_POLICY` is the single source of truth for which channels fire per event type. Channel priority is WhatsApp (Twilio) first, email fallback, stopping at first success; action-required events additionally write an in-app notification. Every attempt is logged to `notification_log` (with message body, so it can be retried). A scheduled sweep retries failures (max 3 attempts per user/event/reference within 48h).
- `advert_expiry.py` — sweeps open, unaccepted booking-request adverts whose start time has passed
- `payout.py`, `debt.py`, `demerit.py`, `cancellation.py` — payout scheduling, nanny debt ledger, demerit scoring, cancellation handling
- `google_calendar.py` — syncs bookings to Google Calendar
- `paystack.py` — Paystack payment integration
- `audit.py` — writes to `audit_logs`

Three APScheduler jobs run in-process (registered in `app/main.py`): payouts (every 30 min), advert expiry (every 30 min), notification retries (every 15 min).

### Request-scoped auth token

`app/request_context.py` exposes a `contextvar` (`auth_token_ctx`) set by the auth middleware in `app/main.py`, letting deep call chains (e.g. outbound calls that need to forward the caller's token) access the current request's token without threading it through every function signature.

## Key business rules to know before changing booking/availability/payment code

(Full detail in `APP_RULES.md` — read it before touching these areas.)

- Nannies get a 5-hour unavailability buffer before any existing booking starts, **except** when the new booking is from the same parent.
- Nanny check-in/out requires being within 100m of the booking location (server-enforced geofence).
- All scheduling is authored/displayed in SAST but persisted as ISO/UTC-compatible timestamps.
- Payment failure is expressed via `admin_reason = "payment_failed"`, never via `payment_status`.

## Constraints from AGENTS.md

- Prefer small, safe changes over broad rewrites; don't rename files unless necessary.
- Preserve existing API request/response shapes unless a change is explicitly requested.
- For auth/security/payment changes, include a quick risk note before implementing.
