---
name: cheese
description: Route any dropped-in input — idea, spec path, file path, PR or issue, stack trace, bug report, or bare `/cheese` — to the right workflow skill and dispatch it immediately. Use as the unified entry point — phrases include "/cheese", "what should I do with this", "help me get started", "route this", "figure out what skill I need", or any opening message that does not already name a downstream skill. Classifies the input into an intent shape, announces the target and reason in a short three-line block (Intent / Reason / Target), then runs the chosen skill with the exact command and context packet. Add `--safe` to gate dispatch behind a confirmation prompt; otherwise cheese decides and acts. Before any other workflow skill.
license: MIT
---

# /cheese

Use this skill as the single front door to the easy-cheese workflow. Inspect whatever the user dropped in, classify it into an intent shape, announce the routing decision as a short three-line block (Intent / Reason / Target — see `## Output`), and dispatch immediately to the chosen skill. Cheese is autonomous by default — it picks the best target and runs it, only stopping to ask when `--safe` is passed or when the input is genuinely ambiguous.

Do not use it once a downstream skill is already running, or when the user has already named the skill they want (`/mold ...`, `/cook ...`, `/age`, etc.) — pass straight through to that skill instead.

## Inputs

Accept anything the user supplies as `$ARGUMENTS`:

- A natural-language feature description, idea, or question.
- A spec path (`.cheese/specs/<slug>.md`) or pasted spec content.
- A bug report, stack trace, failing test output, or reproduction steps.
- A file path, glob, or directory.
- A PR or issue reference (`PR#142`, `#87`, GitHub URL).
- A research question about an external library, API, or pattern.
- An empty or near-empty prompt — treat as "what's next?" and clarify.

Optional flags:

- `--safe` — gate dispatch behind a confirmation prompt. Use when the user wants the chance to redirect routing before the chosen skill runs. Without this flag, cheese announces and dispatches in the same turn. `--safe` also propagates downstream, re-introducing the per-skill gates that the autonomous default skips (`/age` / `/affinage` cure-selection, `/cure`'s PR push).
- `--open-pr` — propagate to `/cure` so a clean cure may open a *new* PR when none exists (the default only pushes an already-open one). Useful when routing a fresh branch through the pipeline and you want the PR created at the end.
- `--continue <slug>` — resume an in-flight pipeline from the latest handoff slug. See `## --continue` below.
- `--hard` — inject the `/hard-cheese` metacognitive gate before code is shared for review. The flag propagates to whichever target the router dispatches and fires at `/cure`'s share-for-review handoff (or end of `/cure`'s final auto pass under `--auto --hard`). See `skills/hard-cheese/SKILL.md`.

If `$ARGUMENTS` is missing entirely and there is no recent context to lean on, ask one clarifying question through the host routing guide in [`../../shared/handoff-gate.md`](../../shared/handoff-gate.md) before classifying.

## Flow

1. **Think first (silent).** Before announcing, model the problem internally per `skills/culture/SKILL.md` — restate the ask in one sentence, list the candidate targets, name the deciding signal. This is the agent's own reasoning, not a user-facing dialogue; the only output of this step is the classification decision that drives step 2.
2. **Classify** — match `$ARGUMENTS` against the intent shapes in `references/classification.md`. Pick the highest-confidence shape; below the threshold, route to `clarify` (handled by the tier-3 escalation in step 4).
3. **Clarity check (implementation intents only).** For `cook` and `mold` intents, run the cook fast-path check (`skills/cook/SKILL.md:30-35` — clear I/O, bounded scope, obvious verification). The result drives the three-tier escalation in `## Escalation` below. Non-implementation intents (`research`, `rubber-duck`, `debug`, `age`, `age-then-cure`, `cheese-factory`) skip the clarity check and route directly to their target skill.
4. **Escalate (if needed).** Tier 1 dispatches the chosen target (writing a mini-spec via `/mold`'s agent-invoked mode when the dispatch is `/cook --auto` and no spec path was supplied). Tier 2 autonomously invokes `/culture` and/or `/briesearch` in internal mode, then re-runs the clarity check. Tier 3 blocks on a single targeted host-routed question and re-enters classification on the answer. See `## Escalation`.
5. **Announce** — print a short three-line block (Intent / Reason / Target) per the format in `## Output`. Cite the signal that drove the routing decision.
6. **Self-check** — run the coherence questions in `references/coherence-check.md`. If any fails, downgrade to `clarify` (tier 3) or `research`.
7. **Dispatch** — without `--safe`, run the chosen skill immediately with its exact dispatch command and context packet, in the same turn as the announce. With `--safe`, issue a handoff gate per [`../../shared/handoff-gate.md`](../../shared/handoff-gate.md) (recommended target pre-selected, at least one alternative, `Stop`) and wait for the user's selection before dispatching. Either way the downstream skill owns its flow; `/cheese` does not narrate beyond the routing decision.

`/cheese` is a router, not a worker. It never edits files, runs tests, or opens PRs. It does invoke `/mold`'s agent-invoked mini-spec mode in tier 1 when a spec needs to materialise before `/cook --auto` can run; that write is the only file-touching `/cheese` ever does.

## Intent shapes

| Intent | Trigger signals | Pre-step | Target skill |
| --- | --- | --- | --- |
| clarify | Empty input, single keyword, or critical ambiguity | host-routed question for the missing fact | re-enter `/cheese` once answered |
| research | Library / API / vendor question, "what's the best…", comparison | — | `/briesearch` |
| rubber-duck | User explicitly asks for discussion only — "no writes", "let's just talk", "rubber-duck this" — with no artifact intent | — | `/culture` |
| mold | Feature description with fuzzy scope, multi-module idea, or stated need for a spec | optional `/briesearch` first if external evidence is missing | `/mold` → `/cook` |
| cook | Spec path, focused fix with clear inputs/outputs/verification, single-file tweak | — | `/cook --auto` (default) — chains through `/press → /age → /cure` |
| cheese-factory | Approved spec at `.cheese/specs/<slug>.md` with 5+ acceptance criteria / behavioural curds, or user phrases like "send through the factory", "parallelize", "many curds", "fan out" | — | `/cheese-factory` |
| debug | Stack trace, failing test, reproduction steps, "why is X broken", visual bug + repro path | — | `/pasteurize --auto` (default) → `/cook --auto` |
| age | PR reference, file path/glob review request, "is this safe to merge", "find bugs" | — | `/age` |
| age-then-cure | Existing `.cheese/age/<slug>.md` plus a "fix the findings" instruction | — | `/age` (re-scope if needed) → `/cure` |

`/culture` is otherwise an internal-use skill the agent invokes during step 1 of the flow to think through routing — it is not a default user-facing target. Only surface it when the user has explicitly opted out of writes for this session.

The full classification table — including disambiguation rules, edge cases, and confidence cues — lives in `references/classification.md`.

## Escalation

For implementation intents (`cook` and `mold`), `/cheese` runs the cook fast-path check from `skills/cook/SKILL.md:30-35` (clear I/O, bounded scope, obvious verification) and escalates through three tiers based on the result:

**Tier 1 — clear (all three checks pass).** Agent invokes `/mold`'s agent-invoked mini-spec mode (see `skills/mold/SKILL.md` § Agent-invoked mini-spec mode) to write `.cheese/specs/<slug>.md`, then dispatches `/cook --auto <spec-path>` in the same turn as the announce, where `<spec-path>` is the explicit mini-spec path returned by `/mold`. Do not collapse that path to a bare `<slug>`. No user interaction. When the input already names a spec path under `.cheese/specs/`, skip the mini-spec write and dispatch `/cook --auto` against the existing path directly.

**Tier 2 — borderline (any check fails or is uncertain).** Agent autonomously invokes `/culture` (internal-mode thinking) and/or `/briesearch` (internal-mode research) — agent's choice each call, no fixed order, no requirement to run both — to fill the missing context. After the internal pass, re-run the cook fast-path check on the refined understanding. If all three checks now pass, drop into tier 1 (the mini-spec records the culture / briesearch synthesis under `## Provenance`). Otherwise tier 3.

**Tier 3 — still borderline after tier 2.** Block on the human via a single targeted host-routed question whose answer closes the failing check. On the answer, re-enter classification with the augmented input. This is the only sanctioned user-facing prompt in the autonomous-by-default path; the `clarify` intent and the below-`medium`-confidence path both map here.

`--safe` does not skip the escalation logic — the tiers still run silently — but it inserts a handoff gate before the final dispatch in every tier. The recommended option stays auto-flavoured (`/cook --auto <spec-path>` etc., using the explicit mini-spec path); the non-auto variant is offered as the alternative.

Non-implementation intents bypass the escalation entirely. Their target skills own their own internal escalation: `/pasteurize` has its Phase 1 feedback-loop check, `/briesearch` clarifies missing version/scope inline, `/age` and `/cure` work directly against the supplied diff or report.

## --continue

`/cheese --continue <slug>` is the manual fresh-context resumption path. Use it after compacting the conversation, after `/ultracook` has stopped on a halt, or whenever the user wants to drive the pipeline by hand from a cleared context.

Flow:

1. Scan for the most recently modified handoff slug across `.cheese/{cook,press,age,cure,affinage,notes}/<slug>.md`.
2. If none exist, offer to start the pipeline from scratch — `/mold` for fuzzy specs, `/cook` for clear asks, `/ultracook` for high-blast-radius specs — and stop.
3. If at least one exists, read the latest one and surface the orientation line so the user knows where they are. Decide the next action from the slug's `next:` field:
   - **When `next:` names a phase** (`mold | cook | press | age | cure | affinage | ultracook`) — dispatch `/\<next\> \<slug\>` directly. `affinage` is the exception: it takes a PR ref, not a slug, so read the PR from the slug's `artifact:` field (`PR#<n>` or its URL) and dispatch `/affinage <pr>`; fall back to a bare `/affinage` (branch auto-detect) only when `artifact:` carries no PR. Under `--safe`, offer it as the pre-selected option, with `/ultracook \<slug\>` as an alternative and `Stop` last.
   - **When `next:` is terminal** (`done` from a phase slug, or `stop` from a culture-notes slug — the pipeline already finished) — report the terminal state and stop. The terminal values surface state to the user, not a runnable command; never construct `/done <slug>` or `/stop <slug>`.

Under `--safe`, gate the resumption through the handoff gate in [`../../shared/handoff-gate.md`](../../shared/handoff-gate.md); otherwise run the named phase immediately with the slug. The slug files are the resumability contract: they tell the router where the pipeline is and how to move it forward.

`--continue` does *not* propagate `--auto`. The "manual fresh-context resumption path" framing is intentional: resuming after a compact or halt is a moment to drive the pipeline by hand, not to silently re-enter an autonomous chain. Dispatch `/<next> <slug>` — without `--auto` — even when no `--safe` flag is present. The user can append `--auto` explicitly (`/cheese --continue <slug> --auto`) to opt back into auto-mode propagation; otherwise the dispatched phase runs in its default interactive mode.

## Confidence and the clarify gate

Treat classification confidence qualitatively (`low | medium | high`). Threshold for direct routing is `medium` or better. Below that, route to tier 3 (`clarify`):

- Ask exactly one question through the host routing guide in [`../../shared/handoff-gate.md`](../../shared/handoff-gate.md).
- Offer the two most-likely targets as alternatives plus `Stop`.
- Re-enter `/cheese` with the answer.

At `medium` or above, dispatch — don't second-guess a clear signal with extra questions. For implementation intents, the cook-fast-path clarity check in `## Escalation` is the additional layer: low intent confidence sends you to tier 3 directly, while a confident-intent + borderline-clarity input goes through tier 2 first. Silent misrouting is worse than asking once, but reflexive gating is worse than acting on a confident read.

## Preferred tools and fallbacks

When the input is a path or slug, code reading and searching go through the `cheez-*` skills (`/cheez-read`, `/cheez-search`) — see those skills for tool selection rules.

Beyond `cheez-*` there are router-specific tools:

| Need | Prefer | Fallback |
| --- | --- | --- |
| PR / issue context | `gh` | the URL or numbers the user provided |
| Confirming routing target with the user (only under `--safe` or `clarify`) | host-routed structured question per [`../../shared/handoff-gate.md`](../../shared/handoff-gate.md) | a numbered list with explicit dispatch commands |

`/cheese` keeps tool use light. Treat anything heavier than a single-file read or one search call as a sign the work belongs in the downstream skill, not in the router.

## Output

Always emit, in order:

1. **Detected intent** — one line, e.g. `Intent: cook (clear single-file fix)`.
2. **Reason** — one line citing the signal (`reason: spec path .cheese/specs/foo.md`).
3. **Target** — the chosen skill, e.g. `Target: /cook .cheese/specs/foo.md`.

Then dispatch the target in the same turn. Under `--safe`, append a handoff gate (recommended target pre-selected, one alternative, `Stop`, exact dispatch records for every non-stop option) and wait for the user before dispatching. If `clarify` is chosen, replace the dispatch with the single clarifying question.

## Handoff

Dispatch happens through [`../../shared/handoff-gate.md`](../../shared/handoff-gate.md) when `--safe` is set; otherwise cheese runs the target directly. Without `--safe`, cheese propagates `--auto` to any target that supports it, so the chain runs all the way through without per-step gates. Under `--safe`, dispatch waits for the user's selection, but the auto variant remains the pre-selected recommended target (the non-auto variant is offered as the alternative).

Default targets per intent:

- **clarify** — single targeted question; no skills run until the answer arrives.
- **research** — `/briesearch` (recommended). No auto variant.
- **rubber-duck** — `/culture` (recommended). Only reached when the user explicitly opted out of writes. No auto variant.
- **mold** — `/mold` (recommended). Safe-mode alternative: `/briesearch first` when external evidence is missing.
- **cook** — default: `/cook --auto <slug-or-path>`. Safe-mode alternatives: `/cook <slug-or-path>` (no auto), `/mold first` if scope is borderline.
- **cheese-factory** — `/cheese-factory <slug-or-path>` (recommended when the spec decomposes into 5+ curds). Safe-mode alternative: `/ultracook <slug-or-path>` (sequential pipeline).
- **debug** — default: `/pasteurize --auto <input>`. Safe-mode alternatives: `/pasteurize <input>` (no auto), `/culture` only when the user explicitly wants no-write diagnosis.
- **age** — `/age <ref>` (recommended). Safe-mode alternative: `/age --scope <path>` when the user named a path glob.
- **age-then-cure** — `/age <slug>` (recommended). Safe-mode alternative: `/cure <slug>` when a fresh report already exists.

Pre-select only the highest-confidence target. Without `--safe`, surface the target as a decision, not a question — dispatch the recommended option directly. With `--safe`, dispatch waits for the user's selection; the captured dispatch packet runs immediately on a non-stop choice.

## Rules

- Default mode is autonomous: announce the routing decision and dispatch in the same turn. `--safe` is the only switch that re-introduces a confirmation prompt.
- Implementation intents (`cook`, `mold`) go through the cook-fast-path clarity check and escalate through the three tiers in `## Escalation`. Other intents dispatch directly.
- Below `medium` intent confidence — or when a coherence check trips — route to tier 3 (`clarify`) instead of guessing. One clarifying question, max, before re-entering classification.
- The only file `/cheese` ever writes is a mini-spec at `.cheese/specs/<slug>.md` via `/mold`'s agent-invoked mode, and only when tier 1 needs one before dispatching `/cook --auto`. No code edits, no tests, no quality gates.
- Never paraphrase or summarise downstream skill output — that is the downstream skill's job.

## References

- `references/classification.md` — intent shapes, signals, disambiguation rules.
- `references/coherence-check.md` — pre-dispatch self-checks that downgrade misroutes.
- [`../../shared/handoff-gate.md`](../../shared/handoff-gate.md) — Codex-safe post-selection dispatch contract (shared across workflow skills).
