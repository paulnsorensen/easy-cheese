# Issue #457 — suggestions

`Decide: keep the Cut RED-gate as an adversary gate, an accident gate, or retire it`

## Channel

**This is a `next`-channel decision. It is already settled on `main`.**

PR #560 removed the `/cut` skill and the RED-gate machinery from `main`, and
#562 dropped the cut and red-gate expectations from the `.pyz` bundle suite.
On `main`, option **C (retire)** is the shipped state — `main` has no
`skills/cut/`, no `src/easy_cheese/shared/cut/`, and no `cut.pyz`.

So the live question is narrower than the issue frames it: **what threat model
does the gate carry on the `next` soak branch, where it still lives?** Retag to
a next-channel label (see #542's suggestions for the label proposal).

## Re-verification against current `origin/next`

The issue's evidence was gathered at the `hoist/418v2` tree. Line numbers have
shifted; the findings have not. Re-checked against `origin/next`:

| Finding | Status on `next` | Current location |
|---|---|---|
| 1. Assertion-origin short-circuit | **Still present** | `_looks_harness_failure`, `red_gate.py:1384-1387` — `if run.assertion_origin: return False` still precedes the marker scan |
| 2. Probe fd on argv | **Still present** | `_python_case_command` appends `str(probe_fd)` to the bootstrap prefix, `red_gate.py:1285-1316` |
| 3. Asymmetric shadow defence | **Still present, and sharper than described** | `_stdlib_unittest` is called only from `_run_direct` (`cut_assertion_probe.py:246`, used at `:367`); `_run_pytest` (`:430`) and `_run_unittest` (`:482`) do no origin check. In the bootstrap, `import unittest` (`red_gate.py:265`) runs *inside* the trusted quarantine, but `import pytest` (`:263`) runs immediately after `sys.path[:] = target_path` (`:262`) — pytest is resolved from the target path, outside quarantine |
| 4. Console-seam detect / `hookwrapper` | **Still present** | `pytest.hookimpl(hookwrapper=True)`, `cut_assertion_probe.py:441` |
| 5. Snapshot walk hashes `.venv` | **Still present** | `_EXCLUDED_SNAPSHOT_DIRS` (`red_gate.py:166-175`) covers `.git`, `.cheese`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `__pycache__` — no `.venv`, `node_modules`, `.tox`, `node_modules`, `dist`, `build` |
| 6. File size | **Worse** | `red_gate.py` is now 3,468 lines (was 3,239) |

## Recommendation: option B+ — an honestly-scoped accident gate, hardened

Not A, not C. Reasoning:

- **Against A (adversary gate).** The forgery hole is not fixable by a nonce.
  A per-run token passed on argv is readable by the same test code that reads
  `/proc/self/fd` — it raises the exploit's cost from three lines to five. A
  genuine adversary gate needs the probe channel to be unreachable from user
  code, which means the fd must be closed in the child before the test body
  runs, with the probe holding the only reference. That is a real redesign of
  `_python_case_command` / `cut_assertion_probe`, and it still cannot survive a
  test that simply `os._exit(1)`s after writing a crafted event from inside the
  probe's own process. Paying redesign cost for a property you cannot fully
  reach is the wrong trade.
- **Against C (retire).** `main` already took C. `next` exists to soak the
  gate. Retiring it on `next` too would mean deleting the branch's reason to
  exist — that is a channel decision, not a code decision, and it should be
  made explicitly by the release owner rather than as the outcome of this
  issue.
- **For B+.** The accident-gate value is the part the issue reports as proven
  daily, and #542's data corroborates it ("the gate rejected harness-only
  failures and witness mismatches before issuing evidence"). Findings 3-6 are
  worth fixing under *any* option, and finding 1 is a genuine correctness bug
  in the accident gate itself, not only in the adversary claim.

## Concrete work

### 1. Fix finding 1 — it is an accident-gate bug, not just an adversary hole

`_looks_harness_failure` (`red_gate.py:1384-1403`): delete the
`if run.assertion_origin: return False` short-circuit so origin and markers are
**conjunctive**. A run is behavioral RED only when the probe reports
`assertion_origin` *and* no harness marker appears in the output.

Then in `cut_assertion_probe.py`, extend the probe event with the observed
exception's `__cause__` / `__context__` chain type names, and reject in
`red_gate` when the chain bottoms out in `ImportError`, `ModuleNotFoundError`,
`FileNotFoundError`, or `SyntaxError`. This is what actually catches the
issue's exploit 1, whose `AssertionError` is raised *from* an `ImportError`
handler and therefore carries `__context__`.

Note the ordering consequence: this makes a legitimate test that asserts on an
import failure (rare, but real) fail the gate. That is the correct default —
the escape hatch is an explicit harness decision, not a silent pass.

### 2. Fix findings 3-5

- Hoist the `_stdlib_unittest` origin check out of `_run_direct`
  (`cut_assertion_probe.py:367`) into `_run_unittest` (`:482`) and the pytest
  plugin path (`:430`). `_stdlib_unittest` currently has zero test references —
  add them in the same change.
- Move `import pytest` inside the quarantine: in the bootstrap
  (`red_gate.py:262-263`), import pytest while `sys.path` is still
  `[root, *trusted_path]`, or explicitly justify in a comment why the target
  path is required and add a subprocess-level shadow test for the pytest
  profile mirroring the existing unittest ones.
- Add a distinct `probe seam not invoked` refusal (maps to #542's
  `environment` category) so a future pytest that stops routing `__main__`
  through `_console_main` produces an accurate message instead of blaming the
  author's test.
- Replace `hookwrapper=True` (`cut_assertion_probe.py:441`) with
  `wrapper=True`; pluggy has deprecated the former.
- Extend `_EXCLUDED_SNAPSHOT_DIRS` (`red_gate.py:166-175`) with `.venv`,
  `venv`, `node_modules`, `.tox`, `.nox`, `.gradle`, `target`, `dist`,
  `build`, `.next`, `.turbo`. The measured 34%-of-entries figure is pure
  overhead hashed twice per validation, and its churn surfaces as a misleading
  "production-tree file changed during validation".

### 3. Fix finding 6 — split `red_gate.py`

Extract, in this order (each independently landable, each shrinking the next
diff):

| New module | Moves out of `red_gate.py` |
|---|---|
| `src/easy_cheese/shared/cut/snapshot.py` | `_hash_file` (`:1525`) … `_receipt_changes` (`:1736`) — the snapshot/differ subsystem |
| `src/easy_cheese/shared/cut/phase_token.py` | `_load_phase_plan` (`:2718`) … `_load_phase_token` (`:2839`) and `begin_phase` (`:2796`) |
| `src/easy_cheese/shared/cut/press_history.py` | `_read_press_history` (`:2080`) … `consume_press_boundary` (`:2477`) |

This is the same move the probe extraction already validated. It also makes
#542's `transaction.py` a thin caller rather than another reason to grow the
monolith.

### 4. Re-scope the claim in the ADRs

Amend `.hallouminate/wiki/adr/outer-tdd-gates-003.md` and `005.md` with an
explicit **Threat model** section:

> The `GateReceipt` certifies that the declared case failed via an
> `AssertionError`-typed exception, at the declared witness, under the declared
> runner, with an unchanged production tree. It is **not** an unforgeable
> causal witness: a hostile test author with arbitrary code execution in the
> test process can produce a passing receipt for behavior that does not exist.
> The gate's job is catching *accidents* — import typos, missing fixtures,
> harness crashes, stale witnesses — not resisting the agent it gates.

Do not quietly drop the adversarial framing; state the downgrade, so a future
reader knows the claim was narrowed deliberately.

### 5. Tests

`tests/python/test_cut_red_gate_adversarial.py`, exercising the real
subprocess seam:

- **Exploit 1 (laundering)** — the exact three-line `try/except ImportError:
  raise AssertionError(WITNESS)` case from the issue. Assert: no receipt
  written, refusal names the `ImportError` in the exception chain. This test
  **fails today**; it is the regression fence for item 1.
- **Exploit 2 (forgery)** — a case that locates the probe fd via
  `/proc/self/fd`, writes a well-formed event, and `os._exit(1)`s. Assert the
  *documented* behavior. Under B+ that is **accepted**, and the test's docstring
  must say so, citing the ADR threat model. A test that pins a known limitation
  as intended behavior is more honest than no test, and it will fail loudly if
  someone later claims the hole is closed.
- Shadow tests for the pytest profile mirroring the existing unittest ones
  (finding 3).
- A snapshot test asserting a `.venv/` directory contributes zero entries
  (finding 5).

## Tradeoffs

- **B+ narrows a shipped promise.** Five accepted ADRs (`outer-tdd-gates-001`
  … `005`) and #396 describe a stronger property than the code delivers.
  Narrowing the ADR is the honest move; the alternative is leaving accepted
  design docs describing a property with two verified counterexamples.
- **Item 1 will produce new refusals during soak.** That is the point, but it
  will look like a regression in `next`'s receipt-issuance rate. Ship it with
  #542's refusal categories so the new refusals are attributable rather than
  mysterious.
- **Item 3 is churn with no behavior change.** Sequence it after items 1-2 so
  the security fixes land in reviewable diffs against the file everyone knows,
  not against three fresh modules.
- **If the release owner decides `next` is not soaking toward a merge**, then C
  applies to `next` too and items 1-3 are wasted effort. Get that decision
  before starting.
