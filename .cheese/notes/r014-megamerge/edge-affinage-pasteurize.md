# Affinage to Pasteurize Edge Review

## State

broken

Affinage can request Pasteurize, but the edge has no reliable request or return contract.

## Evidence

### Calls and imports

- Affinage names `/pasteurize` only in `skills/affinage/references/flow-details.md:82-89` and `skills/affinage/references/handoff-templates.md:28-38`.
- A source search found no Pasteurize import or call under `src/easy_cheese/skills/affinage/`.
- The Affinage manifest exposes four unrelated commands (`src/easy_cheese/skills/affinage/commands.py:7-39,42-59`).
- The Pasteurize manifest imports no Affinage code (`src/easy_cheese/skills/pasteurize/commands.py:7-28`).
- The direct edge is a prose dispatch of `/pasteurize`, not a Python call or bundle command.

### Request data

- Affinage emits a Markdown claim with a comment identifier, claim text, reason, and suggested action (`skills/affinage/references/report-template.md:46-50`).
- Pasteurize defines no input syntax, source report field, comment field, or Affinage report reader (`skills/pasteurize/SKILL.md:22-71`).
- The edge defines no required fields, field types, or defaults.

### Reproduction command

- Pasteurize calls `repro-rerun` with `--cmd <string>` and `--runs <integer>` (`skills/pasteurize/SKILL.md:60-70`).
- The skill selects five runs, while the command defaults to three (`src/easy_cheese/skills/pasteurize/repro_rerun.py:32,74-82`).
- The command returns `exit_code: int`, `reproduced: bool`, `runs: int`, and `failures: int` (`src/easy_cheese/skills/pasteurize/repro_rerun.py:35-56`).
- A missing command or a run count below one causes a CLI error (`src/easy_cheese/skills/pasteurize/repro_rerun.py:59-66`).
- Affinage supplies no command, run count, expected exit code, expected output, or failure matcher.

### Result data and errors

- Affinage requires exact evidence and an actual result before a reply (`skills/affinage/references/flow-details.md:82-90`).
- Pasteurize emits `status`, `next`, `artifact`, `cause`, `loop`, `seam`, `fix`, and `follow_up` (`skills/pasteurize/SKILL.md:245-268`).
- Affinage does not name or consume the Pasteurize slug or any Pasteurize result field.
- Pasteurize halts when no loop or test seam exists (`skills/pasteurize/SKILL.md:41-48,292-305`).
- Affinage does not map either halt mode to a reply or a retained investigation state.
- Pasteurize sends a successful result to Cook, not back to Affinage (`skills/pasteurize/SKILL.md:178-180,270-290`).

## Findings by severity

### Blocker

- **The reproduction command can confirm the wrong claim.** Affinage requires exact evidence and an actual result (`skills/affinage/references/flow-details.md:84-89`). Pasteurize also requires the expected failure mode (`skills/pasteurize/SKILL.md:68-71`). `rerun` discards command output and accepts every nonzero exit (`src/easy_cheese/skills/pasteurize/repro_rerun.py:42-56`). Its tests protect this incorrect rule (`tests/pasteurize/python/test_repro_rerun.py:26-75,103-121`). **Fix:** Add expected exit and bounded output matchers. Return each matched result. Reject an unrelated failure.

### High

- **Pasteurize cannot return an investigation verdict to Affinage.** Affinage sends a plausible claim that can be false (`skills/affinage/references/flow-details.md:70,82-90`). Pasteurize blocks until reproduction, adds a test, changes production code, and routes to Cook (`skills/pasteurize/SKILL.md:60-71,117-149,178-180`). Its slug has no source report, comment identifier, expected symptom, mode, or return phase (`skills/pasteurize/SKILL.md:245-268`). **Fix:** Add an investigation request with typed source and symptom fields. Add `reproduced`, `not-reproduced`, and `inconclusive` results. Return the result to Affinage before any fix starts.

### Medium

- **Tests do not exercise the seam from either side.** The closest Affinage tests stop at `Needs-investigation` classification (`tests/python/test_pr_status.py:734-753,900-940`). The Pasteurize tests exercise only the standalone rerun helper (`tests/pasteurize/python/test_repro_rerun.py:26-157`). A repository search found no test that passes or returns this handoff. **Fix:** Add an Affinage producer contract test. Add a Pasteurize consumer test for positive, negative, and halt results.

### Low

none

## Contract changes

The reconciliation notes label this edge unchanged (`.cheese/notes/r014-megamerge/affinage.md:47-48`; `.cheese/notes/r014-megamerge/pasteurize.md:22-26`).
No changed field or command lacks a matching migration.
The edge is broken because it never defines request and return data.

## Test result

`uv run --frozen pytest -q tests/python/test_pr_status.py tests/pasteurize/python/test_repro_rerun.py` passed 54 tests.
These tests do not exercise the edge.

## STE100 status

not compliant

- `skills/affinage/SKILL.md:44,51,84,194` puts multiple instructions in one sentence. Split each instruction into a separate sentence.
- `skills/affinage/SKILL.md:76,111,217` uses multiple terms for the fresh review. Use `fresh review` everywhere.
- `skills/pasteurize/SKILL.md:24-30` uses `signal` and `loop` for one term. Use `feedback loop` everywhere.
- `skills/pasteurize/SKILL.md:81` gives two commands in one sentence. Give each command in a separate sentence.
- The edge instructions in both Affinage references comply with ASD-STE100.
- This note complies with ASD-STE100.
