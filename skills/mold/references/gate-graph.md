# The gate graph

Mold's gate state machine has one canonical model: `src/mold/gate-graph.py`'s
`GATE_MODEL` (bundled into `mold.pyz` as the `gate-graph` subcommand). Both render
targets derive from that one model, so they cannot drift (ADR-001). The model
doubles as the gate-prose-sync source: a test asserts the handshake
coherence-checklist items equal the model's gate nodes, so a gate cannot be
silently dropped from prose.

## Subcommand

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/mold.pyz gate-graph \
  [--state <state.json>] [--render dot|svg|png|mermaid] [--out <path>]
```

- `--render dot` (default): canonical Graphviz `.dot` to stdout.
- `--render mermaid`: a fenced ```mermaid flowchart block to stdout — renders
  natively in GitHub and markdown viewers, **no binary required**.
- `--render svg|png`: shells out to Graphviz `dot` when it is on PATH; pass
  `--out <path>` for binary targets. When `dot` is absent it **degrades to
  mermaid** and prints a note to stderr — run-anywhere by construction.
- `--state`: optional mold `state.json`, validated for shape; the gate model
  itself is static, so state does not change the graph today.

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
python3 ${CLAUDE_SKILL_DIR}/scripts/mold.pyz gate-graph --render dot \
  --out ${CLAUDE_SKILL_DIR}/scripts/mold.dot
```

## The non-goals gate

One coherence gate is worth calling out on its own: `non_goals_audit` (rendered
`non_goals_audit` in the `.dot`; label *Non-goals audit: every bullet traces to a
user-stated out-of-scope item or is marked [AGENT-INTRODUCED]*). Like every gate
node it feeds the handshake and is kept in lockstep with the `handshake.md`
checklist. It makes the most consequential lean — narrowing scope via `Non-goals`
— a first-class, testable gate rather than a prose-only check (ADR-002). The
audit procedure lives in `handshake.md` § Non-goals audit.
