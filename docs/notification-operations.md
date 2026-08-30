# Notification operations

## Service ownership

- Render service `mynanny` is the API, database-facing application, Twilio sender and scheduled-job runner.
- Render service `mynanny-v2` is the user and admin web application.
- The existing Render names and URLs are intentionally retained because Twilio callbacks, frontend API routing and saved links depend on them.

## Controls

- Admin > Settings is the normal source of truth for system-generated outbound notifications.
- The Render variable `AUTOMATED_NOTIFICATIONS_ENABLED` is a hard emergency override. When it is false, Admin cannot turn delivery on.
- Turning system notifications off does not disable in-app notifications, manual messages sent from the Communicator, or security messages such as password resets and admin invitations.
- Test mode redirects system-generated external messages to one nominated WhatsApp number and prefixes the free-form message with its intended recipient. The test number must have an open WhatsApp customer-service window.

## Duplicate protection

- A system notification is claimed atomically using recipient, event type and reference ID before delivery.
- Scheduled jobs also acquire a database lease so only one application instance starts a sweep in a given interval.
- Duty reminders and escalations use one claim per booking and recipient. They do not repeat every five minutes.

## Monitoring

- Admin > Settings shows effective delivery status, test routing, recent destinations, provider status and failures.
- A warning appears when the number of external attempts in the last hour reaches the configured threshold.
- Twilio delivery callbacks update the original notification log record from accepted/sent to delivered/read or failed.
