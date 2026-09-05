# #477 — Enforceable skill boundaries and doctrine-compliant bundles

Status: **partly superseded**. Base: `bab83ce4` (main, cut-free).

## Current state

Release 0.14 lands wave B. Every skill declares its commands with
`@bundle_command` and compiles them with `derive_command`
(`src/easy_cheese/skills/affinage/commands.py:14-54`).
`validate_command_surface` rejects an undeclared or unreferenced name
(`src/easy_cheese/shared/bundle_commands.py:97-115`).

Waves A, C, and D remain open. The text below records the original plan.
Read every wave except wave B as a historical proposal.

## Why this work needs multiple changes

The design is complete.
Issue #477 links an approved Mold spec and four ADRs.
It also defines canonical `PlannerResult` and `CurdPlan` artifacts.

The original order depends on open pull requests.
Wave 1 requires a new base for #433.
Waves 2 through 7 require decisions for #429, #430, #455, #459, and #460.
The release owner must make those decisions.

The new order removes open pull request dependencies from wave A.

## Existing components on main

Do not rebuild these components:

- `src/easy_cheese/skills/<skill>/` contains each skill package.
- `src/easy_cheese/shared/` contains shared code.
- `src/easy_cheese_schemas/` contains the published schema package.
- `scripts/build_pyz.py` builds one Shiv archive for each registered skill.
- `scripts/check_bundles.py` compares canonical member content.
- `tests/python/test_pyz_bundle.py` checks several doctrine requirements.
- The bundle tests check package ownership, internal distributions, and source-independent publication.
- The `@document_contract` and `@contract` decorators declare contracts once.
- Generated projections compile those declarations into bundles.

The missing controls are derivation and rejection.
A maintained registry defines ownership.
No build check rejects access outside an archive.

---

## Wave A — derive ownership and reject violations (historical proposal)

Start with this wave.
The release plan recommends this wave for the first 0.15 cycle.

### A1. Derive the skill registry from `src/easy_cheese/skills/`

`scripts/build_pyz.py` contains an explicit skill registry.
PR #562 updates this registry after the removal of `/cut`.
That manual update shows the defect.

Replace the registry with a scan of `src/easy_cheese/skills/*/`.
Map each package to `skills/<kebab-slug>/scripts/<slug>.pyz`.
Put the underscore-to-kebab conversion in one shared function.

Add regression tests to `tests/python/test_pyz_bundle.py`.
Build a temporary skill package from a staged source tree.
Verify that the batch builds exactly one archive at the derived path.
Verify that an unmatched `skills/<name>/` directory builds no archive.
Verify that `check_bundles.py` rejects an orphan archive.

### A2. Reject cross-skill imports during the build

Add an import closure check to `scripts/build_pyz.py`.
Port the AST logic from #460.
Do not create another implementation.

Inspect each staged Python file for cross-skill imports.
Reject `import easy_cheese.skills.<other>` when `<other>` is not the owner.
Permit imports from `easy_cheese.shared` and `easy_cheese_schemas`.

Add a regression test with a cross-skill import.
Verify that the build fails and names the module and symbol.
Add a shared import in the same location.
Verify that this build succeeds.

### A3. Reject impure Python and ambient dependencies

The doctrine forbids native extensions and platform-specific libraries.
It also forbids required external programs, runtime installation, and caller-managed extraction.

Reject each `.so`, `.pyd`, or `.dylib` archive member.
Reject each staged distribution whose wheel tag is not `py3-none-any`.

Build a test archive with an impure wheel.
Verify that the build returns the specific error.

### A4. Reject repository path escapes in skill prose

`.github/scripts/validate_skills.py` parses every `SKILL.md` file.
Extend it to reject calls outside the skill archive.

Reject another skill archive, a `scripts/` path, `common.pyz`, or bare `python3 src/...`.
The fallback in `skills/mold/references/curdle.md` is one example.
It calls `python3 shared/scripts/artifact_path.py`.

Add regression tests to `.github/scripts/test_validate_skills.py`.
Verify that a sibling archive call fails and quotes the source line.
Verify that `skills/<self>/scripts/<self>.pyz` succeeds.

**Wave A exit criterion:** `just check` passes.
Removing a skill source package must produce a clear build failure.

---

## Wave B — declare bundle commands

Wave B depends only on A1.

Each `src/easy_cheese/skills/<skill>/commands.py` file maintains a command map.
Add a `@bundle_command("<verb>")` decorator to `src/easy_cheese/shared/`.
Follow the `@contract` pattern in `src/easy_cheese_schemas/contracts.py`.
Use a module scan, marker attribute, and deterministic order.
Compile the declarations into a command map for each skill.
Stage that map in the skill archive.

This change prevents drift between decorators and dispatchers.
It also supports generated command guidance in `SKILL.md`.

Extend `test_kebab_commands_and_legacy_aliases_dispatch_from_committed_bundles`.
Compare the generated map with a fresh compilation.
Reject a stale projection.
Verify that an undeclared verb exits with status 2.

---

## Wave C — publish pointers last and consume only pointers

Wait before you start this wave.
This wave changes `PlannerResult` publication and Cook input.
PRs #429 and #430 contain related work.

Use this structure:

1. Add `HandoffPointer` beside the `CurdPlan` declaration in `src/easy_cheese_schemas/`.
2. Declare it with `@contract("handoff-pointer")`.
3. Include `schema_uri`, `contract_version`, payload path, and payload digest.
4. Make Mold write the payload before the optional `NormalizationReceipt`.
5. Make Mold write the pointer last.
6. Treat the pointer as the commit signal.
7. Make Cook accept only a pointer.
8. Make Cook resolve the pointer and validate the payload digest.
9. Reject inline payloads with a typed error.

Add a test at the real boundary.
Write a payload and pointer to a temporary tree.
Verify that Cook accepts the pointer.
Verify that Cook rejects the direct payload.
Verify that Cook rejects an incorrect digest.

PR #430 contains projection and reference changes.
Keep the pointer contract in one location.
Extend the #430 projection if that PR lands first.

---

## Wave D — verify bundle currency against the index

Start this wave after waves A and B.
Port the currency checks from #459.
Make `check_bundles.py` compare archives with staged index content.
Do not compare only with working tree content.

Also apply the CI fix in the release plan.
The check has no value until `build-pyz` becomes required on `main`.

---

## Sequence

| Wave | Scope | Prerequisite |
|---|---|---|
| A | Derived ownership and violation rejection | none |
| B | `@bundle_command` compilation | A1 |
| C | Pointer publication and consumption | Decisions for #429 and #430 |
| D | Index bundle currency | A, B, and required checks on `main` |

Waves A and B have stable boundaries and no open pull request dependencies.
Wave C requires the related pull request decisions.
Do not start wave C before those decisions.

## Excluded from release 0.14 (historical proposal)

The original plan keeps every wave out of release 0.14.
It asks the release to publish the doctrine as documentation only.
Release 0.14 supersedes that plan for wave B.
Waves A, C, and D keep the original exclusion.

Do not add partial ownership or import enforcement.
An incomplete check appears to provide a guarantee that it cannot provide.