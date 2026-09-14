# Production Database Access

Direct production database access is not granted by default to any engineer, including senior
engineers - all routine data questions should go through the read-only reporting replica, which
any engineer can query without a separate request.

For cases that genuinely require primary-database access (e.g. a one-off manual data fix), an
engineer must file a time-boxed access request through the internal access-management tool,
naming a specific reason and a maximum duration of 4 hours. Access requests longer than 4 hours
require sign-off from the engineering director, not just the requester's manager.

All primary-database sessions granted this way are automatically recorded (query text and
results) for audit purposes, and the access is automatically revoked at the end of the requested
window even if the engineer is still connected - there is no way to extend an active session
without filing a new request.

Read-only replica access does not expire and does not require a request, but write access to the
replica does not exist under any circumstances - it is a hard read-only copy used specifically to
keep ad-hoc queries off the primary database.
