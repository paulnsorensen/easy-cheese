# Issue #542 — suggestions

`perf(cut): collapse RED-gate authoring choreography behind one host-owned transaction`

## Channel

**This is a `next`-channel issue. Do not implement it on `main`.**

PR #560 removed the `/cut` skill and the RED-gate enforcement machinery from
`main`; `main` ships no `skills/cut/`, no `skills/cut/scripts/cut.pyz`, and no
`src/easy_cheese/shared/cut/`. Every file this proposal touches exists only on
the `next` soak branch. Retag to a next-channel label (see
[Retagging](#retagging-all-five)).

All line numbers below are against `origin/next` as of `bab83ce4`'s fetch.

## What the machinery actually looks like today

The agent-facing surface is four subcommands dispatched from
`red_gate.main` (`src/easy_cheese/shared/cut/red_gate.py:3419-3466`):

| Command | Host function |
|---|---|
| `red-gate contracts <spec>` | `_parse_spec` (`red_gate.py:538`) |
| `red-gate begin <plan> --out <token>` | `begin_phase` (`red_gate.py:2796`) |
| `red-gate issue <candidate> --token <t> --out <r>` | `issue_gate` (`red_gate.py:3220`) |
| `red-gate validate <receipt> --state red\|green` | `validate_gate` (`red_gate.py:1941`) |

`skills/cut/SKILL.md` steps 3-8 are the choreography the issue is measuring.
Steps 5 ("copy the token's exact baseline command identities into the
candidate"), 6 ("write only the oracle"), and 8 ("build the candidate under
`.cheese/cut/candidates/` with the frozen pre-Cut `baseline_checks`, phase token
ref and digest, protected test digests, and zero initial guards") are the three
that are entirely host-computable and are currently agent-authored.

## Proposal

### 1. One new module, not a bigger `red_gate.py`

Add `src/easy_cheese/shared/cut/transaction.py`. Do **not** grow
`red_gate.py` — it is already 3,468 lines and #457 finding 6 asks for the
opposite direction. The transaction is a *caller* of the existing host
functions, never a second receipt writer:

```text
_parse_spec  ->  synthesize _PhasePlan  ->  begin_phase  ->  install oracle drafts
             ->  _run_case replay       ->  build candidate  ->  issue_gate
```

`issue_gate` (`red_gate.py:3220`) stays the only code path that writes a
`GateReceipt`. This is the invariant that keeps acceptance criterion
"production mutation, harness failures, unsupported assertion origins, and
witness mismatches still issue no receipt" free.

### 2. New subcommand, old ones retained

In `red_gate.main` (`red_gate.py:3419`) add:

```text
red-gate cut <semantic-input.json> --out .cheese/cut/<slug>.json
```

Keep `contracts` / `begin` / `issue` / `validate` registered and documented as
diagnostics only (issue's proposed change 6). Nothing in Cook's preflight
(`skills/cook/SKILL.md:38-45`) needs to change: it still consumes the same
phase-neutral receipt at the same path.

### 3. Semantic-input schema — the only public surface

`<semantic-input.json>` carries agent judgment and nothing else:

| Field | Why it is judgment, not mechanics |
|---|---|
| `spec` | The approved spec path |
| `production_paths` | The roots Cook may change — a scoping decision |
| `runner`, `cwd`, `selectors` | Which existing project runner and seam |
| `oracle_drafts` | Path + content for each test-only oracle file |
| `adopted_reproduction` | Set instead of `oracle_drafts` when adopting a Pasteurize repro |
| `harness_decision` | The explicit halt/proceed when no supported runner profile exists |

Everything the SKILL.md currently asks for and this schema omits —
`schema_version`, `producer`, `work_id`, `project_key`, baseline identities,
`phase_token_ref`, `phase_token_sha256`, protected-file digests, `guards: []`,
receipt-level mode — is derived by `transaction.py`. That is the whole
performance claim.

Reject `oracle_drafts` entries whose path is not test-side per
`_is_test_side_path` (`red_gate.py:3040`) *before* calling `begin_phase`, so a
production-targeting draft costs one refusal instead of a full begin/replay
cycle. See #425 for the placement rule those paths should also satisfy.

### 4. N/A fast path

When `_parse_spec` returns `GateDisposition.NOT_APPLICABLE`, skip
`begin_phase`, oracle install, and replay entirely; build a candidate with no
`baseline_checks`, no cases, no protected files, no guards, and no
receipt-level mode, and call `issue_gate` directly. The validation that keeps
this honest already exists (`red_gate.py:668-688`: "not-applicable receipts
cannot carry Test Contracts", "not-applicable requires a non-empty reason").

### 5. Typed refusal categories

Today every failure funnels through `GateValidationError` and
`_print_problems` (`red_gate.py:3414`), which prints prose. Add a `category`
field to `GateValidationError` and have `red-gate cut` emit
`{"ok": false, "category": ..., "problems": [...]}` on stdout with the five
categories the issue names:

| Category | Source |
|---|---|
| `semantic` | witness mismatch, wrong assertion origin, contract/AC mismatch |
| `harness` | `_looks_harness_failure` (`red_gate.py:1384`) true |
| `environment` | `run.error`, exit 127, unresolvable runner, unsafe argv (`_validate_argv`, `:882`) |
| `integrity` | stale token/digest, production-tree change, `_protected_errors` (`:1536`), receipt drift |
| `authoring` | malformed semantic input, non-test-side oracle draft, missing `gate_applicability` |

This is what makes the issue's "retries need cause classification" finding
measurable, and it is the cheapest item on the list — wire it first.

### 6. Telemetry

Append one JSON line per invocation to `.cheese/cut/telemetry.jsonl`:
`{work_id, disposition, wall_ms, host_command_count, refusal_category,
oracle_origin: "generated"|"adopted", receipt_issued}`. `.cheese` is already in
`_EXCLUDED_SNAPSHOT_DIRS` (`red_gate.py:166-175`), so writing there cannot
perturb the production-tree fingerprint. This is what the issue's "reassess
after at least 20 top-level invocations" criterion needs.

### 7. Prose

Collapse `skills/cut/SKILL.md` steps 3-8 into one transaction step; move the
current step-by-step into `skills/cut/references/gate-workflow.md` as the
diagnostic appendix (it already carries the detailed event order per
`SKILL.md:110`).

## Tests

New `tests/python/test_cut_red_gate_transaction.py`, driving the real
subprocess seam (no mocks — matches the existing suites' style):

- production mutation staged between `begin` and replay -> no receipt at the
  `--out` path, category `integrity`
- an `ImportError`-only oracle draft -> no receipt, category `harness`
- an oracle whose failure text does not match the declared witness -> no
  receipt, category `semantic`
- N/A spec -> receipt exists with empty `baseline_checks`, `cases`,
  `protected_files`, `guards`, and no receipt-level mode
- baseline capture ordering: assert the recorded baseline exits are `0` and
  that the snapshot digest in the phase token predates the oracle file's
  existence (this is acceptance criterion "GREEN is captured before the oracle
  is installed" and it is the one that is easy to silently break)

The existing oracle-sensitivity suites (`tests/python/test_cut_skill_contract.py`,
`test_cut_assertion_probe.py`, `test_cut_spec_format_tracers.py`) must stay
green unchanged — that is the regression fence for "existing oracle-sensitivity
tests continue rejecting ...".

## Tradeoffs and risks

- **Auditability vs. ergonomics.** Hiding token and digest plumbing makes the
  integrity boundary less visible at the agent surface. Given #457's two
  *verified* exploits, land #457's fixes first or concurrently — otherwise this
  issue ships a smoother path to a gate whose adversarial claim is known-broken.
- **`transaction.py` becomes a trust boundary.** It assembles the candidate
  that `issue_gate` then validates. Keep it dumb: it may only copy values that
  `begin_phase` printed and digests it computed from files on disk. Any
  "helpful" normalization inside it is a new forgery surface.
- **Sequencing with #546.** Cook's bundled preflight (#546) should call
  `red-gate cut`, not re-implement it. Land #542 first; #546's "Cut is invoked
  at most once" criterion is trivial once Cut is one command.
- **YAGNI check on the diagnostics commands.** Four low-level commands plus one
  transaction is five entrypoints for one workflow. If the diagnostics
  commands see no use during soak, delete them rather than maintaining both.

## Effort

Medium. ~400-600 lines of new module + tests, no change to the validated
invariants. The refusal-category work (item 5) is independently shippable in
well under a day and unblocks the measurement the issue's own acceptance
criteria depend on.

## Retagging all five

#542, #546, #457, #425, and #401 all describe machinery that exists only on
`next`. The repo has no channel label today (`gh label list` shows only
`triage/*`, `bug`, `enhancement`, and routine-artifact labels). Create one —
`channel/next`, "Applies only to the next soak branch, not main" — and apply it
to all five, so `main` triage sweeps stop surfacing them as actionable.
