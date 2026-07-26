---
name: pasteurize
description: "Hard-bug DIAGNOSIS + FIX: reproduce the failure, name the cause, write a regression test, apply the minimal fix. Use whenever the user reports a bug, failure, flaky test, perf regression, error, or visible misbehaviour whose cause is not yet known — even if they only paste a symptom, stack trace, or failing test output, or say \"why is X broken\", \"it stopped working\", \"it got slower\", \"this looks wrong\". Do NOT start debugging inline without this skill: if your next step would be forming hypotheses about an unexplained failure, invoke /pasteurize first. Do NOT use for review-only diffs (/age), feature design (/mold), fixes where the cause is already known (/cook), or when the user opted out of writes (/culture)."
license: MIT
---

# /pasteurize

A discipline for hard bugs. Skip phases only when explicitly justified.

When exploring the codebase, call the selected source-code backend directly according to [`code-intelligence-routing.md`](../cheese/references/code-intelligence-routing.md), and check `.cheese/specs/` for any spec or design notes that touch the failing seam.

Portability reference: [`../cheese/references/harness-portability.md`](../cheese/references/harness-portability.md). It covers helper resolution, sub-agent dispatch, GitHub operations, and handoff transitions; prefer the bundled or repo-local helper first, and treat `${CLAUDE_SKILL_DIR}` as optional host-provided fallback.
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

Stop and say so explicitly. List what you tried and ask for the missing evidence. Commit `status: halt` with a non-empty reason and a resumable destination through `handoff-commit`; do not proceed to hypotheses without a loop.

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

## Symptom-shape gate

Before forming any hypothesis, classify the symptom shape:

- **Clean stack trace + deterministic repro** — stay at current tier, proceed to Phase 3 normally.
- **Heisenbug, race condition, cross-module failure, or perf regression** — warn to upgrade (harness-detected phrasing: claude `/model opus` + `/effort`; codex/OMP named equivalent; generic fallback) _before_ forming any hypothesis. The extra tier buys the wider context window and reasoning depth these shapes need; do not start Phase 3 at the current tier once this branch fires.

## Phase 3 — Hypothesise

Generate **3–5 ranked hypotheses** before testing any of them. Single-hypothesis generation anchors on the first plausible idea.

Each hypothesis must be **falsifiable**: state the prediction it makes.

> Format: "If `<X>` is the cause, then `<changing Y>` will make the bug disappear / `<changing Z>` will make it worse."

If you cannot state the prediction, the hypothesis is a vibe — discard or sharpen it.

**Show the ranked list to the user through the host routing guide in [`../cheese/references/handoff-gate.md`](../cheese/references/handoff-gate.md) before testing.** They often have domain knowledge that re-ranks instantly ("we just deployed a change to #3"), or know hypotheses they've already ruled out. Cheap checkpoint, big time saver. Don't block on it — proceed with your ranking if the user is AFK or running `--auto`.

## Phase 4 — Instrument

Each probe must map to a specific prediction from Phase 3. **Change one variable at a time.**

Tool preference:

1. **Debugger / REPL inspection** if the env supports it. One breakpoint beats ten logs.
2. **Targeted logs** at the boundaries that distinguish hypotheses.
3. Never "log everything and search".

**Tag every debug log** with a unique prefix, e.g. `[DEBUG-a4f2]`. Cleanup at the end becomes a single content query through the selected search backend. Untagged logs survive; tagged logs die.

**Perf branch.** For performance regressions, logs are usually wrong. Instead: establish a baseline measurement (timing harness, `performance.now()`, profiler, query plan), then bisect. Measure first, fix second.

## Phase 5 — Fix + regression test

Write the regression test **before the fix** — but only if there is a **correct seam** for it.

A correct seam is one where the test exercises the **real bug pattern** as it occurs at the call site. If the only available seam is too shallow (single-caller test when the bug needs multiple callers, unit test that can't replicate the chain that triggered the bug), a regression test there gives false confidence.

**If no correct seam exists, that itself is the finding.** Record it in the report body and phase payload as an architectural follow-up. Skip the test write; Phase 6's retrospective still applies.

**Before writing the test, confirm the seam is correct:** verify that the test you're about to write targets the boundary where the bug actually occurs — the real call site, the real data path, the real failure mode. A test at the wrong seam (too shallow, wrong abstraction level, mocked-away side that hides the failure) will pass after the fix but won't catch a regression. If you discover the seam is wrong at this point, treat it as "no correct seam": write the no-correct-seam halt string from [Early-stop conditions](#early-stop-conditions) and route to `/mold`, per the halt path above.

If a correct seam exists:

1. Turn the minimised repro into a failing test at that seam.
2. Watch it fail.
3. Apply the **smallest** production change that makes the test pass. No scope creep, no "while I'm here" cleanup. If the test still fails, revert and retry — but cap the retries (see **After 3 failed fix attempts** below).
4. Watch the test pass.
5. Re-run the Phase 1 feedback loop against the original (un-minimised) scenario to confirm the symptom is gone, not just the test seam.

**After 3 failed fix attempts** (3 cycles of "apply change → watch test → revert because test still fails"), stop attempting fixes and re-question the approach: is the hypothesis from Phase 3 actually correct? Is the seam exposing the right failure? Is the bug at a different layer than assumed? Step back to Phase 3 and generate a fresh ranked hypothesis list — do NOT attempt a 4th blind fix. If the re-questioning produces a new hypothesis, restart from Phase 4. If all hypotheses are exhausted, write the fix-attempts-exhausted halt string from [Early-stop conditions](#early-stop-conditions) and route to `/mold`.

Broader implementation is not pasteurize's job. Record it in the report body and let the resolved `cook` destination own it.

## Phase 6 — Cleanup

Before committing the handoff, confirm:

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
| Code search / blast radius | semantic caller and dependency search | bounded text search with explicit precision loss |
| Reading code | fresh bounded read from the intended write backend family | native bounded read with snapshot/line anchors |
| Editing instrumentation | stale-safe anchored edit | LSP or native snapshot edit with stale-write detection |
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

## Handoff artifact

Commit the diagnosis report through the shared runtime with `phase: pasteurize`. Put `cause`, `loop`, `seam`, `fix`, and `follow_up` in the phase payload, and keep the full diagnosis in the Markdown body. Set `status: ok` only when the regression test is green, the original reproduction no longer fails, and cleanup is complete; otherwise use `status: halt` plus the early-stop reason. Set `next_phase` to `cook` for the standard chain, `mold` for an architectural spec, or `done` when the cause is outside the repository and no follow-up remains. Use the artifact path returned by `handoff-commit`.

## Handoff

**Pipeline:** cheese (debug) → **[pasteurize]** → cook --auto → press → age → cure → plate

After committing the report and resolving its destination, ask through the host routing guide when manual choice remains. Lead each option with the verb:

- **Validate and chain forward** _(recommended when `status: ok`)_ — `/cook <slug> --auto`.
- **Validate without auto chain** — `/cook <slug>` (cook runs taste-test, then the user picks each subsequent step).
- **Spec the architectural follow-up first** — `/mold <slug>` (when `seam: none — architectural follow-up`).
- **Stop** — fix is in tree; defer the chain.

Pre-select **Validate and chain forward** when `status: ok`. The chain default is `--auto` because pasteurize already wrote and verified the fix; the work left for cook → press → age → cure is mechanical validation, not new authoring. Never auto-invoke; the user must still select.

When invoked with `--auto`, skip this host-routed question entirely and chain forward per [Auto mode](#auto-mode).

## Auto mode

`--auto` skips Phase 3's user-ranking gate, skips the Phase 6 handoff gate, and invokes `/cook <slug> --auto` directly. Phase 4–5 still run in full.

### Early-stop conditions

- Phase 1 fails: commit `status: halt` with the unavailable-loop reason.
- Phase 3 disproves all hypotheses across two rounds.
- Phase 5 finds no correct seam: commit halt with reason `no correct regression-test seam` and retain `next_phase: mold`.
- The fix breaks an unrelated test that pasteurize cannot reconcile within scope.
- Three failed fix attempts exhaust the hypotheses: commit halt with reason `fix attempts exhausted — architectural re-examination needed` and retain `next_phase: mold`.

Every early stop commits the versioned report and lets `handoff-resolve` return `action: halt`; never silently downgrade to a best guess.

## Rules

- Do not skip Phase 1, and do not hypothesise without a reproducing loop.
- Phase 5 writes only the regression test and the **minimal** production change; broader work belongs in `/cook`.
- Remove every `[DEBUG-...]` tag before committing the handoff.
- Do not claim "shipped". Pasteurize claims "cause named, regression green, fix in tree, ready for chain". The chain (cook → press → age → cure) claims shipped.
- If the bug exposes an architectural gap, record it in the payload and report body.

## References

- `skills/pasteurize/scripts/pasteurize.pyz repro-rerun` — run the repro command N times and emit `{exit_code, reproduced, runs, failures}` (Phase 2).
- `skills/pasteurize/scripts/pasteurize.pyz debug-tag-sweep` — scan the tree for instrumentation tag prefixes and exit 1 if any survive (Phase 6 cleanup gate).

## Work continuity

Follow the executable [cross-skill work contract](../cheese/references/work-contract.md) before phase work. A meaningful direct invocation ensures one WorkRecord; a nested invocation joins the inherited work ID. Emitting phases commit their versioned envelope and report body through `handoff-commit`, then act only on `handoff-resolve`. Never write or route from a legacy line-based handoff header.
