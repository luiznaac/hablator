---
source: research
branch: research/push-oss-iphone
date: 2026-11-16
---

# Push channel: open-source servers and iPhone delivery paths

Research for [issue #18](https://github.com/luiznaac/hablator/issues/18), feeding the push-channel design in [issue #8](https://github.com/luiznaac/hablator/issues/8). Scope: a self-hosted, single-user homelab hub whose target device is an iPhone. The ntfy decision from [issue #2](https://github.com/luiznaac/hablator/issues/2) is the default, not locked.

## Recommendation

For this homelab, **ntfy remains the best default**: one container, an official open-source iOS app, token + per-topic ACL auth, tags/priority/click/attachments, and very active security maintenance. Its documented iOS caveat is real: a self-hosted server cannot push to the iPhone directly — instant delivery rides a metadata-only ping through `ntfy.sh`'s APNs/Firebase relay, and the app then polls your server for the body.

Choose **Bark** instead if native iOS alert semantics and direct-to-APNs delivery (no third-party relay) matter more than tags, attachments and action buttons. Bark self-hosts cleanly and needs no Apple developer account, but it pushes with the Bark app's own APNs credential shipped by the upstream project, so the hub inherits an upstream dependency.

**Apprise** is a router, not a receiver: it fans one publish URL out to many downstream services (`ntfy://`, `gotify://`, `bark://`), but its iOS app is a send/manage client, not a notification receiver. **Native APNs** is a build-your-own-app project ($99/yr Apple Developer Program + a companion app), not worth it here.

## Server comparison

| | ntfy | Gotify | Bark (`bark-server`) | Apprise |
|---|---|---|---|---|
| Self-host | Docker `binwiederhier/ntfy`, volumes for cache + config; SQLite or PostgreSQL | Docker `gotify/server`, `/app/data`; SQLite, MySQL or PostgreSQL | Docker `finab/bark-server`, `/data` (bbolt) or MySQL | Docker `caronc/apprise` API; a router |
| License | Apache-2.0 / GPL-2.0 | MIT | MIT | BSD-2-Clause (core), MIT (API) |
| Maintenance | Very active; v2.38.1 (2026-11-16) | Active; v3.1.1 (2026-09-15) | Active; server v2.4.0 (2026-11-06), iOS app v1.6.4 (2026-09-23) | Very active; v2.2.0 (2026-11-08) |
| Auth | Users + per-topic ACL (`rw`/`ro`/`wo`/`deny`) + bearer `tk_…` tokens | Users + clients + per-user applications; `X-Gotify-Key`; optional OIDC | Optional single global HTTP Basic + per-device `device_key`; no per-device ACLs | Per-config-ID HTTP Basic; `locked`/`public`/`disabled` modes |
| Publish | `POST/PUT /<topic>` (headers) or `POST /` JSON | `POST /message` (form or JSON) | `POST /push` JSON or V1 path form | `POST /notify` (URLs in body) |
| Features | Title, body, priority 1–5, tags/emoji, click, action buttons, attachments, Markdown, scheduling | Title, body, priority 0–10, Markdown, click URL, big image; no tags/attachments/actions | Title, subtitle, body, level, volume, badge, sound, icon, group, URL, ciphertext, TTL | Routes to downstream services; inherits their limits |
| iPhone path | Official OSS app; self-hosted instant delivery needs `upstream-base-url: https://ntfy.sh` (metadata ping via ntfy.sh) | No official app; third-party iGotify + its Notification Assistant relay through third-party SecNtfy to APNs | First-party app; server pushes straight to APNs | No receiver; the "Apprise Mobile" app is a send/manage client |
| Limits | 4 KiB message, 15 MiB attachment (3 h expiry), 12 h cache, 1 KiB title | No per-message cap by default; messages persist until deleted | APNs ~4 KiB payload; no server-side store (archive is client-side) | Inherited |

## iPhone delivery paths

- **ntfy iOS.** Official app (App Store, v1.7.0, 2026-05-29). A self-hosted server cannot deliver directly: with `upstream-base-url: https://ntfy.sh`, the server publishes a metadata-only `poll_request` to ntfy.sh, which sends the APNs/Firebase ping; the app then fetches the body from your server. Content stays local, but delivery transits ntfy.sh. No foreground service; background tasks run at iOS's discretion; known issues include "New message" with no content and a non-refreshing list. Source: [ntfy config](https://docs.ntfy.sh/config/), [ntfy server.yml](https://raw.githubusercontent.com/binwiederhier/ntfy/main/server/server.yml), [ntfy iOS limitations](https://raw.githubusercontent.com/binwiederhier/ntfy-ios/main/docs/TECHNICAL_LIMITATIONS.md), [known issues](https://docs.ntfy.sh/known-issues/).
- **Bark iOS.** First-party app (App Store, v1.6.4, 2026-09-23). `bark-server` pushes directly to APNs using the Bark app's own embedded credential (team `5U8LBRXG3A`, key `LH4T9V5U4R`, topic `me.fin.bark`), so no Apple account is needed — but the hub inherits the upstream project's key and its ability to rotate or revoke it. Free, MIT, optional end-to-end encryption, battery-free delivery via APNs. Source: [bark-server](https://github.com/Finb/bark-server), [APNs source](https://raw.githubusercontent.com/Finb/bark-server/master/apns/apns.go), [API V2](https://github.com/Finb/bark-server/blob/master/docs/API_V2.md).
- **Gotify iOS.** No official app (Android only). The practical path is third-party iGotify (App Store, v1.7.0, 2026-10-26) plus its self-hosted Notification Assistant, which forwards through the third-party SecNtfy relay to APNs. Source: [Gotify docs](https://gotify.net/docs/), [iGotify](https://github.com/androidseb25/iGotify-Notification-Assistent).
- **Pushover.** Not self-hostable and closed source; $4.99 one-time per platform, 10k messages/month free, own APNs infrastructure. Useful as a reliability baseline, not a fit for the self-hosted hub. Source: [Pushover pricing](https://pushover.net/pricing).
- **Native APNs.** Requires the $99/yr Apple Developer Program, a push entitlement + App ID, an APNs auth key/certificate on the server, and an installed companion app that registers a per-app device token. There is no generic push to an iPhone without an app. Source: [Apple Developer Program](https://developer.apple.com/programs/), [APNs registration](https://developer.apple.com/documentation/usernotifications/registering-your-app-with-apns).
- **Other OSS options.** Chanify (node→APNs direct, or stateless via `api.chanify.net`) and PushDeer (unmaintained, annual certificate refresh) do not beat Bark for this use case. Sources: [chanify](https://github.com/chanify/chanify), [pushdeer](https://github.com/easychen/pushdeer).

## Implications for the hub's `PushProvider` port

- **Recipient** differs by provider: an ntfy **topic** (plus server URL and token) vs a Bark **device key** vs a Gotify app token. The port should take an opaque channel-specific recipient/config, not assume a topic.
- **Content** maps cleanly for ntfy (title, message, priority, tags, click, actions, attach); Bark supports title/subtitle/body/level/sound/group/url but not tags; Gotify supports title/message/priority/click but not tags. The port should expose a common core (title, body, priority, click) with provider-specific extras passed through.
- **Auth/config** must be provider-agnostic: env for secrets, DB for the active provider and its non-secret config.
- **History** needs the provider name and response in each Attempt (already the domain model from #3); the provider's own response id differs (ntfy has no message id; Gotify returns an id; Bark returns a code).
- **Recommendation for #8:** design the port around ntfy as the default, keep the recipient/content shape provider-agnostic, and record the iOS relay caveat as an accepted trade-off. If the direct-APNs property is a hard requirement, switch the default to Bark.

## Sources

Primary: [ntfy docs](https://docs.ntfy.sh/), [ntfy publish](https://docs.ntfy.sh/publish/), [ntfy install](https://docs.ntfy.sh/install/), [ntfy config](https://docs.ntfy.sh/config/), [ntfy phone](https://docs.ntfy.sh/subscribe/phone/), [ntfy known issues](https://docs.ntfy.sh/known-issues/), [ntfy server.yml](https://raw.githubusercontent.com/binwiederhier/ntfy/main/server/server.yml), [ntfy releases](https://github.com/binwiederhier/ntfy/releases), [Gotify docs](https://gotify.net/docs/), [Gotify install](https://gotify.net/docs/install), [Gotify config](https://gotify.net/docs/config), [Gotify pushmsg](https://gotify.net/docs/pushmsg), [Gotify msgextras](https://gotify.net/docs/msgextras), [bark-server](https://github.com/Finb/bark-server), [bark-server API V2](https://github.com/Finb/bark-server/blob/master/docs/API_V2.md), [bark-server APNs](https://raw.githubusercontent.com/Finb/bark-server/master/apns/apns.go), [Apprise](https://github.com/caronc/apprise), [Apprise API](https://github.com/caronc/apprise-api), [Pushover pricing](https://pushover.net/pricing), [Apple Developer Program](https://developer.apple.com/programs/), [APNs registration](https://developer.apple.com/documentation/usernotifications/registering-your-app-with-apns), [chanify](https://github.com/chanify/chanify), [pushdeer](https://github.com/easychen/pushdeer).
