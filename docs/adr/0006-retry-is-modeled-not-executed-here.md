# Retry is modeled and classified here, executed by chameidor

**Status:** accepted

The hub models retry but does not schedule it: a failed Attempt records `retriable` (timeout, network, 420, 429, 5xx), a Delivery carries `next_attempt_at`, and a `retry_policy` table exists per channel with an explicit `backoff_seconds` schedule. Nothing in v1 reads that table or schedules the transition back to `pending`. When retry lands, chameidor creates a one-time task with `execute_at = next_attempt_at` pointing at the hub's retry endpoint; the hub's manual `POST /deliveries/{id}/retry` uses the same dispatch path today.

Scheduling belongs to chameidor because it already owns timed tasks for every project in the family; a second scheduler inside the hub would duplicate that machinery, need its own crash recovery, and split the operational story. The hub's job is to say *whether* an attempt is worth retrying and *when* the next one is due, not to run a timer.

**Consequences:** `retry_policy` rows are inert until chameidor's `execute_at` exists ([luiznaac/chameidor#14](https://github.com/luiznaac/chameidor/issues/14)), and the policy values stay undecided by design — the table shape (an explicit schedule, not a multiplier) is what is locked, so the future implementation does not inherit a guessed curve. The manual retry endpoint and the retriable classification are useful immediately, which is why they ship now. `failed` is terminal for the hub; only an external scheduler can move a retriable failure back to `pending`.

**Considered options:** a scheduler inside the hub (rejected: duplicated timed-task machinery and crash recovery); no retry model at all (rejected: the schema and API would then need a breaking change when chameidor catches up); a multiplier-based backoff column (rejected: it encodes a curve nobody has chosen).
