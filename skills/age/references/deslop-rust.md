# Rust De-slop Catalog

Per-language evidence for the `age` `deslop` dimension. Each pattern is a Rust-specific AI tell to look for during review; most map to a clippy lint, giving a citable rule name to attach to a finding. Use alongside `dimensions.md`'s `deslop` rubric — this is the "Look for" detail, not a separate severity scale.

## 1. Excessive `.clone()` to silence the borrow checker

LLMs reach for `.clone()` as a universal fix for ownership errors.

**Fix:**

- Use borrowing (`&` and `&mut`) instead
- Take `&str` instead of `String` in function parameters
- Use `.as_ref()` on `Option`/`Result` instead of cloning to unwrap
- Rule: `.clone()` is banned unless you can explain why you need owned data

```rust
// SLOP
fn greet(name: String) { println!("Hello, {name}"); }
let msg = my_string.clone();
greet(msg);

// CLEAN
fn greet(name: &str) { println!("Hello, {name}"); }
greet(&my_string);
```

## 2. `.unwrap()` everywhere

Creates runtime panics scattered throughout the codebase.

**Fix:**

- Use `?` operator for error propagation
- Use `anyhow` or `thiserror` for structured errors
- Use `if let Some(x)` or `match` for `Option` types
- `.unwrap()` only for compile-time guarantees (hardcoded regex, constants)

```rust
// SLOP
let file = File::open("config.toml").unwrap();
let config: Config = toml::from_str(&contents).unwrap();

// CLEAN
let file = File::open("config.toml")?;
let config: Config = toml::from_str(&contents)?;
```

## 3. Treating everything as `String`

Losing type safety and adding unnecessary allocations.

**Fix:**

- Accept `&str` or `impl AsRef<str>` in function parameters
- Use `Cow<'_, str>` when sometimes owned, sometimes borrowed
- Create newtypes for domain concepts: `struct UserId(String)`

```rust
// SLOP
fn find_user(id: String, name: String) -> String { ... }

// CLEAN
fn find_user(id: &UserId, name: &str) -> Result<User> { ... }
```

## 4. Index-based loops instead of iterators

C-style `for i in 0..vec.len()` misses safety and optimization.

**Fix:**

- Use `.iter()`, `.map()`, `.filter()`, `.enumerate()`, `.collect()`
- Use slice patterns: `match vec.as_slice() { [first, ..] => ... }`

```rust
// SLOP
for i in 0..items.len() {
    process(i, &items[i]);
}

// CLEAN
for (i, item) in items.iter().enumerate() {
    process(i, item);
}
```

## 5. Fighting lifetimes with `Rc<RefCell<T>>`

When ownership gets complex, AI reaches for interior mutability or `unsafe`.

**Fix:**

- Reduce borrow lifetimes so they don't overlap
- Design structs to own their data
- Pass short-lived borrows as method parameters
- Restructure to avoid holding long-lived references

## 6. Weak assertions — the #1 AI test smell

`assert!(result.is_ok())` and `assert!(result.is_err())` swallow the actual
error/value on failure, printing only `false`.

**Fix:**

- Propagate with `.expect("context")` or `?` to see the real error
- Check actual values, not just existence
- For errors, verify the specific variant with `matches!` or check the message
- Every `assert_eq!`/`assert!` with non-obvious operands needs a failure message

```rust
// SLOP
assert!(result.is_ok());
assert!(result.is_err());
assert_eq!(count, 3);  // no context on failure
```

```rust
// CLEAN — propagate the real error
let value = result.expect("scan_worktree should succeed");
assert_eq!(value.label, "Ready");
```

```rust
// CLEAN — check specific error variant
assert!(matches!(result, Err(MyError::NotFound { .. })));
// or check the message
let err = result.unwrap_err();
assert!(err.to_string().contains("not found"), "expected NotFound, got: {err}");
```

```rust
// CLEAN — failure message for non-obvious operands
assert_eq!(count, 3, "expected 3 active workers after spawn");
```

## 7. `is_none()` / `is_some()` without value context

`assert!(x.is_none())` prints `assertion failed: false`. `assert_eq!` shows what was actually there.

**Fix:**

- Use `assert_eq!(x, None)` for better failure messages
- For `is_some()`, extract and check the inner value

```rust
// SLOP
assert!(x.is_none());
assert!(ping["result"]["host_type"].as_str().is_some());

// CLEAN
assert_eq!(x, None);
assert_eq!(ping["result"]["host_type"].as_str(), Some("daemon"));
```

## 8. Async timing slop

Raw `tokio::time::sleep` before assertions is fragile — passes on fast machines, flakes in CI.

**Fix:**

- Use a `wait_until_async` polling pattern with timeout
- Sleep-then-assert is only acceptable for testing actual timing behavior

```rust
// SLOP
tokio::time::sleep(Duration::from_millis(500)).await;
assert_eq!(state.status(), "ready");

// CLEAN — poll with timeout
wait_until_async(Duration::from_secs(2), || async {
    state.status() == "ready"
}).await.expect("status should reach ready");
```

## 9. `#[should_panic]` without `expected`

A bare `#[should_panic]` passes on *any* panic — including unrelated ones from
refactoring. Always pin the expected message.

**Fix:**

- Add `expected = "substring"` to match the intended panic message

```rust
// SLOP
#[test]
#[should_panic]
fn rejects_empty_input() {
    parse("");
}

// CLEAN
#[test]
#[should_panic(expected = "input must not be empty")]
fn rejects_empty_input() {
    parse("");
}
```

## 10. No-crash-is-success tests

Tests with zero assertions only prove the code doesn't panic — not that it works.

**Fix:**

- Add assertions on return values or side effects
- If intentionally testing "no panic", add an explicit comment documenting why

```rust
// SLOP
#[test]
fn stamp_activity_nonexistent_is_noop() {
    tracker.stamp_activity("ghost-id");
}

// CLEAN — document the intent
#[test]
fn stamp_activity_nonexistent_is_noop() {
    // No assertion needed: verifying no panic on missing ID
    tracker.stamp_activity("ghost-id");
}
```

## 11. Lint suppression as band-aid (`#[allow(...)]`)

AI sprinkles `#[allow(...)]` to silence warnings instead of fixing root causes.
The compiler is telling you something — listen, don't muzzle it.

### Crate-level nuclear options (instant fail)

These suppress warnings globally and are never legitimate in production code:

```rust
// SLOP — the nuclear option
#![allow(warnings)]
#![allow(clippy::all)]

// SLOP — the scaffold dump (3+ together = AI signature)
#![allow(dead_code)]
#![allow(unused_imports)]
#![allow(unused_variables)]
```

**Fix:** Delete the allows and fix each warning individually. If there are too
many warnings, the code has bigger problems than lint noise.

### The AI scaffold cluster

These five attributes appearing together are the highest-confidence AI signal:

| Attribute | AI excuse | Real fix |
|-----------|-----------|----------|
| `allow(dead_code)` | "I'll wire it up later" | Delete unconnected code |
| `allow(unused_imports)` | Copied from examples | Remove unused `use` statements |
| `allow(unused_variables)` | Bound "just in case" | Prefix with `_` or remove |
| `allow(unused_mut)` | Added `mut` preemptively | Remove unnecessary `mut` |
| `allow(unused_assignments)` | Assign then overwrite | Remove dead assignment |

**Fix:** Each has a specific fix — the allow hides which one is needed.
Remove the allow, read the warning, apply the real fix.

### Clippy suppression smells

**Red Flag (almost always slop — these suppress restrictions for a reason):**

```rust
// SLOP — hiding panic risks
#[allow(clippy::unwrap_used)]
#[allow(clippy::expect_used)]
#[allow(clippy::indexing_slicing)]
#[allow(clippy::panic)]

// CLEAN — handle the error
fn get_item(items: &[Item], idx: usize) -> Option<&Item> {
    items.get(idx)
}
```

```rust
// SLOP — incomplete code in CI
#[allow(clippy::todo)]
#[allow(clippy::unimplemented)]
#[allow(clippy::dbg_macro)]       // debug macros left in source

// CLEAN — ship nothing with these lints suppressed
```

```rust
// SLOP — logging-aware code ignored
#[allow(clippy::print_stdout)]
#[allow(clippy::print_stderr)]

// CLEAN — use a logging framework (tracing, log, slog)
tracing::info!("event happened");
```

```rust
// SLOP — weak error handling
#[allow(clippy::result_unit_err)]  // Result<T, ()> is useless for error context

// CLEAN — use a real error type
fn parse_config(s: &str) -> Result<Config, ConfigError> { ... }
```

**Yellow Flag (often slop, but context-dependent — check before removing):**

```rust
// SLOP (often) — hiding complexity debt
#[allow(clippy::too_many_arguments)]
#[allow(clippy::too_many_lines)]

// CLEAN — decompose the function
```

```rust
// SLOP (often) — legitimate in some contexts (async move blocks, trait impls)
#[allow(clippy::needless_pass_by_value)]
#[allow(clippy::cognitive_complexity)]

// Check: does the suppression hide a real refactoring opportunity?
```

**Blue Flag (style preference, not necessarily slop):**

```rust
// Acceptable — pedantic lints are opt-in for a reason
#[allow(clippy::cast_possible_truncation)]
#[allow(clippy::cast_sign_loss)]
#[allow(clippy::module_name_repetitions)]
#[allow(clippy::wildcard_imports)]

// These are in "pedantic" (not "restriction"), so suppressing them
// is more defensible. Still check the reason.
```

### Naming convention suppressions

Three together = author came from Python/Java, not Rust:

```rust
// SLOP
#![allow(non_snake_case)]
#![allow(non_camel_case_types)]
#![allow(non_upper_case_globals)]

// CLEAN — use Rust conventions
// snake_case for functions, CamelCase for types, SCREAMING for constants
```

**Exception:** FFI modules wrapping C libraries may legitimately need
`non_snake_case` or `non_camel_case_types` to match the C API.

### The "debug and print" tells

Three patterns that almost certainly indicate hastily generated code:

```rust
// SLOP — debug macro left in source
fn process(data: &[u8]) {
    #[allow(clippy::dbg_macro)]
    dbg!(data);  // this went to production
    // ...
}

// CLEAN — remove the debug macro entirely
fn process(data: &[u8]) {
    tracing::debug!(?data);  // use structured logging
    // ...
}
```

```rust
// SLOP — println instead of logging
#[allow(clippy::print_stdout)]
println!("Processing file: {}", path);

// CLEAN — use a logging framework
tracing::info!(file = %path, "Processing file");
```

```rust
// SLOP — placeholder error type
#[allow(clippy::result_unit_err)]
fn load_config(path: &str) -> Result<Config, ()> {
    // caller has no idea what went wrong
}

// CLEAN — define a real error type
#[derive(Debug)]
pub enum ConfigError {
    NotFound(String),
    InvalidFormat { line: usize, reason: String },
}

fn load_config(path: &str) -> Result<Config, ConfigError> {
    // caller can now handle specific errors
}
```

### Redundant allows

An allow that duplicates what the language already provides:

```rust
// SLOP — `_name` already suppresses unused_variables
#[allow(unused_variables)]
fn process(_name: &str, _config: &Config) { ... }

// SLOP — pub items can't be dead code (compiler perspective)
#[allow(dead_code)]
pub fn my_function() { ... }

// CLEAN — just use the underscore prefix
fn process(_name: &str, _config: &Config) { ... }
```

### Scope matters

The further an allow reaches, the worse it smells:

| Scope | Severity | Example |
|-------|----------|---------|
| Crate-level `#![allow(...)]` | High | Suppresses across entire crate |
| Module-level `#[allow(...)]` on `mod` | Medium | Blanket suppression for module |
| Function-level | Low | Targeted, possibly legitimate |
| Statement-level | Lowest | Precise suppression with clear reason |

**Rule:** If you must allow, scope it to the narrowest possible target and
add a comment explaining why.

```rust
// Acceptable — narrow scope, clear reason
#[allow(clippy::too_many_arguments)] // mirrors the C FFI signature exactly
fn ffi_create_window(x: i32, y: i32, w: i32, h: i32, flags: u32) -> *mut Window { ... }
```

### Tier system for evaluation

Clippy groups lints into categories. Use these groupings as a heuristic when judging whether suppression is legitimate:

| Category | Philosophy | Example | Suppression OK? |
|----------|-----------|---------|-----------------|
| **restriction** | "Don't do this" | `unwrap_used`, `panic`, `todo`, `print_stdout` | 🔴 Almost never |
| **correctness** | "This is likely wrong" | Most logic bugs | 🔴 Almost never |
| **complexity** | "This is confusing" | `too_many_arguments`, `type_complexity` | 🟡 With justification |
| **perf** | "This is slow" | `clone_on_copy`, `inefficient_to_string` | 🟡 Document why |
| **style** | "Use X instead" | `let_and_return`, `wildcard_imports` | 🟡 Preference |
| **pedantic** | "Extra strict" | `cast_possible_truncation`, `module_name_repetitions` | 🟢 Usually OK |

**Rule:** Never suppress `restriction` lints casually. `Pedantic` lints are opt-in,
so suppressing them is more defensible. `Complexity` lints need justification.

### Legitimate uses (don't flag these)

**Test code:**

- `#[allow(dead_code)]` on test utility functions
- `#[allow(unused)]` in `mod tests` blocks
- `#[allow(clippy::unwrap_used)]` in test assertions (idiomatic)

**Framework integration:**

- `#[allow(unused)]` on trait impls required by framework (async frameworks often have dead-looking methods)
- `#[allow(clippy::must_use_candidate)]` when the framework signature doesn't support `#[must_use]`

**Intentional design:**

- `#[allow(clippy::pedantic)]` at crate level (pedantic lints are opt-in)
- `#[allow(clippy::cognitive_complexity)]` on state machines or DSLs (legitimately complex, not a bug)

**FFI/interop:**

- `#[allow(non_snake_case)]` / `non_camel_case_types` matching C signatures
- `#[allow(unsafe_code)]` when wrapping C libraries

**Generated code:**

- `build.rs` output
- Protobuf/gRPC generated files
- Macro-generated code inside the macro itself
- `#[cfg_attr(feature = "generated", allow(...))]` for optional generated modules

**Red flag check:** If the allow targets a **restriction** lint (unwrap, panic, todo, print)
in these contexts, it's still slop. Only pedantic/style/perf lints are genuinely legitimate here.

## 12. Hallucinated APIs and deprecated syntax

AI generates functions that don't exist or uses outdated API patterns
(e.g., `clap` `App::new` instead of derive macros).

**Fix:**

- Run `cargo check` immediately after generating code
- Pin specific crate versions
- Use Clippy: `cargo clippy -- -W clippy::all`
- When in doubt, check docs against the current crate version

## 13. Deref polymorphism (fake inheritance)

Implementing `Deref` on a wrapper so it "inherits" the inner type's methods —
simulating the OO inheritance Rust deliberately doesn't have.

```rust
// SLOP
struct AppConfig { base: Config }
impl Deref for AppConfig {
    type Target = Config;
    fn deref(&self) -> &Config { &self.base }
}

// CLEAN — delegate explicitly, or implement the shared trait
impl AppConfig {
    fn timeout(&self) -> Duration { self.base.timeout() }
}
```

`Deref` is for smart pointers. No clippy lint catches this — review by hand.
(rust-unofficial/patterns, anti-patterns chapter.)

## 14. Boxing reflex

`Box`/`Arc` where plain ownership or a borrow works — indirection reached for
to make the borrow checker go away.

```rust
// SLOP
fn process(data: &Box<MyStruct>) { ... }        // borrowed_box
struct Registry { items: Vec<Box<String>> }      // vec_box
let cfg: Box<Config> = Box::new(Default::default()); // box_default

// CLEAN
fn process(data: &MyStruct) { ... }
struct Registry { items: Vec<String> }
let cfg = Config::default();
```

clippy: `borrowed_box`, `vec_box`, `box_collection`, `box_default`.
Inverse case: a very large enum variant SHOULD be boxed
(`large_enum_variant`) — boxing isn't wrong, unmotivated boxing is.

## 15. `async fn` with no `.await`

Functions marked async by habit. An async fn that never awaits forces every
caller into the async machinery for nothing.

```rust
// SLOP
async fn config_path() -> PathBuf {
    dirs::config_dir().expect("config dir").join("app")
}

// CLEAN
fn config_path() -> PathBuf { ... }
```

clippy: `unused_async` (has false-negative gaps — also check by hand).

## 16. `#![deny(warnings)]`

Turns every future compiler warning into a build break — the crate stops
compiling on a new toolchain that added a lint.

```rust
// SLOP
#![deny(warnings)]

// CLEAN — enforce in CI instead:
// RUSTFLAGS="-D warnings" cargo build
```

(rust-unofficial/patterns, anti-patterns chapter.)

## 17. `anyhow::Error` in a library's public API

`anyhow` is for applications. A library returning `anyhow::Error` gives
callers nothing to match on.

```rust
// SLOP (in a lib crate)
pub fn parse(s: &str) -> anyhow::Result<Config> { ... }

// CLEAN — concrete error type; thiserror for the boilerplate
#[derive(Debug, thiserror::Error)]
pub enum ParseError {
    #[error("invalid syntax at line {0}")]
    Syntax(usize),
}
pub fn parse(s: &str) -> Result<Config, ParseError> { ... }
```

Convention, not a lint — check whether the crate is a lib or a bin before
flagging. `anyhow` in binaries and tests is fine.

## 18. `unsafe` to make it compile

Agent-speed pressure produces `unsafe` as a borrow-checker escape hatch.
Bun's audit of its AI-assisted Zig→Rust port found 13,365 unsafe call sites
needing review. For every `unsafe` block ask: is there a safe alternative, is
the invariant documented, is it tested?

```rust
// SLOP — no SAFETY comment, no bounds reasoning
let val = unsafe { *ptr.add(i) };

// CLEAN — safe alternative existed all along
let val = slice.get(i).copied().ok_or(Error::OutOfBounds)?;

// If unsafe is genuinely required:
// SAFETY: i < self.len is checked by the caller contract above.
```

## Sources

- rust-unofficial/patterns (Rust Design Patterns book) — the official anti-pattern chapter
- clippy lint list (rust-lang.github.io/rust-clippy/master) — ground truth for every lint named above
- Bun unsafe audit (bun.com/bun-unsafe-audit) — quantified case study of AI-agent Rust output
