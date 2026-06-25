---
name: cheese
description: Route any dropped-in input — idea, spec path, file path, PR or issue, stack trace, bug report, or bare `/cheese` — to the right workflow skill and dispatch it immediately. Use as the unified entry point — phrases include "/cheese", "what should I do with this", "help me get started", "route this", "figure out what skill I need", or any opening message that does not already name a downstream skill. Classifies the input into an intent shape, announces the target and reason in a short three-line block (Intent / Reason / Target), then runs the chosen skill with the exact command and context packet. Add `--safe` to gate dispatch behind a confirmation prompt; otherwise cheese decides and acts. Before any other workflow skill.
license: MIT
---

# /cheese

Always emit a short three-line routing block (Intent / Reason / Target — see `## Output`) before dispatching.

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
- `--continue <slug-or-note-path>` — resume an in-flight pipeline from a handoff slug, or from an explicit `.cheese/.../<slug>.md` note path when outside the original repo. See `## --continue` below.
- `--hard` — inject the `/hard-cheese` metacognitive gate before code is shared for review. The flag propagates to whichever target the router dispatches and fires at `/cure`'s share-for-review handoff (or end of `/cure`'s final auto pass under `--auto --hard`). See `skills/hard-cheese/SKILL.md`.

If `$ARGUMENTS` is missing entirely and there is no recent context to lean on, ask one clarifying question through the host routing guide in [`../../shared/handoff-gate.md`](../../shared/handoff-gate.md) before classifying.

## Flow

1. **Think first (silent).** Before announcing, model the problem internally per `skills/culture/SKILL.md` — restate the ask in one sentence, list the candidate targets, name the deciding signal. This is the agent's own reasoning, not a user-facing dialogue; the only output of this step is the classification decision that drives step 2.
2. **Classify** — match `$ARGUMENTS` against the intent shapes in `references/classification.md`. Pick the highest-confidence shape; below the threshold, route to `clarify` (handled by the tier-3 escalation in step 4).
3. **Clarity check (implementation intents only).** For `cook` and `mold` intents, run cook's fast-path check (§ "Standalone fast-path" in `skills/cook/SKILL.md` — clear I/O, bounded scope, obvious verification). The result drives the three-tier escalation in `## Escalation` below. Non-implementation intents (`research`, `rubber-duck`, `debug`, `age`, `age-then-cure`, `cheese-factory`) skip the clarity check and route directly to their target skill.
4. **Escalate (if needed).** Tier 1 dispatches the chosen target (writing a mini-spec via `/mold`'s agent-invoked mode when the dispatch is `/cook --auto` and no spec path was supplied). Tier 2 autonomously invokes `/culture` and/or `/briesearch` in internal mode, then re-runs the clarity check. Tier 3 blocks on a single targeted host-routed question and re-enters classification on the answer. See `## Escalation`.
5. **Announce** — print a short three-line block (Intent / Reason / Target) per the format in `## Output`. Cite the signal that drove the routing decision.
6. **Self-check** — run the coherence questions in `references/coherence-check.md`. If any fails, downgrade to `clarify` (tier 3) or `research`.
7. **Dispatch** — without `--safe`, run the chosen skill immediately with its exact dispatch command and context packet, in the same turn as the announce. With `--safe`, issue a handoff gate per [`../../shared/handoff-gate.md`](../../shared/handoff-gate.md) (recommended target pre-selected, at least one alternative, `Stop`) and wait for the user's selection before dispatching. Either way the downstream skill owns its flow; `/cheese` does not narrate beyond the routing decision.

`/cheese` is a router, not a worker. It never edits files, runs tests, or opens PRs. It does invoke `/mold`'s agent-invoked mini-spec mode in tier 1 when a spec needs to materialise before `/cook --auto` can run; that write is the only file-touching `/cheese` ever does.

## Intent shapes

The full classification table — including all intent shapes, signals, disambiguation rules, and edge cases — lives in `references/classification.md`.

## Escalation

For implementation intents (`cook` and `mold`), `/cheese` runs cook's fast-path check (§ "Standalone fast-path" in `skills/cook/SKILL.md` — clear I/O, bounded scope, obvious verification) and escalates through three tiers based on the result:

**Tier 1 — clear (all three checks pass).** Agent invokes `/mold`'s agent-invoked mini-spec mode (see `skills/mold/SKILL.md` § Agent-invoked mini-spec mode) to write `.cheese/specs/<slug>.md`, then dispatches `/cook --auto <spec-path>` in the same turn as the announce, where `<spec-path>` is the explicit mini-spec path returned by `/mold`. Do not collapse that path to a bare `<slug>`. No user interaction. When the input already names a spec path under `.cheese/specs/`, skip the mini-spec write and dispatch `/cook --auto` against the existing path directly.

**Tier 2 — borderline (any check fails or is uncertain).** Agent autonomously invokes `/culture` (internal-mode thinking) and/or `/briesearch` (internal-mode research) — agent's choice each call, no fixed order, no requirement to run both — to fill the missing context. After the internal pass, re-run the cook fast-path check on the refined understanding. If all three checks now pass, drop into tier 1 (the mini-spec records the culture / briesearch synthesis under `## Provenance`). Otherwise tier 3.

**Tier 3 — still borderline after tier 2.** Block on the human via a single targeted host-routed question whose answer closes the failing check. On the answer, re-enter classification with the augmented input. This is the only sanctioned user-facing prompt in the autonomous-by-default path; the `clarify` intent and the below-`medium`-confidence path both map here.

`--safe` does not skip the escalation logic — the tiers still run silently — but it inserts a handoff gate before the final dispatch in every tier. The recommended option stays auto-flavoured (`/cook --auto <spec-path>` etc., using the explicit mini-spec path); the non-auto variant is offered as the alternative.

Non-implementation intents bypass the escalation entirely. Their target skills own their own internal escalation: `/pasteurize` has its Phase 1 feedback-loop check, `/briesearch` clarifies missing version/scope inline, `/age` and `/cure` work directly against the supplied diff or report.

## --continue

`/cheese --continue <slug-or-note-path>` is the manual fresh-context resumption path. Use it after compacting the conversation, after `/ultracook` has stopped on a halt, or whenever the user wants to drive the pipeline by hand from a cleared context.

Flow:

1. If the argument is a readable `.md` handoff path, read that file directly and derive `<slug>` from its basename. If the path contains a `.cheese/` parent, treat the directory above `.cheese/` as the original repo root for any repo-relative paths in the handoff.
2. Otherwise, scan for the most recently modified handoff slug across `.cheese/{cook,press,age,cure,affinage,notes}/<slug>.md`.
3. If none exist, offer to start the pipeline from scratch — `/mold` for fuzzy specs, `/cook` for clear asks, `/ultracook` for high-blast-radius specs — and stop.
4. If a handoff exists, read it and surface the orientation line so the user knows where they are. Parse `status:`, `next:`, and optional `mode:`:
   - **First parse optional `mode:`.** Missing `mode:` means `mode: single`, preserving all existing handoffs. In `mode: single`, `next:` remains the runnable phase and the existing bullets below apply. In `mode: parallel`, `next:` is only the coarse resume category; prefer `next: tasks` when the handoff may mix skills. Never dispatch `next:` directly in parallel mode. Instead parse the handoff's optional `parallel:` block and required `tasks:` list, where each item carries an explicit `command:` such as `/ultracook .cheese/specs/kip-77-ai-test-server.md`, `/briesearch ...`, or `/affinage <pr>`.
   - **When `mode: parallel` and `tasks:` is present** — dispatch one isolated agent per task in the same response / same turn so the tasks run concurrently. Each agent receives the original handoff path, repo root, task name/slug if present, exact `command:`, any task-local branch/worktree notes, and an instruction to work only that task and not run sibling tasks. Use the task `command:` as authoritative even when tasks name different skills or intents. For write-capable commands (`/cook`, `/ultracook`, `/cure`, `/affinage`, or any command expected to edit a branch), require `slug`, `repo`, `branch:`, `branch_from`, and a checkout-isolation plan. Supported `parallel.worktree_strategy` values are `existing` (every write task declares a distinct `worktree:`), `create` (create one git worktree per task under `worktree_root` from `branch_from`), and `harness` (ask/create one harness-managed isolated thread or worktree per task). Never run parallel write tasks in the same checkout or a shared checkout. If `tasks:` is missing, any task lacks `command:`, write tasks lack branch/worktree isolation, branches collide, worktrees collide, or the strategy is unsupported, stop and ask for a corrected handoff instead of guessing. Under `--safe`, offer the parallel dispatch as the pre-selected option, with `Stop` last.
   - **When `status:` starts with `halt` and `next:` names a phase** (`mold | cook | press | age | cure | affinage | ultracook`) — surface the halt reason, then treat `/cheese --continue <slug>` as the user's explicit permission to dispatch the next phase. `affinage` is the exception: it takes a PR ref, not a slug, so read the PR from the slug's `artifact:` field (`PR#<n>` or its URL) and dispatch `/affinage <pr>`; fall back to a bare `/affinage` (branch auto-detect) only when `artifact:` carries no PR. Under `--safe`, offer the dispatch as the pre-selected option, with `/ultracook \<slug\>` as an alternative and `Stop` last.
   - **When `status:` is `ok` and `next:` names a pipeline phase** (`mold | cook | press | age | cure | affinage`) — dispatch `/\<next\> \<slug\>` directly, with the same `affinage` exception above. Under `--safe`, offer it as the pre-selected option, with `/ultracook \<slug\>` as an alternative and `Stop` last.
   - **When `status:` is `ok` and `next:` names a read-only kickoff** (`briesearch | culture`) — auto-dispatch it directly (`/briesearch \<arg\>`, `/culture`), taking `\<arg\>` from the handoff's orientation line. These are read-only and low-risk, so frictionless dispatch is the goal; do not gate them behind a question. Under `--safe`, offer the dispatch as the pre-selected option with `Stop` last.
   - **When `status:` starts with `gated:`** — do *not* auto-dispatch `next:`, whatever it names. Surface the one-line decision from `status:` plus the body's open-questions/blockers, then ask the user which direction: **research / decide / build**. Dispatch nothing until the user picks; on the pick, route research → `/briesearch`, build → the named phase, decide → resolve the decision with the user, then re-read the handoff. Never fire a binary design popup that presumes the user wants to decide.
   - **When `next:` is a list** (`next: [<skill> "<arg>", ...]`) — `order:` is required; if it is missing, stop and ask for a corrected handoff. The inline list accepts only read-only skills (`briesearch | culture`); if any item names a write or pipeline skill, reject it and point at the heavyweight `mode: parallel` + `tasks:` block (which carries the worktree/branch isolation those skills need). With `order: parallel`, dispatch one read agent per item in the same turn so they run concurrently; with `order: sequential`, dispatch the items in listed order. Under `--safe`, offer the batch dispatch as the pre-selected option with `Stop` last.
   - **When `next:` is `hold`** — surface the orientation line and stop without dispatching. `hold` means restore context and wait for instruction; it is not a runnable command. Distinct from `done` (terminal record) — `hold` is a live session paused for input.
   - **When `next:` is missing entirely** — flag the handoff as malformed (`malformed handoff: next: required`) and stop. Do not guess a next step or default to a phase; `hold` is the author's value for "no action."
   - **When `next:` is terminal** (`done` from a phase or culture-notes slug) — report the terminal state and stop. If `status:` starts with `halt`, call it a non-resumable halt (per cook/press's slug contract a resumable halt carries a runnable `next:`, so `halt` + `next: done` can only mean non-resumable); otherwise call it pipeline completion. The terminal value surfaces state to the user, not a runnable command; never construct `/done <slug>`.

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
