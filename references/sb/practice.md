# Sliced Bread in Practice

Applied patterns and judgement calls that don't fit cleanly in the language docs:
how slices interact with CQRS, anti-corruption layers, testing, slice-local
duplication, and — the section most teams need most — when a slice should
graduate from a folder to a workspace package, library, or service.

> **Load this doc when** the task is a judgement call, not a build:
> extracting/keeping near-duplicate models, deciding on a read/write split,
> integrating with an external system whose vocabulary clashes, choosing a
> per-slice testing strategy, or graduating a slice. For routine feature work
> inside an existing slice, [Sliced Bread](../sliced-bread.md) alone is enough.

> Companion to [Sliced Bread](../sliced-bread.md). Read that first for the
> language-agnostic rationale and anti-patterns. See also
> [attribution](./attribution.md) for predecessor lineage.

---

## Slice-local duplication is fine

The single most-resisted rule in vertical-slice architectures: **each slice owns
its own model of a concept.** If `orders.LineItem` and `invoicing.LineItem` look
80% alike, that is not duplication to eliminate. It is two distinct concepts
that happen to share a current shape.

Sandi Metz: *"Duplication is far cheaper than the wrong abstraction."* The cost
ordering, in practice:

| Cost | Severity |
|---|---|
| A wrong abstraction shared across slices | High — every change ripples and shapes both sides |
| Two near-duplicate structures evolving independently | Low — each slice updates its own without coordination |
| Genuine pure-data values used identically by 3+ slices, kept duplicated | Medium — extract to `common/` |

### Keep the duplication when

- The structures look similar but model different concepts (`Customer` in
  `billing` is not `Customer` in `support`).
- The slices have different lifecycle, validation, or consistency needs.
- One representation is read-optimized, the other is write-authoritative.
- Extraction would force every change to coordinate across slice owners.

### Promote to `common/` only when a named slice is the wrong answer

The first question is never "should this go in common?" — it's "is there a
slice missing here?" Most extraction candidates turn out to be unnamed
domains. A `notifications/` slice beats a `common/notify.*` file every time.

Promote to `common/` only when *all* of these hold:

- 2+ slices reference the type today, with identical semantics. (Don't
  pre-promote on speculation.)
- The type carries **zero behavior** — pure data, or a port/protocol whose
  shape is the contract.
- A named slice would be a worse fit — the type is too atomic to deserve a
  domain (`Money`, `UserId`, `Timestamp`, `Email`), or it's an event payload
  whose schema can't live with either producer or consumer without creating
  a cycle.

If you find yourself adding *behavior* to a `common/` type, that's the
signal: the type wants to live in a slice. Move it.

The promotion threshold is a deliberate counterweight to the DRY reflex. Two
copies of a struct cost less than one wrong abstraction — and a named slice
usually beats both.

---

## CQRS within a slice

Command Query Responsibility Segregation pairs naturally with vertical slices.
Inside a slice, commands (mutations) and queries (reads) can take separate paths
with different models.

```
domains/orders/
├── (slice facade)              # whatever your language calls the crust
├── order.*                     # write model — the entity
├── place.*                     # command
├── update-status.*             # command
└── queries/
    ├── by-customer.*           # read-optimized, can join across stores
    └── pending-summary.*       # denormalized projection
```

### When CQRS earns its keep within a slice

- Read models genuinely differ in shape (denormalized for UI).
- Reads and writes scale on different dimensions (heavy reads, infrequent
  writes — read-side caching, replicas, or projections).
- Different consistency contracts per side (eventual on reads, strong on writes).

### When it's overkill

- Reads and writes share the same shape — a query method on the entity is enough.
- No projections, no event sourcing, no replicas.
- The slice has five operations total and you'd be adding two folders to
  separate `find_by_id` from `place`.

CQRS is a slice-local choice, not a project-wide mandate. Some slices will use
it, most won't. There is no global "queries/ folder must exist" rule.

---

## Anti-corruption layers

When a slice talks to an external system whose vocabulary or model conflicts
with yours — legacy databases, third-party APIs, partner integrations — the
adapter doubles as an Anti-Corruption Layer (ACL). Its job is to make sure
foreign concepts never leak past it.

### The rule

- **Domain code never imports vendor types.** No `StripeCharge`,
  `LegacyAccountRow`, or `SalesforceOpportunity` inside `domains/`.
- **Adapters speak both languages.** The domain port is in your concepts.
  The adapter implementation knows the foreign one. Translation happens at
  the boundary.

### Example

```ts
// domains/payments/index.ts — port in your vocabulary
export interface PaymentGateway {
  charge(amount: Money, customer: CustomerRef): Promise<PaymentReceipt>;
}
```

```ts
// adapters/stripe/payment-gateway.ts — the ACL
export class StripePaymentGateway implements PaymentGateway {
  async charge(amount: Money, customer: CustomerRef): Promise<PaymentReceipt> {
    const result = await this.stripe.charges.create({
      amount: amount.cents,
      currency: amount.currency.code,
      customer: customer.externalId,
    });
    return PaymentReceipt.fromStripe(result); // translate at the seam
  }
}
```

### The harder case: legacy databases

If you adopt a system with hundreds of badly-named columns, the ORM mapping
inside the adapter *is* your ACL. The domain entity has well-named fields;
the adapter does the renaming. A leaky ORM that surfaces `usr_acct_typ_cd`
to the domain has skipped the ACL and corrupted the model.

### When the foreign model is your model

If you're integrating with a system whose vocabulary you've adopted as the
authoritative one (e.g. you're a thin shell over a SaaS), the adapter is
just an adapter — there's nothing to anti-corrupt against. The ACL pattern
exists to protect a *distinct* domain model.

---

## Testing strategy per slice

Vertical slicing reshapes the test pyramid. Center of gravity shifts up:

| Layer | What it tests | Where it lives |
|---|---|---|
| **Slice integration** (most) | Slice's public API end-to-end with in-memory or testcontainer adapters | Co-located with the slice (`orders/__tests__/place.test.ts`) |
| **Pure unit** | Calculations, parsing, validation — no IO | Co-located, often same file as the function |
| **Cross-slice / use-case** | Orchestration across multiple slices | `app/__tests__/checkout.test.ts` |
| **End-to-end** (few) | Through entrypoints to real adapters | Top-level `e2e/` |

### What changes vs layered testing

- **Repository-mock unit tests largely disappear.** Slice integration tests
  exercise the real interface against a fake or in-memory adapter — same
  surface as production, faster than the DB.
- **Service-layer unit tests disappear with the service layer.** A slice's
  public API *is* the service.
- **Each slice's test suite is self-contained.** No shared fixtures across
  slices. If `pricing` tests need data set up by the `orders` slice, that
  is a coupling smell — the dependency is leaking through tests.

### Heuristics

- Test through the crust, not through internals. Internal refactors
  shouldn't break tests; behavior changes should.
- One integration test that goes through the slice's public command beats
  five unit tests on private helpers.
- Don't unit-test code that's already covered by an integration test for
  the same path — you're paying maintenance for the same coverage twice.

---

## Slice growth and graduation

A slice starts as one file. It can grow into multiple files, then a folder
with hidden internals, then a workspace package, then a separately versioned
library, then a separately deployed service. Each step adds friction. Never
take a step without a concrete reason — and **don't skip steps**.

### Five stages of slice maturity

| Stage | Shape | Cost | Triggers to advance |
|---|---|---|---|
| 1. **File** | `pricing.*` | None | >150–200 lines, 3+ concepts in one file |
| 2. **Folder** | `pricing/{index,calc,rules}.*` (+ internal) | Subdir, facade file | Hidden helpers want privacy from siblings |
| 3. **Workspace package** | `packages/pricing/` (Cargo member / pnpm workspace / `go.mod`) | Manifest, build target, typecheck boundary | Build-time pain, ownership split, contract pressure, TS visibility enforcement |
| 4. **Versioned library** | published to internal registry | SemVer, publish pipeline, registry coordination | A second repository imports it |
| 5. **Service** | network boundary | Network reliability, distributed observability, schema versioning, deployment topology | Independent scale / deploy / runtime / failure isolation |

You can stop at any stage. **Most slices end at stage 2 forever.** The
literature loves stages 4–5; production codebases live at stage 2.

### Stage 1 → 2: file becomes folder

Mechanical. Covered in [sliced-bread.md → Growth pattern](../sliced-bread.md#growth-pattern).
The trigger is internal pressure (file size, hidden helpers wanting
privacy) — no external coordination, no manifest changes.

### Stage 2 → 3: folder becomes workspace package

A workspace package adds a manifest (`Cargo.toml`, `package.json`, `go.mod`),
a build target, and a typecheck/test boundary. The cost is real: cross-package
refactors need package-aware tooling, and your devloop now includes a build
step per package.

**Worth it when:**

- **Build-time pain.** Typecheck or compile of one slice gates iteration on
  another. Workspace packages give you parallel, cacheable build units.
- **Ownership split.** A different team owns the slice's evolution and you
  want explicit changelog and review surface for the boundary.
- **Public-API contract pressure.** The slice has many consumers and you
  want changes to the crust to break loudly at compile time across them.
- **TypeScript visibility enforcement.** TS has no compile-enforced module
  privacy at the directory level (see [`./ts.md`](./ts.md)). Once the
  honor system on `"exports"` stops being honored, a package boundary is
  the strongest enforcement available.

**Don't graduate because:**

- The directory "feels important."
- You read a blog post about monorepo packages.
- Reviewers say "this should be its own package" without naming a concrete pain.

### Stage 3 → 4: workspace package becomes versioned library

A second repository needs the slice. Now you publish.

**Triggers:**

- A second repo imports the package.
- The slice's release cadence diverges from the host application's.
- An open-source release is planned.

**Costs:**

- SemVer commitment — every breaking change is a major version bump.
- Publish pipeline, registry, security scanning, sign-off.
- Coordination overhead with downstream consumers on every change.

This is the most common over-shoot in monorepos: extracting a library "to be
reusable" *before* there is a second consumer. Resist. **Two consumers is
the trigger; one consumer is just a directory.**

### Stage 4 → 5: library becomes service

The slice runs in its own process, exposed by RPC, HTTP, or message queue.

**Real triggers:**

- **Independent scaling.** The slice is the bottleneck or a fan-out hot spot;
  scaling the host wastes resources.
- **Independent deploy.** Deploying the host has unacceptable risk and the
  slice changes on a different cadence.
- **Runtime isolation.** Different language, memory profile, or security
  boundary.
- **Failure isolation.** The slice crashing shouldn't take the host with it.

**Not triggers:**

- "Microservices are best practice."
- "We want to reuse this from another service" — publish a library first.
- Resume-driven architecture.

The operational tax of a service split is severe and well-documented:
network reliability, distributed transactions, observability across
processes, schema versioning, deployment topology. **Default to in-process.**
The slice boundary already gives you most of what you'd want from a service
split — without that tax. Promote only when the in-process arrangement is
causing concrete, measurable pain.

### Reverse moves

Graduation is reversible:

- A graduated workspace package can be inlined back to a folder if the
  boundary turned out wrong.
- A published library can be republished as a workspace package and the
  external version frozen.
- A service can be re-merged into the monolith ("strangler fig" in reverse).

Reverse moves are how you correct over-shoot. They should not be rare.
Architectures that treat graduation as a one-way ratchet calcify.

### When the loaf itself gets too big

A monorepo with 30+ slices and a single flat `domains/` directory eventually
feels heavy. Three options, in order of cost:

1. **Group by bounded context.** `domains/billing/{invoicing,subscriptions,payments}/`
   when groups of slices share value objects, events, or vocabulary. Cheap,
   reversible, no manifest changes.
2. **Extract a sub-loaf.** `packages/billing/src/domains/{invoicing,subscriptions}/`
   — a workspace package that is itself a Sliced Bread structure inside.
   Medium cost, reversible, follows the stage 2→3 rule.
3. **Split the application.** When two halves of the loaf rarely touch and
   have separate users / deployments, the second loaf is a different
   application. Expensive, often irreversible.

Try the cheap moves first. Bounded-context grouping costs nothing and tells
you most of what you'd learn from a hypothetical split.

### The graduation review checklist

Before advancing a slice, write down:

1. **What concrete pain does the current shape cause?** (Build minutes,
   blast radius incidents, ownership friction, contract drift.) If you
   can't name it in one paragraph with a real example, don't graduate.
2. **What does this graduation cost in tooling, process, and friction?**
   Be specific — "extra build step in CI," "every change now needs a
   version bump," etc.
3. **What's the smallest graduation that resolves the pain?** Don't skip
   stages. A folder might be enough; a workspace package might be enough;
   you probably don't need a service.
4. **Is graduation reversible? If not, what would you need to see to undo it?**

Adjective-only justifications ("cleaner," "more scalable," "more
modular") are an architectural smell. They mean someone is graduating to
satisfy a feeling, not to resolve a problem.

---

## Reading order

1. [`../sliced-bread.md`](../sliced-bread.md) — start here for the rationale.
2. This doc — applied patterns and graduation triggers.
3. Language-specific guide ([rust](./rust.md), [go](./go.md), [ts](./ts.md))
   for the actual mechanics in your language. Each covers the *syntax* of
   workspaces, packages, and module privacy; this doc covers the *when*.
4. [`./attribution.md`](./attribution.md) — predecessors and what's distinct.
