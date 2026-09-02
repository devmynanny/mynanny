# MyNanny V2 integrated delivery roadmap

**Status:** Active programme. The core Permanent Placement journey, protected
interview chat and first invoice/receipt slice are implemented locally; paid
UAT provisioning is not approved yet.

**Updated:** 2 September 2026

## 1. Programme outcome

MyNanny will operate short-term bookings and Permanent Placement from the same
V2 landing page, accounts and administration application. Permanent Placement
is an additional service journey, not a separate website or database.

The programme also includes the shared commercial foundation needed by both
service lines:

- service orders and price snapshots;
- invoices, receipts, credit notes and refunds;
- Paystack payment verification and reconciliation;
- agreements and native signatures;
- email delivery, reminders and failure handling;
- protected in-app communication and admin-mediated support;
- private document storage and authorised downloads;
- audit history, reporting and operational documentation; and
- a UAT-to-production release path.

## 2. Current baseline and release warning

Production already runs on Render from `devmynanny/mynanny`:

- `mynanny`: FastAPI backend;
- `mynanny-v2`: Next.js V2 application;
- `mynanny-db`: managed PostgreSQL; and
- a private AWS S3 bucket for production uploads.

The `codex/permanent-placements` branch contains a useful pilot, but it is not
ready for UAT or production. The approved pricing defaults and the 40-day
replacement terminology have now been reconciled. Admin can edit every
Permanent Placement amount, while each new case freezes its own price snapshot
so an existing client's fees cannot change retroactively.

Accepted-interview credit accounting, auditable restoration, nanny check-in,
interview completion, parent feedback, paid trials, formal offers and nanny
availability restructuring are implemented locally. Temporary contact details
and direct in-app interview chat now require both parties to accept the rules;
both lock when the nanny checks in or completes the interview.

The shared billing core now creates a draft from every Permanent Placement
payment, issues an immutable private PDF once admin billing details are ready,
allocates verified Paystack/manual payments, creates a receipt and records the
email request. The short-term invoice proof, void/reissue lifecycle,
transactional email outbox and delivery-exception queue remain future work.

A more complete Permanent Placement implementation exists in an older local
working copy. It must be reconciled into this production repository in small,
reviewed changes. It must not be copied over the current application wholesale.

## 3. Settled Permanent Placement direction

### Self-Match

- R350 activates a limited profile search.
- The R350 is credited toward the R1,500 interview package, leaving an R1,150
  top-up when the activation was paid and unused as agreed.
- Parents can browse and invite any number of nannies, but only five accepted
  interviews consume the package credits.
- A cancelled or unheld interview restores a credit through a recorded,
  auditable rule.
- The placement fee is R1,500 when an accepted offer becomes a placement.
- One admin-approved replacement is available within 40 days, with three
  replacement interview credits. A second replacement is not included.

### Concierge

- R550 consultation fee.
- R9,500 placement service fee.
- Mariette manages consultations, candidate selection, interview scheduling,
  Uber arrangements, weekend work, salary negotiation, offers and ongoing
  client consultation.
- The R9,500 placement service is now collected as a configurable R2,500
  engagement milestone and R7,000 balance after offer acceptance.
- A Self-Match client upgrading after paying the R1,500 interview package is
  credited against the remaining Concierge service. With the approved defaults,
  that leaves R1,000 engagement and R7,000 balance.

### Candidate privacy and communication

- Permanent Placement never reuses the unrestricted short-term nanny view.
- Limited Permanent Placement profiles exclude phone numbers, exact addresses,
  identity numbers and protected documents.
- Interview acceptance can open the specifically approved contact window.
- Contact details lock again when the nanny checks in or completes the
  interview.
- Both parties accept the same contact rules before the window opens.
- After the interview, parent-to-nanny chat is restricted at the configured
  stages and negotiation or support is routed through MyNanny administration.
- Face-to-face contact sharing cannot be technically prevented; terms, audit
  history and operational follow-up provide the control boundary.

### Interview, trial and offer journey

- The nanny can check in and mark an interview completed.
- The parent records feedback and chooses reject, maybe, trial, make an offer
  or admin assistance.
- Maybe expires after four days unless the business changes the configured
  period.
- Trial dates are checked against the nanny calendar and can be accepted,
  declined or counter-proposed.
- Offers contain start date, working days and hours and can be accepted,
  declined or referred to admin.
- Once an offer is accepted, the nanny restructures recurring availability. A
  Monday-to-Friday permanent role can still leave Saturday and Sunday available
  for short-term work.

## 4. Sprint sequence

### Sprint 8 - production-repository reconciliation and Render UAT foundation

1. Reconcile the approved business rules and the more complete local workflow
   into this production branch without replacing existing short-term code.
2. Preserve current route shapes and production migrations.
3. Add a visible UAT banner and environment-safe defaults.
4. Prepare and validate `render.uat.yaml`.
5. Create a separate private UAT S3 bucket and restricted application identity.
6. Create paid Render UAT resources only after the cost gate is approved.
7. Use a separate Render PostgreSQL database with no public inbound access.
8. Add Paystack Test credentials and a UAT webhook; never copy the live secret.
9. Seed synthetic parents, nannies and admins only.
10. Run migrations, health checks and short-term regression smoke tests before
    enabling Permanent Placement in UAT.

Exit gate: the correct repository deploys to an isolated UAT environment, the
same V2 landing/admin applications serve both services, payments remain in Test
mode, private data is separated, rollback is rehearsed, and every known pricing
or workflow mismatch is closed.

### Sprint 9 - shared order, invoice and Paystack core

Status: Permanent Placement slice implemented locally; shared short-term proof
and lifecycle exceptions remain open.

- Service orders for short-term and permanent work.
- Frozen price and policy snapshots.
- Invoice numbering, preview, issue, void and reissue.
- Immutable invoice PDF and parent portal history.
- Verified Paystack allocation, receipt creation and exception handling.
- Self-Match R350 activation and R1,150 interview-package top-up.
- One normal short-term booking invoice to prove the engine is shared.

### Sprint 10 - short-term documents and financial changes

- Booking confirmations and nanny assignment acceptance.
- Changes, overtime, transport and approved expenses.
- Cancellations, credit notes and refunds.
- Document history and the disabled short-term-to-permanent conversion trigger.

### Sprint 11 - agreements and native signatures

- Versioned agreement templates and approved variables.
- Immutable document snapshots and hashes.
- Authenticated acknowledgement and drawn touch/mouse signatures.
- Signer order, expiry, decline, void and supersede.
- Completed PDF, signing evidence and protected access.

### Sprint 12 - email, reminders and communication exceptions

- Transactional outbox and retry worker.
- Invoice, receipt, agreement, reminder and completion messages.
- Secure, short-lived links rather than public attachments.
- Delivery, bounce, complaint and failure states.
- Admin resend and delivery-exception queue.
- In-app notification mirrors and the permanent-chat restriction rules.

### Sprint 13 - complete Permanent Placement and Concierge integration

- Interview/contact-rule acceptance and contact-window enforcement.
- Five accepted-interview credits and restoration rules.
- Maybe, trial, offer, salary negotiation and calendar restructuring.
- Self-Match placement payment and automatic-charge/fallback handling.
- 40-day replacement, three replacement credits and one-replacement limit.
- Concierge tasks, consultations, Uber/expense handling and fee milestones.
- Placement agreements, signatures, documents and prerequisite gates.

### Sprint 14 - integrated business UAT

David validates customer, payment and commercial behaviour. Mariette validates
placement operations, Concierge work, negotiation, support and the admin
journey. Existing short-term booking, payment, availability and communication
flows must pass alongside the complete Permanent Placement scenarios.

### Sprint 15 - production readiness

- Use the existing Render production platform and private production S3 bucket.
- Promote only the UAT-approved code and migration set.
- Configure Paystack Live and the production email domain separately.
- Rehearse backup, restore, document recovery and rollback.
- Restrict production database public access after confirming no approved
  external dependency needs it.
- Deploy with new features disabled and pass short-term production smoke tests.

### Sprint 16 - controlled production pilot

- Take a pre-release database backup.
- Enable Permanent Placement for an invited Gauteng pilot.
- Monitor one Self-Match and one Concierge journey end to end.
- Review payments, webhooks, documents, email, chat, admin work and support
  daily before wider Gauteng availability.

## 5. Documentation gate for every sprint

A sprint is not complete until the repository records:

1. business rules and open decisions;
2. technical design and integration boundaries;
3. migrations and rollback;
4. security, privacy and retention;
5. automated and UAT evidence;
6. admin and support runbooks;
7. release version, configuration and approvers; and
8. blockers with an owner and decision date.

## 6. Non-negotiable release gates

- No production data in UAT; use synthetic data unless a separately approved,
  anonymised extract is required.
- No live Paystack key or live charge in UAT.
- No secret in Git or a PDF.
- No Permanent Placement release while the approved price, interview-credit,
  replacement, privacy or contact rules differ from the implementation.
- No paid infrastructure creation without a cost approval.
- No production launch without David and Mariette's recorded UAT sign-off.
