# Cook to Cheese edge review

## State

broken

Cook writes a phase report and then tells the user to resume by slug.
Cheese cannot resolve that report by slug or path.

## Evidence

- Cook writes `.cheese/cook/<slug>.md` at `skills/cook/SKILL.md:131-165`.
- Cook directs `/cheese --continue <slug>` at `skills/cook/references/fan-pathway.md:23-32`.
- Cheese requires `/wheypoint resolve --ref` at `skills/cheese/SKILL.md:107-117`.
- Cheese defines resume behavior at `skills/cheese/references/continue-resume.md:14-181`.
- The shared writer validates Cook transitions at `src/easy_cheese/shared/write_handoff_artifact.py:125-197`.
- The shared parser reads the preamble at `src/easy_cheese/shared/handoff.py:105-184`.
- The phase registry defines Cook routes at `src/easy_cheese_schemas/_compiled_phase_registry.py:23-50`.

## Blocker

- **[correctness:blocker] The resume command cannot resolve a Cook report.**
  Cook finds a phase report and directs `/cheese --continue <slug>` at `skills/cook/references/fan-pathway.md:23-32`.
  Cheese sends that slug to Wheypoint at `skills/cheese/SKILL.md:109-117`.
  The resolver falls back to legacy lookup at `src/easy_cheese/skills/wheypoint/resolve.py:120-143`.
  Legacy lookup searches only `.cheese/notes/<slug>.md` at `src/easy_cheese/skills/wheypoint/legacy.py:350-366`.
  Exact Cook paths also fail the projection check at `src/easy_cheese/skills/wheypoint/resolve.py:179-203`.
  A probe returned `not-found` while `.cheese/cook/demo.md` existed.
  **Fix:** Accept exact phase report paths with strict preamble and artifact validation.
  Require a user selection when several phase reports exist.
  Do not select a report by time.

## High

- **[correctness:high] Cook documents an invalid handoff reader command.**
  Cook uses a positional path at `skills/cook/references/fan-pathway.md:48-50`.
  The command requires `--phase` and `--slug` at `src/easy_cheese/shared/read_handoff_slug.py:43-46`.
  The documented command returned exit code 2 and reported both missing flags.
  **Fix:** Use `read-handoff-slug --phase <phase> --slug <slug>` in Cook prose.
  Add a bundle test for that exact command.

- **[spec:high] Cook and Cheese assign different meanings to `artifact:`.**
  Cook calls it a richer report at `skills/cook/SKILL.md:140-147`.
  Cheese defines it as the consumed prior report at `skills/cheese/references/handback-contract.md:17-32`.
  Cheese keeps the Mold specification pointer authoritative at `skills/cheese/references/continue-resume.md:115-120`.
  The round-trip test uses the Cook report as its own pointer at `tests/shared/python/test_handoff_roundtrip_integration.py:136-156`.
  **Fix:** Define `artifact:` as the consumed upstream artifact in Cook prose.
  Use a Mold pointer in the Cook round-trip test.
  Prove that Cheese forwards the same pointer.

- **[correctness:high] The documented `baseline:` block cannot cross the seam.**
  Cook defines nested YAML at `skills/cook/references/quality-gates.md:32-46`.
  The writer accepts only one physical line at `src/easy_cheese/shared/handoff.py:166-182`.
  Cheese expects settled baseline state at `skills/cheese/references/continue-resume.md:178-181`.
  A probe rejected the documented shape with `baseline must fit on one physical line`.
  **Fix:** Define `baseline:` as a one-line artifact reference.
  Store the YAML record in that artifact.
  Validate its digest before resume.

## Medium

- **[spec:medium] The concrete Cook gate does not match the standard Cook menu.**
  Cook requires forward, Plate, checkpoint, and stop options at `skills/cook/SKILL.md:186-203`.
  The Cheese example has forward, decomposition, and stop options at `skills/cheese/references/handoff-gate.md:27-54`.
  The same reference requires four standard options at `skills/cheese/references/handoff-gate.md:195-204`.
  The prose test protects only part of the example at `tests/python/test_docs_emphasis_guard.py:194-207`.
  **Fix:** Replace the example with the exact Cook menu.
  Test every option ID, action, context field, and propagated flag.

- **[assertions:medium] Tests do not exercise Cook output through Cheese resume.**
  The shared test stops after writer and reader checks at `tests/shared/python/test_handoff_roundtrip_integration.py:216-251`.
  The Cheese test checks only prose fields at `tests/python/test_docs_emphasis_guard.py:194-207`.
  Fifty-four focused tests passed despite the failed resume probe.
  **Fix:** Write a Cook report.
  Resolve it through Wheypoint.
  Assert the Cheese dispatch.
  Cover malformed reports, duplicate reports, stop statuses, and upstream artifact pointers.

## Low

none

## Verification

- The focused handoff and prose tests passed with 54 tests.
- The Cook resume probe returned `not-found` for an existing Cook report.
- The nested baseline probe returned `CliError`.
- The documented reader command returned exit code 2.

## STE100 status

not compliant

- `skills/cook/SKILL.md:63` combines two instructions.
- `skills/cook/SKILL.md:241-242` uses passive voice.
- `skills/cook/SKILL.md:250` combines two instructions.
- `skills/cheese/SKILL.md:120-122` contains long compound sentences.
- `skills/cheese/SKILL.md:126,132,136` contains long procedural sentences.
- `skills/cheese/SKILL.md:143` contains a long table instruction.
- This note complies with the Simplified Technical English rules.
