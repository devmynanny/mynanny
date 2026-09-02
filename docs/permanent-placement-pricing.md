# Permanent Placement pricing configuration

**Status:** Implemented locally on `codex/permanent-placements`  
**Updated:** 2 September 2026

## Admin ownership

Permanent Placement pricing is maintained on the existing V2 Permanent
Placements admin screen. Admin enters amounts in rand; the API stores them in
cents. Changes apply to new searches only.

| Amount | Approved starting value |
| --- | ---: |
| Self-Match search activation | R350 |
| Self-Match interview package total | R1,500 |
| Self-Match top-up after the activation credit | R1,150 |
| Self-Match successful placement | R1,500 |
| Concierge consultation | R550 |
| Concierge engagement invoice | R2,500 |
| Concierge placement balance | R7,000 |
| Concierge placement service total | R9,500 |

The Self-Match top-up is calculated from the package total less the activation
fee when the activation-credit switch is on. It is not stored as a separate
admin amount, which prevents the displayed figures from falling out of balance.
The two Concierge placement amounts make up the configurable R9,500 placement
service. The workflow now collects R2,500 when a qualified Concierge brief is
engaged and R7,000 after the nanny accepts the final offer. The separate R550
consultation remains the opening payment.

If a family upgrades from Self-Match after paying the full R1,500 interview
package, that R1,500 is credited against the Concierge placement service. With
the approved defaults, the next payments are R1,000 engagement and R7,000
balance. The calculation also handles future admin amount changes without
creating a negative payment.

## Price protection for existing cases

When a family creates a Permanent Placement brief, the system stores a price
snapshot on that case. All later fees, limits and replacement dates for that
case use the snapshot rather than the current admin settings.

When a payment becomes due, its exact amount is also stored on the payment.
Editing admin pricing cannot reprice a pending, initialised or paid payment.
This makes Paystack verification, invoices, receipts and later reconciliation
auditable.

Existing cases created before the pricing migration receive a legacy snapshot
during the PostgreSQL migration so the system does not rewrite terms already
shown to those clients.

## Validation and release checks

- Amounts may be R0 or more.
- If activation is credited, the interview package cannot be lower than the
  activation fee.
- The public pricing cards read the current admin settings.
- A case detail reads its frozen snapshot.
- UAT must test admin change, old-case retention, new-case pricing, Paystack
  initialisation and invoice/receipt rendering before production approval.
- A configured R0 milestone is automatically recorded as waived and advances
  the case without trying to open a zero-value Paystack transaction.
- The historical Alembic chain currently has an unrelated SQLite-only replay
  failure in the earlier messaging migration. Render UAT and production use
  PostgreSQL, where the full migration chain must be tested before release.
