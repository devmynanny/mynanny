# MyNanny POPIA Compliance Position

Operational reference for how MyNanny handles personal information under the
Protection of Personal Information Act. Review with a privacy attorney before
scale; this documents the technical posture and operating procedures.

## Personal information held

| Category | Examples | Where |
|---|---|---|
| Identity (special care) | SA ID numbers, passport/permit numbers and scans, police clearance | nanny_profiles + uploads disk |
| Children's information (special care) | Kids count/ages, special notes, family photos | parent_profiles |
| Contact & location | Phone, email, home address, GPS coordinates | users, parent_locations |
| Financial | Bank details (tokenized/masked), card last4/brand, Paystack codes | nanny_bank_accounts, users |
| Operational | Bookings, check-in GPS points, reviews, cancellation history | bookings, reviews, demerit log |

Never stored: full card numbers (Paystack holds them; we keep only the
authorization code + last4/brand).

## Technical controls in place

- Uploaded identity/vetting documents (`id_`, `passport_`, `permit_`, `police_`,
  `drivers_license_`, `reference_`, `certificate_` files) are access-controlled:
  only the owning user and admins can retrieve them. All other uploads
  (profile/family photos) require an authenticated session. Enforced in
  middleware; unauthenticated access returns 401/403.
- Upload URLs additionally contain unguessable UUIDs.
- Bank account numbers masked (`account_number_token`), full numbers not
  returned by APIs.
- Contact-info redaction (`redact_contact_info`) strips phone/email from
  free-text fields so parties cannot bypass the platform.
- Parent full address revealed to a nanny only after acceptance; suburb only
  before.
- Audit logging on profile changes, booking status changes, admin actions,
  and every impersonation session (incl. IP).
- CSRF protection, JWT auth, admin-only endpoints gated server-side.
- Postgres with daily backups; access via Render env-scoped credentials.

## Retention policy (operating rule)

- Active accounts: data retained while the account is active.
- Deactivated nannies/parents: identity documents deleted 12 months after
  deactivation (manual sweep for now - see BACKUPS.md drill cadence);
  financial/booking records kept 5 years (tax and dispute obligations).
- Notification and audit logs: retained 24 months.
- Backups age out on the Render retention schedule.

## Data subject requests (POPIA s23/24)

- Access/correction: user can view and edit their profile in-app; anything
  else via support email, verified against the account email, fulfilled
  within 30 days.
- Deletion: on request, delete identity documents and anonymize the user row
  (name -> "Deleted user", contact fields nulled) while retaining booking and
  financial records with the anonymized reference.

## Breach response

1. Contain: rotate secrets (JWT, admin key, Paystack, Twilio) in Render;
   suspend affected accounts if needed.
2. Assess scope from audit_logs and notification_log.
3. Notify the Information Regulator and affected data subjects as soon as
   reasonably possible (POPIA s22) with what was accessed and mitigation.
4. Post-mortem entry in this file's changelog.

## Operator (company) obligations still open

- Appoint/register an Information Officer with the Information Regulator.
- Publish a privacy policy + PAIA manual on the website and link at signup.
- Add explicit consent checkbox at signup for processing of children's data
  and identity documents (signup currently implies consent; make it express).
- Automate the deactivated-account document deletion sweep.
