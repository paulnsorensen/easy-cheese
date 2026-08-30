# #477 — Enforceable skill boundaries and doctrine-compliant bundles

Status: **suggested**. Base `bab83ce4` (main, cut-free).

## Why this is not a single fix

The design is settled — #477 links an approved Mold spec, ADRs
`skill-boundary-protocol-001`, `skill-boundary-normalization-002`,
`skill-bundle-authority-003`, `legacy-adapter-lifecycle-004`, and canonical
`PlannerResult` / `CurdPlan` artifacts. What blocks it is ordering and other
people's open PRs: the stated wave 1 requires restacking #433, and waves 2-7
depend on ride-along dispositions for #429, #430, #455, #459, #460. Those are
user calls on live branches, not code this pass can write.

The waves below are re-cut so that **wave A has no open-PR dependency** and can
start immediately.

## What already exists on main (do not rebuild)

- `src/easy_cheese/skills/<skill>/` + `src/easy_cheese/shared/` layout is in
  place; `src/easy_cheese_schemas/` is the published schema package.
- `scripts/build_pyz.py` builds one Shiv archive per registered skill;
  `scripts/check_bundles.py` compares canonical member content.
- `tests/python/test_pyz_bundle.py` already asserts several doctrine
  properties: `test_bundle_carries_only_its_own_skill_package`,
  `test_briesearch_bundle_uses_internal_distributions`,
  `test_plate_bundle_validates_publication_without_source_imports`.
- `@document_contract` / `@contract` decorators and the generated projections
  (`_document_rules.py`, `_compiled_phase_registry.py`, `_schema_catalog.py`)
  are the working precedent for "declare once, compile into the bundle".

So the gap is not the mechanism. It is that the doctrine has no *derivation*
(ownership is a hand-maintained registry) and no *rejection* (nothing fails a
build when a skill reaches outside its archive).

---

## Wave A — layout-derived bundle ownership and rejection (no dependencies)

Start here. This is the wave the release-decisions plan recommends for 0.15.

### A1. Derive the skill registry from `src/easy_cheese/skills/`

`scripts/build_pyz.py` currently carries an explicit registry of skills to
build (the "13-skill registry" #562 had to hand-edit when `/cut` was removed —
that hand-edit is the bug this item prevents). Replace it with a directory
scan of `src/easy_cheese/skills/*/` mapped to `skills/<kebab-slug>/scripts/<slug>.pyz`,
with the underscore→kebab conversion in one shared helper.

Regression test (`tests/python/test_pyz_bundle.py`): create a temporary
skill package under a staged source tree and assert the default batch builds
exactly one archive for it — asserting the derived path, not that "a file
exists". Assert the inverse too: a `skills/<name>/` directory with no
corresponding `src/easy_cheese/skills/<name>/` package must build no `.pyz`,
and an orphan `.pyz` with no source package must fail `check_bundles.py`.

### A2. Reject cross-skill imports at build time

Add an import-closure check to `scripts/build_pyz.py` (this is the work #460
prototyped; port the AST logic rather than re-deriving it). For each built
archive, walk the staged tree's ASTs and fail the build on any
`import easy_cheese.skills.<other>` where `<other>` is not the owning skill.
`easy_cheese.shared` and `easy_cheese_schemas` stay permitted.

Regression test: stage a skill package that imports another skill's module and
assert `build_pyz.py` exits non-zero with the offending module and symbol in
the message. Assert a `shared` import in the same position still builds.

### A3. Reject non-pure-Python and ambient dependencies

Doctrine forbids native extensions, platform-specific libraries, required
external executables, runtime installation, and caller-managed extraction. Add
to the same pass: fail on any `.so` / `.pyd` / `.dylib` member in a built
archive, and on any staged distribution whose wheel tag is not `py3-none-any`.

Regression test: build with a deliberately impure wheel staged in a temp
requirements file and assert the specific rejection message.

### A4. Reject repository-path and `PYTHONPATH` escapes in skill prose

`.github/scripts/validate_skills.py` already parses every `SKILL.md`. Extend it
to fail when a skill's prose or references invoke anything other than its own
archive: another skill's `.pyz`, a `scripts/` path, `common.pyz`, or a bare
`python3 src/...`. Today `skills/mold/references/curdle.md` still documents a
`python3 shared/scripts/artifact_path.py` fallback — that is the pattern to
catch.

Regression test in `.github/scripts/test_validate_skills.py`: a fixture skill
invoking a sibling archive must fail with the offending line quoted; the same
skill invoking `skills/<self>/scripts/<self>.pyz` must pass.

**Wave A exit criterion:** `just check` green, and removing a skill's source
package makes the build fail loudly instead of leaving a stale archive.

---

## Wave B — `@bundle_command` declarations (depends on A1 only)

Each skill's `commands.py` (`src/easy_cheese/skills/<skill>/commands.py`)
hand-maintains its subcommand map. Introduce a `@bundle_command("<verb>")`
decorator in `src/easy_cheese/shared/` following the exact pattern of
`@contract` in `src/easy_cheese_schemas/contracts.py` (module-scan +
marker attribute + deterministic ordering), and compile the declarations into
a generated per-skill command map staged into that skill's archive — the same
build-time projection pattern as `src/easy_cheese/shared/document_rules.py`.

This removes the drift class where a decorator exists but the dispatcher does
not list it, and it is the prerequisite for generated per-skill command
guidance in `SKILL.md`.

Regression test: extend the existing
`test_kebab_commands_and_legacy_aliases_dispatch_from_committed_bundles` to
assert the generated map is byte-identical to a fresh compile (a stale
projection must fail the build), and that an undeclared verb exits 2.

---

## Wave C — pointer-last Mold producer / pointer-only Cook consumer

This is the vertical boundary the issue actually names, and it is the wave that
should wait: it touches `PlannerResult` publication order and Cook's ingress,
both of which the ride-along PRs (#429, #430) still hold work for.

Shape, when it starts:

1. `HandoffPointer` contract in `src/easy_cheese_schemas/` (a new
   `@contract("handoff-pointer")` class next to the `CurdPlan` declaration),
   carrying `schema_uri`, `contract_version`, payload path, and payload digest.
2. Mold's curdle path writes payload → optional `NormalizationReceipt` →
   *then* the pointer. The pointer's appearance is the commit signal; an
   interrupted publication leaves no pointer and is therefore re-runnable.
   Seam: `src/easy_cheese/skills/mold/` curdle writer.
3. Cook's ingress (`src/easy_cheese/skills/cook/`, the merged CLI from #470)
   accepts *only* a pointer, resolves it, and re-validates the payload digest
   before use. Reject inline payloads with a typed error, not a fallback.

Regression test at the real seam: write a payload and pointer to a tmp tree,
then assert Cook's ingress (a) accepts the pointer, (b) rejects the payload
passed directly, and (c) rejects a pointer whose digest no longer matches the
payload on disk.

**Dependency note:** #430 carries projection/reference work. Land the pointer
contract in exactly one place — do not create a second schema authority. If
#430 lands first, extend its projection rather than adding a parallel one.

---

## Wave D — index/HEAD bundle currency

Port #459's currency enforcement after waves A and B: `check_bundles.py`
should fail when a committed `.pyz` does not match the *staged index*
content of its source, not merely the working tree. This is what turns "the
bundle is stale" from a merge-time surprise into a commit-time one.

Pair it with the CI fix in
[`../plans/release-0-14-decisions.md`](../plans/release-0-14-decisions.md) § (c):
currency enforcement is worthless while `build-pyz` is not a required check on
`main`.

---

## Sequencing summary

| Wave | Scope | Blocked on |
|---|---|---|
| A | Derived ownership, cross-skill/native/path rejection | nothing |
| B | `@bundle_command` compilation | A1 |
| C | Pointer-last Mold → pointer-only Cook | #429/#430 disposition |
| D | Index/HEAD bundle currency | A, B, and required checks on `main` |

Waves A and B are ordinary implementation work with clean outer seams and no
open-PR entanglement. Wave C is the one that genuinely needs the ride-along
decisions the triage note flagged. Do not open wave C before those are settled.

## Explicitly out of scope

The 0.14 release should ship the doctrine as documentation with the
"skill boundaries are documented, not enforced" caveat drafted in
`../plans/release-0-14-decisions.md` § (d). Partial enforcement is worse than
none: a check that catches three of five violation classes reads as a
guarantee it does not provide.
