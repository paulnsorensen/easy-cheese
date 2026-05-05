# Sliced Bread Architecture for TypeScript

Organic vertical slices using `package.json` `"exports"` maps and TypeScript project references as the enforcement mechanisms. No ceremony upfront — structure emerges as complexity demands it.

> Companion to [Sliced Bread](../sliced-bread.md). Read that first for the language-agnostic rationale and anti-patterns. See also [attribution](./attribution.md) for predecessor lineage (VSA, Hexagonal, Screaming, Clean, DDD).

---

## Why TypeScript is the trickiest fit

TypeScript has *no built-in compiler-enforced privacy at module boundaries*. The `private` modifier only hides class members. A file's exports are visible to anyone who can resolve the file path — the compiler will not stop `import { internalThing } from "../slices/orders/_secret"`.

Privacy in TypeScript comes from **packaging**, not from language keywords:

| Mechanism | Enforces |
|---|---|
| `package.json` `"exports"` map | What can be imported from a package — Node.js refuses other paths |
| `tsconfig.json` project references | Build graph — TS errors on out-of-graph imports |
| ESLint rules (e.g. `no-restricted-imports`) | Linter-enforced facade |
| Monorepo workspace boundaries (npm/pnpm/yarn workspaces) | Hard separation per package |

**Key insight:** the modern TypeScript facade is the `"exports"` map, not the barrel `index.ts`. Barrel files used to be the recommended pattern; since 2024 they are widely considered an anti-pattern (see "Barrel files considered harmful," below).

---

## Why barrel files are now an anti-pattern

A barrel file (`index.ts` that re-exports from siblings) was the classic facade pattern in TypeScript. It is now considered harmful:

- **Tree-shaking breaks.** Bundlers must follow every re-export to determine if anything in the barrel is used. Even with ESM, complex barrels defeat dead-code elimination — practitioners have measured 60–70% bundle bloat in real projects.
- **Cold-start cost.** Importing one symbol via a barrel forces the module loader to evaluate every re-exported file. For `vitest`, `tsx`, and other dev-time loaders this becomes a multi-second startup penalty.
- **Circular import landmines.** Barrels make cycles silent. `a → index → b → index → a` is invisible until runtime.
- **IDE rename slowdowns.** Every rename has to walk the barrel graph.

The replacement: **`package.json` `"exports"` maps** define the facade declaratively, the bundler reads them directly, and Node.js enforces them at import time.

---

## Core structure

Single-package layout:

```
my-app/
├── package.json                      # "exports" map = the facade
├── tsconfig.json
├── src/
│   ├── domains/                      # The loaf
│   │   ├── common/                   # Common leaf
│   │   │   └── money.ts
│   │   ├── orders/                   # A slice
│   │   │   ├── orders.ts             # Public API (the crust)
│   │   │   ├── fulfillment.ts        # Sibling
│   │   │   └── _validation.ts        # Underscore = "do not import"
│   │   └── pricing/                  # Thin slice — one file is fine
│   │       └── pricing.ts
│   ├── entrypoints/                  # Inbound — HTTP handlers, CLI, etc.
│   │   ├── http/
│   │   └── cli/
│   ├── adapters/                     # Outbound — implements domain protocols
│   │   ├── postgres/
│   │   └── stripe/
│   └── app/                          # Composition root
│       └── app.ts
└── tests/
```

Monorepo layout (workspaces):

```
my-app/
├── package.json                      # workspaces: ["packages/*"]
├── tsconfig.json                     # references each package
└── packages/
    ├── domain-orders/                # own package — own "exports"
    │   ├── package.json
    │   ├── src/
    │   │   ├── orders.ts             # exposed via package.json "exports"
    │   │   └── internal/
    │   │       └── validation.ts     # not exposed, sibling-private
    │   └── tsconfig.json
    ├── domain-pricing/
    ├── adapters-postgres/
    └── app-server/
```

### The critical mapping

| Sliced Bread concept | TypeScript mechanism |
|---|---|
| The crust (public API) | `package.json` `"exports"` map (or, in single-package, the slice's named entry file) |
| Slice internals | Files not listed in `"exports"`; underscore-prefixed names by convention |
| Index/barrel file | **Not used.** `"exports"` map replaces it. |
| "No cross-slice reaching" | `"exports"` map (Node enforces) + `no-restricted-imports` (lint) |
| Pure domain models | No `pg`, `stripe`, `express` imports under `domains/` |
| Entrypoints | `entrypoints/http`, `entrypoints/cli`, etc. |
| Adapters | `adapters/<technology>/` |

---

## The `"exports"` map is the crust

In a monorepo workspace package:

```json
// packages/domain-orders/package.json
{
  "name": "@my-app/domain-orders",
  "type": "module",
  "exports": {
    ".": "./dist/orders.js",
    "./events": "./dist/events.js"
  }
}
```

External code can do:

```ts
import { Order, place } from "@my-app/domain-orders";
import { OrderPlaced } from "@my-app/domain-orders/events";
```

But cannot do:

```ts
import { validate } from "@my-app/domain-orders/internal/validation";
//                       ^ Node.js refuses; tsserver flags it
```

Single-package equivalent (no workspace): use `tsconfig.json` `paths` to alias the slice root, plus a lint rule (`no-restricted-imports`) to forbid deeper paths.

```json
// tsconfig.json
{
  "compilerOptions": {
    "paths": {
      "@/orders": ["src/domains/orders/orders.ts"],
      "@/orders/events": ["src/domains/orders/events.ts"]
    }
  }
}
```

```js
// .eslintrc.js
{
  rules: {
    "no-restricted-imports": ["error", {
      patterns: ["@/orders/internal/*", "**/domains/orders/_*"]
    }]
  }
}
```

### Visibility cheat sheet

| Mechanism | Meaning in Sliced Bread |
|---|---|
| Listed in `"exports"` | Public — part of the package's API |
| Not listed in `"exports"` | Package-private — Node refuses; TS errors with `"moduleResolution": "node16"+` |
| `_underscore-prefix` filename | Convention: "do not import from outside this slice" — relies on lint, not compiler |
| `private` class member | Object-level only — does not affect module imports |

**Default to "not exported."** Add to `"exports"` only by deliberate decision. The exports map *is* the contract.

---

## Growth pattern

### Stage 1: One file per concept

```
src/domains/
├── common/
│   └── money.ts
├── orders/
│   └── orders.ts            # everything in one file
└── pricing/
    └── pricing.ts
```

### Stage 2: Extract siblings

```
src/domains/orders/
├── orders.ts                # the crust — what tsconfig paths point at
├── fulfillment.ts
└── _validation.ts
```

Update `tsconfig.json` `paths` and the lint rule if needed; the slice's public surface (`orders.ts`) stays the import target.

### Stage 3: Promote to a workspace package

When the slice has stable boundaries and benefits from independent build/test, lift it into a workspace package:

```
packages/domain-orders/
├── package.json             # "exports" replaces the tsconfig paths trick
├── src/
│   ├── orders.ts
│   ├── fulfillment.ts
│   └── internal/
│       └── validation.ts
└── tsconfig.json
```

Now Node.js enforces the boundary. No lint rules needed.

---

## Cross-slice communication

### Do: Import via the package name (or path alias)

```ts
// src/domains/pricing/pricing.ts
import { Order, type LineItem } from "@my-app/domain-orders";
```

### Don't: Reach into internals

```ts
import { validate } from "@my-app/domain-orders/internal/validation";  // ← refused
import type { OrderInternal } from "../orders/_validation";            // ← lint error
```

### Events for reverse dependencies

If `orders` depends on `pricing`, then `pricing` cannot import `orders`. Define the event in `common/`:

```ts
// src/domains/common/events.ts
export type DomainEvent =
  | { type: "OrderPlaced"; orderId: string }
  | { type: "PriceChanged"; sku: string; newPrice: number };

export interface EventBus {
  publish(event: DomainEvent): void;
  subscribe(handler: (event: DomainEvent) => void): void;
}
```

Slices emit; `app/` wires subscriptions. Synchronous in-process dispatch is the default; an async or queued bus is an adapter implementation choice.

---

## Adapters and protocols

Domain slices define interfaces. Adapters implement them.

```ts
// src/domains/orders/orders.ts — defines the port
export interface OrderRepository {
  save(order: Order): Promise<void>;
  findById(id: OrderId): Promise<Order | null>;
}
```

```ts
// src/adapters/postgres/orders.ts — implements the port
import type { Order, OrderId, OrderRepository } from "@/orders";
import { Pool } from "pg";

export class PostgresOrderRepo implements OrderRepository {
  constructor(private pool: Pool) {}

  async save(order: Order): Promise<void> { /* ... */ }
  async findById(id: OrderId): Promise<Order | null> { /* ... */ }
}
```

```ts
// src/app/app.ts — wires it together
import { Pool } from "pg";
import express from "express";
import { PostgresOrderRepo } from "@/adapters/postgres/orders";
import { placeOrderHandler } from "@/entrypoints/http/orders";

export async function run() {
  const pool = new Pool({ /* config */ });
  const repo = new PostgresOrderRepo(pool);

  const app = express();
  app.post("/orders", placeOrderHandler(repo));
  app.listen(3000);
}
```

The `domains/` tree has zero `pg`, `express`, `stripe`, or HTTP-client imports. If you see one, that's a boundary violation. (Exception: `zod` schemas on domain types are pragmatic and acceptable.)

---

## Entrypoints

`entrypoints/` translates external requests into domain calls. Express handlers, Next.js route handlers, tRPC procedures, CLI commands.

```ts
// src/entrypoints/http/orders.ts
import type { Request, Response } from "express";
import { type OrderRepository, place, type LineItem } from "@/orders";

export function placeOrderHandler(repo: OrderRepository) {
  return async (req: Request, res: Response) => {
    const items = req.body as LineItem[];
    try {
      const order = await place(items);
      await repo.save(order);
      res.json(order);
    } catch (err) {
      res.status(422).json({ error: (err as Error).message });
    }
  };
}
```

Entrypoints decode, call domain, encode, map errors. They receive dependencies as parameters.

---

## When to use TypeScript project references

`tsconfig.json` `references` give you incremental build graphs and out-of-graph import errors. Use when:

| Signal | Response |
|---|---|
| Slow `tsc` rebuilds across slices | Add references — only changed slices recompile |
| Want explicit "this slice depends on that one" declared in config | References declare it |
| Need stricter compile-time isolation than lint provides | References are TS-enforced |
| Already in a workspace monorepo | Pair references with workspaces — they layer cleanly |

```json
// tsconfig.json (root)
{
  "files": [],
  "references": [
    { "path": "./packages/domain-common" },
    { "path": "./packages/domain-orders" },
    { "path": "./packages/domain-pricing" },
    { "path": "./packages/adapters-postgres" },
    { "path": "./packages/app-server" }
  ]
}
```

```json
// packages/domain-orders/tsconfig.json
{
  "extends": "../../tsconfig.base.json",
  "compilerOptions": {
    "outDir": "./dist",
    "composite": true
  },
  "references": [
    { "path": "../domain-common" }
  ]
}
```

If `domain-orders` doesn't reference `adapters-postgres`, importing from it now causes a TS build error — not just a lint warning.

---

## Rules (TypeScript-specific)

1. **The `"exports"` map is the crust.** Use it in workspace packages. In single-package projects, use `tsconfig.json` `paths` + a lint rule that forbids deep imports.
2. **Avoid barrel files.** No `src/domains/orders/index.ts` that re-exports from siblings. Either use `"exports"` or alias the slice's root file directly.
3. **Default to "not exported."** Add to `"exports"` only by deliberate decision. Underscore-prefix files inside a slice when they are internal helpers.
4. **No infrastructure imports in `domains/`.** No `pg`, `mysql2`, `express`, `axios`, `stripe`, `aws-sdk`. `zod` schemas on domain types are pragmatic.
5. **Interfaces as ports.** Domain slices declare interfaces that adapters implement. Don't put interfaces in adapter packages.
6. **Entrypoints are thin.** Parse, call, serialize. No business logic. Receive adapters as constructor arguments or function parameters.
7. **Common is a leaf.** `domains/common/` imports nothing from sibling slices.
8. **Grow, don't pre-build.** A new slice starts as one `.ts` file. Extract siblings when crowded. Promote to a workspace package when the slice's boundary is stable enough to benefit from compile-time enforcement.

---

## The `app/` and entry point split

Top-level entry (`bin/server.ts` or `src/index.ts`) should be trivial — it calls `app.run()` and nothing else.

```ts
// src/index.ts
import { run } from "@/app";

run().catch((err) => {
  console.error(err);
  process.exit(1);
});
```

`app/` is the composition root: instantiate adapters, inject them into entrypoints, mount routes, start the server.

```
            ┌──────────────┐
            │  index.ts    │  Trivial — calls app.run()
            └──────┬───────┘
                   │
                   ▼
            ┌──────────────┐
            │     app/     │  Composition root — sees all three layers
            └──┬───┬───┬───┘
               │   │   │
       ┌───────┘   │   └───────┐
       ▼           ▼           ▼
┌────────────┐ ┌────────┐ ┌──────────┐
│entrypoints/│ │domains/│ │adapters/ │
└────────────┘ └────────┘ └──────────┘
```

**Who imports whom:**

- **`domains/`** → only `domains/common/` and stdlib types
- **`adapters/`** → `domains/` (implements interfaces)
- **`entrypoints/`** → `domains/` (calls domain functions, receives adapters as params)
- **`app/`** → all three
- **`index.ts`** → `app/` only
