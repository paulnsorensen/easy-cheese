# Domain-model correction for Cure

Read this file before Flow step 6.

After Cook fixes land, correct domain terms that the Cook diff touches.
Do not rewrite terms outside that diff.

After the Hallouminate probe, resolve the store with the Cure bundle command:

```text
python3 skills/cure/scripts/cure.pyz domain-model-target \
  --probe <unavailable|no-match|match> \
  [--corpus repo:<repo>:wiki --model <present|absent|unknown>]
```

Use the domain-model probe transport in [`../../cheese/references/optional-plugins.md`](../../cheese/references/optional-plugins.md).

Pass `unavailable` when Hallouminate is not loaded or the probe failed. Pass `no-match` when the listing completed but contained no `repo:*:wiki` corpus. Pass `match` with the exact corpus name and its model status when the listing found one. The command accepts only these explicit probe results; it does not import or invoke MCP machinery. It emits canonical JSON with `backend`, string `location`, and `wiki_reachable`. Preserve the resolver's wiki, docs, then XDG precedence. When `wiki_reachable` is false, report the degraded file fallback before correcting it; the wiki can contain the authoritative model.

Read and write each backend with these steps:

- **One file.** Read the whole file. Update the touched entry. Read the file again.
- **Split directory.** List the context pages. Select the page of the bounded context that owns the term.
  Read only that page. Update the touched entry there. Read that page again.
  Stop and report when two pages define the same term.
- **Hallouminate corpus.** Read the entry with `read_markdown`.
  Write the updated entry with `add_markdown` and `overwrite: true`.
  Read the entry again with `read_markdown`.

Report the backend and the exact location in the Cure report.

Update a touched entry when its definition or `_Code_:` target no longer matches the code.
Write one change note for each edit.
Use this format:

```text
**Term** — definition.
_Avoid_: syn1, syn2
_Code_: file:line (or NEW ENTITY)
```

`_Avoid_` is optional.
Mold omits this line when the term has no synonym.
Keep that omission, and never create a placeholder synonym.

**Hard rule: Report a reversal, but do not apply it.**
Do not replace or contradict a canonical term that Mold made authoritative.
Report the term, the Mold decision, and the conflict.
Leave the entry unchanged.
Mold selects canonical terms during Curdle.
Cure applies only bounded corrections.
