# Cross-skill work contract implementation gaps

Status: open as of 2026-07-26
Spec: [Cross-skill work contract](./cross-skill-work-contract.md)
Review stack tip: `feat/cross-skill-work-contract` / PR #331

The reconstructed stack preserves the implementation from PR #331 for review, but it is not ready to merge as a complete implementation of the approved specification. Every cumulative layer passes `just check`; the remaining work is behavioral and contract conformance, not stack mechanics.

## 1. Replace runtime YAML with JSON frontmatter

The current handoff parser imports PyYAML at runtime, WorkRecord rendering calls the same YAML helper, and the bundle builder vendors PyYAML plus its license into `cheese.pyz`.[^1] That implements the superseded serialization decision.

Required closure:

- parse and render persisted HandoffEnvelope and WorkRecord frontmatter with standard-library `json`;
- retain `---` fences and Markdown bodies;
- keep source `handoff-contract.yaml` declarations in YAML;
- use pinned PyYAML only while validating and compiling the registry during bundle construction;
- embed the compiled JSON-compatible registry, not the YAML parser;
- remove `yaml/` and `licenses/PyYAML-LICENSE.txt` from released artifacts;
- replace YAML round-trip tests with JSON round-trip and archive-member exclusion tests under `python3 -S`;
- use the approved missing-companion diagnostic rather than a missing-PyYAML diagnostic.

Because the implementation has not shipped, rewrite the versioned v1 persistence before release rather than supporting the rejected YAML representation as a durable format.

## 2. Expose and wire the task lifecycle

The domain layer defines `claim_task` and `transition_task`, but `work_cli.py` exposes only `ensure`, `continue`, and `migrate`.[^2] Cheese continuation describes dispatching ordered tasks, yet there is no public command path that returns stable task IDs, claims a task, blocks it, returns it to pending, abandons it, or binds its completing handoff.[^3]

Required closure:

- add public JSON CLI operations for task listing/resolution, claim, block, return-to-pending, abandon, and task-bound handoff commit;
- return stable task IDs with ordered directives from continuation resolution;
- make Cheese dispatch claim before invoking a phase and pass both work and task identity;
- make the resulting phase handoff complete that exact bound task once;
- cover the public command path, not only direct Python calls.

## 3. Enforce explicit unblock before work resumes

`NONTERMINAL` includes `blocked`. Both `claim_task` and handoff commit accept any attempt whose status is in that set, so a blocked attempt can claim or complete work without an explicit transition to active or paused.[^4]

Required closure:

- require `attempt.status == "active"` for task claim and handoff commit;
- retain blocked attempts during join without creating a replacement;
- require revision-checked `transition_attempt` to clear the block;
- add regression tests for blocked → claim rejection and blocked → commit rejection, followed by explicit unblock success.

## 4. Make legacy migration structurally conservative

The current migrator checks the first status line and second `next:` line, then treats the rest of the file as an importable body.[^5] That admits unrelated files with a matching two-line prefix and does not meet the bounded recognized-header requirement.

Required closure:

- define the exact recognized legacy header and heading shapes;
- reject unknown preamble fields, misplaced headers, truncated bodies, and unrelated trailing structures;
- preserve every rejected source unchanged and report it as skipped;
- retain the existing deterministic `gated` and list-form `next` conversions only after structural recognition;
- add adversarial fixtures for lookalike non-handoffs and ambiguous relationships.

## 5. Close acceptance coverage through production paths

The current tests prove important primitives, but the missing public task path, blocked-attempt restrictions, JSON runtime, archive exclusions, and conservative migration cannot be proven by the existing suite because those behaviors are not implemented.

Required closure:

- create a requirement-to-test matrix for every WHEN/SHALL item in the tracked spec;
- require a production path for every criterion, not a test-only manufactured state;
- exercise CLI entry → persistence → continuation → task claim → phase handoff → task completion end to end;
- exercise crash recovery at every transaction boundary and changed-content operation-ID rejection;
- keep `just check` green on each corrected stack layer;
- finish with `python3 -S skills/cheese/scripts/cheese.pyz contract-registry validate` and archive inspection proving no PyYAML ships.

## Closure order

1. Rewrite serialization and packaging together so no intermediate release contract depends on runtime YAML.
2. Tighten blocked-attempt rules in WorkRecord and atomic commit.
3. Add public task commands and Cheese orchestration.
4. Harden legacy migration.
5. Build the acceptance matrix, add missing end-to-end tests, and run the full quality gates.
6. Re-review the corrected stack against the tracked spec before making any implementation PR ready for merge.

[^1]: `feat/cross-skill-work-contract:shared/scripts/handoff.py:218-251`; `feat/cross-skill-work-contract:shared/scripts/work.py:89-113`; `feat/cross-skill-work-contract:scripts/build_pyz.py:1-27,285-394`.
[^2]: `feat/cross-skill-work-contract:shared/scripts/work.py:380-406`; `feat/cross-skill-work-contract:shared/scripts/work_cli.py:7-32`.
[^3]: `feat/cross-skill-work-contract:skills/cheese/SKILL.md:89-103`; `feat/cross-skill-work-contract:shared/scripts/work_cli.py:10-32`.
[^4]: `feat/cross-skill-work-contract:shared/scripts/work.py:25,380-393`; `feat/cross-skill-work-contract:shared/scripts/write_handoff_artifact.py:175-225`.
[^5]: `feat/cross-skill-work-contract:shared/scripts/work.py:522-587`.