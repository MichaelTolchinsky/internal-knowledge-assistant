# Webhook Troubleshooting

Webhook deliveries are retried automatically on failure using exponential backoff: 1 minute, 5
minutes, 30 minutes, 2 hours, and a final attempt at 12 hours, after which the delivery is marked
permanently failed and no further retries occur.

A delivery counts as failed if the receiving endpoint does not return an HTTP 2xx status within 5
seconds, or if the connection cannot be established at all. A slow endpoint that eventually
responds with a 2xx after the 5-second timeout is still treated as a failure for that attempt,
even though the request technically succeeded server-side.

The most common cause of "missing" webhooks reported by customers is an endpoint that started
returning non-2xx responses (often a 401 after a credential change on the customer's side) - the
webhook delivery log in the admin console shows the HTTP status code and response body for every
attempt, which is the first place to check.

Customers can manually replay any individual failed delivery from the webhook delivery log within
30 days of the original attempt; deliveries older than 30 days are no longer available to replay
and the underlying event data is not stored anywhere else.

Webhook payloads are signed with an HMAC-SHA256 signature in the `X-Webhook-Signature` header,
and the signing secret can be rotated independently of API credentials from the same admin
console page.
