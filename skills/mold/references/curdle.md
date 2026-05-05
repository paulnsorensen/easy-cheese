# Curdle — artifact extraction

Curdle is the terminal state of mold. It runs only after the two-key handshake (see `handshake.md`).

## Artifact types

| Type | When | Path |
| --- | --- | --- |
| **Spec** | Any meaningful design discussion | `.cheese/specs/<slug>.md` |
| **Spec + Issues** | Side-channel actionables surfaced (out-of-scope bugs, follow-ups) | spec at `.cheese/specs/<slug>.md`; issues at `.cheese/issues/<slug>-001.md`, `-002.md`, … |
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

```markdown
---
slug: <slug>
status: draft
created: <YYYY-MM-DD>
confidence: <low | medium | high>
gates_overridden: []   # list of unchecked handshake items if `curdle anyway` was used
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

## Atomic write

Stage to a temp directory under `${TMPDIR}` first, then move into place. Never leave partial files on a write failure.

## Hand-off

After writing, suggest the next step inline. **Never auto-invoke.**

| Artifact | Suggested next step |
| --- | --- |
| Spec | `/cook .cheese/specs/<slug>.md` |
| Issues | Paste each into your tracker, or `gh issue create --body-file <path>` |
