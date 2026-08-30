# Issue #556 — cross-test-module private imports (suggestions)

**Status:** suggested. Nothing to fix on `main` — the offending seam does not
exist here. Both remaining consumers live off-channel (open PR #514 and the
`next` soak branch), so the fix has to land there, not on `main`.

## What `main` actually contains (verified at `bab83ce4`)

Scope checked: `tests/`, `src/`, `scripts/`, `.github/` in the `main` worktree.

| Claim | Evidence |
|---|---|
| No module imports `_unaccounted_sites` | `grep -rn "_unaccounted_sites" .` → only `tests/python/test_transport_audit.py` (def at :193, calls at :230, :276, :292, :298) |
| No cross-test-module import at all | `grep -rnE "^\s*(from\|import)\s+test_" tests/ src/ scripts/ .github/` → no matches |
| `test_mold_domain_contracts.py` absent | file does not exist; `git log --all` shows it only on `origin/paulnsorensen/salvage-pr-330-changes` (PR #514, still **open**, `mergedAt: null`) |
| `test_cut_assertion_probe.py` / `test_red_gate_validator.py` absent | removed with the cut/RED-gate machinery (#560, #562); both still exist on `origin/next` |

`_unaccounted_sites` on `main` therefore has exactly one consumer — its own
module. Extracting it now would be a shared helper with no second caller, i.e.
a speculative abstraction. Do that extraction **as part of** whichever branch
adds the second consumer, per the plan below.

## Fix 1 — PR #514 (`paulnsorensen/salvage-pr-330-changes`)

`tests/python/test_mold_domain_contracts.py:14` is the reported seam:

```python
from test_transport_audit import _unaccounted_sites
```

Do this on that branch, before it merges:

1. Create `tests/python/transport_audit_helpers.py` — a plain sibling helper
   module, **not** a `test_*` module and **not** a new package. This is the
   established idiom in this suite: `tests/python/ref_extraction.py` is a
   shared non-test helper imported by `test_ref_extraction_fixture.py:8`,
   `test_reference_resolution.py:15`, and `test_stage_release.py:22`.
   Move into it, renamed public:
   - `QUESTION_KEYWORDS` (`test_transport_audit.py:37`)
   - `unaccounted_sites(...)` (from `_unaccounted_sites`, :193)

   Leave `_read` (:164) and `_paragraph_after` (:239) where they are — both
   have a single in-module consumer each and are not part of the shared seam.
2. In `test_transport_audit.py`, replace the definition with:

   ```python
   from transport_audit_helpers import (  # pyright: ignore[reportImplicitRelativeImport]
       QUESTION_KEYWORDS,
       unaccounted_sites,
   )
   ```

   and update the four call sites (:230, :276, :292, :298).
3. In `test_mold_domain_contracts.py`, import the same public name instead of
   the private one.

The `# pyright: ignore[reportImplicitRelativeImport]` comment is required
today and matches the three `ref_extraction` importers verbatim.

**Verified**, not assumed: a sibling helper module in `tests/python/` resolves
at runtime under the repo's own invocation
(`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 … -m pytest tests/python -q`) because pytest's
prepend import mode inserts `tests/python` on `sys.path` (there is no
`__init__.py` there). basedpyright resolves it too, but emits
`reportImplicitRelativeImport` unless suppressed — confirmed by running
`just typecheck` against a throwaway probe on this branch.

## Fix 2 — `next` soak branch (the repeated pattern)

`origin/next:tests/python/test_cut_assertion_probe.py:9-13`:

```python
from test_red_gate_validator import (  # pyright: ignore[reportImplicitRelativeImport]
    _candidate,   # pyright: ignore[reportPrivateUsage]
    _issue,       # pyright: ignore[reportPrivateUsage]
    _receipt_path,# pyright: ignore[reportPrivateUsage]
)
```

Sources on that branch: `_receipt_path` at `test_red_gate_validator.py:91`,
`_issue` at :142, `_candidate` at :158. Same treatment: move those three (plus
the `_begin`/`_spec`/`_digest` helpers they call, if they are not already
self-contained) into `tests/python/red_gate_receipt_helpers.py` as public
names, and re-point both modules. That deletes three `reportPrivateUsage`
suppressions, which is the local signal that the seam is gone.

`test_cut_assertion_probe.py` is a Cut-protected oracle on that branch, so this
needs a re-cut there — that constraint is why #556 was deferred in the first
place and it has not changed.

## Optional — stop the pattern recurring on `main`

Not applied here, because it would fail `next`'s CI the moment `next` merges
back, and that is a release-owner call rather than a bug fix.

Add to a `main` test (e.g. a new `tests/python/test_test_suite_hygiene.py`):
walk `tests/**/*.py` with `ast.parse`, and assert no `ImportFrom` node whose
`module` starts with `test_`. Roughly 25 lines, no new dependency. It fails
today on `next` (`test_cut_assertion_probe.py`) and on PR #514 — which is the
point: it converts "someone must remember" into a gate. Land it only after
Fix 1 and Fix 2, or it blocks both branches.

## Related cleanup found while verifying (separate from #556)

Adding

```toml
[[tool.basedpyright.executionEnvironments]]
root = "tests/python"
extraPaths = ["tests/python", ".", "src", "scripts", ".github/scripts", "src/easy_cheese_schemas"]
```

before the existing `root = "tests"` block in `pyproject.toml` makes
basedpyright treat `tests/python` as a real search root, which clears
`reportImplicitRelativeImport` for the whole directory. Verified: with that
block, `just typecheck` reports `0 errors` and instead flags the three existing
`# pyright: ignore[reportImplicitRelativeImport]` comments in
`test_ref_extraction_fixture.py`, `test_reference_resolution.py`, and
`test_stage_release.py` as unnecessary (`reportUnnecessaryTypeIgnoreComment`),
so those three comments must be deleted in the same commit. It mirrors the
`tests/schemas/python` and `tests/wheypoint/python` blocks already there.
This is orthogonal to #556 — it removes the need for the ignore comment in
Fix 1, but does nothing about the encapsulation seam itself.
