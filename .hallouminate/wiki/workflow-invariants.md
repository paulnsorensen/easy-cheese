# Workflow invariants

These are the rules the cheese pipeline holds constant across every task.
Break one and the pipeline's guarantees stop holding, so treat them as
contracts, not conventions.

## Pipeline ordering

The canonical order is fixed:

```text
culture → mold → cook (⇄ press) → age → cure → plate
```

- **culture** — no-write thinking; never edits code, never the gate.
- **mold** — converges a fuzzy idea into an approved spec at the durable
  XDG corpus path (`$XDG_DATA_HOME/cheese/<project>/specs/<slug>.md`;
  `skills/cheese/references/formatting.md`). Every spec carries an
  `## Acceptance demonstration` section, or `n/a: <reason>` for
  non-behavior work
  ([adr/acceptance-demonstration-press-fold-002](./adr/acceptance-demonstration-press-fold-002.md)).
- **cook** — implementation of that spec. Cook owns first acceptance
  coverage as a reported obligation, not a RED gate, and runs the Press
  loop for behavior work.
- **press** — the adversarial pass that Cook dispatches inside its loop;
  `/press <slug>` stays callable for a manual re-run.
- **age** — twelve-dimension review producing a findings report.
- **cure** — applies the selected findings as focused fixes.
- **plate** — write and verify final artifacts, run `just check`, commit, then publish an ordinary PR or stack.

Skipping forward is allowed (e.g. cook → age for non-behavior work) but
the relative order never inverts: you do not cure before age. Each phase
hands off through a gate (below), and writes a handoff slug the next phase
reads. The phase registry has no `cook -> press` transition; Cook hands
behavior work to Age after its Press loop is green.

The retired `/cut` phase and its `GateReceipt` RED gate no longer exist
([adr/outer-tdd-gates-001](./adr/outer-tdd-gates-001.md) records the
earlier design).

## The two-key handshake (mold's curdle gate)

`/mold` will not extract a spec until **both keys** turn
(`skills/mold/references/handshake.md:1-3`):

1. **User key** — the user expresses explicit extraction intent: `curdle`,
   `ship it`, `extract`, or `that's enough`. A clear affirmative such as
   `ok let's go`, `sounds good`, or `go ahead` also counts when it directly
   answers an agent's extraction question. Do not infer the key from unrelated
   or ambiguous approval (`handshake.md:5-10`).
2. **Agent key** — the agent prints a 10-item coherence self-check
   (problem grounded, ≥2 options weighed including Do Nothing, interface
   sketches as a complete Placement block, Validate Cycles judged, Grill run
   for high-blast-radius work, open questions marked, quality gates
   specified) and every box must be checked, or the user issues an
   explicit `curdle anyway` override (`handshake.md:11-27`).

Mandatory gates fire even before the keys: Ground (≥1 citation), Shape
(≥1 option block), Sketch (when >1 module is touched), Grill (when blast
radius is `high`), and the agent-introduced-scope gate — every
distinguishing noun in the spec must trace to a user mention or get
explicit per-term approval (`handshake.md:31-64`).

The handshake is **bypassed** in mold's agent-invoked mini-spec mode,
i.e. when `/cheese` calls `/mold` internally to materialise a spec for an
already-clear task (`skills/mold/SKILL.md:12,46`).

## Handoff gates between phases

Phases never dispatch the next phase silently. Each ends at a handoff
gate defined by `skills/cheese/references/handoff-gate.md`: a `handoff_gate:` block naming
the `source_skill`, a `recommended` option, and an `options` list, each
option carrying a `label` plus a `dispatch` / `continue` / `dispatch:
none` action (`skills/cheese/references/handoff-gate.md:18-40`). Context for the next phase
rides alongside as `handoff_context:` (`skills/cheese/references/handoff-gate.md:69-85`).
A gate prevents silent dispatch; it does **not** mean the agent halts
after the user chooses (`skills/cheese/references/handoff-gate.md:7`).

`--auto` propagates through the chain to skip these gates for autonomous
runs. `/cook`'s `--auto` mode runs Cook with its Press loop, then
`age → cure → age → cure → age`, capped at **two cure passes**
(`skills/cook/references/auto-mode.md`). This chain — and the parallel fan
pathway — was absorbed from the now-retired `/ultracook` (PR #316 moved
ownership; PR #317 retired the entry point).

Press is not a handoff step. For behavior work, Cook dispatches a
fresh-context Press agent after its taste test and loops on the outcome:
`finding` and `coverage_gap` return to Cook as a correction, and `green`
lets Cook hand off to Age (`skills/cook/references/press-loop.md`). Cook
counts the rounds: two corrections per attack, one `coverage_gap` retry,
and six Press rounds in total. Non-behavior work skips the loop, because it
has no adversarial contract for Press to attack. The fan orchestrator runs
the same loop per curd and runs an integrated acceptance check on the
merged tip; no global post-merge Press runs
(`src/easy_cheese/shared/fanout/run_fan.py`;
[adr/acceptance-demonstration-press-fold-001](./adr/acceptance-demonstration-press-fold-001.md)).




### Handback vs handoff (PR #578, r014)

Two terms, one contract. A **handback** is the in-session `status:` message a
spawned phase worker returns to its orchestrator; a **handoff** is the durable
`.cheese/<phase>/<slug>.md` artifact (and its preamble "slug") that carries
that status plus routing (`next:`, `artifact:`) between phases. They meet at
the `status:` field. The word "handback" first entered the repo in PR #578
(closing #350 and #154); it does not exist on `main` before that PR.

The vocabulary is machine-owned by `easy_cheese_schemas.handback_status`
(re-exported by the package): `ok`, `ok-with-concerns`,
`needs-context`, `gated`, `halt`, each mapped to a `Disposition` StrEnum
(`proceed` / `retry` / `stop`). Prose face:
`skills/cheese/references/handback-contract.md`; every producer doc prints
`status: <canonical status field>` and links there — a docs test
(`tests/python/test_handback_grammar_docs.py`) forbids the old
`status: ok | halt:` literal anywhere else under `skills/`.

Gotchas the r014 cure settled:

- Consumers branch on `disposition`, never on a name or prefix. The pre-#578
  fan router used `startswith("halt")`, so a `gated:` handback spawned the
  next phase silently. The router's `Verdict` now also carries `status`,
  `disposition`, and `reason`; `action` is the router's decision and can
  differ from `disposition` at the retry cap (second `needs-context` at the
  same phase → `action: halt`, `disposition: retry`). Branch on `action`.
- `needs-context` must name a gap; a bare one is a contract error. Retry is
  once-only via `phase-decision --retry-count`.
- Every preamble field is single-line; reasons are capped at
  `MAX_REASON_LENGTH = 512`; status names are ASCII-only.
- The preamble field is `reason`; `halt_reason` survives as a deprecated
  alias (constructor kwarg, property, and JSON key from `handoff-cli parse`
  and `read-handoff-slug`) because the stacked r014 PRs (#579–#589) read it.
- CLIs exit `3` on a contract violation (bad status, illegal transition,
  newline in a field — prefixed with the dispatch context) and `2` on I/O.
- `WheypointStatus` (`ok`/`gated`) is a second, derived vocabulary rendered
  by `wheypoint/projection.py`; a conformance test pins it to the registered
  statuses, but its render path does not yet go through
  `render_status_field` (deferred to the wheypoint stack).



[architecture/handoff-preamble-grammar](./architecture/handoff-preamble-grammar.md)
records the preamble key set, the single-line rule, the `--body-file` trap, the
route-table gate on the canonical writer (`validate_route` in
`src/easy_cheese/shared/phase_routes.py`), and the base-revision rule for
phase writes.

## Cook entry refuses held specs

Cook has no typed handoff or `prepare` step.
Mold `finalize` prints `/cook --auto --result <result_path>` for bound work, and standalone work uses `/cook --spec <path>`.
Bound work runs through `execute_bound_plan`, which first calls `validate_bound_execution` (`src/easy_cheese/shared/mold_cook_handoff.py`).
That validator refuses a spec whose lifecycle is not `approved` and a spec with non-empty `gates_overridden`.
For a `--spec` run, Cook's ingress prose adds a spec-hold refusal: it refuses a spec with `execution_holds`, or with a `do-not-implement` or `do-not-proceed` `request_directive` (`skills/cook/SKILL.md:280`).
Saving a spec never clears a hold.
Cook still accepts a legacy spec that lacks a hardened `source` on read.
The reasons are in [mold-cook-boundary-002](./adr/mold-cook-boundary-002.md); PR #774 removed the typed handoff.

## Plate is the final writing gate

`/plate` is the only phase that owns the complete transition from finished local work
to reviewable remote work.[^plate-flow] Before `just check`, staging, commit, or PR
publication, it inventories every promised artifact and implementation-time durable fact,
writes each required target through hallouminate or the tracked fallback, reads it back,
and records `{target, backend, verified}`.[^plate-writes] A required write that cannot be
verified stops publication.

For every new PR, an explicit topology choice is authoritative. Otherwise `/plate`
decides the shape without asking: `single`, `orthogonal_flat`, `stacked_linear`, or a
dependent chain plus independent PRs ([[plate-publication-boundary-002]]). It never
stacks parts that do not depend on each other. Dependency and cohesion decide the shape;
size never decides it alone. `/cook`'s parallel fan pathway (`--open-pr`) runs that policy
before seed or worker commits, records `plate_layout` and `shape` in its manifest and PR
plan, and reuses the resolution at terminal publication. A supplied plan cannot override an
explicit choice. Existing PR updates preserve detected topology. A stack runs the write,
validation, named-stage, commit, and verification transaction once per layer before
whole-chain submission; shared durable writes belong on the bottom/common branch or an
explicit wiring branch.

[^plate-flow]: skills/plate/SKILL.md:33-147
[^plate-writes]: skills/plate/references/durable-writes.md:1-40

## `just check` is the single quality gate

There is exactly one shippability signal: green from `just check`
(`AGENTS.md:7`). It autofixes lint (markdown, yaml, python via ruff) then
runs skill- and wiki-frontmatter validation, shell lint, the python +
bash + JS test suites, and the Astro/Starlight docs build
(`pnpm run docs:build`). CI runs `just ci` — the same gates,
no autofixes. **Never commit or push on a red `just check`**, and never
weaken or skip a test to force green. See [tooling](./tooling.md) for the
recipe breakdown.

## The durable/transient boundary

Durable knowledge splits two ways. Architecture, protocols, conventions,
and rationale are git-tracked under `.hallouminate/wiki/`; specs and
research reports are durable too but live out of git at the XDG project
corpus (`$XDG_DATA_HOME/cheese/<project>/`, owned by
`shared/scripts/paths.py`). Only per-task pipeline output (`/cook` `/age`
`/press` `/cure` reports, notes, hard, handoffs) is transient, gitignored
under `.cheese/` (`.gitignore:2`). Durability is not the git-tracking
axis (`skills/cheese/references/formatting.md:103`) — see
[wiki-conventions](./wiki-conventions.md) for the full classification
rule. This invariant exists so later integration seams cannot dump
transient noise into durable memory.


_Source: repository skills and tests; r014 skill-review round notes (ingest hash 499c49c7b67d5eb6) for the preamble-grammar pointer · Updated: 2026-09-04_

