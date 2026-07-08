# The Prototype Cycle

An escape hatch for design questions that can't be settled by reasoning, search,
or doc-reading — only by *trying it*. Spawnable at any point in the dialogue, in
parallel with a Validate Cycle. Mold owns the parent dialogue; the sub-agent owns
the throwaway. The code is discarded; the answer is the keeper.

Use it when a question is **ungrillable**: an API's real behaviour, whether two
libraries compose, the actual shape of an error, an ergonomics call that only a
running sketch can answer. Do not use it for questions a `cheez-search` /
`cheez-read` / Validate Cycle already settles — those are cheaper.

## The frame

Always announce the cycle before dispatching — the announcement is the discipline.

```text
Launching a prototype cycle on question: "<ungrillable design unknown>"

Plan:
  spawn sub-agent(isolation: "worktree")   # degrade to a temp dir if the repo is not git
    build a throwaway (may try several variations)
  digest ← { question, answer, snippet?, confidence }   # <=2 KB; no code dumped
  discard the worktree                      # the answer is the keeper, never the code
  log state.prototype_cycles[] ; optionally emit an ADR (adr.md)
```

**1 cycle == 1 design question resolved**, not 1 per variation. The sub-agent may
try several throwaways internally; that is still one cycle.

## What the sub-agent returns

A digest, never a code dump (sub-agent split + digest size live in the shared
kernel at `../../age/references/sub-agent-gate.md`):

| Field | Content |
| --- | --- |
| `question` | the design unknown, restated |
| `answer` | the resolved behaviour, in one or two sentences |
| `snippet?` | the minimal decision-encoding fragment, only if it captures the answer better than prose |
| `confidence` | `certain \| speculating \| don't know` |

The worktree is discarded after the digest is extracted. Nothing from the
throwaway tree is committed, copied back, or referenced by path — if a fragment
matters, it lives in the digest `snippet`.

## Isolation and degrade

- Default: `isolation: "worktree"` — a hermetic git worktree, auto-cleaned.
- The repo is not a git repo: degrade to a temp directory under `${TMPDIR}`,
  say so out loud, and clean it up after extraction.
- Harness lacks sub-agent spawning: run the throwaway inline in a scratch dir,
  note the loss of isolation, and still discard it.

## Budget

Prototype cycles are **context-bounded, not capped** (ADR-003). Run as many as
confidence needs; the 120k/140k context-budget mechanic
(`context-budget.md`) is the natural limiter. A **soft backstop of 10**
prompts a single "still gathering — continue?" check; it is not a hard stop and
the user can wave it through.

## Logging

Every launched cycle is logged in the mold state file:

```yaml
prototype_cycles:
  - id: pc-1
    question: "Does library X's streaming API surface backpressure?"
    answer: "Yes — it yields when the consumer is slow; no manual pause needed."
    confidence: certain
    adr: ADR-002   # optional, when the answer encodes a non-obvious decision
```

An open cycle (no `answer:`) blocks Curdle until it settles or the user accepts
it as `[TBD]`, exactly like a Validate Cycle.
