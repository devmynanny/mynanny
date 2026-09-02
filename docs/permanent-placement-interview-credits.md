# Permanent Placement interview credits

**Status:** Implemented locally on `codex/permanent-placements`  
**Updated:** 2 September 2026

## Family and nanny flow

- A parent may send interview invitations to any number of released candidate
  profiles.
- Sending an invitation does not use a credit.
- A credit is consumed only when the nanny accepts the interview invitation.
- The initial search includes five accepted interviews by default.
- Once all five are used, another nanny cannot accept until a credit is
  restored or an admin-approved replacement search begins.
- A nanny may decline without using a credit.

## Credit restoration

A consumed credit can be restored when:

- the nanny cancels an accepted interview; or
- admin records that the interview did not take place.

Every consumption and restoration creates an immutable ledger event containing
the placement, candidate, search cycle, actor, reason and time. Repeating the
same restoration is idempotent and cannot create extra credits.

Admin and the family see included, used and available credits on the same V2
Permanent Placements screen. Admin schedules an interview only after the nanny
has accepted the current invitation.

## Replacement cycle

An approved replacement starts a new interview-credit cycle with three credits
by default. Credits from the initial search do not roll into this cycle. The
case tracks how many replacements were approved and blocks a second included
replacement.

The credit limits and replacement allowance are frozen in the case's pricing
snapshot, so later admin configuration changes apply only to new cases.

## Interview completion and parent feedback

- Once admin schedules an accepted interview, the nanny can confirm arrival.
- The nanny can mark the interview completed, with or without an earlier
  arrival confirmation.
- Completion notifies the family and opens the feedback panel on the family
  case.
- The parent records a written interview impression and chooses Reject, Maybe,
  Request trial, Make an offer or Ask My Nanny.
- Maybe uses the frozen case rule, initially four days. Choosing Maybe again
  does not extend the original deadline.
- Trial and offer choices currently create managed next-step requests. The
  dated trial, offer acceptance and availability update are the next workflow
  slice and remain admin-mediated until implemented.

## Verification

Automated tests cover five successful acceptances, rejection of a sixth,
restoration for an interview that was not held, acceptance after restoration,
ledger balance and the existing privacy/payment journey. PostgreSQL migration
SQL is generated successfully; a live PostgreSQL migration remains part of the
UAT release gate.
