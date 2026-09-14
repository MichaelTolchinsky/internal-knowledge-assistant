# API Versioning and Deprecation

The API is versioned in the URL path (e.g. `/v2/`), and only the two most recent major versions
are supported at any given time - when a new major version ships, the oldest supported version
enters a 12-month deprecation window before being shut off entirely.

During the deprecation window, deprecated-version requests continue to work unchanged, but every
response includes a `Deprecation` header with the shutoff date, and the account owner receives a
one-time email notification when the window begins. There are no recurring reminder emails after
that first notification - the `Deprecation` header is the ongoing signal.

Minor, backward-compatible additions (new optional fields, new endpoints) ship continuously
within the current major version and do not require a version bump or any deprecation process,
since existing integrations are guaranteed not to break from additive changes.

Breaking changes - removing a field, changing a field's type, or changing default behavior -
always require a new major version; they are never introduced into an existing version, even
behind a feature flag.

Customers can check which API version an integration is using from the "API Usage" tab in the
admin console, which also flags any calls still hitting a deprecated version so they can migrate
before the shutoff date.
