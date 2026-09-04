# Plate to Hard-cheese Edge Review

## State

broken

Plate promises four final evidence values.
Hard-cheese has no validated input for those values.
A cached PASS can also approve a changed tracked tree.

## Evidence

### Agreement

- Plate runs `/hard-cheese` before review sharing and supplies the final inventory and verification rows (`skills/plate/SKILL.md:45-46`).
- Hard-cheese names Plate as the sole caller at the same boundary (`skills/hard-cheese/SKILL.md:25-32`).
- Both sides use the completion row shape `{target, backend, verified}` (`skills/plate/references/durable-writes.md:44-46`; `skills/hard-cheese/SKILL.md:58-63`).

### Plate producer

- Plate also requires the tracked artifact diff and quality gate result (`skills/plate/references/durable-writes.md:58-61`).
- Plate exposes only `stack-tools` and `validate-publication` as runtime commands (`src/easy_cheese/skills/plate/commands.py:11-29`).
- The validator defines typed `artifacts` and `gate` fields (`src/easy_cheese/skills/plate/publication.py:18-19,81-99`).
- It requires a verified pull request for new publication (`src/easy_cheese/skills/plate/publication.py:156-164`).
- [INFERENCE] Plate cannot use that terminal state at the prepublication gate.

### Hard-cheese consumer

- Hard-cheese accepts only a slug, retry cap, passing score, and log-only flag (`skills/hard-cheese/SKILL.md:12-23`).
- The flow shows the diff summary, inventory, and completion rows (`skills/hard-cheese/SKILL.md:58-63`).
- The judge receives no inventory, tracked diff, or quality gate result (`skills/hard-cheese/SKILL.md:64-71`).
- The runtime exposes only `append-attempt` and `freshness-check` (`src/easy_cheese/skills/hard_cheese/commands.py:14-34`).
- Freshness compares only the current HEAD and prior score (`src/easy_cheese/skills/hard_cheese/freshness_check.py:165-189`).
- The audit schema stores no Plate evidence (`skills/hard-cheese/SKILL.md:90-117`).

### Tests

- The hard-cheese seam test checks one Plate sentence only (`tests/python/test_hard_cheese.py:161-166`).
- Plate runtime tests validate terminal publication data only (`tests/python/test_plate_runtime.py:14-43`).
- No Plate test in `test_plate_contract.py` or `test_plate_runtime.py` references `hard`.
- Focused execution passed 78 tests across both runtime suites and the prose contract suite.
- A temporary repository probe changed a tracked file without changing HEAD.
- `decide()` returned `previously_passed` after that change.

## Findings by severity

### Blocker

- **A changed final state keeps an old PASS.** Plate prohibits an earlier snapshot (`skills/plate/SKILL.md:45-46`). Hard-cheese stops on matching HEAD and score (`skills/hard-cheese/SKILL.md:46-56`; `src/easy_cheese/skills/hard_cheese/freshness_check.py:165-189`). **Fix:** Hash HEAD, the tracked diff, the specification, and the canonical Plate context. Store and compare this reviewed-state digest.

### High

- **Hard-cheese drops two required producer values.** Plate added the tracked artifact diff and quality gate result. Hard-cheese still consumes the older inventory and row pair. No command validates this handoff. **Fix:** Define one JSON context with `artifacts`, `tracked_diff_digest`, and `gate`. Require all fields. Reject missing, unverified, or stale context.
- **The gate outcome policy conflicts.** Plate publishes only after a pass (`skills/plate/evals/evals.json:109-114`). Hard-cheese returns zero for `LOGGED` and `ERROR` (`skills/hard-cheese/SKILL.md:73-78,152-177`). **Fix:** Define the Plate status matrix. Continue on PASS and explicit LOGGED. Ask after ERROR. Stop on FAILED.
- **The seam tests are one-sided and text-only.** The current test does not send or consume final evidence (`tests/python/test_hard_cheese.py:161-166`). **Fix:** Add one producer-to-consumer test. Cover missing fields, failed verification, changed tracked data, and every gate status.

### Medium

none

### Low

none

## STE100 status

- `skills/plate/SKILL.md:23,35,53,63,92,101` needs active voice, separate instructions, and consistent terms.
- `skills/hard-cheese/SKILL.md:30,32,47,127,157,197` needs one gate term and separate instructions.

## Follow-ups

- Define and validate the Plate-to-Hard-cheese context.
- Bind freshness to the complete reviewed state.
- Define the gate status matrix in both skills.
- Add producer and consumer seam tests.
- Rewrite both SKILL files for STE100.
