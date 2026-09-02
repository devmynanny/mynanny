# MyNanny Deployment Guide

## Architecture

- Frontend: Next.js V2 on Render (`mynanny-v2`), proxied to the backend through same-origin `/api/*` rewrites.
- Backend: FastAPI on Render (`mynanny`), uvicorn.
- Database: managed Render Postgres (`mynanny-db`). SQLite is LOCAL DEV ONLY.
- Uploads: private S3-compatible object storage, delivered through authenticated `/media/*` routes. Local development continues to use `app/static/uploads`.

## Environments

| Environment | Application | Database | Payments | Private files |
|---|---|---|---|---|
| Local | Local FastAPI and V2 | Local SQLite/test database | Mock or Paystack Test | Private local directory |
| UAT | Separate Render services from `render.uat.yaml` | Logical `mynanny_uat` database on the shared instance | Paystack Test only | Existing private bucket under `uat/` |
| Production | Render services from `render.yaml` | `mynanny-db` | Paystack Live | Production S3 bucket |

Never share authentication secrets, Paystack secrets, S3 credentials or user
data between UAT and production. UAT uses synthetic data. The approved UAT
design shares the paid Postgres instance and S3 bucket only: the logical
database, object prefix and application credentials remain isolated. See
`docs/render-uat-plan.md`.

## Private media storage

Production and staging use `STORAGE_BACKEND=s3`. Configure:

- `S3_BUCKET`: private bucket name.
- `S3_KEY_PREFIX`: optional environment namespace such as `uat`; application
  `/media/*` URLs remain unchanged while provider objects stay isolated.
- `S3_REGION`: provider region.
- `S3_ENDPOINT_URL`: optional for S3-compatible providers such as Cloudflare R2; omit for AWS S3.
- `S3_ACCESS_KEY_ID`: restricted application access key.
- `S3_SECRET_ACCESS_KEY`: restricted application secret.

Production AWS values:

- `STORAGE_BACKEND=s3`
- `S3_BUCKET=my-nanny-production-uploads-337903911181-af-south-1-an`
- `S3_REGION=af-south-1`
- Leave `S3_ENDPOINT_URL` unset for AWS S3.
- `S3_ACCESS_KEY_ID` and `S3_SECRET_ACCESS_KEY` belong to the restricted Render application identity, never the AWS root user.

The bucket must remain private. Do not configure public-read ACLs or expose its provider URL. The application stores stable `/media/<key>` references and checks authentication and document ownership before streaming an object. Existing `/static/uploads/*` database references remain supported while historical files are migrated.

UAT uses the same bucket with `S3_KEY_PREFIX=uat` and an IAM identity restricted
to `arn:aws:s3:::my-nanny-production-uploads-337903911181-af-south-1-an/uat/*`.
Do not reuse the production S3 access key.

Permanent Placement invoices and receipts are stored below `invoices/<parent-id>/` in the same private storage backend. The `/media/invoices/*` application route allows only the owning parent or an authorized administrator to download them; provider URLs must never be shared directly.
- Schema management:
  - Postgres: Alembic only. `alembic upgrade head` runs automatically before each deploy (`preDeployCommand`).
  - SQLite (local dev): `create_all` + legacy `ensure_*` functions run at app startup, unchanged workflow.

## Environment variables (Render dashboard, sync: false)

| Key | Purpose |
|---|---|
| DATABASE_URL | Production database connection; UAT instead receives `DATABASE_ADMIN_URL` and rewrites only the database name |
| DATABASE_NAME_OVERRIDE / UAT_EXPECTED_DATABASE_NAME | Both must be `mynanny_uat`; deployment fails closed if they differ |
| ADMIN_API_KEY | Admin API access |
| JWT_SECRET | Token signing |
| AUTH_SECRET | Auth cookies |
| PAYSTACK_SECRET_KEY | Live Paystack secret key (sk_live_...) |
| EMAIL_MODE | Set to `smtp` in deployed environments |
| SMTP_HOST / SMTP_PORT | Google Workspace SMTP endpoint (`smtp.gmail.com:587`) |
| SMTP_USER | Single My Nanny mailbox: `sayhi@mynanny.co.za` |
| SMTP_PASS | Environment-specific Google app password; never the normal mailbox password |
| FROM_EMAIL | `sayhi@mynanny.co.za` |
| TWILIO_ACCOUNT_SID | Existing WhatsApp notification sending (unchanged) |
| TWILIO_AUTH_TOKEN | Also verifies inbound `/whatsapp/webhook` signatures |
| TWILIO_WHATSAPP_FROM | Existing WhatsApp notification sending (unchanged) |
| TWILIO_REQUIRE_TEMPLATES | Set `true` in production to block out-of-session free-form sends |
| TWILIO_CONTENT_SID_* | Approved Content SID generated for each notification event |
| TELEGRAM_BOT_TOKEN | Bot API token from @BotFather - outbound sends |
| TELEGRAM_BOT_USERNAME | Bot's @username (no @) - used to build the `/me/telegram/connect` deep link |
| TELEGRAM_WEBHOOK_SECRET | Random secret; also the path segment in `/telegram/webhook/{secret}` and the `setWebhook` `secret_token` |

### Conversations (WhatsApp/Telegram inbox) one-off setup

Create the privacy-safe Utility templates and request WhatsApp approval from a secure development machine:

```bash
.venv/bin/python -m scripts.setup_twilio_whatsapp_templates --env-file .env --submit
```

The command is idempotent, records the returned Content SIDs in the ignored `.env`, and enables template enforcement. Check asynchronous approval status with:

```bash
.venv/bin/python -m scripts.setup_twilio_whatsapp_templates --env-file .env --status
```

Copy `TWILIO_REQUIRE_TEMPLATES` and every generated `TWILIO_CONTENT_SID_*` value into the Render environment before production notification testing. Content SIDs identify templates but should remain tenant-specific configuration for white-label deployments.

1. In Twilio's console, set the WhatsApp sender's inbound webhook URL to `https://<render-url>/whatsapp/webhook` (POST). No code-side registration call needed - Twilio just needs the URL configured.
2. Register the Telegram webhook once (from any machine with `TELEGRAM_BOT_TOKEN` and the deployed URL):
   ```bash
   curl -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
     -d "url=https://<render-url>/telegram/webhook/$TELEGRAM_WEBHOOK_SECRET" \
     -d "secret_token=$TELEGRAM_WEBHOOK_SECRET"
   ```
   Re-run this any time `TELEGRAM_WEBHOOK_SECRET` is rotated - Telegram doesn't pick up the new value on its own.
3. The WhatsApp signature check reconstructs the request URL from `X-Forwarded-Proto`/`X-Forwarded-Host` (Render terminates TLS in front of the app) - if signature verification ever fails only in production and not locally, this reconstruction is the first thing to check against what's actually configured in Twilio's console.

## First-time Postgres cutover (one-off)

1. Deploy this branch. Render provisions `mynanny-db` from render.yaml and
   `preDeployCommand` creates the full schema via Alembic.
2. Copy existing staging data from the old SQLite file (if you want to keep it):

       python scripts/migrate_sqlite_to_postgres.py \
           --sqlite sqlite:////opt/render/project/src/app/static/uploads/data/nanny_app.db \
           --postgres "$DATABASE_URL"

   Run this in a Render shell on the web service. Skip if starting clean.
3. Verify: log in as admin, check dashboards, create and accept a test booking.

## Day-to-day schema changes

1. Edit models.
2. `DATABASE_URL=sqlite:///$(mktemp -d)/x.db alembic revision --autogenerate -m "describe change"`
3. Review the generated file in `alembic/versions/` (autogenerate is a draft, not gospel).
4. Commit model + migration together. Render applies it on deploy.
5. For local SQLite dev the legacy ensure_* path still applies changes automatically
  where implemented; keep both paths in sync for columns that matter locally.

### Shared Postgres instance guard for UAT

Render injects the existing instance connection as `DATABASE_ADMIN_URL`. UAT
sets both `DATABASE_NAME_OVERRIDE` and `UAT_EXPECTED_DATABASE_NAME` to
`mynanny_uat`. The pre-deploy step creates that logical database if necessary,
then verifies the resolved target before Alembic runs. Startup repeats the same
check. Never remove these checks or point UAT at the production database name.

## Local development

    pip install -r requirements.txt
    uvicorn app.main:app --reload        # uses sqlite:///./nanny_app.db

Before Permanent Placement payment testing in UAT, an administrator must complete the Billing identity & tax setup on the existing Permanent Placements admin screen. Use the legal entity's confirmed details and VAT treatment; do not infer them from branding or Paystack account data.

Google Workspace must also be configured before invoice-email UAT. Use the one
existing `sayhi@mynanny.co.za` mailbox for sending and replies, with a separate
Google app password in each Render environment. A missing or failed SMTP
provider is recorded as a failed notification and must never be treated as a
delivered invoice email. Invoice emails link back to the authenticated V2
Placement screen; private storage URLs are not exposed as public attachments.

## Tests

    python -m pytest -q

Tests run against a fresh temp database per run (hermetic). Set
MYNANNY_TEST_USE_REAL_DB=1 to run against the local dev DB instead.

## Rollback

- App: Render "Rollback" to a previous deploy.
- Schema: `alembic downgrade -1` (run manually in a Render shell) - only safe
  if the migration has a real downgrade path; review before relying on it.
- Data: Render Postgres has automated daily backups; restore via dashboard.
