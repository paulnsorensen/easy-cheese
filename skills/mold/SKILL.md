---
name: mold
description: Turn a high-leverage design decision into a validated spec through grounded dialogue. Use it when a leverage trigger fires (auth, irreversible effects, concurrency, contracts, destructive ops, a new slice, a cross-slice dependency, an invariant gap) or when the user asks for a spec or design. Typical phrases include "let's design X", "shape this into a spec", "what should the API for Z look like", and "/mold". A feature ask with zero fired triggers is a `/cook` mini-spec, not a mold; route it through `/cheese`. Do NOT use it for free-form discussion without artifact intent (`/culture`), direct implementation (`/cook`), or research-only questions (`/briesearch`). Ceremony scales to the ask through `references/tiers.md`, so a small clear change gets a validated mini-spec without a write-approval turn.
license: MIT
metadata: {dispatches-agents: true}
---

# /mold

Ceremony scales to the job. The Bounds pass picks one of three tiers from `references/tiers.md`: **Quick** writes a validated mini-spec, **Light** runs only the dialogue modes the open forks need, and **Full** runs the whole Flow below. Saving a spec needs no extraction approval. Cook still needs an explicit user request. `/cheese`'s tier-1 escalation enters mini-spec mode; see `## Agent-invoked mini-spec mode`.

## Flow

1. **Bounds pass** — open the `Goal / Decided / Asking / [AGENT-DECIDED]` ledger with the goal pinned as one sentence; only an explicit user fork changes it. Split it into `G-n` clauses (`references/handshake.md` § Goal coverage). Map every input's goals and **non-goals** as one `[AGENT-DECIDED]` line; ask the user only when the goal is genuinely unknown or a leverage trigger fires. Run the shape check, then announce the tier with its reason (`references/tiers.md`). Quick exits here to `## Agent-invoked mini-spec mode` without a write-approval turn. Upgrade the tier whenever the evidence changes; never downgrade silently.
2. **Route** — choose the secondary mode from `references/modes.md`, announce it, and correct false premises first.
3. **Dialogue** — consequential forks are the user's to pick. A fork is consequential per the leverage line in `../age/references/voice.md`. Every other fork is `[AGENT-DECIDED]`. Supply options, trade-offs, and evidence before you ask. Ground each critical claim through code, the [Validate Cycle](references/validate-cycle.md), or a [Prototype Cycle](references/prototype-cycle.md). Resolve every contradiction. Render the decision map after three consecutive fork questions, or on request.
4. **Sketch** — For work across modules or with a new public interface, run `references/shape-check.md`. Bind identity and role nouns to code referents. Record the Placement block; no bodies.
5. **Plan and validate** — run the fresh-context fork-coherence taste test with `python3 skills/mold/scripts/mold.pyz taste-test` and persist its digest-bound pass; a failure reopens only named forks, and the third failed verdict stops. Light with one expected curd needs no planner. Otherwise dispatch a typed `PlannerRequest`, validate its `PlannerResultWriterView` (one retry, then save without a runnable handoff), and normalize on the host. Show the semantic curds and waves before any Cook choice. See `references/curdle.md` § "Pre-approval typed planner dispatch".
6. **Readiness check** — Before saving, the agent runs the coherence self-check and strict spec validation. Save a draft even when unresolved parent work remains; record each hold. User approval is not a prerequisite for writing. Before Cook, require an explicit user selection of the exact scope and route. See `references/handshake.md` and `references/early-curds.md`.
7. **Curdle** — Resolve the durable spec path with `SPEC=$(python3 skills/mold/scripts/mold.pyz artifact-path specs <slug>)`. Write the validated draft and read it back. Retain typed plan evidence and unresolved holds. Write local issue drafts and durable decisions; publish follow-ups only after their own approval. A concrete bounded curd may use `references/early-curds.md` now, while Mold continues shaping its parent. The resolved spec path is internal; Cook receives only a ready finalizer pointer after the user selects Cook.
8. **Offer Cook or keep shaping** — after reconciliation, run [`python3 skills/mold/scripts/mold.pyz curd-count`](references/curd-count.md). A saved draft is not a handoff. If the user selects Cook, bind the exact scope or plan with `mold.pyz approve`, then run `mold.pyz finalize`. Dispatch only a ready pointer and the selected route. Otherwise keep shaping or stop without a Cook command.

Portability: [rules](../cheese/references/harness-portability.md). Slash commands are host renderings, not the control model.

## Follow-up candidates

Every non-goal and explicit dialogue deferral becomes a `[FOLLOW-UP?]` follow-up candidate. Dispose of the set before a runnable Cook handoff; details: `references/handshake.md` § Follow-up disposition.

## Modes

| Mode | Use when | Goal |
| --- | --- | --- |
| Explore | The idea is vague | Identify the real problem and pain point |
| Ground | A file, bug, or existing doc is named | Verify facts against evidence |
| Shape | The goal is known but approach is open | Compare viable options (Do Nothing always included) |
| Sketch | Interfaces or module boundaries matter | Lock responsibilities and seams |
| Grill | A favoured approach needs stress-testing | Steelman each item, then put every design-changing call to the user as a fork |
| Diagnose | A symptom, failure, or trace is supplied | Build a Loop → reproduce → hypothesize → confirm root cause |

Modes: references/modes.md. Evals: references/evals.md. Canvas: [review-canvas.md](references/review-canvas.md).

## Agent-invoked mini-spec mode

`/cheese`'s tier-1 escalation calls `/mold` after the call site passes all cook fast-path checks, and the Quick tier enters the same mode without a write-approval turn. It produces a validated draft without design dialogue. Return the spec path, not a runnable pointer. If the user's entry already requested Cook, bind that request to the exact scope, finalize, and dispatch only a ready pointer. Append `--hard` when the user passed it.

The full coherence checklist does not run in this mode. The agent-introduced-scope check still runs implicitly. Every distinguishing noun must come from the user's input or tier-2 `/culture`/`/briesearch` synthesis. Never add one silently.

Full procedure, the mini-spec schema, and the `## Provenance` rules: `references/mini-spec-mode.md`.

## Preferred tools and fallbacks

Call source-code search, read, and edit backends according to [`code-intelligence-routing.md`](../cheese/references/code-intelligence-routing.md). Shape checks use semantic caller search plus dependency context; procedure: `references/shape-check.md`.

Mold-specific tools beyond source-code routing:

| Need | Prefer | Fallback |
| --- | --- | --- |
| External validation | `/briesearch` with Context7/Tavily | user docs, repo docs, or note as unverified |
| Wiki grounding (Ground entry + decision points; scope per `references/grounding.md` § When to probe) | `mcp__hallouminate__list_corpora` + `mcp__hallouminate__ground` on `repo:<repo>:wiki` | record `hallouminate: absent` in the ledger, proceed on code evidence, and cap at `speculating` when design rationale is central |

**The grounding record precedes the first structured question:** the ledger holds a probe result — citations or `hallouminate: absent` — first. Mark each unsupported claim `[?]` until settled.

## Sub-agent context gate

`/mold` owns the dialogue, contradictions, and approval state. Do not delegate these items. Delegate evidence-heavy code work to a fresh-context `explorer` and external research to a `researcher`. **Shape uses an explorer digest as input.** Record parent-context exploration as a degraded path. See `references/context-budget.md` for budgets and checkpoints.

### Gate graph

`python3 skills/mold/scripts/mold.pyz gate-graph --render dot|svg|png|mermaid` renders one gate model. Image targets use Mermaid when Graphviz is unavailable. Tests keep gate nodes aligned with the handshake checklist. See `references/gate-graph.md`.

### Gate applicability and Test Contracts

Every Mold-produced spec carries a provenance marker in frontmatter:

```yaml
source: mold-handshake | agent-mini-spec | mold-curd-mini-spec
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

`python3 skills/mold/scripts/mold.pyz taste-test` binds the verdict to draft SHA256 and each settled fork. Stale, partial, or blocked verdicts fail; a failure reopens only named forks, with two rounds. Approved `red-required` specs pass unchanged metadata and the published pointer to `/cook --auto`.

Each fork appears in Approach, Interface sketches, Acceptance, plus Test Contracts for `red-required`; none in `not-applicable` specs. Do not rename sections. Tag reflecting lines with fork id and run `taste-test --precheck` before dispatch. `goal` must survive verbatim in Problem statement (`goal-drift`); each `G-n` clause carries an Acceptance or disposition tag (`goal-coverage`). See `references/curdle.md` § Spec template and `references/gate-graph.md`.

## Execution gate

Mold may save a validated parent spec or early curd mini-spec without an approval turn. The agent coherence check still controls what the artifact claims as settled. Print the narrowing delta (`taste-test --coverage`) and the scope audit table before presenting any Cook option. Unresolved decisions remain visible holds, not implicit approvals. See `references/handshake.md`.

Never start Cook from a saved spec, silence, `--auto`, or a general design approval. The user must select the exact curd or parent scope and a Cook route. Bind that literal selection to the scope or plan proposal, then finalize. A changed scope or plan needs a new selection. A failed gate leaves a saved draft without a runnable pointer. See `references/early-curds.md`.

## --hard

Mold never runs the metacognitive check. Plate alone runs it at the
verified-artifacts boundary. Mold appends `--hard` to every Cook command that
it emits when the user passed the flag. Cure forwards the same flag to Plate.
See `../hard-cheese/references/composition.md`.

## Handoff

**Pipeline:** culture → **[mold]** → cook → press → age → cure → plate

After Curdle's phase two finishes, run [`python3 skills/mold/scripts/mold.pyz curd-count`](references/curd-count.md) for the blast-radius digest. A draft offers no Cook command. On an explicit Cook selection, finalize and keep only a consumer-valid canonical `HandoffPointer`. Prompt through the shared handoff gate ([policy](../cheese/references/handoff-gate.md)); never pre-select. Keep applicability, contract, and taste metadata unchanged. Append `--hard` when the user passed it.

The digest's `mode` is orientation, not a skill. Render the fixed blast-radius menu from `decomposable`, `candidate_curds`, `verdict`, and `mode`; see `references/handoff-menus.md`.

## Rules

- Dialogue first; artifacts are the by-product.
- **Tiered lettered options.** Consequential forks use `A/B/C/D` choices via the question transport at `../cheese/references/ask-user-question.md`. Never decide them silently. Everything below the leverage line is `[AGENT-DECIDED]` by default: make the call, log a one-line vetoable alternative in the ledger, and do not ask. A fork is valid only after its depth was contributed in-dialogue first. Precede every structured question with visible prose that weighs the fork and the evidence. Keep one open picker.
- **Altitude tag.** Every `Asking` fork names the acceptance criterion, public seam, or non-goal it moves. A fork that moves none, or that sits below the leverage line, is `[AGENT-DECIDED]` or a follow-up candidate, never a user question.
- **Decision ledger.** Each round prints `Goal / Decided / Asking / [AGENT-DECIDED]`, the goal verbatim. Curdle persists consequential decisions to [ADRs](references/adr.md) and minor ones to the spec. The taste verdict names every settled consequential entry exactly once.
- **Decision map and fork-round cap.** Stop after three consecutive fork rounds that add no new evidence, or three consecutive forks that fail the altitude tag, or when the user requests a decision map. Show completed forks, remaining forks, and a ready or blocked verdict. A fourth round requires new grounding, a delegated digest, or a `/wheypoint` checkpoint. The map shows ledger state. It does not create an artifact.
- Do not implement code.
- Do not write production files in Mold. Saving a spec does not authorize Cook.
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
Commands: [`references/commands.md`](references/commands.md).
