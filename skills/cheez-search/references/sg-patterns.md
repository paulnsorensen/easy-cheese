# ast-grep (`sg`) patterns

`tilth_search` covers names and text. For *shapes* with metavariables — "any
call to `JSON.parse(JSON.stringify(…))`", "any `for` loop with `time.Sleep` in
its body" — drop to `sg` (ast-grep) via Bash. This is the **only** sanctioned
shell escape from cheez-search. The same escape covers structural codemods
via `sg --rewrite` (see "Structural codemods" below); `tilth_edit` remains
the default for one-off block edits.

## When `sg` is the right pick

- The pattern needs metavars (`$X`, `$$$BODY`) or specific node kinds.
- You're surveying a structural shape across a directory (anti-pattern sweeps,
  refactor previews, lint-style scans).
- Tree-sitter symbol search would over-match because the *name* isn't fixed.
- You want to apply the same structural change across many files in one pass
  (codemod) — see the dedicated section below.

If the question is "where is `handleAuth` defined" or "what calls
`validateToken`", stay in `tilth_search`. `sg` is for shape, not name.

## Pattern syntax

```bash
# AST template: $X is a metavar that matches any single node.
sg --lang typescript -p 'JSON.parse(JSON.stringify($X))' --json src/

# $$$BODY matches a sequence of statements.
sg --lang rust -p 'impl std::fmt::Display for $TYPE { $$$BODY }' --json src/

# Bound the scan; never splice unvalidated user input as the path.
SCOPE=$(realpath "$SCOPE_INPUT")
sg --lang python -p 're.match($PATTERN, $INPUT)' --json "$SCOPE"
```

## Hard rules for `sg` invocations

- **Always pass `--lang`/`-l`.** Pattern parsing is language-specific; the
  same pattern string can parse differently per language. Don't rely on
  extension inference for anything that goes into a script.
- **Always pass `--json`** when piping into a tool, an LLM, or a follow-up
  shell step. Never parse the pretty TTY output.
- **Never pass `--interactive`.** It requires a TTY and human input; it will
  hang or fail in agent contexts.
- **Never pass `-U` (rewrite-update) without a dry run first.** See
  "Structural codemods" — search-only invocation, then re-run with `-U`
  after the diff is staged or confirmed.
- **Validate any path** that flows from user input before splicing it into
  the command line. Reject `;`, `&`, `|`, backtick, `$(`, `>`, `<`, newline.
  Resolve to an absolute path with `realpath` and confirm it sits under the
  repo root.
- **Parse `--json` defensively.** Key by field name (`text`, `file`,
  `range`, `metaVariables`); tolerate missing keys; do not hard-code
  positional `jq` paths. The shape has shifted between minor releases.
- **Filter test/build/vendor directories** with `--globs` or by
  post-filtering JSON.

## Pitfalls

- **CST, not AST.** ast-grep matches the Concrete Syntax Tree, so trivia
  and punctuation can affect what nodes exist. The pattern itself must be
  valid syntax in the target language — "didn't match" is often "didn't
  parse on the pattern side".
- **Metavar binding.** Repeating the same metavar name within a single
  pattern (`$VAR ... $VAR`) requires both occurrences to match the **same**
  node text. Use distinct names (`$A`, `$B`) when you want independent
  matches; reuse the name only when you want the binding.
- **Lenient by default.** ast-grep matches loosely on CST nodes. Pass
  `--strict` (or `strictness:` in YAML rules) when you need exact node-kind
  equality and the loose match is producing surprises.
- **No semantics.** `$X.unwrap()` is text-shape only — the receiver's type
  is unknown to ast-grep. Anything that needs type info, control flow, or
  data flow has to escalate (see "When to escalate further").

## Performance: narrow first, parse second

ast-grep parses every file in scope, so cost scales with **file count**, not
match count. A wide `**/*` over a monorepo can be ~10× slower than a
constrained scope. Two-stage workflow:

1. **List candidates** with `tilth_search` (definitions, imports, content
   hits) or `tilth_files` (glob/path predicates) to get the file set.
2. **Run `sg`** with `--globs` or explicit paths bounded to that set.

This pattern beats one giant wildcard scan and keeps the JSON output small
enough to inspect.

## Common pattern shapes

| Goal | Pattern |
|------|---------|
| Calls to a method on any receiver | `$RECV.someMethod($$$ARGS)` |
| Anti-pattern: deep clone via JSON | `JSON.parse(JSON.stringify($X))` |
| Empty catch blocks | `try { $$$BODY } catch ($E) { }` |
| Sleep inside a loop | `for ($$$INIT) { $$$BEFORE time.Sleep($D) $$$AFTER }` |
| Trait impls for a specific trait | `impl Display for $TYPE { $$$BODY }` |
| React hook destructure | `const [$STATE, $SETTER] = useState($$$INIT)` |
| Async function declaration | `async function $NAME($$$PARAMS) { $$$BODY }` |
| Class with any body | `class $NAME { $$$BODY }` |

## Structural codemods (`sg --rewrite`)

`sg --rewrite '<template>'` plus `-U` (update files in place) is the
sanctioned codemod path. It complements `tilth_edit` rather than replacing
it: tilth_edit excels at "replace this specific block in this specific file"
with hash-anchor concurrency safety; `sg --rewrite` excels at "rewrite every
instance of this shape across the repo" with structural-match safety.

Use it when:

- The change repeats across N locations and the surrounding text varies.
- The pattern can be expressed structurally (metavars carry the variable
  parts; the rewrite template fills them back in).
- You don't know all the locations a priori and want discovery + change in
  one pass.

**Dry-run-first protocol** (non-negotiable):

1. Run the pattern **without** `-U`. Inspect `--json` matches; count them.
   ```bash
   sg --lang typescript \
      -p 'JSON.parse(JSON.stringify($X))' \
      -r 'structuredClone($X)' \
      --json src/
   ```
2. Confirm the working tree is clean or stashed. Mass rewrites that bury
   uncommitted work are unrecoverable without a stash.
3. Re-run with `-U` to apply.
   ```bash
   sg --lang typescript \
      -p 'JSON.parse(JSON.stringify($X))' \
      -r 'structuredClone($X)' \
      -U src/
   ```
4. **Diff the result** (`git diff`). Commit or revert as a unit; do not
   layer additional changes on top until the codemod is reviewed.
5. If matches > expected, **bail and revert** — your pattern was too loose.
   Tighten with `--strict`, `--globs`, or distinct metavar names, then
   repeat from step 1.

`sg --rewrite` does not have hash-anchor safety. Structural matching catches
"didn't accidentally rewrite a string literal that looks like code"; it does
not catch "file changed under me mid-run". Treat it as a single transactional
change between two clean git states.

## When to escalate further

`sg` does not implement type information, control-flow analysis, data-flow
analysis, taint analysis, or constant propagation. If the rule needs any of
those, escalate to a real linter or a security tool:

- **ESLint** (`@typescript-eslint`) — type-aware JS/TS rules, plugin
  ecosystem, editor integration.
- **Clippy** — Rust lints with full type inference and borrow-checker
  awareness. `sg` can do shape-level Rust patterns but not lifetime
  semantics.
- **Ruff** — Python lint/format with thousands of vetted rules covering
  what isort/flake8/pyupgrade/black do.
- **gosec** — Go security rule pack.
- **Semgrep** — when you need taint analysis, security rule packs, or
  composition primitives like `pattern-not-inside` and `pattern-either`
  that ast-grep does not provide.

If your `sg` patterns are growing chained metavars and nested negations,
or you're hand-rolling logic that overlaps a maintained rule set, stop and
adopt the linter. `sg` is for one-off structural sweeps and
repo-specific codemods, not for maintained rule infrastructure.
