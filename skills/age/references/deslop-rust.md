# Rust De-slop Catalog

This catalog provides Rust-specific evidence for the `age` `deslop` dimension.
Each pattern identifies a Rust-specific AI tell for review.
Most patterns map to a clippy lint.
The lint provides a citable rule name for each finding.
Use this catalog with the `deslop` rubric in `dimensions.md`.
This catalog provides the "Look for" details, not a separate severity scale.

## 1. Excessive `.clone()` to silence the borrow checker

LLMs reach for `.clone()` as a universal fix for ownership errors.

**Fix:**

- Use borrowing (`&` and `&mut`) instead
- Take `&str` instead of `String` in function parameters
- Use `.as_ref()` on `Option`/`Result` instead of cloning to unwrap
- Ban `.clone()` unless you can explain why you need owned data

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

Excessive `.unwrap()` calls create runtime panics throughout the codebase.

**Fix:**

- Use the `?` operator to propagate errors
- Use `anyhow` or `thiserror` for structured errors
- Use `if let Some(x)` or `match` for `Option` types
- Use `?` for every error you can propagate
- Use `.unwrap()` only when the type system proves the value exists, such as a `const` or a checked index
- A hardcoded regex is not a compile-time guarantee. `Regex::new` parses at run time. Use `LazyLock` plus `expect("static regex")`, or a compile-time macro crate

```rust
// SLOP
let file = File::open("config.toml").unwrap();
let config: Config = toml::from_str(&contents).unwrap();

// CLEAN
let file = File::open("config.toml")?;
let config: Config = toml::from_str(&contents)?;
```

## 3. Treating everything as `String`

Using `String` for every value loses type safety and adds unnecessary allocations.

**Fix:**

- Accept `&str` or `impl AsRef<str>` as function parameters
- Use `Cow<'_, str>` when a value may be owned or borrowed
- Create newtypes for domain concepts, such as `struct UserId(String)`

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

## 6. Weak assertions

The assertions `assert!(result.is_ok())` and `assert!(result.is_err())` hide the actual error or value when they fail and print only `false`.

**Fix:**

- Propagate the error with `?` and let the test signature return `Result`
- `.expect("context")` panics. Use it only when the test cannot return `Result`
- Check actual values, not just existence
- For errors, verify the specific variant with `matches!` or check the message
- Add a failure message to every `assert_eq!`/`assert!` with non-obvious operands

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

The assertion `assert!(x.is_none())` prints `assertion failed: false`, while `assert_eq!` shows the actual value.

**Fix:**

- Use `assert_eq!(x, None)` when the inner type implements `Debug` and `PartialEq`
- Use `assert!(matches!(x, None), "got {x:?}")` when it implements only `Debug`
- Keep `assert!(x.is_none())` when the inner type implements neither trait
- For `is_some()`, extract the inner value and check it

```rust
// SLOP
assert!(x.is_none());
assert!(ping["result"]["host_type"].as_str().is_some());

// CLEAN
assert_eq!(x, None);
assert_eq!(ping["result"]["host_type"].as_str(), Some("daemon"));
```

## 8. Async timing slop

A raw `tokio::time::sleep` call before assertions is fragile: it passes on fast machines and flakes in CI.

**Fix:**

- Use a `wait_until_async` polling pattern with a timeout
- Use sleep-then-assert only to test actual timing behavior

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

A bare `#[should_panic]` accepts *any* panic, including unrelated panics caused by refactoring. Always pin the expected message.

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

Tests with zero assertions prove only that the code does not panic, not that it works.

**Fix:**

- Add assertions on return values or side effects
- If you intentionally test "no panic", add a comment that explains why

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

## 11. Lint suppression instead of a fix (`#[allow(...)]`)

AI adds `#[allow(...)]` attributes to silence warnings instead of fixing their causes.
Treat each compiler warning as a problem to fix, not a message to suppress.

### Crate-level suppression (always a finding)

These attributes suppress warnings globally and do not belong in production code:

```rust
// SLOP — suppresses every warning in the crate
#![allow(warnings)]
#![allow(clippy::all)]

// SLOP — three or more together are an AI signature
#![allow(dead_code)]
#![allow(unused_imports)]
#![allow(unused_variables)]
```

**Fix:** Delete the allows.
Fix each warning individually.
Numerous warnings indicate broader code problems, not mere lint noise.

### The AI scaffold cluster

These five attributes together provide the strongest AI signal:

| Attribute | AI excuse | Real fix |
|-----------|-----------|----------|
| `allow(dead_code)` | "I'll wire it up later" | Delete unconnected code |
| `allow(unused_imports)` | Copied from examples | Remove unused `use` statements |
| `allow(unused_variables)` | Bound "just in case" | Prefix with `_` or remove |
| `allow(unused_mut)` | Added `mut` preemptively | Remove unnecessary `mut` |
| `allow(unused_assignments)` | Assign then overwrite | Remove dead assignment |

**Fix:** Each attribute has a specific fix, but the allow hides which fix you need.
Remove the allow.
Read the warning.
Apply the appropriate fix.

### Clippy suppression smells

**Red Flag:** These attributes almost always indicate slop because they suppress restrictions.

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

**Yellow Flag:** These attributes often indicate slop; check the context before removing them.

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

**Blue Flag:** These attributes express style preferences and do not necessarily indicate slop.

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

Three together suggest that the author came from Python/Java, not Rust:

```rust
// SLOP
#![allow(non_snake_case)]
#![allow(non_camel_case_types)]
#![allow(non_upper_case_globals)]

// CLEAN — use Rust conventions
// snake_case for functions, CamelCase for types, SCREAMING for constants
```

**Exception:** FFI modules that wrap C libraries may need `non_snake_case` or `non_camel_case_types` to match the C API.

### The "debug and print" tells

These three patterns almost certainly indicate hastily generated code:

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

This allow duplicates behavior that the language already provides:

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

A wider allow scope increases the risk of hidden problems:

| Scope | Severity | Example |
|-------|----------|---------|
| Crate-level `#![allow(...)]` | High | Suppresses across entire crate |
| Module-level `#[allow(...)]` on `mod` | Medium | Blanket suppression for module |
| Function-level | Low | Targeted, possibly legitimate |
| Statement-level | Lowest | Precise suppression with clear reason |

**Rule:** Scope each allow to the narrowest possible target.
Add a comment that explains why.

```rust
// Acceptable — narrow scope, clear reason
#[allow(clippy::too_many_arguments)] // mirrors the C FFI signature exactly
fn ffi_create_window(x: i32, y: i32, w: i32, h: i32, flags: u32) -> *mut Window { ... }
```

### Tier system for evaluation

Clippy groups lints into categories. Use these categories as a heuristic when you judge whether a suppression is legitimate:

| Category | Philosophy | Example | Suppression OK? |
|----------|-----------|---------|-----------------|
| **restriction** | "Don't do this" | `unwrap_used`, `panic`, `todo`, `print_stdout` | 🔴 Almost never |
| **correctness** | "This is likely wrong" | Most logic bugs | 🔴 Almost never |
| **complexity** | "This is confusing" | `too_many_arguments`, `type_complexity` | 🟡 With justification |
| **perf** | "This is slow" | `clone_on_copy`, `inefficient_to_string` | 🟡 Document why |
| **style** | "Use X instead" | `let_and_return`, `wildcard_imports` | 🟡 Preference |
| **pedantic** | "Extra strict" | `cast_possible_truncation`, `module_name_repetitions` | 🟢 Usually OK |

**Rule:** Do not suppress `restriction` lints casually.
Treat `Pedantic` lints as more defensible because they are opt-in.
Justify each `Complexity` lint suppression.

### Legitimate uses (don't flag these)

**Test code:**

- `#[allow(dead_code)]` on test utility functions
- `#[allow(unused)]` in `mod tests` blocks
- `#[allow(clippy::unwrap_used)]` on a test function, scoped to that item

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

**One suppression rule.** Judge each `#[allow(...)]` by its scope and its context.

| Scope | Verdict |
| --- | --- |
| Crate level (`#![allow(...)]`) | Slop, except for an opt-in group such as `clippy::pedantic` |
| Item level in production code | Slop for a restriction lint such as `unwrap_used`, `panic`, `todo`, or `print` |
| Item level in a test, a generated file, or an FFI binding | Acceptable, including a restriction lint |

Require a comment that names the reason on every allow that this table accepts.

## 12. Hallucinated APIs and deprecated syntax

AI generates nonexistent functions or uses outdated API patterns, such as `clap` `App::new` instead of derive macros.

**Fix:**

- Run `cargo check` immediately after generating code
- Pin specific crate versions
- Use Clippy: `cargo clippy -- -W clippy::all`
- When in doubt, check docs against the current crate version

## 13. Deref polymorphism (fake inheritance)

Implementing `Deref` on a wrapper so it "inherits" the inner type's methods simulates OO inheritance, which Rust deliberately lacks.

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

Use `Deref` for smart pointers.
No clippy lint catches this pattern, so review it by hand (`rust-unofficial/patterns`, anti-patterns chapter).

## 14. Boxing reflex

Using `Box` or `Arc` when plain ownership or a borrow works adds unnecessary indirection to avoid borrow-checker errors.

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

`clippy` reports `borrowed_box`, `vec_box`, `box_collection`, and `box_default`.
In the inverse case, you SHOULD box a very large enum variant (`large_enum_variant`).
Boxing is not inherently wrong, but unmotivated boxing is wrong.

## 15. `async fn` with no `.await`

Functions marked `async` by habit add unnecessary async behavior.
An `async fn` that never awaits forces every caller into async machinery for no reason.

```rust
// SLOP
async fn config_path() -> PathBuf {
    dirs::config_dir().expect("config dir").join("app")
}

// CLEAN
fn config_path() -> PathBuf { ... }
```

`unused_async` has false-negative gaps, so check async functions by hand.

## 16. `#![deny(warnings)]`

`#![deny(warnings)]` turns every future compiler warning into a build break.
The crate then stops compiling when a new toolchain adds a lint.

```rust
// SLOP
#![deny(warnings)]

// CLEAN — leave the crate free of a global deny
```

Enforce the warning budget in CI, on a pinned toolchain, with an explicit lint list.
Do not replace the attribute with `RUSTFLAGS="-D warnings"` on a floating toolchain.
That replacement breaks the same build for the same reason.
The `rust-unofficial/patterns` anti-patterns chapter documents this pattern.

## 17. `anyhow::Error` in a library's public API

Use `anyhow` in applications, not in public library APIs.
Libraries that return `anyhow::Error` give callers no concrete error type to match.

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

Pressure to move quickly causes agents to use `unsafe` to escape the borrow checker.
Bun's audit of its AI-assisted Zig→Rust port found 13,365 `unsafe` call sites that required review.
For every `unsafe` block, ask whether a safe alternative exists.
Confirm that the code documents the invariant.
Confirm that tests cover the block.

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
