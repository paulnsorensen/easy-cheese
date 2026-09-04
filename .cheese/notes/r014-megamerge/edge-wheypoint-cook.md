# Wheypoint to Cook Edge Review

## State

broken

## Evidence

- No runtime import or function call joins the two skill packages.
- Wheypoint forbids calls to another archive at `skills/wheypoint/SKILL.md:40-44`.
- Cook exports the `baseline` command at `src/easy_cheese/skills/cook/commands.py:28-32,189-200`.
- The command uses `{suite, test_id, signature}` records at `src/easy_cheese/shared/fanout/baseline.py:38-48`.
- Cook defines the optional `baseline` mapping at `skills/cook/references/quality-gates.md:5-46`.
- Cook writes this mapping into its handoff or fan manifest at `skills/cook/references/quality-gates.md:58-67`.
- Cook also requires the field in its handoff schema at `skills/cook/SKILL.md:131-146,179-184`.
- Wheypoint promises exact baseline preservation at `skills/wheypoint/SKILL.md:73-130`.
- `CheckpointIntent` has no baseline field at `src/easy_cheese/skills/wheypoint/checkpoint.py:85-108`.
- `WheypointRecord` omits baseline at `src/easy_cheese_schemas/wheypoint.py:542-569`.
- `WheypointDelta` omits baseline at `src/easy_cheese_schemas/wheypoint.py:625-669`.
- `WheypointProjection` omits baseline at `src/easy_cheese_schemas/wheypoint.py:710-726`.
- The projection renderer emits no baseline at `src/easy_cheese/skills/wheypoint/projection.py:68-95`.
- A source probe supplied a valid Cook baseline mapping to `CheckpointIntent`.
- The loader accepted the payload and removed `baseline`.
- The legacy model stores baseline as a string at `src/easy_cheese/skills/wheypoint/legacy.py:64-80`.
- The legacy parser requires a value on the same line at `src/easy_cheese/skills/wheypoint/legacy.py:156-200`.
- A source probe gave the legacy parser Cook's documented mapping.
- The parser returned `LegacyDecodeError: 'baseline:' line requires a value`.
- The `next` name agrees through `NextMove.COOK` at `src/easy_cheese_schemas/wheypoint.py:86-101`.
- The `artifact` field agrees with Cook's optional specification input at `src/easy_cheese_schemas/wheypoint.py:282-290` and `skills/cook/SKILL.md:20-36`.
- Parallel handoffs emit valid `/cook <spec-path>` commands at `skills/wheypoint/references/parallel-handoffs.md:55-78`.
- The resume flow covers stopped Cook fan runs at `skills/cheese/references/continue-resume.md:1-5`.
- That flow dispatches `/cook <slug>` and preserves `artifact` only after a gate at `skills/cheese/references/continue-resume.md:109-120`.
- Cook requires `/cook --resume <slug>` for typed fan state at `skills/cook/references/fan-pathway.md:330-354`.
- Cook offers `/wheypoint` as a stop option at `skills/cook/SKILL.md:186-205`.
- Wheypoint excludes Cook phase handoffs at `skills/wheypoint/SKILL.md:3-10`.
- Cook tests cover classification and manifest shape at `tests/fanout/python/test_baseline.py:39-117` and `tests/python/test_baseline_policy_coherence.py:105-192`.
- Consumer tests check only prose and the `baseline: none` sentinel at `tests/python/test_baseline_consumer_docs.py:87-105`.
- The Wheypoint legacy test uses `baseline: none` and does not assert it at `tests/wheypoint/python/test_resolve.py:651-689`.
- Focused seam tests passed with 69 tests.
- No test carries a non-empty Cook baseline through a Wheypoint checkpoint.

## Findings

### Blocker

- Wheypoint cannot carry a non-empty Cook baseline through either supported path.
  The normal path silently removes the mapping.
  The legacy path rejects the mapping.
  A resumed Cook run can treat settled failures as new failures.
  **Fix:** Define one typed baseline model.
  Add it to the Wheypoint intent, delta, record, and projection.
  Preserve the model when a delta omits it.
  Render and parse the complete mapping.
  Reject unsupported fields instead of removing them.

### High

- The tests do not exercise the producer-to-consumer seam.
  Current tests protect the classifier, prose, and `none` sentinel separately.
  **Fix:** Create a non-empty Cook baseline and pass it through `checkpoint`, `show`, projection parsing, and Cook resume.
  Assert every field and every failure record.
  Add a legacy mapping test or remove legacy mapping support.

- The two skill descriptions disagree about the checkpoint route.
  Cook offers Wheypoint after its handoff.
  Wheypoint says not to use it for Cook phase handoffs.
  **Fix:** Keep the explicit Cook stop option.
  State that Wheypoint does not replace routine phase handoffs.
  Permit it when the user selects **Checkpoint & stop**.

- The resume command does not match Cook's typed fan contract.
  The router sends a bare Cook slug after a stopped fan run.
  Cook requires `--resume` and stops a bare run when a handoff exists.
  The ordinary Cook route can also ignore Wheypoint's specification pointer.
  **Fix:** Route Cook by the artifact type.
  Use `/cook --resume <slug>` for a typed fan handoff.
  Use `/cook <artifact>` for a specification pointer.
  Add tests for both routes.

### Medium

none

### Low

none

## STE100 status

compliant

The reviewed prose in both `SKILL.md` files complies with the required sentence rules.
The cross-skill contradiction is a contract defect, not an STE100 defect.

## Follow-ups

- Add typed baseline preservation to the canonical Wheypoint path.
- Align the legacy baseline codec with Cook's mapping or remove that support.
- Add a non-empty baseline seam test.
- Align the Cook checkpoint option with the Wheypoint description.
- Align the resume router with Cook's specification and typed fan commands.
