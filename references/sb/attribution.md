# Sliced Bread — Lineage and Attribution

Sliced Bread doesn't invent much. It synthesizes five well-known architectural ideas into one organic growth pattern, then files off the ceremony each predecessor accumulated. This doc credits the predecessors and pins down where Sliced Bread inherits, where it differs, and where its terminology overlaps but means something different.

> Companion to [Sliced Bread](../sliced-bread.md).

---

## Predecessors

### Vertical Slice Architecture — Jimmy Bogard, 2018

**Inherits:** organize-by-feature; "minimize coupling between slices, maximize within"; rejection of mandated layered abstractions; tolerance for slice-local duplication.

**Differs:** Sliced Bread adds the explicit organic growth pattern (file → extract sibling → facade + folder) and the `common/` leaf rule. VSA leaves both unspecified.

**Read:** Bogard, "Vertical Slice Architecture," April 2018.

### Hexagonal Architecture / Ports & Adapters — Alistair Cockburn, 2005

**Inherits:** the entire `adapters/` ↔ `domains/` boundary. The rule "domain defines a protocol (port), adapter implements it" is verbatim Cockburn.

**Differs:** Sliced Bread doesn't distinguish primary (driving) from secondary (driven) ports as a top-level concern — it splits the same role across `entrypoints/` (driving) and `adapters/` (driven) when needed. The two layers together cover what Cockburn calls "ports and adapters."

**Read:** Cockburn, "Hexagonal Architecture," HaT 2005.02.

### Screaming Architecture — Robert C. Martin, 2012

**Inherits:** the principle that the top-level folder layout should "scream" what the system does. `orders/`, `pricing/`, `fulfillment/` are the scream. Not `controllers/`, `services/`, `repositories/`.

**Differs:** nothing meaningful.

**Read:** Martin, "Screaming Architecture," 2012.

### Clean Architecture / Onion — Robert C. Martin, 2012; Jeffrey Palermo, 2008

**Inherits:** the dependency-inversion direction (outer layers depend on inner; inner never depends on outer); domain model purity.

**Differs:** Sliced Bread deliberately drops the concentric ring structure. There are no use-case, interactor, or controller rings — just slices. Layers within a slice are emergent, not prescribed.

**Read:** Martin, "Clean Architecture," 2012; Palermo, "Onion Architecture," 2008.

### Domain-Driven Design — Eric Evans, 2003

**Inherits:** domain events as a first-class concept; ubiquitous-language naming (slice names match business concepts).

**Differs significantly on terminology:**

> **DDD's "shared kernel" is not Sliced Bread's `common/` leaf.**
> Evans' shared kernel is a *bidirectional governance artifact* shared between two bounded contexts that requires team coordination to evolve. Sliced Bread's `common/` is a *unidirectional utility leaf* — it imports nothing from siblings, siblings import freely from it, no governance involved. Use the term "common leaf" to avoid the collision.

Sliced Bread also drops most of DDD's tactical patterns (aggregates, repositories as a separate noun, factories): a slice owns its own model and chooses its own internal structure.

**Read:** Evans, *Domain-Driven Design*, 2003 (Ch. 14: "Maintaining Model Integrity").

---

## What Sliced Bread adds

Ideas not in any single predecessor:

1. **Organic growth pattern.** File → extract sibling → file becomes facade + folder. No predecessor specifies the growth path; most default to pre-built layered structures.
2. **The crust = the index/facade file.** Every slice has a single public API surface. External code only imports from the crust.
3. **Common leaf rule.** `common/` imports nothing from siblings. Strictly unidirectional — distinct from DDD's bidirectional shared kernel.
4. **Event-direction discipline.** Events are for *reverse* dependencies only, not general-purpose messaging.
5. **Concrete growth thresholds.** Numeric triggers (extract ~150–200 lines, hard ceiling 300) instead of "split when it feels right."

---

## What Sliced Bread deliberately drops

| Drop | Why |
|---|---|
| Clean's concentric rings | Adds ceremony for no enforcement gain |
| Hexagonal's primary/secondary distinction as a top-level split | Already handled by the `entrypoints/` vs `adapters/` split |
| DDD's tactical patterns (aggregates, repositories as nouns, factories) | Slice owns its own model; no aggregate-root prescription |
| MediatR / explicit dispatcher | Direct function calls until events are needed |
| Use-case classes per operation | A function in the slice is enough |
| "Application Services" as a separate ring | The slice's public API *is* the application service |
