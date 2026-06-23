---
name: mold
description: Converge a fuzzy idea or half-formed feature into an approved spec through an iterative, grounded design dialogue. Use when the user has a fuzzy idea or design direction — phrases like "let's design X", "I'm thinking about Y", "what should the API for Z look like", "shape this into a spec", "I want to add a feature that…", "/mold". Runs an iterative dialogue (Explore / Ground / Shape / Sketch / Grill / Diagnose), grounds every critical claim with cheez-search or briesearch, locks public seams in pseudocode, and only writes a spec to `.cheese/specs/<slug>.md` after an explicit approval gate. Use even when the user is "just thinking out loud" if they want the dialogue to leave behind a written artifact — for pure no-write thinking, route to `/culture` instead. After `/culture` (optional); before `/cook`.
license: MIT
---

# /mold

Two modes, by analogy to `/culture`:

1. **User-invoked full ceremony (default).** The user typed `/mold` (or `/cheese` routed an explicit fuzzy-design ask straight here). Runs the full Explore/Ground/Shape/Sketch/Grill/Diagnose dialogue and the two-key handshake before any spec is written. The flow below describes this mode.
2. **Agent-invoked mini-spec mode.** `/cheese` calls into `/mold` at tier 1 of its escalation (see `skills/cheese/SKILL.md` § Escalation) when the cook fast-path checks all pass and a spec needs to materialise before `/cook --auto` runs. No dialogue, no handshake — the agent writes a mini-spec directly from the user's input (plus any tier-2 `/culture` / `/briesearch` synthesis) and returns the spec path. See `## Agent-invoked mini-spec mode` below.

Do not use the user-invoked ceremony for free-form discussion with no artifact intent (`/culture`), direct implementation (`/cook`), or research-only questions (`/briesearch`).

## Flow

1. **Route** — pick a starting mode from the input shape (see `references/modes.md`) and announce it in one line. If the user's framing rests on a false premise or a loaded assumption, name it before routing.
2. **Dialogue** — build shared understanding through the smallest useful question to the user, but contribute at maximum useful depth between questions (full options, named edge cases, concrete evidence — not gestural sketches). Ground every critical claim with `cheez-search`, `cheez-read`, a Validate Cycle (`references/validate-cycle.md`), or — for an ungrillable design unknown only a running sketch can settle — a Prototype Cycle (`references/prototype-cycle.md`). Both cycles are sub-agent-spawnable mid-dialogue, in parallel, and are context-bounded (no hard cap; soft backstop of 10). Track contradictions across turns; if turn N contradicts an earlier conclusion, flag and resolve it before continuing.
3. **Sketch** — for any feature touching >1 module or a new public interface, run the shape check (`references/shape-check.md`) on the touched symbols, then lock seams in pseudocode signatures before talking spec content. Default to full signatures, not hand-waving. While the code is open, bind every identity/ownership-role noun to a code referent per `references/handshake.md` § Entity-referent binding — a search hit of a *different* referent is an alias, not a pass.
4. **Two-key handshake** — both the user (explicit verb) and the agent (coherence self-check) must agree before extraction. See `references/handshake.md`.
5. **Curdle** — resolve the durable spec path with `SPEC=$(python3 ${CLAUDE_SKILL_DIR}/scripts/mold.pyz artifact-path specs <slug>)`, then write the approved spec to `"$SPEC"` (and optional issues alongside). The resolver anchors specs at the per-project durable corpus (see `shared/formatting.md` § Corpus location); never hardcode a `.cheese/specs/` path. In the same atomic step, write the session's non-obvious decisions as durable ADRs — to the consumer repo's `repo:<their-repo>:wiki` hallouminate corpus when present (resolved dynamically, never hardcoded), else to a tracked `docs/adr/<slug>-NNN.md`. Format, slug, and ADR resolution rules in `references/curdle.md` and `references/adr.md`.
6. **Hand off** — once the spec is on disk, run `python3 ${CLAUDE_SKILL_DIR}/scripts/mold.pyz curd-count "$SPEC" --blast-radius <low|medium|high>` to compute the recommended downstream skill (full procedure in `references/curd-count.md`). Omit `--blast-radius` when the shape-check verdict is `[?]` or shape-check was skipped — the script degrades to `/cook` for sub-threshold specs in that case. Then prompt the next step via the shared handoff gate in [`../../shared/handoff-gate.md`](../../shared/handoff-gate.md). Never dispatch before the user selects; after a non-stop selection, run the selected downstream skill immediately.

## Modes

| Mode | Use when | Goal |
| --- | --- | --- |
| Explore | The idea is vague | Identify the real problem and pain point |
| Ground | A file, bug, or existing doc is named | Verify facts against evidence |
| Shape | The goal is known but approach is open | Compare viable options (Do Nothing always included) |
| Sketch | Interfaces or module boundaries matter | Lock responsibilities and seams |
| Grill | A favoured approach needs stress-testing | Steelman the rejected option, find weak assumptions and edge cases |
| Diagnose | A symptom, failure, or trace is supplied | Build a Loop → reproduce → hypothesize → confirm root cause |

Full mode definitions, exit criteria, and user knobs in `references/modes.md`.

## Agent-invoked mini-spec mode

`/cheese`'s tier-1 escalation calls into `/mold` to produce a spec without a user-facing dialogue. The cook fast-path checks have already passed at the call site, so the input is unambiguous by construction — there is nothing left to ground, no trade-offs to grill. The mode skips the Flow above entirely:

1. **Derive slug** from the user's ask (kebab-case noun-phrase, ≤ 4 words).
2. **Write `.cheese/specs/<slug>.md`** with the mini-spec schema below. Resolve the path via `python3 ${CLAUDE_SKILL_DIR}/scripts/mold.pyz artifact-path specs <slug>` when the resolver is available; otherwise fall back to the literal `.cheese/specs/<slug>.md` path.
3. **Return the explicit spec path** to `/cheese` so it can dispatch `/cook --auto <spec-path>` (the full `.cheese/specs/<slug>.md` form, not a bare `<slug>`).

The two-key handshake does not fire in this mode. The agent-introduced-scope check still runs implicitly: every distinguishing noun in the mini-spec must come from the user's input or from the tier-2 `/culture` / `/briesearch` synthesis recorded in `## Provenance`. Anything else is a silent agent addition and is forbidden — the mini-spec records only what the user asked for, not what the agent thinks they might have meant.

### Mini-spec schema

```markdown
---
slug: <kebab-slug>
source: agent-mini-spec
intent: <one-sentence restatement of the user's ask>
blast_radius: low | medium | high
inputs: <one-line>
outputs: <one-line>
verification: <one-line: the obvious check>
---

## Contract
<one paragraph: behaviour change, scope boundary>

## Acceptance
- <verifiable check 1>
- <verifiable check 2>

## Non-goals
- <what we are NOT changing>

## Provenance (tier 2 only)
- culture: <one-line synthesis of what /culture concluded>
- briesearch: <one-line synthesis>; artifact: research/<slug>/<slug>.md
```

`source: agent-mini-spec` is the marker that downstream skills (`/cook`, `/age`, etc.) can read if they ever want different taste-test stringency for agent-written vs handshake-approved specs. They are not required to act on it today. User-invoked-ceremony specs omit `source:` or use `source: mold-handshake`.

`## Provenance` appears only when `/cheese` reached tier 2 before falling into tier 1 — i.e., when `/culture` or `/briesearch` contributed context the original input lacked. Omit the section when tier 1 fires on the raw input. When `/briesearch` ran, the `artifact:` field links the durable cited research at `research/<slug>/<slug>.md` so the citations are preserved and `/cook` (or any later skill) can re-read them without re-researching. Omit `artifact:` only when `/briesearch` answered from local code patterns alone and wrote no durable file.

## Preferred tools and fallbacks

Code search, reading, and editing (including spec writing) all go through the `cheez-*` skills (`/cheez-search`, `/cheez-read`, `/cheez-write`) — see those skills for tool selection rules. Shape checks specifically use `cheez-search` callers (`kind: "callers"`) plus `tilth_deps`; the procedure lives in `references/shape-check.md`.

Beyond `cheez-*` there are mold-specific tools:

| Need | Prefer | Fallback |
| --- | --- | --- |
| External validation | `/briesearch` with Context7/Tavily | user-provided docs, repo docs, or note as unverified |
| Wiki grounding (Ground phase) | `mcp__hallouminate__list_corpora` + `mcp__hallouminate__ground` on `repo:<repo>:wiki` — see `references/grounding.md` | skip; proceed with code evidence only; cap at `speculating` when design rationale is central |

Optional tools accelerate the work; missing tools do not block the dialogue. When evidence is unavailable, mark the affected claim `[?]` until settled.

## Sub-agent context gate

`/mold` keeps the dialogue, contradictions, approval state, and the two-key handshake in the parent context — those never delegate. Offloading heavy work to a read-only sub-agent is the **default**, not an exception — it is the reliable lever for staying out of the model's degraded-attention band (`references/context-budget.md`). Spawn one whenever the work would flood the conversation with raw evidence or graph output:

- External validation needs deep `/briesearch` evidence, three or more doc fetches, or two or more independent search angles.
- Shape check touches more than 5 symbols, fans out across many modules, or requires large caller/dependency traversals.
- Diagnose mode needs bulky logs, traces, or search output before a concise root-cause hypothesis can be formed.
- A Prototype Cycle builds a throwaway to settle an ungrillable design unknown — the build always runs in a sub-agent worktree (`references/prototype-cycle.md`).

The sub-agent returns a ≤2 KB digest: a claim table, shape-check summary, prototype answer, or root-cause evidence summary with citations and confidence. The parent reads that digest, asks the user the smallest useful next question, and still owns the handshake. Do not spawn sub-agents for normal dialogue, the approval gate, or curdle/spec writing.

Digest size, parent-vs-sub-agent split, and harness-agnostic sub-agent selection live in the shared kernel at `skills/age/references/sub-agent-gate.md`.

### Context budget

The dialogue itself has a window budget. As the estimated context fills, nudge the user — advisory near ~120k tokens (prefer sub-agent offload, tighten questions), and suggest `/wheypoint` + resume-in-fresh-context near ~140k. The estimate is a heuristic nudge, not a hard gate; sub-agent offload above is the reliable lever. Full rule in `references/context-budget.md`.

### Gate graph

Mold's gate state machine is a single machine-readable model rendered two ways: `python3 ${CLAUDE_SKILL_DIR}/scripts/mold.pyz gate-graph --render dot|svg|png|mermaid`. `dot`/`mermaid` need no binary; `svg`/`png` use Graphviz `dot` when present and degrade to mermaid otherwise. The model's gate nodes are kept in lockstep with the `handshake.md` coherence checklist by a test, so a gate cannot be dropped from prose. Details in `references/gate-graph.md`.

## Approval gate

Curdle requires the **two-key handshake**: an explicit user verb (e.g. `curdle`, `ship it`) and the agent's coherence self-check. The full checklist, mandatory gates, and override semantics live in `references/handshake.md` — do not duplicate them here.

Before the handshake fires, also run the **agent-introduced-scope** check (`references/handshake.md` § Agent-introduced scope): list every distinguishing noun in Approach / Decisions / Interface sketches, grep the prior user turns for each, and flag any unmatched noun as `[AGENT-INTRODUCED]`. The user must explicitly approve each flagged item before extraction — silent inclusion of an agent-introduced feature is the cardinal sin. Curdle is the single chokepoint for this check; downstream skills (`/cook`, etc.) trust the spec frontmatter and do not re-block, so the gate must fully resolve here.

If any gate is unmet, propose the smallest next question or evidence check. Write artifacts only after both keys pass.

## Output paths

Resolve durable artifact locations through the resolver, never hardcode them:

- Spec: `python3 ${CLAUDE_SKILL_DIR}/scripts/mold.pyz artifact-path specs <slug>` (anchored at the per-project durable corpus — see `shared/formatting.md` § Corpus location).
- Issues: stay repo-local at `.cheese/issues/<slug>-001.md`, `.cheese/issues/<slug>-002.md`, ... — `issues` is a transient phase, not a durable-corpus artifact.

## --hard

`/mold --hard` propagates `--hard` through to `/cook` at handoff (any of the cook-flavoured options below carries the flag forward). Mold itself runs no gate — the metacognitive vibecheck fires later, at `/cure`'s share-for-review boundary. See `skills/hard-cheese/SKILL.md` and `skills/hard-cheese/references/composition.md`.

## Handoff

**Pipeline:** culture → **[mold]** → cook → press → age → cure → ship

After Curdle writes the spec, run the curd-count script with the shape-check verdict to compute the recommended downstream skill — full procedure in [`references/curd-count.md`](references/curd-count.md):

```bash
SPEC=$(python3 ${CLAUDE_SKILL_DIR}/scripts/mold.pyz artifact-path specs <slug>)
python3 ${CLAUDE_SKILL_DIR}/scripts/mold.pyz curd-count "$SPEC" --blast-radius <low|medium|high>
```

Omit `--blast-radius` when the shape-check verdict is `[?]` or skipped; the script accepts only `low|medium|high` and degrades to `/cook` for sub-threshold specs without the flag.

Read the JSON digest. Its `decomposable` field (true when `candidate_curds ≥ 5`) picks the option set rendered below; its `recommended_skill` field picks which option holds the *(recommended)* slot — subject to one user-confirmed override in the decomposable branch (see below). Then ask the user via the shared handoff gate in [`../../shared/handoff-gate.md`](../../shared/handoff-gate.md). Lead each option with the verb; the skill command (with the spec path and any in-scope `--hard` propagation) is the backing detail.

**Decomposable specs (`decomposable: true`, `candidate_curds ≥ 5`):**

The spec splits into many independent slices, so the natural fit is fan-out parallelism with reviewable PRs. Before rendering the menu, confirm with the user that the candidate curds are file-disjoint (criterion 4) — the script counts signals, it does not verify independence. **If the user confirms any two candidate curds share a file, override the digest's `recommended_skill`**: shift the *(recommended)* marker from `/cheese-factory` to `/ultracook` for this menu. The option list itself is unchanged.

- **Fan out into parallel curds with reviewable PRs** *(recommended when curds are file-disjoint)* — `/cheese-factory .cheese/specs/<slug>.md`. Spawns per-curd worker sub-agents; ends in 1–N reviewable PRs (published via a discovered `/pr-stack` skill when available, plain `gh` otherwise).
- **Run the full pipeline in fresh-context isolation** *(recommended when curds share files)* — `/ultracook .cheese/specs/<slug>.md`. Autonomous chain with each phase blind to prior phases.
- **Implement manually, one phase at a time** — `/cook .cheese/specs/<slug>.md`.
- **Stop** — dispatch none; leave the spec for later.

**Non-decomposable, high-blast-radius specs (`decomposable: false`, verdict `high` only):**

The spec is large enough that per-phase context contamination becomes a real concern: review reasoning softens when the same window contains the cook reasoning, and the parent context bloats across phases. Offer the fresh-context orchestrator and the manual compaction path:

- **Run the full pipeline in fresh-context isolation** *(recommended)* — `/ultracook .cheese/specs/<slug>.md`, autonomous chain (`cook → press → age → cure → age → cure → age`, all `--auto`) with each phase running inside its own sub-agent, blind to prior phases.
- **Implement manually, one phase at a time** — `/cook .cheese/specs/<slug>.md`.
- **Compact and resume by hand** — dispatch none; clear context, then dispatch `/cook .cheese/specs/<slug>.md` or `/ultracook .cheese/specs/<slug>.md` directly. (`/cheese --continue` scans phase handoff slugs only — fresh specs don't surface there until cook lands a slug — so dispatching the explicit command is the resumption path here.)
- **Stop** — dispatch none; leave the spec for later.

**Non-decomposable, low- or medium-blast-radius specs (`decomposable: false`, verdict `low` or `medium`):**

- **Implement the spec** *(recommended)* — `/cook .cheese/specs/<slug>.md`.
- **Implement and auto-review** — `/cook --auto .cheese/specs/<slug>.md`, chains straight through `/press → /age → /cure` autonomously, fixing every medium-or-above finding plus cheap (contained-fix) lows across up to two cure passes. Stops at the final cure pass; opening or updating the PR stays a manual step. Offer when acceptance criteria are explicit *and* the user has signalled they want the pipeline to run forward without per-step approval. In the user-invoked ceremony, never pre-select this option — auto mode is opt-in here because the user has stayed in the loop through the whole dialogue and the gate is the natural place to confirm autonomy. The agent-invoked mini-spec mode bypasses this gate entirely (no handoff prompt is rendered); `/cheese` dispatches `/cook --auto` directly from tier 1.
- **Research more first** — `/briesearch`, gather more external evidence before implementing.
- **Stop** — dispatch none; leave the spec for later.

`/cook --auto` is omitted from the decomposable and high-blast-radius offer sets: with many parallel curds or a wide footprint, fan-out parallelism (`/cheese-factory`) or fresh-context isolation (`/ultracook`) is the actual motivation for going autonomous, and the in-session chain is the wrong transport. Never pre-select an autonomous option; the user must opt in. `medium` blast radius keeps the standard handoff because the in-session `/cook --auto` chain is still the right tool for that footprint — the fresh-context premium is only worth paying when the spec actually crosses module boundaries broadly enough to flip the verdict to `high`, or when the spec decomposes into 5+ independent curds.

## Rules

- Dialogue first; artifacts are the by-product.
- Do not implement code.
- Do not write production files before the approval gate.
- Do not silently settle uncertain claims.
- Apply the shared voice kernel (lives at `skills/age/references/voice.md` in this repo): correct false premises, flag confidence as `certain | speculating | don't know` on each critical claim, steelman before dismissing, ask the smallest useful question while contributing at maximum useful depth.
