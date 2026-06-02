# `tilth_edit` JSON cookbook

Every edit follows the same shape: `{ path, edits: [...] }`. Each edit needs
a `start` anchor; `end` is required only for range replacements. `content` is
the new text (use `""` to delete).

## Single-line replacement

```json
{
  "path": "src/auth.ts",
  "edits": [
    { "start": "42:a3f", "content": "  let x = recompute();" }
  ]
}
```

Replaces line 42 only. The hash `a3f` must match what `tilth_read` returned
in edit mode.

## Multi-line range replacement

```json
{
  "path": "src/auth.ts",
  "edits": [
    {
      "start": "44:b2c",
      "end": "89:e1d",
      "content": "export function handleAuth(req, res, next) {\n  const token = extractToken(req);\n  if (!token) return res.status(401).end();\n  next();\n}"
    }
  ]
}
```

Replaces lines 44–89 inclusive. Both anchors must match.

## Delete a block

```json
{
  "path": "src/auth.ts",
  "edits": [
    { "start": "44:b2c", "end": "89:e1d", "content": "" }
  ]
}
```

Empty `content` deletes the range.

## Multiple edits in one call

```json
{
  "path": "src/auth.ts",
  "edits": [
    { "start": "12:a1b", "content": "import { newHelper } from './helpers';" },
    { "start": "44:b2c", "end": "89:e1d", "content": "// replaced function\n..." }
  ]
}
```

All edits in a single call apply atomically — either every anchor matches and
all edits land, or none do. Order edits **bottom-up by line number** so that
earlier edits don't invalidate later anchors.

## Show diff in response

```json
{
  "path": "src/auth.ts",
  "diff": true,
  "edits": [
    { "start": "44:b2c", "end": "89:e1d", "content": "..." }
  ]
}
```

Useful when the change is non-trivial and you want to verify the diff before
moving on.

## Insert "after" a line

`tilth_edit` replaces the anchored line(s); there is no native insert. To
insert after line 13, anchor on line 13 and prepend the original line content
to your new content:

```json
{
  "path": "src/auth.ts",
  "edits": [
    {
      "start": "13:abc",
      "content": "import { existingThing } from './existing';\nimport { newHelper } from './helpers';"
    }
  ]
}
```

The first line of `content` reproduces line 13 (`import { existingThing }
…`); the second is the actual insertion. Read line 13 carefully before doing
this — the original content goes back verbatim.

## Edits across multiple files

`tilth_edit` is single-file. For multi-file changes, make one call per file:

```text
tilth_edit({ path: "src/auth.ts",   edits: [...] })
tilth_edit({ path: "src/routes.ts", edits: [...] })
```

There is no atomic cross-file edit. If the second call fails after the first
succeeded, you have a partially applied change — read the second file and
recover before moving on.

## Caller-update notices

When you change a function signature, `tilth_edit` may surface callers in
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
