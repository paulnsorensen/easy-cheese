# Sliced Bread Architecture for Go

Organic vertical slices using Go's package model and the `internal/` directory as the enforcement mechanism. No ceremony upfront — structure emerges as complexity demands it.

> Companion to [Sliced Bread](../sliced-bread.md). Read that first for the language-agnostic rationale and anti-patterns. See also [attribution](./attribution.md) for predecessor lineage (VSA, Hexagonal, Screaming, Clean, DDD).

---

## Why Go is a natural fit

Go's package system gives you two compile-time enforcement primitives out of the box:

- **Capitalization controls export.** Lowercase identifiers are package-private. There is no `pub` or `private` keyword — just naming.
- **`internal/` is compile-enforced.** Code under `path/internal/foo` can only be imported by code rooted at `path/`. The Go compiler rejects external imports outright. This is unique among mainstream languages — it gives you slice boundaries that even a determined developer cannot bypass without restructuring.

These two mechanics map cleanly onto Sliced Bread's "crust" concept. The crust is the package directory itself; everything below an `internal/` is hidden from siblings.

**Key insight:** Go's package = directory. There's no facade-file vs internals split like Rust's `foo.rs` + `foo/` convention. The package's exported identifiers *are* the crust. `internal/` lets you have multiple files (or sub-packages) without exposing them.

---

## Core structure

```
my-app/
├── go.mod                            # Module root
├── cmd/
│   └── server/
│       └── main.go                   # Ignition key — calls app.Run()
├── internal/                         # Module-private — invisible to other modules
│   ├── domain/                       # The loaf — all business logic
│   │   ├── common/                   # Common leaf
│   │   │   └── money.go
│   │   ├── orders/                   # A slice
│   │   │   ├── orders.go             # Public API (the crust)
│   │   │   ├── fulfillment.go        # Sibling, same package
│   │   │   └── internal/             # Hidden even from sibling slices
│   │   │       └── validation.go
│   │   └── pricing/                  # Thin slice — one file is fine
│   │       └── pricing.go
│   ├── entrypoints/                  # Inbound — HTTP handlers, gRPC, CLI cmds
│   │   ├── http/
│   │   └── cli/
│   ├── adapters/                     # Outbound — implements domain interfaces
│   │   ├── postgres/
│   │   └── stripe/
│   └── app/                          # Composition root
│       └── app.go
└── pkg/                              # Optional: code intended for external import
```

### The critical mapping

| Sliced Bread concept | Go mechanism |
|---|---|
| The crust (public API) | Exported identifiers (capitalized) in the package's top-level files |
| Slice internals | Lowercase identifiers + `internal/` subdirectories |
| Index/barrel file | The package itself — Go has no separate "index" file |
| "No cross-slice reaching" | Place internals under `internal/`; the compiler rejects sibling imports |
| Pure domain models | No `database/sql`, `net/http`, or third-party SDK imports under `internal/domain/` |
| Entrypoints | `internal/entrypoints/<protocol>/` |
| Adapters | `internal/adapters/<technology>/` |

---

## The package is the crust

In Go, a package's exported (capitalized) names form its public API. There is no separate facade file. To split a slice across multiple files without exposing internals, use *unexported names* + `internal/` subdirectories.

```go
// internal/domain/orders/orders.go — the crust
//
// External callers do:
//   import "my-app/internal/domain/orders"
//   orders.Place(items)
//   var o orders.Order

package orders

type Order struct {
    ID     OrderID
    Status Status
    Items  []LineItem
}

type Status int

const (
    Pending Status = iota
    Fulfilled
    Cancelled
)

// Place is the slice's public entry point.
func Place(items []LineItem) (*Order, error) {
    if err := validateItems(items); err != nil {  // unexported helper, same package
        return nil, err
    }
    return &Order{Items: items, Status: Pending}, nil
}

// validateItems lives in this same file (or any sibling .go file in
// package orders). Lowercase = invisible to sibling slices like pricing/.
func validateItems(items []LineItem) error { /* ... */ }
```

For helpers that want their own package namespace while staying invisible to
sibling slices, drop them under `internal/`. Anything under `orders/internal/`
is importable only by code rooted at `orders/` — the compiler rejects any
other consumer. Helpers there operate on primitives or types they own;
importing the parent `orders` package would form a cycle
(orders → internal → orders).

```go
// internal/domain/orders/internal/limits.go
//
// Anything under orders/internal/ is importable only by files rooted at
// orders/. The compiler rejects any other consumer.

package internal

const MaxLineItems = 100

func CheckCount(n int) error { /* takes a primitive — no cycle with orders */ }
```

### Visibility cheat sheet

| Mechanism | Meaning in Sliced Bread |
|---|---|
| Capitalized name | Exported — part of the package's public API |
| Lowercase name | Package-private — invisible outside this package |
| `internal/` directory | Subtree-private — only importable from within the parent path |
| `pkg/` directory | Convention for code intentionally meant for external consumers |

**Default to lowercase** for everything inside a slice. Promote to exported only by deliberate decision. Every capital letter is a contract.

---

## Growth pattern

### Stage 1: One file per concept

```
internal/domain/
├── common/
│   └── money.go
├── orders/
│   └── orders.go          # everything in one file
└── pricing/
    └── pricing.go
```

### Stage 2: Multiple files, same package

```
internal/domain/orders/
├── orders.go              # core types + public API
├── fulfillment.go         # related logic, same package
└── validation.go          # private helpers (lowercase exports)
```

All three files are in `package orders`. Lowercase identifiers stay hidden; capitalized ones are exposed.

### Stage 3: Hide internals with `internal/`

When `validation.go` grows into multiple files but you don't want them visible to sibling slices, push them down:

```
internal/domain/orders/
├── orders.go
├── fulfillment.go
└── internal/
    ├── validation.go
    └── tax.go
```

Now `internal/domain/pricing/` cannot import `internal/domain/orders/internal/...` even if it tried — the compiler rejects it.

### Stage 4: Sub-packages for genuinely independent concerns

When `fulfillment.go` itself becomes a cluster of files with its own public API:

```
internal/domain/orders/
├── orders.go
├── fulfillment/             # sub-package with its own crust
│   └── fulfillment.go
└── internal/
    └── validation.go
```

`fulfillment` is now a sub-slice. External code can do `import "my-app/internal/domain/orders/fulfillment"`.

---

## Cross-slice communication

### Do: Import the package

```go
// internal/domain/pricing/pricing.go
import "my-app/internal/domain/orders"

func calculate(o *orders.Order) Money { /* ... */ }
```

### Don't: Import a slice's `internal/`

```go
// internal/domain/pricing/pricing.go
import "my-app/internal/domain/orders/internal"  // ← compile error
```

The compiler enforces this. No linter needed.

### Events for reverse dependencies

If `orders` depends on `pricing`, then `pricing` cannot import `orders`. Define the event in `common/`:

```go
// internal/domain/common/events.go
package common

type DomainEvent interface{ event() }

type OrderPlaced struct{ OrderID string }

func (OrderPlaced) event() {}

type EventBus interface {
    Publish(DomainEvent)
    Subscribe(func(DomainEvent))
}
```

Slices emit events via the bus; `app/` wires subscriptions. Synchronous in-process dispatch is the default; an async or queued bus is an adapter implementation choice.

---

## Adapters and interfaces

Domain slices define interfaces (Go's structural typing makes this implicit-friendly). Adapters implement them. The domain never imports adapter code.

```go
// internal/domain/orders/orders.go — defines the port
type Repository interface {
    Save(*Order) error
    FindByID(OrderID) (*Order, error)
}
```

```go
// internal/adapters/postgres/orders.go — implements the port
package postgres

import (
    "database/sql"
    "my-app/internal/domain/orders"
)

type OrderRepo struct {
    DB *sql.DB
}

func (r *OrderRepo) Save(o *orders.Order) error                          { /* ... */ }
func (r *OrderRepo) FindByID(id orders.OrderID) (*orders.Order, error)   { /* ... */ }
```

```go
// internal/app/app.go — wires it together
package app

import (
    "my-app/internal/adapters/postgres"
    "my-app/internal/domain/orders"
    "my-app/internal/entrypoints/http"
)

func Run() error {
    db := openDB()
    repo := &postgres.OrderRepo{DB: db}

    var _ orders.Repository = repo  // compile-time interface check

    return http.Serve(repo)
}
```

The `internal/domain/` tree has zero `database/sql`, `net/http`, or SDK imports. If you see one, that's a boundary violation.

---

## Entrypoints

`internal/entrypoints/` is where external requests translate into domain calls. HTTP handlers, gRPC service impls, CLI subcommands, queue consumers.

```go
// internal/entrypoints/http/orders.go
package http

import (
    "encoding/json"
    "net/http"

    "my-app/internal/domain/orders"
)

func PlaceHandler(repo orders.Repository) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        var items []orders.LineItem
        if err := json.NewDecoder(r.Body).Decode(&items); err != nil {
            http.Error(w, err.Error(), 400)
            return
        }

        o, err := orders.Place(items)
        if err != nil {
            http.Error(w, err.Error(), 422)
            return
        }
        if err := repo.Save(o); err != nil {
            http.Error(w, err.Error(), 500)
            return
        }
        json.NewEncoder(w).Encode(o)
    }
}
```

Entrypoints decode, call domain, encode, map errors. They receive their dependencies as parameters — they do not construct adapters themselves.

---

## When to use `go.work` workspaces

`go.work` is the heavy artillery. Use when module privacy isn't enough:

| Signal | Response |
|---|---|
| Want independent builds and versioning per slice | Multi-module workspace |
| Need to publish a slice as a standalone library | Separate module |
| Single application, <20k LOC | One module + `internal/` is fine |
| Multiple binaries sharing domain logic | Multi-module with shared domain module |

For multi-module:

```
my-app/
├── go.work
├── domain/                  # own module: github.com/me/my-app/domain
│   ├── go.mod
│   ├── orders/
│   └── pricing/
├── adapters/                # own module
│   ├── go.mod
│   └── postgres/
└── cmd/
    └── server/              # own module
        ├── go.mod
        └── main.go
```

The `go.mod` `require` graph now physically encodes the dependency direction.

---

## Rules (Go-specific)

1. **The package is the crust.** A package's exported names are its public API. Don't add a separate "index file" — Go doesn't need it.
2. **Default to lowercase.** Export only with intent. Every capital letter is a contract.
3. **`internal/` is your friend.** Anything you don't want siblings to reach goes under `internal/`. The compiler enforces it for free.
4. **No infrastructure imports in `internal/domain/`.** No `database/sql`, no `net/http`, no SDK packages. (Exception: `encoding/json` struct tags on domain types are pragmatic.)
5. **Interfaces as ports — defined where they're consumed.** Go style: the domain declares what it needs as an interface; adapters satisfy it structurally. Don't put interfaces in adapter packages.
6. **Entrypoints are thin.** Decode, call domain, encode. No business logic. Receive dependencies as parameters.
7. **Common is a leaf.** `internal/domain/common/` imports nothing from sibling slices.
8. **Grow, don't pre-build.** A new slice starts as one `.go` file. It earns more files when crowded, an `internal/` subdirectory when it needs hidden helpers, a sub-package when it has its own crust, a separate module when independent versioning matters.

---

## The `cmd/` and `app/` split

Go convention puts binaries under `cmd/<name>/main.go`. Keep `main.go` trivial — call `app.Run()` and nothing else.

```go
// cmd/server/main.go
package main

import (
    "log"

    "my-app/internal/app"
)

func main() {
    if err := app.Run(); err != nil {
        log.Fatal(err)
    }
}
```

`internal/app/` is the composition root: build adapters, inject them into entrypoints, start the server.

```
            ┌──────────────┐
            │   main.go    │  cmd/server/main.go — calls app.Run()
            └──────┬───────┘
                   │
                   ▼
            ┌──────────────┐
            │     app/     │  Composition root — only package that
            │              │  sees all three layers below
            └──┬───┬───┬───┘
               │   │   │
       ┌───────┘   │   └───────┐
       ▼           ▼           ▼
┌────────────┐ ┌────────┐ ┌──────────┐
│entrypoints/│ │domain/ │ │adapters/ │
└────────────┘ └────────┘ └──────────┘
```

**Who imports whom:**

- **`internal/domain/`** → nothing outside itself
- **`internal/adapters/`** → `internal/domain/` only (implements interfaces)
- **`internal/entrypoints/`** → `internal/domain/` only (calls domain, receives adapters as parameters)
- **`internal/app/`** → all three
- **`cmd/*/main.go`** → `internal/app/` only
