# Age fan-out router

The implemented `/age` router is a contextual planner, not the old
dimension-lens scorer. `src/easy_cheese/shared/fanout/age_route.py::route()`
validates a canonical context record and emits a versioned plan with
assignments, subject dispositions, rationale, workload effort, verification
work, and capability-degradation details. This is a clean break: the current
plan has subjects, not `lenses`, and does not restore the historical
`{n, lenses, effort, overrides_hit, rationale}` API.

## Semantic boundary

The coordinator interprets source evidence. It identifies the review scope,
changed component responsibilities, caller and trust boundaries, applicable
subjects, and semantic risk observations. It supplies those observations with
evidence. The planner does not inspect a repository, classify files, call a
host, or observe dispatch.

The planner validates and canonicalizes that record, then applies the
versioned subject policy. Identical canonical input and policy produce the
same assignment plan and rationale. Independent coordinators can still produce
different semantic input from the same diff; the planning step is deterministic,
but semantic context acquisition is not. A directory name alone is never
semantic evidence.

## Dimensions and subjects

The report has twelve finding dimensions. The established ten remain:
`correctness`, `security`, `encapsulation`, `spec`, `complexity`, `deslop`,
`assertions`, `nih`, `efficiency`, and `telemetry`. `conventions` and
`altitude` are now first-class dimensions with their own rubrics and boundary
rules. A subject may emit several dimensions, and different subjects may
surface one underlying defect; the coordinator reconciles those overlaps.

The planner assigns independent procedures called subjects:

1. `changed-behavior` reads changed hunks and enclosing functions, including
   inputs, state, timing, errors, language pitfalls, wrappers, silent failures,
   and telemetry coverage.
2. `removed-behavior` traces deleted guards, validation, error paths, tests,
   and invariants into the replacement.
3. `caller-impact` follows changed preconditions, return shapes, exceptions,
   ordering, callers, and callees.
4. `security` examines trust boundaries, permissions, secrets, hostile input,
   and dangerous operations.
5. `spec-tests` compares behavior with requirements and checks test coverage.
6. `reuse` looks for existing mechanisms that new code duplicates.
7. `simplification` looks for unnecessary structure, special cases,
   indirection, and generated residue.
8. `efficiency` inspects costly paths, avoidable work, copying, allocation,
   I/O, and scaling.
9. `conventions` cites the applicable written rule, source, violating code,
   and correction.
10. `altitude` names the local symptom, responsible component, better
    placement, and concrete cost.

## Context input

The request record distinguishes coordinator assertions from host-derived
facts. It contains:

- `scope`: `diff` or `overall`. An overall review is system-wide and does not
  prune subjects from a diff.
- `effort`: explicit `quick`, `normal`, or `deep`; absent effort defaults to
  `normal`, never to an effort inferred from size.
- `snapshot`, `changed_paths`, and `surface_score`: the actual evidence
  identity, every changed path, and the finite non-negative workload score.
  Paths with zero workload weight remain in relevance analysis.
- `components`: changed component rows with `id`, role, and paths.
- `subjects`: one row per subject with `applicability`, targets, and evidence.
  Applicability is `yes`, `no`, or `unknown`; unknown is not exclusion.
- `risks`: evidence-backed flags with `yes`, `no`, or `unknown` state.
- `is_subagent`, `can_fan_out`, and `concurrency_limit`: the available
  execution capabilities.

The review-instructions command collects repository and explicitly named
external instruction sources for this record. The collection reports candidate
content and provenance; it does not grant authority or resolve precedence
across Claude, Codex, OMP, or other hosts. A `tests/` path does not exclude
security, and an assertion-only edit does not by itself require a security
specialist.

## Workload and subject policy

`review_surface` remains a workload measurement, not a security classifier.
The pure scorer lives at
`src/easy_cheese/shared/fanout/review_surface.py` and computes
`sum(weight * lines) + FILE_COST * sum(weight)`, with `FILE_COST = 8`.
Its current weights remain the safe default: zero for lockfiles, bytecode,
fixtures, snapshots, and vendored trees; `0.25` for README/changelog,
documentation, content, and `.hallouminate`; and `1.0` for everything else.
Unknown extensions are reviewed. Use
`python3 skills/age/scripts/age.pyz review-surface --repo . <base>...HEAD`
for a committed range, or the working diff when that is the target.

The score supplies ordinary workload allowances. It does not choose effort,
remove paths from context, or replace semantic risk evidence:

| Effort | Below 60 | 60 through 250 | Above 250 |
| --- | --- | --- | --- |
| `quick` | 1 | 1 | 1 |
| `normal` | 1 | up to 2 | up to 5 |
| `deep` | up to 3 | up to 5 | full relevant subject separation |

These are allowances, not quotas. Quick mode combines ordinary work with the
protected `conventions` and `altitude` coverage instead of reserving those
subjects independently. Normal and deep reserve separate conventions and
altitude reviewers. A mandatory risk specialist is a protected addition and
may exceed the ordinary allowance; the plan records that reason and gives the
risk assignment high worker effort.

Risk flags map to procedures. Authentication, secrets, crypto, and tenant
isolation require `security`; payments, ledgers, irreversible effects,
production-destructive operations, concurrency, idempotency, ordering, and
retries require `changed-behavior`; schema migration, protocol, and public API
changes require `caller-impact`; weak integration coverage requires
`spec-tests`; removed protection requires `removed-behavior`; and hot paths
require `efficiency`. Unknown risk remains visible as uncertainty and keeps
the affected general assignment cautious.

Optional specialists are extracted in this priority order:
`security`, `caller-impact`, `removed-behavior`, `spec-tests`, `efficiency`,
`reuse`, `simplification`. Outside full separation,
`changed-behavior` stays in the general assignment rather than becoming an
optional specialist. Deep reviews of a large surface and every `overall`
review use full relevant-subject separation. Overall scope assigns every
subject, while diff scope uses evidence-backed applicability.

## Dispatch, verification, and degradation

The plan records desired assignments before host restrictions and actual
assignments after them. If the invocation is a sub-agent or the host cannot
fan out, independent assignments collapse into one combined assignment with a
`degraded_reason`; the plan retains `desired_assignments` and
`desired_n`. It must never claim that protected subjects received independent
review when the host could not provide it.

The plan records dispatch batches and candidate verification batches. The
coordinator reconciles findings by underlying defect, not only by file and
line. Quick and normal reviews have no gap sweep. Deep review runs a fresh
gap sweep after verification and verifies any new candidates.
Persist the complete route output at `.cheese/age/<slug>-plan.json`. The
resolution record carries the plan path, policy version, input digest, planned
assignments, and observed dispatch. Keep observed dispatch separate from the
planner's desired assignments.

`review-plan-check` compares reported assignment IDs and one-message/batch
shape with the plan. It is a consistency check, not an authentication
mechanism: `verified` and `authenticated` remain false even for a
host-reported observation. A null observation is `unobserved`; a reported
observation remains unverified. Mismatches require reconciliation or an
explicitly incomplete review, never a success claim.

## Runtime and CLI

`age_route.py` is pure. The JSON-in/JSON-out wrapper is the sibling module
`src/easy_cheese/shared/fanout/age_route_cli.py`, and `commands.py` registers
it as `age-route`. Invoke the packaged command:

```text
python3 skills/age/scripts/age.pyz age-route [request.json]
```

The wrapper reads an optional JSON path or stdin. The source path is a source
location, not a standalone script contract; its package-relative import
expects the bundled package environment. The build stages the package and its
shared dependencies together. Do not document the obsolete `src/fanout/*`
paths or the former flat-helper staging model.

The `git diff --numstat -z` revision-ordering gotcha remains relevant:
`git diff --numstat -z --no-renames -- HEAD~1 HEAD` treats the revisions as
pathspecs and can return zero rows with exit 0. Use
`git diff --numstat -z --no-renames <revs> --`, matching Git's
`git diff [<commit>…] [--] [<path>…]` grammar. Reject leading-dash diff
arguments before constructing the command.

## Related decisions

- [ADR-001](../adr/deterministic-fanout-sizing-001.md) — historical
  risk-promotion policy, superseded for current Age subject planning.
- [ADR-002](../adr/deterministic-fanout-sizing-002.md) — historical weight
  decision; its workload scoring remains the basis for current allowances.
- [ADR-003](../adr/deterministic-fanout-sizing-003.md) — historical
  no-classifier boundary, qualified for the current semantic input boundary.
- [ADR-004](../adr/deterministic-fanout-sizing-004.md) — historical curd
  workload-estimate decision, not the current Age subject policy.
- [../fanout-engine-entities.md](../fanout-engine-entities.md) — related
  fan-out entities and validation boundaries.

_Source: `src/easy_cheese/shared/fanout/age_route.py`,
`src/easy_cheese/shared/fanout/review_surface.py`,
`skills/age/references/fan-out.md`, and approved spec
`age-contextual-review-parity`; updated for the contextual policy._