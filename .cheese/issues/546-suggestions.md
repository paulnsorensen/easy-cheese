# Issue #546 — suggestions

`perf(cook): collapse GateReceipt preflight and make oracle-change routing explicit`

## Channel

**This is a `next`-channel issue. Do not implement it on `main`.**

PR #560 removed RED-gate enforcement from `main`. `main`'s `/cook` has no
GateReceipt preflight at all — `skills/cook/SKILL.md` on `main` carries no
`red-gate` invocation, and `src/easy_cheese/skills/cook/commands.py` on `main`
packages no `red-gate` command. The preflight this issue optimizes exists only
on `next`. Retag to a next-channel label (see #542's suggestions for the
label proposal).

## What the preflight actually is today

On `next`, Cook resolves `red-gate` through its own bundle
(`skills/cook/SKILL.md:34-36`: `python3 skills/cook/scripts/cook.pyz red-gate
...`), and the preflight is prose-driven across
`skills/cook/SKILL.md:38-45` and `:73-83`:

1. Load the canonical receipt at `.cheese/cut/<slug>.json`.
2. If absent, invoke Cut once.
3. Classify RED vs. closed N/A.
4. `red-gate validate <receipt> --state red` (`validate_gate`,
   `src/easy_cheese/shared/cut/red_gate.py:1941`).
5. No production path may run before that returns ok.

Every one of those five is deterministic. None requires agent judgment. That
is the issue's finding, and it is correct.

## Proposal

### 1. One bundled preflight command

Add `src/easy_cheese/skills/cook/gate_preflight.py` and register it in
`src/easy_cheese/skills/cook/commands.py` alongside the existing
`Command(...)` tuple entries:

```python
Command("gate-preflight", "easy_cheese.skills.cook.gate_preflight:main"),
```

```text
cook.pyz gate-preflight --spec <spec> --slug <slug> [--production-paths ...]
```

Typed stdout result, one of:

| `status` | Meaning | Cook's next move |
|---|---|---|
| `red` | Valid RED receipt, replayed | Implement against the named cases |
| `not-applicable` | Closed N/A receipt | Implement; no RED to satisfy |
| `oracle-overlap` | Intended change targets a protected oracle | Halt once, actionably |
| `failed` | Terminal | Halt; do not mutate production |

`failed` carries the same refusal categories #542 proposes
(`semantic` / `harness` / `environment` / `integrity` / `authoring`) so both
skills classify identically. Wire #542's categories first; this issue consumes
them rather than defining a parallel vocabulary.

### 2. Internal ownership, exactly-once Cut

`gate_preflight.main` owns: canonical-receipt load, the single Cut dispatch
when absent, `validate_gate(receipt, "red")`, and error classification. Making
Cut invocation an internal call rather than an agent step is what mechanically
satisfies "Cut is invoked at most once" — a prose instruction cannot.

Once #542 lands, that internal call is `red-gate cut <semantic-input> --out
...`. Until then it is the four-step choreography, wrapped. **Prefer to land
#542 first**; wrapping the four-step version means writing candidate-assembly
logic in Cook that #542 then deletes.

### 3. Oracle-overlap routing — the actually novel part

This is the finding worth the most, and it needs a mechanism the codebase
does not have yet.

The invariant: `issue_gate` records protected test digests, and
`_protected_errors` (`red_gate.py:1536`) rejects any post-receipt change to
them. Work that legitimately targets a would-be oracle collides with that
*after* production mutation has already begun — which is the churn the issue
describes.

Move the collision earlier. Before receipt issuance, intersect the intended
change surface with the would-be oracle surface:

- The intended surface is Cook's `production_paths` (already declared in the
  Cut phase plan per `skills/cut/SKILL.md:53-58`), plus any test-side path
  Cook plans to modify.
- The oracle surface is every path `_is_test_side_path` (`red_gate.py:3040`)
  accepts within the spec's blast radius.

On a non-empty intersection, emit `status: "oracle-overlap"` with the
colliding paths and exactly two documented resolutions:

1. **Independent outside-in evidence** — the oracle moves to a seam strictly
   outside the intended change surface. Preflight re-runs against the narrowed
   surface.
2. **Halt once** — typed `no-independent-oracle` result naming the paths.
   Route to `/mold` to re-scope, not to a retry loop.

Never a third option. In particular: preflight must never refresh, substitute,
or recompute `phase_token_sha256`, protected-file digests, or the receipt
token. Enforce that structurally — `gate_preflight` imports `validate_gate`
and the loaders, and must not import `issue_gate`, `begin_phase`, or
`_atomic_write` (`red_gate.py:3380`). Assert the import boundary in a test.

### 4. Stage telemetry

Emit one JSONL record per Cook run to `.cheese/cook/telemetry.jsonl` with
`{slug, preflight_ms, implementation_ms, green_ms, taste_test_ms, handoff_ms,
preflight_round_trips, refusal_category}`. `.cheese` is in
`_EXCLUDED_SNAPSHOT_DIRS` (`red_gate.py:166-175`), so this cannot perturb the
production-tree fingerprint that Cut's validation replays.

Without this, the issue's own acceptance criterion — "after at least 20
post-change invocations, preflight round-trips decrease without error-rate
regression" — is unmeasurable. Its "Low" finding is really a blocker on
proving the other two.

## Tests

New `tests/python/test_cook_gate_preflight.py`, at the real seam:

- missing receipt -> Cut dispatched exactly once (assert via a recorded
  invocation log, not a mock of the module under test) -> `status: "red"`
- invalid receipt (tampered digest) -> `status: "failed"`,
  `category: "integrity"`, and the on-disk receipt is byte-unchanged
- closed N/A receipt -> `status: "not-applicable"`, no Cut dispatch
- adopted-reproduction receipt -> `status: "red"`
- baseline replay failure -> `status: "failed"`, `category: "harness"`
- intended change surface overlapping a protected oracle path ->
  `status: "oracle-overlap"` listing exactly the colliding paths, and **no
  production file written**
- import-boundary test: `gate_preflight`'s module namespace exposes no
  `issue_gate` / `begin_phase` / `_atomic_write`

Existing RED, adopted-reproduction, guard, witness, GREEN, and N/A suites must
stay green unchanged.

## Tradeoffs and risks

- **Ordering dependency on #542.** Real, and worth respecting. Implementing
  #546 first duplicates candidate assembly in Cook, then throws it away.
- **Overlap detection can be wrong in both directions.** A false positive
  halts legitimate work; a false negative restores today's churn. Bias to
  false positives (halt) — the halt is one actionable message, the false
  negative is silent corruption of the evidence chain. Say so in the docs.
- **Scope discipline.** The issue's non-goals are sound and easy to violate:
  do not optimize legitimate implementation test/build calls, do not let Cook
  retry Cut implicitly, do not let Cook repair evidence. The import boundary
  in item 3 is the cheapest enforcement of the last one.
- **12 invocations is thin evidence.** The oracle-change failures are reported
  operationally, not replayed. Build the fixtures in the test list above
  first; if none of them reproduce the reported failure, the diagnosis is
  wrong and the preflight rewrite is not the fix.

## Effort

Medium. Item 4 (telemetry) is a few hours and unblocks measurement. Item 3
(overlap routing) is the design-heavy piece and deserves its own review pass.
Items 1-2 are mostly mechanical once #542 exists.
