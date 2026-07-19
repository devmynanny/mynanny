# MyNanny Backup & Restore Plan

## What needs protecting

| Asset | Where it lives | Backup mechanism |
|---|---|---|
| Database (users, bookings, payments, audit) | Render Postgres `mynanny-db` | Render automated daily backups (retained per plan) + manual pre-change snapshots |
| Uploaded documents (IDs, passports, permits, police clearance, photos) | Render disk at `app/static/uploads` | Render disk snapshots + periodic manual export |
| Code | GitHub devmynanny/mynanny | Git history (push regularly) |
| Secrets (Paystack, JWT, Twilio) | Render env vars | Keep an offline copy in a password manager - env vars are NOT in git |

## Database

Automated: Render Postgres takes daily automated backups. Verify retention in
the Render dashboard (Database -> Backups) and upgrade the plan if launch
volume warrants point-in-time recovery.

Manual snapshot before risky changes (migrations, bulk updates):

    pg_dump "$DATABASE_URL" -Fc -f mynanny_$(date +%Y%m%d_%H%M).dump

Restore:

    pg_restore --clean --no-owner -d "$DATABASE_URL" mynanny_YYYYMMDD_HHMM.dump

## Uploaded documents

The uploads disk holds POPIA-sensitive identity documents - treat exports
with the same care as the database.

Monthly manual export (Render shell on the web service):

    tar czf /tmp/uploads_$(date +%Y%m%d).tgz -C /opt/render/project/src/app/static uploads
    # download via render CLI or scp equivalent, store encrypted

## Restore drill (do this once before launch, then quarterly)

1. Restore latest DB backup into a scratch Postgres instance.
2. Point a local app instance at it (`DATABASE_URL=...`), log in as admin.
3. Verify: user counts, a recent booking's money fields, an uploaded document opens.
4. Record the drill date and any gaps found.

## Recovery objectives (current posture)

- RPO (max data loss): 24h (daily backups). If real bookings ramp up, move to
  point-in-time recovery for an RPO of minutes.
- RTO (time to restore): ~1h manual. Acceptable at launch scale.

## Ops monitoring

`GET /admin/ops/health` surfaces failure queues (undelivered notifications,
rejected webhooks, stuck payouts, refunds awaiting review, stale adverts,
impersonation counts). Check it daily until volume justifies alerting;
`GET /admin/ops/impersonations` lists recent impersonation sessions.
