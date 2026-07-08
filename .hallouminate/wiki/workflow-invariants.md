# Workflow invariants

These are the rules the cheese pipeline holds constant across every task.
Break one and the pipeline's guarantees stop holding, so treat them as
contracts, not conventions.

## Pipeline ordering

The canonical order is fixed
(`skills/mold/SKILL.md:125`, `skills/cook/SKILL.md:90`):

```text
culture → mold → cook → press → age → cure → ship
```

- **culture** — no-write thinking; never edits code, never the gate.
- **mold** — converges a fuzzy idea into an approved spec at the durable
  XDG corpus path (`$XDG_DATA_HOME/cheese/<project>/specs/<slug>.md`,
  resolved by `shared/scripts/paths.py`; `skills/cheese/references/formatting.md:103`).
- **cook** — TDD-disciplined implementation of that spec.
- **press** — adversarial test hardening of the cooked diff.
- **age** — ten-dimension review producing a findings report.
- **cure** — applies the selected findings as focused fixes.
- **ship** — push / open PR once `just check` is green.

Skipping forward is allowed (e.g. cook → age, skipping press) but the
relative order never inverts: you do not cure before age, or press before
cook. Each phase hands off through a gate (below), and writes a handoff
slug the next phase reads.

## The two-key handshake (mold's curdle gate)

`/mold` will not extract a spec until **both keys** turn
(`skills/mold/references/handshake.md:1-3`):

1. **User key** — the user says an explicit extraction verb: `curdle`,
   `ship it`, `extract`, `that's enough`. A vague "ok let's go" does not
   count (`handshake.md:5-9`).
2. **Agent key** — the agent prints a 10-item coherence self-check
   (problem grounded, ≥2 options weighed including Do Nothing, interface
   sketches with pseudocode signatures, Validate Cycles judged, Grill run
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
runs. `/ultracook` runs the chain
`cook → press → age → cure → age → cure → age` (all `--auto`), capped at
**two cure passes** (`skills/cook/SKILL.md:132`).

## `just check` is the single quality gate

There is exactly one shippability signal: green from `just check`
(`AGENTS.md:7`). It autofixes lint (markdown, yaml, python via ruff) then
runs skill-frontmatter validation, shell lint, the python + bash test
suites, and `mkdocs build --strict`. CI runs `just ci` — the same gates,
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
