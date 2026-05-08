---
name: mold
description: This skill should be used when the user has a fuzzy idea, half-formed feature, or design direction and wants to converge on a spec — phrases like "let's design X", "I'm thinking about Y", "what should the API for Z look like", "shape this into a spec", "I want to add a feature that…", "/mold". Runs an iterative dialogue (Explore / Ground / Shape / Sketch / Grill / Diagnose), grounds every load-bearing claim with cheez-search or briesearch, locks public seams in pseudocode, and only writes a spec to `.cheese/specs/<slug>.md` after an explicit approval gate. Use even when the user is "just thinking out loud" if they want the dialogue to leave behind a written artifact — for pure no-write thinking, route to `/culture` instead. After `/culture` (optional); before `/cook`.
license: MIT
---

# /mold

Use this skill when the user has a fuzzy feature idea, bug symptom, or design direction and wants a coherent spec or issue set before implementation.

Do not use it for free-form discussion with no artifact intent (`/culture`), direct implementation (`/cook`), or research-only questions (`/briesearch`).

## Flow

1. **Route** — pick a starting mode from the input shape (see `references/modes.md`) and announce it in one line. If the user's framing rests on a false premise or a loaded assumption, name it before routing.
2. **Dialogue** — build shared understanding through the smallest useful question to the user, but contribute at maximum useful depth between questions (full options, named edge cases, concrete evidence — not gestural sketches). Ground every load-bearing claim with `cheez-search`, `cheez-read`, or a Validate Cycle (`references/validate-cycle.md`). Track contradictions across turns; if turn N contradicts an earlier conclusion, flag and resolve it before continuing.
3. **Sketch** — for any feature touching >1 module or a new public interface, run the shape check (`references/shape-check.md`) on the touched symbols, then lock seams in pseudocode signatures before talking spec content. Default to full signatures, not hand-waving.
4. **Two-key handshake** — both the user (explicit verb) and the agent (coherence self-check) must agree before extraction. See `references/handshake.md`.
5. **Curdle** — write the approved spec to `.cheese/specs/<slug>.md` (and optional `.cheese/issues/<slug>-NNN.md`). Format and slug rules in `references/curdle.md`.
6. **Hand off** — once the spec is on disk, prompt the next step via `AskUserQuestion` (see `## Handoff` below). Never auto-invoke.

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

If any gate is unmet, propose the smallest next question or evidence check. Write artifacts only after both keys pass.

## Output paths

Default to project-local cheese artifacts when the user wants files:

- Spec: `.cheese/specs/<slug>.md`
- Issues: `.cheese/issues/<slug>-001.md`, `.cheese/issues/<slug>-002.md`, ...

## Handoff

After the spec is written, ask the user via `AskUserQuestion` which downstream to run. Default options:

- **Run /cook `.cheese/specs/<slug>.md`** *(recommended)* — implement the spec.
- **Run /cook --auto `.cheese/specs/<slug>.md`** — implement the spec and chain straight through `/press → /age → /cure` autonomously, fixing every medium-or-above finding across up to two cure passes. Offer when acceptance criteria are explicit *and* the user has signalled they want the pipeline to run forward without per-step approval. Never pre-select; auto mode is opt-in.
- **Run /briesearch** — gather more external evidence first.
- **Stop** — leave the spec for later.

Pre-select `Run /cook` (the gated form) only when acceptance criteria are explicit and quality gates are runnable. Never auto-invoke; the user must select.

## Rules

- Dialogue first; artifacts are the by-product.
- Do not implement code.
- Do not write production files before the approval gate.
- Do not silently settle uncertain claims.
- Apply the shared voice kernel (lives at `skills/age/references/voice.md` in this repo): correct false premises, flag confidence as `certain | speculating | don't know` on each load-bearing claim, steelman before dismissing, ask the smallest useful question while contributing at maximum useful depth.
