# Fast path, probe budget, and routing receipt

`/cheese` classifies input and hands work to one skill. The routing receipt marks where routing ends. The probe budget keeps routing short.

## The routing receipt

Emit exactly one line on every route, including `clarify`. Make it the last line before dispatch.

```text
route: intent=<intent> target=<skill> path=<fast|escalated> probes=<n>
```

| Field | Value |
| --- | --- |
| `intent` | The intent shape from `classification.md`, such as `cook`, `mold`, `debug`, `age`, `research`, `rubber-duck`, `plate`, or `clarify`. |
| `target` | The dispatched skill without arguments, such as `cook`. Use `clarify` when a question replaces dispatch. |
| `path` | Use `fast` when the route spent zero evidence probes. Otherwise, use `escalated`. |
| `probes` | The number of evidence probes used for this route. |

Apply these rules:

- **One line, one route.** A re-entry after a `clarify` answer starts a new route. Print a new receipt.
- **Exactly one receipt for each route.** Never print a second receipt for the same route.
- **Nothing follows the receipt.** Print no other router output between this line and the dispatch.
  Put the wiki-hit lines and every other announce line before it.
- **Never a duration and never a timestamp.** Omit both values.
  The router cannot measure wall-clock time.
  The host adds timestamps.
  Analytics take the boundary from the moment the router emits this line.
- **Never a new artifact.** Keep the receipt as ordinary one-line output.
  It is not written to `.cheese/`, not a schema, not a handoff field.
  It carries no authority over the pipeline.
- **Portable by construction.** The receipt is plain text in the announce block. No harness capability is required.
- **Optional to consume, mandatory to emit.** Emit it on all routes, including obvious routes and the fast path.

## What counts as an evidence probe

One probe is one file read, one search call, one `gh` call, or the wiki-grounding call in `## Flow`. The router's budget is **three**. Message reads, argument parsing, and classification table checks cost no probes.

Exceeding three is a routing signal. Escalate to `/culture` or `/briesearch` in internal mode. Spend more probes under a skill whose measurement is supposed to include them.

## The fast path

Classify and dispatch with **zero** probes for these inputs:

- **An explicit skill command** that the user names, such as `/age`, `/cook <path>`, or `/plate`. The user already selected the route.
- **A resolvable durable pointer**, such as a spec path, note path, work ID, or slug. The target validates this pointer.
- **A bounded implementation request** that passes Cook's standalone fast-path check from the message text.
  `/cook` owns that check at [`../../cook/SKILL.md`](../../cook/SKILL.md) section Standalone fast-path.
  Do not restate the check here.

On the fast path, use no repository exploration, task graph, wiki grounding, or clarifying question.
Skip the wiki-grounding step and the bounded artifact read of `coherence-check.md`.
A route that runs either probe is not a fast route.
Count each probe and print `path=escalated` instead.
Never print `probes=0` for a route that read a file or grounded the wiki.
Print the receipt with `path=fast probes=0`.
Then dispatch.

- **Everything else is `escalated`, and stays escalated.** Route every other input through escalation.
- **Genuinely ambiguous input still gets `/culture` reasoning.** Run `/culture` before dispatch.
- **Never removes a tier from unclear ones.** Keep every tier for unclear input.
- **Never adds an approval step to a route that was already unambiguous.** Do not add approval to a clear route.
