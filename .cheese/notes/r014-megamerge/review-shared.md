# Shared Area Review

## Verdict

reject

Two blocker findings affect durable publication.
Three high findings affect security, portability, and contract ownership.

## Blocker

- **[correctness] Quote repair changes payload data.** `src/easy_cheese/shared/publication.py:132-168` marks all curly quotes as structural when no straight quote exists. A probe changed `{“a”: “don’t”}` to `{"a": "don't"}` before publication. `tests/python/test_publication_gateway.py:110-147` does not cover this case. **Fix:** Preserve quote characters inside values. Reject ambiguous input. Add the probe as a regression test.
- **[correctness] Replay ignores the requested operation identity.** `_validate_replay` omits `pointer.operation_id` at `src/easy_cheese/shared/publication.py:517-526`. A probe changed the value in `expected.json` to `other`. The replay returned a pointer with `operation_id=other`. **Fix:** Compare both operation IDs before rehydration. Add a tampered-pointer regression test.

## High

- **[security] Pointer input has no size limit.** Cook accepts a caller-provided path at `src/easy_cheese/skills/cook/contract_handlers.py:119-133`. `_read_pointer` calls `Path.read_bytes()` before validation at `src/easy_cheese/shared/publication.py:418-425`. The schema resolver already bounds referenced artifacts at `src/easy_cheese_schemas/artifacts.py:65-126,311-335`. **Fix:** Read pointers through one bounded schema helper. Reject oversized pointers before allocation.
- **[spec] Publication is not OS independent.** `pyproject.toml:15-22` declares OS-independent support. `_fsync_dir` opens and syncs a directory at `src/easy_cheese/shared/publication.py:298-303`. `_atomic_reveal` requires a hard link at `src/easy_cheese/shared/publication.py:326-345`. Windows directory handles and filesystems without hard links fail on these paths. **Fix:** Add one portable persistence backend. Test fallback paths without `fcntl`, directory `fsync`, or hard links.
- **[encapsulation] The applied taste-test cure keeps two parsers.** `src/easy_cheese/shared/taste_test.py:501-802` parses frontmatter, tables, and Grounding rows. `src/easy_cheese/skills/mold/validate_spec.py:223-634` parses the same document. `_grounding_rows` invents missing rows at `src/easy_cheese/shared/taste_test.py:681-689`. The canonical contract requires one row per probe at `src/easy_cheese_schemas/contracts.py:2604-2617`. **Fix:** Parse the document once in Mold. Pass `MoldSpecDocument` to shared taste checks. Synthesize rows only for a declared legacy policy.

## Medium

- **[spec] `compiled_commands` retains placeholder summaries from the superseded design.** It passes the command name as the summary at `src/easy_cheese/shared/bundle_commands.py:86-105`. Its only caller uses names at `src/easy_cheese/shared/bundle_commands.py:108-127`. This contradicts the explicit-summary decision in `.cheese/notes/r014-megamerge/shared.md:39-40`. **Fix:** Replace it with a private decorated-name helper. Remove the unused public export.

## Low

- **[spec] `CorruptLeftoverError` has stale behavior prose.** Its text promises removal at `src/easy_cheese/shared/publication.py:94-100`. Race repair can retain a valid replacement at `src/easy_cheese/shared/publication.py:403-408`. **Fix:** Describe both outcomes.
- **[deslop] One test name contradicts its assertion.** `tests/python/test_artifact_path.py:90-100` says the CLI prints a corpus root. The assertion checks a complete flat artifact path. **Fix:** Rename the test to describe the asserted path.

## Simplifications

- Delete `compiled_commands`. `validate_command_surface` needs only decorated command names.
- Keep one Mold Markdown parser. Do not construct a second typed document in shared code.
- Replace the five constructor protocols at `src/easy_cheese/shared/taste_test.py:37-99` with one typed construction boundary.
- Keep payload, receipt, and pointer reads behind one bounded artifact reader.
- Put OS-specific durability calls behind one small adapter.

## Edge check

| Edge | State | Evidence |
| --- | --- | --- |
| schemas -> shared: generated document rules | ok | `src/easy_cheese/shared/document_rules.py:6-53`; synchronization test at `tests/python/test_document_rules_compiler.py:243-248` |
| shared -> schemas: migration and publication models | ok | Imports at `src/easy_cheese/shared/migrate.py:22-35` and `src/easy_cheese/shared/publication.py:31-54` resolve at HEAD. |
| build -> shared: `Command.summary` | ok | Renderer use at `scripts/render_generated_regions.py:269-300`; manifest check at `tests/python/test_bundle_commands.py:289-342` |
| affinage -> shared | ok | Manifest import at `src/easy_cheese/skills/affinage/commands.py:7-11`; shared surface test at `tests/python/test_bundle_commands.py:253-258` |
| age -> shared | ok | Manifest import at `src/easy_cheese/skills/age/commands.py:8`; shared surface test at `tests/python/test_bundle_commands.py:253-258` |
| briesearch -> shared | ok | Manifest import at `src/easy_cheese/skills/briesearch/commands.py:7-11`; path import at `src/easy_cheese/skills/briesearch/research_layout.py:20` |
| cook -> shared | broken | `accept` matches at `src/easy_cheese/skills/cook/contract_handlers.py:119-142`, but pointer input is unbounded. |
| cure -> shared | ok | Manifest import at `src/easy_cheese/skills/cure/commands.py:7`; shared surface test at `tests/python/test_bundle_commands.py:253-258` |
| easy-cheese-setup -> shared | ok | `Command` and `dispatch` import at `src/easy_cheese/skills/easy_cheese_setup/commands.py:7`. |
| hard-cheese -> shared | ok | Manifest import at `src/easy_cheese/skills/hard_cheese/commands.py:7-11`; shared surface test at `tests/python/test_bundle_commands.py:253-258` |
| melt -> shared | ok | Manifest import at `src/easy_cheese/skills/melt/commands.py:7`; shared surface test at `tests/python/test_bundle_commands.py:253-258` |
| mold -> shared | broken | Imports exist at `src/easy_cheese/skills/mold/contract_handlers.py:27-28` and `curd_count.py:33-38`. Publication changes payload data, and taste checks keep duplicate parsing.
| pasteurize -> shared | ok | Manifest import at `src/easy_cheese/skills/pasteurize/commands.py:7`; shared surface test at `tests/python/test_bundle_commands.py:253-258` |
| plate -> shared | ok | Manifest import at `src/easy_cheese/skills/plate/commands.py:8`; shared surface test at `tests/python/test_bundle_commands.py:253-258` |
| press -> shared | ok | Targets at `src/easy_cheese/skills/press/commands.py:7-19` are callable under the manifest test. |
| wheypoint -> shared | ok | Manifest import at `src/easy_cheese/skills/wheypoint/commands.py:8-12`; path imports exist in `commit.py:66`, `resolve.py:43`, `storage.py:45`, and `wheypoint.py:43`. |

The focused review suite passed 174 tests.
The suite covered shared publication, paths, manifests, document rules, transport checks, and Mold taste checks.
`ruff check` passed for all 12 reviewed paths.
The migration bundle test stayed untested because this node must not rebuild bundles.

## STE100 status

compliant

## Follow-ups

- Fix quote repair before publication can change more payloads.
- Bind replay to `operation_id` before the next publication.
- Add a size limit for pointer input before the next release.
- Add the portable publication backend before merge.
- Replace the duplicate Mold parser before merge.
- Remove the superseded command-summary helper during shared cure.
- Correct the two low prose defects during shared cure.
