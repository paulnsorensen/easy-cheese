# Issue #425 — suggestions

`/cut: fold RED-oracle evidence into the existing test format, not a separate tests/cut/ folder`

## Channel

**This is a `next`-channel issue. Do not implement it on `main`.**

PR #560 removed `/cut` from `main`; there is no `skills/cut/` and no
`skills/cut/scripts/cut.pyz` to change there. The behavior reported in
`sorensen-labs/football` PR #11 came from an installed `cut.pyz`, which `main`
no longer produces. Retag to a next-channel label (see #542's suggestions for
the label proposal).

## Root cause — narrower than the issue assumes

The `tests/cut/cut_*.py` layout is **not prescribed by the repository**.
Grepping `origin/next` for `tests/cut` across `skills/`, `src/`, and `docs/`
returns nothing. The oracle path is chosen by the agent at
`skills/cut/SKILL.md` step 6 ("Write only the oracle"), constrained only by:

- `_is_test_side_path` (`src/easy_cheese/shared/cut/red_gate.py:3040-3051`),
  which accepts any path with a `test` / `tests` / `spec` / `specs` /
  `__tests__` directory part, or a basename of `conftest.py`, or one starting
  with `test_`, or matching `(_test|.test|.spec).<ext>$`.
- `_protected_errors` (`red_gate.py:1536`), which byte-freezes whatever paths
  the candidate declares as protected test files.

Note what `_is_test_side_path` permits: `tests/cut/cut_ingest_ac1.py` is
test-side purely because of the `tests` **directory part** — the `cut_` basename
is irrelevant to the check. So the machinery cheerfully accepts a file that
pytest will never collect and that ruff will always lint. That gap is the
actual defect, and it is fixable in about twenty lines.

## Proposal: the preferred direction is already reachable

The issue's preferred fix ("emit the evidence as normal pytest test files …
have the GateReceipt select them by nodeid / `pytest -k` + exit code") does not
need new machinery. `_python_case_command` (`red_gate.py:1285-1330`) already
supports a `python -m pytest` profile and forwards `argv[3:]` verbatim as
selectors, and the probe reports assertion origin **in-interpreter** rather
than by scraping stderr — so a nodeid selector satisfies the RED contract
exactly as a loose script argv does. The frozen-witness half is likewise
independent of file location: it is enforced by the protected-file digests,
not by living outside `tests/`.

So this is a prose-plus-validation change, not a redesign.

### 1. Make the skill prose require a collected test file

Rewrite `skills/cut/SKILL.md` step 6 and the matching section of
`skills/cut/references/gate-workflow.md`:

> Author each oracle as a normal test file in the project's existing test
> layout, named so the declared runner collects it (`test_*.py` /
> `*_test.py` for pytest). Select it in the case argv by nodeid
> (`python -m pytest tests/test_ingest.py::test_ingest_ac1`). Declare it as a
> protected test file so its bytes are frozen; do not create a runner-invisible
> directory such as `tests/cut/`.

### 2. Enforce it, so prose is not the only guard

Add a check in `_semantic_errors` (`red_gate.py:952`) — the existing candidate
validation seam — that rejects a protected oracle path when **both** hold:

- the path is test-side only by virtue of a test **directory** part (i.e.
  `_is_test_side_path` is true but the basename would not satisfy it alone),
  and
- the declared runner is a collecting runner (`pytest` or `unittest` per
  `_python_case_runner`, `red_gate.py:1241`).

Refusal text, in #542's `authoring` category:

```text
protected oracle tests/cut/cut_ingest_ac1.py is not collected by the declared
pytest runner; name it test_*.py in the existing test root, or place it outside
the project's test tree
```

Factor the basename half of `_is_test_side_path` into a small
`_is_collected_basename(name, runner)` helper so both call sites share one
definition. That is the whole implementation.

### 3. Keep the fallback available, and understand what it costs

The issue's fallback — oracles under `.cheese/cut/oracles/` — is *permitted* by
this rule (no test directory part, so the collecting-runner check does not
apply), and it does keep them off both the pytest and ruff surfaces. But note a
consequence the issue does not:

**`.cheese` is in `_EXCLUDED_SNAPSHOT_DIRS` (`red_gate.py:166-175`).** An
oracle under `.cheese/cut/oracles/` is invisible to the production-tree
snapshot, so it is protected *only* by its protected-file digest, not by the
tree fingerprint's double-bracketed TOCTOU check. That is a weaker integrity
posture than an oracle inside the snapshotted tree. Document it as the
last-resort option the issue already calls it, and say why.

## Tests

New `tests/python/test_cut_oracle_placement.py`, at the real seam:

- a candidate declaring protected `tests/cut/cut_ingest_ac1.py` with a
  `python -m pytest` runner -> refused, no receipt at `--out`, message names
  the path and the runner
- the same path with a direct-script runner (`python tests/cut/cut_x.py`) ->
  accepted, since nothing claims collection
- `tests/test_ingest.py::test_ingest_ac1` under pytest -> accepted, receipt
  issued, RED replayed at the nodeid
- `tests/conftest.py` -> still accepted (basename satisfies collection on its
  own; do not regress the existing rule)
- an oracle under `.cheese/cut/oracles/` -> accepted, and assert the receipt
  records it as protected while the phase-token snapshot contains no entry for
  it (pins the tradeoff in item 3 rather than leaving it folklore)

## Tradeoffs

- **A collected oracle fails the project's suite between RED and GREEN.** This
  is the real cost of the preferred direction, and it is acceptable only
  because Cut -> Cook is atomic within one branch and never commits between RED
  and GREEN. State that constraint explicitly in the prose change; if a
  workflow ever needs to commit mid-window, this decision has to be revisited.
- **`xfail` is not an escape hatch.** `@pytest.mark.xfail(strict=True)` makes
  the run exit `0` and swallows the `AssertionError`, destroying the RED
  witness. Do not suggest it.
- **The duplicate-coverage complaint resolves itself.** The issue notes the
  oracles "duplicate the durable contract/hardening tests the same spec
  produces". Folding the oracle into the normal test file makes the RED oracle
  and the durable test the *same* file — the duplication disappears rather than
  being managed.
- **Consuming repos still need a one-time cleanup.** Existing
  `extend-exclude = ["tests/cut/cut_*.py"]` entries (e.g. the two
  `pyproject.toml` files in `sorensen-labs/football`) can be dropped once their
  oracles are renamed. Worth a note in the release entry; not this repo's work.
- **Ordering.** Independent of #542 and #546, and cheap. This is the best
  first-landing candidate of the five — it fixes a reproducible CI break in
  consuming repos with a contained diff.

## Acceptance mapping

| Issue acceptance criterion | Satisfied by |
|---|---|
| "A fresh `/cut` run produces no files that require a ruff `extend-exclude`" | Items 1 + 2 — collected `test_*.py` files lint like every other test |
| "Oracle evidence is either collected by the normal test runner or lives entirely outside `tests/`" | Item 2's check enforces exactly this disjunction, with item 3 as the documented second branch |

## Effort

Small. One helper + one check in `_semantic_errors`, two prose edits, one new
test module.
