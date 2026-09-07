# Sliced Bread — the shared architecture vocabulary

The pipeline's one page on how code is shaped. Mold's Sketch places a change with it, cook keeps to it, and age's `encapsulation` dimension reviews against it. Read it when a Placement block, a shape-check `crust delta`, or an encapsulation finding needs the terms.

## Terms

| Term | Meaning |
| --- | --- |
| **Slice** | A vertical module grouped by business concept (`orders/`, `pricing/`), not by technical role. A feature change stays inside one slice. |
| **Spine** | The request path a concept travels: entry → workflow → domain → infra. A spine step is where a change sits on that path. Entry and workflow live in `app/`, domain in `domains/*`, infra in `adapters/`. |
| **Crust** | A slice's public API: its index or barrel file (the full Sliced Bread reference calls this the facade). Consumers import from the crust only. Internals may be renamed or split freely. |
| **Deep module** | A small, stable crust hiding substantial implementation. The goal of every slice. Measure by the ratio of private surface to public surface. |
| **Crust delta** | Any change to a crust: a new export, a cross-slice import, or a contract change. Always a consequential fork. |
| **Arrow** | A permitted dependency direction. See the quick-check below. |

## Dependency direction quick-check

```text
app/           →  domains/*     →  domains/common/
adapters/      →  domains/*

Never:
  domains/*    →  adapters/*
  domains/*    →  app/*
  adapters/*   →  app/*
  common/      →  sibling domains
```

Arrows describe permitted direction, not required directories. A repo without an `adapters/` layer is not in violation.

## Anti-patterns

- **Cross-slice internal import** — reaching past the crust into another slice's file. Import from the crust.
- **Domain importing infrastructure** — the domain defines a protocol (port); an adapter implements it.
- **Circular slices** — resolve with a domain event in `common/` or the emitter's crust.
- **Premature abstraction** — a registry, base class, or interface with one implementation. Use the concrete thing until a second use exists.

## Growth triggers

Structure emerges from pressure, not imagination.

- A file passes ~200 lines or holds 3+ distinct concepts → extract siblings.
- 3+ related files cluster around a sub-concept → create a subdirectory.
- A file becomes an import hub for its children → it is now a crust.

Not triggers: "we might need this later", "this looks like it could be its own module", and a single implementation of a pattern (one adapter, one strategy, one handler).

## Where things belong

- **`common/`** — value types, events, or errors used by 2+ slices. Never pre-promote.
- **Adapter** — only when the domain talks to something external (database, API, filesystem, queue).
- **`app/` use case** — orchestration across 2+ slices. A single-slice operation stays in the slice.
- **Event vs import** — import when A needs B's data; event when B reacts to A and A must not know B.

## Reviewing against Sliced Bread

1. **Import direction** — do all arrows point inward?
2. **Crust integrity** — do consumers import from the index only?
3. **Model purity** — do domain files import only stdlib, common, and sibling crusts?
4. **Growth justification** — does every directory or abstraction have 2+ concrete uses?
5. **Event usage** — are events reserved for reverse dependencies?

Source: the full rationale lives in the user's Sliced Bread reference; this page is the pipeline's stable digest.
