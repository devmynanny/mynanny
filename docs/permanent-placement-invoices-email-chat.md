# Permanent Placement invoices, email and protected chat

**Status:** Implemented locally for Permanent Placement; not yet deployed to UAT  
**Updated:** 2 September 2026

## 1. Concierge payment milestones

Fresh Concierge searches use three payments, all read from the case's frozen
admin pricing snapshot:

| Milestone | Approved starting amount | When due |
| --- | ---: | --- |
| Consultation | R550 | When the family opens the search |
| Engagement | R2,500 | After admin qualifies the brief |
| Placement balance | R7,000 | After the nanny accepts the final offer |

The placement service remains R9,500 in total. Admin can change every amount
for future searches without repricing an existing search, payment or invoice.

For an upgrade after the Self-Match R1,500 interview package has been paid, the
package credit reduces the remaining Concierge service. Under the approved
defaults this produces R1,000 engagement plus R7,000 placement balance. If a
future engagement fee is lower than the credit, the unused credit continues to
reduce the balance. No calculated payment can become negative.

## 2. Invoice and receipt lifecycle

1. Creating a payment also creates one linked invoice draft with the exact
   payment amount, fee label, customer identity and placement reference.
2. A draft cannot be issued until admin completes the billing readiness gate.
3. On Paystack initialisation, a ready draft receives a sequential invoice
   number and an immutable issuer/customer/line-item snapshot. The generated PDF
   and its SHA-256 hash are stored.
4. Verified Paystack or explicitly recorded offline/test payment marks the
   invoice paid and creates a sequential receipt PDF and hash.
5. The parent sees invoice and receipt downloads in the existing V2 Placement
   screen. Admin sees the same documents and can issue or resend the email.
6. Document email events go through the existing notification controls and
   notification log and link to the authenticated V2 Placement screen. A
   missing or failed SMTP provider is recorded as failed rather than delivered.
   Automated tests replace notification delivery and never contact a real
   provider.

Issued PDFs are stored under a parent-owned private path. Anonymous users and a
different logged-in parent receive no access; the document owner and authorised
admin can download it. The sample at `output/pdf/permanent-placement-invoice-sample.pdf`
contains synthetic UAT data only and is used for visual QA.

## 3. Billing readiness gate

Admin configures these values on the existing V2 Permanent Placements admin
screen:

- legal issuer and trading names;
- billing email and phone;
- business address and registration number where applicable;
- invoice prefix;
- confirmed VAT registration status;
- VAT number and rate if registered; and
- confirmation that customer-facing configured fees include VAT.

The repository deliberately contains no guessed legal entity or VAT value. A
missing required field leaves invoices in draft. If the issuer is VAT registered,
the PDF calculates the VAT portion from the configured VAT-inclusive total; it
does not increase a frozen payment after the client has seen it.

## 4. Temporary interview communication

- A nanny accepting an interview opens an eligible communication window.
- Parent and nanny must each accept the same contact rules.
- Only after both accept can they see the other party's phone/email and use the
  direct in-app chat for interview logistics.
- Home addresses and protected profile documents are never revealed.
- Nanny check-in or interview completion immediately hides contact details and
  disables new direct messages. Existing message history remains auditable.
- Trials, offers, salary negotiation and later questions are handled through My
  Nanny administration after the lock.
- Re-inviting a candidate resets both acknowledgements so stale consent cannot
  silently reopen a later contact window.

## 5. Offer and calendar control

The final offer records salary, start date, working days, working hours and
terms. On nanny acceptance, each agreed working day is blocked in full for the
next year in the short-term availability calendar. Existing calendar history is
preserved and days outside the permanent role remain available. For example, a
Monday-to-Friday offer leaves Saturday and Sunday available for the nanny to
publish short-term availability.

## 6. Verification completed locally

- 12 focused Permanent Placement tests pass.
- 241 backend tests pass, including existing short-term booking workflows.
- V2 lint, TypeScript checks and production build pass.
- New contact/chat and billing migrations render valid PostgreSQL SQL.
- Invoice and receipt generation, immutable amount, private download ownership,
  contact consent, chat lock and calendar restructuring have automated coverage.
- The synthetic A4 invoice sample was rendered to an image and visually checked
  for clipping, overlap, spacing and legibility.

## 7. Remaining before UAT

- Run the full migration chain on an isolated PostgreSQL UAT database.
- Enter and approve the real billing identity and VAT status.
- Configure private UAT S3, Paystack Test and UAT notification controls.
- Generate separate Google app passwords for UAT and production and store each
  only as `SMTP_PASS` in its Render environment. The single sender and reply
  mailbox is `sayhi@mynanny.co.za`; the existing production Render service
  currently has no email-provider variables.
- Add the normal short-term booking invoice to prove the billing core is shared.
- Add invoice void/reissue, credit-note/refund documents and the transactional
  email retry/delivery-exception queue.
- Obtain the explicit Render cost approval before creating paid UAT resources.
