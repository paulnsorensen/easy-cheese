# Cross-skill work contract implementation gaps

Status: open as of 2026-07-27
Spec: [Cross-skill work contract](./cross-skill-work-contract.md)
Review stack tip: `feat/cross-skill-work-contract` / PR #331

The review stack now implements the approved YAML persistence and packaging decision: HandoffEnvelope and WorkRecord use schema-bounded YAML frontmatter, and the deterministic `cheese.pyz` bundles pinned pure-Python PyYAML plus its license. The archive tests exercise both persisted formats under `python3 -S` and prove reproducible bytes.[^1]

Four behavioral gaps remain before the stack implements the full specification. Keep every implementation PR in draft until these close and the corrected stack is re-reviewed.

## 1. Expose and wire the task lifecycle

The domain layer defines `claim_task` and `transition_task`, but `work_cli.py` exposes only `ensure`, `continue`, and `migrate`.[^2] Cheese continuation describes dispatching ordered tasks, yet there is no public command path that returns stable task IDs, claims a task, blocks it, returns it to pending, abandons it, or binds its completing handoff.[^3]

Required closure:

- add public JSON CLI operations for task listing/resolution, claim, block, return-to-pending, abandon, and task-bound handoff commit;
- return stable task IDs with ordered directives from continuation resolution;
- make Cheese dispatch claim before invoking a phase and pass both work and task identity;
- make the resulting phase handoff complete that exact bound task once;
- cover the public command path, not only direct Python calls.

## 2. Enforce explicit unblock before work resumes

`NONTERMINAL` includes `blocked`. Both `claim_task` and handoff commit accept any attempt whose status is in that set, so a blocked attempt can claim or complete work without an explicit transition to active or paused.[^4]

Required closure:

- require `attempt.status == "active"` for task claim and handoff commit;
- retain blocked attempts during join without creating a replacement;
- require revision-checked `transition_attempt` to clear the block;
- add regression tests for blocked → claim rejection and blocked → commit rejection, followed by explicit unblock success.

## 3. Make legacy migration structurally conservative

The current migrator checks the first status line and second `next:` line, then treats the rest of the file as an importable body.[^5] That admits unrelated files with a matching two-line prefix and does not meet the bounded recognized-header requirement.

Required closure:

- define the exact recognized legacy header and heading shapes;
- reject unknown preamble fields, misplaced headers, truncated bodies, and unrelated trailing structures;
- preserve every rejected source unchanged and report it as skipped;
- retain the existing deterministic `gated` and list-form `next` conversions only after structural recognition;
- add adversarial fixtures for lookalike non-handoffs and ambiguous relationships.

## 4. Close acceptance coverage through production paths

The archive test now proves YAML persistence and parsing through the released runtime under `python3 -S`, but the missing task commands, blocked-attempt restrictions, and conservative migration still lack production paths because those behaviors are not implemented.[^1]

Required closure:

- create a requirement-to-test matrix for every WHEN/SHALL item in the tracked spec;
- require a production path for every criterion, not a test-only manufactured state;
- exercise CLI entry → persistence → continuation → task claim → phase handoff → task completion end to end;
- exercise crash recovery at every transaction boundary and changed-content operation-ID rejection;
- keep `just check` green on each corrected stack layer;
- inspect the final archive and run its contract, WorkRecord, and HandoffEnvelope paths under `python3 -S`.

## Closure order

1. Tighten blocked-attempt rules in WorkRecord and atomic commit.
2. Add public task commands and Cheese orchestration.
3. Harden legacy migration.
4. Build the acceptance matrix, add missing end-to-end tests, and run the full quality gates.
5. Re-review the corrected stack against the tracked spec before making any implementation PR ready for merge.

[^1]: `shared/scripts/handoff.py:218-251`; `shared/scripts/work.py:90-116`; `scripts/build_pyz.py:284-411`; `tests/python/test_build_pyz.py:34-147`.
[^2]: `shared/scripts/work.py:380-406`; `shared/scripts/work_cli.py:7-32`.
[^3]: `skills/cheese/SKILL.md:89-103`; `shared/scripts/work_cli.py:10-32`.
[^4]: `shared/scripts/work.py:25,380-393`; `shared/scripts/write_handoff_artifact.py:175-232`.
[^5]: `shared/scripts/work.py:522-615`.