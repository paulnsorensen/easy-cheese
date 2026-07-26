# GitHub publication

Use this reference only when `/age` receives `--post-report` or `--post-inline`.
The default remains local-only: without either flag, write the canonical Age
artifact and perform no GitHub write.

## Shared contract

Apply these rules to both modes:

1. Write the canonical local report first. Publish only a completed
   `status: ok` report.
2. Require an existing pull request. Resolve it from the explicit PR input or
   the current branch. `--open-pr` does not create a publication target early
   enough for Age.
3. Before dispatching reviewers, resolve the PR's base and head SHAs and review
   that exact committed `base...head` diff. Exclude index and working-tree
   changes even when local `HEAD` equals the PR head. Refuse publication when
   the completed report came from any other input.
4. Pin publication to both reviewed SHAs. Re-read the PR immediately before
   the first write and stop if its base or head changed.
5. Fetch existing PR conversation comments and inline review threads before
   posting. Use the markers below to update prior Age output instead of
   duplicating it.
6. Use the host GitHub primitive when available, with `gh` as fallback. Halt
   when neither exists.
7. Submit review comments with the `COMMENT` event. Comment-only publication
   must never `APPROVE` or `REQUEST_CHANGES`.
8. Publish only findings visible in the canonical report. Suppressed lows stay
   unpublished until the user reruns with `--full`.
9. Do not publish from dimension workers or review-context sub-agents.
10. Do not propagate either publication flag to `/cure`, `/plate`, or nested
   `/age --auto` invocations.

Leave the local report intact on any publication failure. Report how many
comments were created or updated, then stop before the Handoff.

## Full-report mode

`--post-report` publishes one top-level PR conversation comment.

Render the reader-facing report from its `# Age Report` heading onward. Omit
the machine handoff header (`status`, `next`, `artifact`, `durable_flags`,
`baseline`, and orientation preamble). Prepend this stable marker:

```html
<!-- easy-cheese:age:report slug=<slug> -->
```

Search existing PR conversation comments for the exact marker. When found,
update the existing comment. Otherwise, create one new comment. Never split a
normal Age report across comments; if the provider rejects its size, fail loud
and leave the local artifact as the complete source.

Do not create inline threads in this mode.

## Inline mode

`--post-inline` publishes one inline thread per anchorable finding plus one
top-level summary comment.

### Finding keys and markers

Derive a deterministic finding key from the finding's dimension, repository
path, and normalized claim. Do not include line numbers, severity,
recommendation, or other mutable rendering fields. Use a short SHA-256 digest
or an equivalent stable hash. Append this marker to every inline body:

```html
<!-- easy-cheese:age:finding slug=<slug> key=<finding-key> -->
```

Before posting, search all current and outdated review threads for the marker:

- Partition the canonical findings into anchorable and unanchorable sets before
  matching threads.
- Match an anchorable finding by exact key first. If its prose was rephrased
  and no exact key exists, semantically reconcile same-slug Age comments using
  dimension, path, referenced symbol, and problem category. Reuse and replace
  the old marker only when exactly one prior finding is an unambiguous match;
  otherwise create a new thread and retire unmatched prior threads normally.
- When a current thread contains the matched marker and its anchor still
  supports the finding, update the existing inline comment and unresolve the
  thread if a prior run retired it.
- When the matched current thread's anchor no longer supports the finding,
  resolve it and create a replacement at the current anchor.
- When only an outdated thread contains it and the finding remains, create a
  replacement at the current anchor and resolve the outdated thread. Prefer the
  current non-outdated thread on later runs.
- When no thread contains it, create a new inline comment.

Group all new inline comments into one PR review with the `COMMENT` event.
Updates to existing threads may happen individually before that review is
submitted.

After matching the anchorable findings, retire every current, same-slug Age
thread whose marker is unmatched or whose finding is now unanchorable: append
`Resolved by the Age review of <head-sha>.` while preserving its marker, then
resolve the thread. Never delete the historical comment. Include an
unanchorable finding only in the top-level summary, not in a still-current
inline thread. If the provider cannot resolve or unresolve a marked thread,
report partial counts and treat publication as failed rather than leaving the
summary in conflict with open Age threads. Do not touch unmarked threads or
markers for another slug.

### Anchoring

Anchor a finding only when its reported range overlaps the PR diff:

- added or context line: `RIGHT`;
- deleted line: `LEFT`;
- multi-line finding: use the narrowest changed range that supports the claim.

Do not guess a nearby changed line. Treat findings on unchanged code, the PR
body, external files, generated context, or a range GitHub rejects as
unanchorable findings.

Render each inline body as:

```markdown
**[<dimension>:<severity>]** <claim>

<location / fix-cost / confidence line>

Recommendation: <action>

<!-- easy-cheese:age:finding slug=<slug> key=<finding-key> -->
```

### Summary and unanchorable findings

Publish one top-level summary comment containing severity counts and every
unanchorable finding in the report's normal finding format. For a clean review,
publish the summary with zero counts and no inline threads. Prepend:

```html
<!-- easy-cheese:age:inline-summary slug=<slug> -->
```

Search PR conversation comments for the exact marker and update the existing
comment. Otherwise, create it. Keep this summary compact; the canonical local
artifact remains the complete report.

## Transport

State the semantic operation first: fetch PR comments and threads, update a
matching marked comment, create a top-level comment, or submit a comment-only
review with file comments.

Prefer the host GitHub primitive. With `gh`, use the corresponding GitHub REST
or GraphQL endpoint and pass bodies as data fields or files, never shell-
interpolated JSON. Follow
[`../../cheese/references/harness-portability.md`](../../cheese/references/harness-portability.md)
for capability detection and fallback.
