---
name: cheese
description: Route any dropped-in input — idea, spec path, file path, PR or issue, stack trace, bug report, or bare `/cheese` — to the right workflow skill. Use as the unified entry point — phrases include "/cheese", "what should I do with this", "help me get started", "route this", or any opening message that does not already name a downstream skill.
license: MIT
---

# /cheese

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

- `--safe` — gate dispatch behind a confirmation prompt.
- `--open-pr` — propagate through the implementation chain to terminal `/plate`; a new PR follows `/plate`'s explicit-choice and review-shape policy.
- `--continue <slug-or-note-path>` — resume an in-flight pipeline from a handoff slug or note.
- `--hard` — propagate to `/plate`, which runs the final artifact-writing gate before `/hard-cheese` and publication.

If `$ARGUMENTS` is missing entirely and there is no recent context to lean on, ask one clarifying question through the host routing guide in [`references/handoff-gate.md`](references/handoff-gate.md) before classifying.

## Flow

0. **Read the full user message, not just `$ARGUMENTS`.** Any prose accompanying the invocation is a directive list; execute or answer it before — and where it conflicts, instead of — the flow's defaults and any handoff protocol. The handoff file restores state; the user's live message overrides it.
1. **Think first (silent).** Model the problem internally per `skills/culture/SKILL.md` — restate the ask, list candidate targets, name the deciding signal. Output is the classification that drives step 2.
2. **Classify** — match `$ARGUMENTS` against the intent shapes in `references/classification.md`. Pick the highest-confidence shape; below the threshold, route to `clarify` (handled by the tier-3 escalation in step 4).
3. **Clarity check (implementation intents only).** Run cook's fast-path check for `cook` and `mold`. Direct `plate` intents bypass it.
4. **Escalate (if needed).** Tier 1 dispatches the chosen target (writing a mini-spec via `/mold`'s agent-invoked mode when the dispatch is `/cook --auto` and no spec path was supplied). Tier 2 autonomously invokes `/culture` and/or `/briesearch` in internal mode, then re-runs the clarity check. Tier 3 blocks on a single targeted host-routed question and re-enters classification on the answer. See `## Escalation`.
5. **Wiki grounding (when hallouminate is present).** Derive a search query from the dropped-in input, ground it against the wiki corpus — at most one `mcp__hallouminate__ground` call, corpus resolved via `list_corpora` (probe shape: `skills/mold/references/grounding.md`) — and fold the top hits into the dispatch packet as `handoff_context.wiki_hits` (`[{page, line, why}]`; see [`references/handoff-gate.md`](references/handoff-gate.md) § Context payloads). When hallouminate is absent or no wiki corpus exists, skip and degrade per [`references/optional-plugins.md`](references/optional-plugins.md).
6. **Announce** — print a short block (Intent / Reason / Target, plus wiki hits when present) per the format in `## Output`. Cite the signal that drove the routing decision.
7. **Self-check** — run the coherence questions in `references/coherence-check.md`. If any fails, downgrade to `clarify` (tier 3) or `research`.
8. **Dispatch** — without `--safe`, run the chosen skill immediately with its exact dispatch command and context packet, in the same turn as the announce. With `--safe`, issue a handoff gate per [`references/handoff-gate.md`](references/handoff-gate.md) (recommended target pre-selected, at least one alternative, `Stop`) and wait for the user's selection before dispatching.

`/cheese` is a router, not a worker: it never edits files, runs tests, or opens PRs. Use only the host's read, search, and dispatch capabilities. The sole exception is invoking `/mold`'s agent-invoked mini-spec mode in tier 1 when `/cook --auto` needs a spec first; that write happens inside `/mold`'s own capability scope, not the router's.

Portability reference: [`references/harness-portability.md`](references/harness-portability.md). It covers helper resolution, sub-agent dispatch, GitHub operations, and handoff transitions; prefer the bundled or repo-local helper first, and treat `${CLAUDE_SKILL_DIR}` as optional host-provided fallback.
The handoff blocks below are the portable contract; slash commands are host renderings, not the control model.

## Intent shapes

The full classification table — including all intent shapes, signals, disambiguation rules, and edge cases — lives in `references/classification.md`.

## Escalation

For `cook` and `mold` intents, `/cheese` runs cook's fast-path check (§ "Standalone fast-path" in `skills/cook/SKILL.md`) and escalates through three tiers:

**Tier 1 — clear (all three checks pass).** First run the `## Spec-discovery check` — if an existing spec in `.cheese/specs/` substantially matches the request, dispatch `/cook --auto` against it and skip the mini-spec write. Otherwise the agent invokes `/mold`'s agent-invoked mini-spec mode (see `skills/mold/SKILL.md` § Agent-invoked mini-spec mode) to write `.cheese/specs/<slug>.md`, then dispatches `/cook --auto <spec-path>` in the same turn as the announce, where `<spec-path>` is the explicit mini-spec path returned by `/mold`. Do not collapse that path to a bare `<slug>`. No user interaction. When the input already names a spec path under `.cheese/specs/`, skip both the discovery scan and the mini-spec write and dispatch `/cook --auto` against the existing path directly.

**Tier 2 — borderline (any check fails or is uncertain).** Agent autonomously invokes `/culture` (internal thinking) and/or `/briesearch` (internal research), in any order, to fill the missing context. After the internal pass, re-run the cook fast-path check on the refined understanding. If all three checks now pass, drop into tier 1 (the mini-spec records the culture / briesearch synthesis under `## Provenance`). Otherwise tier 3.

**Tier 3 — still borderline after tier 2.** Block on the human via a single targeted host-routed question whose answer closes the failing check. On the answer, re-enter classification with the augmented input. This is the only sanctioned user-facing prompt in the autonomous-by-default path; the `clarify` intent and the below-`medium`-confidence path both map here.

`--safe` does not skip the escalation logic — the tiers still run silently — but it inserts a handoff gate before the final dispatch in every tier. The recommended option stays auto-flavoured (`/cook --auto <spec-path>` etc., using the explicit mini-spec path); the non-auto variant is offered as the alternative.

Non-implementation intents bypass the escalation entirely. Their target skills own their own internal escalation: `/pasteurize` has its Phase 1 feedback-loop check, `/briesearch` clarifies missing version/scope inline, `/age` and `/cure` work directly against the supplied diff or report.

## Rejected-directions check

Before dispatching any `mold` intent, scan `.cheese/.out-of-scope/` for rejection records whose `## Direction` section's one-line description substantially matches the incoming request. If a match is found:

1. Surface the previously-rejected direction and its rationale in one line.
2. Ask the user whether to proceed with the new request or take a different angle.
3. Do not suppress or re-propose the rejected direction silently.

This check is lightweight — a glob + keyword scan over `.cheese/.out-of-scope/*.md`. Skip silently when the directory does not exist. Non-`mold` intents skip this check.

## Spec-discovery check

Before minting a new mini-spec for a tier-1 `cook` or `mold` dispatch, look for an existing spec that already covers the request. Specs land in the durable XDG corpus (`default_root_for_phase("specs")`), not repo-local, so probe there:

- **hallouminate present** — `ground` the candidate spec text against the `cheese-durable` corpus for a near-duplicate (semantic match across every project's durable specs). Detect-and-degrade per [`references/optional-plugins.md`](references/optional-plugins.md).
- **hallouminate absent** — fall back to `resolve_slug(candidate_slug, phase_hint="specs")` (the XDG-correct `difflib` resolver in `shared/scripts/paths.py`), and note the degrade once: name-based rather than semantic matching. This keeps slug-level dedup on the headless/cron path where hallouminate is routinely unavailable.

Act on the result, do not guess:

1. **One clear match (high confidence)** — surface the resolved spec path in one line and dispatch against it (`/cook --auto <resolved-spec-path>`) instead of writing a duplicate.
2. **Multiple plausible matches, or a weak best match** — under `--safe`, present the candidates in the handoff gate for the user to pick; without `--safe`, fall back to minting a fresh mini-spec rather than risk dispatching against the wrong spec.

Skip silently when no specs exist yet, and when the user already named a spec path (the path is authoritative).

## --continue

`/cheese --continue <slug-or-note-path>` is the manual fresh-context resumption path. Use it after compacting the conversation, after `/ultracook` has stopped on a halt, or whenever the user wants to drive the pipeline by hand from a cleared context.

Flow:

0. **Read the full user message, not just the `--continue` argument.** Any prose accompanying the invocation is a directive list; execute or answer it before — and where it conflicts, instead of — the handoff protocol below. The handoff file restores state; the user's live message overrides it.
1. If the argument is a readable `.md` handoff path, read that file directly and derive `<slug>` from its basename. If the path contains a `.cheese/` parent, treat the directory above `.cheese/` as the original repo root for any repo-relative paths in the handoff.
2. Otherwise, scan for the most recently modified handoff slug across `.cheese/{cook,press,age,cure,affinage,notes}/<slug>.md`.
3. If none exist, offer to start the pipeline from scratch — `/mold` for fuzzy specs, `/cook` for clear asks, `/ultracook` for high-blast-radius specs — and stop.
4. If a handoff exists, read it and surface the orientation line so the user knows where they are. Parse `status:`, `next:`, and optional `mode:`:
   - **First parse optional `mode:`.** Missing `mode:` means `mode: single`, preserving all existing handoffs. In `mode: single`, `next:` remains the runnable phase and the existing bullets below apply. In `mode: parallel`, `next:` is only the coarse resume category; prefer `next: tasks` when the handoff may mix skills. Never dispatch `next:` directly in parallel mode. Instead parse the handoff's optional `parallel:` block and required `tasks:` list, where each item carries an explicit `command:` such as `/ultracook .cheese/specs/kip-77-ai-test-server.md`, `/briesearch ...`, or `/affinage <pr>`.
   - **When `mode: parallel` and `tasks:` is present** — dispatch one isolated agent per task in the same response / same turn so the tasks run concurrently. Each agent receives the original handoff path, repo root, task name/slug if present, exact `command:`, any task-local branch/worktree notes, and an instruction to work only that task and not run sibling tasks. Use the task `command:` as authoritative even when tasks name different skills or intents. For write-capable commands (`/cook`, `/ultracook`, `/cure`, `/affinage`, or any command expected to edit a branch), require `slug`, `repo`, `branch:`, `branch_from`, and a checkout-isolation plan. Supported `parallel.worktree_strategy` values are `existing` (every write task declares a distinct `worktree:`), `create` (create one git worktree per task under `worktree_root` from `branch_from`), and `harness` (ask/create one harness-managed isolated thread or worktree per task). Never run parallel write tasks in the same checkout or a shared checkout. If `tasks:` is missing, any task lacks `command:`, write tasks lack branch/worktree isolation, branches collide, worktrees collide, or the strategy is unsupported, stop and ask for a corrected handoff instead of guessing. Under `--safe`, offer the parallel dispatch as the pre-selected option, with `Stop` last.
   - **When `status:` starts with `halt` and `next:` names a phase** (`mold | cook | press | age | cure | affinage | ultracook`) — surface the halt reason, then treat `/cheese --continue <slug>` as the user's explicit permission to dispatch the next phase. `affinage` is the exception: it takes a PR ref, not a slug, so read the PR from the slug's `artifact:` field (`PR#<n>` or its URL) and dispatch `/affinage <pr>`; fall back to a bare `/affinage` (branch auto-detect) only when `artifact:` carries no PR. Under `--safe`, offer the dispatch as the pre-selected option, with `/ultracook \<slug\>` as an alternative and `Stop` last.
   - **When `status:` is `ok` and `next:` names a pipeline phase** (`mold | cook | press | age | cure | affinage`) — dispatch `/\<next\> \<slug\>` directly, with the same `affinage` exception above. Under `--safe`, offer it as the pre-selected option, with `/ultracook \<slug\>` as an alternative and `Stop` last.
   - **When `status:` is `ok` and `next:` names a read-only kickoff** (`briesearch | culture`) — auto-dispatch it directly (`/briesearch \<arg\>`, `/culture`), taking `\<arg\>` from the handoff's orientation line. These are read-only and low-risk, so frictionless dispatch is the goal; do not gate them behind a question. Under `--safe`, offer the dispatch as the pre-selected option with `Stop` last.
   - **When `status:` starts with `gated:`** — do *not* auto-dispatch `next:`, whatever it names. If the accompanying message contains directives or already answers the gate, execute them and surface the gate as one line of plain text — do not raise the structured question. Otherwise, surface the one-line decision from `status:` plus the body's open-questions/blockers, then ask the user which direction: **research / decide / build**. First classify each open gate item as mechanical or design per [`references/ask-user-question.md`](references/ask-user-question.md) § When to structure: a mechanical item may go straight to that structured question, but a design item whose weighing was not already shown this session must not — re-establish the weighing in prose first (both ends, code-grounded evidence, pushback invited), converge conversationally, then ask at most one structured confirm, and never bundle multiple design forks into one prompt. Dispatch nothing until the user picks; on the pick, route research → `/briesearch`, build → the named phase, decide → resolve the decision with the user, then re-read the handoff. Never fire a binary design popup that presumes the user wants to decide.
   - **When `next:` is a list** (`next: [<skill> "<arg>", ...]`) — `order:` is required; if it is missing, stop and ask for a corrected handoff. The inline list accepts only read-only skills (`briesearch | culture`); if any item names a write or pipeline skill, reject it and point at the heavyweight `mode: parallel` + `tasks:` block (which carries the worktree/branch isolation those skills need). With `order: parallel`, dispatch one read agent per item in the same turn so they run concurrently; with `order: sequential`, dispatch the items in listed order. Under `--safe`, offer the batch dispatch as the pre-selected option with `Stop` last.
   - **When `next:` is `hold`** — surface the orientation line and stop without dispatching. `hold` means restore context and wait for instruction; it is not a runnable command. Distinct from `done` (terminal record) — `hold` is a live session paused for input.
   - **When `next:` is missing entirely** — flag the handoff as malformed (`malformed handoff: next: required`) and stop. Do not guess a next step or default to a phase; `hold` is the author's value for "no action."
   - **When `next:` is terminal** (`done` from a phase or culture-notes slug) — report the terminal state and stop. If `status:` starts with `halt`, call it a non-resumable halt (per cook/press's slug contract a resumable halt carries a runnable `next:`, so `halt` + `next: done` can only mean non-resumable); otherwise call it pipeline completion. The terminal value surfaces state to the user, not a runnable command; never construct `/done <slug>`.
   - **When the handoff carries a recorded `baseline:` block** — treat it as settled state, not an open question: never re-ask about or re-halt on the failures it records, whether in this reader or in the dispatched phase. See [`../cook/references/quality-gates.md`](../cook/references/quality-gates.md).

Under `--safe`, gate the resumption through the handoff gate in [`references/handoff-gate.md`](references/handoff-gate.md); otherwise run the named phase immediately with the slug. The slug files are the resumability contract: they tell the router where the pipeline is and how to move it forward.

`--continue` does *not* propagate `--auto` — dispatch `/<next> <slug>` in its default interactive mode even with no `--safe`. The user can append `--auto` explicitly (`/cheese --continue <slug> --auto`) to opt back in.

## Confidence and the clarify gate

Treat classification confidence qualitatively (`low | medium | high`). Threshold for direct routing is `medium` or better. Below that, route to tier 3 (`clarify`):

- Ask exactly one question through the host routing guide in [`references/handoff-gate.md`](references/handoff-gate.md).
- Offer the two most-likely targets as alternatives plus `Stop`.
- Re-enter `/cheese` with the answer.

At `medium` or above, dispatch directly. For implementation intents, the cook-fast-path clarity check adds a second layer (see `## Escalation`).

## Preferred tools and fallbacks

When the input is a path or slug, code reading and searching go through the `cheez-*` skills (`/cheez-read`, `/cheez-search`) — see those skills for tool selection rules.

Beyond `cheez-*` there are router-specific tools:

| Need | Prefer | Fallback |
| --- | --- | --- |
| PR / issue context | `gh` | the URL or numbers the user provided |
| Confirming routing target with the user (only under `--safe` or `clarify`) | host-routed structured question per [`references/handoff-gate.md`](references/handoff-gate.md) | a numbered list with explicit dispatch commands |

`/cheese` keeps tool use light. Beyond the single wiki-grounding probe in `## Flow`, treat anything heavier than a single-file read or one search call as a sign the work belongs in the downstream skill, not in the router.

## Output

Always emit, in order:

1. **Detected intent** — one line, e.g. `Intent: cook (clear single-file fix)`.
2. **Reason** — one line citing the signal (`reason: spec path .cheese/specs/foo.md`).
3. **Target** — the chosen skill, e.g. `Target: /cook .cheese/specs/foo.md`.
4. **Wiki hits** — when `handoff_context.wiki_hits` is non-empty, one line per hit: `wiki: <page>:<line> — <why>` — always rendered before dispatch so the user sees what memory informed the routing and can challenge stale hits. Omit the section when hallouminate is absent.

Then dispatch in the same turn (or, under `--safe`, via the handoff gate). If `clarify` is chosen, replace the dispatch with the single clarifying question.

## Handoff

Without `--safe`, cheese propagates `--auto` to any target that supports it. Under `--safe`, dispatch waits for the user's selection via the handoff gate; the auto variant stays the pre-selected recommended target.

Default targets per intent:

- **clarify** — single targeted question; no skills run until the answer arrives.
- **research** — `/briesearch` (recommended). No auto variant.
- **rubber-duck** — `/culture` (recommended). Only reached when the user explicitly opted out of writes. No auto variant.
- **mold** — `/mold` (recommended). Safe-mode alternative: `/briesearch first` when external evidence is missing.
- **cook** — default: `/cook --auto <slug-or-path>`. Safe-mode alternatives: `/cook <slug-or-path>` (no auto), `/mold first` if scope is borderline.
- **ultracook** — `/ultracook <slug-or-path>` (recommended for a high-blast or decomposable spec). The decomposer picks the mode: parallel curd fan-out when the spec decomposes into 2+ file-disjoint curds, else the linear 7-phase chain.
- **plate** — `/plate` for commit-only work, ordinary PR publication, or stack publication/maintenance. New PRs infer an obviously cohesive single, recommend and ask for reviewable ordered stacks, and ask when shape is ambiguous; explicit choices win.
- **debug** — default: `/pasteurize --auto <input>`. Safe-mode alternatives: `/pasteurize <input>` (no auto), `/culture` only when the user explicitly wants no-write diagnosis.
- **age** — `/age <ref>` (recommended). Safe-mode alternative: `/age --scope <path>` when the user named a path glob.
- **age-then-cure** — `/age <slug>` (recommended). Safe-mode alternative: `/cure <slug>` when a fresh report already exists.

Pre-select only the highest-confidence target. Without `--safe`, surface the target as a decision, not a question — dispatch the recommended option directly. With `--safe`, dispatch waits for the user's selection; the captured dispatch packet runs immediately on a non-stop choice.

## Rules

- Never paraphrase or summarise downstream skill output — that is the downstream skill's job.
- A declined question gate is an answer. Do not re-raise it; state the open item as one line and wait for freeform input.

## References

- `references/classification.md` — intent shapes, signals, disambiguation rules.
- `references/coherence-check.md` — pre-dispatch self-checks that downgrade misroutes.
- [`references/handoff-gate.md`](references/handoff-gate.md) — cross-harness post-selection dispatch contract (shared across workflow skills).
