# The legacy `POST /send-email` stays byte-compatible and unauthenticated

**Status:** accepted

The hub keeps `POST /send-email` with today's request and response contract, routed through `NotificationService` as one Notification plus one email Delivery, and it stays outside the Bearer scheme that protects the new API. Consumers (valoab through the chameidor scheduler) keep their configuration unchanged during the migration; the endpoint can only create email deliveries, which bounds the exposure.

Compatibility is pinned by golden fixtures at the HTTP boundary: the exact `200` body (`{"message": "Emails sent successfully", "response": <provider raw body>}`), the `502` body when the delivery ends failed or pending, today's `400` messages for invalid payloads, the `404` status for unknown paths, and the env-fallback case with no provider row. `text` maps to `body_html` so rendering is unchanged, and a stdlib `HTMLParser` tag-strip produces the new `text/plain` alternative — derivation lives only in the legacy adapter; the new API path never derives.

**Consequences:** the endpoint is an unauthenticated write surface on a LAN service; accepted for a single-user homelab and recorded as a revisit trigger once every consumer is migrated to `/notifications`. The legacy response passes the provider's raw body through, so a caller still sees Mailgun's message id even though the hub does not persist it. The old single-file proxy is deleted once this adapter lands, so there is exactly one implementation.

**Considered options:** keep the proxy running in parallel (rejected: two implementations and two deploy paths); require the token on the legacy endpoint (rejected: breaks consumer configs mid-migration); drop the legacy endpoint (rejected: breaks the only production consumer).
