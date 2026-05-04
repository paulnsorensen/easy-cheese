---
name: mold
description: Shape a fuzzy idea into a grounded spec through dialogue, evidence checks, interface sketches, and an explicit approval gate.
license: MIT
---

# /mold

Use this skill when the user has a fuzzy feature idea, bug symptom, or design direction and wants a coherent spec or issue set before implementation.

Do not use it for free-form discussion with no artifact intent (`/culture`), direct implementation (`/cook`), or research-only questions (`/briesearch`).

## Flow

1. Pick a starting mode from the user's input and announce it in one line.
2. Build shared understanding through the smallest useful dialogue.
3. Ground load-bearing claims with code, docs, or `/briesearch` evidence.
4. Compare options, including Do Nothing when relevant.
5. Sketch public seams in pseudocode before writing a spec.
6. Run a coherence check and ask for explicit approval before writing artifacts.
7. Write only the approved spec or issue drafts, then suggest the next skill.

## Modes

| Mode | Use when | Goal |
| --- | --- | --- |
| Explore | The idea is vague | Identify the real problem and pain point |
| Ground | A file, bug, or existing doc is named | Verify facts against evidence |
| Shape | The goal is known but approach is open | Compare viable options |
| Sketch | Interfaces or module boundaries matter | Lock responsibilities and seams |
| Grill | A favored approach needs stress-testing | Find weak assumptions and edge cases |
| Diagnose | A symptom, failure, or trace is supplied | Reproduce and isolate root cause before spec |

## Preferred tools and fallbacks

| Need | Prefer | Fallback |
| --- | --- | --- |
| External validation | `/briesearch` with Context7/Tavily | user-provided docs, repo docs, or note as unverified |
| Codebase grounding | Serena or LSP, `sg`, tilth read/search | `ripgrep`, `find`, targeted file reads |
| Dependency/blast-radius checks | code review graph, tilth deps | import searches, caller searches, test references |
| Spec writing | precise edit tooling | create/update markdown directly after approval |

Optional tools accelerate the work; missing tools do not block the dialogue. When a fallback is weaker, mark the affected claim `[?]` until settled.

## Approval gate

Before writing, present this check:

- [ ] Problem statement is clear and grounded.
- [ ] Chosen option and non-goals are explicit.
- [ ] Public seams or affected modules are sketched when relevant.
- [ ] Open questions are marked `[TBD]`, `[BLOCKED]`, or `[?]`.
- [ ] Quality gates or reproduction steps are named.
- [ ] User approved artifact type, slug, and target path.

If any item is unchecked, propose the smallest next question or evidence check. Write artifacts only after approval.

## Output paths

Default to project-local cheese artifacts when the user wants files:

- Spec: `.cheese/specs/<slug>.md`
- Issues: `.cheese/issues/<slug>-001.md`, `.cheese/issues/<slug>-002.md`, ...

## Rules

- Dialogue first; artifacts are the by-product.
- Do not implement code.
- Do not write production files before the approval gate.
- Do not silently settle uncertain claims.
