# Cut gate workflow

This reference is the executable-minded companion to `/cut`. The phase owns
an outer oracle, not implementation. The validator in `red-gate` owns receipt
semantics and is the only supported receipt-writing boundary.

## Packaged command resolution

Resolve the validator once as an argv prefix and append every documented
`red-gate` subcommand/argument to it:

1. Installed sibling skills: `python3
   ${CLAUDE_SKILL_DIR}/../cut/scripts/cut.pyz red-gate`.
2. Source checkout fallback: `python3 skills/cut/scripts/cut.pyz red-gate`.

The first path works from Cut, Cook, and Press because each receives its own
`CLAUDE_SKILL_DIR`. Halt if neither bundle exists; a bare `red-gate` executable
is not installed. Every `red-gate ...` example in these skills is shorthand
for the resolved argv prefix, never a PATH lookup.

## Inputs and provenance

Resolve the approved durable spec pointer and identify the current `work_id`
and sanitized `project_key`. Run:

```text
red-gate contracts <spec>
```

The plan is authoritative for the chosen interface, outer seam, expected
failure, and per-contract mode. A table-backed contract has
`contract_source: approved`. A legacy acceptance criterion without a table is
inferred once, with `contract_source: inferred` retained in every emitted
contract. Never rewrite the legacy spec merely to make inference look
approved.

A reproduction supplied by the user or Pasteurize is an input, not a receipt.
Normalize its command to an argv list, its cwd to a project-relative path, its
outer seam to the approved contract, and its output to the declared witness.
Use `origin: adopted` only after the normalized case passes the baseline and
fails for that witness. If the reproduction cannot be normalized without
changing the approved seam, halt and name the ambiguity.

## Applicability closure

Validate the Mold declaration before creating a test file:

| declaration | Cut action |
| --- | --- |
| `red-required` + `behavior` + one or more contracts | Continue with RED evidence. |
| `not-applicable` + `docs-only` | Issue closed N/A evidence with a docs reason. |
| `not-applicable` + `refactor-only` | Issue closed N/A evidence with a refactor reason. |
| `not-applicable` + `test-only` | Issue closed N/A evidence with a test reason. |
| `not-applicable` + `appearance-only` | Issue closed N/A evidence with an appearance reason. |
| any contradictory declaration, closed class with contracts, or behavior without contracts | Halt; do not infer applicability from prose. |

The N/A candidate contains no contracts, baseline checks, cases, protected
files, guards, or gate mode and carries a non-empty `not_applicable_reason`.
It is still sent to `red-gate issue`; Cut does not write an N/A receipt itself.

## Runner and seam selection

Prefer, in order:

1. the target project's existing runner and its established selector syntax;
2. a Python 3.12 standard-library runner already present in the target;
3. an explicit harness decision when neither is available.

Do not add pytest, a browser framework, a mutation framework, or any other
third-party dependency from Cut. A functional UI is ordinary behavior: use the
browser/E2E interface already named by Mold. An appearance-only UI is closed
N/A, not a reason to invent a screenshot runner.

Commands are argv arrays with no shell interpolation. Keep test files,
fixtures, and test-only harness adapters inside the project's test surface.
A harness import/collection crash, syntax failure, missing dependency, broken
fixture, or unrelated runner error is a blocker, not a declared behavior RED.

Assertion-origin proof has validated adapters for direct Python scripts/`-c`,
`python -m pytest`, and `python -m unittest`. Any other existing runner is
unsupported by the packaged proof channel and therefore requires an explicit
harness decision. Do not treat rendered traceback text, framework output, or a
non-zero exit alone as assertion-origin evidence.

## Evidence sequence

Record the pre-existing dirty-worktree delta before phase entry. The phase
token freezes that exact starting tree, so only declared protected test-side
additions may appear before issue; preserve unrelated user edits byte-for-byte.

For each selected behavior curd:

1. Choose the available runner and selector from the declared seam. Write the
   strict `.cheese/cut/<slug>.plan.json` before creating the oracle. Its
   `production_paths` are the exact project-relative roots Cook may mutate;
   they cannot be the project root, overlap one another, or overlap a
   protected oracle. Every path outside those roots is frozen as an oracle
   dependency.
2. Run `red-gate begin <plan> --out .cheese/cut/<slug>.phase.json`. It executes
   all baseline argv arrays in their declared cwd, requires exit code `0`, and
   freezes the pre-oracle project tree. If no token is emitted, remove no user
   work and halt without issuing evidence.
3. Write the smallest outer tracer at the approved seam. Use a full matrix only
   when every case is mechanically derived from a ratified interface version,
   schema, or protocol. Declare the version and unique matrix row identities,
   then bind exactly one contract case to each row. Mixed tracer/matrix receipts
   are valid. Do not change production files.
4. Run each selected `RedCase` once. Its assertion must fail with one of the
   declared `expected_witness` tokens and a normal test exit; collection or
   harness failure is not enough.
5. Re-snapshot the project. Any change other than a newly added exact protected
   test-side file is a Cut refusal. Test-side files become `ProtectedFile`
   claims with their SHA-256 digests; declared production roots remain frozen
   throughout Cut.
   Directory symlinks are unsupported and halt phase snapshotting rather than
   following a tree outside the project.
6. Set `producer: cut`, `disposition: red`, `guard_receipt_refs: []`, and copy
   the exact phase-token ref, digest, baseline commands, and observed zero exits.
   Preserve the spec digest, project key, contract provenance, case origin, and
   observed evidence. Do not invent guards for an initial receipt.
   Every observed exit code must be `0`.
7. Send the candidate through the one writer:

   ```text
   red-gate issue <candidate> --token .cheese/cut/<slug>.phase.json --out .cheese/cut/<slug>.json
   ```

   The command verifies phase identity and the exact post-token test-side
   changes, replays GREEN baselines and RED cases, checks protected digests,
   canonicalizes observed witness data, and atomically emits the receipt. A
   short-lived candidate input belongs under `.cheese/cut/candidates/`; it is
   not the published artifact.
8. Write `.cheese/cut/<slug>.md` with `status: ok`, `next: cook`, and the exact
   receipt artifact pointer only after `issue` succeeds.

The successful sequence is therefore:

```text
contracts → select/infer → choose runner → red-gate begin/baseline GREEN
→ test-only oracle → declared RED → protected digests → token-bound issue
→ Cook handoff
```

No step may be reordered around a production edit. Cook consumes the receipt
and replays `red-gate validate <receipt> --state red` before changing
production. That implementation preflight belongs to Cook; Cut only hands off.

## Refusal matrix

| observed condition | result |
| --- | --- |
| production digest changed during Cut | halt; no successful receipt |
| baseline is missing or non-zero | halt; no successful receipt |
| case fails only in collection/import/fixture/dependency setup | halt as harness failure |
| witness is absent or assertion is not deterministic | halt for a contract/seam decision |
| runner is unavailable | halt for explicit harness decision |
| candidate contains an initial Cut guard | `red-gate issue` rejects it |
| candidate is hand-written/published without `issue` | not a valid Cut artifact |
| dirty worktree has unrelated edits | preserve them; add only test-side files; never commit |
| approved closed non-behavior declaration | issue closed N/A; no RED evidence |

## Auto and synchronous handoff

`/cut --auto <spec>` runs the same evidence sequence, writes the canonical
receipt, and dispatches Cook once with the receipt pointer and relevant flags.
The dispatch is downstream handoff, not a recursive Cut/Cook call.

When Cook invokes Cut as a synchronous preflight, Cut runs with `auto = false`
and returns the validated `GateReceipt` to that caller. It does not dispatch
Cook from inside the preflight. Cook then owns the first production mutation
only after replaying the active RED receipt.

A failed Cut returns a precise `halt:` reason and no `next: cook`. A successful
Cut always leaves the handoff projection beside the receipt; the projection is
not an alternate authority.
