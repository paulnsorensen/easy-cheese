# ADR: Cook prepares missing plans but preserves plan approval

Status: implemented for the repository boundary; external harness integration remains (2026-09-18).

Cook may generate a missing Full-tier plan from approved scope. It must request approval of the generated plan before execution.

## Context

Issue 694 exposed a spec that passed Mold shape validation but could not enter Cook. Scope approval did not establish an approved execution plan.

The typed fan path now supplies planning and materialization; the boundary implementation binds its output to explicit approval before execution.

## Decision

Cook owns bounded preparation. It reuses the existing planner, validates its output, and asks once for plan approval. It does not restart Mold or repeat settled scope decisions.

Approval binds the exact displayed proposal and explicit response. Unchanged bound approval is reusable. Semantic plan changes require approval again.

## Alternatives

Automatic execution from scope approval removes a pause but changes the authority granted by that approval. Returning all missing planning to Mold preserves ownership at the cost of another phase switch. The user rejected both.

## Consequences

Keep forgiving ingress separate from strict execution authority. Do not treat a status string, taste verdict, or --auto as human plan approval.

The typed handoff, approval binding, and Cook preparation paths are now implemented in the repository. The remaining gap is the external harness wiring that turns a protected response event into the approval reference; this ADR does not claim end-to-end completion without that evidence.



Mold may save a validated draft parent spec or a concrete child mini-spec without a separate write-approval turn.[^draft] A child records its parent slug, covered goal clauses, dependencies, and frozen decisions. The parent tracks each child under `## Curds`.[^child]

Saving does not grant execution authority. The user must select the exact scope and Cook route before Mold binds approval and publishes a runnable pointer. Mold can instead give a child-spec command for another worktree while parent shaping continues. A changed child contract requires a new execution decision.[^execution]

[^draft]: skills/mold/SKILL.md:103-107; skills/mold/references/tiers.md
[^child]: skills/mold/references/early-curds.md:11-25
[^execution]: skills/mold/references/early-curds.md:27-37; skills/mold/references/handshake.md:5-9

## Implementation status

- Contract and shared validation: `src/easy_cheese_schemas/mold_cook.py` and `src/easy_cheese/shared/mold_cook_handoff.py` define and validate the versioned approval and handoff records.
- Producer: `src/easy_cheese/skills/mold/producer.py` finalizes a spec and publishes only a consumer-valid handoff.
- Consumer: `src/easy_cheese/skills/cook/preparation.py` consumes the canonical handoff without treating planning or approval outcomes as execution authority.
- Remaining gap: external harness response-channel wiring and its live end-to-end evidence are outside these modules.

## Evidence

- Durable spec: mold-cook-boundary, resolved through Mold artifact-path specs.
- User selected F1 option A and then approved the four-curd design for saving only.
- Existing planner path: src/easy_cheese/shared/workflow.py:188-246.
- Current input conflict: skills/cook/SKILL.md:32-46.
- Related decision: [Generous ingress, strict persistence](./skill-boundary-normalization-002.md).
