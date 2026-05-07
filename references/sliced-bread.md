# Sliced Bread Architecture

Organic vertical slices. Files grow into facades. No ceremony.

```
src/
├── domains/                     # The loaf
│   ├── common/                  # Common leaf (no sibling deps — see attribution.md re: DDD)
│   ├── orders/                  # A slice
│   │   ├── index.*              # Public API (the crust)
│   │   ├── order.*              # Core concept
│   │   ├── fulfillment.*        # Facade → delegates to fulfillment/
│   │   └── fulfillment/
│   └── pricing/                 # Thin slice (one file is fine)
├── adapters/                    # Implements domain protocols
│   ├── postgres/                # Outbound — DB driver
│   ├── stripe/                  # Outbound — third-party SDK
│   ├── auth/                    # Cross-cutting — JWT, session
│   ├── logging/                 # Cross-cutting — structured logger
│   └── cache/                   # Cross-cutting — Redis, in-memory
└── app/                         # Presentation + orchestration (DI)
```

Cross-cutting concerns (auth, logging, cache, metrics) are a *category of adapter*,
not a separate "infrastructure" or "middleware" layer. They implement domain-defined
ports (e.g. `domains.common.AuthContext`) the same way storage adapters do.

## Growth pattern

1. Start with one file per concept.
2. Extract sibling when crowded.
3. File becomes facade + folder when it wants friends.

## Rules

- Index/barrel file is the crust — external code imports from here only.
- Don't reach into another slice (import from index, not internals).
- Models stay pure (no ORM, framework, or adapter imports).
- One direction only (use events for reverse deps).
- `common/` is a leaf (imports nothing from siblings).

## Lineage

Sliced Bread synthesizes Vertical Slice Architecture (Bogard, 2018), Hexagonal /
Ports & Adapters (Cockburn, 2005), Screaming Architecture (Martin, 2012),
Clean / Onion (Martin 2012, Palermo 2008), and Domain-Driven Design (Evans, 2003).
For what it inherits, what it differs on, and why "common leaf" is *not* DDD's
"shared kernel," see [`sb/attribution.md`](./sb/attribution.md).

---

## Why vertical slices?

Layered architecture (controllers → services → repositories) groups by technical role.
This means a single feature change touches every layer. Vertical slices group by
business concept — an `orders` change stays in `orders/`.

Cross-cutting concerns (auth, logging, caching) live in `adapters/` behind
domain-defined ports — not sprinkled across slices, and not pushed into a
separate middleware layer. If you're tempted to add auth logic inside a domain
slice, push it down to `adapters/`.

## Why organic growth?

Pre-creating folders, abstract base classes, and registries for a single implementation
is speculative architecture. It costs complexity now for flexibility that may never
be needed. The growth pattern (one file → extract sibling → facade + folder) means
structure emerges from actual pressure, not imagination.

**Growth triggers:**

- A file passes ~150–200 lines or holds 3+ distinct concepts → extract siblings.
  (300 lines is the hard ceiling in this guide — by then you are well past
  the trigger.)
- 3+ related files cluster around a sub-concept → create subdirectory
- A file becomes an import hub for its children → it's now a facade

**Not growth triggers:**

- "We might need this later"
- "This looks like it could be its own module"
- A single implementation of a pattern (one adapter, one strategy, one handler)

## Anti-patterns

### Cross-slice internal imports

```
# BAD — reaching past the crust
from domains.pricing.discount_calculator import DiscountCalculator

# GOOD — import from the public API
from domains.pricing import calculate_discount
```

Why it matters: internal files can be renamed, split, or reorganized freely.
The index/barrel file is a contract; internals are implementation details.

### Domain importing infrastructure

```
# BAD — order.py imports an HTTP client
from adapters.stripe import StripeClient

# GOOD — order.py defines a protocol, adapter implements it
class PaymentGateway(Protocol):
    async def charge(self, amount: Money) -> PaymentResult: ...
```

Why it matters: domain models are the most stable code. Coupling them to
infrastructure means infrastructure changes ripple into business logic.

### Circular dependencies between slices

```
# orders imports pricing, pricing imports orders — cycle
```

Resolution: use domain events. `orders` emits `OrderPlaced`, `pricing` subscribes.

Where does the event type live? Default rule:

- **Single-producer event** → in the producer slice's public API
  (`orders.OrderPlaced`), *when the consumer can import from the producer
  without forming a cycle*.
- **Promoted to `common/events/`** → when (a) 2+ slices need to *produce* the
  same event type, (b) the consumer can't import from the producer without
  forming a cycle (e.g. `orders` already imports `pricing`, so `pricing`
  consuming `OrderPlaced` would cycle), or (c) it's referenced by a contract
  outside the loaf (entrypoints, persisted log).

Default to keeping events in the producer. Promote on second producer or to
break a cycle, not in anticipation.

**Dispatch is synchronous in-process by default.** Subscribers run on the producer's
call stack within the same transaction unless an adapter (queue, outbox, broker)
explicitly says otherwise. Async dispatch is an *implementation choice of the bus
adapter*, not a property of the event itself — domain code shouldn't care.

### Adapters importing app layer

```
# BAD — adapter depends on a use case or handler
from app.use_cases.checkout import Checkout

# GOOD — adapters only know about domain ports
from domains.orders import OrderRepository
```

Why it matters: adapters implement domain contracts. They shouldn't know how the
application orchestrates those contracts.

### Premature abstraction

```
# BAD — AbstractRepositoryFactory with one concrete implementation
# BAD — EventBus interface when only one event exists
# BAD — PluginRegistry with a single plugin

# GOOD — just use the concrete thing until you need the abstraction
```

## Boundary decisions

### When does something belong in `common/`?

**Default: prefer a named slice.** Most "shared" code is a missing domain in
disguise. If two slices both send notifications, the right answer is usually a
`notifications/` slice with its own crust — not `common/notifications.*`.
Naming the slice forces you to articulate what it *is*, rather than where it
*goes*. A soft `common/` is worse than no `common/`; it becomes a junk drawer
that quietly couples everything to everything.

`common/` is a quarantine for **shapes, not behavior**. Use it only when *all*
of these hold:

- The type has **zero behavior** — pure data, no methods that encode
  slice-specific rules.
- It is **referenced by 2+ slices today** (don't pre-promote on speculation).
- A named slice is genuinely a worse fit — the type is too atomic to deserve
  a domain of its own, or extraction would force a cycle.

**Valid cases:**

- Pure value types with universal semantics — `Money`, `UserId`, `Timestamp`,
  `Email`.
- Cross-slice event payloads, where producer and consumer can't both own the
  schema without creating a cycle.
- Infrastructural taxonomy with no domain — error enums, result wrappers,
  opaque ID newtypes, trace/correlation context.
- Ports (protocols/traits) defined for adapters to implement — these are
  shape, not behavior.

**Not common:**

- Anything with logic ("validation helpers," "format utilities") — that logic
  belongs to *some* slice. Find it, name it, and put it there.
- Anything used by only one slice — keep it inside the slice.
- Anything extracted "to be reusable later" — wait until a second caller
  actually exists.
- Cross-slice request/response models — prefer events; the producer owns the
  schema and consumers adapt.

If `common/` ever needs to import from a sibling slice, it has stopped being
common. The fix is to move the offending type into a slice (or create one) —
not to relax the leaf rule.

### When do you introduce an adapter?

When domain code needs to talk to something external (database, API, filesystem,
message queue). The domain defines a protocol (port), the adapter implements it.

Don't create an adapter for in-process utilities (string formatting, date math,
pure computation). Those are just functions.

### When does a use case belong in `app/` vs inside a slice?

- **Inside the slice:** operations on a single domain concept (create order,
  update order status). These are domain services or methods on the entity.
- **In `app/use_cases/`:** orchestration across 2+ slices (checkout needs orders +
  pricing + inventory). The use case imports from multiple slice public APIs.

### When do you use events vs direct imports?

- **Direct import:** slice A needs data from slice B to do its work (orders imports
  pricing to calculate totals). This is a natural dependency.
- **Events:** slice B needs to react to something slice A did, but slice A shouldn't
  know about slice B. This prevents cycles and keeps the emitter independent.

Rule of thumb: if adding the import would create a cycle, use an event.

**Event-direction discipline.** Events are for *reverse* dependencies — the
emitter must not know who subscribes. If you find yourself reaching for events
to avoid a forward import that would compile fine, you're using events as a
generic message bus. Stop. Direct calls are clearer when the dependency
direction is already correct.

## Dependency direction quick-check

```
app/           →  domains/*     →  domains/common/
adapters/      →  domains/*

Never:
  domains/*    →  adapters/*
  domains/*    →  app/*
  adapters/*   →  app/*
  adapters/*   →  sibling adapters/*
  common/      →  sibling domains
```

(Adapters never call other adapters directly. If a Stripe adapter needs to log,
it depends on the *logging port* defined in `common/`, and `app/` wires the
logging adapter in. Adapter-to-adapter coupling is how cross-cutting concerns
become a tangled middle layer.)

## Reviewing against Sliced Bread

When reviewing code for architecture compliance, check:

1. **Import direction** — do all arrows point inward (toward domains)?
2. **Crust integrity** — are external consumers importing from index files only?
3. **Model purity** — do domain files import only stdlib, common, and sibling public APIs?
4. **Growth justification** — does every directory/abstraction have 2+ concrete uses?
5. **Event usage** — are events used for reverse deps, not passed around as general-purpose messaging?
6. **Cross-cutting containment** — auth, logging, cache, metrics live in `adapters/*`
   behind ports, not sprinkled through domain code or wired adapter-to-adapter?

## Companion documents

- [`sb/attribution.md`](./sb/attribution.md) — predecessor lineage and what Sliced Bread inherits, differs on, and drops.
- [`sb/practice.md`](./sb/practice.md) — applied patterns: CQRS pairing, anti-corruption layers, slice-local duplication, testing strategy, and slice graduation (when to split a slice into its own crate / package / library / service).
- [`sb/rust.md`](./sb/rust.md) — Rust-specific mechanics (`pub use`, `pub(super)`, `foo.rs` + `foo/` facade, Cargo workspaces).
- [`sb/go.md`](./sb/go.md) — Go-specific mechanics (`internal/` compile-time enforcement, capitalization, `go.work`).
- [`sb/ts.md`](./sb/ts.md) — TypeScript-specific mechanics (`package.json` `"exports"` map as the modern facade, why barrel files are now an anti-pattern).
