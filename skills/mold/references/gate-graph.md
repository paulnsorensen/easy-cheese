# The gate graph

`GATE_MODEL` in `src/easy_cheese/skills/mold/gate_graph.py` holds the one
canonical model of Mold's gate state machine. `mold.pyz` bundles it as the
`gate-graph` subcommand. Both render targets derive from that one model, so
they cannot drift. See ADR-001. The model is also the gate-prose-sync source.
One test asserts that the handshake coherence-checklist items equal the model's
gate nodes. No gate can therefore disappear from the prose without a failure.

## Subcommand

```bash
python3 skills/mold/scripts/mold.pyz gate-graph \
  [--state <state.json>] [--render dot|svg|png|mermaid] [--out <path>]
```

- `--render dot` (default): canonical Graphviz `.dot` to stdout.
- `--render mermaid`: a fenced ```mermaid flowchart block to stdout — renders
  natively in GitHub and markdown viewers, **no binary required**.
- `--render svg|png`: shells out to Graphviz `dot` when it is on PATH; pass
  `--out <path>` for binary targets. When `dot` is absent it **degrades to
  mermaid** and prints a note to stderr — run-anywhere by construction.
- `--state`: an optional Mold `state.json`. The command validates its shape.
  The gate model stays static, so the state does not change the graph today.

## When to use it

- Onboarding a contributor to mold's flow — one picture of modes → gates →
  handshake → curdle.
- Auditing that the prose checklist and the enforced gates still agree (the
  gate-prose-sync test is the automated form; the rendered graph is the human
  form).
- Embedding the mermaid block in a doc or PR description where no Graphviz
  toolchain exists.

## Why dual-render from one model

Requiring Graphviz would break run-anywhere (it is absent on many machines,
including the dev box). Mermaid-only would lose the canonical `.dot` /
enforcement angle. Emitting both from one in-memory model keeps zero hard
dependency *and* keeps the two targets in lockstep — the no-drift guarantee is
structural, not a convention someone has to remember.

## Snapshot

`skills/mold/scripts/mold.dot` is the committed canonical `.dot`. A test asserts
it byte-matches `to_dot()`, so the snapshot can never go stale against the model.
Regenerate it whenever the model changes:

```bash
python3 skills/mold/scripts/mold.pyz gate-graph --render dot \
  --out skills/mold/scripts/mold.dot
```

## The non-goals gate

One coherence gate is worth calling out on its own: `non-goals-audit` (rendered
`non_goals_audit` in the `.dot`; label *Non-goals audit: every bullet traces to a
user-stated out-of-scope item or is marked [AGENT-INTRODUCED]*). Like every gate
node it feeds the handshake and is kept in lockstep with the `handshake.md`
checklist. It makes the most consequential lean — narrowing scope via `Non-goals`
— a first-class, testable gate rather than a prose-only check (ADR-002). The
audit procedure lives in `handshake.md` § Non-goals audit.

## Fork taste planner gate
`fork_taste_test_passed` is the only edge into the typed planner stage. Mold
hashes the exact draft before it accepts a verdict. The strict
`ForkTasteVerdict` must cover each settled consequential decision exactly once.

The verdict fails for a stale digest, missing reflection, contradiction, orphan, unsupported assumption, or acceptance gap. A semantic `pass` with blockers also fails.

The required reflection set depends on the disposition. A `red-required` draft requires Approach, Interface sketches, Acceptance, and Test Contracts. A `not-applicable` draft requires the first three reflections. The applicability gate prohibits Test Contracts in a `not-applicable` draft.

A third failure stops typed planning and the two-key handshake.

The automatic handoff is `/cook --auto <pointer path>`. It passes the published pointer and the approved metadata without changes. This metadata includes applicability, contract, and taste data.
