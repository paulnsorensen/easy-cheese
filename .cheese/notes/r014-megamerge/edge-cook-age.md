# Cook to Age edge review

## State

broken

Cook and Age do not share one executable typed review boundary.
The direct route also drops required handoff state.

## Evidence

- No skill runtime imports the other skill. Both command bundles use shared helpers (`src/easy_cheese/skills/cook/commands.py:7-25`; `src/easy_cheese/skills/age/commands.py:8-29`).
- Cook exposes `age-route` through `age_route_cli.main`. Age exposes the same command and implementation (`src/easy_cheese/skills/cook/commands.py:21-25`; `src/easy_cheese/skills/age/commands.py:25-29`).
- Cook requests a taste test through a reviewer, not through a full Age report (`skills/cook/references/tdd-loop.md:36-82`).
- Cook requests per-curd and final Age reviews in its fan pathway (`skills/cook/SKILL.md:82-86`; `skills/cook/references/fan-pathway.md:220-248`).
- The typed workflow calls `ReviewDispatch(ReviewRequest)` and expects `ReviewResultWriterView` (`src/easy_cheese_schemas/workflow.py:72-77,1047-1078`).
- Cook declares `CurdResult` as the Age payload (`skills/cook/phase-contract.yaml:8-10`; `skills/cook/SKILL.md:153-165`).
- Age declares `CurdResult` as input (`skills/age/phase-contract.yaml:5-10`).
- Age only documents a diff, range, path, or slug input (`skills/age/SKILL.md:17-38`).
- Age emits `.cheese/age/<slug>.md` with `status`, `next`, `artifact`, `durable_flags`, and `baseline` (`skills/age/SKILL.md:145-188`).
- Cook consumes `status` and `next` through its phase decision (`src/easy_cheese/shared/fanout/phase_decision.py:126-267`).
- The focused seam command passed 245 tests. The passing tests do not detect the contract conflicts.

## Findings by severity

### Blocker

- **[correctness:blocker] The typed curd review has no Age adapter.** Cook declares `CurdResult` at the phase boundary (`skills/cook/phase-contract.yaml:8-10`). The workflow instead sends `ReviewRequest` and expects `ReviewResultWriterView` (`src/easy_cheese_schemas/workflow.py:74,1047-1078`). Age declares `CurdResult` input but documents only CLI review targets (`skills/age/phase-contract.yaml:5-10`; `skills/age/SKILL.md:17-38`). Age uses `blocker`, but `ReviewSeverity` requires `critical` (`skills/age/SKILL.md:57-74`; `src/easy_cheese_schemas/contracts.py:212-216`). Age commands contain no adapter for these types (`src/easy_cheese/skills/age/commands.py:11-106`). **Fix:** Add one host adapter for the declared payload. Convert Age output into `ReviewResultWriterView`. Set `review_kind` explicitly. Use one severity term.

### High

- **[correctness:high] Direct Cook-to-Age review drops `artifact` and `baseline`.** Cook emits both fields and routes closed N/A work directly to Age (`skills/cook/SKILL.md:69-72,131-160,170-184`). Age only checks whether the Cook file exists (`skills/age/SKILL.md:97-100`). Its writer passes an empty artifact and omits `--baseline` (`skills/age/SKILL.md:112-115`). The writer omits a missing baseline by default (`src/easy_cheese/shared/write_handoff_artifact.py:243-267`). **Fix:** Read the Cook handoff by phase and slug. Preserve its artifact and baseline in the Age handoff.
- **[spec:high] Cook and Age assign the Cure cap to different owners.** Cook says fixed chain length owns the cap (`skills/cook/references/auto-mode.md:59-81`). Age tries to count completed Cure passes (`skills/age/SKILL.md:214-225`). Age has no pass-count input (`skills/age/SKILL.md:17-22`). Its own fan-path rule says Age does not count passes (`skills/age/references/handoff-detail.md:90-107`). **Fix:** Remove pass counting from Age. Let Cook's phase table enforce the two-pass cap.
- **[correctness:high] The scoped Age command loses the pipeline slug.** Cook dispatches `/age --scope <touched-paths> --auto` (`skills/cook/references/auto-mode.md:37-48`). Age requires `<slug>` for its lock and report path (`skills/age/SKILL.md:90,151-153`). Age does not define slug derivation for a scoped call (`skills/age/SKILL.md:19-35`). **Fix:** Add an explicit slug option for scoped review. Pass the current Cook slug on every scoped dispatch.
- **[spec:high] Cook does not transfer `--hard` into Age.** Cook declares the flag once, but its Age commands omit it (`skills/cook/SKILL.md:38-45,195-214`). Age describes the flag, but both input forms omit it (`skills/age/SKILL.md:19-22,40-42`). The Age handoff can forward the flag only when it remains in scope (`skills/age/references/handoff-detail.md:62-85`). **Fix:** Add `--hard` to the Age input forms. Forward it through every Cook and Press Age dispatch.
- **[assertions:high] Tests do not exercise the seam from both sides.** Workflow tests inject a synthetic review callback (`tests/schemas/python/test_workflow_thread.py:249-260`). Phase tests pass synthetic `status` and `next` values (`tests/fanout/python/test_phase_decision.py:38-71`). The Age writer test uses an empty artifact and no baseline (`tests/python/test_age_review_lock.py:38-47,116-129`). **Fix:** Emit a Cook handoff, run the Age adapter, and feed the Age handoff into Cook's phase decision. Cover `done`, `cure`, invalid output, baseline, artifact, scope, and flags.

### Medium

- **[spec:medium] Cook does not document the exact `age-route` input.** Cook lists prose categories instead of the accepted tokens (`skills/cook/references/tdd-loop.md:53-64`). It also links to a missing Age `Router call` section. The exact tokens and JSON command live in the Age fan-out reference (`skills/age/references/fan-out.md:5-24`; `src/easy_cheese/shared/fanout/age_route.py:48-66,140-155`). Unknown flags are ignored, so a spelling error removes a risk promotion. **Fix:** List the exact tokens and JSON shape in Cook. Link to `skills/age/references/fan-out.md#router-call`. Test the Cook bundle command with a promoted risk.

### Low

none

## STE100 status

not compliant

- `skills/cook/SKILL.md:63,250` puts two instructions in each sentence.
- `skills/age/SKILL.md:128` uses dense noun clusters and several instructions in one table cell.
- `skills/age/SKILL.md:219-223` assigns two instructions to one sentence and uses an undefined pass-count input.

## Follow-ups

- Add and test one typed Cook-to-Age adapter.
- Preserve the Cook slug, artifact, baseline, and flags through every Age invocation.
- Move Cure pass counting out of Age and into the Cook phase table.
- Repair the cited STE100 violations.
