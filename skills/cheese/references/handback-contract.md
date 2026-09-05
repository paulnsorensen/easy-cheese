# Handback contract

One contract governs every phase dispatch and handback.
The returned handback and durable `.cheese/` artifact use the same preamble and status vocabulary.
The `hard-cheese` receipt uses `status: PASS | FAIL | FAILED | LOGGED`.
It is a grading record, not a handback.
Neither vocabulary extends the other.

`easy_cheese_schemas.phase_contracts` is the machine source of truth.
It defines the status vocabulary, wire grammar, and phase transition registry.
Each skill bundle contains this module.
This file describes only rules that the module enforces.
Producers and consumers must not derive the grammar again.

## The preamble

```text
status: <status>                            # vocabulary below
next: <skill-name> | done
artifact: <path-to-prior-report-if-any>     # key always present, value may be empty
<one-line orientation: what changed or what was reviewed>
```

Optional keyed lines sit between `artifact:` and the orientation line.
They are `taste_test:`, `durable_flags:`, and `baseline:`.
A fan-in barrier adds `scope`, `evidence`, `assumptions`, and `risks`.
See [`handoff-gate.md`](handoff-gate.md) section Fan-in envelope fields.
These fields extend the preamble and do not create a second shape.

`artifact:` names the **prior** report this dispatch consumed, not the file
being written. It is empty (`artifact:` with nothing after it) when the
dispatch had no upstream report; the key is never omitted.

`artifact:` has exactly one meaning. It never carries another kind of reference.
Each other reference kind has its own carrier:

| Reference kind | Carrier | Consumer |
|---|---|---|
| prior consumed report | `artifact:` | the next phase, `/cheese --continue` |
| approved specification pointer | the typed `handoff.spec_ref` field that `/mold` emits | `/cook` |
| pull request reference | the `<pr-ref>` argument of `/affinage` | `/affinage` |

Read the reference kind from its carrier, not from `next:`.
A legacy handwritten note is the one exception. It can put a pull request reference in `artifact:`.
See [`continue-resume.md`](continue-resume.md) for that legacy rule.

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
- **In `/wheypoint`**, status is derived from the run, not asserted: an open
  blocker means `gated:`, and no caller can force `ok` over it (see
  `skills/wheypoint/SKILL.md` § derivation). Elsewhere the writer is trusted
  to report accurately — this module validates the wire grammar, not the
  phase's self-assessment.

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
| Phase handback | `/mold`, `/cook`, `/press`, `/age`, `/cure` | the dispatching orchestrator | `status`, `next`, `artifact`, orientation | `taste_test`, `durable_flags`, `baseline` |
| Durable report | the same phases, via the artifact writer | the next phase, `/cheese --continue` | same preamble + body | same |
| Unregistered report | `/affinage`, `/pasteurize` | `/cheese --continue` | same preamble, written by hand | same |
| Fan phase router | a fan-out phase handback | `/cook`'s fan pathway phase decision | `status` (routed by disposition), `next` | — |
| Checkpoint note | `/wheypoint` | `/cheese --continue` | `status`, `next`, `artifact`, orientation | decision dossier body |
| Grading receipt (distinct vocabulary, not a handback) | `/hard-cheese` | the attempt log | `status: PASS \| FAIL \| FAILED \| LOGGED` | `attempts` |

`schema-intertwine.md` lists the registered source phases.
Only a registered phase can use the artifact writer, because the writer validates `phase -> next:` first.
`/affinage` and `/pasteurize` have no registered transition today.
They write the same preamble by hand and do not call the writer.
Register their transitions before you route them through the writer.

## Wire-format limits

- **Reasons are capped** at `MAX_REASON_LENGTH` (512 characters); a longer
  reason is rejected on render and on parse, not silently truncated.
- **Status names are ASCII-only.** A homoglyph (e.g. a Unicode lookalike of a
  registered name) is rejected before lookup, so the accepted set never
  widens beyond the vocabulary above.
- **Every preamble field is single-line** — `status`, `next`, `artifact`,
  `orientation`, `taste_test`, `durable_flags`, `baseline` — a newline in any
  of them is a render-time contract violation, not a value that reaches the
  artifact.
- **`reason` is the field name**; `halt_reason` is a deprecated read-only
  alias kept for readers written against the pre-rename shape (`handoff_cli
  parse` still publishes both JSON keys).

## CLI and router behavior

- **Exit codes.** A contract violation exits with code 3.
  Other `CliError` failures exit with code 2.
  The CLI includes the dispatch context in each contract violation.
  This context identifies the phase, slug, or file.
- **The fan router verdict carries the full vocabulary.** `Verdict` always reports `status`, `disposition`, and `reason`.
  A `gated` status uses the `gated` action.
  An `ok-with-concerns` branch adds its concern to `exit_message`.
- **`needs-context` requires a reason and has a limit.** The router rejects a reasonless value.
  The first value re-dispatches the same phase.
  A second value at that phase stops with `retry cap (1) reached`.
- **`next:` is informational under `stop`.** Only a `proceed` disposition
  walks the transition table on `next:`; under `gated` or `halt` the router
  ignores whatever `next:` names and ends the run on the reason instead.

## Dispatch names its contracts

Every worker dispatch names its input and output contracts.
Do not infer output shape from the brief.
A missing output contract means the dispatch is incomplete.
An unsupported returned shape is a contract violation.
