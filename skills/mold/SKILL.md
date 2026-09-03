---
name: mold
description: Turn a fuzzy idea or half-formed feature into an approved spec through iterative, grounded design dialogue. Use it when the user has a fuzzy idea or design direction. Typical phrases include "let's design X", "I'm thinking about Y", and "what should the API for Z look like". Other phrases include "shape this into a spec", "what would it take to build/set up X", "I want to add a feature that…", and "/mold". Use it when users are "just thinking out loud" but want the dialogue to produce a written artifact. Do NOT use it for free-form discussion without artifact intent (`/culture`). Do NOT use it for direct implementation (`/cook`) or research-only questions (`/briesearch`).
license: MIT
metadata: {dispatches-agents: true}
---

# /mold

Two modes, by analogy to `/culture`:

1. **User-invoked full ceremony (default).** The user typed `/mold` (or `/cheese` routed an explicit fuzzy-design ask straight here). Runs the full Explore/Ground/Shape/Sketch/Grill/Diagnose dialogue and the two-key handshake before any spec is written; the Flow below describes it.
2. **Agent-invoked mini-spec mode.** At tier 1 of its escalation, `/cheese` calls `/mold` when all cook fast-path checks pass. See `skills/cheese/SKILL.md` § Escalation. The spec must materialise before the gate-applicability route runs. No dialogue occurs. No handshake occurs. See `## Agent-invoked mini-spec mode` below.

## Flow

1. **Bounds pass** — map every input's goals and **non-goals** before routing; ask the user rather than assume. Open the `Decided / Asking / [AGENT-DECIDED]` ledger. Clear work gets one fast confirm; full-spec work gets an upgrade-tier warning.
2. **Route** — choose the secondary mode from `references/modes.md`, announce it, and correct false premises first.
3. **Dialogue** — consequential forks are the user's to pick. Supply options, trade-offs, and evidence before asking; ground critical claims through code, the [Validate Cycle](references/validate-cycle.md), or a [Prototype Cycle](references/prototype-cycle.md). Resolve contradictions and render the decision map after three consecutive fork questions or on request.
4. **Sketch** — For work across modules or with a new public interface, run `references/shape-check.md`. Bind identity and role nouns to code referents. Lock seams as pseudocode signatures.
5. **Plan for approval** — First, run the fresh-context fork-coherence taste test with `mold.pyz taste-test`. Persist its digest-bound pass. A failure reopens only named forks. Stop after the third failed verdict. Only then, dispatch a typed `PlannerRequest`. Validate its `PlannerResultWriterView`. Retry an invalid result once. If it remains invalid, stop before the handshake. Normalize the valid result on the host. Persist only the typed `PlannerResult` and `CurdPlan` artifacts. The legacy `CurdBlock`/`Decomposition` projection supports migration only. Request it explicitly. Require a lossless projection or `UnsupportedProjection`. At the handshake, present the typed plan's semantic curds and waves. See `references/curdle.md` § "Pre-approval typed planner dispatch".
6. **Two-key handshake** — Before extraction, the user and agent must agree to the draft spec and displayed typed plan. The user provides an explicit verb. The agent performs a coherence self-check. Neither key changes nor disappears. See `references/handshake.md`.
7. **Curdle** — Resolve the durable spec path with `SPEC=$(python3 skills/mold/scripts/mold.pyz artifact-path specs <slug>)`. Before any external call, phase one writes the local artifact and write-ahead prepared state. It writes the approved spec at `"$SPEC"` and the host-validated `PlannerResult` and `CurdPlan`. It also writes local issue drafts and the session's non-obvious decisions as durable ADRs. Phase two publishes approved follow-ups. If an external capability is unavailable or publication fails, retain the prepared recovery state. Phase two reconciles their state and references into the durable spec before any handoff.
8. **Count and hand off** — after reconciliation, run [`mold.pyz curd-count`](references/curd-count.md), then prompt via `## Handoff`; dispatch only the user's non-stop selection.

Portability: [`../cheese/references/harness-portability.md`](../cheese/references/harness-portability.md). Prefer bundled/repo-local helpers; slash commands are host renderings, not the control model.

## Follow-up candidates

Every non-goal and explicit dialogue deferral becomes a `[FOLLOW-UP?]` follow-up candidate. Dispose of the set before the two-key handshake; details: `references/handshake.md` § Follow-up disposition.

## Modes

| Mode | Use when | Goal |
| --- | --- | --- |
| Explore | The idea is vague | Identify the real problem and pain point |
| Ground | A file, bug, or existing doc is named | Verify facts against evidence |
| Shape | The goal is known but approach is open | Compare viable options (Do Nothing always included) |
| Sketch | Interfaces or module boundaries matter | Lock responsibilities and seams |
| Grill | A favoured approach needs stress-testing | Steelman each item, then put every design-changing call to the user as a fork |
| Diagnose | A symptom, failure, or trace is supplied | Build a Loop → reproduce → hypothesize → confirm root cause |

Full mode definitions, exit criteria, and user knobs: `references/modes.md`. Trigger and trace evals, including the Grill user-fork checks: `references/evals.md`.

## Agent-invoked mini-spec mode

`/cheese`'s tier-1 escalation calls `/mold` after the call site passes all cook fast-path checks. It produces a spec without user-facing dialogue. This mode skips the Flow above entirely. Derive a slug. Write the mini-spec. Parse its declared gate applicability. Return the resolved spec path with `/cook --auto <spec-path>`.

The two-key handshake does not run in this mode. The agent-introduced-scope check still runs implicitly. Every distinguishing noun in the mini-spec must come from the user's input or tier-2 `/culture`/`/briesearch` synthesis. Never add one silently.

Full procedure, the mini-spec schema, and the `## Provenance` rules: `references/mini-spec-mode.md`.

## Preferred tools and fallbacks

Call source-code search, read, and edit backends directly according to [`code-intelligence-routing.md`](../cheese/references/code-intelligence-routing.md). Shape checks use semantic caller search plus dependency context; procedure: `references/shape-check.md`.

Beyond source-code routing there are mold-specific tools:

| Need | Prefer | Fallback |
| --- | --- | --- |
| External validation | `/briesearch` with Context7/Tavily | user-provided docs, repo docs, or note as unverified |
| Wiki grounding (Ground entry + decision points; scope per `references/grounding.md` § When to probe) | `mcp__hallouminate__list_corpora` + `mcp__hallouminate__ground` on `repo:<repo>:wiki` | record `hallouminate: absent` in the ledger, proceed on code evidence, and cap at `speculating` when design rationale is central |

**The grounding record is a precondition for the first structured question.** Do not ask the question until the ledger contains a probe result. The result contains citations or `hallouminate: absent`. This fallback keeps the evidence visible. Mark each unsupported claim `[?]` until you settle it.

## Sub-agent context gate

`/mold` owns the dialogue, contradictions, and approval state. Do not delegate these items. Delegate evidence-heavy code work to a fresh-context `explorer`. Delegate external research to a `researcher`. **Shape uses an explorer digest as input.** Record parent-context exploration as a degraded path. See `references/context-budget.md` for budgets and required checkpoints.

### Gate graph

`python3 skills/mold/scripts/mold.pyz gate-graph --render dot|svg|png|mermaid` renders one gate model. Text targets need no binary. Image targets use Mermaid when Graphviz is unavailable. Tests keep gate nodes aligned with the handshake checklist. `fork_taste_test_passed` requires a fresh-context verdict. The verdict must match the digest and cover the complete ledger. See `references/gate-graph.md`.

### Gate applicability and Test Contracts

Every Mold-produced spec carries a provenance marker in frontmatter:

```yaml
source: mold-handshake | agent-mini-spec
```

Every spec declares `gate_applicability`:

```yaml
gate_applicability:
  disposition: red-required | not-applicable
  work_class: behavior | docs-only | refactor-only | test-only | appearance-only
  ui_surface: browser | non-browser | not-applicable
```

`ui_surface` is a required machine-readable field on the new Mold production
path. `browser` means functional browser/E2E behavior and requires every Test
Contract to name an existing browser/E2E interface and outer seam. `non-browser`
means ordinary behavior without a browser/E2E seam and is never inferred from
contract prose. `not-applicable` is required for closed non-behavior classes,
including appearance-only, and keeps their disposition N/A.

`red-required` requires `behavior` plus a complete `## Test Contracts` table:
each stable acceptance ID exactly once, with `interface`, outer `seam`,
deterministic `expected_failure`, and `tracer` or `contract-matrix` mode.
A contract-matrix row also declares a non-empty ratified interface version and
the complete, unique matrix row identities; tracer rows leave both fields
blank. `not-applicable` requires a closed non-behavior class, reason, and no
contracts. Mold never infers applicability. Specs without a Mold provenance
marker remain legacy-compatible and may omit `ui_surface`.

### Fork taste gate

`mold.pyz taste-test` binds the verdict to the draft SHA256. It also binds the verdict to each settled consequential ledger fork. Stale coverage, partial coverage, and blockers fail the gate. A failure reopens only the named forks. Mold permits two correction rounds. Approved `red-required` specs pass unchanged metadata and the durable pointer to `/cook --auto`.

Each settled consequential fork must appear in Approach, Interface sketches, and Acceptance. A `red-required` spec must also include each fork in Test Contracts. A `not-applicable` spec cannot contain Test Contracts. Do not rename a section to simulate the fourth reflection.

## Approval gate

Curdle requires the **two-key handshake**. It requires an explicit user verb, such as `curdle` or `ship it`. It also requires the agent's coherence self-check. Present the validated typed `CurdPlan`'s `N curds / M waves` with the final approval request in Flow step 5. See `references/handshake.md` for the checklist, mandatory gates, and override semantics.

Before the handshake runs, also perform the **agent-introduced-scope** check. Flag each noun in Approach / Decisions / Interface sketches that the user did not type. Require explicit approval for each term before extraction. See `references/handshake.md` § Agent-introduced scope for the full procedure and single-chokepoint guarantee.

If any gate is unmet, propose the smallest next question, evidence check, or planner correction. Do the same if the typed plan remains invalid after one retry. Write artifacts only after both keys pass.

## --hard

`/mold --hard` propagates `--hard` to `/cook` at handoff (any cook-flavoured option carries it forward). Mold runs no gate itself — the metacognitive vibecheck fires later, at `/cure`'s share-for-review boundary. See `skills/hard-cheese/SKILL.md` and `../hard-cheese/references/composition.md`.

## Handoff

**Pipeline:** culture → **[mold]** → cook → press → age → cure → plate

After Curdle's phase two finishes, run `curd-count`, then prompt through the shared handoff gate ([policy](../cheese/references/handoff-gate.md)). Approved `red-required` behavior recommends `/cook --auto <durable spec pointer>` with unchanged applicability, contract, taste metadata, and any in-scope `--hard`. Never pre-select.

The digest's `mode` is orientation, not a skill. Render the fixed blast-radius menu from `decomposable`, `candidate_curds`, `verdict`, and `mode`; see `references/handoff-menus.md`.

## Rules

- Dialogue first; artifacts are the by-product.
- **Tiered lettered options.** Consequential forks use `A/B/C/D` choices via the question transport at `../cheese/references/ask-user-question.md`; never decide them silently. Minor mechanics use `[AGENT-DECIDED]` with a vetoable alternative. A fork is valid only after its depth was contributed in-dialogue first. Precede every structured question with visible prose weighing the fork and evidence, and keep one open picker.
- **Decision ledger.** Each round prints `Decided / Asking / [AGENT-DECIDED]`. Curdle persists consequential decisions to [ADRs](references/adr.md) and minor ones to the spec. The taste verdict names every settled consequential entry exactly once.
- **Decision map and fork-round cap.** Stop after three consecutive fork rounds that add no new evidence. Also stop when the user requests a decision map. Show completed forks, remaining forks, and a ready or blocked verdict. A fourth round requires new grounding, a delegated digest, or a `/wheypoint` checkpoint. The map shows ledger state. It does not create an artifact.
- Do not implement code.
- Do not write production files before the approval gate.
- Do not silently settle uncertain claims.
- Apply the shared voice kernel at `../age/references/voice.md`. Correct false premises. Mark each critical claim's confidence as `certain | speculating | don't know`. Steelman before you dismiss. Put design-shaping decisions to the user. Let depth inform each question, but never let it replace the question.

The schema entanglement behind curdle's spec-template and cook's writer views is phase registry × schema catalog × models per transition. The generated [`../cheese/references/schema-intertwine.md`](../cheese/references/schema-intertwine.md) documents it.

## Agent resolution

Resolve delegates through [`../cheese/references/agent-resolution.md`](../cheese/references/agent-resolution.md).

| Work | Preferred types | Permissions/isolation | Minimum power | Effort | Fallback |
| --- | --- | --- | --- | --- | --- |
| Explore the codebase | explorer | read-only, fresh-context | default | medium | compatible explorer, then general |
| Research external constraints | researcher | read-only, fresh-context | default | medium | compatible researcher, then general |
| Plan for approval | planner, general | read-only, fresh-context | powerful | high | compatible planner, then general |

The canonical mold spec or mini-spec carries the shared `agent_resolution` block.

Generated bundle command inventory: [`references/commands.md`](references/commands.md).
