# Pasteurize Area Review

## Verdict

reject

## Blocker

- **[correctness] The `debug-tag-sweep` command cannot certify a clean repository.** The skill requires a root scan and treats status 0 as clean (`skills/pasteurize/SKILL.md:164-172`). The scanner matches its own examples, source constants, tests, and run logs. The root probe reported four files and 398 matches. **Fix:** Require exact session tags. Exclude tool logs. Scan only changed source files.
- **[correctness] The rerun verdict cannot confirm the expected failure.** The skill requires failure-mode confirmation (`skills/pasteurize/SKILL.md:68-71`). The command manifest exposes the rerun helper (`src/easy_cheese/skills/pasteurize/commands.py:24-39`). The helper discards output and accepts any nonzero exit (`src/easy_cheese/skills/pasteurize/repro_rerun.py:42-56`). A probe that printed `wrong failure` still returned `reproduced: true` without output evidence. **Fix:** Accept an expected exit code and a bounded output pattern. Report each run match. Require the configured reproduction threshold.
- **[spec] The Pasteurize handoff cannot meet the canonical phase contract.** The template places custom fields before the orientation (`skills/pasteurize/SKILL.md:245-260`). The parser treats `cause:` as the orientation and ignores the intended orientation (`src/easy_cheese/shared/handoff.py:105-161`). The phase registry has no Pasteurize source (`src/easy_cheese_schemas/_compiled_phase_registry.py:5-103`). The canonical writer probe rejected the source phase. **Fix:** Add `skills/pasteurize/phase-contract.yaml`. Expose the canonical writer in the command manifest. Put the orientation on line four. Put cause details after a blank line.

## High

- **[spec] The skill looks for specifications in the wrong store.** The skill checks `.cheese/specs/` (`skills/pasteurize/SKILL.md:13-14`). Shared paths stores `specs` under the project XDG directory (`src/easy_cheese/shared/paths.py:48-54`). The resolver returned the XDG path during the probe. **Fix:** Consume the upstream artifact pointer or expose the shared artifact resolver.
- **[correctness] `repro-rerun` has no execution timeout.** The skill requires a loop under 30 seconds (`skills/pasteurize/SKILL.md:50-58`). The helper calls `subprocess.run` without a timeout (`src/easy_cheese/skills/pasteurize/repro_rerun.py:42-48`). A hung command blocks the phase without a built-in stop. **Fix:** Add a required per-run timeout and an overall limit. Terminate the complete child process group.
- **[spec] The frontmatter does not identify user triggers.** The description states capability and workflow only (`skills/pasteurize/SKILL.md:3-5`). The skill-authoring contract requires concrete user phrases and a `Use when` trigger. **Fix:** Name bug reports, failures, flaky tests, and unexplained regressions. Exclude fixes with a known cause.

## Medium

- **[deslop] The bundle ships an unused future fan-out command.** The skill says it starts no agents. It says the policy is for future work (`skills/pasteurize/SKILL.md:182-216`). The command manifest still exposes `pasteurize-route` (`src/easy_cheese/skills/pasteurize/commands.py:17-21,33-36`). Repository search found only the declaration, generated documentation, and bundle contract tests. **Fix:** Remove the command and section until a dispatch uses the policy. Remove the Pasteurize-only shared policy with them.
- **[spec] The skill lacks the required discipline section.** The skill enforces a non-skippable gate (`skills/pasteurize/SKILL.md:22-180,308-316`). It has no Iron Law, Red Flags, or rationalization table. **Fix:** Add one compact discipline section. Keep the detailed phase steps in their current sections.

## Low

- **[spec] The fan-out table omits the exact score of 250.** The rows use `< 250` and `> 250` (`skills/pasteurize/SKILL.md:190-200`). The next sentence and runtime classify 250 as tight (`skills/pasteurize/SKILL.md:202`). **Fix:** Use `<= 250` for each tight row.

## Simplifications

- Delete the dormant fan-out command and its Pasteurize-only shared policy. Do not move the unused API.
- Use the canonical handoff writer. Do not maintain a second preamble format.
- Make one rerun verdict own the expected symptom, threshold, and timeout.
- Scan exact session tags in changed source files. Do not scan task logs or tool source.
- Use the shared artifact resolver for specifications. Do not reconstruct its path.

## Edge check

| Edge | State | Evidence |
| --- | --- | --- |
| `pasteurize -> shared bundle commands` | ok | `commands.py:7-44` uses symbols that exist in `bundle_commands.py:61-154`. |
| `pasteurize -> shared fan-out route` | ok | The route import exists. The bundle returned `1` for valid score-250 JSON. |
| `pasteurize -> shared CLI helpers` | ok | Both helpers import `shared.cli`. Both bundle commands started successfully. |
| `build -> pasteurize` | ok | Bundle help lists all three manifest commands. `references/commands.md:7-9` matches them. |
| `cheese -> pasteurize` | ok | `classification.md:103-118` routes unexplained failures to Pasteurize. |
| `cook -> pasteurize` | ok | `quality-gates.md:63-69` defines the isolated repair dispatch and override. |
| `affinage -> pasteurize` | ok | `flow-details.md:82-89` uses Pasteurize for a requested regression test. |
| `pasteurize -> phase handback` | broken | The phase registry omits Pasteurize. The canonical writer rejected the phase. |
| `pasteurize -> specification store` | broken | The skill uses `.cheese/specs/`. The resolver uses the project XDG directory. |
| emitted `debug-tag-sweep` command | broken | The required root probe matched the scanner's own repository files. |
| emitted `repro-rerun` command | broken | The verdict omits failure evidence and has no timeout. |

## STE100 status

- `skills/pasteurize/SKILL.md:24-30` uses `signal` and `loop` for one feedback-loop meaning. Use `feedback loop`.
- `skills/pasteurize/SKILL.md:81` gives two Claude commands in one sentence. Split the commands into separate sentences.
- `skills/pasteurize/references/commands.md:8` uses `lanes` where the skill uses `agents`. Use `agents`.
- `skills/pasteurize/references/commands.md:9` uses undefined `N` and the shortened term `repro`. Use `specified number` and `reproduction`.
- `skills/pasteurize/references/feedback-loops.md` is compliant.

## Follow-ups

- Register Pasteurize in the phase contract and expose the canonical handoff writer.
- Correct the handoff template and add a parser test for its complete preamble.
- Make `repro-rerun` match the expected symptom and enforce time limits.
- Make `debug-tag-sweep` scan exact session tags without tool artifacts.
- Resolve specification paths through the shared artifact resolver.
- Remove the dormant fan-out command and its shared policy.
- Correct the frontmatter triggers, discipline section, fan-out boundary, and STE100 terms.
