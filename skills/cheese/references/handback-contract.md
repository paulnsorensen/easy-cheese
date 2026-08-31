# Handback contract

One contract governs every phase dispatch and every handback in the pipeline.
There is no second dialect: the in-session handback a worker returns and the
durable `.cheese/` artifact it writes carry the *same* preamble block, and the
same status vocabulary routes both.

The machine source of truth is `easy_cheese_schemas.phase_contracts` — the
status vocabulary, its wire grammar, and the phase-transition registry — staged
into every skill bundle. This file is that module's prose face; nothing here
restates a rule the module does not enforce, and no producer or consumer
re-derives the grammar locally.

## The preamble

```text
status: <status>                            # vocabulary below
next: <skill-name> | done
artifact: <path-to-prior-report-if-any>     # key always present, value may be empty
<one-line orientation: what changed or what was reviewed>
```

Optional keyed lines sit between `artifact:` and the orientation line:
`taste_test:`, `durable_flags:`, `baseline:`. A fan-in barrier extends the same
block with `scope` / `evidence` / `assumptions` / `risks`
(see [`handoff-gate.md`](handoff-gate.md) § Fan-in envelope fields) — an
extension of this preamble, never a second shape.

`artifact:` names the **prior** report this dispatch consumed, not the file
being written. It is empty (`artifact:` with nothing after it) when the
dispatch had no upstream report; the key is never omitted.

## Status vocabulary

| `status:` | Wire form | Disposition | Meaning |
|---|---|---|---|
| `ok` | `ok` — stands alone, never carries a reason | **proceed** | The phase did its job; the orchestrator walks on to `next:`. |
| `ok-with-concerns` | `ok-with-concerns: <one-line concern>` | **proceed** | The phase did its job and found something the next phase should know. Name the concern; the run walks on and carries it forward. |
| `needs-context` | `needs-context: <one-line gap>` | **retry** | The phase cannot finish with what it was handed. Name the missing input; the orchestrator re-dispatches the **same** phase with it. |
| `gated` | `gated: <one-line decision>` | **stop** | The work is sound but the next step is blocked on a human decision. Name the decision. |
| `halt` | `halt: <one-line reason>` | **stop** | The phase could not complete. Name the reason. |

Rules that hold at every seam:

- **Consumers branch on the disposition, not the name.** `proceed` walks the
  table; `retry` re-dispatches the phase that just returned, without advancing
  the phase index; `stop` ends the run and surfaces the reason. Adding a status
  must not require editing every consumer, and a status a consumer does not
  recognise is an error — never a silent "proceed".
- **A `retry` handback is a request for input, not a second attempt at the same
  brief.** The re-dispatch must carry the gap the worker named; re-running the
  identical prompt would return the identical status.
- **Every non-`ok` status carries a one-line reason**; `ok` carries none.
  Both halves are enforced on render and on parse.
- **Names are matched case-insensitively** after stripping, because the field
  is read back out of agent-authored prose.
- **Readers of an already-emitted field** (the phase router, the legacy note
  reader) tolerate a reason-carrying status that arrived bare — it still routes
  by its declared disposition. They never widen the vocabulary itself.
- Status is **derived from the run, not asserted**: an open blocker means
  `gated:`, and no caller can force `ok` over it.

## In-session handback vs durable artifact

Two carriers, one contract:

- The **in-session handback** is the preamble block a spawned worker returns as
  the head of its final message. It is what the dispatching orchestrator parses.
- The **durable artifact** is `.cheese/<phase>/<slug>.md`, written atomically by
  the handoff-artifact writer: the identical preamble as its first lines,
  a blank line, then the report body. The write validates `phase → next:`
  against the phase-transition registry before it touches the filesystem, so an
  artifact that exists is an artifact whose transition is legal.

A worker that writes a durable artifact hands back the same `status:` /
`next:` it wrote there, with `artifact:` pointing at the report it consumed.
The two must never tell different stories.

## Boundaries

| Boundary | Producer | Consumer | Required fields | Optional fields |
|---|---|---|---|---|
| Phase handback | `/cook`, `/press`, `/age`, `/cure`, `/affinage`, `/pasteurize`, `/mold` | the dispatching orchestrator | `status`, `next`, `artifact`, orientation | `taste_test`, `durable_flags`, `baseline` |
| Durable report | the same phases, via the artifact writer | the next phase, `/cheese --continue` | same preamble + body | same |
| Fan phase router | a fan-out phase handback | `/cook`'s fan pathway phase decision | `status` (routed by disposition), `next` | — |
| Checkpoint note | `/wheypoint` | `/cheese --continue` | `status`, `next`, `artifact`, orientation | decision dossier body |

## Dispatch names its contracts

Every worker dispatch states, explicitly, the input contract it is handed and
the output contract it must return — by name, in the prompt. Output shape is
never inferred from wording in the brief: a worker that is not told which
contract to return has been underspecified, and returning a shape the consumer
does not accept is a contract violation, not a style difference.
