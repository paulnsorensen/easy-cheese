# Release 0.14 — open decisions

Base: `bab83ce4` (main, cut-free, basedpyright 0/0). Prior tag: `v0.13.0`.
Scope: five decisions the release owner must land or consciously defer before
tagging 0.14. Each carries one recommendation, not a menu.

---

## (a) Spec-format fork from #466 — v0.13-era specs fail `validate-spec` unconditionally

### What is actually true

`git ls-tree v0.13.0 --name-only src/` returns
`affinage age assets briesearch components content.config.ts content fanout
hard-cheese melt mold pasteurize styles` — **there is no
`src/easy_cheese_schemas` at v0.13.0**. The whole schemas package landed after
the tag (#380 published it to PyPI; #466 added the document-contract layer).
The v0.13 spec shape was never schema-declared; it was prose in
`skills/mold/references/curdle.md` § Spec template.

Reproduced against a spec built verbatim from the v0.13.0 template
(`git show v0.13.0:skills/mold/references/curdle.md`), run through
`skills/mold/scripts/mold.pyz validate-spec`:

```text
ERROR: missing-required-section 'Test Contracts' section not found in <spec>
ERROR: gate-applicability-required frontmatter gate_applicability is missing or unparseable in <spec>

FAIL: 2 error(s) in <spec>
EXIT=1
```

Both failures are structural and unconditional: the v0.13 template has no
`## Test Contracts` section and no `gate_applicability` frontmatter key, and
neither can be absent under
`src/easy_cheese/shared/document_rules.py` (`sections[].optional = False` for
Test Contracts) or `src/easy_cheese/skills/mold/validate_spec.py:322-327`.
`validate-spec` blocks curdle through the `spec-format-valid` gate node
(`tests/python/test_gate_graph.py:637-684`), so this is a hard stop, not a
warning.

### Options weighed

**Option 1 — ship as a documented breaking change.**
Cost: any spec authored under v0.13 must be re-run through `/mold`, or
hand-patched with a `gate_applicability` block and a `## Test Contracts` table.

**Option 2 — legacy-accept path in the schemas package.**
Cost: a permanent legacy branch in `validate_spec.py`, a second rule set in the
`_document_rules` projection, a sunset timer, and its own test matrix.

The decisive fact is that Option 2 **cannot be built as an adapter**. A v0.13
spec contains no source for any of the seven Test Contracts columns
(`Acceptance ID`, `Interface referent`, `Outermost stable seam`,
`Expected failure`, `Mode`, `Interface version`, `Matrix rows`) nor for
`work_class` / `ui_surface`. Its Acceptance section is EARS prose bullets with
no `AC-<n>:` identifiers, so even `ac-coverage-exactly-once` has nothing to
bind. A legacy path would have to *synthesise* those semantics — i.e. guess a
seam and a witness — and then issue a passing verdict on the guess. That is
precisely what ADR `legacy-adapter-lifecycle-004` forbids: migration happens
"only through exact schema/version adapters with declared sunsets", and no
exact adapter exists from an unversioned prose template to a semantic contract.

This is also the failure mode #401 already reported from the other direction
(Mold-produced specs rejected by Cut's contract inference). Adding a lenient
accept path re-opens that class rather than closing it.

### Recommendation — Option 1: ship as a documented breaking change

Blast radius is bounded and non-durable: specs live in per-project `.cheese/`
scratch, which is gitignored, not in a published artifact surface. The migration
is two additive edits to a document a human already owns.

Do:

1. Add a **"v0.13 → v0.14 spec migration"** subsection to
   `skills/mold/references/curdle.md`, immediately after § Spec template,
   listing exactly the two required additions and pointing at
   `tests/python/fixtures/spec_format/valid_spec.md` as the worked example.
2. Ship the release-notes caveat drafted in (d).
3. Do **not** add a `--legacy` or `--lenient` flag. `validate-spec` already
   separates syntax repair from semantic rejection; a bypass flag would erode
   the only thing the gate buys.

Do not do in 0.14: `gate_applicability.disposition` still carries the enum
value `red-required` (`src/easy_cheese/shared/document_rules.py`) on a tree
where the RED gate was removed by #560. The field itself is still load-bearing
— `src/easy_cheese/skills/mold/curd_count.py` and
`src/easy_cheese/shared/taste_test.py` both consume it — so keep it. Renaming
the enum value now would be a *second* spec-format break in one release.
Track the rename as post-0.14 work and land it with a real adapter.

---

## (b) #470 strict contract-version equality — compat window before the first post-0.14 minor bump

### Where it stands

#470 deleted `_decimal_greater`, `_migrate_payload`, `_MIGRATION_REGISTRY`, and
`MigrationStep`. Acceptance is now exact equality in two places:

- `src/easy_cheese_schemas/schema_runtime.py:738` (`validate_contract`)
- `src/easy_cheese_schemas/schema_runtime.py:679`
  (`_validate_curd_plan_against`)

The ADR (`writer-view-boundary-simplification-001`) justifies this on evidence:
the migration registry was empty, and producer and consumer ship in the same
commit. That reasoning holds **only while there is no independently versioned
client** — which stops being true the moment `easy-cheese-schemas` (PyPI, now
1.1.0) is consumed at a different version than the skill bundle that produced
the payload.

### The blocking precondition nobody has written down

There is currently **no per-contract version declaration at all**.
`schema_runtime.py:74-77` hardcodes every registered contract to 1.0:

```python
ContractVersion(schema_uri=schema_uri, major="1", minor="0")
if "contract_version" in attrs.fields_dict(contract)
else None
```

`contracts.py`'s `@contract(slug)` decorator records only a slug. So the first
minor bump is not a one-line change — it needs a declaration seam first. A
compat window that does not exist before that bump lands cannot be
retrofitted afterwards without a second break.

### Recommended mechanism — mirror `compat.py`, do not resurrect the registry

`src/easy_cheese_schemas/compat.py` already ships the right shape for this
repo: a `SCHEMA_VERSION` / `MIN_READABLE` pair with documented N-1 tolerance and
a `classify_stamp` → `Provenance` (`CURRENT` / `PRIOR` / `STALE` / `FUTURE` /
`UNSTAMPED`) verdict. It reports provenance rather than repairing payloads,
which is exactly the property #470's ADR wanted to preserve.

Land these five, in order:

1. **Declaration seam.** Extend `contracts.py` `@contract(slug)` to
   `@contract(slug, version="1.0", min_readable_minor="0")`, defaulting to
   today's values so the change is inert. Consume it in
   `contract_models.registered_contracts()` and in the `_RegisteredContract`
   construction at `schema_runtime.py:70-80`, replacing the hardcoded literal.
2. **Window check.** Replace both equality comparisons with: `schema_uri` must
   match exactly; `major` must match exactly; `min_readable_minor <=
   source.minor <= supported.minor`. Keep a *distinct* error message for a
   future minor ("written by a newer producer") versus a too-old minor, so a
   version skew is diagnosable from the message alone.
3. **Additive-only constraint, in place of migration code.** A minor bump may
   only add optional fields. That single rule is what makes a read window safe
   without `_migrate_payload`, and it is the clause that replaces the
   superseded minor-forward-migration text in
   `workflow-contract-milknado-seam-002`. Enforce it with a test that diffs the
   required-field set of the current contract against the previous minor's
   frozen conformance fixture.
4. **Widen the emitted JSON Schema with it.** `_contract_version_definition`
   (`schema_runtime.py:216-231`) pins `"const": version.minor`. If runtime
   widens and the published schema does not, a payload the library accepts is
   rejected by the schema shipped to external consumers — a silent
   producer/consumer fork in the PyPI package. Change `minor` to
   `{"enum": [<accepted minors>], "type": "string"}`; leave `major` and
   `schema_uri` as `const`.
5. **Conformance coverage.**
   `src/easy_cheese_schemas/conformance/v1/contract-cases.json` needs a
   prior-minor accept case and a below-window reject case, plus the matching
   assertions in `tests/schemas/python/test_schema_runtime.py`.

### Recommended timing

**Ship 0.14 with strict equality as-is.** Every contract is at 1.0, so the
window would be a no-op and would only add untested code to a release.

Make the window a **merge-blocking prerequisite on the PR that first bumps any
contract minor** — steps 1-5 land in that PR or before it, never after. Record
the constraint in the release notes as a known limitation (text in (d)) and in
the ADR so the next author does not discover it at bump time.

---

## (c) CI gap behind #562 — bundle regressions surface after merge

### Root cause, verified

Three independent holes, in descending order of blame:

1. **`main` has no required status checks.**
   `gh api repos/paulnsorensen/easy-cheese/branches/main/protection` →
   `404 Branch not protected`. PR #560's `build-pyz` job **did** run and
   **did** fail on both matrix legs (run `33334026483`, jobs `99317581430`
   and `99317581515`) — and the PR merged anyway. Nothing about paths filters
   or local skips would have mattered; the red check simply did not block.
   This is the cause of #562.

2. **The bundle suite silently skips locally.**
   `tests/python/test_pyz_bundle.py:27` skips the whole module when `build`,
   `pip`, or `shiv` is missing. `just check` runs it under the justfile's
   interpreter (`justfile:2`):
   `uv run --no-project --with-requirements requirements/runtime.txt --with
   pip==26.2.1 --with pytest==9.0.3 --with pyyaml==6.0.2 python3` — no `build`,
   no `shiv`. `requirements-build.txt` (`build`, `hatchling`, `shiv`) is never
   installed for `check`. So the author sees green locally, and the *only*
   thing that runs the suite is the one job that is not required.
   `validate.yml`'s `pytest tests/python -q` has the same gap: its env installs
   only `pytest`, `pyyaml`, and `requirements/runtime.txt`.

3. **`build-pyz.yml` paths filter excludes `tests/`.** Both the
   `pull_request` and `push` filters list `src/**`, `scripts/build_pyz.py`,
   `scripts/check_bundles.py`, `skills/*/scripts/*.pyz`, `pyproject.toml`,
   `requirements-build.txt`, `requirements/**/*.txt` — and nothing under
   `tests/`. A PR that only edits the bundle suite (which is exactly what
   #562 was) does not run the only job that executes it.

### Recommended fix, in landing order

**1. Require the checks (highest value, smallest diff).** Add a repository
ruleset on `main` requiring, at minimum:

- `check .pyz bundles are current`
- `check .pyz bundles are current (Python 3.14)`
- `test melt + shared + fan-out scripts`
- `validate skills`
- `lint markdown, yaml, python`
- `type-check python`

`/gh-bootstrap` already owns this ceremony. Until it is in place, every other
item here is advisory.

**2. Make the skip impossible where it must not happen.** Replace the bare
`pytestmark = pytest.mark.skipif(...)` in `tests/python/test_pyz_bundle.py`
with a guard that *fails* rather than skips when
`EASY_CHEESE_REQUIRE_BUNDLE_TESTS=1`, and set that variable in
`build-pyz.yml`'s "Test bundle build and isolation contracts" step. Five lines,
and it converts "build tooling missing → silently green" into a hard error in
the one job that is supposed to prove the bundles. Do this even if item 1 lands
— it closes the class, not just the instance.

**3. Add the test paths to the workflow filter.** In both `on.pull_request.paths`
and `on.push.paths` of `.github/workflows/build-pyz.yml`, add:

```yaml
      - 'tests/python/test_pyz_bundle.py'
      - 'tests/python/test_build_pyz_tree_staging.py'
      - 'tests/python/fixtures/**'
```

Path-list rather than a blanket `tests/**`, so unrelated test edits do not pay
the ~3-minute bundle build twice per matrix leg.

**4. (Optional) Run the suite locally.** Add a `bundle-python` interpreter var
to the justfile that appends `--with-requirements requirements-build.txt`, plus
a `test-bundles` recipe running `tests/python/test_pyz_bundle.py` and
`tests/python/test_build_pyz_tree_staging.py` under it, wired into `check` and
`ci`. This is genuinely useful but costs a real shiv build in every local
`just check`. Recommend deferring it behind items 1-3 and, if adopted, putting
it in `check` only — never make `ci` depend on a recipe that item 1 already
covers in a dedicated job.

---

## (d) Release-notes caveat queue

Verification performed for this section:

- **#304 — verified fixed on main; close it.** All three acceptance criteria
  are implemented. Opt-in concurrent dispatch, isolated worktree, and the
  resume link are specified in `skills/cook/references/quality-gates.md`
  § Repair pathway (steps 1-5: dedupe / consent / worktree / dispatch /
  record) with a § Merge-time topology section; the
  `baseline.repair_dispatch: {slug, branch, pr}` block is declared in
  § Baseline block shape; and it is enforced by
  `tests/python/test_baseline_policy_coherence.py` and
  `tests/fanout/python/test_validate_manifest.py`. Close as completed,
  citing the repair-pathway section — not as stale.
- **#492, #493, #393** — open, unimplemented, correctly stated as known gaps.
- **#542, #457, #425, #401, #546** — all describe `/cut` and RED-gate
  behaviour, which #560 removed from main. Retag each to the `next` channel
  (label `channel/next`, or move to the next-channel milestone) so 0.14
  triage does not keep surfacing issues about code that is not on this branch.
  #401 in particular is *not* reproducible on main: `cut.pyz` no longer ships.

### Draft caveat text (paste into the 0.14 release notes)

> #### Known limitations
>
> **Skill boundaries are documented, not enforced.** The one-skill / one-bundle
> doctrine in `AGENTS.md` § Skill Python bundle doctrine is the target
> contract, and existing violations are migration work. Nothing in this release
> mechanically prevents a skill from invoking another skill's archive, loose
> source, or repository automation. Typed, enforced boundaries between skills
> are tracked in #477 and are not part of 0.14 — treat the doctrine as a
> review checklist, not a guarantee.
>
> **Spec format is a breaking change.** `/mold` now validates spec documents at
> curdle time (`mold.pyz validate-spec`), and the gate blocks curdle. Specs
> authored under v0.13 fail unconditionally: they lack the `## Test Contracts`
> section and the `gate_applicability` frontmatter block, both of which are
> required. Re-run `/mold` on the spec, or add the two sections by hand —
> `skills/mold/references/curdle.md` § Spec template shows the shape and
> `tests/python/fixtures/spec_format/valid_spec.md` is a passing example.
> There is no legacy-accept mode: a v0.13 spec carries no source for the
> acceptance IDs, seams, and witnesses the validator checks, so accepting one
> would mean certifying a guess.
>
> **Contract versions are matched exactly.** `easy-cheese-schemas` accepts a
> payload only when its `contract_version` equals the version the host was
> built against. Every contract is at 1.0 today and producers ship with their
> consumers, so this is invisible in 0.14 — but there is no compatibility
> window yet. If you pin `easy-cheese-schemas` independently of the skill
> bundles, keep the two in lockstep. A read window (N-1 minor tolerance,
> additive-only minors) must land before the first contract minor bump.
>
> **Open gaps carried into 0.14.**
> - `/briesearch` `artifact-path` returns the research root; there is no
>   slug-aware `research-layout --json` command yet (#492).
> - `ground-check` validates report structure and local evidence only. Cited
>   remote URLs are not fetched or verified; that remains the selected
>   provider's responsibility (#493).
> - `/plate` does not use GitHub's documented `GET /repos/{owner}/{repo}/stacks`
>   preflight for Stacked PRs enablement; it still discovers the requirement
>   from an exit-4 on the first mutating operation (#393).
>
> **`/cut` is not in this release.** The RED-gate subsystem was removed from
> the main channel. Issues #542, #457, #425, #401, and #546 describe its
> behaviour and are tracked on the `next` soak channel, not here.

---

## (e) #477 — enforceable skill boundaries

Design is settled (approved Mold spec, four ADRs, canonical `PlannerResult` and
`CurdPlan` artifacts); execution ordering is not. Triage already marked it
`deferred` for that reason, and the ride-along dispositions for #429, #430,
#455, #459, and #460 are user calls about other people's open PRs — not
something to decide unilaterally inside a release-decisions pass.

Concrete implementation suggestions, with file paths and a wave order that does
not depend on restacking #433 first, are in
[`.cheese/issues/477-suggestions.md`](../issues/477-suggestions.md).

**Recommendation for 0.14:** do not attempt any part of #477 in this release.
Ship the doctrine as documentation with the caveat above, and start with
wave A of the suggestions document (bundle-ownership enforcement) in the first
0.15 cycle — it is the only wave with no open-PR dependency.
