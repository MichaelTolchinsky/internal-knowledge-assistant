# Log Retention Policy

Application logs are retained for 30 days in the hot storage tier (searchable via the internal
logging dashboard) and then automatically archived to cold storage for an additional 11 months,
for a total retention period of 12 months before permanent deletion.

Logs containing personally identifiable information (PII) - such as customer email addresses in
support-ticket-related log lines - are redacted at ingestion time before they ever reach hot
storage, not after the fact. Redaction is irreversible; there is no way to recover the original
unredacted value later, even for debugging purposes.

Security-relevant audit logs (authentication events, permission changes, credential rotations)
follow a separate, longer retention policy of 7 years to satisfy compliance requirements, and are
stored in a write-once, append-only log store distinct from general application logs.

Engineers can request an extended hold on specific log ranges (e.g. during an active incident
investigation) by filing a retention-hold request in the logging dashboard; holds pause the
automatic deletion for the specified range until the hold is explicitly released.
