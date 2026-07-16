# Curdle — artifact extraction

Curdle is the terminal state of mold. It runs only after the two-key handshake (see `handshake.md`).

## Artifact types

Resolve the spec path with `SPEC=$(python3 ${CLAUDE_SKILL_DIR}/scripts/mold.pyz artifact-path specs <slug>)` — it anchors at the per-project durable corpus (see `../../cheese/references/formatting.md` § Corpus location). Issues stay repo-local: write them as `.cheese/issues/<slug>-NNN.md`.

| Type | When | Path |
| --- | --- | --- |
| **Spec** | Any meaningful design discussion | `$SPEC` (resolver output) |
| **Spec + Issues** | Accepted follow-ups whose disposition calls for local recovery or tracker payload | spec at `$SPEC`; issues at `.cheese/issues/<slug>-001.md`, `-002.md`, … |
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

## Deferred follow-ups
- **<deterministic follow-up ID>** — <summary>
  - Destination: <github_issue | roadmap_goal | local_draft>
  - State: <prepared | linked | created>
  - Reference: <local draft path | URL | durable roadmap reference>

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

## Two-phase Curdle for accepted follow-ups

Accepted follow-ups use a local-first two-phase Curdle. Each receives a deterministic follow-up ID composed from the spec slug and its one-based ordinal, for example `mold-follow-up-routing-F001`.

### Phase one — local write-ahead state

Preserve every existing Curdle by-product: the spec, ADRs, glossary, domain model, and any rejected-direction records. Add a local issue draft for each accepted follow-up that needs recoverable tracker payload, then persist its ID, destination, `prepared` state, and draft reference in `Deferred follow-ups` before any external call.

`$SPEC` is the authoritative store for prepared follow-up state because the resolver anchors it in the durable project corpus. Local issue drafts are auxiliary publication payloads, not the authoritative record. Stage and move this complete local set under the existing atomic-write rule before phase two begins.

### Phase two — external publication and reconciliation

Only units whose approved action is **create/link now** and whose destination is external enter phase two. A local issue draft destination completes as `prepared` in phase one:

- For GitHub Issues, use the host GitHub capability first and `gh` as the portable fallback. Discover repository labels and issue forms instead of assuming them.
- For roadmap goals, run the owned `/wiki-roadmap` workflow when that skill and its required capability are available. New roadmap creation and extension remain owned by that workflow.
- Put the deterministic follow-up ID in every published item. On every retry, search the exact deterministic follow-up ID before creation; when an exact match exists, link it and SHALL NOT create a duplicate.
- A reused external item becomes `linked`; a newly published item becomes `created`. Reconcile that state and the final URL or durable roadmap reference into `Deferred follow-ups`.
- When a capability is unavailable or publication fails, retain the recovery draft, keep the follow-up prepared, report the failed action and retry path, and continue without blocking the approved spec.

Finish roadmap publication and all mechanical spec reconciliation before the implementation handoff. Reconciliation records the already-approved result; it does not reopen the design.

## ADRs (durable by-product)

After both handshake keys pass, write the session's non-obvious decisions as durable ADRs in phase one's local atomic write with the durable spec. Both remain in the durable project corpus: the spec is the approved implementation contract, while ADRs preserve the rationale behind it. The corpus is resolved **dynamically** — probe for the consumer's `repo:<their-repo>:wiki` hallouminate corpus and write there if present, else fall back to a tracked `docs/adr/<slug>-NNN.md`. Never hardcode a corpus name. Full resolution rule and ADR format in [`adr.md`](adr.md).

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

When the agent-introduced-scope audit or the two-key handshake explicitly **rejects a direction** (the user says "drop <term>" for an approach or design knob, or "not that approach"), write the rejection to `.cheese/.out-of-scope/<slug>-NNN.md`. An explicit deferral becomes a follow-up candidate; a rejected direction is not a follow-up candidate.

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

This store is consulted by `/cheese` before re-proposing a direction (see `skills/cheese/SKILL.md` § Rejected-directions check). Do not write ordinary scope boundaries or accepted follow-ups here: non-goal-only dispositions create no artifact, while accepted follow-ups use `Deferred follow-ups` plus any auxiliary `.cheese/issues/` recovery draft. Write only direction-level rejections (approaches, design knobs, named features the user explicitly declined). Note: this store is dot-prefixed (`.out-of-scope`) while its sibling stores (`glossary/`, `issues/`, `specs/`) are not — any scan must target the dotted path explicitly; a bare `.cheese/*` glob will not match it.

## Spec-verify pass (optional)

Before the hand-off, if the `/spec-verify` skill is available in the harness, run it as an independent spec-review pass. If absent, skip silently and note once — this pass is optional and must not block curdle in environments where the skill is not bundled. Never hard-depend on it.

Detection is instruction-level, not code: check whether `/spec-verify` appears in the agent's available toolset (the same pattern as `../../cheese/references/optional-plugins.md` § Probe pattern). Do not use `command -v` or any shell probe — `/spec-verify` is a skill, not a `$PATH` executable.

## Atomic write

Stage to a temp directory under `${TMPDIR}` first, then move into place. Never leave partial files on a write failure.

## Hand-off

Do not render this hand-off until phase-two publication attempts and the mechanical `Deferred follow-ups` reconciliation are complete.
After writing, suggest the next step inline. **Never auto-invoke.**

| Artifact | Suggested next step |
| --- | --- |
| Spec | `/cook <spec-path>` |
| Issues | Paste each into your tracker, or `gh issue create --body-file <path>` |
