---
name: pasteurize
description: Hard-bug DIAGNOSIS + FIX. Builds a deterministic agent-runnable feedback loop, reproduces the failure, names the cause, writes a regression test, applies the minimal production fix. Use when the user reports a bug, flaky test, perf regression, or visible misbehaviour — phrases like "diagnose this", "debug this", "why is X broken", "/pasteurize", or a pasted stack trace / repro / "this looks wrong, investigate" with no stated cause. Pasteurize EDITS code (regression test + fix); culture does not. Do NOT use for review-only diffs (`/age`), feature design (`/mold`), known-cause fixes (`/cook`), or when the user explicitly opted out of writes (`/culture`).
license: MIT
---

# /pasteurize

A discipline for hard bugs. Skip phases only when explicitly justified.

When exploring the codebase, use `/cheez-search` to orient and check `.cheese/specs/` for any spec or design notes that touch the failing seam.

Portability reference: [`../../shared/harness-portability.md`](../../shared/harness-portability.md). It covers helper resolution, sub-agent dispatch, GitHub operations, and handoff transitions; prefer the bundled or repo-local helper first, and treat `${CLAUDE_SKILL_DIR}` as optional host-provided fallback.
The handoff blocks below are the portable contract; slash commands are host renderings, not the control model.

## Phase 1 — Feedback loop

**This is the skill.** Everything else is mechanical. If you have a fast, deterministic, agent-runnable pass/fail signal for the bug, you will find the cause — bisection, hypothesis-testing, and instrumentation all just consume that signal. If you don't have one, no amount of staring at code will save you.

Spend disproportionate effort here.

### Ways to construct one

To pick a loop shape, see [`references/feedback-loops.md`](references/feedback-loops.md) for the ten-option ordered menu.

### Iterate on the loop itself

Treat the loop as a product. Once you have _a_ loop, ask:

- Can I make it faster? (Cache setup, skip unrelated init, narrow the test scope.)
- Can I make the signal sharper? (Assert on the specific symptom, not "didn't crash".)
- Can I make it more deterministic? (Pin time, seed RNG, isolate filesystem, freeze network.)

### Non-deterministic bugs

The goal is not a clean repro but a **higher reproduction rate**. Loop the trigger 100×, parallelise, add stress, narrow timing windows, inject sleeps. A 50%-flake bug is debuggable; 1% is not — keep raising the rate until it's debuggable.

### When you genuinely cannot build a loop

Stop and say so explicitly. List what you tried. Ask the user for: (a) access to whatever environment reproduces it, (b) a captured artifact (HAR file, log dump, core dump, screen recording with timestamps), or (c) permission to add temporary production instrumentation. Do **not** proceed to hypothesise without a loop. Write a `status: halt` handoff slug (see below) and stop.

Do not proceed to Phase 2 until the loop passes all four checks:

- [ ] **Deterministic** — runs the same way every time (or, for flaky bugs, reproduction rate >50% and rising).
- [ ] **Agent-runnable** — a single command with no human in the loop.
- [ ] **Asserts the user’s exact symptom** — the failure message / wrong output / timing the user reported, not a nearby failure.
- [ ] **Fast** — under 30 seconds end-to-end (aim for under 5).

## Phase 2 — Reproduce

Run the repro loop N times and verify the failure is consistent:

```
python3 skills/pasteurize/scripts/pasteurize.pyz repro-rerun --cmd "<repro-command>" --runs 5
```

Confirm the returned `reproduced: true` and check `failures` matches the expected failure mode. If `reproduced: false` at N=5, the bug is flaky — increase `--runs` before proceeding.

Do not proceed until you reproduce the bug.

## Phase 3 — Hypothesise

Generate **3–5 ranked hypotheses** before testing any of them. Single-hypothesis generation anchors on the first plausible idea.

Each hypothesis must be **falsifiable**: state the prediction it makes.

> Format: "If `<X>` is the cause, then `<changing Y>` will make the bug disappear / `<changing Z>` will make it worse."

If you cannot state the prediction, the hypothesis is a vibe — discard or sharpen it.

**Show the ranked list to the user through the host routing guide in [`../../shared/handoff-gate.md`](../../shared/handoff-gate.md) before testing.** They often have domain knowledge that re-ranks instantly ("we just deployed a change to #3"), or know hypotheses they've already ruled out. Cheap checkpoint, big time saver. Don't block on it — proceed with your ranking if the user is AFK or running `--auto`.

## Phase 4 — Instrument

Each probe must map to a specific prediction from Phase 3. **Change one variable at a time.**

Tool preference:

1. **Debugger / REPL inspection** if the env supports it. One breakpoint beats ten logs.
2. **Targeted logs** at the boundaries that distinguish hypotheses.
3. Never "log everything and search".

**Tag every debug log** with a unique prefix, e.g. `[DEBUG-a4f2]`. Cleanup at the end becomes a single `/cheez-search` content query. Untagged logs survive; tagged logs die.

**Perf branch.** For performance regressions, logs are usually wrong. Instead: establish a baseline measurement (timing harness, `performance.now()`, profiler, query plan), then bisect. Measure first, fix second.

## Phase 5 — Fix + regression test

Write the regression test **before the fix** — but only if there is a **correct seam** for it.

A correct seam is one where the test exercises the **real bug pattern** as it occurs at the call site. If the only available seam is too shallow (single-caller test when the bug needs multiple callers, unit test that can't replicate the chain that triggered the bug), a regression test there gives false confidence.

**If no correct seam exists, that itself is the finding.** Note it in the handoff slug as an architectural follow-up. The codebase is preventing the bug from being locked down. Skip the test write; do not paper over it. Phase 6's "what would have prevented this bug?" retrospective still applies.

**Before writing the test, confirm the seam is correct:** verify that the test you're about to write targets the boundary where the bug actually occurs — the real call site, the real data path, the real failure mode. A test at the wrong seam (too shallow, wrong abstraction level, mocked-away side that hides the failure) will pass after the fix but won't catch a regression. If you discover the seam is wrong at this point, treat it as "no correct seam": write `status: halt: no correct regression-test seam` and route to `/mold`, per the halt path above.

If a correct seam exists:

1. Turn the minimised repro into a failing test at that seam.
2. Watch it fail.
3. Apply the **smallest** production change that makes the test pass. No scope creep, no "while I'm here" cleanup. If the test still fails, revert and retry — but cap the retries (see **After 3 failed fix attempts** below).
4. Watch the test pass.
5. Re-run the Phase 1 feedback loop against the original (un-minimised) scenario to confirm the symptom is gone, not just the test seam.

**After 3 failed fix attempts** (3 cycles of "apply change → watch test → revert because test still fails"), stop attempting fixes and re-question the approach: is the hypothesis from Phase 3 actually correct? Is the seam exposing the right failure? Is the bug at a different layer than assumed? Step back to Phase 3 and generate a fresh ranked hypothesis list — do NOT attempt a 4th blind fix. If the re-questioning produces a new hypothesis, restart from Phase 4. If all hypotheses are exhausted, write `status: halt: fix attempts exhausted — architectural re-examination needed` and route to `/mold`.

Broader implementation (related cleanup, follow-on changes, anything beyond the minimal fix) is **not** pasteurize's job. Note it in the slug and let `/cook --auto` pick it up in Phase 6's handoff.

## Phase 6 — Cleanup

Before writing the handoff slug, confirm:

- [ ] Original repro no longer reproduces (re-run the Phase 1 loop).
- [ ] Regression test passes (or absence of seam is documented in the slug).
- [ ] All `[DEBUG-...]` instrumentation removed:

  ```
  python3 skills/pasteurize/scripts/pasteurize.pyz debug-tag-sweep --root .
  ```

  Exit 0 = clean. Exit 1 = tags found (listed in output). Resolve before continuing.
- [ ] Throwaway harnesses / prototypes deleted (or moved to a clearly-marked debug location and called out in the slug).
- [ ] The confirmed hypothesis is captured in the slug so the commit message downstream can reference it.

**Then ask: what would have prevented this bug?** If the answer involves architectural change (no good test seam, tangled callers, hidden coupling), note it in the slug under an architectural-follow-up line. The chain still runs; the user can pick up the architectural work via `/mold` after the fix lands. Make the recommendation **after** the fix is in, not before.

Once the checklist is green and the slug is on disk, hand off to `/cook <slug> --auto` (default). Cook --auto picks up the post-fix state, runs its taste-test against the applied diff for spec drift / readability / scope creep, produces its package-ready report, and triggers the autonomous `/press → /age → /cure` chain. Pasteurize itself does not commit, open PRs, or drive the chain — cook owns that.

## Preferred tools and fallbacks

| Need | Prefer | Fallback |
| --- | --- | --- |
| Code search / blast radius | `/cheez-search` (tilth MCP) | LSP, native AST search, or another semantic backend that answers the same question |
| Reading code | `/cheez-read` (tilth MCP) | Native bounded read with snapshot/line anchors, or LSP symbol read when it supplies a stale-safe edit path |
| Editing instrumentation | `/cheez-write` (tilth MCP) | Native anchored-edit backend with stale-write detection, or LSP-driven edit when it preserves the same safety |
| Diff visualization | `delta` | plain `git diff` |
| GitHub context | `gh` | local git history or user-provided links |
| External sanity check | `/briesearch` | clearly mark as an assumption |

Missing optional tools should not interrupt diagnosis.

## Output

Return a short report covering:

- The named cause (one sentence, with `<certain>` / `<speculating>` / `<don't know>` calibration).
- The feedback loop (command, observed vs expected).
- Hypotheses considered and which one held.
- The regression test path and the fix's file:line footprint.
- Cleanup status (`[DEBUG-...]` removed, harnesses deleted or relocated).
- Suggested next skill — `/cook <slug> --auto` for the autonomous chain forward.

## Handoff slug

Write a minimum-shape handoff slug to `.cheese/pasteurize/<slug>.md` so `/cook` (and any orchestrator) can resume without re-reading the full report. Schema:

```markdown
status: ok | halt: <one-line reason>
next: cook | mold | done
artifact: <path-to-richer-report-if-any>
cause: <one-sentence named cause>
loop: <command or repro path>
seam: <regression-test path:line, or "none — architectural follow-up">
fix: <production diff footprint, e.g. "src/foo.ts:42">
follow_up: <architectural follow-up note, or "none">
<one-line orientation: what pasteurize converged on>
```

`status: ok` when the regression test is green, the original repro no longer reproduces, and cleanup is done. `status: halt: <reason>` when any early-stop condition fires — see [Early-stop conditions](#early-stop-conditions) below. `next:` is `cook` for the standard chain, `mold` if the diagnosis itself recommends an architectural spec instead of a per-bug fix, or `done` if the bug was caused outside the repo and no follow-up is needed.

## Handoff

**Pipeline:** cheese (debug) → **[pasteurize]** → cook --auto → press → age → cure → ship

After the report is printed and the handoff slug is on disk, ask through the host routing guide in [`../../shared/handoff-gate.md`](../../shared/handoff-gate.md) which downstream to run. Lead each option with the verb (what the user wants to _do_ next):

- **Validate and chain forward** _(recommended when `status: ok`)_ — `/cook <slug> --auto`.
- **Validate without auto chain** — `/cook <slug>` (cook runs taste-test, then the user picks each subsequent step).
- **Spec the architectural follow-up first** — `/mold <slug>` (when `seam: none — architectural follow-up`).
- **Stop** — fix is in tree; defer the chain.

Pre-select **Validate and chain forward** when `status: ok`. The chain default is `--auto` because pasteurize already wrote and verified the fix; the work left for cook → press → age → cure is mechanical validation, not new authoring. Never auto-invoke; the user must still select.

When invoked with `--auto`, skip this host-routed question entirely and invoke `/cook <slug> --auto` directly.

## Auto mode

`--auto` skips Phase 3's user-ranking gate, skips the Phase 6 handoff gate, and invokes `/cook <slug> --auto` directly. Phase 4–5 still run in full.

### Early-stop conditions

- Phase 1 fails (`status: halt` written, no loop achievable).
- Phase 3 disproves all hypotheses across two rounds (cap at two Phase 3 rounds, then halt).
- Phase 5's seam check finds no correct seam — write `status: halt: no correct regression-test seam` and route to `/mold` instead of `/cook`.
- The fix breaks an unrelated test that pasteurize cannot reconcile within scope.
- Phase 5's fix loop exhausts all hypotheses after 3 failed fix attempts — write `status: halt: fix attempts exhausted — architectural re-examination needed` and route to `/mold` instead of `/cook`.

In every early-stop case, write the halt slug and surface the report. Do not silently downgrade to "best guess".

## Rules

- Do not skip Phase 1, and do not hypothesise without a reproducing loop.
- Phase 5 writes only the regression test and the **minimal** production change; broader work belongs in `/cook`.
- Do not leave `[DEBUG-...]` tags in the tree — clean them before the handoff slug is written.
- Do not claim "shipped". Pasteurize claims "cause named, regression green, fix in tree, ready for chain". The chain (cook → press → age → cure) claims shipped.
- If the bug exposes an architectural gap (no correct regression-test seam), say so in the slug. Do not silently paper over it.

## References

- `skills/pasteurize/scripts/pasteurize.pyz repro-rerun` — run the repro command N times and emit `{exit_code, reproduced, runs, failures}` (Phase 2).
- `skills/pasteurize/scripts/pasteurize.pyz debug-tag-sweep` — scan the tree for instrumentation tag prefixes and exit 1 if any survive (Phase 6 cleanup gate).
