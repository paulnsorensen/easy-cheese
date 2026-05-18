---
name: mold
description: This skill should be used when the user has a fuzzy idea, half-formed feature, or design direction and wants to converge on a spec — phrases like "let's design X", "I'm thinking about Y", "what should the API for Z look like", "shape this into a spec", "I want to add a feature that…", "/mold". Runs an iterative dialogue (Explore / Ground / Shape / Sketch / Grill / Diagnose), grounds every critical claim with cheez-search or briesearch, locks public seams in pseudocode, and only writes a spec to `.cheese/specs/<slug>.md` after an explicit approval gate. Use even when the user is "just thinking out loud" if they want the dialogue to leave behind a written artifact — for pure no-write thinking, route to `/culture` instead. After `/culture` (optional); before `/cook`.
license: MIT
---

# /mold

Use this skill when the user has a fuzzy feature idea, bug symptom, or design direction and wants a coherent spec or issue set before implementation.

Do not use it for free-form discussion with no artifact intent (`/culture`), direct implementation (`/cook`), or research-only questions (`/briesearch`).

## Flow

1. **Ground the repo** — run the orientation read-or-write procedure in [`../../shared/orientation.md`](../../shared/orientation.md) before mode routing. If `.cheese/orient/<slug>.md` already exists (likely if `/cheese` or `/culture` ran first this session), load it; otherwise build it from the five-step recipe and load. Print the one-line acknowledgement. Mode routing in step 2 reads against this snapshot, not against a blind input parse.
2. **Route** — pick a starting mode from the input shape (see `references/modes.md`) and announce it in one line. If the user's framing rests on a false premise or a loaded assumption, name it before routing.
3. **Dialogue** — build shared understanding through the smallest useful question to the user, but contribute at maximum useful depth between questions (full options, named edge cases, concrete evidence — not gestural sketches). Ground every critical claim with `cheez-search`, `cheez-read`, or a Validate Cycle (`references/validate-cycle.md`). Track contradictions across turns; if turn N contradicts an earlier conclusion, flag and resolve it before continuing.
4. **Sketch** — for any feature touching >1 module or a new public interface, run the shape check (`references/shape-check.md`) on the touched symbols, then lock seams in pseudocode signatures before talking spec content. Default to full signatures, not hand-waving.
5. **Two-key handshake** — both the user (explicit verb) and the agent (coherence self-check) must agree before extraction. See `references/handshake.md`.
6. **Curdle** — write the approved spec to `.cheese/specs/<slug>.md` (and optional `.cheese/issues/<slug>-NNN.md`). Format and slug rules in `references/curdle.md`.
7. **Hand off** — once the spec is on disk, prompt the next step via the shared handoff gate in [`../../shared/handoff-gate.md`](../../shared/handoff-gate.md). Never dispatch before the user selects; after a non-stop selection, run the selected downstream skill immediately.

Repo-level orientation (step 1) and symbol-level shape check (step 4) are deliberately separate: orientation tells you what the codebase *is*, the shape check tells you what a specific seam *touches*. Both are cached read-only artifacts under `.cheese/`; neither blocks the dialogue.

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

Default to project-local cheese artifacts when the user wants files:

- Spec: `.cheese/specs/<slug>.md`
- Issues: `.cheese/issues/<slug>-001.md`, `.cheese/issues/<slug>-002.md`, ...

## --hard

`/mold --hard` propagates `--hard` through to `/cook` at handoff (any of the cook-flavoured options below carries the flag forward). Mold itself runs no gate — the metacognitive vibecheck fires later, at `/cure`'s share-for-review boundary. See `skills/hard-cheese/SKILL.md` and `skills/hard-cheese/references/composition.md`.

## Handoff

**Pipeline:** culture → **[mold]** → cook → press → age → cure → ship

After the spec is written, ask the user via the shared handoff gate in [`../../shared/handoff-gate.md`](../../shared/handoff-gate.md). Lead each option with the verb (what the user wants to *do* next); the skill command (with the spec path and any in-scope `--hard` propagation) is the backing detail. Default options vary with the shape-check verdict:

**Low- and medium-blast-radius specs (verdict `low` or `medium`):**

- **Implement the spec** *(recommended)* — `/cook .cheese/specs/<slug>.md`.
- **Implement and auto-review** — `/cook --auto .cheese/specs/<slug>.md`, chains straight through `/press → /age → /cure` autonomously, fixing every medium-or-above finding across up to two cure passes. Stops at the final cure pass; opening or updating the PR stays a manual step. Offer when acceptance criteria are explicit *and* the user has signalled they want the pipeline to run forward without per-step approval. Never pre-select; auto mode is opt-in.
- **Research more first** — `/briesearch`, gather more external evidence before implementing.
- **Stop** — dispatch none; leave the spec for later.

**High-blast-radius specs (verdict `high` only):**

The spec is large enough that per-phase context contamination becomes a real concern: review reasoning softens when the same window contains the cook reasoning, and the parent context bloats across phases. Offer the fresh-context orchestrator and the manual compaction path:

- **Run the full pipeline in fresh-context isolation** *(recommended)* — `/ultracook .cheese/specs/<slug>.md`, autonomous chain (`cook → press → age → cure → age → cure → age`, all `--auto`) with each phase running inside its own sub-agent, blind to prior phases.
- **Implement manually, one phase at a time** — `/cook .cheese/specs/<slug>.md`.
- **Compact and resume by hand** — dispatch none; clear context, then dispatch `/cook .cheese/specs/<slug>.md` or `/ultracook .cheese/specs/<slug>.md` directly. (`/cheese --continue` scans phase handoff slugs only — fresh specs don't surface there until cook lands a slug — so dispatching the explicit command is the resumption path here.)
- **Stop** — dispatch none; leave the spec for later.

`/cook --auto` is omitted from the high-blast-radius offer set: with a large footprint, the fresh-context property of `/ultracook` is the actual motivation for going autonomous, and the in-session chain it offers is the wrong transport for that need. Never pre-select an autonomous option; the user must opt in. `medium` blast radius keeps the standard handoff because the in-session `/cook --auto` chain is still the right tool for that footprint — the fresh-context premium is only worth paying when the spec actually crosses module boundaries broadly enough to flip the verdict to `high`.

## Rules

- Dialogue first; artifacts are the by-product.
- Do not implement code.
- Do not write production files before the approval gate. The shared orientation cache at `.cheese/orient/<slug>.md` (per [`../../shared/orientation.md`](../../shared/orientation.md)) is the one exception, written only on cache miss.
- Do not silently settle uncertain claims.
- Apply the shared voice kernel (lives at `skills/age/references/voice.md` in this repo): correct false premises, flag confidence as `certain | speculating | don't know` on each critical claim, steelman before dismissing, ask the smallest useful question while contributing at maximum useful depth.
