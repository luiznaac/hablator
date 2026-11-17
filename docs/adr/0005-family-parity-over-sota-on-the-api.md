# Family parity wins over SOTA on the new API's shape

**Status:** accepted

Where the modern practice and the family's existing shape disagreed, the new API followed the family: no `/v1` path prefix, offset pagination with a `total`, the scaffold's `{code, detail, errors?}` error envelope instead of RFC 9457 `application/problem+json`, and no `Idempotency-Key` on `POST /notifications`. The parts that are cheap and invisible to consumers were adopted from SOTA: RFC 6750 Bearer with constant-time comparison and `WWW-Authenticate`, RFC 3339 UTC timestamps, `201` with `Location`, strict schemas with explicit caps, stable machine-readable error codes with field paths, OpenAPI 3.1, and a documented derived status rather than a persisted one.

The reason is not indifference: a single-user homelab with one consumer set gains little from a versioned surface or cursor pagination, and the react scaffold's client plus the scaffold's exception handlers already read this envelope. Diverging would make hablator the odd repo in the family and force a family-wide migration later. Each declined practice is recorded in the spec with its revisit trigger, so a future reader can tell a decision from an oversight.

**Consequences:** the risk of a duplicated notification after a client timeout is accepted (no dedup store); the UI disables double submits, and chameidor's retry is the only guard. `OFFSET` scans and an in-app status aggregate are acceptable at this volume. A family-wide move to problem+json is `environments`' work, not hablator's.

**Considered options:** RFC 9457 errors and keyset pagination (rejected for family parity, revisit on volume or a family migration); an `Idempotency-Key` header (rejected: no dedup store in v1, revisit if duplicates appear).
