---
name: mold
description: This skill should be used when the user has a fuzzy idea, half-formed feature, or design direction and wants to converge on a spec — phrases like "let's design X", "I'm thinking about Y", "what should the API for Z look like", "shape this into a spec", "I want to add a feature that…", "/mold". Runs an iterative dialogue (Explore / Ground / Glossary / Shape / Sketch / Grill / Diagnose), grounds every critical claim with cheez-search or briesearch, locks public seams in pseudocode, optionally captures the domain glossary (CONTEXT.md) and architecture decision records, and only writes a spec to `.cheese/specs/<slug>.md` after an explicit approval gate. Use even when the user is "just thinking out loud" if they want the dialogue to leave behind a written artifact — for pure no-write thinking, route to `/culture` instead. After `/culture` (optional); before `/cook`.
license: MIT
---

# /mold

Use this skill when the user has a fuzzy feature idea, bug symptom, or design direction and wants a coherent spec or issue set before implementation.

Do not use it for free-form discussion with no artifact intent (`/culture`), direct implementation (`/cook`), or research-only questions (`/briesearch`).

## Flow

1. **Route** — pick a starting mode from the input shape (see `references/modes.md`) and announce it in one line. If the user's framing rests on a false premise or a loaded assumption, name it before routing.
2. **Dialogue** — build shared understanding through the smallest useful question to the user, but contribute at maximum useful depth between questions (full options, named edge cases, concrete evidence — not gestural sketches). Ground every critical claim with `cheez-search`, `cheez-read`, or a Validate Cycle (`references/validate-cycle.md`). Track contradictions across turns; if turn N contradicts an earlier conclusion, flag and resolve it before continuing.
3. **Sketch** — for any feature touching >1 module or a new public interface, run the shape check (`references/shape-check.md`) on the touched symbols, then lock seams in pseudocode signatures before talking spec content. Default to full signatures, not hand-waving.
4. **Two-key handshake** — both the user (explicit verb) and the agent (coherence self-check) must agree before extraction. See `references/handshake.md`.
5. **Curdle** — resolve the durable spec path with `SPEC=$(python3 ${CLAUDE_SKILL_DIR}/scripts/mold.pyz artifact-path specs <slug>)`, then write the approved spec to `"$SPEC"` (and optional issues alongside). The resolver anchors specs at the per-project durable corpus (see `shared/formatting.md` § Corpus location); never hardcode a `.cheese/specs/` path. Format and slug rules in `references/curdle.md`. If the dialogue pinned domain terms or surfaced ADR-worthy decisions, flush them to `CONTEXT.md` / `docs/adr/` at the same gate — see `references/domain-docs.md`.
6. **Hand off** — once the spec is on disk, run `python3 ${CLAUDE_SKILL_DIR}/scripts/mold.pyz curd-count "$SPEC" --blast-radius <low|medium|high>` to compute the recommended downstream skill (full procedure in `references/curd-count.md`). Omit `--blast-radius` when the shape-check verdict is `[?]` or shape-check was skipped — the script degrades to `/cook` for sub-threshold specs in that case. Then prompt the next step via the shared handoff gate in [`../../shared/handoff-gate.md`](../../shared/handoff-gate.md). Never dispatch before the user selects; after a non-stop selection, run the selected downstream skill immediately.

## Modes

| Mode | Use when | Goal |
| --- | --- | --- |
| Explore | The idea is vague | Identify the real problem and pain point |
| Ground | A file, bug, or existing doc is named | Verify facts against evidence |
| Glossary | Domain terms are fuzzy, conflicting, or a `CONTEXT.md` exists to challenge against | Pin the ubiquitous language; resolve term conflicts |
| Shape | The goal is known but approach is open | Compare viable options (Do Nothing always included) |
| Sketch | Interfaces or module boundaries matter | Lock responsibilities and seams |
| Grill | A favoured approach needs stress-testing | Steelman the rejected option, find weak assumptions and edge cases |
| Diagnose | A symptom, failure, or trace is supplied | Build a Loop → reproduce → hypothesize → confirm root cause |

Full mode definitions, exit criteria, and user knobs in `references/modes.md`.

## Preferred tools and fallbacks

Code search, reading, and editing (including spec writing) all go through the cheez-* skills (`/cheez-search`, `/cheez-read`, `/cheez-write`) — see those skills for tool selection rules. Shape checks specifically use `cheez-search` callers (`kind: "callers"`) plus `tilth_deps`; the procedure lives in `references/shape-check.md`.

Beyond cheez-* there are mold-specific tools:

| Need | Prefer | Fallback |
| --- | --- | --- |
| External validation | `/briesearch` with Context7/Tavily | user-provided docs, repo docs, or note as unverified |

Optional tools accelerate the work; missing tools do not block the dialogue. When evidence is unavailable, mark the affected claim `[?]` until settled.

## Sub-agent context gate

`/mold` keeps the dialogue, contradictions, approval state, and the two-key handshake in the parent context — those never delegate. Spawn a read-only grounding sub-agent only when validation would flood the conversation with raw evidence or graph output:

- External validation needs deep `/briesearch` evidence, three or more doc fetches, or two or more independent search angles.
- Shape check touches more than 5 symbols, fans out across many modules, or requires large caller/dependency traversals.
- Diagnose mode needs bulky logs, traces, or search output before a concise root-cause hypothesis can be formed.

The sub-agent returns a digest: a claim table, shape-check summary, or root-cause evidence summary with citations and confidence. The parent reads that digest, asks the user the smallest useful next question, and still owns the handshake. Do not spawn sub-agents for normal dialogue, the approval gate, or curdle/spec writing.

Digest size, parent-vs-sub-agent split, and harness-agnostic sub-agent selection live in the shared kernel at `skills/age/references/sub-agent-gate.md`.

## Approval gate

Curdle requires the **two-key handshake**: an explicit user verb (e.g. `curdle`, `ship it`) and the agent's coherence self-check. The full checklist, mandatory gates, and override semantics live in `references/handshake.md` — do not duplicate them here.

Before the handshake fires, also run the **agent-introduced-scope** check (`references/handshake.md` § Agent-introduced scope): list every distinguishing noun in Approach / Decisions / Interface sketches, grep the prior user turns for each, and flag any unmatched noun as `[AGENT-INTRODUCED]`. The user must explicitly approve each flagged item before extraction — silent inclusion of an agent-introduced feature is the cardinal sin. Curdle is the single chokepoint for this check; downstream skills (`/cook`, etc.) trust the spec frontmatter and do not re-block, so the gate must fully resolve here.

If any gate is unmet, propose the smallest next question or evidence check. Write artifacts only after both keys pass.

## Output paths

Resolve durable artifact locations through the resolver, never hardcode them:

- Spec: `python3 ${CLAUDE_SKILL_DIR}/scripts/mold.pyz artifact-path specs <slug>` (anchored at the per-project durable corpus — see `shared/formatting.md` § Corpus location).
- Issues: stay repo-local at `.cheese/issues/<slug>-001.md`, `.cheese/issues/<slug>-002.md`, ... — `issues` is a transient phase, not a durable-corpus artifact.
- Domain docs: repo-local at their literal paths — glossary at `CONTEXT.md` (root or per-context), ADRs at `docs/adr/NNNN-slug.md`. Written at the handshake, lazily, not through the resolver — see `references/domain-docs.md`.

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

- **Fan out into parallel curds with reviewable PRs** *(recommended when curds are file-disjoint)* — `/cheese-factory .cheese/specs/<slug>.md`. Spawns per-curd worker sub-agents; ends in 1–N reviewable PRs via `/pr-stack`.
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
- **Implement and auto-review** — `/cook --auto .cheese/specs/<slug>.md`, chains straight through `/press → /age → /cure` autonomously, fixing every medium-or-above finding plus cheap (contained-fix) lows across up to two cure passes. Stops at the final cure pass; opening or updating the PR stays a manual step. Offer when acceptance criteria are explicit *and* the user has signalled they want the pipeline to run forward without per-step approval. Never pre-select; auto mode is opt-in.
- **Research more first** — `/briesearch`, gather more external evidence before implementing.
- **Stop** — dispatch none; leave the spec for later.

`/cook --auto` is omitted from the decomposable and high-blast-radius offer sets: with many parallel curds or a wide footprint, fan-out parallelism (`/cheese-factory`) or fresh-context isolation (`/ultracook`) is the actual motivation for going autonomous, and the in-session chain is the wrong transport. Never pre-select an autonomous option; the user must opt in. `medium` blast radius keeps the standard handoff because the in-session `/cook --auto` chain is still the right tool for that footprint — the fresh-context premium is only worth paying when the spec actually crosses module boundaries broadly enough to flip the verdict to `high`, or when the spec decomposes into 5+ independent curds.

## Rules

- Dialogue first; artifacts are the by-product.
- Do not implement code.
- Do not write production files — including domain docs (CONTEXT.md, CONTEXT-MAP.md, ADRs) — before the approval gate. Accumulate them in the state ledger and flush at curdle (`references/domain-docs.md`).
- Do not silently settle uncertain claims.
- Apply the shared voice kernel (lives at `skills/age/references/voice.md` in this repo): correct false premises, flag confidence as `certain | speculating | don't know` on each critical claim, steelman before dismissing, ask the smallest useful question while contributing at maximum useful depth.

## Credits

The domain-documentation layer — the Glossary mode, `CONTEXT.md` as a ubiquitous-language glossary, lazy `CONTEXT-MAP.md` for bounded contexts, and the sparingly-offered ADR with its three-part test — is adapted from Matt Pocock's **grill-with-docs** skill (MIT): <https://github.com/mattpocock/skills/tree/main/skills/engineering/grill-with-docs>. mold integrates it behind the two-key handshake rather than writing docs inline.
