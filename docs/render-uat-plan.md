# MyNanny Render UAT plan

**Status:** Design prepared; no UAT resource has been created.

**Updated:** 2 September 2026

## 1. Why Render remains the application platform

MyNanny production already uses a Render Blueprint for the FastAPI backend,
Next.js V2 application and PostgreSQL database. Rebuilding those components in
AWS ECS and RDS would duplicate hosting, release tooling, TLS, logs, rollbacks
and managed database operations.

Sprint 8 therefore keeps:

- Render for the backend, V2 application and PostgreSQL;
- AWS S3 with an isolated `uat/` object prefix and UAT-scoped credentials;
- the existing `devmynanny/mynanny` GitHub repository as the source of truth;
  and
- Paystack Test mode in UAT and Live mode only in production.

## 2. Current production inventory and actual cost

The signed-in Render dashboard was inspected on 1 September 2026 without
opening secret values or changing resources.

| Production component | Current plan | Approximate monthly cost |
| --- | --- | ---: |
| `mynanny` backend | 0.5 CPU, 512 MB | $7.00 |
| Backend legacy 1 GB disk | 1 GB | $0.22 |
| `mynanny-v2` | 0.5 CPU, 512 MB | $7.00 |
| `mynanny-db` compute | 0.1 CPU, 256 MB | $6.00 |
| `mynanny-db` storage | 15 GB | $4.50 |
| **Approximate recurring total** | | **$24.72-$24.75** |

The August invoice was $22.87 because resources were introduced during the
month. The current month-to-date breakdown and hourly rates reconcile to an
approximately $24.75 full month before unusual bandwidth or tax adjustments.

## 3. Approved cost-conscious UAT environment

| UAT component | Proposed plan | Approximate monthly cost |
| --- | --- | ---: |
| `mynanny-uat` backend | 0.5 CPU, 512 MB | $7.00 |
| `mynanny-v2-uat` | 0.5 CPU, 512 MB | $7.00 |
| Logical `mynanny_uat` database on existing Postgres instance | shared | $0.00 added |
| Isolated `uat/` objects in the existing private S3 bucket | usage based | expected to be small during UAT |
| **Approximate added fixed Render cost** | | **$14.00/month** |

The expected combined Render total is therefore about $38.75/month while UAT
is retained. The rand amount varies with the exchange rate and card charges.
The cost gate is expressed in US dollars because Render bills in US dollars.

Free Render services are not recommended for this permanent UAT environment:
sleeping services and time-limited free database behaviour make payment,
webhook, reminder and multi-day placement testing unreliable. Temporary preview
environments can be considered later for individual proposed changes, but they
do not replace the stable business UAT environment.

## 4. Isolation controls

UAT and production must have separate:

- Render services and logical PostgreSQL databases;
- S3 object prefixes and scoped AWS application credentials;
- JWT, authentication and admin secrets;
- Paystack keys and webhook endpoints;
- document objects, invoices and signature evidence;
- seed users and placement records; and
- email/notification configuration.

UAT and production share one paid Postgres instance to avoid a second fixed
database charge. The UAT application rewrites the injected connection to the
logical `mynanny_uat` database. Both pre-deploy and application startup run a
fail-closed target check. If the resolved database is the instance's production
database, the release stops before migrations or application startup.

The shared instance remains a deliberate compromise: UAT load can still affect
production compute and backups share the same instance lifecycle. UAT therefore
uses synthetic data, automated notifications remain disabled, and load testing
is prohibited. A dedicated UAT database instance becomes mandatory if usage or
the team grows beyond controlled acceptance testing.

## 5. Safe deployment sequence

1. Reconcile the approved Permanent Placement implementation into this repo.
2. Add the UAT banner and environment safety tests.
3. Validate `render.uat.yaml` without applying it.
4. Run backend, frontend and migration tests against PostgreSQL.
5. Review the expected $14.00 monthly addition and obtain explicit approval.
6. Create an UAT-only S3 application identity restricted to the shared bucket's
   `uat/*` objects.
7. Create the separate Render UAT Blueprint from `render.uat.yaml`; its
   idempotent pre-deploy step creates `mynanny_uat` on the existing instance.
8. Enter the Paystack Test, SMTP and UAT-scoped S3 credentials through Render;
   never commit them.
9. Deploy with external notifications and Permanent Placement disabled.
10. Run short-term regression, auth, storage and Paystack Test smoke checks.
11. Configure `uat.app.mynanny.co.za` and HTTPS.
12. Enable Permanent Placement in UAT only and begin the signed UAT checklist.

## 6. Release and rollback

- Production continues to auto-deploy only from its approved `main` branch.
- UAT deploys from the dedicated reviewed branch configured in its Blueprint.
- A failed UAT build cannot change production resources or data.
- Database migrations run before a release becomes live.
- Permanent Placement remains behind the database feature flag.
- The first response to a placement defect is to disable the feature while
  keeping short-term care online.
- Application rollback uses Render's previous deploy. Database restore is used
  only for confirmed data damage, not as the default application rollback.

## 7. Approval gate

Preparing and committing the UAT Blueprint does not incur a charge. Creating
the Render Blueprint resources does. Before applying it, confirm:

- an added Render ceiling of $14/month before unusual usage;
- the UAT service names and Git branch;
- control of DNS for `mynanny.co.za`;
- synthetic UAT data only;
- the Paystack Test account/key owner; and
- who may approve the later production promotion.

## 8. Findings that block applying the Blueprint

1. **Permanent Placement is reconciled locally but not yet proven on a real
   Render PostgreSQL UAT database.** All new migrations render valid PostgreSQL
   SQL and local workflow/regression tests pass. The complete migration chain,
   storage integration and Paystack Test webhook still need a real isolated UAT
   deployment and review.
2. **The production PostgreSQL public allow-list is broad.** It currently allows
   `0.0.0.0/0`. Credentials are still required, but the rule should be narrowed
   after confirming that no approved developer or migration process needs
   external access. UAT is already designed with no public database access.
3. **The V2 build dependency audit reports four high-severity findings.** They
   resolve through the Prisma development/build toolchain, including
   `deepmerge-ts` and `mysql2`. MyNanny uses PostgreSQL and the flagged packages
   are not the deployed application database driver, which reduces direct
   runtime exposure, but the build-chain risk must be resolved or formally
   accepted before UAT sign-off. Do not run an automatic forced downgrade.
4. **Billing identity is intentionally unset.** Admin must enter the real legal
   issuer name, business address, billing email, registration number where
   applicable, VAT status and VAT number where applicable. Until that readiness
   gate passes, invoices remain drafts and no invoice PDF/email is issued.
