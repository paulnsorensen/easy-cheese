# ast-grep (`sg`) patterns

`tilth_search` covers names and text. For *shapes* with metavariables — "any
call to `JSON.parse(JSON.stringify(…))`", "any `for` loop with `time.Sleep` in
its body" — drop to `sg` (ast-grep) via Bash. This is the **only** sanctioned
shell escape from cheez-search.

## When `sg` is the right pick

- The pattern needs metavars (`$X`, `$$$BODY`) or specific node kinds.
- You're surveying a structural shape across a directory (anti-pattern sweeps,
  refactor previews, lint-style scans).
- Tree-sitter symbol search would over-match because the *name* isn't fixed.

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

- Validate any path that flows from user input before splicing it into the
  command line. Reject `;`, `&`, `|`, backtick, `$(`, `>`, `<`, newline.
  Resolve to an absolute path with `realpath` and confirm it sits under the
  repo root.
- Always pass `--json` and parse defensively — the JSON shape varies between
  ast-grep versions.
- Filter test/build/vendor directories with `--globs` or by post-filtering
  JSON.

## Common pattern shapes

| Goal | Pattern |
|------|---------|
| Calls to a method on any receiver | `$RECV.someMethod($$$ARGS)` |
| Anti-pattern: deep clone via JSON | `JSON.parse(JSON.stringify($X))` |
| Empty catch blocks | `try { $$$BODY } catch ($E) { }` |
| Sleep inside a loop | `for ($$$INIT) { $$$BEFORE time.Sleep($D) $$$AFTER }` |
| Trait impls for a specific trait | `impl Display for $TYPE { $$$BODY }` |

## When to escalate further

If `sg` patterns get hairy (chained metavars, nested negations) and you're
hand-rolling logic that overlaps a real linter — clippy, eslint, ruff, gosec
— stop and use the linter. `sg` is for one-off structural sweeps, not for
maintained rule sets.
