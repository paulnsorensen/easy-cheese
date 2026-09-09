# Sliced Bread — the shared architecture vocabulary

The pipeline's one page on how code is shaped. Mold's Sketch places a change with it, cook keeps to it, and age's `encapsulation` dimension reviews against it. Read it when a Placement block, a shape-check `crust delta`, or an encapsulation finding needs the terms.

## Layers and terms

| Term | Meaning |
| --- | --- |
| **Slice** | A vertical module grouped by business concept (`orders/`, `pricing/`), not by technical role. A feature change stays inside one slice. |
| **Spine** | The path a request travels: entry → use case → domain → infra. A spine step is where a change sits. Entry lives in `entrypoints/` (one driving adapter per medium — CLI, HTTP, worker, scheduler), use cases and the composition root in `app/`, domain in `domains/*`, infra in `adapters/`. |
| **Crust** | A slice's public seam in the language's native form: exported identifiers in Go, the package `__init__` surface in Python, an index module in TypeScript. Consumers import the crust only; internals may be renamed or split freely. Where the language has no visibility form (e.g. GDScript), the crust is positional — root files public, nested files internal. |
| **Deep module** | A small, stable crust hiding substantial implementation. The goal of every slice. |
| **Crust delta** | Any change to a crust: a new export, a cross-slice import, or a contract change. Always a consequential fork. |
| **Arrow** | A permitted dependency direction. See the quick-check below. |

Cross-cutting concerns (auth, logging, caching) live in `app/` or `adapters/`, never sprinkled across slices.

## Dependency direction quick-check

```text
entrypoints/   →  app/   →  domains/*   →  domains/common/
app/bootstrap  →  adapters/            (composition root only)
adapters/      →  domains/*            (implement domain ports)

Never:
  app/use_cases/*  →  adapters/*
  domains/*    →  adapters/*
  domains/*    →  app/* | entrypoints/*
  adapters/*   →  app/* | entrypoints/*
  common/      →  sibling domains
  anything     →  entrypoints/
```

Arrows describe permitted direction, not required directories. A repo without an `adapters/` or `entrypoints/` layer is not in violation. When the framework natively supplies a role — a routing or CLI host as the entry point, a DI container as the composition root, a native event publisher — use it directly rather than wrapping what you did not need to abstract.

## Anti-patterns

- **Cross-slice internal import** — reaching past the crust into another slice's file. Import from the crust.
- **Domain importing infrastructure** — the domain defines a protocol (port); an adapter implements it.
- **Use case importing a concrete adapter** — the use case takes the port; `app/bootstrap` injects the adapter.
- **Circular slices** — resolve with a domain event in `common/`: the emitter emits, the sibling subscribes. Putting the event in the emitter's crust does not break the cycle — the subscriber still imports the emitter.
- **Premature abstraction** — a registry, base class, or interface with no demonstrated pressure. Use the concrete thing until pressure appears.

## Growth

Structure emerges from demonstrated pressure, not imagination. These signals prompt a look; none is a graded rule on its own:

- A file passes ~200 lines or holds 3+ distinct concepts → extract siblings.
- 3+ related files cluster around a sub-concept → create a subdirectory.
- A file becomes an import hub for its children → it is now a crust.

Two concrete consumers are the *normal* evidence threshold, not a hard requirement. Grade whether concrete pressure exists, not a count: a dispatcher that breaks a real cross-slice cycle is pressure with one event and one subscriber, and a positional crust marking internal files in a privacy-less language is pressure with a single file inside. Not pressure: "we might need this later", "this could be its own module", or an abstraction added only because the pattern might be useful later.

## Where things belong

- **`common/`** — value types, events, or errors used by 2+ slices. Never pre-promote; cycle-breaking events are the stated exception.
- **Adapter** — only when the domain talks to something external (database, API, filesystem, queue). Not for in-process utilities.
- **`app/` use case** — when the operation needs an entry point or a port, or orchestrates 2+ slices. A single-slice operation stays in the slice; a sibling may import another slice's crust directly for in-process queries.
- **Event vs import** — import when A needs B's data; event when B reacts to A and A must not know B. Take the earliest event stage that works: framework-native publisher, then a domain publish port with an `app/`-owned dispatcher, then durable delivery only once it leaves the process.

## Reviewing against Sliced Bread

1. **Import direction** — do all arrows point in a permitted direction? Only the composition root imports concrete adapters; nothing imports `entrypoints/`.
2. **Crust integrity** — do external consumers use the slice's public seam, not its internals?
3. **Model purity** — do domain files import only stdlib, common, and sibling crusts?
4. **Growth justification** — does demonstrated pressure justify each directory or abstraction? Two concrete consumers is the normal threshold, not a hard requirement.
5. **Event usage** — are events reserved for reverse dependencies, not general-purpose messaging?

Severity when a violation lands: **blocker** — an inverted dependency arrow, or infrastructure executing at import time in a domain file. **high** — a cross-slice internal import, circular slices, or a crust bypass with multiple consumers. **medium** — a static domain→infra dependency, premature abstraction, events-as-messaging, or an adapter imported outside the composition root. **low** — a single-consumer crust bypass or naming drift.
