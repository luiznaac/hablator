# One channel port with a provider registry, inside the scaffold's hexagonal layers

**Status:** accepted

Hablator runs on the `environments/python` scaffold's layered hexagon (`httpapi` / `gateway` / `persistence` → `usecase`, dependencies inward, enforced by import-linter) with one channel port, `IChannelProvider`, and a `ChannelRegistry` keyed by `(channel, provider)` instead of a class per channel. A `Delivery` carries an opaque `Recipient.address` and an opaque `options` mapping; each adapter validates and translates its own vocabulary, and the core classifies retriability once.

The alternative — a typed model per channel (`EmailDelivery`, `PushDelivery`, …) with channel-specific service methods — was rejected because every new channel would then touch the domain, the API DTOs and the dispatch path, which is exactly the change this hub exists to make cheap. The cost we accept is that channel rules (a push topic is server-side, email takes no per-delivery options) live in adapter validation rather than in the type system; the API's `422 domain_error` shapes keep them observable.

**Consequences:** adding a channel is one adapter class plus one composition-root line. The `usecase` slice DAG is `delivery → notification → channel`, with `IDeliveryDispatcher` declared where its consumer lives and implemented in `delivery`, so the graph stays acyclic and a second import-linter contract (or a static architecture test) can enforce it. Provider instances are stateless and built once; per-dispatch configuration is read from the database, so a provider cannot cache config at construction.

**Considered options:** a channel enum switch inside one dispatcher (rejected: the switch grows forever and defeats the port); separate usecase packages per channel (rejected: duplicated dispatch, history and retry logic).
