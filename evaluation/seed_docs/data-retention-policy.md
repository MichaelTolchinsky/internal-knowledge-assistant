# Customer Data Retention Policy

Customer account data is retained for the full duration of an active subscription, plus 90 days
after cancellation, to allow for accidental-cancellation recovery. After the 90-day window,
customer data is permanently deleted from all production systems, including backups, once the
next backup rotation cycle completes.

A customer can request early deletion of their data at any time during the 90-day post-
cancellation window by submitting a data-deletion request through support - early deletion
requests are processed within 5 business days and, once processed, cannot be undone or reversed.

Aggregated, anonymized usage statistics (e.g. "average requests per day across all customers")
are exempt from the deletion policy and may be retained indefinitely, since they no longer
identify any individual customer or account.

Billing records are retained for 7 years regardless of subscription or deletion status, to
satisfy financial and tax record-keeping requirements - this is the one category of data not
covered by the standard 90-day post-cancellation deletion window.

Data-deletion requests are logged in the security-audit trail described in the log retention
policy doc, and that audit record itself is retained for 7 years even after the underlying
customer data is deleted.
