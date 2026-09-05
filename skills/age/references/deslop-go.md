# Go De-slop Catalog

This section provides Go evidence for the `age` `deslop` dimension.
Each pattern names a Go-specific AI signature for review.
Most patterns map to a staticcheck or golangci-lint rule.
These rules give reviewers citable names for findings.
Use this section with the `deslop` rubric in `dimensions.md`.
This section provides review details, not a separate severity scale.

## 1. Error string conventions

Go error strings use lowercase text and no trailing punctuation.
Go code wraps returned errors with `%w`.

```go
// SLOP
return fmt.Errorf("Failed to open file: %s", err)
return errors.New("User not found.")

// CLEAN
return fmt.Errorf("open file: %w", err)
return errors.New("user not found")
```

The `%w` verb wraps the error so callers can use `errors.Is`/`errors.As`.
Use `%v` only when you intentionally want to break the error chain.

Staticcheck `ST1005` checks error-string capitalization and punctuation.
`errorlint` checks `%w` and `%v` wrapping.

## 2. Named returns with bare `return`

A bare `return` in a long function is the defect. A named result is not.
Grade the bare `return`, not the declaration.

```go
// SLOP
func getUser(id int) (user *User, err error) {
    user = db.Find(id)
    if user == nil {
        err = errors.New("not found")
        return  // Which values? Have to read the whole function
    }
    return
}

// CLEAN
func getUser(id int) (*User, error) {
    user := db.Find(id)
    if user == nil {
        return nil, errors.New("user not found")
    }
    return user, nil
}
```

A named result is correct in several cases that the Go guide permits.
Use one to recover a panic in a `defer` block.
Use one to document two results of the same type.
Use one to modify a result in a `defer` block.
Keep the explicit `return user, nil` form in every case.
The `nakedret` and revive `bare-return` linters flag the bare `return`.

## 3. `context.TODO()` permanently

AI often generates `context.TODO()` and leaves it in place.

```go
// SLOP
func handleRequest(w http.ResponseWriter, r *http.Request) {
    ctx := context.TODO()
    result, err := db.Query(ctx, query)
}

// CLEAN — use the context you already have
func handleRequest(w http.ResponseWriter, r *http.Request) {
    result, err := db.Query(r.Context(), query)
}
```

`context.TODO()` records that the caller has not chosen a context yet.
Replace it with the caller's context before you ship production code.
`context.Background()` stays correct at the top of `main`, in a test, and in an initializer.

## 4. Pointer to interface

Avoid a pointer to an interface in almost every case.
An interface value is a two-word pair: a type and a value pointer.
Passing it by value copies that pair, not the concrete data behind it.
A pointer to an interface adds one indirection and no benefit.

```go
// SLOP
func NewService(repo *Repository) *Service { ... }
// where Repository is an interface

// CLEAN
func NewService(repo Repository) *Service { ... }
```

## 5. Goroutine leaks

AI spawns goroutines without cancellation paths.

```go
// SLOP — runs forever, no way to stop it
go func() {
    for {
        doWork()
        time.Sleep(time.Second)
    }
}()

// CLEAN — respects context cancellation
go func(ctx context.Context) {
    ticker := time.NewTicker(time.Second)
    defer ticker.Stop()
    for {
        select {
        case <-ctx.Done():
            return
        case <-ticker.C:
            doWork()
        }
    }
}(ctx)
```

`go.uber.org/goleak` catches leaked goroutines during tests.

## 6. `fmt.Sprintf` for string concatenation in loops

Repeated string building has O(n²) cost.

```go
// SLOP
var result string
for _, s := range items {
    result = fmt.Sprintf("%s%s", result, s)
}

// CLEAN
var b strings.Builder
for _, s := range items {
    b.WriteString(s)
}
result := b.String()
```

`perfsprint` flags this pattern.

## 7. Stuttering package names

```go
// SLOP — user.UserService, user.UserModel
package user
type UserService struct{}
type UserModel struct{}

// CLEAN — user.Service, user.Model
package user
type Service struct{}
type Model struct{}
```

Revive `exported` reports this issue ("type name will be used as `user.UserService` by other packages").

## 8. `init()` for non-trivial setup

AI puts complex initialization in `init()`.
`init()` cannot return errors.
`init()` runs at import time, so callers cannot control it.

```go
// SLOP
func init() {
    db, err := sql.Open("postgres", os.Getenv("DATABASE_URL"))
    if err != nil {
        log.Fatal(err)  // Kills the process at import time
    }
    globalDB = db
}

// CLEAN — explicit initialization the caller controls
func NewDB(dsn string) (*sql.DB, error) {
    return sql.Open("postgres", dsn)
}
```

`gochecknoinits` flags every `init()` function.

## Sources

- The Go wiki covers error strings, naked returns, package-name stutter, and contexts in Code Review Comments (go.dev/wiki/CodeReviewComments).
- The Uber Go guide (github.com/uber-go/guide) covers goroutine lifetimes and `init()` avoidance.
- The golangci-lint linters index (golangci-lint.run/usage/linters) lists `nakedret`, `perfsprint`, `gochecknoinits`, and revive rules.
- `go.uber.org/goleak` detects goroutine leaks during tests.
