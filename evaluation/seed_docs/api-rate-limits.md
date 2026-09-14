# API Rate Limits

The default API rate limit is 100 requests per minute per API key. This applies to all
standard-tier accounts and is enforced at the gateway level, independent of which endpoint is
being called. Exceeding the limit returns an HTTP 429 response with a `Retry-After` header
indicating how many seconds to wait before retrying.

Enterprise plans can request an increase to 500 requests per minute by contacting support with
their account ID and expected peak traffic. Increases are typically applied within one business
day and do not require a service restart. There is currently no self-service option to raise
your own rate limit - all increases go through a support request.

Rate limits are counted per API key, not per IP address or per user account, so a customer with
multiple integrations should provision a separate API key for each one to avoid one integration's
traffic exhausting the shared limit. The counter resets on a rolling 60-second window, not a
fixed calendar minute.

Webhook delivery attempts and the `/health` endpoint are exempt from rate limiting.
