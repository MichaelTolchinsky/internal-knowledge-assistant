# Auth & Credential Rotation

Rotate production API credentials every 90 days via the admin console. Credentials that are not
rotated within 120 days of issuance are automatically revoked, and any service still using a
revoked credential will start receiving HTTP 401 responses immediately.

Rotating a credential does not require downtime - both the old and new credential remain valid
for a 24-hour overlap window so dependent services can be updated without an outage. After the
overlap window closes, the old credential is deleted and cannot be recovered; if it's still in
use somewhere at that point, that integration will start failing.

Service accounts used by internal automation (CI pipelines, scheduled jobs) follow the same
90-day rotation policy as customer-facing API keys - there is no exemption for internal tooling.
Rotation reminders are sent by email to the account owner 14 days, 7 days, and 1 day before the
90-day mark.

If a credential is suspected to be compromised, it must be revoked immediately through the admin
console rather than waiting for the scheduled rotation - immediate revocation does not have the
24-hour overlap window, since the goal is to cut off access as fast as possible.
