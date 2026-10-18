# Applying behavioral acceptance research to easy-cheese

Candidate changes that apply
[behavioral-acceptance-ears-loops](./behavioral-acceptance-ears-loops.md) to the
cheese pipeline. The core change: every behavior curd carries one acceptance
check at a real entrypoint, and that check proves it can fail before anyone
trusts it passing. None of these is adopted. Each needs a `/mold` decision;
guard and contract changes need explicit approval.

## Current state at `336258e0`

The pipeline already has several pieces of the research:

- Mold writes acceptance criteria in EARS `WHEN ... SHALL` form
  (`skills/mold/references/curdle.md:101-108`).
- Test Contracts carry an outermost seam and an expected-failure witness
  (`curdle.md:114-125`), but the section is optional and no gate requires it
  (`skills/mold/SKILL.md:79-81`).
- Cook does not require a failing test first and loads no gate receipt
  (`skills/cook/SKILL.md:26-27`). The RED-reason check runs only "when that is
  cheap to do" (`skills/cook/references/tdd-loop.md:11`).
- Cook's taste-test has Production path and Wired callers lenses
  (`tdd-loop.md:97-98`), but the cost gate skips the fresh reviewer for a
  one-file diff under about 40 lines with no risk flag (`tdd-loop.md:53-60`).
- Cook's repair loop already stops: two taste-test rounds, one final
  correction, then `blocked` (`tdd-loop.md:141-151`).
- Press checks assertion sensitivity (`skills/press/references/gap-analysis.md:38`)
  and never owns first coverage (`skills/press/SKILL.md:11`). It names no
  no-op, mutation, or known-working control.
- Age's `assertions` dimension flags no-crash-as-success and mocked SUTs by
  reading tests (`skills/age/references/dimensions.md:322-333`). It does not
  run a test with the effect removed.

## Suggestions, ordered by leverage

### 1. Mold: one acceptance record per behavior criterion

Extend the Test Contracts row so it answers the research's six questions.
Add three columns: **Real entrypoint** (the installed command, archive, or
public API a user calls), **Oracle** (the independent source of truth, not the
program's own output), and **False-success case** (the plausible broken result
that must fail). Make the section required when a criterion crosses a live
boundary: packaging, `.pyz` dispatch, git or GitHub, the filesystem, or another
skill's handoff. Keep it optional for pure internal logic.

Also teach `curdle.md` the other EARS forms. Today it shows only `WHEN`.
`IF ... THEN` for unwanted behavior fits failure paths. `WHILE` needs checks
across transitions, not one snapshot.

Cost: schema change in `src/easy_cheese_schemas/contracts.py` (the
`Section("Test Contracts", optional=True, ...)` entry) and the generated
document rules. Mold has about 260 tokens of SKILL.md headroom, so the text
belongs in `curdle.md`.

### 2. Cook: owns first acceptance coverage with red-then-green evidence

For each behavior criterion, Cook runs the acceptance check at the real
entrypoint on the base revision first, records why it fails, then runs it
green on the final tree. Replace "when that is cheap to do" with a required
line in the Cook handoff, for example
`acceptance: AC-1 <command> red@base:<reason> green@head`. This brings back the
evidence of the retired RED gate without the `GateReceipt` machinery.

Add "the acceptance criterion names a live boundary" to the risk-flag list
(`tdd-loop.md:64-71`). Then a small diff that touches a live boundary still
gets the fresh Production path review.

Cost: Cook has about 100 tokens of SKILL.md headroom, and prose tests pin
its body sentences (`tests/python/test_cook_prose_contract.py`). Put the
rule in `tdd-loop.md`.

### 3. Press: attacks false success, not just edge cases

Name two controls in `gap-analysis.md` beside assertion sensitivity:

- **No-op control.** Revert the production change in a disposable worktree
  and run Cook's acceptance check. It must fail for the expected reason. If
  it passes, the finding is `vacuous-acceptance`.
- **Reference control.** The same check passes on the final tree from a clean
  environment. An unexpected error or a skipped live dependency is not a pass.

This keeps Press's boundary: Cook writes the check, Press challenges it.
Press has about 1,650 tokens of headroom.

### 4. Age: catch success-shaped assertions

Add triggers to the `assertions` dimension: a test that asserts only an exit
status, a success message, a mock call, or a golden file that the code under
test wrote. Add the test-admission question to the test-bloat checks
(`dimensions.md:295`): which distinct observable failure does this test reject?
Age stays read-only; Press runs the controls.

### 5. Keep repair loops and optimization loops apart

Cook's two-round cap is an acceptance repair loop, so keep its stop rule. Any
optimization or hill-climb skill added later must start from an accepted
baseline and must not drive acceptance repair, because it keeps going after a
target. In fan runs, Milknado's verify-until-green
(`skills/cook/references/fan-pathway.md:234-235`) needs a frozen evaluator:
record the acceptance check's digest at dispatch and reject a candidate that
changes it. This extends "must not weaken an existing test"
(`tdd-loop.md:41`).

### 6. Make doctrine rules executable

`AGENTS.md` says `shared/` code must not import `cli/`.
`tests/python/test_doctrine_topology.py` checks the source tree layout. A
search of `tests/` found no test for that import direction. An AST test that
fails on `easy_cheese.shared` → `easy_cheese.cli` imports makes the rule a
hard gate, as ArchUnit does in Java ([archunit](../sources/archunit-use-cases.md)).

### 7. Skill experiments: separate three claims

For skill optimization work
([skill-optimization-landscape](../skill-optimization-landscape.md)), report
three verdicts per run: the run completed, the artifact reproduces the
candidate, and the candidate improved reserved tasks. Give each task a
reference solution and a negative control. Keep the reserve untouched during
iteration.

## Wiki drift found during this ingest

Before adopting suggestion 2, reconcile pages that still describe `/cut` and
`GateReceipt` as live: `architecture.md:78`, `domain-model.md:175-205`,
`red-gate-environment-gotchas.md`, and the `adr/outer-tdd-gates-00*` set.
`adr/outer-tdd-gates-004.md:13` says Mold locks a Test Contract for every
criterion; `skills/mold/SKILL.md:79` says the section is optional.

## Validate before adopting

Pick one real failure where unit tests passed and live behavior failed. Run
the current pipeline and the candidate method on the same task, base, model,
and budget. Judge both with a check the implementing agent cannot edit.
Report first-attempt success, eventual success, repair time, and review
defects separately.

_Source: [behavioral-acceptance-ears-loops](./behavioral-acceptance-ears-loops.md) applied to easy-cheese at `336258e0` · Updated: 2026-10-18 · Supersedes: none_
