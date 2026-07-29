---
name: mold
description: Converge a fuzzy idea or half-formed feature into an approved spec through an iterative, grounded design dialogue. Use when the user has a fuzzy idea or design direction — phrases like "let's design X", "I'm thinking about Y", "what should the API for Z look like", "shape this into a spec", "what would it take to build/set up X", "I want to add a feature that…", "/mold". Use even when the user is "just thinking out loud" if they want the dialogue to leave behind a written artifact. Do NOT use for free-form discussion with no artifact intent (`/culture`), direct implementation (`/cook`), or research-only questions (`/briesearch`).
license: MIT
metadata: {dispatches-agents: true}
---

# /mold

Two modes, by analogy to `/culture`:

1. **User-invoked full ceremony (default).** The user typed `/mold` (or `/cheese` routed an explicit fuzzy-design ask straight here). Runs the full Explore/Ground/Shape/Sketch/Grill/Diagnose dialogue and the two-key handshake before any spec is written; the Flow below describes it.
2. **Agent-invoked mini-spec mode.** `/cheese` calls into `/mold` at tier 1 of its escalation (`skills/cheese/SKILL.md` § Escalation) when the cook fast-path checks all pass and a spec must materialise before `/cook --auto` runs. No dialogue, no handshake. See `## Agent-invoked mini-spec mode` below.

## Flow

1. **Bounds pass** — before routing, run one Explore-style bounds round for *every* input shape: map the problem's edges to candidate goals and **non-goals**, asking the user rather than assuming. Open the per-round decision ledger (`Decided / Asking / [AGENT-DECIDED]`; see `## Rules`). Tier it — a clear input gets a single fast confirm, not a full A/B/C/D menu — but never skip it. When the dialogue reveals full-spec-sized work, warn to upgrade tier (harness-detected: claude `/model opus` + `/effort`; codex/OMP equivalent; generic fallback) before continuing.
2. **Route** — pick the *secondary* mode from the input shape (see `references/modes.md`) and announce it in one line. If the user's framing rests on a false premise or a loaded assumption, name it before routing.
3. **Dialogue** — build shared understanding: every consequential fork is the user's to pick, surfaced as a choice, never settled for them. Contribute full depth (options, edge cases, evidence) to inform each question, never to replace asking it. Ground every critical claim via the selected source-code search/read backend, a Validate Cycle (`references/validate-cycle.md`), or — for an ungrillable design unknown — a Prototype Cycle (`references/prototype-cycle.md`); both are sub-agent-spawnable mid-dialogue, in parallel, context-bounded (soft backstop of 10). Track and resolve contradictions across turns before continuing. After 3 consecutive fork questions, or on "what forks are left?", render the decision map (`## Rules` § Decision map).
4. **Sketch** — for any feature touching >1 module or a new public interface, run the shape check (`references/shape-check.md`) on the touched symbols, then lock seams in pseudocode signatures before talking spec content. While the code is open, bind every identity/ownership-role noun to a code referent per `references/handshake.md` § Entity-referent binding — a search hit of a *different* referent is an alias, not a pass.
5. **Decompose for approval** — once the draft spec and any pre-Curdle follow-up disposition are complete, dispatch the fresh-context curd-block decomposer on the draft text and validate its result before requesting approval. Retry an invalid result once; if it is still invalid, stop before the handshake rather than approving a block that cannot be persisted. Present the validated curd block as `N curds / M waves` at the handshake. See `references/curdle.md` § "Pre-approval decomposer dispatch".
6. **Two-key handshake** — both the user (explicit verb) and the agent (coherence self-check) must agree to the draft spec and displayed curd plan before extraction. Neither key changes or disappears. See `references/handshake.md`.
7. **Curdle** — resolve the durable spec path with `SPEC=$(python3 shared/scripts/artifact_path.py specs <slug>)` (bundle-only host fallback: `python3 skills/mold/scripts/mold.pyz artifact-path specs <slug>`). The resolver anchors specs at the per-project durable corpus (`../cheese/references/formatting.md` § Corpus location); never hardcode a repo-local spec path. Phase one writes every local artifact and write-ahead prepared state *before any external call*: the approved spec at `"$SPEC"`, the same approved curd block as `## Curds`, any local issue drafts, and the session's non-obvious decisions as durable ADRs. Phase two then publishes approved follow-ups, retains prepared recovery state when an external capability is unavailable or publication fails, and reconciles their state and references into the durable spec. Never re-dispatch or mutate the approved curd block during Curdle. Format, slug, publication, reconciliation, corpus-resolution, and curd-block persistence rules: `references/curdle.md` and `references/adr.md`.
8. **Count and hand off** — only after phase-two publication attempts and reconciliation finish, run `python3 skills/mold/scripts/mold.pyz curd-count "$SPEC" --blast-radius <low|medium|high>` for the recommended downstream skill (procedure in `references/curd-count.md`), then prompt via `## Handoff`. Never dispatch before the user selects; after a non-stop selection, run the selected skill immediately.

Portability reference: [`../cheese/references/harness-portability.md`](../cheese/references/harness-portability.md). It covers helper resolution, sub-agent dispatch, GitHub operations, and handoff transitions; prefer the bundled or repo-local helper first, and treat `${CLAUDE_SKILL_DIR}` as optional host-provided fallback.
The handoff blocks below are the portable contract; slash commands are host renderings, not the control model.

## Follow-up candidates

Every non-goal and explicit dialogue deferral enters the session's follow-up candidate set, logged as `[FOLLOW-UP?]`. When candidates exist, the pre-Curdle disposition batch must complete before the two-key handshake can pass; omit it when none exist. Ledger notation, dialogue-state semantics, and Curdle-ordering detail: `references/handshake.md` § Follow-up disposition.

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

`/cheese`'s tier-1 escalation calls into `/mold` to produce a spec without a user-facing dialogue, once the cook fast-path checks have already passed at the call site. The mode skips the Flow above entirely: derive a slug, write the mini-spec, and return the resolved spec path so `/cheese` can dispatch `/cook --auto <spec-path>`.

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

`/mold` keeps the dialogue, contradictions, approval state, and the two-key handshake in the parent context — those never delegate. Offloading heavy work to a read-only sub-agent is the **default**: `explorer` for code reads and shape checks, `researcher` for deep `/briesearch`. Spawn one whenever the work would flood the conversation with raw evidence or graph output. Triggers, digest constraints, and the inline fallback: `references/context-budget.md`.

### Gate graph

Mold's gate state machine is one machine-readable model, rendered via `python3 skills/mold/scripts/mold.pyz gate-graph --render dot|svg|png|mermaid`. `dot`/`mermaid` need no binary; `svg`/`png` use Graphviz `dot` when present and degrade to mermaid. A test keeps its gate nodes in lockstep with the `handshake.md` coherence checklist, so a gate cannot be dropped from prose. Details: `references/gate-graph.md`.

## Approval gate

Curdle requires the **two-key handshake**: an explicit user verb (e.g. `curdle`, `ship it`) plus the agent's coherence self-check, with the validated curd block's `N curds / M waves` presented alongside the final approval request (Flow step 5). Checklist, mandatory gates, and override semantics: `references/handshake.md`.

Before the handshake fires, also run the **agent-introduced-scope** check — flag any noun in Approach / Decisions / Interface sketches the user did not type, and require explicit per-term approval before extraction. Full procedure and the single-chokepoint guarantee in `references/handshake.md` § Agent-introduced scope.

If any gate is unmet or the curd block remains invalid after one retry, propose the smallest next question, evidence check, or decomposer correction. Write artifacts only after both keys pass.

## --hard

`/mold --hard` propagates `--hard` to `/cook` at handoff (any cook-flavoured option carries it forward). Mold runs no gate itself — the metacognitive vibecheck fires later, at `/cure`'s share-for-review boundary. See `skills/hard-cheese/SKILL.md` and `../hard-cheese/references/composition.md`.

## Handoff

**Pipeline:** culture → **[mold]** → cook → press → age → cure → plate

After Curdle's phase two finishes, run the curd-count script (procedure and `--blast-radius` rules in [`references/curd-count.md`](references/curd-count.md)), then render the branch menu below and prompt via the shared handoff gate. Never pre-select an autonomous option.

Read the JSON digest. `/cook` is the uniform *(recommended)* option; the digest's `mode` field (`parallel`, `linear`, or `null`) is orientation-only — it explains why a branch recommends the autonomous chain and is never rendered as a skill name. Ask via the shared handoff gate ([`../cheese/references/handoff-gate.md`](../cheese/references/handoff-gate.md)), leading each option with the verb and the skill command (spec path plus any in-scope `--hard`) as backing detail.

The three blast-radius branches — decomposable, non-decomposable high-blast-radius, and non-decomposable low/medium — each render a fixed menu keyed off the digest's `decomposable`, `candidate_curds`, `verdict`, and `mode` fields. Menu wording, the recommended/manual/stop options per branch, and `mode`'s role in choosing the branch: `references/handoff-menus.md`.

## Rules

- Dialogue first; artifacts are the by-product.
- **Tiered lettered options.** Consequential forks (scope, approach, non-goals, interface/seam, trade-offs) go to the user as `A/B/C/D` choices via the question transport at `../cheese/references/ask-user-question.md` — never resolved silently. Minor mechanical calls are logged `[AGENT-DECIDED]` inline with a one-line vetoable alternative (ADR-003). A fork is valid only after its depth was contributed in-dialogue first. **Visible-prose gate (hard):** every structured question MUST be preceded, same visible turn, by prose naming the fork, weighing options, and citing evidence — never in a thinking block, never straight from the user's message to the picker. **One open picker:** never emit a second structured question before the first is answered.
- **Per-round decision ledger.** Each dialogue round prints `Decided / Asking / [AGENT-DECIDED]`. At curdle the ledger persists to the ADR(s) (`references/adr.md`) plus a one-line minor decision-log on the spec; no separate ledger file (ADR-004).
- **Decision map.** After 3 consecutive fork questions, or on "what forks are left?", render a compact map from the ledger: Done forks (from `Decided`), remaining-before-curdle forks split into required (`references/handshake.md` § Mandatory gates) vs optional, and a one-line curdle-readiness verdict (ready, or blocked naming the unmet gate). It renders existing state — not a new artifact, file, or script.
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
| Decompose for approval | planner, general | read-only, fresh-context | powerful | high | compatible planner, then general |

The canonical mold spec or mini-spec carries the shared `agent_resolution` block.
