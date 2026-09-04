# Cheese to Affinage edge review

## State

broken

The documented `PR#<n>` value does not reach the Affinage integer command.

## Evidence

- Cheese resolves legacy notes through Wheypoint at `skills/cheese/references/continue-resume.md:14-31`.
  It requires `status: ok` and an informed trust gate.
- Cheese handles `next: affinage` at `skills/cheese/references/continue-resume.md:98-111`.
  It reads the pull request reference from `artifact:`.
  It accepts `PR#<n>` or a URL.
  It emits `/affinage <pr>`, or bare `/affinage` when the reference is absent.
- Affinage accepts a number or full URL at `skills/affinage/SKILL.md:30-38`.
  Bare `/affinage` uses the current branch.
- Affinage calls `pr-status` at `skills/affinage/SKILL.md:66-75`.
  The command requires an integer at `src/easy_cheese/skills/affinage/pr_status.py:356-364`.
  It returns exit 3 for expired logs.
  Other failures stop Affinage as unavailable.
- Affinage writes `.cheese/affinage/pr-<n>.md` at `skills/affinage/SKILL.md:163-183`.
  The report emits `status`, `next`, `artifact`, and one orientation line.
  `next` is `cure` or `done`.
- Cheese defines canonical fields at `skills/cheese/references/handback-contract.md:15-32`.
  It assigns Affinage to this boundary at `skills/cheese/references/handback-contract.md:67-91`.
- The runtime registry omits Affinage at `src/easy_cheese_schemas/_compiled_phase_registry.py:5-103`.
  The registered sources are Age, Cook, Cure, Mold, and Press.
- The Cheese test checks the generic legacy trust gate at `tests/python/test_wheypoint_skill_contract.py:77-95`.
  It does not check an Affinage dispatch.
- The Affinage command test passes only `"42"` at `tests/python/test_pr_status.py:260-282`.
  It does not check `PR#<n>` or a pull request URL.
- Probe: `python3 skills/affinage/scripts/affinage.pyz pr-status 'PR#42'` exits with code 2.
  Argparse reports `invalid int value: 'PR#42'`.

## Findings by severity

### Blocker

none

### High

- **[correctness] Cheese emits a pull request form that Affinage does not accept.**
  Cheese accepts `PR#<n>` at `skills/cheese/references/continue-resume.md:104-108`.
  Affinage declares only a number or URL at `skills/affinage/SKILL.md:30-38`.
  Its command requires an integer at `src/easy_cheese/skills/affinage/pr_status.py:356-364`.
  The probe confirms that `PR#42` fails before GitHub access.
  **Fix:** Normalize every accepted pull request reference before Affinage calls `pr-status`.
  Add one shared parser for numbers, `PR#<n>`, and URLs.

- **[spec] Affinage cannot use the canonical durable handback path.**
  The shared contract assigns Affinage to the artifact writer at `skills/cheese/references/handback-contract.md:67-88`.
  Affinage writes `next: cure | done` at `skills/affinage/SKILL.md:163-183`.
  The phase registry has no Affinage source at `src/easy_cheese_schemas/_compiled_phase_registry.py:5-103`.
  **Fix:** Add an Affinage phase contract and use the canonical artifact writer.
  If manual reports remain, narrow the shared writer claim.

### Medium

- **[spec] The `artifact` field has two meanings on this edge.**
  The shared contract defines a prior report at `skills/cheese/references/handback-contract.md:30-32`.
  Cheese reads a pull request reference at `skills/cheese/references/continue-resume.md:104-108`.
  Affinage emits a prior report path at `skills/affinage/SKILL.md:171-175`.
  **Fix:** Add a typed `pr_ref` field for the Affinage dispatch.
  Keep `artifact` for the prior report.

- **[spec] Explicit resume auto mode lacks the required Affinage stake.**
  Cheese lets a user add bare `--auto` at `skills/cheese/SKILL.md:120`.
  Affinage requires `--auto --stake <floor>` at `skills/affinage/SKILL.md:30-45`.
  Cheese defines no stake default for this resume path.
  **Fix:** Require `--stake` during an Affinage resume.
  Alternatively, define one Affinage default.

- **[assertions] Tests do not exercise the Cheese to Affinage seam.**
  The Cheese test covers only trust-gate prose at `tests/python/test_wheypoint_skill_contract.py:77-95`.
  The Affinage test covers only a decimal number at `tests/python/test_pr_status.py:260-282`.
  **Fix:** Add a seam test for an approved legacy note with `next: affinage`.
  Test a number, `PR#<n>`, a URL, a missing reference, and bare `--auto`.

### Low

none

## Contract changes

No integrated change updates this edge's pull request grammar.
The contracts disagree at HEAD.

## STE100 status

not compliant

- `skills/cheese/SKILL.md:136` has a procedural sentence longer than 20 words.
- `skills/cheese/references/continue-resume.md:255` uses the passive voice.
- `skills/affinage/SKILL.md:44,51,84,194,202` combines multiple instructions in one sentence.
- `skills/affinage/SKILL.md:76,111,217` uses three terms for one fresh review.
- This note complies with the stated STE100 rules.

## Follow-ups

- Normalize the pull request reference before Affinage calls `pr-status`.
- Register the Affinage handback transition or narrow the shared writer claim.
- Replace the overloaded `artifact` value with a typed pull request field.
- Define the Affinage stake for resumed auto mode.
- Add a seam test for each accepted pull request form.
- Apply the STE100 fixes listed above.
