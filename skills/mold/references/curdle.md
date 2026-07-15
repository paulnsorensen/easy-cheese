# Curdle — artifact extraction

Curdle is the terminal state of mold. It runs only after the two-key handshake (see `handshake.md`).

## Artifact types

Resolve the spec path with `SPEC=$(python3 ${CLAUDE_SKILL_DIR}/scripts/mold.pyz artifact-path specs <slug>)` — it anchors at the per-project durable corpus (see `../../cheese/references/formatting.md` § Corpus location). Issues stay repo-local: write them as `.cheese/issues/<slug>-NNN.md`.

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

Cross-cutting house style and citation form: [`formatting.md`](../../cheese/references/formatting.md). This section owns the spec shape; formatting.md owns the voice rules and the footnote primitive.

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
- _Minor decisions:_ <one line capturing the `[AGENT-DECIDED]` calls the user did not veto — the per-round ledger's minor tier; major decisions get full ADRs per `adr.md`>

## Acceptance

Write acceptance criteria in **EARS form** by default:
```
WHEN <trigger> THE SYSTEM SHALL <response>
```
If the trigger cannot be stated precisely (e.g. pure internal utilities with no external event), use prose with a `[prose-fallback]` marker.

- WHEN <trigger> THE SYSTEM SHALL <response>
- WHEN <trigger> THE SYSTEM SHALL <response>

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
<one footnote definition per cited source; include only when out-of-scope evidence was cited above per `../../cheese/references/formatting.md` § Citations>
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

## Durable glossary (by-product)

Write resolved canonical terms to `.cheese/glossary/<slug>.md` in the same atomic step as the spec and ADRs. Downstream skills (`/cook`, `/age`, `/press`) read this file for naming consistency. The glossary is the output of the Ground phase's term resolution; it is not reconstructed from the spec.

Format:
```markdown
# Glossary — <slug>

| Term | Canonical meaning | Code referent (file:line or NEW ENTITY) | Avoid |
| --- | --- | --- | --- |
| <term> | <one-line definition> | <referent> | <losing synonym, …> |
```

The `Avoid` column records the losing synonyms the Ground phase rejected in favour of the canonical term (comma-separated, or `—` when none). Omit the file if no terms were resolved during Ground (no overloaded-term dialogue occurred).

## Domain model (cumulative by-product)

In the same atomic step as the spec, ADRs, and per-slug glossary, merge the session's resolved terms — **with their Avoid synonyms** — into the project-level domain model resolved via `domain_model_target()` (`shared/scripts/paths.py`). Unlike the per-slug glossary (a branch-local handoff), the domain model is cumulative cross-session memory: it builds the project's ubiquitous language across every session. Context-specific terms only; general programming concepts never enter.

Merge, don't overwrite:
- **New term** — append an entry.
- **Changed term** (definition, referent, or Avoid set differs) — update that entry in place.

Entry format:
```markdown
**<Term>** — <definition>.
_Avoid_: <syn1>, <syn2>
_Code_: <file:line (or NEW ENTITY)>
```
Omit the `_Avoid_` line when no synonyms were rejected.

**Lazy context-map split.** A single bounded context lives as one `domain-model.md` at the store root. When a **second** bounded context crystallises, split lazily into:
- `domain-model/index.md` — the context map: the bounded contexts and their relationships (Pocock CONTEXT-MAP shape).
- `domain-model/<context>.md` — one page per bounded context, each holding that context's entries.

Do not pre-split for a single context. This layout is identical across all three stores `domain_model_target()` may resolve to (wiki, `docs/`, XDG corpus).

## Rejected-directions store (by-product)

When the agent-introduced-scope audit or the two-key handshake explicitly **rejects a direction** (the user says "drop <term>" for an approach or design knob, or "not that approach"), write the rejection to `.cheese/.out-of-scope/<slug>-NNN.md`. Deferrals ("make X a follow-up") are not direction rejections — route those to `.cheese/issues/`.

Format:
```markdown
# Rejected direction — <slug>-<NNN>

## Direction
<one-line description of what was rejected>

## Rationale
<why it was rejected, in 1–2 sentences>

## Context
Session: <slug>; rejected at: <handshake | scope-audit>
```

This store is consulted by `/cheese` before re-proposing a direction (see `skills/cheese/SKILL.md` § Rejected-directions check). Do not write to this store for normal out-of-scope bugs or follow-ups (those go to `.cheese/issues/`); write only for **direction-level** rejections (approaches, design knobs, named features the user explicitly declined). Note: this store is dot-prefixed (`.out-of-scope`) while its sibling stores (`glossary/`, `issues/`, `specs/`) are not — any scan must target the dotted path explicitly; a bare `.cheese/*` glob will not match it.

## Spec-verify pass (optional)

Before the hand-off, if the `/spec-verify` skill is available in the harness, run it as an independent spec-review pass. If absent, skip silently and note once — this pass is optional and must not block curdle in environments where the skill is not bundled. Never hard-depend on it.

Detection is instruction-level, not code: check whether `/spec-verify` appears in the agent's available toolset (the same pattern as `../../cheese/references/optional-plugins.md` § Probe pattern). Do not use `command -v` or any shell probe — `/spec-verify` is a skill, not a `$PATH` executable.

## Atomic write

Stage to a temp directory under `${TMPDIR}` first, then move into place. Never leave partial files on a write failure.

### Write → read-back → completion record

This is the runtime home of the **Durable writes** coherence gate (`handshake.md` § Agent key). The gate locks the commitment before the handshake; this step honours it. For each durable write — every ADR and the domain-model merge — run:

1. **Resolve** the target dynamically — the ADR resolution procedure in [`adr.md`](adr.md) § Resolution for ADRs, the `domain_model_target()` function (`shared/scripts/paths.py`) for the model. Both yield `(backend, location)`.
2. **Write** to that target: `add_markdown` when the backend is `hallouminate`, a staged file write when it is `file`.
3. **Read back** and confirm the entry landed: `ground` / `read_markdown` for the wiki backend, a re-read of the file for the file backend. A write that cannot be read back is a failure — fail loud, do not claim the write.
4. **Record** it in the curdle completion record printed to the user: one line per durable write naming `<artifact> → <location> (<backend>)`.

**Loud fallback.** When hallouminate is unavailable and the resolver degrades to a file backend (`docs/adr/…`, `docs/domain-model*`, or the XDG corpus), say so in one visible line — never let a write silently go to files when the author expected the wiki. Absent-plugin degrade contract: [`../../cheese/references/optional-plugins.md`](../../cheese/references/optional-plugins.md).

## Hand-off

After writing, suggest the next step inline. **Never auto-invoke.**

| Artifact | Suggested next step |
| --- | --- |
| Spec | `/cook .cheese/specs/<slug>.md` |
| Issues | Paste each into your tracker, or `gh issue create --body-file <path>` |
