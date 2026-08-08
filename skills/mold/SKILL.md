---
name: mold
description: Converge a fuzzy idea or half-formed feature into an approved spec through an iterative, grounded design dialogue. Use when the user has a fuzzy idea or design direction — phrases like "let's design X", "I'm thinking about Y", "what should the API for Z look like", "shape this into a spec", "what would it take to build/set up X", "I want to add a feature that…", "/mold". Use even when the user is "just thinking out loud" if they want the dialogue to leave behind a written artifact. Do NOT use for free-form discussion with no artifact intent (`/culture`), direct implementation (`/cook`), or research-only questions (`/briesearch`).
license: MIT
metadata: {dispatches-agents: true}
---

# /mold

Two modes, by analogy to `/culture`:

1. **User-invoked full ceremony (default).** The user typed `/mold` (or `/cheese` routed an explicit fuzzy-design ask straight here). Runs the full Explore/Ground/Shape/Sketch/Grill/Diagnose dialogue and the two-key handshake before any spec is written; the Flow below describes it.
2. **Agent-invoked mini-spec mode.** `/cheese` calls into `/mold` at tier 1 of its escalation (`skills/cheese/SKILL.md` § Escalation) when the cook fast-path checks all pass and a spec must materialise before the gate-applicability route runs. No dialogue, no handshake. See `## Agent-invoked mini-spec mode` below.

## Flow

1. **Bounds pass** — map every input's goals and **non-goals** before routing; ask the user rather than assume. Open the `Decided / Asking / [AGENT-DECIDED]` ledger. Clear work gets one fast confirm; full-spec work gets an upgrade-tier warning.
2. **Route** — choose the secondary mode from `references/modes.md`, announce it, and correct false premises first.
3. **Dialogue** — consequential forks are the user's to pick. Supply options, trade-offs, and evidence before asking; ground critical claims through code, the [Validate Cycle](references/validate-cycle.md), or a [Prototype Cycle](references/prototype-cycle.md). Resolve contradictions and render the decision map after three consecutive fork questions or on request.
4. **Sketch** — for work spanning modules or adding a public interface, run `references/shape-check.md`, bind identity/role nouns to code referents, and lock seams as pseudocode signatures.
5. **Plan for approval** — first run the fresh-context fork-coherence taste test from `src/mold/taste_test.py` and persist its digest-bound pass. A failure reopens only named forks; halt after the third failed verdict. Only then dispatch a typed `PlannerRequest` and validate its `PlannerResultWriterView`; retry an invalid result once and stop before the handshake if it remains invalid. Normalize it on the host and persist only the typed `PlannerResult` and `CurdPlan` artifacts. The legacy `CurdBlock`/`Decomposition` projection is migration-only: request it explicitly and require a lossless projection or `UnsupportedProjection`. Present the typed plan's semantic curds and waves at the handshake. See `references/curdle.md` § "Pre-approval typed planner dispatch".
6. **Two-key handshake** — both the user (explicit verb) and the agent (coherence self-check) must agree to the draft spec and displayed typed plan before extraction. Neither key changes or disappears. See `references/handshake.md`.
7. **Curdle** — resolve the durable spec path with `SPEC=$(python3 shared/scripts/artifact_path.py specs <slug>)` (bundle-only host fallback: `python3 skills/mold/scripts/mold.pyz artifact-path specs <slug>`). Phase one writes every local artifact and write-ahead prepared state *before any external call*: the approved spec at `"$SPEC"`, the host-validated `PlannerResult` and `CurdPlan`, any local issue drafts, and the session's non-obvious decisions as durable ADRs. Phase two then publishes approved follow-ups, retains prepared recovery state when an external capability is unavailable or publication fails, and reconciles their state and references into the durable spec before any handoff.
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

`/cheese`'s tier-1 escalation calls into `/mold` to produce a spec without a user-facing dialogue, once the cook fast-path checks have already passed at the call site. The mode skips the Flow above entirely: derive a slug, write the mini-spec, parse its declared gate applicability, and return the resolved spec path with `/cut --auto <spec-path>` for `red-required` or `/cook --auto <spec-path>` for a closed `not-applicable` disposition.

The two-key handshake does not fire in this mode; the agent-introduced-scope check still runs implicitly — every distinguishing noun in the mini-spec must come from the user's input or the tier-2 `/culture`/`/briesearch` synthesis, never a silent agent addition.

Full procedure, the mini-spec schema, and the `## Provenance` rules: `references/mini-spec-mode.md`.

## Preferred tools and fallbacks

Call source-code search, read, and edit backends directly according to [`code-intelligence-routing.md`](../cheese/references/code-intelligence-routing.md). Shape checks use semantic caller search plus dependency context; procedure: `references/shape-check.md`.

Beyond source-code routing there are mold-specific tools:

| Need | Prefer | Fallback |
| --- | --- | --- |
| External validation | `/briesearch` with Context7/Tavily | user-provided docs, repo docs, or note as unverified |
| Wiki grounding (Ground entry + decision points; scope per `references/grounding.md` § When to probe) | `mcp__hallouminate__list_corpora` + `mcp__hallouminate__ground` on `repo:<repo>:wiki` | skip; proceed with code evidence only; cap at `speculating` when design rationale is central |

Optional tools accelerate the work but never block the dialogue. When evidence is unavailable, mark the claim `[?]` until settled.

## Sub-agent context gate

`/mold` owns dialogue, contradictions, and approval state. Delegate evidence-heavy reads or graphs to a fresh-context `explorer`, and external research to a `researcher`; see `references/context-budget.md`.

### Gate graph

`python3 skills/mold/scripts/mold.pyz gate-graph --render dot|svg|png|mermaid` renders one gate model. Text targets need no binary; image targets degrade to mermaid without Graphviz. Tests keep gate nodes aligned with the handshake checklist. `fork_taste_test_passed` requires a fresh-context verdict with matching digest and complete ledger coverage; see `references/gate-graph.md`.

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
marker remain legacy-compatible for Cut and may omit `ui_surface`.

### Fork taste gate

`mold.pyz taste-test` binds the verdict to the draft SHA256 and every settled consequential ledger fork. Stale/partial coverage or any blocker fails; failures reopen named forks only, with two correction rounds. Approved `red-required` specs hand off unchanged metadata and durable pointer to `/cut --auto`.

## Approval gate

Curdle requires the **two-key handshake**: an explicit user verb (e.g. `curdle`, `ship it`) plus the agent's coherence self-check, with the validated typed `CurdPlan`'s `N curds / M waves` presented alongside the final approval request (Flow step 5). Checklist, mandatory gates, and override semantics: `references/handshake.md`.

Before the handshake fires, also run the **agent-introduced-scope** check — flag any noun in Approach / Decisions / Interface sketches the user did not type, and require explicit per-term approval before extraction. Full procedure and the single-chokepoint guarantee in `references/handshake.md` § Agent-introduced scope.

If any gate is unmet or the typed plan remains invalid after one retry, propose the smallest next question, evidence check, or planner correction. Write artifacts only after both keys pass.

## --hard

`/mold --hard` propagates `--hard` to `/cook` at handoff (any cook-flavoured option carries it forward). Mold runs no gate itself — the metacognitive vibecheck fires later, at `/cure`'s share-for-review boundary. See `skills/hard-cheese/SKILL.md` and `../hard-cheese/references/composition.md`.

## Handoff

**Pipeline:** culture → **[mold]** → cut → cook → press → age → cure → plate

After Curdle's phase two finishes, run `curd-count`, then prompt through the shared handoff gate ([policy](../cheese/references/handoff-gate.md)). Approved `red-required` behavior recommends `/cut --auto <durable spec pointer>` with unchanged applicability, contract, taste metadata, and any in-scope `--hard`; `/cook` is the synchronous no-receipt fallback. Never pre-select.

The digest's `mode` is orientation, not a skill. Render the fixed blast-radius menu from `decomposable`, `candidate_curds`, `verdict`, and `mode`; see `references/handoff-menus.md`.

## Rules

- Dialogue first; artifacts are the by-product.
- **Tiered lettered options.** Consequential forks use `A/B/C/D` choices via the question transport at `../cheese/references/ask-user-question.md`; never decide them silently. Minor mechanics use `[AGENT-DECIDED]` with a vetoable alternative. A fork is valid only after its depth was contributed in-dialogue first. Precede every structured question with visible prose weighing the fork and evidence, and keep one open picker.
- **Decision ledger.** Each round prints `Decided / Asking / [AGENT-DECIDED]`. Curdle persists consequential decisions to [ADRs](references/adr.md) and minor ones to the spec. The taste verdict names every settled consequential entry exactly once.
- **Decision map.** After three consecutive fork questions, or on request, show done forks, required and optional remaining forks, and a ready/blocked verdict. It renders ledger state; it creates no artifact.
- Do not implement code.
- Do not write production files before the approval gate.
- Do not silently settle uncertain claims.
- Apply the shared voice kernel (lives at `../age/references/voice.md`): correct false premises, flag confidence as `certain | speculating | don't know` on each critical claim, steelman before dismissing, and put the design-shaping decisions to the user — depth informs each question, it never replaces asking it.

## Agent resolution

Resolve delegates through [`../cheese/references/agent-resolution.md`](../cheese/references/agent-resolution.md).

| Work | Preferred types | Permissions/isolation | Minimum power | Effort | Fallback |
| --- | --- | --- | --- | --- | --- |
| Explore the codebase | explorer | read-only, fresh-context | default | medium | compatible explorer, then general |
| Research external constraints | researcher | read-only, fresh-context | default | medium | compatible researcher, then general |
| Plan for approval | planner, general | read-only, fresh-context | powerful | high | compatible planner, then general |

The canonical mold spec or mini-spec carries the shared `agent_resolution` block.
