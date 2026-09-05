# Curdle — artifact extraction

Curdle is the terminal state of mold. It runs only after the two-key handshake (see `handshake.md`).

## Artifact types

Resolve the spec path with `SPEC=$(python3 skills/mold/scripts/mold.pyz artifact-path specs <slug>)` — it anchors at the per-project durable corpus (see `../../cheese/references/formatting.md` § Corpus location). Issues stay repo-local: write them as `.cheese/issues/<slug>-NNN.md`.

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
source: mold-handshake
created: <YYYY-MM-DD>
confidence: <low | medium | high>
gates_overridden: []   # list of unchecked handshake items if `curdle anyway` was used
agent_introduced_scope: []   # terms in the spec the user did not type — each approved per `handshake.md` § Agent-introduced scope (audit trail; downstream skills trust this list)
entity_referent_bindings: []   # list of binding records {noun, verdict, referent, citation, note} for identity/ownership-role nouns bound to code referents or marked NEW ENTITY — each resolved per `handshake.md` § Entity-referent binding (audit trail; downstream skills trust this list)
gate_applicability:
  disposition: red-required | not-applicable
  work_class: behavior | docs-only | refactor-only | test-only | appearance-only
  ui_surface: browser | non-browser | not-applicable
  reason: <required only for not-applicable>

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

## Grounding

Add exactly one row for each probe. Use `hit`, `miss`, or `unavailable` for `Outcome`.
Use `unavailable` when a probe cannot run. Record the attempted action in `Evidence`.
Do not leave `Evidence` blank. You can skip a probe, but do not assume its result.

| Probe | Outcome | Evidence |
| --- | --- | --- |
| wiki | <hit \| miss \| unavailable> | <wiki path and one-line finding, or what was attempted> |
| explorer | <hit \| miss \| unavailable> | <explorer digest path and one-line finding, or what was attempted> |

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

- AC-1: WHEN <trigger> THE SYSTEM SHALL <response>
- AC-2: WHEN <trigger> THE SYSTEM SHALL <response>

## Test Contracts

Include this entire section only when `gate_applicability.disposition` is
`red-required`. Every numbered Acceptance ID appears exactly once in this table.
`expected_failure` names a deterministic witness and expected red assertion.
`mode` is `tracer`, `contract-matrix`, or `guard`.
The seam is the outer boundary that proves the behavior.
A matrix names its ratified interface version and each unique row identity.
Separate row identities with `<br>`.
A guard or tracer leaves those cells blank.
Add one row for each criterion.

| Acceptance ID | Interface referent | Outermost stable seam | Expected failure | Mode | Interface version | Matrix rows |
| --- | --- | --- | --- | --- | --- | --- |
| AC-1 | <public interface> | <existing outer seam> | <witness and expected red assertion> | tracer | | |
| AC-2 | <public interface> | <existing outer seam> | <witness and expected red assertion> | contract-matrix | <ratified version> | <row 1><br><row 2> |

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

## Curds
<the host-validated typed CurdPlan approved at the two-key handshake>

## Reproduction (Diagnose only)
<failing test, curl, replay command, etc.>

## References
<one footnote definition per cited source; include only when out-of-scope evidence was cited above per `../../cheese/references/formatting.md` § Citations>
```

`source: mold-handshake` marks the strict Mold production path. Every new
behavior declaration must set `ui_surface` to `browser` or `non-browser`;
closed non-behavior declarations, including `appearance-only`, set it to
`not-applicable`. A browser declaration is valid only when every Test Contract
names an existing browser/E2E interface and outer seam.

Specs without this provenance marker are v0.13-era legacy and stay
**readable forever**: `validate-spec` accepts them, waiving only the two parts
the hardened format added after v0.13 — the `Test Contracts` section and the
`gate_applicability` block — and printing a one-line `NOTICE:` rather than an
error. Everything a v0.13 spec did carry is still validated. Minting is the
mirror image: Curdle writes only the template above and gates it with
`validate-spec --strict`, which enforces the hardened format *and* the
`source:` marker unconditionally. Legacy is a read-side grace, never a
write-side option. The policy lives once in
`src/easy_cheese_schemas/spec_format.py` so every release channel inherits it.

### Current mold-spec schema (generated)

The `mold-spec` document contract enforced by `validate-spec` (`shape-check.md`), refreshed by `scripts/render_generated_regions.py` from the `MoldSpecDocument` model in `src/easy_cheese_schemas/contracts.py`. Do not hand-edit the generated region.

<!-- BEGIN GENERATED: mold-spec-schema -->
document mold-spec {
  section "Problem"
  section "Goals"
  section "Non-goals"
  section "Deferred follow-ups"?
  section "Grounding" {
    columns: ['Probe', 'Outcome', 'Evidence']
    per_row: ['Probe and Outcome are drawn from their closed sets', 'Evidence is non-empty, including for unavailable outcomes']
  }
  section "Approach"
  section "Decisions"
  section "Acceptance"
  section "Test Contracts"? {
    columns: ['Acceptance ID', 'Interface referent', 'Outermost stable seam', 'Expected failure', 'Mode', 'Interface version', 'Matrix rows']
    per_row: ['tracer rows leave Interface version and Matrix rows blank', 'contract-matrix rows require both Interface version and Matrix rows']
  }
  section "Interface sketches"
  section "Risks"
  section "Open questions"
  section "Quality gates"
  section "Curds"
  section "Reproduction"?
  section "References"?
}

rule ac-coverage-exactly-once: "Every Acceptance ID must appear exactly once in the Test Contracts table."
rule tracer-row-blank-matrix-cells: "Tracer rows must leave Interface version and Matrix rows blank."
rule contract-matrix-row-requires-both: "Contract-matrix rows require both Interface version and Matrix rows."
rule grounding-probe-recorded: "The Grounding table must record the wiki probe exactly once with non-empty evidence."
rule delegation-digest-recorded: "The Grounding table must record the explorer probe exactly once with non-empty evidence."
rule not-applicable-closed-class: "red-required requires Test Contracts; not-applicable forbids them and requires a reason."

type GateApplicability {
  disposition GateApplicabilityDisposition
  work_class WorkClass
  ui_surface UiSurface
  reason? str | None = None
}

type GroundingRow {
  probe GroundingProbe
  outcome GroundingOutcome
  evidence str
}

type MoldSpecDocument {
  frontmatter MoldSpecFrontmatter
  acceptance_ids? tuple[str, ...] = ()
  test_contract_rows? tuple[TestContractRow, ...] = ()
  grounding_rows? tuple[GroundingRow, ...] = ()
}

type MoldSpecFrontmatter {
  slug str
  status str
  source str
  created str
  confidence SpecConfidence
  gate_applicability GateApplicability
  gates_overridden? tuple[str, ...] = ()
  agent_introduced_scope? tuple[str, ...] = ()
  entity_referent_bindings? tuple[Mapping[str, object], ...] = ()
}

type TestContractRow {
  acceptance_id str
  interface_referent str
  outermost_stable_seam str
  expected_failure str
  mode TestContractMode
  interface_version? str = ''
  matrix_rows? tuple[str, ...] = ()
}

enum GateApplicabilityDisposition = "red-required" | "not-applicable"

enum GroundingOutcome = "hit" | "miss" | "unavailable"

enum GroundingProbe = "wiki" | "explorer"

enum SpecConfidence = "low" | "medium" | "high"

enum TestContractMode = "tracer" | "contract-matrix" | "guard"

enum UiSurface = "browser" | "non-browser" | "not-applicable"

enum WorkClass = "behavior" | "docs-only" | "refactor-only" | "test-only" | "appearance-only"
<!-- END GENERATED -->

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
- AC-1: <bullet — verifiable outcome>

## Notes
- <optional caveat or pointer>
```

## Two-phase Curdle for accepted follow-ups

Accepted follow-ups use a local-first two-phase Curdle. Each receives a deterministic follow-up ID composed from the spec slug and its one-based ordinal, for example `mold-follow-up-routing-F001`.

### Phase one — local write-ahead state

Preserve every existing Curdle by-product: the spec, ADRs, glossary, domain model, and all rejected-direction records. Add a local issue draft for each accepted follow-up that needs a recoverable tracker payload. Before any external call, persist its ID, destination, `prepared` state, and draft reference in `Deferred follow-ups`.

`$SPEC` is the authoritative store for prepared follow-up state because the resolver anchors it in the durable project corpus. Local issue drafts are auxiliary publication payloads, not the authoritative record. Stage and move this complete local set under the existing atomic-write rule before phase two begins.

### Phase two — external publication and reconciliation

Only units whose approved action is **create/link now** and whose destination is external enter phase two. A local issue draft destination completes as `prepared` in phase one:

- For GitHub Issues, use the host GitHub capability first and `gh` as the portable fallback. Discover repository labels and issue forms instead of assuming them.
- For roadmap goals, run the owned `/wiki-roadmap` workflow when that skill and its required capability are available. New roadmap creation and extension remain owned by that workflow.
- Put the deterministic follow-up ID in every published item. On every retry, search for the exact deterministic follow-up ID before creation. If an exact match exists, link it. You SHALL NOT create a duplicate.
- A reused external item becomes `linked`; a newly published item becomes `created`. Reconcile that state and the final URL or durable roadmap reference into `Deferred follow-ups`.
- When a capability is unavailable or publication fails, retain the recovery draft. Keep the follow-up prepared. Report the failed action and retry path. Continue without blocking the approved spec.

Finish roadmap publication and all mechanical spec reconciliation before the implementation handoff. Reconciliation records the already-approved result; it does not reopen the design.

## ADRs (durable by-product)

After both handshake keys pass, write the session's non-obvious decisions as durable ADRs. Include them with the durable spec in phase one's local atomic write. Both remain in the durable project corpus. The spec is the approved implementation contract. ADRs preserve its rationale. Resolve the corpus **dynamically**. Probe for the consumer's `repo:<their-repo>:wiki` hallouminate corpus. Write there if present. Otherwise, use a tracked `docs/adr/<slug>-NNN.md`. Never hardcode a corpus name. See [`adr.md`](adr.md) for the full resolution rule and ADR format.

## Durable glossary (by-product)

Write resolved canonical terms to `.cheese/glossary/<slug>.md` in the same atomic step as the spec and ADRs. Downstream skills (`/cook`, `/age`, `/press`) read this file for naming consistency. The glossary is the output of the Ground phase's term resolution; it is not reconstructed from the spec.

Format:
```markdown
# Glossary — <slug>

| Term | Canonical meaning | Code referent (file:line or NEW ENTITY) | Avoid |
| --- | --- | --- | --- |
| <term> | <one-line definition> | <referent> | <losing synonym, …> |
```

The `Avoid` column records losing synonyms that the Ground phase rejected in favour of the canonical term. Separate multiple synonyms with commas. Use `—` when none exist. Omit the file if Ground resolved no terms and no overloaded-term dialogue occurred.

## Domain model (cumulative by-product)

During the same atomic step as the spec, ADRs, and per-slug glossary, merge the session's resolved terms with their **Avoid synonyms**. Merge them into the project-level domain model. Resolve it with `domain_model_target()` (`src/easy_cheese/shared/paths.py`). The per-slug glossary is a branch-local handoff. The domain model is cumulative cross-session memory. It builds the project's ubiquitous language across every session. Add only context-specific terms. Never add general programming concepts.

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

Write the rejection to `.cheese/.out-of-scope/<slug>-NNN.md` when the agent-introduced-scope audit **rejects a direction**. Do the same when the two-key handshake rejects it. Rejections include "drop <term>" for an approach or design knob, and "not that approach." An explicit deferral becomes a follow-up candidate. A rejected direction is not a follow-up candidate.

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

`/cheese` consults this store before it proposes a direction again. See `skills/cheese/SKILL.md` § Rejected-directions check. Do not write ordinary scope boundaries or accepted follow-ups here. Non-goal-only dispositions create no artifact. Accepted follow-ups use `Deferred follow-ups` and any auxiliary `.cheese/issues/` recovery draft. Write only direction-level rejections. These include approaches, design knobs, and named features that the user explicitly declined. Note: this store uses the dot-prefixed path `.out-of-scope`. Its sibling stores, `glossary/`, `issues/`, and `specs/`, do not use dot prefixes. Each scan must explicitly target the dotted path. A bare `.cheese/*` glob does not match it.

## Spec-verify pass (optional)

Before the hand-off, run `/spec-verify` as an independent spec-review pass if the harness provides it. If it is absent, skip it without warning and note the absence once. This pass is optional. It must not block curdle where the environment does not bundle the skill. Never create a hard dependency on it.

Detect the skill at the instruction level, not in code. Check whether `/spec-verify` appears in the agent's available toolset. Use the pattern in `../../cheese/references/optional-plugins.md` § Probe pattern. Do not use `command -v` or another shell probe. `/spec-verify` is a skill, not a `$PATH` executable.

## Atomic write

Stage to a temp directory under `${TMPDIR}` first, then move into place. Never leave partial files on a write failure.

### Write → read-back → completion record

This is the runtime home of the **Durable writes** coherence gate (`handshake.md` § Agent key). The gate locks the commitment before the handshake; this step honours it. For each durable write — every ADR and the domain-model merge — run:

1. **Resolve** the target dynamically. For the ADR, use the resolution procedure in [`adr.md`](adr.md) § Resolution. For the model, use `domain_model_target()` in `src/easy_cheese/shared/paths.py`. Both return `(backend, location)`. `domain_model_target()` also returns `wiki_reachable` as a third element. `False` means that the wiki probe was not consulted because no hook existed or the hook raised. Thus, its `file` backend is a degraded fallback, not a confirmed absence. This condition triggers the loud fallback below.
2. **Write** to that target: `add_markdown` when the backend is `hallouminate`, a staged file write when it is `file`.
3. **Read back** the entry and confirm that it exists. For the wiki backend, use `ground` or `read_markdown`. For the file backend, read the file again. Treat a write that you cannot read back as a failure. Fail loudly, and do not claim the write.
4. **Record** it in the curdle completion record printed to the user: one line per durable write naming `<artifact> → <location> (<backend>)`.

**Loud fallback.** If hallouminate is unavailable and the resolver degrades to a file backend, state this in one visible line. File backends include `docs/adr/…`, `docs/domain-model*`, and the XDG corpus. Never write silently to files when the author expected the wiki. See the absent-plugin degrade contract in [`../../cheese/references/optional-plugins.md`](../../cheese/references/optional-plugins.md).

## Pre-approval typed planner dispatch

Before this procedure, run the digest-bound fresh-context fork taste test on the dialogue-state draft. It must pass; failures reopen only named forks, with two correction rounds. Then run the procedure on the draft before the two-key handshake. It prepares the typed plan that the handshake approves; Curdle later persists the host-validated artifacts.

1. **Dispatch** a fresh-context planner on a `PlannerRequest` built from the current draft spec text. The planner returns a `PlannerResultWriterView`; it does not own contract versions, identifiers, digests, lineage, or evidence references.
2. **Validate and normalize** the writer view on the host. The normal selected path is the typed `PlannerResult` containing a typed `CurdPlan`; reject malformed or wrong-kind output before approval.
3. **Still invalid after one retry** — stop before the two-key handshake. Do not approve or persist an invalid plan.
4. **On success**, count semantic curds and waves from the typed `CurdPlan`, then show `N curds / M waves` with the final approval request. The typed plan is part of what both handshake keys approve.
5. **During Curdle phase one**, persist the approved spec, typed `PlannerResult`, and typed `CurdPlan`. Put them after `## Quality gates` or the natural equivalent section for this spec's shape. Do not regenerate or mutate them after approval.

The legacy `CurdBlock`/`Decomposition` projection is not the normal path. Use it only when an explicit migration consumer requests it; the projection must be lossless or return `UnsupportedProjection`. Never invoke the legacy curd-block decomposer or persist its block as the selected production artifact.

## Hand-off

Do not render this hand-off until phase-two publication attempts and the mechanical `Deferred follow-ups` reconciliation are complete.
After writing, suggest the next step inline. **Never auto-invoke.**

| Artifact | Suggested next step |
| --- | --- |
| Red-required Spec | `/cook --auto <durable spec pointer>` (preserve gate and taste metadata) |
| Spec | `/cook <spec-path>` |
| Issues | Paste each into your tracker, or `gh issue create --body-file <path>` |
