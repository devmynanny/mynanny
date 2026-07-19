# MyNanny Deployment Guide

## Architecture

- Web service: FastAPI on Render (render.yaml), uvicorn.
- Database: managed Render Postgres (`mynanny-db`). SQLite is LOCAL DEV ONLY.
- Uploads: persistent Render disk mounted at `app/static/uploads` (documents, photos). The database no longer lives on this disk.
- Schema management:
  - Postgres: Alembic only. `alembic upgrade head` runs automatically before each deploy (`preDeployCommand`).
  - SQLite (local dev): `create_all` + legacy `ensure_*` functions run at app startup, unchanged workflow.

## Environment variables (Render dashboard, sync: false)

| Key | Purpose |
|---|---|
| DATABASE_URL | Injected automatically from the mynanny-db database |
| ADMIN_API_KEY | Admin API access |
| JWT_SECRET | Token signing |
| AUTH_SECRET | Auth cookies |
| PAYSTACK_SECRET_KEY | Live Paystack secret key (sk_live_...) |

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

## Local development

    pip install -r requirements.txt
    uvicorn app.main:app --reload        # uses sqlite:///./nanny_app.db

## Tests

    python -m pytest -q

Tests run against a fresh temp database per run (hermetic). Set
MYNANNY_TEST_USE_REAL_DB=1 to run against the local dev DB instead.

## Rollback

- App: Render "Rollback" to a previous deploy.
- Schema: `alembic downgrade -1` (run manually in a Render shell) - only safe
  if the migration has a real downgrade path; review before relying on it.
- Data: Render Postgres has automated daily backups; restore via dashboard.
