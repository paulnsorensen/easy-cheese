# Build to Shared Edge Review

## State

`ok`

The runtime contract agrees at HEAD.
The tests exercise the shared producer and the build consumer.
One low-risk duplicate type view can hide future contract drift from static checks.

## Evidence

### Shared producer

- `src/easy_cheese/shared/bundle_commands.py:20-24` defines the frozen `Command` value.
- `name`, `target`, and `summary` are required strings with no defaults.
- `src/easy_cheese/shared/bundle_commands.py:26-39` rejects invalid names, targets, and summaries with `ValueError`.
- A summary must contain one trimmed line and no Markdown table pipe.
- `src/easy_cheese/shared/bundle_commands.py:42-58` defines `command_map`.
- The function accepts `Sequence[Command]` and returns `dict[str, Command]`.
- It sorts exact names before it returns the copy.
- It rejects duplicate names, normalized alias collisions, and empty input.
- `src/easy_cheese/shared/bundle_commands.py:78-83` requires an explicit summary when it derives a command.

### Build consumer

- `scripts/render_generated_regions.py:35` imports only `Command` and `command_map` from shared.
- `scripts/render_generated_regions.py:269-273` imports each static `COMMANDS` tuple without resolving targets.
- `scripts/render_generated_regions.py:276-300` passes that tuple to `command_map`.
- The renderer reads each sorted `Command.name` and `Command.summary`.
- `scripts/render_generated_regions.py:75-81` discovers 13 skill manifests.
- `scripts/render_generated_regions.py:265-266,313-332` emits one `skills/<slug>/references/commands.md` file for each manifest.
- Generation stops before writes when a manifest import or `command_map` fails.
- Check mode reports each stale path and returns status one.
- Write mode creates missing parent directories and returns status zero.
- `scripts/render_generated_regions.py:336-348` defines these command modes.
- Build emits no file, command, or handoff field to shared.

### Skill prose

- The build and shared areas do not own `SKILL.md` files.
- `scripts/render_generated_regions.py:280-289` defines the generated command prose.
- Every bundled skill links its generated command reference from its `SKILL.md`.
- Evidence appears at `skills/affinage/SKILL.md:265`, `skills/age/SKILL.md:257`, and `skills/briesearch/SKILL.md:81`.
- Evidence appears at `skills/cook/SKILL.md:283`, `skills/cure/SKILL.md:291`, and `skills/easy-cheese-setup/SKILL.md:60`.
- Evidence appears at `skills/hard-cheese/SKILL.md:204`, `skills/melt/SKILL.md:177`, and `skills/mold/SKILL.md:160`.
- Evidence appears at `skills/pasteurize/SKILL.md:320`, `skills/plate/SKILL.md:157`, `skills/press/SKILL.md:170`, and `skills/wheypoint/SKILL.md:353`.

### Tests

- `tests/python/test_bundle_commands.py:64-94` tests producer validation for names, targets, and summaries.
- `tests/python/test_bundle_commands.py:97-118` tests duplicate names, alias collisions, and sorted output.
- `tests/python/test_bundle_commands.py:186-199` checks every real manifest and every target.
- `tests/python/test_bundle_commands.py:289-315` checks exact build output from names and summaries.
- `tests/python/test_bundle_commands.py:318-331` proves that documentation generation does not resolve command targets.
- `tests/python/test_bundle_commands.py:334-349` checks every emitted file and the complete skill set.
- The focused test run passed all 52 tests.
- `scripts/render_generated_regions.py --check` returned status zero.

## Findings by severity

### Blocker

none

### High

none

### Medium

none

### Low

- **[encapsulation:low] Build repeats the shared command shape.**
  `_DocumentedCommand` repeats all three fields at `scripts/render_generated_regions.py:47-50`.
  The renderer erases the `Command` type at `scripts/render_generated_regions.py:296`.
  Static checks can miss a future shared field rename at this consumer.
  **Fix:** Delete `_DocumentedCommand` and read `command.summary` directly.

## Contract drift

- The integrated shared contract requires an explicit command summary.
- Build follows that contract and emits each summary without substitution.
- No unmatched contract change remains at HEAD.

## STE100 status

`compliant`

The generated paragraph uses active voice and short sentences.
The current command summaries use one stable term for each meaning.
This note uses active voice, short sentences, and one term for each meaning.

## Follow-ups

- Remove `_DocumentedCommand` and use `Command.summary` directly.
