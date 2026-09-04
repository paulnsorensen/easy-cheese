# Cure Area Review

## Verdict

reject

## Blocker

- **[correctness:blocker] The canonical writer deletes the Cure report body.** `skills/cure/SKILL.md:97-99,135-179` requires a report, then runs the writer without `--body-file`. `src/easy_cheese/shared/write_handoff_artifact.py:106-109,164-173` replaces the same target with only the preamble. The command probe removed `## Applied` and its finding from `.cheese/cure/loss.md`. **Fix:** Write a body-only file first. Pass it through `--body-file`. Also pass `--baseline` and `--durable-flags` when these values exist.
- **[spec:blocker] The required typed Cure path cannot consume each advertised input.** `skills/cure/SKILL.md:14-25` accepts Age reports, CI summaries, and scoped instructions. Lines 49-75 require `PlannerResult`, `CurdPlan`, and confirmed `DiagnosisResult` values. `skills/age/references/handoff-detail.md:71-85` and `skills/affinage/references/handoff-templates.md:42-55` provide only a report and selected identifiers. `src/easy_cheese_schemas/workflow.py:1180-1210` requires bindings for every plan curd. **Fix:** Define one normal repair path for report, CI, and scoped inputs. Use typed Cure only when the handoff supplies a plan and complete confirmed bindings.

## High

- **[spec:high] The documented writer cannot emit the terminal Cure state.** `skills/cure/SKILL.md:141-170` allows `next: done`, but its command always passes `--next age` with a payload schema. `src/easy_cheese/shared/write_handoff_artifact.py:22-24,47-58,84-95` writes `--next` into the preamble and validates that transition. The probe made `--next done` with the payload schema exit with status 3. The command wrote `next: done` only after the probe omitted the schema. **Fix:** Show separate commands for `age` and `done`. Remove the false routing statement at line 161.
- **[correctness:high] Post-publication write-back leaves tracked changes outside the Plate transaction.** `skills/cure/SKILL.md:205,221-246` and `skills/cure/references/post-pr-writeback.md:3-41` place knowledge capture after publication. The fallback writes tracked files at `post-pr-writeback.md:28-30`. `skills/plate/SKILL.md:63-76` requires all durable writes before its commit and forbids later wiki publication. **Fix:** Move knowledge capture before Plate's final writing gate. Delete the deferred move section after the cutover.
- **[spec:high] Cure can replace a required fresh-context review with a same-context check.** `skills/cure/SKILL.md:83-86` requires fresh context, names Opus, and permits an inline fallback. `skills/cheese/references/agent-resolution.md:65-71` requires a halt when fresh-context isolation is unavailable. `skills/cook/references/tdd-loop.md:68-78` permits inline review only for a nested deferral or a small diff. **Fix:** Resolve the reviewer through the shared resolver at powerful and high settings. Allow inline review only under Cook's small-diff cost gate. Make a nested coder defer the authoritative review.

## Medium

none

## Low

- **[spec:low] The selection guide omits an accepted range verb.** `skills/cure/references/selection.md:61-72` calls its list complete but omits `1-3`. `src/easy_cheese/shared/findings.py:180,213-222,239-247` accepts that range. **Fix:** Add the range verb to the guide, or remove it from the parser.
- **[deslop:low] The area uses multiple terms for two workflow concepts.** `skills/cure/SKILL.md:31,205,221,236,246`, `skills/cure/references/selection.md:19,78,120`, and `skills/cure/references/post-pr-writeback.md:1,27` vary the terms. **Fix:** Use `automatic mode` and `post-PR write-back` throughout the area.

## Simplifications

- Separate normal report repair from the typed per-curd path. Do not make one path imitate both contracts.
- Give the handoff writer two complete command examples. Remove prose that restates the writer implementation.
- Let Plate own knowledge capture before its final transaction. Remove the `[TBD]` section from `post-pr-writeback.md`.
- Replace the model-specific reviewer rule with the shared agent resolver.
- Keep the command wrappers. They form the required manifest dispatcher surface.

## Edge check

| Edge | State | Evidence |
| --- | --- | --- |
| cure to shared | broken | `commands.py:7-96` exposes all eight helpers. Bundle help matches the manifest. `SKILL.md:151-171` misstates the handoff writer contract. |
| cure to schemas | broken | `workflow.py:1180-1210,1305-1329` validates the plan and complete bindings. Normal Cure inputs do not supply them. |
| cook to cure | ok | `cook/references/fan-pathway.md:87-100` supplies the plan and complete `CureDiagnosisBinding` collection. |
| age to cure | broken | `age/references/handoff-detail.md:71-85` supplies only the report path and selection identifiers. |
| cure to age | broken | The documented command deletes the report body and cannot emit the documented terminal form. |
| affinage to cure | broken | `affinage/references/handoff-templates.md:42-55` supplies only the report path and selection identifiers. |
| cure to mold | ok | `domain-model-correction.md:5-31` preserves Mold terms. `shared/paths.py:555-602` supplies `domain_model_target`. |
| cure to plate | broken | Cure writes knowledge after Plate publishes. Plate requires those writes before its final commit. |
| cure to hard-cheese | ok | `SKILL.md:227-234` forwards `--hard` only through Plate. `hard-cheese/references/composition.md:3-13` requires that boundary. |
| cure to cheese | broken | `SKILL.md:83-86` conflicts with the shared fresh-context and model resolution rules. |
| cure to wiki-ingest | untested | HEAD has no tracked `skills/wiki-ingest/SKILL.md`. Cure documents this command as optional and provides a file fallback. |
| build to cure | ok | `skills/cure/scripts/cure.pyz --help` exposes the same eight commands as `commands.py:66-92` and `references/commands.md:5-14`. |

## STE100 status

- `skills/cure/SKILL.md:31,45,116,205,221,236,246` needs active voice, sentence capitalization, and consistent terms.
- `skills/cure/references/cure-discipline.md:5,10,53` uses `fixed`, `Applied`, and `cured` for one state.
- `skills/cure/references/post-pr-writeback.md:1,27` uses `learning write-back` instead of the area term.
- `skills/cure/references/selection.md:19,78,120` uses two terms for automatic mode.
- The audit found no violation in `auto-mode.md`, `commands.md`, or `domain-model-correction.md`.
