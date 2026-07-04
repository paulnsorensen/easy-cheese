# `tilth_edit` JSON cookbook

Every edit needs a `start` anchor; `end` is required only for range replacements, and `content` is the new text (use `""` to delete). Read the active tilth docs or tool schema for exact call wrapping before copying these shapes.

## Single-line replacement

```json
{
  "path": "src/auth.ts",
  "edits": [
    { "start": "42:a3f", "content": "  let x = recompute();" }
  ]
}
```

Replaces line 42 only. The hash `a3f` must match the `<line>:<hash>` prefix
`tilth_read` returned for that line.

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

## Multiple edits in one file

```json
{
  "path": "src/auth.ts",
  "edits": [
    { "start": "12:a1b", "content": "import { newHelper } from './helpers';" },
    { "start": "44:b2c", "end": "89:e1d", "content": "// replaced function\n..." }
  ]
}
```

Keep related edits together when the backend supports it. If any anchor fails,
re-read the file and recover before moving on.

## Show diff in response

```text
tilth_edit({ "path": "src/auth.ts", "edits": [{ "start": "44:b2c", "end": "89:e1d", "content": "..." }], "diff": true })
```

`diff` is a call option; if the backend exposes it only at batch scope, pass it there.

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

Use the backend's batch form when it has one; otherwise edit one file at a time
and verify each response before moving to the next file.

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
