---
name: pasteurize
description: This skill should be used when the user has a hard bug, flaky failure, or performance regression — phrases like "diagnose this", "debug this", "why is X broken", "the test fails intermittently", "/pasteurize", or a pasted stack trace / repro without a stated cause. Runs Matt Pocock's six-phase diagnosis loop (feedback loop → reproduce → hypothesise → instrument → fix + regression test → cleanup); phase 1 (build a deterministic, agent-runnable feedback loop) is the skill — everything else consumes the signal. Writes the regression test, applies the minimal fix, verifies the original repro is gone, then writes `.cheese/pasteurize/<slug>.md` and hands off to `/cook --auto` (default) for taste-test and the `/press → /age → /cure` chain. Supports `--auto` to skip the handoff gate. Do NOT use for review-only diffs (`/age`), feature design (`/mold`), or fixes where the cause is already known (`/cook` directly). After `/cheese` debug intent; before `/cook --auto` → `/press` → `/age` → `/cure`.
license: MIT
---

# /pasteurize

A discipline for hard bugs. Skip phases only when explicitly justified.

> Attribution: this skill adapts Matt Pocock's `diagnose` skill — <https://github.com/mattpocock/skills/blob/main/skills/engineering/diagnose/SKILL.md>. The six-phase structure and the "build a feedback loop first" insight are his. Easy-cheese-specific adaptations (cheez-* tooling, handoff slug, `--auto` chain, `/cook` handoff for Phase 5) are layered on top.

When exploring the codebase, use `/cheez-search` to orient and check `.cheese/specs/` for any spec or design notes that touch the failing seam.

## Phase 1 — Build a feedback loop

**This is the skill.** Everything else is mechanical. If you have a fast, deterministic, agent-runnable pass/fail signal for the bug, you will find the cause — bisection, hypothesis-testing, and instrumentation all just consume that signal. If you don't have one, no amount of staring at code will save you.

Spend disproportionate effort here. **Be aggressive. Be creative. Refuse to give up.**

### Ways to construct one — try them in roughly this order

1. **Failing test** at whatever seam reaches the bug — unit, integration, e2e.
2. **Curl / HTTP script** against a running dev server.
3. **CLI invocation** with a fixture input, diffing stdout against a known-good snapshot.
4. **Headless browser script** (Playwright / Puppeteer) — drives the UI, asserts on DOM/console/network.
5. **Replay a captured trace.** Save a real network request / payload / event log to disk; replay it through the code path in isolation.
6. **Throwaway harness.** Spin up a minimal subset of the system (one service, mocked deps) that exercises the bug code path with a single function call.
7. **Property / fuzz loop.** If the bug is "sometimes wrong output", run 1000 random inputs and look for the failure mode.
8. **Bisection harness.** If the bug appeared between two known states (commit, dataset, version), automate "boot at state X, check, repeat" so you can `git bisect run` it.
9. **Differential loop.** Run the same input through old-version vs new-version (or two configs) and diff outputs.
10. **HITL bash script.** Last resort. If a human must click, drive _them_ with a structured loop so output still feeds back to you.

Build the right feedback loop, and the bug is 90% fixed.

### Iterate on the loop itself

Treat the loop as a product. Once you have _a_ loop, ask:

- Can I make it faster? (Cache setup, skip unrelated init, narrow the test scope.)
- Can I make the signal sharper? (Assert on the specific symptom, not "didn't crash".)
- Can I make it more deterministic? (Pin time, seed RNG, isolate filesystem, freeze network.)

A 30-second flaky loop is barely better than no loop. A 2-second deterministic loop is a debugging superpower.

### Non-deterministic bugs

The goal is not a clean repro but a **higher reproduction rate**. Loop the trigger 100×, parallelise, add stress, narrow timing windows, inject sleeps. A 50%-flake bug is debuggable; 1% is not — keep raising the rate until it's debuggable.

### When you genuinely cannot build a loop

Stop and say so explicitly. List what you tried. Ask the user for: (a) access to whatever environment reproduces it, (b) a captured artifact (HAR file, log dump, core dump, screen recording with timestamps), or (c) permission to add temporary production instrumentation. Do **not** proceed to hypothesise without a loop. Write a `status: halt` handoff slug (see below) and stop.

Do not proceed to Phase 2 until you have a loop you believe in.

## Phase 2 — Reproduce

Run the loop. Watch the bug appear.

Confirm:

- [ ] The loop produces the failure mode the **user** described — not a different failure that happens to be nearby. Wrong bug = wrong fix.
- [ ] The failure is reproducible across multiple runs (or, for non-deterministic bugs, reproducible at a high enough rate to debug against).
- [ ] You have captured the exact symptom (error message, wrong output, slow timing) so later phases can verify the fix actually addresses it.

Do not proceed until you reproduce the bug.

## Phase 3 — Hypothesise

Generate **3–5 ranked hypotheses** before testing any of them. Single-hypothesis generation anchors on the first plausible idea.

Each hypothesis must be **falsifiable**: state the prediction it makes.

> Format: "If `<X>` is the cause, then `<changing Y>` will make the bug disappear / `<changing Z>` will make it worse."

If you cannot state the prediction, the hypothesis is a vibe — discard or sharpen it.

**Show the ranked list to the user via `AskUserQuestion` before testing.** They often have domain knowledge that re-ranks instantly ("we just deployed a change to #3"), or know hypotheses they've already ruled out. Cheap checkpoint, big time saver. Don't block on it — proceed with your ranking if the user is AFK or running `--auto`.

## Phase 4 — Instrument

Each probe must map to a specific prediction from Phase 3. **Change one variable at a time.**

Tool preference:

1. **Debugger / REPL inspection** if the env supports it. One breakpoint beats ten logs.
2. **Targeted logs** at the boundaries that distinguish hypotheses.
3. Never "log everything and search".

**Tag every debug log** with a unique prefix, e.g. `[DEBUG-a4f2]`. Cleanup at the end becomes a single `/cheez-search` content query. Untagged logs survive; tagged logs die.

**Perf branch.** For performance regressions, logs are usually wrong. Instead: establish a baseline measurement (timing harness, `performance.now()`, profiler, query plan), then bisect. Measure first, fix second.

Use `/cheez-write` for any instrumentation edits — never the host Edit / Write tools.

## Phase 5 — Fix + regression test

Write the regression test **before the fix** — but only if there is a **correct seam** for it.

A correct seam is one where the test exercises the **real bug pattern** as it occurs at the call site. If the only available seam is too shallow (single-caller test when the bug needs multiple callers, unit test that can't replicate the chain that triggered the bug), a regression test there gives false confidence.

**If no correct seam exists, that itself is the finding.** Note it in the handoff slug as an architectural follow-up. The codebase is preventing the bug from being locked down. Skip the test write; do not paper over it. Phase 6's "what would have prevented this bug?" retrospective still applies.

If a correct seam exists:

1. Turn the minimised repro into a failing test at that seam — write it via `/cheez-write`.
2. Watch it fail.
3. Apply the **smallest** production change that makes the test pass — also via `/cheez-write`. No scope creep, no "while I'm here" cleanup.
4. Watch the test pass.
5. Re-run the Phase 1 feedback loop against the original (un-minimised) scenario to confirm the symptom is gone, not just the test seam.

All edits go through `/cheez-write` — never the host Edit / Write tools.

Broader implementation (related cleanup, follow-on changes, anything beyond the minimal fix) is **not** pasteurize's job. Note it in the slug and let `/cook --auto` pick it up in Phase 6's handoff.

## Phase 6 — Cleanup + hand off

Before writing the handoff slug, confirm:

- [ ] Original repro no longer reproduces (re-run the Phase 1 loop).
- [ ] Regression test passes (or absence of seam is documented in the slug).
- [ ] All `[DEBUG-...]` instrumentation removed — run a `/cheez-search` content query for the prefix and verify zero hits.
- [ ] Throwaway harnesses / prototypes deleted (or moved to a clearly-marked debug location and called out in the slug).
- [ ] The confirmed hypothesis is captured in the slug so the commit message downstream can reference it.

**Then ask: what would have prevented this bug?** If the answer involves architectural change (no good test seam, tangled callers, hidden coupling), note it in the slug under an architectural-follow-up line. The chain still runs; the user can pick up the architectural work via `/mold` after the fix lands. Make the recommendation **after** the fix is in, not before — you have more information now than when you started.

Once the checklist is green and the slug is on disk, hand off to `/cook <slug> --auto` (default). Cook --auto picks up the post-fix state, runs its taste-test against the applied diff for spec drift / readability / scope creep, produces its package-ready report, and triggers the autonomous `/press → /age → /cure` chain. Pasteurize itself does not commit, open PRs, or drive the chain — cook owns that.

## Preferred tools and fallbacks

| Need | Prefer | Fallback |
| --- | --- | --- |
| Code search / blast radius | `/cheez-search` (tilth MCP) | flag the gap; do not fall back to host `grep` |
| Reading code | `/cheez-read` (tilth MCP) | flag the gap; do not fall back to host `cat`/`Read` |
| Editing instrumentation | `/cheez-write` (tilth MCP) | flag the gap; do not fall back to host `Edit`/`Write` |
| Diff visualization | `delta` | plain `git diff` |
| GitHub context | `gh` | local git history or user-provided links |
| External sanity check | `/briesearch` | clearly mark as an assumption |

Missing optional tools should not interrupt diagnosis. Keep tool use proportional to the bug.

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

`status: ok` when the regression test is green, the original repro no longer reproduces, and cleanup is done. `status: halt: <reason>` when Phase 1 failed (cannot build a loop, missing environment access, missing artifact), or Phase 3 exhausted both hypothesis rounds without a confirmed cause. `next:` is `cook` for the standard chain, `mold` if the diagnosis itself recommends an architectural spec instead of a per-bug fix, or `done` if the bug was caused outside the repo and no follow-up is needed.

## Handoff

**Pipeline:** cheese (debug) → **[pasteurize]** → cook --auto → press → age → cure → ship

After the report is printed and the handoff slug is on disk, ask via `AskUserQuestion` which downstream to run. Lead each option with the verb (what the user wants to _do_ next):

- **Validate and chain forward** _(recommended when `status: ok`)_ — `/cook <slug> --auto`.
- **Validate without auto chain** — `/cook <slug>` (cook runs taste-test, then the user picks each subsequent step).
- **Spec the architectural follow-up first** — `/mold <slug>` (when `seam: none — architectural follow-up`).
- **Stop** — fix is in tree; defer the chain.

Pre-select **Validate and chain forward** when `status: ok`. The chain default is `--auto` because pasteurize already wrote and verified the fix; the work left for cook → press → age → cure is mechanical validation, not new authoring. Never auto-invoke; the user must still select.

When invoked with `--auto`, skip this `AskUserQuestion` entirely and invoke `/cook <slug> --auto` directly.

## Auto mode

`--auto` is the autonomous-pipeline switch. Propagated from upstream skills (`/cheese --auto`) or invoked directly with `--auto`.

What auto mode does:

1. Phase 3's "show the user the ranked hypothesis list" gate is skipped — proceed with the model's ranking.
2. Phase 4–5 still run in full; the auto signal does not loosen the discipline.
3. After Phase 6 cleanup, invoke `/cook <slug> --auto` directly.
4. From there, cook's own auto-mode contract takes over (press → age → cure cycle).

Auto mode stops early when:

- Phase 1 fails (`status: halt` written, no loop achievable).
- Phase 3 disproves all hypotheses across two rounds (cap at two Phase 3 rounds, then halt).
- Phase 5's seam check finds no correct seam — write `status: halt: no correct regression-test seam` and route to `/mold` instead of `/cook`.
- The fix breaks an unrelated test that pasteurize cannot reconcile within scope.

In every early-stop case, write the halt slug and surface the report. Do not silently downgrade to "best guess".

## Rules

- Do not skip Phase 1. The feedback loop is the skill; everything else is mechanical.
- Do not hypothesise without a reproducing loop.
- Phase 5 writes only the regression test and the **minimal** production change. Broader implementation — related cleanup, follow-on features, refactors the bug suggests — belongs in `/cook`, not pasteurize.
- Do not leave `[DEBUG-...]` tags in the tree — clean them before the handoff slug is written.
- Do not claim "shipped". Pasteurize claims "cause named, regression green, fix in tree, ready for chain". The chain (cook → press → age → cure) claims shipped.
- If the bug exposes an architectural gap (no correct regression-test seam), say so in the slug. Do not silently paper over it.
