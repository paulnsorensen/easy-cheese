# Fast path, probe budget, and the terminal routing receipt

`/cheese` classifies and hands off. Everything after the handoff belongs to the skill that was chosen, and until the router printed a boundary of its own, nothing downstream could tell the two apart: a measured "cheese episode" ran from the invocation to whatever the *next* skill happened to log, so the router was charged for the work it dispatched. The receipt is that boundary, and the probe budget is what keeps the span before it short.

## The routing receipt

Emit exactly one line, as the last line before dispatch, on every route including `clarify`:

```text
route: intent=<intent> target=<skill> path=<fast|escalated> probes=<n>
```

| Field | Value |
| --- | --- |
| `intent` | the intent shape chosen in `classification.md` (`cook`, `mold`, `debug`, `age`, `research`, `rubber-duck`, `plate`, `clarify`, …) |
| `target` | the skill actually dispatched, without arguments (`/cook` → `cook`); `clarify` when the dispatch is replaced by the clarifying question |
| `path` | `fast` when the route spent zero evidence probes, `escalated` otherwise |
| `probes` | the integer count of evidence probes spent this route (see below) |

Rules that make it usable as data:

- **One line, one route.** A re-entry after a `clarify` answer is a new route and prints its own receipt.
- **Never a duration and never a timestamp.** The router cannot measure wall-clock time and must not guess at one. The host already timestamps messages, so analytics take the boundary from when this line was emitted and derive the classification span themselves. A self-reported number would be a second, worse answer to a question the transcript already answers.
- **Never a new artifact.** The receipt is one line of ordinary output. It is not written to `.cheese/`, not a schema, not a handoff field, and carries no authority over the pipeline: deleting it would change what analytics can measure and nothing about what runs.
- **Portable by construction.** Plain text in the normal announce block, so a harness with no telemetry support still shows it and a harness that scrapes transcripts still gets it. No harness capability is required or probed for.
- **Optional to consume, mandatory to emit.** Skipping it on "obvious" routes is what produced the unattributable sample in the first place; the fast path is exactly the case worth counting.

## What counts as an evidence probe

One probe is one of: a single file read, one search call, one `gh` call, or the single wiki-grounding call in `## Flow`. The router's budget is **three**. Reading the user's own message, parsing arguments, and matching the classification table cost nothing.

Exceeding three is a routing signal, not a licence to keep going: the input needs work the router should not be doing, so escalate to `/culture` or `/briesearch` in internal mode (tier 2) and let the probes be spent there, under a skill whose measurement is supposed to include them.

## The fast path

Classify and dispatch with **zero** probes when the input is any of:

- **An explicit skill command** the user already named (`/age`, `/cook <path>`, `/plate`) — the routing decision was made by the user, so re-deriving it is wasted work.
- **A resolvable durable pointer** — a spec path, a `.cheese/notes/<slug>.md` path, a work id, or a slug. Validation belongs to the target (`/cook` reads the spec; `/wheypoint resolve` validates the handoff), and duplicating it here buys nothing the target will not redo.
- **A bounded implementation request** that passes cook's fast-path check on the message text alone, with a named file or a named behavior and no open design question.

On the fast path: no repository exploration, no task-graph construction, no wiki grounding, no clarifying question. Print the announce block and the receipt with `path=fast probes=0`, and dispatch.

Everything else is `escalated`, and stays escalated: genuinely ambiguous input still gets `/culture` reasoning before dispatch rather than a premature guess. The fast path removes work from clear inputs; it never removes a tier from unclear ones, and it never adds an approval step to a route that was already unambiguous.
