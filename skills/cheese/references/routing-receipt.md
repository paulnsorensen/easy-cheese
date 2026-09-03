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
- **Never a duration and never a timestamp.** The router cannot measure wall-clock time. The host adds timestamps. Analytics take the boundary from when this line was emitted.
- **Never a new artifact.** The receipt is ordinary output. It is not written to `.cheese/`, not a schema, not a handoff field. It carries no authority over the pipeline.
- **Portable by construction.** The receipt is plain text in the announce block. No harness capability is required.
- **Optional to consume, mandatory to emit.** Emit it on all routes, including obvious routes and the fast path.

## What counts as an evidence probe

One probe is one file read, one search call, one `gh` call, or the wiki-grounding call in `## Flow`. The router's budget is **three**. Message reads, argument parsing, and classification table checks cost no probes.

Exceeding three is a routing signal. Escalate to `/culture` or `/briesearch` in internal mode. Spend more probes under a skill whose measurement is supposed to include them.

## The fast path

Classify and dispatch with **zero** probes for these inputs:

- **An explicit skill command** that the user names, such as `/age`, `/cook <path>`, or `/plate`. The user already selected the route.
- **A resolvable durable pointer**, such as a spec path, note path, work ID, or slug. The target validates this pointer.
- **A bounded implementation request** that passes cook's fast-path check from the message text. It must name a file or behavior. It must have no open design question.

On the fast path, use no repository exploration, task graph, wiki grounding, or clarifying question. Print the receipt with `path=fast probes=0`, and dispatch.

Everything else is `escalated`, and stays escalated. Genuinely ambiguous input still gets `/culture` reasoning before dispatch. The fast path never removes a tier from unclear ones. It never adds an approval step to a route that was already unambiguous.
