# Curdle — artifact extraction

Curdle is the terminal state of mold. It runs only after the two-key handshake (see `handshake.md`).

## Artifact types

Resolve the spec path with `SPEC=$(python3 ${CLAUDE_SKILL_DIR}/scripts/mold.pyz artifact-path specs <slug>)` — it anchors at the per-project durable corpus (see `shared/formatting.md` § Corpus location). Issues stay repo-local: write them as `.cheese/issues/<slug>-NNN.md`.

| Type | When | Path |
| --- | --- | --- |
| **Spec** | Any meaningful design discussion | `$SPEC` (resolver output) |
| **Spec + Issues** | Side-channel actionables surfaced (out-of-scope bugs, follow-ups) | spec at `$SPEC`; issues at `.cheese/issues/<slug>-001.md`, `-002.md`, … |
| **Issues only** | Pure standalone bug tickets, no design | `.cheese/issues/<slug>-001.md`, … |

A spec is the rich container; absorbs problem framing, requirements, approach, decisions, interface sketches, risks, gates. An issue is a separate, GitHub-flavoured item the user can paste into a tracker.

## Slug rules

- Lowercase the working problem statement, drop stopwords, kebab-case, cap at 5 words.
- Honour user-passed slugs verbatim.
- Match the spec's parent slug for issues (`<slug>-001.md`, `-002.md`).

## Collisions

| Existing | Action |
| --- | --- |
| Same slug, status `draft` | Overwrite (default) or rev (`<slug>-v2`) — ask if unsure |
| Same slug, status `approved` | Default to rev; never silently overwrite |
| Existing spec, new issues for same slug | Append issues to that slug's series |

## Spec template

Cross-cutting house style and citation form: [`shared/formatting.md`](../../../shared/formatting.md). This section owns the spec shape; formatting.md owns the voice rules and the footnote primitive.

```markdown
---
slug: <slug>
status: draft
created: <YYYY-MM-DD>
confidence: <low | medium | high>
gates_overridden: []   # list of unchecked handshake items if `curdle anyway` was used
agent_introduced_scope: []   # terms in the spec the user did not type — each approved per `handshake.md` § Agent-introduced scope (audit trail; downstream skills trust this list)
entity_referent_bindings: []   # list of binding records {noun, verdict, referent, citation, note} for identity/ownership-role nouns bound to code referents or marked NEW ENTITY — each resolved per `handshake.md` § Entity-referent binding (audit trail; downstream skills trust this list)
---

# <Title>

## Problem
<one paragraph; what's broken or missing today, who feels it>

## Goals
- <bullet>

## Non-goals
- <bullet>

## Approach
<chosen option summary>

## Decisions
- <one-line decision> — <one-line rationale>

## Interface sketches
```pseudocode
<signatures, schemas, seams>
```

## Risks
- <bullet>

## Open questions
- [TBD] <question>
- [BLOCKED] <question> — <unblocker>

## Quality gates
- <runnable command>: <expected result>

## Reproduction (Diagnose only)
<failing test, curl, replay command, etc.>

## References
<one footnote definition per cited source; include only when out-of-scope evidence was cited above per `shared/formatting.md` § Citations>
```

## Issue template

```markdown
---
slug: <slug>-<NNN>
status: open
flavor: bug | chore | slice
parent_spec: <slug>
---

# <One-line summary>

## Context
<why this exists, in 1–3 sentences>

## Acceptance
- <bullet — verifiable outcome>

## Notes
- <optional caveat or pointer>
```

## ADRs (durable by-product)

After both handshake keys pass, write the session's non-obvious decisions as
durable ADRs in the same atomic step as the spec. The spec is transient; the ADRs
outlive it. The corpus is resolved **dynamically** — probe for the consumer's
`repo:<their-repo>:wiki` hallouminate corpus and write there if present, else fall
back to a tracked `docs/adr/<slug>-NNN.md`. Never hardcode a corpus name. Full
resolution rule and ADR format in [`adr.md`](adr.md).

## Atomic write

Stage to a temp directory under `${TMPDIR}` first, then move into place. Never leave partial files on a write failure.

## Hand-off

After writing, suggest the next step inline. **Never auto-invoke.**

| Artifact | Suggested next step |
| --- | --- |
| Spec | `/cook .cheese/specs/<slug>.md` |
| Issues | Paste each into your tracker, or `gh issue create --body-file <path>` |
