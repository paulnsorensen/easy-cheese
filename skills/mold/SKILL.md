---
name: mold
description: This skill should be used when the user has a fuzzy idea, half-formed feature, or design direction and wants to converge on a spec — phrases like "let's design X", "I'm thinking about Y", "what should the API for Z look like", "shape this into a spec", "I want to add a feature that…", "/mold". Runs an iterative dialogue (Explore / Ground / Shape / Sketch / Grill / Diagnose), grounds every load-bearing claim with cheez-search or briesearch, locks public seams in pseudocode, and only writes a spec to `.cheese/specs/<slug>.md` after an explicit approval gate. Use even when the user is "just thinking out loud" if they want the dialogue to leave behind a written artifact — for pure no-write thinking, route to `/culture` instead. After `/culture` (optional); before `/cook`.
license: MIT
---

# /mold

Use this skill when the user has a fuzzy feature idea, bug symptom, or design direction and wants a coherent spec or issue set before implementation.

Do not use it for free-form discussion with no artifact intent (`/culture`), direct implementation (`/cook`), or research-only questions (`/briesearch`).

## Flow

1. **Route** — pick a starting mode from the input shape (see `references/modes.md`) and announce it in one line.
2. **Dialogue** — build shared understanding through the smallest useful question. Ground every load-bearing claim with `cheez-search`, `cheez-read`, or a Validate Cycle (`references/validate-cycle.md`).
3. **Sketch** — for any feature touching >1 module or a new public interface, lock seams in pseudocode signatures before talking spec content.
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
| Grill | A favoured approach needs stress-testing | Find weak assumptions and edge cases |
| Diagnose | A symptom, failure, or trace is supplied | Build a Loop → reproduce → hypothesize → confirm root cause |

Full mode definitions, exit criteria, and user knobs in `references/modes.md`.

## Preferred tools and fallbacks

| Need | Prefer | Fallback |
| --- | --- | --- |
| External validation | `/briesearch` with Context7/Tavily | user-provided docs, repo docs, or note as unverified |
| Codebase grounding | cheez-search + cheez-read, code-review-graph for graph-shaped questions, Serena or LSP, `sg` | `ripgrep`, `find`, targeted file reads only after MCP/semantic paths cannot answer |
| Dependency/blast-radius checks | code-review-graph, then tilth deps | import searches, caller searches, test references |
| Spec writing | precise edit tooling | create/update markdown directly after approval |

Optional tools accelerate the work; missing tools do not block the dialogue. When a fallback is weaker, mark the affected claim `[?]` until settled.

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
- **Run /briesearch** — gather more external evidence first.
- **Stop** — leave the spec for later.

Pre-select `Run /cook` only when acceptance criteria are explicit and quality gates are runnable. Never auto-invoke; the user must select.

## Rules

- Dialogue first; artifacts are the by-product.
- Do not implement code.
- Do not write production files before the approval gate.
- Do not silently settle uncertain claims.
