# `tilth_deps` — Blast-Radius Check

Shows what imports a file and what that file imports. Use to understand the
fallout of a rename, signature change, or removal **before** you make it.

## Call shape

```
tilth_deps(path: "src/auth.ts")
```

## Output

```text
# Dependencies for src/auth.ts

── imports ──
  express        external
  jsonwebtoken   external
  @/config       src/config/index.ts

── imported by ──
  src/routes/api.ts:5
  src/routes/admin.ts:8
  src/middleware/auth.ts:3
```

The `── imports ──` block is what `src/auth.ts` pulls in. The `── imported
by ──` block is the blast radius — every file that will care if you change
this one.

## When to use

- **Before renaming a file or module** — you'll need to update every
  importer in the bottom block.
- **Before removing or renaming an export** — same.
- **Before changing a function or class signature** — visit each importer to
  decide whether the new shape is compatible.
- **When estimating refactor scope** — count the importers and weigh whether
  the change is local or cross-cutting.

## When NOT to use

- For "where is X defined" — that's `tilth_search`, not `tilth_deps`.
- For "what does this function do" — that's `tilth_read`.
- For unrelated curiosity — every call costs tokens; only run when you're
  about to make a structural change.

## Limits

- `tilth_deps` is path-scoped, not symbol-scoped. It tells you which files
  import the target file, not which functions inside those files use a
  specific export. For that, follow up with
  `tilth_search(query: "<symbol>", kind: "callers")`.
- External dependencies are listed without versions. If you need version
  context, check the lockfile or `package.json` / `Cargo.toml` separately.
- Generated, vendored, or `.gitignore`d files may not appear — tilth indexes
  what tree-sitter can parse and what's in the repo.
