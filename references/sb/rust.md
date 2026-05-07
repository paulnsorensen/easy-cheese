# Sliced Bread Architecture for Rust

Organic vertical slices that grow from simple files into structured modules, using Rust's module system and privacy model as the enforcement mechanism. No ceremony upfront — structure emerges as complexity demands it.

> Companion to [Sliced Bread](../sliced-bread.md). Read that first for the language-agnostic rationale and anti-patterns. See also [attribution](./attribution.md) for predecessor lineage (VSA, Hexagonal, Screaming, Clean, DDD).

---

## Why Rust is a natural fit

Rust's module system was *designed* around the facade pattern. Aaron Turon's 2017 survey of `futures`, `regex`, `rayon`, `serde`, `std`, and other major crates found that virtually all of them used `pub use` re-exports to decouple internal file organization from the public API surface. The Rust 2018 edition formalized this by introducing the `foo.rs` + `foo/` convention — a file that acts as a facade over a directory of the same name.

This is exactly the Sliced Bread growth pattern. Rust just gives it compiler-enforced privacy boundaries for free.

**Key insight:** Rust's tightest privacy boundary is the module subtree. Private items are visible to child modules but invisible to siblings. This makes domain modules natural bounded contexts — a `users/` slice can enforce invariants across all its internals while hiding everything behind `pub use` re-exports. Horizontal layers (separate `models/`, `handlers/`, `services/` folders) work *against* this strength by forcing everything to be `pub(crate)`.

---

## Core structure

```
src/
├── lib.rs                         # Table of contents — declares all four modules
├── main.rs                        # Ignition key — calls app::run()
├── domain/                        # The loaf — all business logic lives here
│   ├── mod.rs                     # Declares child modules, re-exports public API
│   ├── common/                    # Common leaf (no sibling deps; not DDD's shared kernel)
│   │   └── mod.rs
│   ├── orders.rs                  # ← A slice facade (the crust)
│   ├── orders/                    # ← Internals behind the facade
│   │   ├── model.rs
│   │   ├── fulfillment.rs         # Can itself become a facade later
│   │   └── validation.rs
│   └── pricing.rs                 # Thin slice — single file is fine
├── entrypoints/                   # Inbound surface — where the outside world calls in
│   ├── mod.rs
│   ├── commands.rs                # Tauri commands
│   └── routes.rs                  # axum route handlers
├── adapters/                      # Outbound — implements domain traits
│   ├── mod.rs
│   ├── sqlite.rs
│   └── github.rs
└── app/                           # Composition root — wires everything together
    └── mod.rs
```

### The critical mapping

| Sliced Bread concept | Rust mechanism |
|---------------------|----------------|
| The crust (public API) | `foo.rs` — the facade file |
| Slice internals | `foo/` — the directory of private submodules |
| Index/barrel file | `pub use` re-exports in `foo.rs` |
| "No cross-slice reaching" | Module privacy — siblings can't see each other's internals |
| Pure models | No `use rusqlite`, `use axum`, etc. in `domain/` |
| Entrypoints call in | `entrypoints/` translates external requests into domain calls |
| Adapters implement out | `adapters/` implements domain-defined traits |
| One-way dependencies | Enforced by `use` paths; cycles won't compile cleanly |

---

## The facade is the file

In Rust 2018+, when you have both `orders.rs` and `orders/`, the file `orders.rs` **is** the module root. Everything in `orders/` is a child module. This is the facade pattern with zero boilerplate — the language gives it to you.

```rust
// src/domain/orders.rs — THE CRUST
//
// This file IS the public API. External code does:
//   use crate::domain::orders::Order;
//   use crate::domain::orders::place_order;
//
// They never touch orders/model.rs or orders/fulfillment.rs directly.

mod model;        // private — declares orders/model.rs
mod fulfillment;  // private — declares orders/fulfillment.rs
mod validation;   // private — declares orders/validation.rs

// Re-export the public surface
pub use model::Order;
pub use model::OrderStatus;
pub use model::LineItem;
pub use fulfillment::FulfillmentService;

// Public functions that orchestrate internals
pub fn place_order(items: Vec<LineItem>) -> Result<Order, OrderError> {
    validation::validate_items(&items)?;
    let order = Order::new(items);
    Ok(order)
}

// This stays private — internal error type
pub(crate) struct OrderError { /* ... */ }
```

```rust
// src/domain/orders/model.rs — INTERNAL
//
// This file defines the core types. It's private to the orders module.
// Only orders.rs (the facade) decides what gets re-exported.

pub struct Order {
    pub id: OrderId,
    pub status: OrderStatus,
    pub items: Vec<LineItem>,
}

pub struct LineItem { /* ... */ }

pub enum OrderStatus {
    Pending,
    Fulfilled,
    Cancelled,
}

// Not re-exported — truly internal
pub(super) fn recalculate_totals(order: &mut Order) { /* ... */ }
```

### Visibility cheat sheet

| Visibility | Meaning in Sliced Bread |
|-----------|------------------------|
| `pub` | Part of the crate's public API (use sparingly) |
| `pub(crate)` | Visible across slices within the crate — the "internal public" |
| `pub(super)` | Visible to the facade file only — internal to the slice |
| `pub(in crate::domain)` | Visible within the domain module tree only |
| (no modifier) | Private to the current file |

**Default to `pub(super)`** for items inside a slice's subfolder. The facade (`orders.rs`) then selectively promotes items to `pub` or `pub(crate)` via re-exports. This is the "crust is the contract" rule enforced by the compiler.

---

## Growth pattern

### Stage 1: One file per concept

```
src/domain/
├── mod.rs
├── common.rs     # shared types
├── orders.rs     # everything in one file
└── pricing.rs    # everything in one file
```

This is fine. Don't create folders preemptively.

### Stage 2: Extract sibling files

When `orders.rs` gets crowded, you split — but the file *becomes the facade* automatically:

```
src/domain/
├── mod.rs
├── common.rs
├── orders.rs       # ← was the whole slice, now becomes the facade
├── orders/
│   ├── model.rs    # ← extracted from orders.rs
│   └── validation.rs
└── pricing.rs
```

The `pub use` re-exports in `orders.rs` mean **no call sites change**. Anyone doing `use crate::domain::orders::Order` still works. This is the key property — the facade absorbs the refactoring.

### Stage 3: Nested facades

When `fulfillment.rs` itself gets complex, it becomes its own facade:

```
src/domain/
├── mod.rs
├── orders.rs                # facade
├── orders/
│   ├── model.rs
│   ├── validation.rs
│   ├── fulfillment.rs       # ← sub-facade
│   └── fulfillment/
│       ├── shipping.rs
│       └── tracking.rs
└── pricing.rs
```

The pattern is fractal. Every `.rs` file is potentially a facade over a same-named directory. You only add the directory when you need it.

---

## Cross-slice communication

### Do: Import through the facade

```rust
// In src/domain/pricing.rs
use crate::domain::orders::Order;       // ✓ goes through the crust
use crate::domain::orders::LineItem;    // ✓ goes through the crust
```

### Don't: Reach into internals

```rust
// In src/domain/pricing.rs
use crate::domain::orders::model::Order;           // ✗ compiler allows it if pub,
                                                    //   but architecturally wrong
use crate::domain::orders::fulfillment::Tracker;   // ✗ reaching into a slice
```

**Enforcement:** Keep submodules private (`mod model` not `pub mod model`). The compiler then prevents the wrong imports entirely. No linter needed.

### Events for reverse dependencies

If `orders` depends on `pricing`, then `pricing` must not `use` anything from `orders`. For reverse communication, define events in `common`:

```rust
// src/domain/common.rs
pub enum DomainEvent {
    OrderPlaced { order_id: OrderId },
    PriceChanged { sku: Sku, new_price: Money },
}

pub trait EventBus: Send + Sync {
    fn publish(&self, event: DomainEvent);
    fn subscribe(&self, handler: Box<dyn Fn(&DomainEvent) + Send>);
}
```

Slices emit events. The `app/` layer wires up the subscriptions. No slice knows who's listening.

---

## Adapters and traits

Domain slices define traits (ports). Adapters implement them. The domain never imports adapter code.

```rust
// src/domain/orders.rs — defines the port
pub trait OrderRepository: Send + Sync {
    fn save(&self, order: &Order) -> Result<(), RepositoryError>;
    fn find_by_id(&self, id: &OrderId) -> Result<Option<Order>, RepositoryError>;
    fn find_pending(&self) -> Result<Vec<Order>, RepositoryError>;
}
```

```rust
// src/adapters/sqlite.rs — implements the port
use crate::domain::orders::{Order, OrderId, OrderRepository, RepositoryError};

pub struct SqliteOrderRepo {
    conn: rusqlite::Connection,
}

impl OrderRepository for SqliteOrderRepo {
    fn save(&self, order: &Order) -> Result<(), RepositoryError> {
        // rusqlite calls here — this is the only place they live
        todo!()
    }
    // ...
}
```

```rust
// src/app.rs — wires it together
use crate::domain::orders::OrderRepository;
use crate::adapters::sqlite::SqliteOrderRepo;
use crate::entrypoints::routes;

pub fn run() {
    // Build adapters
    let repo: Arc<dyn OrderRepository> = Arc::new(SqliteOrderRepo::new("app.db"));

    // Mount entrypoints with injected dependencies
    let router = axum::Router::new()
        .route("/orders", post(routes::place_order_handler))
        .with_state(repo);

    // Start the server
    // ...
}
```

The `domain/` module tree has **zero** `use rusqlite`, `use axum`, `use octocrab`, etc. If you see a framework import in `domain/`, something is wrong.

---

## Entrypoints

`entrypoints/` is what most projects call "handlers" — the code that receives an external request and translates it into a domain operation. CLI subcommands, REST route handlers, Tauri commands, gRPC service impls, webhook receivers. If you've written `handlers/` or `controllers/` before, this is the same role under a more honest name.

Entrypoints are the **mirror image** of adapters. Adapters implement domain traits (the domain calls *out* through them). Entrypoints call *into* the domain. Both are framework-specific. Neither contains business logic.

The important distinction: **the domain and adapters together form the core application — a library that could be used by any entrypoint.** The entrypoints are just different ways to drive that library. A REST API, a CLI tool, and a Tauri desktop app could all share the same `domain/` and `adapters/`, each providing their own `entrypoints/`.

```rust
// src/entrypoints/commands.rs — Tauri commands
use crate::domain::orders::{self, LineItem, Order};
use crate::domain::orders::OrderRepository;

#[tauri::command]
pub async fn place_order(
    items: Vec<LineItem>,
    repo: tauri::State<'_, Box<dyn OrderRepository>>,
) -> Result<Order, String> {
    orders::place_order(items)
        .and_then(|order| {
            repo.save(&order)?;
            Ok(order)
        })
        .map_err(|e| e.to_string())
}
```

```rust
// src/entrypoints/routes.rs — axum handlers
use axum::{Json, extract::State};
use crate::domain::orders::{self, LineItem, Order};
use crate::domain::orders::OrderRepository;

pub async fn place_order_handler(
    State(repo): State<Arc<dyn OrderRepository>>,
    Json(items): Json<Vec<LineItem>>,
) -> Result<Json<Order>, AppError> {
    let order = orders::place_order(items)?;
    repo.save(&order)?;
    Ok(Json(order))
}
```

### What entrypoints do

- **Deserialize** incoming requests (JSON, CLI args, IPC messages)
- **Call** domain functions and trait methods
- **Serialize** domain results into responses
- **Map** domain errors into framework-specific error responses

### What entrypoints do NOT do

- Business logic (that's `domain/`)
- Database queries (that's `adapters/`)
- Construct their own dependencies (that's `app/` — entrypoints receive injected services)

### Entrypoints receive, they don't construct

Entrypoints take their dependencies as parameters — injected by the `app/` layer during composition. A Tauri command receives a `State<Box<dyn OrderRepository>>`. An axum handler receives `State<Arc<dyn OrderRepository>>`. The entrypoint never knows it's talking to SQLite vs Postgres vs an in-memory mock.

---

## When to use workspaces

Workspaces are the heavy artillery. Use them when module privacy isn't enough:

| Signal | Response |
|--------|----------|
| Want independent compile times | Workspace with `crates/` |
| Need to publish a slice as a standalone library | Workspace |
| Team boundaries align with slice boundaries | Workspace |
| Single application, <20k LOC | Single crate with `domain/` modules is fine |
| Multiple binaries sharing domain logic | Workspace with a shared `domain` crate |

For a workspace, each slice becomes its own crate:

```
Cargo.toml (workspace)
crates/
├── domain-common/       # common-leaf crate
├── domain-orders/       # orders slice crate
├── domain-pricing/      # pricing slice crate
├── adapters-sqlite/     # adapter crate
└── app/                 # binary crate, depends on everything
```

Dependency direction is now enforced in `Cargo.toml` — if `domain-orders` doesn't list `domain-pricing` as a dependency, the code physically cannot import from it. This is the strongest architectural guarantee Rust offers.

---

## Rules (Rust-specific)

1. **The facade is the file** — `foo.rs` is the public API for the `foo` slice. `foo/` contains private submodules. External code only `use`s from `foo.rs`, never from `foo/*.rs`.

2. **`mod` is private by default** — Declare child modules with `mod`, not `pub mod`. Selectively re-export with `pub use`. This is the crust.

3. **`pub(super)` for slice internals** — Items in `orders/model.rs` should be `pub(super)`, not `pub`. The facade then decides what to promote.

4. **No framework imports in `domain/`** — If you see `use rusqlite`, `use axum`, `use reqwest`, or `use serde` in a domain file, that's a boundary violation. (Exception: `serde::{Serialize, Deserialize}` on domain types is pragmatic and widely accepted.)

5. **Traits as ports** — Domain slices define trait interfaces. `adapters/` implements them. `entrypoints/` calls through them. `app/` wires them.

6. **Entrypoints are thin** — They deserialize, call domain, serialize. No business logic, no direct adapter access. They receive dependencies via injection.

7. **Common is a leaf** — `domain/common/` imports nothing from sibling slices. It only contains types, errors, and traits that multiple slices share.

8. **Grow, don't pre-build** — A new slice starts as a single `.rs` file. It earns a folder when it needs one. It earns a workspace crate when module privacy isn't enough.

---

## The app layer

`app/` is the one horizontal layer in the architecture. It sits on top of the vertical slices and is the only place where domain traits meet concrete adapters. It's the composition root, the entry point orchestrator, and the home for anything framework-specific that doesn't belong in `domain/` or `adapters/`.

### What lives in `app/`

| Concern | Example |
|---------|---------|
| Composition / DI wiring | Building concrete types, injecting adapters into entrypoints |
| Startup / shutdown | Initializing the database, spawning background tasks, graceful shutdown |
| Configuration | Loading config files, environment variables, choosing which adapters to wire |
| Router / command registration | Mounting entrypoint handlers onto the framework (axum Router, Tauri builder) |

### What does NOT live in `app/`

| Concern | Where it belongs |
|---------|-----------------|
| Business rules | `domain/` slices |
| Request handling logic | `entrypoints/` |
| Database queries, API clients | `adapters/` |
| Domain types and traits | `domain/` slices |

### `app/` as a facade too

`app/` follows the same growth pattern as domain slices. It starts as a single file, earns a folder when it needs one:

```
# Stage 1: Simple
src/app.rs                    # everything in one file

# Stage 2: Growing
src/app.rs                    # facade — re-exports, run()
src/app/
├── config.rs                 # configuration loading
├── startup.rs                # wiring adapters to entrypoints
└── router.rs                 # mounting routes / registering commands
```

---

## The crate root: `lib.rs` and `main.rs`

`lib.rs` is the crate's table of contents. It declares the three top-level modules and nothing else. All the interesting work happens inside them.

```rust
// src/lib.rs — the table of contents
//
// Declares the architecture's four layers.
// Does not contain logic, types, or wiring.

pub mod domain;
pub mod entrypoints;
pub mod adapters;
pub mod app;
```

`main.rs` is a thin shim that calls into the `app` layer to bootstrap:

```rust
// src/main.rs — the ignition key
//
// This file should be trivially small. It calls app::run()
// and that's it. All composition logic lives in app/.

fn main() {
    my_crate::app::run();
}
```

Or for async applications:

```rust
#[tokio::main]
async fn main() {
    my_crate::app::run().await;
}
```

### Why this split matters

- **`lib.rs` makes the crate testable** — integration tests in `tests/` can `use my_crate::domain::orders::Order` without going through `main`.
- **`main.rs` stays trivial** — it's just the entry point. No logic, no wiring, no imports beyond `app::run()`.
- **`app/` owns the composition** — it's the only module that imports from both `domain/` and `adapters/`. Domain slices never see adapters directly. Adapters only see the domain traits they implement.

### Dependency flow

```
            ┌──────────────┐
            │   main.rs    │  Calls app::run(). Nothing else.
            └──────┬───────┘
                   │
                   ▼
            ┌──────────────┐
            │    app/      │  Composition root. The only module that
            │              │  sees all three layers below.
            └──┬───┬───┬───┘
               │   │   │
       ┌───────┘   │   └───────┐
       ▼           ▼           ▼
┌────────────┐ ┌────────┐ ┌──────────┐
│entrypoints/│ │domain/ │ │adapters/ │
│            │ │        │ │          │
│ calls ─────┼─▶        │◀─ impls ── │
│ into       │ │        │ │ traits   │
└────────────┘ └────────┘ └──────────┘
```

**Who can import from whom:**

- **`domain/`** → nothing outside itself (pure, no framework deps)
- **`adapters/`** → `domain/` only (implements domain traits)
- **`entrypoints/`** → `domain/` only (calls domain functions, receives adapters via DI)
- **`app/`** → all three (wires adapters into entrypoints, owns startup)
- **`main.rs`** → `app/` only
