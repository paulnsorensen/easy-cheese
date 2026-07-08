# `tilth_write` JSON cookbook

Each block below is one section object — wrap one or more in
`tilth_write(edits: [ … ])` (max 20 sections per call). A section is
`{path, tag, ops}`: `path` names the file, `tag` is the 4-hex tag copied
verbatim from the `[path#TAG]` header of a `tilth_read`, and `ops` is an
array of op objects, each tagged by `op`. Line numbers (`start`, `end`,
`line`, numeric `at`) are the 1-based `N:` prefixes from that same read.
Omit `tag` only to seed a brand-new file.

## Single-line replacement

```json
{
  "path": "src/auth.ts",
  "tag": "a3f9",
  "ops": [
    { "op": "replace", "start": 42, "end": 42, "content": "  let x = recompute();" }
  ]
}
```

Replaces line 42 only. The tag binds the line numbers to the content you
read; if the file drifted, tilth 3-way-merges or rejects the section.

## Multi-line range replacement

```json
{
  "path": "src/auth.ts",
  "tag": "b2c4",
  "ops": [
    {
      "op": "replace",
      "start": 44,
      "end": 89,
      "content": "export function handleAuth(req, res, next) {\n  const token = extractToken(req);\n  if (!token) return res.status(401).end();\n  next();\n}"
    }
  ]
}
```

Replaces lines 44–89 inclusive.

## Delete a block

```json
{
  "path": "src/auth.ts",
  "tag": "b2c4",
  "ops": [
    { "op": "delete", "start": 44, "end": 89 }
  ]
}
```

`delete` takes no `content`. To remove a whole named symbol instead, use
`{ "op": "delete_block", "at": "#handleAuth" }`.

## Insert before or after a line

```json
{
  "path": "src/auth.ts",
  "tag": "a1b7",
  "ops": [
    { "op": "insert_after", "line": 13, "content": "import { newHelper } from './helpers';" }
  ]
}
```

`insert_before` / `insert_after` are native ops — do not rewrite the anchor
line to fake an insert. `prepend` / `append` (`{content}` only) cover the
file head and tail.

## Symbol-anchored block ops

```json
{
  "path": "src/auth.ts",
  "tag": "b2c4",
  "ops": [
    { "op": "replace_block", "at": "#handleAuth", "content": "export function handleAuth(req, res, next) {\n  // …\n}" }
  ]
}
```

`replace_block`, `insert_after_block` (`{at, content}`), and `delete_block`
(`{at}`) take `at` as a line number or a `"#symbol"` string — use them when
the edit boundary is a whole function or class.

## Multiple edits in one file

```json
{
  "path": "src/auth.ts",
  "tag": "b2c4",
  "ops": [
    { "op": "replace", "start": 12, "end": 12, "content": "import { newHelper } from './helpers';" },
    { "op": "replace", "start": 44, "end": 89, "content": "// replaced function\n..." }
  ]
}
```

All ops in a section reference the line numbers from the same read — do not
adjust later ops for earlier insertions or deletions. If the section is
rejected, re-read the file and recover before moving on.

## Create, move, delete files

```json
{ "path": "src/new-module.ts", "ops": [ { "op": "append", "content": "export const x = 1;\n" } ] }
```

Omitting `tag` seeds a brand-new file; `move_file` / `delete_file` on an *existing* file keep the file's `tag` (omit it only to seed a new file). `{ "op": "move_file", "dest": "src/renamed.ts" }`
moves the section's file; `{ "op": "delete_file" }` removes it.

## Show diff in response

```text
tilth_write(edits: [{ "path": "src/auth.ts", "tag": "b2c4", "ops": [{ "op": "replace", "start": 44, "end": 89, "content": "..." }] }], diff: true)
```

`diff: true` is a call-level option: the response includes a compact
before/after diff per section.

## Edits across multiple files

Pass one `{path, tag, ops}` section per file in a single `edits` array (max
20). Sections are independent and best-effort — a rejected section does not
roll back the others — so check the per-`## <path>` results and re-read any
rejected file before retrying.

## Caller-update notices

When you change a function signature, `tilth_write` may surface callers in
its response:

```text
Edit applied to src/auth.ts

── callers that may need updates ──
  src/routes/api.ts:34   router.use('/api/*', handleAuth)
  src/routes/admin.ts:12 app.use(handleAuth)
  src/middleware.ts:8    const wrapped = handleAuth(...)
```

Visit each location, decide whether the new signature is compatible, and
edit if needed. The notice is informational — it does not block the edit.
