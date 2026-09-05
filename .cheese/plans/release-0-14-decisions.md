# Release 0.14 decision record

Base: `bab83ce4` (main, cut-free, basedpyright 0/0). Prior tag: `v0.13.0`.

This record captures five release decisions.
A resolved decision names the PR that superseded an earlier recommendation.

---

## (a) Spec format from #466

### Historical behavior before PR #592

This section describes the behavior before PR #592.
Version 0.13.0 does not contain `src/easy_cheese_schemas`.
PR #380 published the schema package after that tag.
PR #466 adds the document contract layer after that tag.

The version 0.13 spec format exists only in `skills/mold/references/curdle.md`.
Before PR #592, that template fails `skills/mold/scripts/mold.pyz validate-spec`:

```text
ERROR: missing-required-section 'Test Contracts' section not found in <spec>
ERROR: gate-applicability-required frontmatter gate_applicability is missing or unparseable in <spec>

FAIL: 2 error(s) in <spec>
EXIT=1
```

Before PR #592, both failures always occur.
The old template has no `## Test Contracts` section.
It also has no `gate_applicability` frontmatter key.

At that time, `src/easy_cheese/shared/document_rules.py` requires the Test Contracts section.
The current read and strict-mint policy is in `src/easy_cheese/skills/mold/validate_spec.py:637-735`.
Before PR #592, the `spec-format-valid` gate blocks curdle after either failure.

### Resolved decision

PR #592 supersedes the original recommendation.
Release 0.14 accepts version 0.13 specs only on read.
The read path reports a notice for each legacy spec.
Mint and rewrite paths require the current format.
`src/easy_cheese_schemas/spec_format.py` owns this policy.
No `--legacy` or `--lenient` option exists.
This decision keeps existing specs readable without weakening new specs.

Do not rename `gate_applicability.disposition` in release 0.14.
The field still uses `red-required` after #560 removed the RED gate.
`src/easy_cheese/skills/mold/curd_count.py` and `src/easy_cheese/shared/taste_test.py` still use the field.
Track the rename after release 0.14.
Include an exact adapter with that change.

---

## (b) Strict contract version equality from #470

### Current behavior

PR #470 removed `_decimal_greater`, `_migrate_payload`, `_MIGRATION_REGISTRY`, and `MigrationStep`.
The runtime now requires exact equality in two locations:

- `src/easy_cheese_schemas/schema_runtime.py:738` in `validate_contract`
- `src/easy_cheese_schemas/schema_runtime.py:679` in `_validate_curd_plan_against`

ADR `writer-view-boundary-simplification-001` supports this behavior for paired producers and consumers.
That condition ends when clients independently select `easy-cheese-schemas` versions.

### Missing prerequisite

The code has no declaration for individual contract versions.
`schema_runtime.py:74-77` gives every registered contract version 1.0:

```python
ContractVersion(schema_uri=schema_uri, major="1", minor="0")
if "contract_version" in attrs.fields_dict(contract)
else None
```

The `@contract(slug)` decorator stores only a slug.
A minor version change first needs a declaration interface.
The compatibility window must exist before the first minor change.

### Recommended mechanism

Use the pattern from `src/easy_cheese_schemas/compat.py`.
Do not restore the migration registry.

That module defines `SCHEMA_VERSION`, `MIN_READABLE`, and `classify_stamp`.
It reports `CURRENT`, `PRIOR`, `STALE`, `FUTURE`, or `UNSTAMPED`.
It does not modify payloads.
This behavior preserves the requirement from #470.

Complete these actions in order:

1. Extend `@contract(slug)` to accept `version="1.0"` and `min_readable_minor="0"`.
2. Keep the current values as defaults.
3. Use those values in `contract_models.registered_contracts()` and `_RegisteredContract`.
4. Require an exact `schema_uri` and exact major version.
5. Accept each minor version inside the declared read window.
6. Use different errors for future and obsolete minor versions.
7. Permit a minor version to add only optional fields.
8. Compare required fields with the previous frozen conformance fixture.
9. Update `_contract_version_definition` to list accepted minor versions.
10. Keep `major` and `schema_uri` as `const` values.
11. Add prior-minor and below-window cases to the conformance data.
12. Add matching assertions to `tests/schemas/python/test_schema_runtime.py`.

The optional-field rule replaces minor-version payload migration.
The JSON Schema must accept every payload that the runtime accepts.

### Recommended time

Keep strict equality in release 0.14.
Every current contract uses version 1.0.
A compatibility window cannot exercise another version now.

Require this work before the first contract minor version change.
Update the ADR so the next author sees this prerequisite.
Add the limitation from section (d) to the release notes.

---

## (c) CI gap behind #562

### Verified cause

Three independent gaps caused the failure.

1. **`main` has no required status checks.**
   The branch protection API returned 404.
   The `build-pyz` job fails on both matrix entries for PR #560.
   The repository still merged the pull request.
   This gap caused #562.
2. **The bundle suite skips without local build tools.**
   `tests/python/test_pyz_bundle.py:27` skips when `build`, `pip`, or `shiv` is absent.
   The `just check` environment does not install `build` or `shiv`.
   The `validate.yml` environment has the same gap.
3. **The `build-pyz.yml` path filter excludes tests.**
   A pull request that changes only bundle tests does not start that job.

### Recommended fix order

**1. Require the checks.**

Use `/gh-bootstrap` to require these checks on `main`:

- `check .pyz bundles are current`
- `check .pyz bundles are current (Python 3.14)`
- `test melt + shared + fan-out scripts`
- `validate skills`
- `lint markdown, yaml, python`
- `type-check python`

Other fixes remain advisory until these checks become required.

**2. Make required bundle tests fail when tools are absent.**

Replace the unconditional module skip in `tests/python/test_pyz_bundle.py`.
Fail when a tool is absent and `EASY_CHEESE_REQUIRE_BUNDLE_TESTS=1`.
Set that variable in the bundle test step of `build-pyz.yml`.
Keep this fix after required checks become active.

**3. Add bundle test paths to both workflow filters.**

Add these entries to `on.pull_request.paths` and `on.push.paths`:

```yaml
      - 'tests/python/test_pyz_bundle.py'
      - 'tests/python/test_build_pyz_tree_staging.py'
      - 'tests/python/fixtures/**'
```

Do not use `tests/**`.
That broad filter would run two expensive jobs for unrelated test changes.

**4. Optionally run the bundle suite locally.**

Add a `bundle-python` interpreter variable to the justfile.
Include `--with-requirements requirements-build.txt`.
Add a `test-bundles` recipe for the two bundle test files.
Add the recipe to `check` and `ci`.

This option adds a Shiv build to each local `just check`.
Defer this option until items 1 through 3 are complete.
If you adopt it, add it only to `check`.
The dedicated CI job already covers this work.

---

## (d) Release note caveats

### Verified issue state

- **#304:** All three acceptance criteria exist on main.
- The Cook repair pathway defines dispatch, worktree isolation, and the resume link.
- The tests enforce the repair pathway.
- Close #304 as complete and cite that section.
- **#492, #493, and #393:** The integrated release closes all three issues.
  `research-layout` prints the slug-aware layout as JSON
  (`src/easy_cheese/skills/briesearch/commands.py:35-39`).
  `artifact-path` resolves a phase and a slug
  (`src/easy_cheese/shared/artifact_path.py:27-37`).
  `ground-check` reports a `REMOTE` error for a cited URL that the capture
  manifest omits (`src/easy_cheese/skills/briesearch/ground_check.py:32-37`).
  `stack-tools` runs the documented enablement preflight
  (`skills/plate/references/gh-stack.md:50-70`).
- **#542, #457, #425, #401, and #546:** These issues describe removed `/cut` behavior.
- Move those issues to the `next` channel.
- Issue #401 does not reproduce on main because `cut.pyz` no longer ships.

### Draft text for the release notes

> #### Known limitations
>
> **Skill boundaries are documented, and command surfaces are enforced.**
> The doctrine in `AGENTS.md` defines one skill for each bundle.
> `validate_command_surface` rejects an undeclared or unreferenced command name.
> This release does not yet prevent calls to another archive or to loose source.
> Issue #477 tracks the remaining ownership and import checks.
>
> **Spec readers accept version 0.13 files.**
> `/mold` reports a notice when it reads a legacy spec.
> The read path does not require the newer sections or `gate_applicability`.
> Mint and rewrite paths require the current format.
> Run `/mold` again to update a legacy spec.
>
> **Contract versions must match exactly.**
> `easy-cheese-schemas` accepts only the host contract version.
> All current contracts use version 1.0.
> Keep independently installed schemas and skill bundles at matching versions.
> Add a read window before the first contract minor version change.
> That window must permit only additive minor changes.
>
> **`/cut` is not in this release.**
> The main channel no longer contains the RED gate subsystem.
> Issues #542, #457, #425, #401, and #546 remain on the `next` channel.

---

## (e) Enforceable skill boundaries from #477

The approved Mold spec and four ADRs define the design.
Canonical `PlannerResult` and `CurdPlan` artifacts also exist.

### Resolved decision

PR #592 supersedes the deferred plan.
Release 0.14 enforces command boundaries through explicit command manifests.
The integrated implementation includes the planned command boundary work.
Do not defer this work to release 0.15.