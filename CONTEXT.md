# Hablator — notification hub

The homelab's notification hub: it receives send requests from other projects and delivers them through channels, recording the history of every delivery attempt.

## Language

### Sending

**Notification**:
The notification request: one per HTTP request, with base content (subject/body) and an optional `source`. It produces one Delivery per chosen channel; its status (`succeeded`/`failed`/`pending`) is derived from the deliveries, not persisted.
_Avoid_: message, alert.

**Delivery**:
The intent to deliver one Notification through one channel, with recipients, resolved content and channel options. It has its own status and lifecycle (`pending`, `in_progress`, `succeeded`, `failed`).
_Avoid_: send, job, task.

**Attempt**:
One execution of a Delivery against a provider, recorded append-only with a sequential number, result, error and retriability classification. A Delivery may have several.
_Avoid_: try.

**Content**:
The content actually sent by a Delivery: the channel-specific override or a copy of the Notification's base content at send time.
_Avoid_: body, payload, template.

**Recipient**:
A destination address in a channel's vocabulary: a list of email addresses for email, exactly one topic for push.
_Avoid_: target, address.

**Source**:
The optional origin of a Notification — the project or consumer that requested the send.
_Avoid_: origin, caller.

### Channels and failures

**Channel**:
The delivery medium: `email`, `push`, `sms` or `voice`. Only email and push have a configured provider in this phase; sms and voice exist only in the vocabulary.
_Avoid_: medium, transport.

**Provider**:
The concrete implementation of a channel that runs one attempt (e.g. Mailgun for email, ntfy for push). It is recorded on the Attempt.
_Avoid_: gateway, driver.

**Retriable**:
The classification of a failed Attempt that may produce another attempt (timeout, network error, 5xx, 429). A non-retriable failure ends the Delivery.
_Avoid_: transient, recoverable, retryable.
