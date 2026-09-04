# Cook to Plate Edge Review

## State

broken

Cook can request the Plate topology mode. The publication contract cannot carry all required state safely.

## Evidence

### Calls and commands

- Cook requests `/plate` in `topology-preflight` mode before any parallel worker commit at `skills/cook/references/fan-pathway.md:152-178`.
- Plate defines the same mode at `skills/plate/SKILL.md:27-40`.
- Plate stops this mode before commits, pushes, or pull request operations at `skills/plate/references/topology.md:57-68`.
- Plate validates the mode with `topology` set to `single` or `stacked` at `src/easy_cheese/skills/plate/publication.py:135-145`.
- The record also requires `provider: n/a`, an `n/a` gate, and empty `commits` and `prs` lists.
- Plate requires eight top-level fields and gives them no defaults at `src/easy_cheese/skills/plate/publication.py:14-19,59-79`.
- Plate reports all contract errors and returns exit status 1 at `src/easy_cheese/skills/plate/publication.py:171-193`.
- Cook imports shared and Cook modules only at `src/easy_cheese/skills/cook/commands.py:7-179`.
- Plate imports shared and Plate modules only at `src/easy_cheese/skills/plate/commands.py:8-22`.
- No Python import crosses this edge.
- Plate exposes only `stack-tools` and `validate-publication` at `src/easy_cheese/skills/plate/commands.py:11-30`.
- Cook therefore invokes the Plate skill. Cook does not invoke a Plate Python command.
- The repair-worktree rules agree at `skills/cook/references/quality-gates.md:73-90` and `skills/plate/references/topology.md:70-80`.

### Emitted files and fields

- Cook names `.cheese/cook/<slug>.md` as its handoff file at `skills/cook/SKILL.md:131-165`.
- That handoff supports `status`, `next`, `artifact`, `taste_test`, `durable_flags`, and `baseline`.
- The canonical model supports the same fields at `src/easy_cheese/shared/handoff.py:38-87,105-183`.
- The canonical writer exposes the same fields at `src/easy_cheese/shared/write_handoff_artifact.py:125-162,200-280`.
- Cook requires `plate_layout: single | stacked` in typed handoff evidence at `skills/cook/references/fan-pathway.md:160-172`.
- Plate requires the same name and values at `skills/plate/references/topology.md:57-60`.
- Neither handoff implementation defines `plate_layout`.
- A direct probe parsed `plate_layout: single` as the orientation. The result had no `plate_layout` field.
- Plate names only “workflow state” for the value at `skills/plate/references/topology.md:57-68`.
- Plate does not name a file, schema, or run identifier for this state.

### Pull request plans

- Cook exposes `validate-pr-plan` and `pr-plan-to-branches` at `src/easy_cheese/skills/cook/commands.py:77-102,210-225`.
- The canonical Cook plan requires `shape` and `groups` at `src/easy_cheese_schemas/pr_plan.py:138-145`.
- Plate says a later `pr_plan` must contain `plate_layout` at `skills/plate/references/topology.md:52-60`.
- Plate allows only `plate_layout` inside its `pr_plan` object at `src/easy_cheese/skills/plate/publication.py:127-133`.
- A direct probe passed a complete Cook plan to Plate.
- Plate rejected `pr_plan.groups` and `pr_plan.shape` as disallowed fields.

### Publication intent

- Cook defines `--open-pr` as a separate publication input at `skills/cook/SKILL.md:38-43`.
- Cook auto mode always adds `--open-pr` at `skills/cook/references/auto-mode.md:23-28`.
- Cure uses this flag to request Plate publication at `skills/cure/SKILL.md:196-204,236-245`.
- Plate selects new-pull-request mode when publication is requested at `skills/plate/SKILL.md:31-40`.
- Plate does not define an `--open-pr` input.
- Cook passes `--hard` through Plate at `skills/cook/SKILL.md:40-42`.
- Plate accepts `--hard` at `skills/plate/SKILL.md:45-46`.
- This `--hard` contract agrees.

### Tests

- Three focused tests passed.
- `tests/python/test_plate_contract.py:307-334` checks Cook prose and retired Ultracook schemas.
- That test does not load the Plate topology policy or a current typed Cook handoff.
- `tests/python/test_plate_runtime.py:67-94` checks Plate plan drift and topology-preflight evidence.
- Those tests do not pass a complete Cook plan or Cook handoff into Plate.
- `tests/python/test_cook_contract_accept.py:1-6` covers the Mold-to-Cook pointer seam only.
- `tests/python/test_hard_cheese.py:147-166` checks flag words and the Cure-to-Plate hard gate.
- No test exercises this complete edge from Cook input through Plate publication.

## Findings by severity

### Blocker

- **Cook auto mode grants publication permission without the `--open-pr` input.** This can create a remote pull request without explicit permission. **Fix:** Preserve `--open-pr` only when the Cook invocation contains it. Add a no-publication test for `/cook --auto`.

### High

- **The topology resolution has no current typed storage contract.** Cook names the field, but its handoff parser cannot read it. **Fix:** Add one route-bound topology record with a run identifier. Make Cook write it and Plate read it.
- **Plate rejects the complete Cook `pr_plan`.** Cook uses `shape` and `groups`, while Plate permits only `plate_layout`. **Fix:** Add `plate_layout` to the canonical `PrPlan`. Make both validators consume the complete model.
- **Cook assigns terminal Plate dispatch to two owners.** `skills/cook/SKILL.md:216-217` assigns it to Cure. `skills/cook/references/fan-pathway.md:320-322` assigns it to Cook. **Fix:** Scope Cure ownership to the linear chain. State that the Cook fan orchestrator owns its terminal Plate dispatch.

### Medium

- **The tests inspect each side separately.** They do not protect field storage, plan compatibility, permission retention, or run identity. **Fix:** Add one cross-edge test for each publication path.

### Low

none

## STE100 status

- `skills/cook/SKILL.md:63,241-250` does not use one instruction per sentence.
- `skills/cook/references/auto-mode.md:86` does not use the active voice.
- `skills/cook/references/fan-pathway.md:248,387` does not use the active voice.
- `skills/cook/references/quality-gates.md:29` does not use the active voice.
- `skills/plate/SKILL.md:23,35,53,63,92,101` uses passive voice or compound instructions.
- `skills/plate/references/topology.md:18,33,40,54,61` uses passive voice or compound instructions.
- This note is compliant.

## Follow-ups

- Preserve explicit publication permission through Cook, Press, Age, and Cure.
- Define one typed topology record for Cook and Plate.
- Make Cook and Plate consume one canonical pull request plan.
- Add cross-edge contract tests for topology, publication intent, and terminal ownership.
