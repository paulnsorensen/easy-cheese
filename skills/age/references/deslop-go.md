# Go De-slop Catalog

Per-language evidence for the `age` `deslop` dimension. Each pattern is a Go-specific AI tell to look for during review. Use alongside `dimensions.md`'s `deslop` rubric — this is the "Look for" detail, not a separate severity scale.

## 1. Error string conventions

Go errors are lowercase, no trailing punctuation, and wrap with `%w`.

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

## 2. Named returns with bare `return`

AI loves named returns. They obscure which values are being returned.

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

Named returns are acceptable only in `defer` recovery patterns.

## 3. `context.TODO()` permanently

AI scaffolds with `context.TODO()` and never replaces it.

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

`context.TODO()` means "I haven't decided which context to use yet."
In production code, you should always have decided.

## 4. Pointer to interface

Almost never correct. Interfaces are already reference types.

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

## 6. `fmt.Sprintf` for string concatenation in loops

O(n²) string building.

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

## 8. `init()` for non-trivial setup

AI puts complex initialization in `init()` which can't return errors
and runs at import time with no control.

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
