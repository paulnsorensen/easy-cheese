# Build Area Review

## Verdict

reject

## Findings

### Blocker

- **[correctness:blocker]** `tests/python/test_bundle_closure.py:155-174` writes a fixed marker into the real user site directory. When that file exists, the test overwrites it and does not restore its content. **Fix:** Set `PYTHONUSERBASE` to `tmp_path`. Create the marker inside that temporary site directory.

### High

- **[correctness:high]** `scripts/check_bundles.py:461-499` detects only literal `Command(...)` calls. Most manifests now use `derive_command(...)`, including `src/easy_cheese/skills/cook/commands.py:189-236`. A probe found zero discovered commands in 11 of 13 archives. Thus, `_check_command_dispatch` does not inspect those commands. `tests/python/test_bundle_closure.py:88-109` tests only the old manifest syntax. **Fix:** Build one command inventory from `@bundle_command`. Use it for closure checks, execution checks, and tests.
- **[correctness:high]** `scripts/check_bundles.py:719-756` returns an empty baseline after the Git batch process fails. `scripts/check_bundles.py:878-904` then treats every archive as new and reports all archives as current. A probe with an invalid repository root reported all 13 archives as current. **Fix:** Raise when the Git batch process fails. Treat only explicit `missing` headers as new archives.
- **[spec:high]** `justfile:2,14-31` omits `requirements-build.txt` from the Python test environment. Therefore, `tests/python/test_pyz_bundle.py:27-32` skips every bundle integration test in a clean environment. The focused run passed 324 tests and skipped 197 tests. All 197 skips came from `test_pyz_bundle.py`. `.github/workflows/validate.yml:79-85` has the same missing dependency. `.github/workflows/build-pyz.yml:8-17` does not run for bundle test changes. **Fix:** Install the build requirements for the main Python test job. Add bundle test paths to the build workflow filters.

### Medium

- **[correctness:medium]** `scripts/check_bundles.py:339-350` treats every `sys.stdlib_module_names` entry as importable. On Linux, `winreg` is in that set, but `importlib.util.find_spec("winreg")` returns `None`. The closure probe still returned no problem for a deferred `winreg` import. **Fix:** Check standard-library availability on the active interpreter. Add a test for an unavailable platform module.

### Low

- **[assertions:low]** `tests/python/test_bundle_closure.py:50-51,78-85,108-109,132-133` accepts any diagnostic that contains the expected module name. These checks pass when the resolver also emits unrelated problems. **Fix:** Assert the complete diagnostic list for each single-import fixture.
- **[telemetry:low]** `scripts/check_bundles.py:809-814` ignores every temporary worktree removal failure. Git can retain stale worktree metadata without a diagnostic. **Fix:** Require successful removal when no earlier error exists. Preserve an earlier error and report the cleanup failure.

## Simplifications

- The command checker retains a parser for the superseded literal `Command(...)` syntax. Replace it with the existing decorator contract.
- `SKILL_SUBCOMMANDS` duplicates every command manifest and already omits `cook accept`. Derive the test matrix from each `COMMANDS` tuple.
- `_baseline_blobs` uses an empty mapping for two meanings. Return separate states for a failed batch and an absent blob.
- `native_members` repeats the member scan in `_ArchiveAnalysis.from_archive`. Keep one scanner and reuse its result.
- `_DocumentedCommand` repeats the public `Command.summary` field. Use `Command` directly in the command renderer.

## Edge check

| Edge | State | Evidence |
| --- | --- | --- |
| `build -> shared` | ok | `scripts/render_generated_regions.py:35,269-298` uses `Command` and `command_map`. Their definitions exist at `src/easy_cheese/shared/bundle_commands.py:20-58`. The generated-region check completed successfully. |
| `build -> schemas` | ok | `scripts/render_generated_regions.py:36-38,206-260` reads registered contracts, transition data, and schema URIs. The generated-region check completed successfully. |
| `build -> skills` | broken | All 13 archives and command reference files exist. The bundle currency gate completed successfully. However, command execution checks discover no commands for 11 archives. |
| `build -> docs` | ok | `package.json:8-10` calls `scripts/gen_docs.py`. `.github/workflows/docs.yml:45-111` builds and deploys the site. `just docs-build` completed successfully. |

## STE100 status

compliant

## Follow-ups

none
