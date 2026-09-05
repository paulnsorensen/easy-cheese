# Cure round 2 — easy-cheese-setup

The area owns three paths. It owns `skills/easy-cheese-setup/SKILL.md`,
`skills/easy-cheese-setup/references/commands.md`, and
`src/easy_cheese/skills/easy_cheese_setup/commands.py`.
`src/easy_cheese/shared/hallouminate_setup.py` belongs to the `shared` area.
Every runtime fix goes to that area.

## Findings

| Source note | Severity | Finding | State | Commit | Evidence |
| --- | --- | --- | --- | --- | --- |
| review-easy-cheese-setup.md, hub-shared.md | blocker | The skill names an incomplete closing marker `# <<<`. | applied | `ad7b468a` | `skills/easy-cheese-setup/SKILL.md:43-44`; `tests/python/test_easy_cheese_setup_contract.py:18-31` |
| review-easy-cheese-setup.md | high | Tenant repair routes to a registration-only target. `apply_local` treats any existing file as complete. | deferred: owned by shared | none | `src/easy_cheese/shared/hallouminate_setup.py:277-295` |
| review-easy-cheese-setup.md | medium | The global dry run hides corpus directory creation. | deferred: owned by shared | none | `src/easy_cheese/shared/hallouminate_setup.py:172-195` |
| review-easy-cheese-setup.md | medium | The rules state that the installer changes only the marked block. | applied | `ad7b468a` | `skills/easy-cheese-setup/SKILL.md:64-66` |
| review-easy-cheese-setup.md | medium | Help advertises `--migrate-legacy` for `local` and `doctor`, then rejects it. | deferred: owned by shared | none | `src/easy_cheese/shared/hallouminate_setup.py:314-323` |
| review-easy-cheese-setup.md | medium | The skill names one configuration path as universal. | applied | `ad7b468a` | `skills/easy-cheese-setup/SKILL.md:40-41`; `tests/python/test_easy_cheese_setup_contract.py:41-44` |
| review-easy-cheese-setup.md | low | The prose uses `subcommand` and `repo` for meanings that the area names `command` and `repository`. | applied | `ad7b468a` | `skills/easy-cheese-setup/SKILL.md:22,26,55`; `tests/python/test_easy_cheese_setup_contract.py:34-38` |
| review-easy-cheese-setup.md | simplification | Replace the direct `Command` constructors with `derive_command`. | applied | `3b4969ce` | `src/easy_cheese/skills/easy_cheese_setup/commands.py:10-35` |
| review-easy-cheese-setup.md | simplification | Make `hallouminate_setup.main` call `_leg_main` and remove the duplicate parser. | deferred: owned by shared | none | `src/easy_cheese/shared/hallouminate_setup.py:338-357` |
| review-easy-cheese-setup.md | simplification | Keep one tenant-state validator for dry runs, repair, and apply. | deferred: owned by shared | none | `src/easy_cheese/shared/hallouminate_setup.py:172-295` |
| hub-shared.md | edge | `easy-cheese-setup -> shared`: marker, repair, dry-run, help, and path contracts differ. | partial | `ad7b468a`, `3b4969ce` | The two prose contracts now match the code. The three runtime contracts stay with `shared`. |

## Decision on the decorated handlers

The review asks for decorated shared entry points. `hallouminate_setup.py`
belongs to another area. This area declares three thin handlers in its own
command surface instead. Each handler imports one shared leg and returns its
exit status. The Melt bundle uses the same pattern.

## Disagreements

none

## Edge state after this node

| Edge | State | Evidence |
| --- | --- | --- |
| easy-cheese-setup -> shared: `Command` and `dispatch` | ok | `src/easy_cheese/skills/easy_cheese_setup/commands.py:7-39` |
| skill prose -> shared: `BEGIN` and `END` markers | ok | The test compares the prose against both constants. |
| `global` -> shared: `global_main` | broken | The dry run still omits directory creation. `shared` owns the fix. |
| `local` -> shared: `local_main` | broken | The target still cannot repair a tenant. `shared` owns the fix. |
| `doctor` -> shared: `doctor_main` | broken | Help still lists a rejected option. `shared` owns the fix. |
| build -> easy-cheese-setup: command reference | ok | The reference table matches all three summaries. |

## Tests

`tests/python/test_easy_cheese_setup_contract.py` is new. It has seven tests.
All seven pass. The migration tests and the bundle command tests also pass.

## Follow-ups

- `shared` must implement tenant repair in `apply_local`.
- `shared` must report corpus directory creation in the global dry run.
- `shared` must add `--migrate-legacy` only to the `global` parser.
- `shared` must remove the duplicate parser in `hallouminate_setup.main`.
- `tests/python/test_transport_audit.py::test_no_unaccounted_question_sites`
  fails at HEAD for `skills/briesearch/references/evals.md`. That file is
  outside this area.
