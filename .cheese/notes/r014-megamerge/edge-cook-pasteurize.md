# Cook to Pasteurize edge review

## State

broken

Cook dispatches Pasteurize, but the documented return path sends Cook the wrong artifact type.

## Evidence

- Cook defines `FailureRecord` as `suite`, `test_id`, and `signature` (`skills/cook/references/quality-gates.md:17`).
- Runtime defines all three fields as strings (`src/easy_cheese/shared/fanout/baseline.py:38-41`).
- Runtime rejects a list, object, or record that lacks a required shape (`src/easy_cheese/shared/fanout/baseline.py:91-104`).
- Cook puts those fields in the Pasteurize repair brief (`skills/cook/references/quality-gates.md:63-67`).
- Cook records `slug`, `branch`, and optional `pr` values under `repair_dispatch` (`skills/cook/references/quality-gates.md:42-46,67`).
- The manifest requires nonempty `slug` and `branch` strings (`src/easy_cheese_schemas/manifest.py:435-451`).
- The `pr` and `repair_dispatch` values default to absent (`src/easy_cheese_schemas/manifest.py:435-451`).
- Cook deduplicates live dispatches and obtains consent before dispatch (`skills/cook/references/quality-gates.md:63-65`).
- Pasteurize accepts a bug symptom and requires a reliable reproduction (`skills/pasteurize/SKILL.md:22-71`).
- Pasteurize writes `.cheese/pasteurize/<slug>.md` (`skills/pasteurize/SKILL.md:245-268`).
- Pasteurize then starts `/cook <slug> --auto` (`skills/pasteurize/SKILL.md:178-180,285-290`).
- The repair brief changes that command to `/cook <repair-slug> --auto --open-pr` (`skills/cook/references/quality-gates.md:66`).
- Cook does not wait for Pasteurize (`skills/cook/references/quality-gates.md:69-71`).
- A failed, halted, or active repair leaves the recorded debt unchanged (`skills/cook/references/quality-gates.md:69-71`).
- Cook resolves every bare slug through `artifact-path specs` (`skills/cook/SKILL.md:30-36`).
- Shared paths store `specs` in XDG storage and `pasteurize` under `.cheese/` (`src/easy_cheese/shared/paths.py:30-58`).
- The two path probes returned different files for the same slug.
- The Pasteurize path was `.cheese/pasteurize/repair-edge-probe.md`.
- The Cook path was `~/.local/share/cheese/paulnsorensen-easy-cheese/specs/repair-edge-probe.md`.
- The phase registry omits Pasteurize (`src/easy_cheese_schemas/_compiled_phase_registry.py:5-102`).
- The canonical writer rejects an unknown source phase (`src/easy_cheese/shared/write_handoff_artifact.py:47-58,151`).
- The writer probe returned exit 3 with `unknown source phase 'pasteurize'`.
- The parser permits only three optional keyed preamble lines (`src/easy_cheese/shared/handoff.py:83-87,105-161`).
- Pasteurize puts `cause`, `loop`, `seam`, `fix`, and `follow_up` before its orientation (`skills/pasteurize/SKILL.md:245-260`).
- Pasteurize defines halt modes for missing loops, missing seams, and exhausted fixes (`skills/pasteurize/SKILL.md:41-48,126-147,292-305`).
- The shared contract requires every dispatch to name its input and output contracts (`skills/cheese/references/handback-contract.md:124-129`).
- The Cook repair brief names its input fields, but it does not name the required Pasteurize output shape.
- Cook has no runtime import or direct command call into Pasteurize.
- The edge uses the skill dispatch brief and the handoff file.
- The focused tests passed with nine tests.
- The Cook test checks the dispatch phrase and worktree command (`tests/python/test_baseline_policy_coherence.py:57-70,201-236`).
- The handback test checks only the shared contract link (`tests/python/test_handback_grammar_docs.py:42-49`).
- No test dispatches Pasteurize, parses its handoff, or resumes Cook from that handoff.

## Findings by severity

### Blocker

none

### High

- **[spec:high] Cook cannot consume the documented Pasteurize slug.** Cook resolves the slug as a specification. Pasteurize emits a phase handoff at a different path. This mismatch stops the repair chain before Press, Age, Cure, and Plate. **Fix:** Pass an explicit canonical handoff reference. Make Cook resolve the Pasteurize artifact instead of a specification.
- **[correctness:high] Pasteurize cannot emit the required canonical handoff.** The registry omits the Pasteurize to Cook transition. The writer therefore rejects the phase before it writes a file. The manual template also places unsupported keys inside the preamble. Cook does not name the output contract in its repair brief. **Fix:** Register the transition. Expose the writer in the Pasteurize bundle. Name the output contract. Move diagnostic fields below the preamble.

### Medium

- **[assertions:medium] Tests cover only the Cook side of the dispatch.** Current tests check prose, classification, and worktree creation. They do not check the Pasteurize return path. **Fix:** Add one seam test for dispatch, canonical handoff, Cook resume, and halt behavior.

### Low

none

## STE100 status

not compliant

- `skills/cook/SKILL.md:63` puts two instructions in one sentence. Split the instructions.
- `skills/cook/SKILL.md:250` puts two instructions in one sentence. Split the instructions.
- `skills/cook/references/quality-gates.md:29` uses passive voice for collateral repairs. Use active voice.
- `skills/pasteurize/SKILL.md:24-30` uses `signal` and `loop` for one meaning. Use `feedback loop`.
- `skills/pasteurize/SKILL.md:81` gives two commands in one instruction. Split the instruction.

## Follow-ups

- Define one canonical Pasteurize to Cook handoff.
- Make Cook resolve the Pasteurize artifact.
- Add an end-to-end repair dispatch test.
