# Curdle — artifact extraction

Curdle is the terminal state of mold. It runs only after the two-key handshake (see `handshake.md`).

## Artifact types

Resolve the spec path with `SPEC=$(python3 ${CLAUDE_SKILL_DIR}/scripts/mold.pyz artifact-path specs <slug>)` — it anchors at the per-project durable corpus (see `shared/formatting.md` § Corpus location). Issues stay repo-local: write them as `.cheese/issues/<slug>-NNN.md`.

| Type | When | Path |
| --- | --- | --- |
| **Spec** | Any meaningful design discussion | `$SPEC` (resolver output) |
| **Spec + Issues** | Side-channel actionables surfaced (out-of-scope bugs, follow-ups) | spec at `$SPEC`; issues at `.cheese/issues/<slug>-001.md`, `-002.md`, … |
| **Issues only** | Pure standalone bug tickets, no design | `.cheese/issues/<slug>-001.md`, … |
| **Domain docs** | Glossary terms or ADR-worthy decisions surfaced during the dialogue | `CONTEXT.md` (root or per-context); ADRs at `docs/adr/NNNN-slug.md` — see `domain-docs.md` |

A spec is the rich container; absorbs problem framing, requirements, approach, decisions, interface sketches, risks, gates. An issue is a separate, GitHub-flavoured item the user can paste into a tracker. Domain docs are durable, repo-local, and accompany a spec rather than replacing it.

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

## Domain docs

If the dialogue accumulated `glossary_terms` or `adr_candidates` in the state ledger (see `domain-docs.md`), flush them here — at curdle, after the handshake, never mid-dialogue.

- **CONTEXT.md** — write resolved terms to the glossary. Single-context: root `CONTEXT.md`. Multi-context (`CONTEXT-MAP.md` present): the matching context's `CONTEXT.md`. Create lazily — only the file the first approved term needs. Format in `context-format.md`.
- **CONTEXT-MAP.md** — scaffold only when the user is genuinely working across multiple bounded contexts. Format in `context-format.md`.
- **ADRs** — one file per candidate that cleared all three criteria, at `docs/adr/NNNN-slug.md` (number = highest existing + 1; per-context `docs/adr/` in multi-context repos). Format in `adr-format.md`.

These are durable repo artifacts but not part of the durable-corpus resolver — write them at their literal repo paths, not through `artifact-path`. They are not pre-formed curds: a glossary update accompanies a spec, it does not split it, so they do not count toward `candidate_curds` in the handoff.

## Atomic write

Stage to a temp directory under `${TMPDIR}` first, then move into place. Never leave partial files on a write failure. The same applies to domain docs — an interrupted glossary write must not corrupt an existing `CONTEXT.md`.

## Hand-off

After writing, suggest the next step inline. **Never auto-invoke.**

| Artifact | Suggested next step |
| --- | --- |
| Spec | `/cook .cheese/specs/<slug>.md` |
| Issues | Paste each into your tracker, or `gh issue create --body-file <path>` |
