# Launch Readiness Sign-off

Status against the Production Readiness Checklist (MY_NANNY_PRODUCT_SPEC.md
section 18). Updated 2026-07-19. Test suite: 115 passing.

## Done in code (this workstream)

| Item | Status |
|---|---|
| Real migration tooling (Alembic) | DONE - baseline + message-column migration, preDeploy hook |
| Canonical status enum/state machine | DONE - central vocabularies + write guards on all 4 status columns |
| Structured requested_nannies_count | DONE - column, backfill, admin API |
| Expired advert cleanup + hiding | DONE - 30-min sweep + read-time filter, policy in APP_RULES 6A |
| Automated tests: booking, broadcast/accept, availability + 5h buffer, geofence, payments, webhook, cancellation, demerits | DONE - 115 tests, hermetic DB |
| Impersonation audit visibility | DONE - audit log + /admin/ops/impersonations |
| Monitoring for failed notifications + payment webhooks | DONE - /admin/ops/health + audit-logged webhook rejections |
| Notification reliability (policy matrix, delivery log, retries) | DONE |
| POPIA technical controls | DONE - uploaded ID documents access-controlled (were public), POPIA.md |
| Backup/restore plan | DONE - BACKUPS.md (restore drill still to be performed once) |
| Postgres production path | CODE DONE - render.yaml provisions mynanny-db; deploy pending |

## Blocking launch - needs David

| # | Action | Reference |
|---|---|---|
| 1 | Push to GitHub + deploy on Render (provisions Postgres, runs migrations) | DEPLOYMENT.md |
| 2 | Add PAYSTACK_SECRET_KEY (test) to Render + run the 7-step sandbox sequence | PAYSTACK_TEST_PLAN.md |
| 3 | Swap to live Paystack key after sandbox passes (requires Paystack business verification) | PAYSTACK_TEST_PLAN.md |
| 4 | Set JWT_SECRET / AUTH_SECRET / ADMIN_API_KEY as strong values in Render | DEPLOYMENT.md |

## Non-blocking, do soon after launch

| # | Action | Owner |
|---|---|---|
| 1 | Twilio WhatsApp: account, env vars, WhatsApp Business sender approval (Meta lead time - start now) | David |
| 2 | POPIA company obligations: Information Officer registration, privacy policy + PAIA manual page, express consent checkbox at signup | David + attorney |
| 3 | Support policy decisions: disputes, late arrivals, no-show handling wording; nanny demerit appeals; transport policy | David + Mariette |
| 4 | Perform one backup restore drill | David |
| 5 | Browser walkthrough of all dashboards on mobile for visual polish punch list (code-side polish done: shared labels, empty states verified, viewport fixes) | David |
| 6 | Verify Google Maps/Calendar failure behavior in staging (calendar sync errors are stored on bookings, not verified end-to-end) | David |
| 7 | Full timezone audit pass in staging with real SA-time bookings crossing midnight | David + follow-up fixes if found |

## Known deferred product decisions (intentionally parked)

- Multi-nanny acceptance filling up to requested_nannies_count (currently single winner by rating)
- Nanny demerit appeals process
- Minimum rating floor for permanent removal
- Transport policy
