# ADR: Handoff validation binds to an explicit artifact root and affirmative consent

Status: implemented in the PR #699 review cure (2026-09-19).

The shared Mold-to-Cook validators take no ambient defaults. Every artifact resolves under a caller-named root, consent is an explicit affirmative token, and the seam performs no network I/O.

## Context

The first boundary implementation let `validate_mold_cook_handoff` and `validate_mold_cook_approval` default `artifact_root` to `None`, which resolved `file://` references without containment and retained bytes into the process working directory. The response check inferred consent from a denylist of refusal phrases, and any `https://` reference in a handoff triggered an outbound fetch during validation. Review of PR #699 graded these as blocker and high security findings.

## Decision

`artifact_root` is a required parameter on both exported validators; there is no fallback to `Path.cwd()`. The seam rejects every URI scheme other than `file` and `repo` before resolution. A user response counts as approval only when it matches a closed allowlist of affirmative tokens after casefolding and punctuation stripping; unrecognized text is rejected as unresolved. A local-dialogue artifact authorizes execution only when `execution_authorized` is literally `True` and `clear_holds` is a non-empty list; Mold and Cook share one helper, `dialogue_authorizes_execution`, for that rule. `validate_mold_cook_approval` rebuilds the canonical proposal envelope from the approval's own fields and compares it, so a RUNNER approval cannot widen `setup_authorization` unnoticed.

## Alternatives

Relying on the structured `decision` field alone and deleting the free-text screen was proposed. The allowlist keeps the free-text screen as defense in depth while removing the denylist's false negatives; the decision is recorded as vetoable.

## Consequences

External callers of the two validators must pass a root. Approval prose must be an explicit affirmative; a reply such as "no blockers remain, approved" is no longer accepted by prefix and must be restated. PLAN and PARTIAL_PLAN envelopes still cannot be rebuilt from the approval alone; the handoff validator binds those through planner evidence, and a caller-supplied expected envelope on the exported validator remains follow-up work.

## Implementation status

- Validators and helpers: `src/easy_cheese/shared/mold_cook_handoff.py` (`_root_and_directory`, `_resolve_bytes`, `_validate_response`, `dialogue_authorizes_execution`, `validate_mold_cook_approval`).
- Cook twin: `src/easy_cheese/skills/cook/preparation.py` `_validate_hold_clearance` delegates to the shared helper.
- Tests: `tests/python/test_mold_cook_handoff.py`, `tests/python/test_mold_cook_publication.py`.

## Evidence

- Review report: `.cheese/affinage/pr-699.md` (findings 2, 3, 4, 5, 10).
- Related decisions: [Plan approval remains explicit](./mold-cook-boundary-001.md), [Partial plans need explicit subset approval](./mold-cook-boundary-003.md).
