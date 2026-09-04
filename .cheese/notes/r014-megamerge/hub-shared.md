# Shared consumer hub review

Verdict: **reject**.

The focused seam suite reports 760 passes and seven skipped bundle tests.
The Cook acceptance file reports 12 skipped tests because build requirements are unavailable.
Generic manifest, generated command, and committed bundle checks pass for all 13 skill bundles.

## Edge check

| Edge | State | Evidence |
| --- | --- | --- |
| `affinage -> shared` | broken | Commands use `derive_command` at `src/easy_cheese/skills/affinage/commands.py:7-59`. Manifest and route tests cover these calls. `skills/affinage/SKILL.md:171-183` emits an invalid halt line. |
| `age -> shared` | broken | All named shared imports resolve. Happy-path tests cover the helpers. The lock, Press reader, finding grammar, provenance, and report write contracts do not match. |
| `briesearch -> shared` | broken | Commands and artifact paths match. `research_layout.py:37-43` uses only the generic slug validator. `test_artifact_path.py:122-149` accepts a two-word slug. |
| `cheese -> shared` | untested | `skills/cheese/references/escalation.md:32-48` calls the current `resolve_slug` signature. Shared tests cover resolver primitives. No Cheese test covers all decision branches. |
| `cook -> shared` | broken | Path and worktree calls match. `accept_main` permits network pointer reads. The documented writer call also removes the Cook report body. |
| `cure -> shared` | broken | Command targets and parser calls match. `skills/cure/SKILL.md:151-170` omits the body and cannot emit its terminal form. No Cure test covers this seam. |
| `easy-cheese-setup -> shared` | broken | Explicit summaries and targets match the shared entry points. Marker, repair, dry-run, help, and path contracts differ. Current tests protect some wrong behavior. |
| `hard-cheese -> shared` | ok | Both handlers use decorated callables and shared dispatch at `commands.py:7-39`. Bundle and command tests exercise both handlers. |
| `melt -> shared` | ok | Five handlers use decorated callables and `derive_command` at `commands.py:7-63`. Bundle tests and five focused modules cover dispatch. |
| `mold -> shared` | broken | Commands reach publication, migration, document, taste-test, and fan-out helpers. The normal flow bypasses publication. Phase ownership and document validation also differ. |
| `pasteurize -> shared` | broken | Route, CLI, and rerun behavior have focused tests. The generated route help contract fails because `--help` becomes an input path. |
| `plate -> shared` | ok | Both publication handlers use the shared manifest at `commands.py:8-34`. Committed bundle tests exercise both handlers. |
| `press -> shared` | broken | Route and telemetry tests cover the current helpers. The route, telemetry, dispatch, report, and generated summary contracts remain incomplete. |
| `wheypoint -> shared` | broken | Command and path calls match. Projection tests use only the Wheypoint parser. The shared handoff parser misreads or rejects each projection state. |

## Findings

### Blocker

- **[correctness:blocker] Age disables the review lock after a Git probe error.** `review_lock.py:50-52,157-160,203-210` treats each error as a non-repository. **Fix:** Fail closed for all operational Git errors. Add a failing-probe test.
- **[security:blocker] Age permits Git text conversion during review locking.** `review_lock.py:63-67,172-181` can run configured commands with reviewer privileges. **Fix:** Add `--no-textconv`. Disable command-valued Git helpers.
- **[correctness:blocker] Age writes the final report before its gated writer call.** `skills/age/SKILL.md:111-115,149-154` gives two writers the same target. **Fix:** Create a body-only input. Let the gated writer create the final report.
- **[security:blocker] Cook accepts network artifacts from untrusted pointers.** `publication.py:428-450` calls a resolver that accepts HTTPS. `test_cook_contract_accept.py:226-235` requires rejection. **Fix:** Reject non-local schemes before resolution. Add an active Cook acceptance test.
- **[correctness:blocker] Cure replaces its report with a handoff preamble.** `skills/cure/SKILL.md:97-99,135-159` omits `--body-file`. `write_handoff_artifact.py:106-109,164-173` replaces the target. **Fix:** Pass a body-only file and the upstream baseline.
- **[correctness:blocker] Setup documents an incomplete closing marker.** `skills/easy-cheese-setup/SKILL.md:38-40` gives `# <<<`. `hallouminate_setup.py:76-92` then replaces through end-of-file. **Fix:** Document the exact `END` marker. Add a trailing-configuration preservation test.
- **[correctness:blocker] The normal Mold flow bypasses shared publication.** `skills/mold/SKILL.md:20-24` never invokes the listed `publish` command. Cook receives no canonical pointer. **Fix:** Publish the validated plan before handoff. Pass the returned pointer to Cook.
- **[encapsulation:blocker] Mold exposes caller-selected publication phases.** `contract_handlers.py:88-102,126-136` can publish an unrelated valid transition through Mold. **Fix:** Remove both phase options. Bind `mold -> cook` inside the adapter.
- **[correctness:blocker] Press cannot encode its corrective continuation.** `skills/press/SKILL.md:123-143` emits `next: press` and unsupported keyed lines. The shared writer and parser reject this form. **Fix:** Define one canonical continuation. Put Press-only values in the report body.
- **[spec:blocker] Press dispatch cannot preserve automatic and publication flags.** `press_route.py:23-27` carries only the Age target. **Fix:** Add dispatch context to the route contract. Test exact flag propagation.
- **[correctness:blocker] Wheypoint projections break the shared handoff grammar.** `projection.py:68-81` puts metadata before orientation. Bare `status: gated` also lacks a reason. **Fix:** Render the shared preamble first. Move Wheypoint metadata into the body.

### High

- **[spec:high] Affinage omits the `status:` key for halt.** `skills/affinage/SKILL.md:171-183` conflicts with the shared handoff grammar. **Fix:** Use `status: halt: <reason>`.
- **[correctness:high] Age cannot read the Press findings that it requires.** `read_handoff_slug.py:19-45` returns only preamble fields. **Fix:** Read the complete Press artifact. Add a full Press-to-Age test.
- **[spec:high] Age publishes a finding form that the shared parser rejects.** `skills/age/SKILL.md:157-166` omits required list and location syntax. **Fix:** Publish the exact parser form. Add a prose-to-parser test.
- **[spec:high] Age discards upstream artifact and baseline values.** `skills/age/SKILL.md:112-116,151-155` hardcodes an empty artifact and omits baseline. **Fix:** Forward both available values through the shared writer.
- **[spec:high] Briesearch accepts slugs outside its four-to-six-word rule.** `research_layout.py:37-43` uses `validate_slug`, which permits one to 64 characters. **Fix:** Enforce the Briesearch word count. Test three, four, six, and seven words.
- **[security:high] Cook reads an unbounded pointer before validation.** `publication.py:418-425` reads the caller-selected file into memory. **Fix:** Add one bounded artifact read before allocation.
- **[correctness:high] Cook removes its report body during handoff writing.** `skills/cook/SKILL.md:126-160` omits `--body-file` for the same target. **Fix:** Pass a body-only file. Add a Cook report seam test.
- **[spec:high] Cure cannot emit its documented terminal state.** `skills/cure/SKILL.md:153-171` keeps a payload schema for `next: done`. Terminal transitions reject that schema. **Fix:** Give `age` and `done` separate commands. Omit the schema for `done`.
- **[spec:high] Setup promises repair but accepts every tenant file.** `hallouminate_setup.py:277-295` returns `noop` without checking repository identity. **Fix:** Validate the stored name and path. Repair drift with the supported force option.
- **[correctness:high] Mold has two source policies for one document.** `validate_spec.py:637-645` accepts source text that `taste_test.py:549-570` rejects. **Fix:** Use one typed document constructor and one source policy.
- **[assertions:high] Mold publication tests do not protect route identity.** `test_mold_contract_publish.py:85-105` omits source, destination, and schema assertions. **Fix:** Assert every pointer route and schema field.
- **[telemetry:high] Press treats non-test metadata changes as boundary-safe.** `press_telemetry.py:58-78,247-266` accepts project files outside the approved test paths. **Fix:** Compare changes with approved test paths. Report each other path as inconsistent.
- **[spec:high] Press has no out-of-contract concern outcome.** `press_route.py:10-16,74-87` cannot express the required Age follow-up. **Fix:** Add one concern outcome. Dispatch Age with the recorded concern.
- **[assertions:high] Wheypoint tests do not exercise the shared parser.** `test_wheypoint_skill_contract.py:156-161` checks prose tokens only. **Fix:** Round-trip normal and gated projections through `parse_handoff_slug`.

### Medium

- **[spec:medium] Setup dry-run output omits directory creation.** `hallouminate_setup.py:163-190` reports `noop` before `--apply` creates the corpus directory. **Fix:** Report directory creation as a planned change.
- **[spec:medium] Setup help lists an option that two commands reject.** `hallouminate_setup.py:314-323` adds `--migrate-legacy` to every parser. **Fix:** Add the option only to `global`. Test exact help for all commands.
- **[spec:medium] Setup prose treats the default config path as universal.** `SKILL.md:38-40` ignores the overrides in `hallouminate_setup.py:47-57`. **Fix:** Name `config_path()` as the authority.
- **[spec:medium] Press command text omits the public Age dispatch.** `commands.py:10-18` says the route only continues or stops. **Fix:** Name Continue, Age dispatch, and Stop. Regenerate the reference and bundle.
- **[spec:medium] Generated JSON commands promise help that they do not provide.** Age, Affinage, and Pasteurize route commands treat `--help` as a file path. **Fix:** Add help handling to `json_command`. Add committed bundle tests.

### Low

- **[spec:low] The Age `review-lock` summary says the command verifies a digest.** `commands.py:127-130` exposes only record behavior. **Fix:** Change the summary to `Record`. Regenerate the reference and bundle.

## STE100 status

This note is compliant.
Existing area reviews own all consumer prose corrections.
