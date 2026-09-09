---
name: mold
description: Turn a high-leverage design decision into an approved spec through grounded dialogue. Use it when a leverage trigger fires (auth, irreversible effects, concurrency, contracts, destructive ops, a new slice, a cross-slice dependency, an invariant gap) or when the user asks for a spec or design. Typical phrases include "let's design X", "shape this into a spec", "what should the API for Z look like", and "/mold". A feature ask with zero fired triggers is a `/cook` mini-spec, not a mold; route it through `/cheese`. Do NOT use it for free-form discussion without artifact intent (`/culture`), direct implementation (`/cook`), or research-only questions (`/briesearch`). Ceremony scales to the ask through `references/tiers.md`, so a small clear change gets a one-confirm mini-spec rather than the full dialogue.
license: MIT
metadata: {dispatches-agents: true}
---

# /mold

Ceremony scales to the job. The Bounds pass picks one of three tiers from `references/tiers.md`: **Quick** writes a one-confirm mini-spec, **Light** runs only the dialogue modes the open forks need, and **Full** runs the whole Flow below. `/cheese`'s tier-1 escalation enters mini-spec mode directly with no confirm; see `## Agent-invoked mini-spec mode`.

## Flow

1. **Bounds pass** — open the `Goal / Decided / Asking / [AGENT-DECIDED]` ledger with the goal pinned as one sentence; only an explicit user fork changes it. Map every input's goals and **non-goals** as one `[AGENT-DECIDED]` line; ask the user only when the goal is genuinely unknown or a leverage trigger fires. Run the shape check, then announce the tier with its reason (`references/tiers.md`). Quick exits here: one fast confirm, then `## Agent-invoked mini-spec mode`. Upgrade the tier whenever the evidence changes; never downgrade silently.
2. **Route** — choose the secondary mode from `references/modes.md`, announce it, and correct false premises first.
3. **Dialogue** — consequential forks are the user's to pick. A fork is consequential per the leverage line in `../age/references/voice.md`. Every other fork is `[AGENT-DECIDED]`. Supply options, trade-offs, and evidence before you ask. Ground each critical claim through code, the [Validate Cycle](references/validate-cycle.md), or a [Prototype Cycle](references/prototype-cycle.md). Resolve every contradiction. Render the decision map after three consecutive fork questions, or on request.
4. **Sketch** — For work across modules or with a new public interface, run `references/shape-check.md`. Bind identity and role nouns to code referents. Record the Placement block; no bodies.
5. **Plan for approval** — run the fresh-context fork-coherence taste test with `mold.pyz taste-test` and persist its digest-bound pass; a failure reopens only named forks, and the third failed verdict stops. Light with one expected curd stops here: no planner, and the handoff is `/cook --auto <spec-path>`. Otherwise dispatch a typed `PlannerRequest`, validate its `PlannerResultWriterView` (one retry, then stop before the handshake), normalize on the host, and persist only the typed `PlannerResult` and `CurdPlan`. A legacy projection needs an explicit migration request and must be lossless or `UnsupportedProjection`. Present the plan's semantic curds and waves at the handshake. See `references/curdle.md` § "Pre-approval typed planner dispatch".
6. **Two-key handshake** — Before extraction, the user and agent must agree to the draft spec and displayed typed plan. The user provides an explicit verb. The agent performs a coherence self-check. Neither key changes nor disappears. See `references/handshake.md`.
7. **Curdle** — Resolve the durable spec path with `SPEC=$(python3 skills/mold/scripts/mold.pyz artifact-path specs <slug>)`. Phase one writes the local artifact and write-ahead prepared state before any external call. It writes the approved spec at `"$SPEC"`. It also writes the host-validated `PlannerResult` and `CurdPlan`. It also writes local issue drafts and the session's non-obvious decisions as durable ADRs. Phase two publishes approved follow-ups. Retain the prepared recovery state when an external capability is unavailable or publication fails. Phase two reconciles their state and references into the durable spec before any handoff.
8. **Publish and hand off** — after reconciliation, run [`mold.pyz curd-count`](references/curd-count.md). Then publish the approved `CurdPlan` with `mold.pyz publish` and keep the returned `HandoffPointer` path; Light with one curd skips publish and hands `/cook --auto <spec-path>`. Prompt through `## Handoff`. Dispatch only the user's non-stop selection.

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

`/cheese`'s tier-1 escalation calls `/mold` after the call site passes all cook fast-path checks, and the Quick tier enters the same mode after its one confirm. It produces a spec without design dialogue. This mode skips the rest of the Flow above. Derive a slug. Write the mini-spec. Parse its declared gate applicability. Return the resolved spec path with `/cook --auto <spec-path>`. Append `--hard` when the user passed it.

The two-key handshake does not run in this mode. The agent-introduced-scope check still runs implicitly. Every distinguishing noun in the mini-spec must come from the user's input or tier-2 `/culture`/`/briesearch` synthesis. Never add one silently.

Full procedure, the mini-spec schema, and the `## Provenance` rules: `references/mini-spec-mode.md`.

## Preferred tools and fallbacks

Call source-code search, read, and edit backends directly according to [`code-intelligence-routing.md`](../cheese/references/code-intelligence-routing.md). Shape checks use semantic caller search plus dependency context; procedure: `references/shape-check.md`.

Beyond source-code routing there are mold-specific tools:

| Need | Prefer | Fallback |
| --- | --- | --- |
| External validation | `/briesearch` with Context7/Tavily | user-provided docs, repo docs, or note as unverified |
| Wiki grounding (Ground entry + decision points; scope per `references/grounding.md` § When to probe) | `mcp__hallouminate__list_corpora` + `mcp__hallouminate__ground` on `repo:<repo>:wiki` | record `hallouminate: absent` in the ledger, proceed on code evidence, and cap at `speculating` when design rationale is central |

**The grounding record is a precondition for the first structured question.** Do not ask the question until the ledger contains a probe result. The result contains citations or `hallouminate: absent`. Mark each unsupported claim `[?]` until you settle it.

## Sub-agent context gate

`/mold` owns the dialogue, contradictions, and approval state. Do not delegate these items. Delegate evidence-heavy code work to a fresh-context `explorer`. Delegate external research to a `researcher`. **Shape uses an explorer digest as input.** Record parent-context exploration as a degraded path. See `references/context-budget.md` for budgets and required checkpoints.

### Gate graph

`python3 skills/mold/scripts/mold.pyz gate-graph --render dot|svg|png|mermaid` renders one gate model. Image targets use Mermaid when Graphviz is unavailable. Tests keep gate nodes aligned with the handshake checklist. See `references/gate-graph.md`.

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

`ui_surface` is required on the Mold production path: `browser` means every
Test Contract names an existing browser/E2E interface and outer seam,
`non-browser` is explicit and never inferred from prose, and `not-applicable`
is required for closed non-behavior classes including appearance-only.
`red-required` requires `behavior` plus a complete `## Test Contracts` table
with one executable red row; `not-applicable` requires a closed class, a
reason, and no contracts. Mold never infers applicability. Row-level rules:
`references/curdle.md` § Test Contracts.

### Fork taste gate

`mold.pyz taste-test` binds the verdict to the draft SHA256 and to each settled consequential ledger fork. Stale or partial coverage and blockers fail the gate; a failure reopens only the named forks, with two correction rounds. Approved `red-required` specs pass unchanged metadata and the published pointer to `/cook --auto`.

Each settled consequential fork must appear in Approach, Interface sketches, and Acceptance, plus Test Contracts for `red-required`; a `not-applicable` spec cannot contain Test Contracts. Do not rename a section to simulate the fourth reflection. `goal` must survive unchanged, compared case- and whitespace-insensitively, in Problem statement, else `goal-drift`; see `references/gate-graph.md` § Fork taste planner gate.

## Approval gate

Curdle requires the **two-key handshake**. It requires an explicit user verb, such as `curdle` or `ship it`. It also requires the agent's coherence self-check. Present the validated typed `CurdPlan`'s `N curds / M waves` with the final approval request in Flow step 5; on Light's single-curd path there is no plan, so present the spec alone and mark the plan boxes `n/a`. See `references/handshake.md` for the checklist, mandatory gates, and override semantics.

Before the handshake runs, present the **scope audit table** once: agent-introduced nouns, non-goals, entity bindings, and follow-ups, each with a default. One confirm approves the defaults; only leverage rows and unresolved bindings need their own verb. Procedure: `references/handshake.md` § Scope audit table.

If any gate is unmet, propose the smallest next question, evidence check, or planner correction. Do the same if the typed plan remains invalid after one retry. Write artifacts only after both keys pass.

## --hard

Mold never runs the metacognitive check. Plate alone runs it at the
verified-artifacts boundary. Mold appends `--hard` to every Cook command that
it emits when the user passed the flag. Cure forwards the same flag to Plate.
See `../hard-cheese/references/composition.md`.

## Handoff

**Pipeline:** culture → **[mold]** → cook → press → age → cure → plate

After Curdle's phase two finishes, run `curd-count`. Then publish the approved plan with `mold.pyz publish`. Then prompt through the shared handoff gate ([policy](../cheese/references/handoff-gate.md)). Approved `red-required` behavior recommends `/cook --auto <pointer path>`. Keep the applicability, contract, and taste metadata unchanged. Append `--hard` when the user passed it. Never pre-select.

The digest's `mode` is orientation, not a skill. Render the fixed blast-radius menu from `decomposable`, `candidate_curds`, `verdict`, and `mode`; see `references/handoff-menus.md`.

## Rules

- Dialogue first; artifacts are the by-product.
- **Tiered lettered options.** Consequential forks use `A/B/C/D` choices via the question transport at `../cheese/references/ask-user-question.md`. Never decide them silently. Everything below the leverage line is `[AGENT-DECIDED]` by default: make the call, log a one-line vetoable alternative in the ledger, and do not ask. A fork is valid only after its depth was contributed in-dialogue first. Precede every structured question with visible prose that weighs the fork and the evidence. Keep one open picker.
- **Altitude tag.** Every `Asking` fork names the acceptance criterion, public seam, or non-goal it moves. A fork that moves none, or that sits below the leverage line, is `[AGENT-DECIDED]` or a follow-up candidate, never a user question.
- **Decision ledger.** Each round prints `Goal / Decided / Asking / [AGENT-DECIDED]`, the goal verbatim. Curdle persists consequential decisions to [ADRs](references/adr.md) and minor ones to the spec. The taste verdict names every settled consequential entry exactly once.
- **Decision map and fork-round cap.** Stop after three consecutive fork rounds that add no new evidence, or three consecutive forks that fail the altitude tag, or when the user requests a decision map. Show completed forks, remaining forks, and a ready or blocked verdict. A fourth round requires new grounding, a delegated digest, or a `/wheypoint` checkpoint. The map shows ledger state. It does not create an artifact.
- Do not implement code.
- Do not write production files before the approval gate.
- Do not silently settle uncertain claims.
- Apply the shared voice kernel at `../age/references/voice.md`. Correct false premises. Mark each critical claim's confidence as `certain | speculating | don't know`. Steelman before you dismiss. Put consequential forks to the user; depth informs the question, never replaces it.

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
