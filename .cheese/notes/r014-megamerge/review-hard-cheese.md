# Hard-cheese Review

## Verdict

reject

The gate can accept a changed tree and a non-causal explanation. The judge contract also conflicts with shared agent rules.

## Blocker

- **[correctness] Freshness does not identify the reviewed tree.** `skills/hard-cheese/SKILL.md:40-56` defines a diff scope but checks only `HEAD`. `src/easy_cheese/skills/hard_cheese/freshness_check.py:178-189` compares only the recorded SHA and score. A behavioral probe changed a tracked file without a commit. The command still returned `previously_passed` with status zero. **Fix:** Compute one digest for `HEAD`, the working diff, the optional specification, and Plate evidence. Store and compare that digest.
- **[spec] The default rubric accepts an explanation without causal logic.** `skills/hard-cheese/references/judge-prompt.md:21-31` defines score 3 as Multistructural with no causal link. The same text accepts score 3 as sufficient causal understanding. The cited paper defines score 3 as Relational and requires cause-and-effect reasoning. `tests/python/test_hard_cheese.py:83-120` protects the incorrect remap. **Fix:** Restore the paper's score labels and update the tests. Keep score 3 as Relational.
- **[spec] The judge power rule conflicts with the shared resolver.** `skills/hard-cheese/SKILL.md:124,210-214` requests `default` power without a reason. `skills/cheese/references/agent-resolution.md:83,86,110-113` requires `powerful` for a reviewer. **Fix:** Require `powerful` in both hard-cheese instructions.
- **[spec] The artifact writer cannot produce the documented artifact.** `skills/hard-cheese/SKILL.md:94-108,214` requires frontmatter and an `agent_resolution` block. `src/easy_cheese/skills/hard_cheese/append_attempt.py:110-117` creates only a table. `tests/hard-cheese/python/test_append_attempt.py:155-165` requires that incompatible output. **Fix:** Make `append-attempt` own the complete artifact schema under its lock. Add a first-write behavior test for every required field.

## High

- **[security] The judge prompt does not isolate untrusted instructions.** `skills/hard-cheese/references/judge-prompt.md:15-45,49-56` sends the diff and explanation to the judge. The system prompt does not reject instructions inside either value. The cited paper includes this rejection rule. **Fix:** Mark both values as untrusted data. Reject their embedded instructions before the rubric runs. Validate the returned object independently.
- **[spec] The telemetry claim hides a content-retention difference.** `skills/hard-cheese/SKILL.md:23,110-119,142-150` says log-only mode matches vibecheck. It stores the complete explanation and lists only fail-open behavior as a difference. The cited paper records explanation length and never records explanation content. **Fix:** Add this difference to the policy. Keep no-judge telemetry length-only, or require an explicit audit-content option.
- **[spec] The artifact status list omits `ERROR`.** `skills/hard-cheese/SKILL.md:105` excludes `ERROR`. Lines 78, 165, and 177 require this status. `src/easy_cheese/skills/hard_cheese/append_attempt.py:165` also accepts it. **Fix:** Add `ERROR` to the canonical status list and its behavior test.

## Medium

none

## Low

- **[deslop] Three prose files violate the required term and instruction rules.** `skills/hard-cheese/SKILL.md:30,32,47,127,157,197` uses multiple gate-execution terms and compounds instructions. `skills/hard-cheese/references/composition.md:13,17,37,39` has the same problems. `skills/hard-cheese/references/judge-prompt.md:51` combines two instructions. **Fix:** Use `run` for gate execution. Split each compound instruction into separate sentences.

## Simplifications

- Make `append-attempt` the only artifact writer. Remove hand-written frontmatter steps from the skill flow.
- Replace independent freshness fields with one reviewed-state digest.
- Remove `pass` from the judge JSON. The parent already derives it from `score` and `passing_score`.
- Keep the two decorated command wrappers. The shared command manifest requires their declaration sites.
- Remove no other helper from the five reviewed paths. No superseded command implementation remains there.

## Edge check

| Edge | State | Evidence |
| --- | --- | --- |
| `hard-cheese -> shared` | ok | `commands.py:7-39` resolves `bundle_command`, `derive_command`, and `dispatch` from `bundle_commands.py:61-154`. Both bundled handlers returned help. |
| `affinage -> hard-cheese` | ok | `skills/affinage/SKILL.md:53` passes `--hard` to terminal Plate. |
| `cheese -> hard-cheese` | ok | `skills/cheese/SKILL.md:25-30` passes `--hard` to Plate before publication. |
| `mold -> hard-cheese` | ok | `skills/mold/SKILL.md:121-125` makes Plate the only gate runner. |
| `cook -> hard-cheese` | ok | `skills/cook/SKILL.md:38-43` passes `--hard` through Plate. |
| `press -> hard-cheese` | ok | `skills/press/SKILL.md:145-153` passes `--hard` to Age and later phases. |
| `age -> hard-cheese` | ok | `skills/age/SKILL.md:37-42` passes `--hard` through Cure to Plate. |
| `cure -> hard-cheese` | ok | `skills/cure/SKILL.md:227-234` passes `--hard` to Plate after durable writes. |
| `plate -> hard-cheese` | ok | `skills/plate/SKILL.md:45-46` supplies the final inventory and verification rows. |
| `hard-cheese -> age` | ok | `skills/hard-cheese/SKILL.md:197` uses the scale from `skills/age/references/voice.md:20-23`. |
| `hard-cheese -> cheese` | broken | `SKILL.md:124,210-214` conflicts with the shared reviewer power rule and omits the required resolution block. |
| `build -> hard-cheese` | ok | `references/commands.md:1-8` matches `COMMANDS`. The bundle contains the exact current `commands.py` bytes and dispatches both handlers. |

## STE100 status

- `skills/hard-cheese/SKILL.md` needs one gate-execution term and separate instruction sentences.
- `skills/hard-cheese/references/composition.md` needs one gate-execution term and separate instruction sentences.
- `skills/hard-cheese/references/judge-prompt.md` needs two sentences at line 51. Quoted material remains exempt.
- `skills/hard-cheese/references/commands.md` is compliant.
