# ntfy is the only push provider, and the iOS metadata relay is accepted

**Status:** accepted

Push is delivered through a self-hosted `binwiederhier/ntfy` instance, and ntfy is the locked provider for this phase. The accepted trade-off is that self-hosted iOS instant delivery cannot be pushed to directly: the server sends a metadata-only `poll_request` through `ntfy.sh`, which wakes the app through APNs/Firebase, and the app then polls the hub's ntfy server for the body. **Message content stays local; delivery metadata transits ntfy.sh.** Bark is the documented alternative — it pushes straight to APNs — and can be added later as a second provider through the `(channel, provider)` registry without touching the core.

The hub publishes to exactly one topic configured server-side; a request cannot choose a topic, and `recipients` is rejected for push. That removes the failure mode where a consumer publishes to a topic the phone is not subscribed to. The topic is the push Recipient's address in the domain, so no new vocabulary is introduced.

**Consequences:** push configuration is the topic plus a default priority in the database; the server URL and an admin-user token (`tk_…`, label `hablator-backend`) are secrets in the environment. The instance must run deny-all behind TLS. The single admin token grants access to every topic, which is why the instance stays private; downgrading to a scoped write-only user later is a config change. Content is validated against ntfy's limits at request time (4,096-byte message, 1 KB title, 512 bytes of tags) and rejected with `422` before any row exists — never truncated, never converted to an attachment.

**Considered options:** Bark as default (rejected: inherits the upstream project's APNs key, no tags/attachments); Gotify (rejected: no official iOS app, third-party relay); Apprise (rejected: a router, not a receiver); native APNs (rejected: Apple Developer Program plus a companion app for a homelab).
