---
name: cut
description: Establishes protected, test-only RED evidence for observable behavior before Cook changes production. Use when the user invokes `/cut`, Mold hands off an approved behavior spec, Cook has no valid GateReceipt, or a user/Pasteurize reproduction needs adoption; do not use for closed non-behavior work or Press hardening.
license: MIT
---

# /cut

`/cut` is the outside-in evidence phase between Mold and Cook. It proves that
an approved observable behavior is GREEN in the current project, then fails at
the declared outer seam for the declared witness. It never implements the
behavior. The receipt is the durable boundary; the test and fixture files named
by that receipt are protected from production edits.

## Contract

```text
cut(spec_ref, reproduction? = null, auto = false) -> GateReceipt
```

Resolve every validator invocation through
[`references/gate-workflow.md`](references/gate-workflow.md) § Packaged command
resolution. A bare `red-gate` binary is not installed.

Trigger Cut explicitly, from Mold's approved `red-required` handoff, or from a
Cook preflight that has no valid receipt. Read the durable spec and its gate
metadata; do not infer applicability from prose. A behavior item must have at
least one Test Contract. A legacy spec without the table may proceed without a
new approval, but Cut must stamp every resulting contract
`contract_source: inferred` in the evidence.

Cut owns only test-side files: outer tracers, mechanically justified
contract-matrix cases, fixtures, and test-only harness support. It may adopt a
qualifying user/Pasteurize reproduction after normalizing it to the approved
seam, argv, cwd, and witness. Adopted cases carry `producer: cut` and
`origin: adopted`; generated cases carry `origin: generated`.

## Flow

1. **Resolve and classify.** Read the spec, then run `red-gate contracts
   <spec>`. Preserve approved interface, seam, expected failure, and mode
   exactly. Legacy inference is visible in the returned plan and needs no
   re-approval. Validate `gate_applicability` before selecting a runner.
2. **Close N/A early.** A Mold-approved `not-applicable` declaration for one
   closed class (`docs-only`, `refactor-only`, `test-only`, or
   `appearance-only`) produces a non-empty reason and no RED contracts,
   baseline checks, cases, protected files, guards, or receipt-level mode. It
   still goes through `red-gate issue`.
3. **Choose the seam and declare the phase.** Reuse the project's existing
   runner and conventions. Functional UI reuses the declared browser/E2E seam.
   If no project or standard-library runner is available, halt with an explicit
   harness decision; never install or invent a third-party runner. Write a
   strict phase plan under `.cheese/cut/` with `schema_version`, `producer`,
   `work_id`, `project_key`, the exact project-relative `production_paths`
   Cook may change, and baseline entries containing only `id`, `argv`, and
   project-relative `cwd`. Everything outside those roots is an immutable
   oracle dependency unless Cut adds it as a protected test file.
4. **Begin before the oracle.** Before creating or adopting a new oracle, call:

   ```text
   red-gate begin .cheese/cut/<slug>.plan.json --out .cheese/cut/<slug>.phase.json
   ```

   `begin` runs every broad baseline in order, requires exit `0`, and freezes
   the full project snapshot. Its printed `phase_token_ref` and
   `phase_token_sha256` are mandatory candidate fields. A missing baseline,
   unsafe argv, non-zero exit, stale output path, or uninspectable filesystem
   halts without a token. Never hand-write or reuse a phase token.
5. **Freeze the baseline evidence.** Copy the token's exact baseline command
   identities into the candidate and record each observed exit as `0`.
   Baseline argv must exclude the protected RED-oracle paths or remain green
   with the oracle present, because receipt validation replays them after
   oracle creation. Do not recapture the baseline after writing the oracle.
6. **Write only the oracle.** Add one outer tracer per behavioral curd, or a
   complete matrix only when a ratified/versioned interface mechanically
   derives every named row. A matrix contract declares `interface_version` and
   unique `matrix_rows`; its receipt binds exactly one contract case to each
   row. Do not change production files, add production stubs/adapters, or
   require a commit.
7. **Prove RED.** Replay each selected case through its declared argv (never
   shell evaluation). The case must fail for its assertion witness. Collection,
   import, dependency, fixture, syntax, or other harness failures are not a
   behavioral RED. Recheck the production-tree fingerprint after the run.
   Assertion-origin proof is available only for direct Python scripts/`-c`,
   `python -m pytest`, and `python -m unittest`. An existing runner outside
   those profiles requires an explicit harness decision; never infer RED from
   its rendered traceback or exit text.
8. **Issue canonical evidence.** Build the candidate under
   `.cheese/cut/candidates/` with the frozen pre-Cut `baseline_checks`, phase
   token ref and digest, protected test digests, and zero initial guards, then
   call exactly:

   ```text
   red-gate issue <candidate> --token .cheese/cut/<slug>.phase.json --out .cheese/cut/<slug>.json
   ```

   `red-gate issue` is the only receipt writer. It verifies that every
   post-token project change is an exact protected test-side path before
   replaying. Never hand-write or publish raw GateReceipt JSON. A changed
   production tree, harness-only failure, stale digest or token, missing
   baseline, unsafe argv, or witness mismatch leaves no successful receipt.
9. **Handoff.** After issue succeeds, write the small handoff projection and
   pass the receipt to Cook. In `--auto`, dispatch Cook once with that receipt.
   In synchronous Cook preflight, return the receipt to the caller and do not
   recursively dispatch Cook.

The detailed event order, candidate fields, refusal rules, and dirty-tree
fingerprinting live in [`references/gate-workflow.md`](references/gate-workflow.md).

## Receipt invariants

A RED receipt has `producer: cut`, non-empty contracts, frozen pre-Cut
`baseline_checks`, RED cases, and protected test-side file digests. Each
`baseline_checks` entry is the broad project result captured before the oracle;
its `id`, `argv`, `cwd`, and `observed_exit_code` are immutable receipt
evidence, not a Cook-owned recapture. The receipt also carries the exact
`phase_token_ref` and `phase_token_sha256` emitted before the oracle; Cook
validates that entry proof rather than trusting an issue-time snapshot. Initial
Cut receipts have `guard_receipt_refs: []`; guards belong to later Press evidence.
Each ordinary behavioral curd owns one tracer. A contract matrix is allowed
only for a ratified/versioned interface: the contract records its non-empty
`interface_version` and unique `matrix_rows`, and its RED evidence contains
exactly one `kind: contract` case for each named `matrix_row`. A receipt may mix
tracer and matrix modes because mode belongs to each Test Contract. The active
case origin remains `generated` or `adopted`.

A dirty worktree is safe: preserve the pre-existing delta, add only the oracle
files, and do not create a RED-only commit. A production digest change, a
harness-only failure, or a missing GREEN baseline blocks issuance. An
unavailable runner blocks for a harness decision rather than adding a
third-party dependency.

## Handoff

Write `.cheese/cut/<slug>.md` with this minimum shape only after the canonical
receipt exists:

```text
status: ok
next: cook
artifact: .cheese/cut/<slug>.json
```

The canonical receipt is the handoff's baseline carrier: Cook must consume its
frozen `baseline_checks` exactly and must not overwrite or recapture them.

The orientation line may explain the selected contracts and runner. A blocked
attempt uses `halt: <reason>` and does not claim `next: cook`.

## Discipline

**Iron Law:** No successful Cut RED receipt without a GREEN baseline and a
test-only protected RED oracle issued by `red-gate issue`.

**Red Flags** — stop if you notice these:

- production code changed while the tracer is being written;
- the first run fails during collection, import, fixture setup, or dependency loading;
- a test is failing before the baseline was recorded;
- a missing runner is being solved by adding a dependency;
- a RED-only commit is being proposed;
- the candidate is being serialized directly as the published receipt;
- synchronous Cook is being called recursively from its Cut preflight.

| Rationalization | Why it fails | Required action |
| --- | --- | --- |
| “I can add the outer test after Cook implements it.” | That removes independent evidence of the pre-implementation failure. | Establish GREEN before creating the oracle, then prove RED, before any production edit. |
| “A collection crash is close enough to RED.” | A harness failure does not test the approved behavior or witness. | Fix or report the harness; issue nothing. |
| “The runner is missing, so I will install a convenient framework.” | Cut cannot silently alter the target project's toolchain. | Halt for an explicit harness decision. |
| “The worktree is already dirty, so a commit makes the receipt safer.” | The receipt protects digests; a RED-only commit is not part of the contract. | Fingerprint the pre-existing delta and leave history untouched. |
| “A hand-written receipt has all the fields.” | Raw JSON can bypass replay, digest, guard, and canonicalization checks. | Route every candidate through `red-gate issue`. |
| “Cook called Cut, so Cut should call Cook back.” | Recursive chaining can loop and loses ownership of the preflight boundary. | Return the receipt synchronously; only `--auto` dispatches Cook. |

## Pressure gate

A failing pre-skill pressure run is required before this workflow is treated as
durable. The scenario and oracle-sensitivity mutations are in
[`references/pressure-eval.md`](references/pressure-eval.md); AC-12 is covered
by `tests/python/test_cut_pressure_eval.py`.

## Pipeline

`culture → mold → **cut** → cook → press → age → cure → plate`
