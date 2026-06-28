---
name: ultracook
description: Pipeline one approved high-blast-radius spec sequentially through cook → press → age → cure → age → cure → age (all `--auto`), with fresh-context isolation per phase. Use when the user has such a spec — phrases like "/ultracook .cheese/specs/<slug>.md", "ultracook this", "run the full pipeline in isolation", "fresh-context auto chain", "send it through the cave", "pipeline with no contamination". Runs inline and spawns full-peer general-purpose sub-agents (one per phase), each invoking the phase skill with `--auto` and writing its handoff slug under `.cheese/<phase>/<slug>.md`. Sub-agents inherit the parent's model and full tool / MCP / skill access. Use when the user wants `/cook --auto`'s autonomous chain semantics but with each phase reasoning blind to prior phases. After `/mold`; ends after the third age spawn (or earlier on halt / early-stop).
license: MIT
---

# /ultracook

Use this skill when the user wants the whole `cook → press → age → cure → age → cure → age` chain to run forward without per-step approval, **and** wants each phase to reason in fresh context — blind to the previous phase's chain-of-thought.

Do not use it for short focused changes (`/cook --auto` is cheaper and continuous), for fuzzy planning (`/mold`), or for review-only work (`/age`).

`/ultracook` is the sub-agent-transport sibling of `/cook --auto`: same chain and `--auto` semantics, but each phase runs in its own freshly-spawned sub-agent, so the parent context never accumulates phase-internal reasoning.

## Inputs

Accept one of:

- A spec path. When explicit, it points wherever the user wrote the spec.
- A bare slug whose spec lives in the per-project durable corpus (see `shared/formatting.md` § Corpus location).
- A pasted spec, with a slug supplied alongside.

`/ultracook` does not accept fuzzy or open-ended asks — those go to `/mold` first. The orchestrator assumes the contract is already locked.

Optional flag: `--open-pr` — at the terminal, open a *new* PR when none exists (the default only pushes an already-open one). The phase-only cure sub-agents never push.

## Flow

1. **Resolve slug** — derive `<slug>` from the input. If a spec path is given, the slug is the basename without `.md`; if a bare slug is given, confirm the spec exists at the durable path the spawned `/cook` resolves (`python3 ${CLAUDE_SKILL_DIR}/scripts/cook.pyz artifact-path specs <slug>`; see `shared/formatting.md` § Corpus location).
2. **Guard against re-entry** — if any of `.cheese/{cook,press,age,cure}/<slug>.md` already exist, stop with a one-line list of the existing handoffs and tell the user to either run `/cheese --continue <slug>` to resume from the latest phase or `rm` the relevant files to start fresh.
3. **Phase loop** — for each phase in `cook, press, age, cure, age, cure, age`, spawn a fresh sub-agent (see `## Sub-agent contract` below), wait for it to return, then read each phase's handoff slug and compute the next action deterministically:
   1. **Parse the slug** — `python3 ${CLAUDE_SKILL_DIR}/scripts/common.pyz read_handoff_slug --phase <phase> --slug <slug>` → JSON `{status, next, artifact, orientation, halt_reason}`. Do not infer success from the sub-agent's last line of stdout — read the file.
   2. **Compute the verdict** — `python3 ${CLAUDE_SKILL_DIR}/scripts/ultracook.pyz phase_decision --phase-index <i> --status <status> [--next <next>]` → JSON `{action, next_phase, exit_message}`. `<i>` is the **0-based** position in the chain (0 = cook, 1 = press, … 6 = the final age) — one less than the spawn `#` in the "Phases and slug paths" table below.
   3. **Act on the verdict**:
      - `action=halt` → surface the `exit_message` (which contains the halt reason verbatim) and stop. Never push on a halt.
      - `action=stop_early` → age reported `next: done`; the diff is clean at the medium+ severity floor. Stop early with a clean summary.
      - `action=stop` → chain table exhausted after the terminal age spawn. Proceed to the terminal push.
      - `action=spawn` → spawn `next_phase` and continue the loop.
4. **Terminal push** — after the third age spawn (or any earlier non-halt stop), if an open PR exists for the branch, dispatch `/gh` to commit + push the chain's changes to it (Rule 11 — the existing PR is the authorization). Open a *new* PR only when `--open-pr` is in scope. A halt never pushes.
5. **Final summary** — print a four-line summary: passes completed, total findings applied / deferred, the final age-report path, and whether the PR was pushed (or the next-step nudge "review the diff, then `/gh` when ready" if no PR existed and `--open-pr` was absent).

## Phases and slug paths

Every spawn uses the canonical `/<phase> <slug> --auto` form. Cook accepts a bare slug per its Inputs section; the other phases already resolve their paths from the slug.

| # | Phase invocation                          | Handoff slug                  |
|---|-------------------------------------------|-------------------------------|
| 1 | `/cook <slug> --auto`                     | `.cheese/cook/<slug>.md`      |
| 2 | `/press <slug> --auto`                    | `.cheese/press/<slug>.md`     |
| 3 | `/age <slug> --auto`                      | `.cheese/age/<slug>.md`       |
| 4 | `/cure <slug> --auto --stake medium+`     | `.cheese/cure/<slug>.md`      |
| 5 | `/age <slug> --auto`                      | `.cheese/age/<slug>.md` (overwritten) |
| 6 | `/cure <slug> --auto --stake medium+`     | `.cheese/cure/<slug>.md` (overwritten) |
| 7 | `/age <slug> --auto`                      | `.cheese/age/<slug>.md` (final report) |

### Cap enforcement

The two-cure-pass cap is enforced by **chain length, not by age** — age boots in fresh context and cannot count prior passes. So:

- The chain table has exactly seven entries, with two cure spawns (#4 and #6) and three age spawns (#3, #5, #7). After spawn #7 completes, the orchestrator stops because the table is exhausted.
- Each age spawn writes `next:` from what it observes on its own run: `next: cure` when at least one finding meets the `medium+` floor (medium-or-above, or a cheap contained-fix low), `next: done` when none do. The field is **informational** under ultracook — it drives early-stop (when an age reports clean), but it does not gate cap enforcement.
- `/ultracook` does not pass a pass-ordinal hint to age. Age has no need to know whether it is age₁, age₂, or age₃; the orchestrator owns the position.

## No-chain isolation directive

Each phase's existing `--auto` contract chains forward in-session — `/cook --auto` invokes `/press --auto`, which invokes `/age --auto`, etc. `/ultracook` overrides that behaviour: every spawn must run only its own phase, write the slug, and stop. The orchestrator owns the chain.

The override travels in the spawn prompt as the explicit no-chain directive: `Do not chain forward to the next phase even though your auto-mode contract documents that. Write your handoff slug and stop. The /ultracook orchestrator is driving the chain. Run in the foreground — do not background yourself, spawn detached processes, or defer work to a later session. If you cannot complete the phase within your context window, write a partial slug with status: halt: <reason> and stop; do not silently timeout.`

Each phase's SKILL.md `## Auto mode` section honours this directive — see `skills/<phase>/SKILL.md` `### When invoked from /ultracook` for the per-phase contract amendment.

## Sub-agent contract

Each phase spawns a **full peer** sub-agent. For the five-invariant specification, per-harness invocation examples, and the harness-evaluation checklist, see [`../cheese-factory/references/spawn-primitive-reference.md`](../cheese-factory/references/spawn-primitive-reference.md).

## Handoff slug schema

Every phase writes its handoff slug to `.cheese/<phase>/<slug>.md` with the following minimum shape (prepended as frontmatter or inline at the top of richer reports such as age and press):

```markdown
status: ok | halt: <one-line reason>
next: <phase-name | done>
artifact: <path-to-richer-report-if-any>
<one-line orientation: what this phase did>
```

`status: ok`: phase finished cleanly, `next` names the next phase. `status: halt: <reason>`: the chain stops and surfaces the reason verbatim; for cook and press slugs `next` still names the runnable resume phase for `/cheese --continue` (age and cure halt slugs keep their finding-driven `next:` values — `cure | done` and `age | done`). `next: done` is terminal — age writes it when the diff is clean at the medium+ floor (early-stop).

For phases that already write rich reports (`/age`, `/press`, `/cure` once extended, `/cook` once extended), the slug schema is prepended at the top of the same file — there is no second file. The schema is the contract; the body is whatever the phase normally writes.

## When auto mode stops early

Beyond the halt and age `next: done` cases in Flow step 3, one more early-stop case is an error, not a clean stop:

- A phase's slug file is missing after the sub-agent returns (the sub-agent did not write its handoff). Before surfacing this as a hard stop, attempt a **re-dispatch** with the foreground-only directive reinforced in the prompt. Cap re-dispatches at **2** per phase. After the second failed re-dispatch with no slug, print: `"<phase> did not write handoff after 2 re-dispatch attempts — check sub-agent logs"` and stop. Track the attempt count per phase in the orchestrator loop; reset to 0 when advancing to a new phase.

In every early-stop case, surface the slug file path so the user can read the full report. The natural terminal case (chain table exhausted after spawn #7) does not need an explicit early-stop signal — the orchestrator simply runs out of entries to spawn.

## Existing handoffs

When any `.cheese/{cook,press,age,cure}/<slug>.md` exist (per Flow step 2), scan all four paths and print only the ones present:

```
Slug `<slug>` has existing handoffs:
  .cheese/cook/<slug>.md     (when present)
  .cheese/press/<slug>.md    (when present)
  .cheese/age/<slug>.md      (when present)
  .cheese/cure/<slug>.md     (when present)
Use `/cheese --continue <slug>` to resume from the latest phase, or
`rm` the listed files to start fresh.
```

## Output

A short final summary, after the chain stops (success or early stop):

```
Ultracook summary — <slug>
Passes completed: <list of phase names that ran>
Findings:         <fixed count> applied, <count> deferred (cure-report path)
Final age:        .cheese/age/<slug>.md
Next step:        review the diff, then /gh when ready
```

If the chain stopped on a halt, replace "Next step" with the halt reason and the path of the phase that surfaced it.

## Preferred tools and fallbacks

The orchestrator only needs:

| Need                              | Prefer                | Fallback                          |
|-----------------------------------|-----------------------|-----------------------------------|
| Spawning the per-phase worker     | `Agent()` / harness sub-agent primitive | none — without sub-agent spawn, the fresh-context property cannot be honoured |
| Reading the handoff slug          | `cheez-read` / host file read | host file read                    |
| Detecting existing handoffs       | host file glob / list | `cheez-read` `tilth_list` glob     |

If the host harness does not expose a sub-agent primitive at all, `/ultracook` is the wrong skill — recommend `/cook --auto` instead, which uses the same flag semantics in the parent's own context.

## Rules

- Sub-agents are full peers, not diminutive workers. Do not downgrade the model, do not narrow `subagent_type`, do not restrict tools or MCP access.
- The chain is fixed: cook → press → age → cure → age → cure → age, all `--auto`, cure severity floor `medium+` (the `--stake` flag literal is preserved across callers). Do not invent extra phases or skip phases.
- Read each phase's handoff slug after the sub-agent returns. Do not infer success from the sub-agent's last line — read the file.
- Surface halts verbatim. Do not paraphrase, do not soften, do not "retry" a halted phase silently.
- At the terminal, push to an already-open PR via `/gh` (Rule 11); create a *new* PR only with `--open-pr`. Never push on a halt.
- Never wipe existing handoffs. Stop and tell the user to use `/cheese --continue` or `rm` by hand.
- Apply the shared voice kernel (lives at `skills/age/references/voice.md` in this repo): lead the final summary with what happened, flag residual risk as `certain | speculating | don't know`, do not manufacture follow-ups.
